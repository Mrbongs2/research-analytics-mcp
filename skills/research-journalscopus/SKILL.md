---
name: research-journalscopus
description: Alur riset dari topik sampai target jurnal Scopus memakai server MCP research-analytics — cari literatur (OpenAlex, Semantic Scholar, PubMed), simpan dan saring di database riset lokal, petakan sitasi, susun matriks literatur, temukan research gap, catat alur PRISMA, dan buat shortlist jurnal. Use when the user wants a literature review, state of the art, kajian pustaka, research gap, skripsi/tesis/disertasi background, or a journal to submit to ("jurnal Scopus", "mau publish di mana").
metadata:
  version: "1.0"
  requires: research-analytics MCP server
---

# Research → Scopus journal

All tools below come from the `research-analytics` MCP server. Answer in the user's language
(usually Bahasa Indonesia). **Never invent a paper, author, DOI, number or quartile**: every item
must come from a tool result.

## 0. Scope (one short message, skip what is already known)

Topic / research question and field · purpose (skripsi, tesis, artikel, proposal) · period
(default last 5 years) · for journal targeting: quartile wanted, max APC, open access or not.

Then `db_create_project(name="<topic short name>", kind="literature")`.

## 1. Map the topic

- `topic_trend(query, group_by="publication_year", year_from=2015)` → rising, flat or falling
  (the current year is partial).
- `topic_trend(query, group_by="authorships.institutions.country_code")` → where the research
  happens; few Indonesian studies is itself a gap signal. Compute shares against `total`.

## 2. Find the literature

Run each search, store the hits, and log the search:

| Purpose | Call |
|:--|:--|
| Foundations | `search_openalex(query, sort="cited", work_type="article", per_page=25)` |
| State of the art | `search_openalex(query, year_from=<now-3>, sort="cited")` and `sort="newest"` |
| Reviews to start from | `search_openalex(query, work_type="review")` |
| Gap filling + TLDR | `search_semantic_scholar(query, year="2020-")` (rate-limited without a key; on errors continue) |
| Health topics | `search_pubmed(term)` with MeSH, see the `medical-analytics` skill |

After each: `db_add_papers(project, results)` (de-duplicates by DOI → PMID → title) and
`db_log_search(project, database_name, query, hits=total)`.

Key papers (3–5 most central): `citation_graph(openalex_id, "cited_by")` for who built on it,
`"references"` for its foundations, `"related"` for neighbours you missed.

## 3. Screen and build the matrix

1. `db_list_papers(project)`; read title + abstract.
2. `db_update_paper(id, {"status": "included"})` or `{"status": "excluded", "exclusion_reason": "..."}`.
3. For included papers fill `method`, `data_context`, `finding`, `limitation`, `theme` from the
   abstract or TLDR. If the abstract does not say it, leave it empty (the matrix prints "not stated").
4. `db_literature_matrix(project, export_csv_path="<folder>/matrix.csv")`.

| # | Author (year) | Title | Journal | Method | Data / context | Key finding | Limitation / gap | Cited by | DOI / PMID |

## 4. Research gap

Derive gaps from the matrix, not from general knowledge:
- methods not yet applied in this context (Indonesia, a population, a setting);
- contradicting findings;
- limitations several papers name;
- volume signals from step 1.

One sentence per gap, the 2–3 papers behind it, one research question per gap. Save each with
`db_add_note(project, text, tags=["gap"])`.

## 5. Target journals

1. `journals_for_topic(query, year_from=2021, open_access_only=?, max_apc_usd=?)`.
2. Add the journals of your key papers: `journal_profile(<name or ISSN>)`.
3. **Scopus status and quartile are not in OpenAlex.** For each finalist tell the user to check
   the ISSN at scopus.com/sources and scimagojr.com, or check it yourself with a browser tool and
   quote the page and date. Save with `db_save_journal(project, {..., "scopus_status": "unchecked"})`;
   a quartile is only saved with `quartile_source`.
4. Flag: no DOAJ for an OA journal, very low citedness, generic scope, very high volume,
   "fast review" promises.

Output 5–10 journals: name, ISSN, publisher, quartile (with source, or "cek"), articles on the
topic, h-index, 2-year citedness (not the JIF), APC, OA, fit reason.

## Final output

1. Topic map (trend, countries). 2. Literature matrix + search log. 3. Gaps with papers and RQs.
4. Journal shortlist with Scopus-check status. 5. Method note: databases, exact queries, dates
(`db_prisma(project)` for counts), and limits (OpenAlex/S2 ≠ Scopus; citation counts differ between sources).
