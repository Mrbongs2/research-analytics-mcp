"""Literature connectors: OpenAlex, Semantic Scholar, PubMed (NCBI E-utilities), Crossref,
ClinicalTrials.gov and the WHO Global Health Observatory. All free, public APIs.

Every function returns plain dicts with a ``source`` field so results can be merged,
deduplicated and stored in the research database without guessing where they came from.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any

from .http import get_json, get_text

OPENALEX = "https://api.openalex.org"
S2 = "https://api.semanticscholar.org/graph/v1"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CTGOV = "https://clinicaltrials.gov/api/v2/studies"
CROSSREF = "https://api.crossref.org/works"
GHO = "https://ghoapi.azureedge.net/api"


# ---------------------------------------------------------------- helpers
def _openalex_params(extra: dict[str, Any]) -> dict[str, Any]:
    p = dict(extra)
    if os.getenv("OPENALEX_API_KEY"):
        p["api_key"] = os.environ["OPENALEX_API_KEY"]
    if os.getenv("OPENALEX_MAILTO"):
        p["mailto"] = os.environ["OPENALEX_MAILTO"]
    return p


def _clean(q: str) -> str:
    """Commas separate OpenAlex filters, so they cannot appear inside a search value."""
    return " ".join(q.replace(",", " ").split())


def _year_filter(year_from: int | None, year_to: int | None) -> str | None:
    if year_from and year_to:
        return f"publication_year:{year_from}-{year_to}"
    if year_from:
        return f"publication_year:>{year_from - 1}"
    if year_to:
        return f"publication_year:<{year_to + 1}"
    return None


def abstract_from_inverted_index(inv: dict[str, list[int]] | None) -> str | None:
    if not inv:
        return None
    pos: dict[int, str] = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    doi = doi.strip().lower()
    doi = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", doi)
    return doi.removeprefix("doi:") or None


def _work(w: dict[str, Any], with_abstract: bool) -> dict[str, Any]:
    loc = w.get("primary_location") or {}
    src = loc.get("source") or {}
    oa = w.get("open_access") or {}
    authors = [a.get("author", {}).get("display_name") for a in (w.get("authorships") or [])]
    out = {
        "source": "OpenAlex",
        "openalex_id": (w.get("id") or "").rsplit("/", 1)[-1],
        "title": w.get("display_name"),
        "year": w.get("publication_year"),
        "doi": normalize_doi(w.get("doi")),
        "pmid": ((w.get("ids") or {}).get("pmid") or "").rsplit("/", 1)[-1] or None,
        "type": w.get("type"),
        "cited_by": w.get("cited_by_count"),
        "authors": [a for a in authors if a][:10],
        "venue": src.get("display_name"),
        "venue_id": (src.get("id") or "").rsplit("/", 1)[-1] or None,
        "is_oa": oa.get("is_oa"),
        "oa_url": oa.get("oa_url"),
    }
    if with_abstract:
        out["abstract"] = abstract_from_inverted_index(w.get("abstract_inverted_index"))
    return out


# ---------------------------------------------------------------- OpenAlex
def openalex_search_works(
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
    filters = [f"title_and_abstract.search:{_clean(query)}"]
    if yf := _year_filter(year_from, year_to):
        filters.append(yf)
    if work_type:
        filters.append(f"type:{work_type}")
    if open_access_only:
        filters.append("is_oa:true")
    if country_code:
        filters.append(f"authorships.institutions.country_code:{country_code.upper()}")
    sort_map = {
        "relevance": "relevance_score:desc",
        "cited": "cited_by_count:desc",
        "newest": "publication_date:desc",
    }
    select = "id,display_name,publication_year,doi,ids,type,cited_by_count,authorships,primary_location,open_access"
    if with_abstract:
        select += ",abstract_inverted_index"
    data = get_json(
        f"{OPENALEX}/works",
        params=_openalex_params(
            {
                "filter": ",".join(filters),
                "sort": sort_map.get(sort, sort),
                "per-page": max(1, min(per_page, 100)),
                "select": select,
            }
        ),
    )
    return {
        "query": query,
        "filter": ",".join(filters),
        "total": data.get("meta", {}).get("count"),
        "retrieved": date.today().isoformat(),
        "results": [_work(w, with_abstract) for w in data.get("results", [])],
    }


def openalex_trend(query: str, group_by: str = "publication_year", year_from: int | None = 2015) -> dict[str, Any]:
    """Counts of works matching ``query`` grouped by a field (year, country, source, topic, oa status)."""
    filters = [f"title_and_abstract.search:{_clean(query)}"]
    if yf := _year_filter(year_from, None):
        filters.append(yf)
    data = get_json(
        f"{OPENALEX}/works",
        params=_openalex_params({"filter": ",".join(filters), "group_by": group_by}),
    )
    groups = [
        {"key": (g.get("key") or "").rsplit("/", 1)[-1], "label": g.get("key_display_name"), "count": g.get("count")}
        for g in data.get("group_by", [])
    ]
    if group_by == "publication_year":
        groups.sort(key=lambda g: g["key"])
    return {
        "query": query,
        "group_by": group_by,
        "total": data.get("meta", {}).get("count"),
        "note": "Shares must be computed against total, not the sum of groups (multi-valued fields double count). The current year is partial.",
        "groups": groups,
    }


def openalex_citations(openalex_id: str, direction: str = "cited_by", per_page: int = 25) -> dict[str, Any]:
    """direction: 'cited_by' (papers citing it), 'references' (what it cites), 'related' (OpenAlex related works)."""
    wid = openalex_id.rsplit("/", 1)[-1]
    if direction == "cited_by":
        data = get_json(
            f"{OPENALEX}/works",
            params=_openalex_params({"filter": f"cites:{wid}", "sort": "cited_by_count:desc", "per-page": per_page}),
        )
        works = data.get("results", [])
    else:
        w = get_json(f"{OPENALEX}/works/{wid}", params=_openalex_params({}))
        ids = w.get("referenced_works" if direction == "references" else "related_works", [])[:per_page]
        if not ids:
            return {"id": wid, "direction": direction, "results": []}
        data = get_json(
            f"{OPENALEX}/works",
            params=_openalex_params(
                {"filter": "openalex:" + "|".join(i.rsplit("/", 1)[-1] for i in ids), "per-page": len(ids)}
            ),
        )
        works = data.get("results", [])
    return {"id": wid, "direction": direction, "results": [_work(w, False) for w in works]}


# ---------------------------------------------------------------- journals (OpenAlex sources)
_SOURCE_SELECT = (
    "id,display_name,issn_l,issn,host_organization_name,country_code,type,works_count,cited_by_count,"
    "summary_stats,is_oa,is_in_doaj,apc_usd,homepage_url"
)


def _source(s: dict[str, Any]) -> dict[str, Any]:
    st = s.get("summary_stats") or {}
    return {
        "openalex_id": (s.get("id") or "").rsplit("/", 1)[-1],
        "name": s.get("display_name"),
        "issn_l": s.get("issn_l"),
        "issn": s.get("issn"),
        "publisher": s.get("host_organization_name"),
        "country": s.get("country_code"),
        "type": s.get("type"),
        "works_count": s.get("works_count"),
        "h_index": st.get("h_index"),
        "two_year_mean_citedness": st.get("2yr_mean_citedness"),
        "is_oa": s.get("is_oa"),
        "is_in_doaj": s.get("is_in_doaj"),
        "apc_usd": s.get("apc_usd"),
        "homepage": s.get("homepage_url"),
    }


JOURNAL_CAVEAT = (
    "OpenAlex does not report Scopus/WoS indexing, SJR quartile, JIF or SINTA rank. "
    "two_year_mean_citedness is computed from OpenAlex citations and is NOT the Journal Impact Factor. "
    "Confirm Scopus status at scopus.com/sources and quartile at scimagojr.com before relying on it."
)


def journal_profile(name_or_issn: str) -> dict[str, Any]:
    q = name_or_issn.strip()
    if re.fullmatch(r"\d{4}-?\d{3}[\dXx]", q):
        issn = q if "-" in q else f"{q[:4]}-{q[4:]}"
        s = get_json(f"{OPENALEX}/sources/issn:{issn.upper()}", params=_openalex_params({"select": _SOURCE_SELECT}))
        return {"matches": [_source(s)], "caveat": JOURNAL_CAVEAT}
    data = get_json(
        f"{OPENALEX}/sources", params=_openalex_params({"search": q, "per-page": 10, "select": _SOURCE_SELECT})
    )
    return {
        "matches": [_source(s) for s in data.get("results", [])],
        "note": "Several journals can share a name; pick by ISSN and publisher.",
        "caveat": JOURNAL_CAVEAT,
    }


def journals_for_topic(
    query: str, year_from: int = 2021, top: int = 15, open_access_only: bool = False, max_apc_usd: int | None = None
) -> dict[str, Any]:
    """Rank journals by how many recent articles matching ``query`` they published, then profile them."""
    filters = [
        f"title_and_abstract.search:{_clean(query)}",
        f"publication_year:>{year_from - 1}",
        "type:article",
        "primary_location.source.type:journal",
    ]
    grouped = get_json(
        f"{OPENALEX}/works",
        params=_openalex_params({"filter": ",".join(filters), "group_by": "primary_location.source.id"}),
    ).get("group_by", [])[: max(1, min(top, 50))]
    counts = {(g["key"] or "").rsplit("/", 1)[-1]: g["count"] for g in grouped if g.get("key")}
    if not counts:
        return {"query": query, "journals": [], "caveat": JOURNAL_CAVEAT}
    src = get_json(
        f"{OPENALEX}/sources",
        params=_openalex_params(
            {"filter": "openalex:" + "|".join(counts), "per-page": len(counts), "select": _SOURCE_SELECT}
        ),
    ).get("results", [])
    rows = []
    for s in src:
        j = _source(s)
        j["articles_on_topic"] = counts.get(j["openalex_id"], 0)
        if open_access_only and not (j["is_oa"] or j["is_in_doaj"]):
            continue
        if max_apc_usd is not None and j["apc_usd"] is not None and j["apc_usd"] > max_apc_usd:
            continue
        j["flags"] = [
            f
            for f, cond in (
                ("not in DOAJ", j["is_oa"] and not j["is_in_doaj"]),
                ("low citedness (<0.5)", (j["two_year_mean_citedness"] or 0) < 0.5),
                ("APC unknown", j["apc_usd"] is None),
            )
            if cond
        ]
        rows.append(j)
    rows.sort(key=lambda r: -r["articles_on_topic"])
    return {"query": query, "since": year_from, "journals": rows, "caveat": JOURNAL_CAVEAT}


# ---------------------------------------------------------------- Semantic Scholar
def semantic_scholar_search(
    query: str, year: str | None = None, limit: int = 20, fields_of_study: str | None = None, min_citations: int | None = None
) -> dict[str, Any]:
    headers = {"x-api-key": os.environ["SEMANTIC_SCHOLAR_API_KEY"]} if os.getenv("SEMANTIC_SCHOLAR_API_KEY") else None
    fields = "title,year,externalIds,citationCount,influentialCitationCount,venue,authors,tldr,abstract,openAccessPdf"
    params = {
        "query": query,
        "year": year,
        "limit": max(1, min(limit, 100)),
        "fields": fields,
        "fieldsOfStudy": fields_of_study,
        "minCitationCount": min_citations,
    }
    data = get_json(f"{S2}/paper/search", params=params, headers=headers, retries=3, backoff=3)
    out = []
    for p in data.get("data", []):
        ext = p.get("externalIds") or {}
        out.append(
            {
                "source": "Semantic Scholar",
                "s2_id": p.get("paperId"),
                "title": p.get("title"),
                "year": p.get("year"),
                "doi": normalize_doi(ext.get("DOI")),
                "pmid": ext.get("PubMed"),
                "cited_by": p.get("citationCount"),
                "influential_citations": p.get("influentialCitationCount"),
                "venue": p.get("venue"),
                "authors": [a.get("name") for a in (p.get("authors") or [])][:10],
                "tldr": (p.get("tldr") or {}).get("text"),
                "abstract": p.get("abstract"),
                "oa_url": (p.get("openAccessPdf") or {}).get("url"),
            }
        )
    return {"query": query, "total": data.get("total"), "results": out}


# ---------------------------------------------------------------- PubMed
def _ncbi(params: dict[str, Any]) -> dict[str, Any]:
    if os.getenv("NCBI_API_KEY"):
        params["api_key"] = os.environ["NCBI_API_KEY"]
    params.setdefault("tool", "research-analytics-mcp")
    return params


def pubmed_search(
    term: str, mindate: str | None = None, maxdate: str | None = None, retmax: int = 20, sort: str = "relevance"
) -> dict[str, Any]:
    """term uses full PubMed syntax incl. MeSH, e.g. '"Dental Caries"[MeSH] AND fluoride[tiab]'.
    Dates as YYYY or YYYY/MM/DD (publication date)."""
    es = get_json(
        f"{EUTILS}/esearch.fcgi",
        params=_ncbi(
            {
                "db": "pubmed",
                "term": term,
                "retmode": "json",
                "retmax": max(1, min(retmax, 200)),
                "sort": sort,
                "datetype": "pdat" if (mindate or maxdate) else None,
                "mindate": mindate or ("1800" if maxdate else None),
                "maxdate": maxdate or ("3000" if mindate else None),
            }
        ),
    )["esearchresult"]
    ids = es.get("idlist", [])
    results = []
    if ids:
        summ = get_json(
            f"{EUTILS}/esummary.fcgi", params=_ncbi({"db": "pubmed", "id": ",".join(ids), "retmode": "json"})
        )["result"]
        for pmid in ids:
            s = summ.get(pmid, {})
            doi = next((a["value"] for a in s.get("articleids", []) if a.get("idtype") == "doi"), None)
            results.append(
                {
                    "source": "PubMed",
                    "pmid": pmid,
                    "title": s.get("title"),
                    "year": int(s["pubdate"][:4]) if s.get("pubdate", "")[:4].isdigit() else None,
                    "doi": normalize_doi(doi),
                    "venue": s.get("fulljournalname") or s.get("source"),
                    "authors": [a.get("name") for a in s.get("authors", [])][:10],
                    "publication_types": s.get("pubtype", []),
                }
            )
    return {
        "term": term,
        "query_translation": es.get("querytranslation"),
        "total": int(es.get("count", 0)),
        "run_date": date.today().isoformat(),
        "results": results,
    }


def pubmed_abstracts(pmids: list[str]) -> dict[str, Any]:
    xml = get_text(
        f"{EUTILS}/efetch.fcgi", params=_ncbi({"db": "pubmed", "id": ",".join(pmids[:100]), "retmode": "xml"})
    )
    root = ET.fromstring(xml)
    out = []
    for art in root.findall(".//PubmedArticle"):
        pmid = art.findtext(".//PMID")
        parts = []
        for ab in art.findall(".//Abstract/AbstractText"):
            label = ab.get("Label")
            text = "".join(ab.itertext()).strip()
            parts.append(f"{label}: {text}" if label else text)
        out.append(
            {
                "pmid": pmid,
                "title": "".join(art.find(".//ArticleTitle").itertext()) if art.find(".//ArticleTitle") is not None else None,
                "abstract": "\n".join(parts) or None,
                "mesh": [m.findtext("DescriptorName") for m in art.findall(".//MeshHeading")],
                "publication_types": [p.text for p in art.findall(".//PublicationType")],
            }
        )
    return {"results": out}


# Rough evidence hierarchy from PubMed publication types (label only; confirm the design from the abstract).
EVIDENCE_LEVELS = [
    ("Meta-Analysis", 1, "Meta-analysis"),
    ("Systematic Review", 1, "Systematic review"),
    ("Randomized Controlled Trial", 2, "RCT"),
    ("Controlled Clinical Trial", 3, "Non-randomised controlled trial"),
    ("Clinical Trial", 3, "Clinical trial"),
    ("Observational Study", 4, "Observational (cohort / case-control / cross-sectional)"),
    ("Comparative Study", 4, "Comparative study"),
    ("Case Reports", 5, "Case report"),
    ("Review", 6, "Narrative review"),
    ("Practice Guideline", 0, "Guideline"),
    ("Guideline", 0, "Guideline"),
]


def evidence_level(publication_types: list[str]) -> dict[str, Any]:
    for label, level, name in EVIDENCE_LEVELS:
        if label in publication_types:
            return {"level": level, "design": name}
    return {"level": None, "design": "not stated"}


# ---------------------------------------------------------------- ClinicalTrials.gov
def clinical_trials_search(
    condition: str, intervention: str | None = None, status: str | None = None, country: str | None = None, page_size: int = 20
) -> dict[str, Any]:
    params = {
        "query.cond": condition,
        "query.intr": intervention,
        "query.locn": country,
        "filter.overallStatus": status,
        "pageSize": max(1, min(page_size, 100)),
        "countTotal": "true",
        "format": "json",
    }
    data = get_json(CTGOV, params=params)
    out = []
    for s in data.get("studies", []):
        p = s.get("protocolSection", {})
        ident, st, des = p.get("identificationModule", {}), p.get("statusModule", {}), p.get("designModule", {})
        out.append(
            {
                "nct_id": ident.get("nctId"),
                "title": ident.get("briefTitle"),
                "status": st.get("overallStatus"),
                "start": (st.get("startDateStruct") or {}).get("date"),
                "completion": (st.get("completionDateStruct") or {}).get("date"),
                "study_type": des.get("studyType"),
                "phases": des.get("phases"),
                "enrollment": (des.get("enrollmentInfo") or {}).get("count"),
                "conditions": p.get("conditionsModule", {}).get("conditions"),
                "has_results": s.get("hasResults"),
            }
        )
    return {"total": data.get("totalCount"), "results": out}


# ---------------------------------------------------------------- Crossref
def crossref_lookup(doi: str) -> dict[str, Any]:
    d = normalize_doi(doi)
    m = get_json(f"{CROSSREF}/{d}")["message"]
    issued = (m.get("issued") or {}).get("date-parts", [[None]])[0]
    return {
        "source": "Crossref",
        "doi": d,
        "title": (m.get("title") or [None])[0],
        "venue": (m.get("container-title") or [None])[0],
        "issn": m.get("ISSN"),
        "publisher": m.get("publisher"),
        "year": issued[0] if issued else None,
        "type": m.get("type"),
        "authors": [f"{a.get('family', '')}, {a.get('given', '')}".strip(", ") for a in m.get("author", [])][:20],
        "references_count": m.get("references-count"),
        "is_referenced_by_count": m.get("is-referenced-by-count"),
        "license": [lic.get("URL") for lic in m.get("license", [])],
    }


# ---------------------------------------------------------------- WHO GHO
def who_indicator_search(keyword: str) -> dict[str, Any]:
    kw = keyword.replace("'", "''")
    data = get_json(f"{GHO}/Indicator", params={"$filter": f"contains(IndicatorName,'{kw}')"})
    return {"results": [{"code": i["IndicatorCode"], "name": i["IndicatorName"]} for i in data.get("value", [])][:50]}


def who_indicator_values(code: str, country_iso3: str = "IDN") -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_]+", code) or not re.fullmatch(r"[A-Za-z]{3}", country_iso3):
        raise ValueError("indicator code must be alphanumeric/underscore and country an ISO3 code")
    data = get_json(f"{GHO}/{code}", params={"$filter": f"SpatialDim eq '{country_iso3.upper()}'"})
    rows = [
        {
            "year": v.get("TimeDim"),
            "value": v.get("NumericValue"),
            "display": v.get("Value"),
            "dim1": v.get("Dim1"),
            "low": v.get("Low"),
            "high": v.get("High"),
        }
        for v in data.get("value", [])
    ]
    rows.sort(key=lambda r: (r["year"] or 0, r["dim1"] or ""))
    return {"indicator": code, "country": country_iso3.upper(), "rows": rows, "cite_as": f"WHO GHO indicator {code}"}
