"""Statistics for research, observation and training data.

Input is a table given either as ``csv_path`` or as ``records`` (a list of dicts). Every test
returns the statistic, p-value, an effect size, the assumptions it made, and a one-line
plain-language reading, so the result can go straight into a methods/results section.
"""

from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any

from scipy import stats

Records = list[dict[str, Any]]


# ---------------------------------------------------------------- loading
def load_table(csv_path: str | None = None, records: Records | None = None) -> Records:
    if records:
        return records
    if not csv_path:
        raise ValueError("give csv_path or records")
    p = Path(csv_path).expanduser()
    with p.open(newline="", encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        return list(csv.DictReader(f, dialect=dialect))


def to_float(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return None if (isinstance(v, float) and math.isnan(v)) else float(v)
    s = str(v).strip().replace(" ", "")
    if not s or s.lower() in {"na", "nan", "null", "-", "n/a"}:
        return None
    if s.count(",") == 1 and s.count(".") == 0:  # Indonesian decimal comma
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def column(rows: Records, col: str) -> list[float]:
    if rows and col not in rows[0]:
        raise ValueError(f"column {col!r} not found; columns: {list(rows[0])}")
    return [x for x in (to_float(r.get(col)) for r in rows) if x is not None]


def _p(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def _r(x: float | None, nd: int = 3) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), nd)


# ---------------------------------------------------------------- descriptive
def describe(rows: Records, columns: list[str] | None = None, max_levels: int = 15) -> dict[str, Any]:
    if not rows:
        return {"n_rows": 0, "columns": {}}
    cols = columns or list(rows[0])
    out: dict[str, Any] = {}
    for c in cols:
        raw = [r.get(c) for r in rows]
        nums = [x for x in (to_float(v) for v in raw) if x is not None]
        missing = sum(1 for v in raw if v in (None, "") or (isinstance(v, str) and not v.strip()))
        if nums and len(nums) >= 0.8 * (len(raw) - missing):
            q = sorted(nums)
            n = len(q)
            quart = stats.mstats.mquantiles(q, prob=[0.25, 0.75]) if n > 1 else [q[0], q[0]]
            sw = stats.shapiro(q) if 3 <= n <= 5000 else None
            out[c] = {
                "type": "numeric",
                "n": n,
                "missing": missing,
                "mean": _r(mean(q)),
                "sd": _r(stdev(q)) if n > 1 else None,
                "median": _r(median(q)),
                "q1": _r(quart[0]),
                "q3": _r(quart[1]),
                "min": _r(q[0]),
                "max": _r(q[-1]),
                "normality_shapiro_p": _r(sw.pvalue) if sw else None,
            }
        else:
            cnt = Counter(str(v).strip() for v in raw if v not in (None, "") and str(v).strip())
            total = sum(cnt.values())
            out[c] = {
                "type": "categorical",
                "n": total,
                "missing": missing,
                "levels": len(cnt),
                "top": [
                    {"value": k, "n": v, "pct": round(100 * v / total, 1)} for k, v in cnt.most_common(max_levels)
                ],
            }
    return {"n_rows": len(rows), "columns": out}


# ---------------------------------------------------------------- group comparison
def compare_groups(rows: Records, group_col: str, value_col: str, parametric: bool | None = None) -> dict[str, Any]:
    groups: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        g, v = r.get(group_col), to_float(r.get(value_col))
        if g not in (None, "") and v is not None:
            groups[str(g).strip()].append(v)
    groups = {k: v for k, v in groups.items() if len(v) >= 2}
    if len(groups) < 2:
        raise ValueError(f"need at least two groups with n>=2 in {group_col!r}")
    summary = {
        k: {"n": len(v), "mean": _r(mean(v)), "sd": _r(stdev(v)), "median": _r(median(v))} for k, v in groups.items()
    }
    if parametric is None:  # decide from normality and sample size
        normal = all(len(v) >= 30 or (len(v) >= 3 and stats.shapiro(v).pvalue > 0.05) for v in groups.values())
        parametric = normal
    vals = list(groups.values())
    names = list(groups)
    res: dict[str, Any] = {"groups": summary, "parametric": parametric}
    if len(groups) == 2:
        a, b = vals
        if parametric:
            t = stats.ttest_ind(a, b, equal_var=False)
            sp = math.sqrt(((len(a) - 1) * stdev(a) ** 2 + (len(b) - 1) * stdev(b) ** 2) / (len(a) + len(b) - 2))
            d = (mean(a) - mean(b)) / sp if sp else float("nan")
            res.update(test="Welch t-test", statistic=_r(t.statistic), p_value=_r(t.pvalue, 5),
                       effect_size={"cohens_d": _r(d)}, mean_difference=_r(mean(a) - mean(b)))
        else:
            u = stats.mannwhitneyu(a, b, alternative="two-sided")
            rbc = 1 - 2 * u.statistic / (len(a) * len(b))
            res.update(test="Mann-Whitney U", statistic=_r(u.statistic), p_value=_r(u.pvalue, 5),
                       effect_size={"rank_biserial_r": _r(-rbc)})
    else:
        if parametric:
            f = stats.f_oneway(*vals)
            grand = mean([x for v in vals for x in v])
            ssb = sum(len(v) * (mean(v) - grand) ** 2 for v in vals)
            sst = sum((x - grand) ** 2 for v in vals for x in v)
            res.update(test="One-way ANOVA", statistic=_r(f.statistic), p_value=_r(f.pvalue, 5),
                       effect_size={"eta_squared": _r(ssb / sst if sst else float("nan"))})
        else:
            h = stats.kruskal(*vals)
            n = sum(len(v) for v in vals)
            eps = (h.statistic - len(vals) + 1) / (n - len(vals))
            res.update(test="Kruskal-Wallis H", statistic=_r(h.statistic), p_value=_r(h.pvalue, 5),
                       effect_size={"epsilon_squared": _r(eps)})
    sig = res["p_value"] < 0.05
    res["reading"] = (
        f"{res['test']}: {value_col} {'differs' if sig else 'does not differ significantly'} between "
        f"{', '.join(names)} ({_p(res['p_value'])})."
    )
    res["assumptions"] = (
        "Parametric chosen because every group is n>=30 or Shapiro-Wilk p>0.05." if parametric
        else "Non-parametric chosen (or requested) because at least one group looks non-normal or is small."
    )
    return res


def paired_compare(rows: Records, before_col: str, after_col: str, max_score: float | None = None) -> dict[str, Any]:
    """Pre/post on the same subjects (one row per subject). Adds Hake's normalised gain when max_score is set."""
    pairs = [(to_float(r.get(before_col)), to_float(r.get(after_col))) for r in rows]
    pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
    if len(pairs) < 3:
        raise ValueError("need at least 3 complete pairs")
    pre, post = [p[0] for p in pairs], [p[1] for p in pairs]
    diff = [b - a for a, b in pairs]
    normal = len(diff) >= 30 or stats.shapiro(diff).pvalue > 0.05
    if normal:
        t = stats.ttest_rel(post, pre)
        sd = stdev(diff)
        res = {"test": "Paired t-test", "statistic": _r(t.statistic), "p_value": _r(t.pvalue, 5),
               "effect_size": {"cohens_dz": _r(mean(diff) / sd if sd else float("nan"))}}
    else:
        w = stats.wilcoxon(post, pre)
        z = stats.norm.isf(w.pvalue / 2)
        res = {"test": "Wilcoxon signed-rank", "statistic": _r(w.statistic), "p_value": _r(w.pvalue, 5),
               "effect_size": {"r": _r(z / math.sqrt(len(diff)))}}
    res.update(n=len(pairs), mean_before=_r(mean(pre)), mean_after=_r(mean(post)), mean_change=_r(mean(diff)),
               improved=sum(d > 0 for d in diff), worse=sum(d < 0 for d in diff), unchanged=sum(d == 0 for d in diff))
    if max_score:
        gains = [(b - a) / (max_score - a) for a, b in pairs if max_score - a > 0]
        g = mean(gains) if gains else None
        res["normalized_gain"] = {
            "mean_g": _r(g),
            "category": None if g is None else ("high" if g >= 0.7 else "medium" if g >= 0.3 else "low"),
            "rule": "Hake: g = (post - pre) / (max - pre); high >= 0.7, medium 0.3-0.7, low < 0.3",
        }
    res["reading"] = f"{res['test']}: mean change {res['mean_change']:+} ({_p(res['p_value'])})."
    return res


# ---------------------------------------------------------------- categorical
def crosstab(rows: Records, row_col: str, col_col: str) -> dict[str, Any]:
    table: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        a, b = r.get(row_col), r.get(col_col)
        if a not in (None, "") and b not in (None, ""):
            table[str(a).strip()][str(b).strip()] += 1
    rlev = sorted(table)
    clev = sorted({c for v in table.values() for c in v})
    if len(rlev) < 2 or len(clev) < 2:
        raise ValueError("need at least 2 levels in each column")
    m = [[table[a][b] for b in clev] for a in rlev]
    chi2, p, dof, expected = stats.chi2_contingency(m)
    n = sum(map(sum, m))
    v = math.sqrt(chi2 / (n * (min(len(rlev), len(clev)) - 1)))
    low_expected = sum(e < 5 for row in expected for e in row) / (len(rlev) * len(clev))
    res: dict[str, Any] = {
        "rows": rlev, "columns": clev, "counts": m, "n": n,
        "test": "Chi-square test of independence", "statistic": _r(chi2), "df": int(dof), "p_value": _r(p, 5),
        "effect_size": {"cramers_v": _r(v)},
        "share_cells_expected_below_5": _r(low_expected),
    }
    if len(rlev) == 2 and len(clev) == 2:
        odds, fp = stats.fisher_exact(m)
        res["fisher_exact"] = {"odds_ratio": _r(odds), "p_value": _r(fp, 5)}
        if low_expected > 0:
            res["test"] = "Fisher exact test (expected counts < 5)"
            res["p_value"] = _r(fp, 5)
    elif low_expected > 0.2:
        res["warning"] = "More than 20% of cells have expected count < 5: merge categories before trusting chi-square."
    res["reading"] = f"{res['test']}: association between {row_col} and {col_col} {_p(res['p_value'])}, Cramér's V {res['effect_size']['cramers_v']}."
    return res


def correlate(rows: Records, x: str, y: str, method: str = "auto") -> dict[str, Any]:
    pairs = [(to_float(r.get(x)), to_float(r.get(y))) for r in rows]
    pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
    if len(pairs) < 4:
        raise ValueError("need at least 4 complete pairs")
    xs, ys = zip(*pairs)
    if method == "auto":
        method = "pearson" if (len(xs) >= 30 or (stats.shapiro(xs).pvalue > 0.05 and stats.shapiro(ys).pvalue > 0.05)) else "spearman"
    r = stats.pearsonr(xs, ys) if method == "pearson" else stats.spearmanr(xs, ys)
    coef = float(r.statistic if hasattr(r, "statistic") else r[0])
    p = float(r.pvalue if hasattr(r, "pvalue") else r[1])
    strength = "very weak" if abs(coef) < 0.2 else "weak" if abs(coef) < 0.4 else "moderate" if abs(coef) < 0.6 else "strong" if abs(coef) < 0.8 else "very strong"
    lr = stats.linregress(xs, ys)
    return {
        "method": method, "n": len(xs), "coefficient": _r(coef), "p_value": _r(p, 5), "strength": strength,
        "linear_fit": {"slope": _r(lr.slope), "intercept": _r(lr.intercept), "r_squared": _r(lr.rvalue ** 2)},
        "reading": f"{method.title()} r = {coef:.2f} ({strength}, {'positive' if coef > 0 else 'negative'}), {_p(p)}; correlation is not causation.",
    }


def trend(rows: Records, time_col: str, value_col: str) -> dict[str, Any]:
    pts = sorted(
        (t, v) for t, v in ((to_float(r.get(time_col)), to_float(r.get(value_col))) for r in rows)
        if t is not None and v is not None
    )
    if len(pts) < 3:
        raise ValueError("need at least 3 points")
    ts, vs = zip(*pts)
    lr = stats.linregress(ts, vs)
    mk = stats.kendalltau(ts, vs)
    span = ts[-1] - ts[0]
    cagr = (vs[-1] / vs[0]) ** (1 / span) - 1 if span > 0 and vs[0] > 0 and vs[-1] > 0 else None
    return {
        "n": len(pts), "first": {"t": ts[0], "value": vs[0]}, "last": {"t": ts[-1], "value": vs[-1]},
        "slope_per_unit": _r(lr.slope), "r_squared": _r(lr.rvalue ** 2), "p_value": _r(lr.pvalue, 5),
        "mann_kendall_tau": _r(mk.statistic), "mann_kendall_p": _r(mk.pvalue, 5),
        "cagr": _r(cagr, 4),
        "direction": "rising" if lr.slope > 0 and mk.pvalue < 0.05 else "falling" if lr.slope < 0 and mk.pvalue < 0.05 else "no clear trend",
    }


# ---------------------------------------------------------------- agreement (observers)
def cohen_kappa(rows: Records, rater_a: str, rater_b: str) -> dict[str, Any]:
    pairs = [(str(r.get(rater_a)).strip(), str(r.get(rater_b)).strip()) for r in rows
             if r.get(rater_a) not in (None, "") and r.get(rater_b) not in (None, "")]
    if len(pairs) < 2:
        raise ValueError("need at least 2 rated items")
    n = len(pairs)
    cats = sorted({c for p in pairs for c in p})
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[c] * cb[c] for c in cats) / n**2
    k = (po - pe) / (1 - pe) if pe < 1 else 1.0
    band = ("poor" if k < 0 else "slight" if k <= 0.2 else "fair" if k <= 0.4 else "moderate" if k <= 0.6
            else "substantial" if k <= 0.8 else "almost perfect")
    return {"n_items": n, "categories": cats, "observed_agreement": _r(po), "expected_agreement": _r(pe),
            "kappa": _r(k), "interpretation": f"{band} (Landis & Koch 1977)"}


# ---------------------------------------------------------------- sample size
def sample_size(
    design: str,
    alpha: float = 0.05,
    power: float = 0.8,
    proportion: float | None = None,
    margin: float | None = None,
    population: int | None = None,
    p1: float | None = None,
    p2: float | None = None,
    effect_size_d: float | None = None,
    dropout: float = 0.0,
) -> dict[str, Any]:
    """design: 'proportion' (survey/prevalence: proportion, margin, optional population for FPC),
    'two_proportions' (p1, p2), 'two_means' (effect_size_d = Cohen's d)."""
    za = stats.norm.isf(alpha / 2)
    zb = stats.norm.isf(1 - power)
    if design == "proportion":
        p = 0.5 if proportion is None else proportion
        e = margin or 0.05
        n = za**2 * p * (1 - p) / e**2
        formula = "n = Z² p(1-p) / e² (Lemeshow)"
        if population:
            n = n / (1 + (n - 1) / population)
            formula += ", finite population correction"
        per = "total"
    elif design == "two_proportions":
        if p1 is None or p2 is None:
            raise ValueError("two_proportions needs p1 and p2")
        pb = (p1 + p2) / 2
        n = (za * math.sqrt(2 * pb * (1 - pb)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2 / (p1 - p2) ** 2
        formula, per = "Fleiss (two independent proportions)", "per group"
    elif design == "two_means":
        if not effect_size_d:
            raise ValueError("two_means needs effect_size_d")
        n = 2 * (za + zb) ** 2 / effect_size_d**2
        formula, per = "n = 2(Zα/2 + Zβ)² / d²", "per group"
    else:
        raise ValueError("design must be proportion, two_proportions or two_means")
    n_adj = n / (1 - dropout) if dropout else n
    return {"design": design, "n": math.ceil(n), "n_with_dropout": math.ceil(n_adj), "unit": per,
            "alpha": alpha, "power": power if design != "proportion" else None, "formula": formula}
