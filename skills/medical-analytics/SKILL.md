---
name: medical-analytics
description: Medical, dental, nursing, pharmacy and public-health evidence and data analysis with the research-analytics MCP server — PICO/MeSH PubMed searches with evidence levels, ClinicalTrials.gov, WHO GHO burden data, PRISMA counts, and statistics on clinical or observational data (descriptives, group comparison, pre/post, chi-square, correlation, trend, inter-observer kappa, sample size). Use for "analisis data penelitian", "uji statistik", "uji beda", "sampel berapa", "evidence based", "PICO", "systematic review", "kedokteran gigi", "observasi klinis".
metadata:
  version: "1.0"
  requires: research-analytics MCP server
---

# Medical evidence & analytics

Nothing here is medical advice. For a question about a specific patient, give the evidence and
say it does not replace clinical judgment. Never put identifiable patient data in a tool call:
use codes (P01, P02 …).

## A. Evidence (literature)

1. Write the question as **PICO** (Population, Intervention, Comparison, Outcome).
2. Build the PubMed string from MeSH + free-text synonyms, e.g.
   `("Silver Diamine Fluoride"[MeSH] OR "silver diamine fluoride"[tiab]) AND ("Dental Caries"[MeSH] OR caries[tiab]) AND child*`.
3. `search_pubmed(term, mindate="2020")` → report `query_translation`, `total`, `run_date`.
   Log it: `db_log_search(project, "PubMed", term, total)`, store hits with `db_add_papers`.
4. `pubmed_abstracts(pmids)` → abstract, MeSH, publication types and an `evidence` label
   (1 SR/MA → 2 RCT → 3 trial → 4 observational → 5 case report → 6 narrative review).
   The label comes from PubMed publication types; confirm the design from the abstract and store
   it with `db_update_paper(id, {"evidence_level": n, "method": "..."})`.
5. Registered/unpublished trials: `search_clinical_trials(condition, intervention, status="COMPLETED")`;
   `has_results: false` on completed trials is a publication-bias / gap signal.
6. Burden of disease: `who_indicators("<keyword>")` → `who_indicator_data(code, "IDN")`; cite the code and year.
7. Systematic review: keep PRISMA counts with `db_prisma(project)`. Say clearly that PubMed alone
   is not enough (Scopus, Embase, Cochrane CENTRAL are normally required).
8. Dentistry: use dental MeSH terms (Dental Caries, Periodontitis, Orthodontics, Endodontics,
   Dental Implants, Pit and Fissure Sealants) and the OpenAlex search for non-MEDLINE journals.

## B. Data analysis

Data comes from `csv_path`, inline `records`, or a project's observations
(`db_import_observations_csv`, `db_add_observations`).

| Question | Tool |
|:--|:--|
| Describe the sample (Table 1) | `stats_describe` |
| Do 2+ groups differ on a number? | `stats_compare_groups(group_col, value_col)` — Welch t / Mann-Whitney / ANOVA / Kruskal, chosen from normality |
| Before vs after on the same people | `stats_paired(before_col, after_col)` |
| Are two categories associated? | `stats_crosstab(row_col, col_col)` — chi-square, Fisher for sparse 2×2, Cramér's V |
| Do two numbers move together? | `stats_correlate(x, y)` — Pearson/Spearman |
| Is it rising over time? | `stats_trend(time_col, value_col)` — slope, Mann-Kendall, CAGR |
| Do two examiners agree? | `stats_kappa(rater_a, rater_b)` |
| How many subjects do I need? | `stats_sample_size("proportion" / "two_proportions" / "two_means", ...)` |

Report every test as: test name, statistic, p-value, effect size, n, and the assumption the tool
states — then one plain sentence. Significance is not importance: comment on the effect size.
With many tests, mention multiple-comparison risk. Correlation is not causation.

## C. Write-up

Methods: databases, exact strings, dates, inclusion/exclusion, tests and why. Results: Table 1
(descriptives), main comparison with effect sizes, PRISMA numbers. Limitations: design (from
evidence level), sample size, single database, missing data.
