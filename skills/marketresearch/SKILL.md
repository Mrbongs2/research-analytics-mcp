---
name: marketresearch
description: Market research for a health, dental or other professional product/service (default Indonesia) with the research-analytics MCP server — market size with low/base/high scenarios (demand × supply), value per product, regional split with white-space detection, prices and competitors from the web, business process and patient/customer journey, all with sources. Use for "analisa pasar", "potensi pasar", "market size", "potential sales", "di mana market tertinggi", "white space", "pesaing", "harga", "proses bisnis".
metadata:
  version: "1.0"
  requires: research-analytics MCP server; a web search tool for prices and players
---

# Market research

Tools: `market_example_assumptions`, `market_size_model`, `market_regional_split`,
`stats_trend`, `who_indicator_data`, plus the literature tools for the "need" figure.

Golden rule: **a model estimate is never data.** Label it *estimasi model*, keep the assumptions
table with every number, and keep official figures (BPS, registers) apart from assumptions.

## M1. Scope (one line)

Product and its variants, who pays, geography (default: Indonesia by province), deliverable
(report, sheet, slides). `db_create_project(name, kind="market")`.

## M2. Demand

- Population and income per region: BPS (bps.go.id) tables; if a table page will not load, the
  Wikipedia list of provinces cites BPS. Record the year.
- Target share: the age band or segment that buys it (BPS Sensus 2020 generations, Susenas).
- **Need share** from the literature: a measured prevalence (use the `research-journalscopus`
  search tools; cite the study). Avoid slogans without a primary source.
- Ability to pay: BPS middle class share; aspiring middle class only via instalments, high scenario.
- For health burden, `who_indicators("<keyword>")` → `who_indicator_data(code, "IDN")`.

## M3. Supply

- Providers: a public register (professional association, KKI, Kemenkes facility data). Say
  which register and the date. If some providers have no region, report national and mapped counts.
- Throughput (cases per provider per year) is usually unknown: use a foreign benchmark only as a
  ceiling, and set low/base/high as labelled **Assumption** inputs.
- Secondary providers (e.g. GPs doing part of the volume) get their own line.

## M4. Prices, players, rules (web)

- Prices: clinic/price pages and consumer-finance articles, in Indonesian; record range, source,
  date; flag anything older than 2 years. Include recurring fees in the price per case.
- Players: brands, chains, direct-to-consumer startups, funding news.
- Paywalled market reports: quote only the public headline figure and say what it measures.
- Regulation that limits who may sell/provide it, and the informal segment.

## M5. Model

1. `market_example_assumptions()` shows the format. Build a new file: every input is
   `{"value": <number or {low, base, high}>, "source": "..."}`; assumptions say "Assumption: ...".
2. `market_size_model(assumptions)` → addressable people, cases/year, cases-to-addressable ratio,
   average ticket, value (local and USD), value and cases per product, consistency check.
3. If the check fails (base outside ~2–8 %/year), find the input that is off, change it, and say why.
4. Name the two weakest inputs (the `assumption_inputs` list) — they drive the range.

## M6. Regions

`market_regional_split({"low":..,"base":..,"high":..}, regions=[{region, population, income_per_capita, providers}])`
→ demand share (population × capped income index), providers per million, white space
(demand above mean, density below national), tiers. Present: largest markets, white space
(expansion priority), under-served (long term: tele-service, partnerships).

## M7. Business process

Customer journey stage by stage, where cash comes in (deposit, instalments, per-visit, package),
revenue model per product, value chain (manufacturer → distributor → provider → customer), key
players. A step without a sourced figure gets a description, not an invented price.

## M8. Deliverables

Charts: value per scenario split by product; value per region (leaders highlighted); provider
density vs national (white space highlighted). A spreadsheet keeps assumptions as input cells
and results as formulas. Keep numbers identical across report, sheet and slides.
