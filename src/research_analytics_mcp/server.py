"""MCP server entry point. Run with ``research-analytics-mcp`` (stdio)."""

from __future__ import annotations

from typing import Any

try:  # MCP Python SDK 2.x
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # SDK 1.x
    from mcp.server.fastmcp import FastMCP as _Server  # type: ignore[no-redef]

from . import __version__, analytics, database, literature, market, markets, training, video

INSTRUCTIONS = """Research & analytics toolkit: literature search (OpenAlex, Semantic Scholar, PubMed,
Crossref, ClinicalTrials.gov, WHO GHO), journal targeting, a local research database
(papers/literature matrix/PRISMA, notes, journals, observations), statistics, market sizing,
and training design/evaluation with optional Open-Higgsfield (MuAPI) media generation.
Rules: never invent papers, DOIs or numbers; every item must come from a tool result.
OpenAlex cannot confirm Scopus indexing or quartiles. Market outputs are model estimates.
media_generate spends credits: call it with confirm=true only after the user agrees."""

try:
    mcp = _Server("research-analytics", instructions=INSTRUCTIONS, version=__version__)
except TypeError:  # SDK 1.x has no version argument
    mcp = _Server("research-analytics", instructions=INSTRUCTIONS)


# ================================================================ literature
@mcp.tool()
def search_openalex(
    query: str,
    year_from: int | None = None,
    year_to: int | None = None,
    work_type: str | None = None,
    sort: str = "relevance",
    per_page: int = 25,
    open_access_only: bool = False,
    country_code: str | None = None,
    with_abstract: bool = True,
) -> dict[str, Any]:
    """Search OpenAlex works by title+abstract. sort: relevance | cited | newest.
    work_type: article | review | preprint | book-chapter ... country_code: ISO2 of an author institution (e.g. ID)."""
    return literature.openalex_search_works(query, year_from, year_to, work_type, sort, per_page,
                                            open_access_only, country_code, with_abstract)


@mcp.tool()
def topic_trend(query: str, group_by: str = "publication_year", year_from: int | None = 2015) -> dict[str, Any]:
    """Count OpenAlex works for a topic grouped by publication_year, authorships.institutions.country_code,
    primary_location.source.id, primary_topic.id or open_access.oa_status. Shows growth and gaps."""
    return literature.openalex_trend(query, group_by, year_from)


@mcp.tool()
def citation_graph(openalex_id: str, direction: str = "cited_by", per_page: int = 25) -> dict[str, Any]:
    """Neighbours of a key paper (W… id): cited_by (later work), references (its foundations) or related."""
    return literature.openalex_citations(openalex_id, direction, per_page)


@mcp.tool()
def search_semantic_scholar(
    query: str, year: str | None = None, limit: int = 20, fields_of_study: str | None = None, min_citations: int | None = None
) -> dict[str, Any]:
    """Semantic Scholar search with TLDR summaries and influential-citation counts. year: '2020-' or '2019-2023'.
    Without SEMANTIC_SCHOLAR_API_KEY it is rate-limited; on errors continue with OpenAlex."""
    return literature.semantic_scholar_search(query, year, limit, fields_of_study, min_citations)


@mcp.tool()
def search_pubmed(term: str, mindate: str | None = None, maxdate: str | None = None, retmax: int = 20,
                  sort: str = "relevance") -> dict[str, Any]:
    """PubMed search with full syntax incl. MeSH/PICO, e.g. '("Dental Caries"[MeSH] OR caries[tiab]) AND child*'.
    Returns PMIDs, DOI, journal, publication types and the query translation (report it for reproducibility)."""
    res = literature.pubmed_search(term, mindate, maxdate, retmax, sort)
    for r in res["results"]:
        r["evidence"] = literature.evidence_level(r.get("publication_types") or [])
    return res


@mcp.tool()
def pubmed_abstracts(pmids: list[str]) -> dict[str, Any]:
    """Abstracts, MeSH terms and publication types for up to 100 PMIDs, with an evidence-level label."""
    res = literature.pubmed_abstracts(pmids)
    for r in res["results"]:
        r["evidence"] = literature.evidence_level(r.get("publication_types") or [])
    return res


@mcp.tool()
def search_clinical_trials(condition: str, intervention: str | None = None, status: str | None = None,
                           country: str | None = None, page_size: int = 20) -> dict[str, Any]:
    """ClinicalTrials.gov registry search. status e.g. RECRUITING, COMPLETED. Useful for gaps:
    trials completed without posted results."""
    return literature.clinical_trials_search(condition, intervention, status, country, page_size)


@mcp.tool()
def lookup_doi(doi: str) -> dict[str, Any]:
    """Crossref metadata for a DOI (title, journal, ISSN, publisher, year, authors, licence)."""
    return literature.crossref_lookup(doi)


@mcp.tool()
def who_indicators(keyword: str) -> dict[str, Any]:
    """Find WHO Global Health Observatory indicator codes by keyword (e.g. 'caries', 'diabetes')."""
    return literature.who_indicator_search(keyword)


@mcp.tool()
def who_indicator_data(code: str, country_iso3: str = "IDN") -> dict[str, Any]:
    """Values of a WHO GHO indicator for one country (ISO3, default Indonesia) by year."""
    return literature.who_indicator_values(code, country_iso3)


# ================================================================ journals
@mcp.tool()
def journal_profile(name_or_issn: str) -> dict[str, Any]:
    """Journal profile from OpenAlex: publisher, h-index, 2-year mean citedness, OA/DOAJ, APC.
    Does not confirm Scopus indexing or quartile."""
    return literature.journal_profile(name_or_issn)


@mcp.tool()
def journals_for_topic(query: str, year_from: int = 2021, top: int = 15, open_access_only: bool = False,
                       max_apc_usd: int | None = None) -> dict[str, Any]:
    """Where recent articles on a topic are published, ranked by article count, with red flags."""
    return literature.journals_for_topic(query, year_from, top, open_access_only, max_apc_usd)


# ================================================================ database
@mcp.tool()
def db_create_project(name: str, kind: str = "literature", description: str = "") -> dict[str, Any]:
    """Create (or return) a project. kind: literature | market | observation | training."""
    return database.create_project(name, kind, description)


@mcp.tool()
def db_list_projects() -> list[dict[str, Any]]:
    """All projects with paper and observation counts."""
    return database.list_projects()


@mcp.tool()
def db_add_papers(project: str, papers: list[dict[str, Any]]) -> dict[str, Any]:
    """Store search results (as returned by the search tools) in a project; de-duplicates by DOI, PMID, title."""
    return database.add_papers(project, papers)


@mcp.tool()
def db_update_paper(paper_id: int, fields: dict[str, Any]) -> dict[str, Any]:
    """Fill matrix columns or screening: method, data_context, finding, limitation, theme, evidence_level,
    status (candidate|screened|included|excluded), exclusion_reason."""
    return database.update_paper(paper_id, fields)


@mcp.tool()
def db_list_papers(project: str, status: str | None = None, theme: str | None = None, search: str | None = None,
                   limit: int = 200) -> list[dict[str, Any]]:
    """List stored papers, most cited first."""
    return database.list_papers(project, status, theme, search, limit)


@mcp.tool()
def db_literature_matrix(project: str, status: str = "included", export_csv_path: str | None = None) -> dict[str, Any]:
    """Literature matrix (author-year, journal, method, data, finding, limitation, evidence, DOI) for a project.
    Pass export_csv_path to also write it as CSV."""
    rows = database.literature_matrix(project, status)
    res: dict[str, Any] = {"rows": rows}
    if export_csv_path:
        res["export"] = database.export_matrix_csv(project, export_csv_path, status)
    return res


@mcp.tool()
def db_log_search(project: str, database_name: str, query: str, hits: int, run_date: str | None = None) -> dict[str, Any]:
    """Record a search (database, exact query string, hit count, date) for the methods section and PRISMA."""
    return database.log_search(project, database_name, query, hits, run_date)


@mcp.tool()
def db_prisma(project: str) -> dict[str, Any]:
    """PRISMA flow counts from logged searches and screening statuses."""
    return database.prisma_counts(project)


@mcp.tool()
def db_add_note(project: str, text: str, paper_id: int | None = None, tags: list[str] | None = None) -> dict[str, Any]:
    """Save a reading note, research gap, or insight (optionally linked to a paper)."""
    return database.add_note(project, text, paper_id, tags)


@mcp.tool()
def db_list_notes(project: str, tag: str | None = None) -> list[dict[str, Any]]:
    """Notes of a project, optionally by tag (e.g. 'gap')."""
    return database.list_notes(project, tag)


@mcp.tool()
def db_save_journal(project: str, journal: dict[str, Any]) -> dict[str, Any]:
    """Add a journal to the shortlist: name, issn, publisher, h_index, citedness, is_oa, apc_usd,
    scopus_status (unchecked|indexed|discontinued|not indexed), quartile + quartile_source, fit_reason."""
    return database.save_journal(project, journal)


@mcp.tool()
def db_add_observations(project: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Record observations: [{variable, value, subject, group, session, unit, observer, observed_at, notes}]."""
    return database.add_observations(project, rows)


@mcp.tool()
def db_import_observations_csv(project: str, csv_path: str, mapping: dict[str, str] | None = None) -> dict[str, Any]:
    """Import observations from a CSV (long or wide). mapping renames columns, e.g. {"pasien": "subject"}."""
    return database.import_observations_csv(project, csv_path, mapping)


@mcp.tool()
def db_query_observations(project: str, variable: str | None = None, group: str | None = None,
                          session: str | None = None, limit: int = 5000) -> list[dict[str, Any]]:
    """Read observations back (filter by variable, group, session)."""
    return database.query_observations(project, variable, group, session, limit)


@mcp.tool()
def db_export_csv(project: str, table: str, path: str) -> dict[str, Any]:
    """Export papers | searches | notes | journals | observations of a project to CSV."""
    return database.export_csv(project, table, path)


# ================================================================ analytics
def _table(csv_path: str | None, records: list[dict[str, Any]] | None, project: str | None = None) -> list[dict[str, Any]]:
    if project and not (csv_path or records):
        rows = database.query_observations(project, limit=100000)
        return [{"subject": r["subject"], "group": r["grp"], "session": r["session"], "variable": r["variable"],
                 "value": r["value_num"] if r["value_num"] is not None else r["value_text"], "observer": r["observer"],
                 "observed_at": r["observed_at"]} for r in rows]
    return analytics.load_table(csv_path, records)


@mcp.tool()
def stats_describe(csv_path: str | None = None, records: list[dict[str, Any]] | None = None,
                   columns: list[str] | None = None, project: str | None = None) -> dict[str, Any]:
    """Descriptive statistics per column (n, missing, mean, SD, median, IQR, normality / category counts).
    Data from csv_path, records, or a project's observations."""
    return analytics.describe(_table(csv_path, records, project), columns)


@mcp.tool()
def stats_compare_groups(group_col: str, value_col: str, csv_path: str | None = None,
                         records: list[dict[str, Any]] | None = None, parametric: bool | None = None) -> dict[str, Any]:
    """Compare a numeric outcome across groups: Welch t / Mann-Whitney (2 groups), ANOVA / Kruskal-Wallis (3+),
    chosen from normality unless parametric is set. Returns effect size and a plain reading."""
    return analytics.compare_groups(_table(csv_path, records), group_col, value_col, parametric)


@mcp.tool()
def stats_paired(before_col: str, after_col: str, csv_path: str | None = None,
                 records: list[dict[str, Any]] | None = None, max_score: float | None = None) -> dict[str, Any]:
    """Pre/post comparison on the same subjects (paired t or Wilcoxon) plus normalised gain if max_score is given."""
    return analytics.paired_compare(_table(csv_path, records), before_col, after_col, max_score)


@mcp.tool()
def stats_crosstab(row_col: str, col_col: str, csv_path: str | None = None,
                   records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Contingency table with chi-square (Fisher exact for sparse 2x2) and Cramér's V."""
    return analytics.crosstab(_table(csv_path, records), row_col, col_col)


@mcp.tool()
def stats_correlate(x: str, y: str, csv_path: str | None = None, records: list[dict[str, Any]] | None = None,
                    method: str = "auto") -> dict[str, Any]:
    """Pearson or Spearman correlation (auto from normality) with a linear fit."""
    return analytics.correlate(_table(csv_path, records), x, y, method)


@mcp.tool()
def stats_trend(time_col: str, value_col: str, csv_path: str | None = None,
                records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Trend over time: linear slope, Mann-Kendall test, CAGR."""
    return analytics.trend(_table(csv_path, records), time_col, value_col)


@mcp.tool()
def stats_kappa(rater_a: str, rater_b: str, csv_path: str | None = None,
                records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Inter-observer agreement (Cohen's kappa) between two raters' columns."""
    return analytics.cohen_kappa(_table(csv_path, records), rater_a, rater_b)


@mcp.tool()
def stats_sample_size(design: str, alpha: float = 0.05, power: float = 0.8, proportion: float | None = None,
                      margin: float | None = None, population: int | None = None, p1: float | None = None,
                      p2: float | None = None, effect_size_d: float | None = None, dropout: float = 0.0) -> dict[str, Any]:
    """Sample size: design='proportion' (survey/prevalence), 'two_proportions', or 'two_means' (Cohen's d)."""
    return analytics.sample_size(design, alpha, power, proportion, margin, population, p1, p2, effect_size_d, dropout)


# ================================================================ market
@mcp.tool()
def market_example_assumptions() -> dict[str, Any]:
    """Example assumptions file (orthodontics in Indonesia) showing the input format: every value has a source."""
    return market.example_assumptions()


@mcp.tool()
def market_size_model(assumptions: dict[str, Any]) -> dict[str, Any]:
    """Two-way market model (demand x supply), low/base/high, value by product and a consistency check.
    See market_example_assumptions for the format."""
    return market.market_model(assumptions)


@mcp.tool()
def market_regional_split(national_value: dict[str, float], regions: list[dict[str, Any]],
                          income_cap: float = 2.0) -> dict[str, Any]:
    """Split a national value by region. regions: [{region, population, income_per_capita, providers}].
    national_value: {low, base, high}. Flags white space and tiers."""
    return market.regional_split(national_value, regions, income_cap)


# ================================================================ training / L&D
@mcp.tool()
def training_blueprint(topic: str, audience: str, duration_minutes: int = 120, level: str = "intermediate",
                       n_objectives: int = 4, project: str | None = None, delivery: str = "blended") -> dict[str, Any]:
    """Training module skeleton: Bloom-levelled objectives, agenda, evidence from the project's included papers,
    assessment and a Kirkpatrick evaluation plan."""
    return training.training_blueprint(topic, audience, duration_minutes, level, n_objectives, project, delivery)


@mcp.tool()
def training_observation_checklist(skill: str, steps: list[str], scale: str = "done_not_done",
                                   critical_steps: list[int] | None = None) -> dict[str, Any]:
    """Skills observation checklist (done_not_done | three_point | five_point) with variables to record."""
    return training.observation_checklist(skill, steps, scale, critical_steps)


@mcp.tool()
def training_evaluation_report(project: str, max_score: float | None = 100, pass_threshold: float = 0.8) -> dict[str, Any]:
    """Kirkpatrick L1-L4 report from a project's observations (reaction_*, pre/post_score, step_NN, outcome_*),
    including normalised gain, checklist pass rates, weakest steps and inter-rater kappa."""
    return training.kirkpatrick_report(project, max_score, pass_threshold)


@mcp.tool()
def training_storyboard(objectives: list[str], style: str = "realistic clinical training video, neutral lighting",
                        seconds_per_scene: int = 8) -> dict[str, Any]:
    """Scene prompts for training videos, one per learning objective, ready for media_generate."""
    return training.storyboard(objectives, style, seconds_per_scene)


@mcp.tool()
def media_generate(endpoint: str, payload: dict[str, Any], confirm: bool = False, wait_seconds: int = 0) -> dict[str, Any]:
    """Generate an image/video through Open-Higgsfield's MuAPI gateway: POST /api/v1/{endpoint}.
    PAID. Without confirm=true it only returns a dry run; confirm only after the user agrees."""
    return training.media_generate(endpoint, payload, confirm, wait_seconds)


@mcp.tool()
def media_result(request_id: str, wait_seconds: int = 0) -> dict[str, Any]:
    """Status and output URLs of a MuAPI generation; wait_seconds polls up to 10 minutes."""
    return training.media_result(request_id, wait_seconds)


@mcp.tool()
def media_upload(file_path: str) -> dict[str, Any]:
    """Upload a local reference image/video/audio to MuAPI; returns a hosted URL for image/video-conditioned models."""
    return training.media_upload(file_path)


# ================================================================ markets & news
@mcp.tool()
def bloomberg_headlines(sections: list[str] | None = None, query: str | None = None, limit: int = 20) -> dict[str, Any]:
    """Latest Bloomberg headlines + short summaries + links from Bloomberg's public RSS feeds (no key).
    sections: markets, economics, technology, industries, politics, businessweek, crypto, bview (opinion).
    query filters by words in title/summary (e.g. 'Indonesia rupiah'). Headlines only; never copy article text."""
    return markets.bloomberg_headlines(sections, query, limit)


@mcp.tool()
def market_quote(symbol: str) -> dict[str, Any]:
    """Latest daily quote (price, change %, volume) from Alpha Vantage. Needs ALPHA_VANTAGE_API_KEY."""
    return markets.quote(symbol)


@mcp.tool()
def market_symbol_search(keywords: str) -> dict[str, Any]:
    """Find ticker symbols by company name (Alpha Vantage), with region and currency."""
    return markets.symbol_search(keywords)


@mcp.tool()
def market_history(symbol: str, days: int = 100) -> dict[str, Any]:
    """Daily closes (up to 100 days) with period return, annualised volatility and max drawdown (Alpha Vantage)."""
    return markets.daily(symbol, days)


@mcp.tool()
def market_fx_rate(from_currency: str, to_currency: str = "IDR") -> dict[str, Any]:
    """Real-time exchange rate, e.g. USD -> IDR, for converting market-size values (Alpha Vantage)."""
    return markets.fx_rate(from_currency, to_currency)


@mcp.tool()
def market_news_sentiment(tickers: str | None = None, topics: str | None = None, limit: int = 20,
                          sources: str | None = None) -> dict[str, Any]:
    """Market news with sentiment scores from Alpha Vantage. tickers 'AAPL,MSFT' or 'FOREX:USD';
    topics e.g. economy_macro, financial_markets, life_sciences, technology; sources filters by outlet name."""
    return markets.news_sentiment(tickers, topics, limit, sources)


# ================================================================ teaching video
@mcp.tool()
def video_lesson_plan(title: str, scenes: list[dict[str, Any]], fmt: str = "16:9", words_per_minute: int = 140,
                      out_dir: str | None = None, project: str | None = None) -> dict[str, Any]:
    """Plan a medical teaching video. scenes: [{purpose (hook|objectives|concept|demo|mistakes|summary|quiz|references),
    narration, on_screen_text, visual, objective, paper_ids, duration_s?}]. Times each scene from its word count,
    checks that clinical numbers have sources from the project, flags pedagogy issues, and writes
    lesson-plan.json + edit-plan.md to out_dir. fmt: 16:9 | 9:16 | 1:1 | 4:5."""
    return video.lesson_plan(title, scenes, fmt, words_per_minute, out_dir, project)


@mcp.tool()
def video_captions(scenes: list[dict[str, Any]], out_dir: str | None = None, max_cps: float = 17.0) -> dict[str, Any]:
    """Captions from scene narration and timing (e.g. video_lesson_plan scenes): captions.srt and Remotion
    captions.json, max 2 lines x 42 characters, warns above max_cps characters per second."""
    return video.captions(scenes, out_dir, max_cps)


@mcp.tool()
def video_probe(path: str) -> dict[str, Any]:
    """Inspect a local video/audio file with ffprobe: duration, resolution, fps, codecs, audio, concat readiness."""
    return video.probe(path)


@mcp.tool()
def media_search_openverse(query: str, kind: str = "image", license: str = "commercial", n: int = 10,
                           source: str | None = None) -> dict[str, Any]:
    """Search Creative Commons images/audio (Wikimedia Commons, Flickr, museums, Freesound) via Openverse; no API key.
    license: commercial | pd | any. source e.g. 'wikimedia'. Returns licence and attribution lines."""
    return video.openverse_search(query, kind, license, n, source)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
