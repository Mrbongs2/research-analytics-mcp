"""Market sizing: two-way (demand x supply) model with low/base/high scenarios and a regional split.

Demand:  population x target share x need share x ability-to-pay share  -> addressable people
Supply:  providers x cases/yr (+ secondary providers x share doing it x cases/yr) -> cases/yr
Value:   cases x product mix x price per case
Check:   cases / addressable should be a few % a year; far outside that, an input is off.

Every input is {"value": <number or {low, base, high}>, "source": "..."}; a value without a
source is rejected so that assumptions never pass as data.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

SCEN = ("low", "base", "high")
REQUIRED = ("population", "target_share", "need_share", "ability_to_pay_share", "providers", "cases_per_provider")


def _val(x: Any, k: str) -> float:
    return float(x[k] if isinstance(x, dict) else x)


def _num(entry: dict[str, Any], k: str) -> float:
    return _val(entry["value"], k)


def example_assumptions() -> dict[str, Any]:
    return json.loads(resources.files(__package__).joinpath("data/assumptions_orthodontics_id.json").read_text("utf-8"))


def validate(A: dict[str, Any]) -> list[str]:
    problems = []
    for k in REQUIRED:
        if k not in A:
            problems.append(f"missing input '{k}'")
    for k, v in A.items():
        if k.startswith("_") or k == "products":
            continue
        if not isinstance(v, dict) or "value" not in v:
            problems.append(f"'{k}' must be {{value, source}}")
        elif not str(v.get("source", "")).strip():
            problems.append(f"'{k}' has no source (write 'Assumption: ...' if it is one)")
    for p, v in (A.get("products") or {}).items():
        if not str(v.get("source", "")).strip():
            problems.append(f"product '{p}' has no source")
    return problems


def market_model(A: dict[str, Any]) -> dict[str, Any]:
    problems = validate(A)
    if problems:
        raise ValueError("; ".join(problems))
    fx = A.get("local_per_usd")
    unit = A.get("_currency_unit", "local currency")
    products = A.get("products") or {"all": {"share": 1.0, "price": A.get("price", {"value": 0})["value"], "source": "-"}}
    out: dict[str, Any] = {}
    for k in SCEN:
        pool = _num(A["population"], k) * _num(A["target_share"], k)
        addressable = pool * _num(A["need_share"], k) * _num(A["ability_to_pay_share"], k)
        primary = _num(A["providers"], k) * _num(A["cases_per_provider"], k)
        secondary = 0.0
        if "secondary_providers" in A:
            secondary = (
                _num(A["secondary_providers"], k)
                * _num(A.get("secondary_share_doing_it", {"value": 1}), k)
                * _num(A.get("cases_per_secondary", {"value": 0}), k)
            )
        cases = primary + secondary
        mix = {p: _val(v["share"], k) for p, v in products.items()}
        price = {p: _val(v["price"], k) for p, v in products.items()}
        if abs(sum(mix.values()) - 1) > 0.001:
            raise ValueError(f"product shares for scenario {k} sum to {sum(mix.values()):.3f}, not 1")
        value_by = {p: cases * mix[p] * price[p] for p in mix}
        value = sum(value_by.values())
        pen = cases / addressable if addressable else None
        out[k] = {
            "target_pool": round(pool),
            "addressable": round(addressable),
            "cases_primary": round(primary),
            "cases_secondary": round(secondary),
            "cases_per_year": round(cases),
            "cases_to_addressable": round(pen, 4) if pen else None,
            "average_ticket": round(sum(mix[p] * price[p] for p in mix), 2),
            "value": round(value, 2),
            "value_usd": round(value / _num(fx, k), 2) if fx else None,
            "value_by_product": {p: round(v, 2) for p, v in value_by.items()},
            "cases_by_product": {p: round(cases * mix[p]) for p in mix},
        }
        if "treatment_years" in A:
            out[k]["active_users"] = round(cases * _num(A["treatment_years"], k))
    base_pen = out["base"]["cases_to_addressable"] or 0
    check = (
        "ok: base cases are 2-8% of the addressable group per year"
        if 0.02 <= base_pen <= 0.08
        else f"check inputs: base cases are {base_pen * 100:.1f}% of the addressable group per year (expected roughly 2-8%)"
    )
    weakest = [k for k, v in A.items() if isinstance(v, dict) and "assumption" in str(v.get("source", "")).lower()]
    return {
        "currency_unit": unit,
        "scenarios": out,
        "consistency_check": check,
        "assumption_inputs": weakest,
        "label": "Model estimate (estimasi model), not observed data. Value = revenue paid by customers for the "
        "service/product at the stated prices.",
    }


def regional_split(
    national_value: dict[str, float],
    regions: list[dict[str, Any]],
    income_cap: float = 2.0,
) -> dict[str, Any]:
    """regions: [{region, population, income_per_capita, providers}]. Demand weight =
    population x min(income/national income, cap). White space = demand share above the mean AND
    providers per 1 million below the national density."""
    if not regions:
        raise ValueError("regions is empty")
    tp = sum(float(r["population"]) for r in regions)
    nat_income = sum(float(r["population"]) * float(r["income_per_capita"]) for r in regions) / tp
    tprov = sum(float(r.get("providers") or 0) for r in regions)
    density_nat = tprov / tp * 1e6
    rows = []
    for r in regions:
        idx = min(float(r["income_per_capita"]) / nat_income, income_cap)
        rows.append({**r, "income_index": round(idx, 3), "_w": float(r["population"]) * idx})
    tw = sum(r["_w"] for r in rows)
    for r in rows:
        r["demand_share"] = round(r.pop("_w") / tw, 5)
        r["providers_per_million"] = round(float(r.get("providers") or 0) / float(r["population"]) * 1e6, 2)
        for k, v in national_value.items():
            r[f"value_{k}"] = round(v * r["demand_share"], 2)
        r["white_space"] = r["demand_share"] > 1 / len(rows) and r["providers_per_million"] < density_nat
    key = "value_base" if "base" in national_value else f"value_{next(iter(national_value))}"
    rows.sort(key=lambda r: -r[key])
    n = len(rows)
    for i, r in enumerate(rows):
        r["tier"] = "white space" if r["white_space"] else ("largest market" if i < max(3, n // 5) else
                                                            "under-served" if r["providers_per_million"] < density_nat / 2 else "other")
    return {"national_provider_density_per_million": round(density_nat, 2), "regions": rows}
