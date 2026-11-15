"""Live API smoke tests. Run with: pytest -m network"""

import pytest

from research_analytics_mcp import literature

pytestmark = pytest.mark.network


def test_openalex_search():
    r = literature.openalex_search_works("silver diamine fluoride caries", year_from=2020, per_page=5)
    assert r["results"] and r["results"][0]["title"]


def test_openalex_trend():
    r = literature.openalex_trend("silver diamine fluoride", year_from=2018)
    assert r["groups"]


def test_pubmed():
    r = literature.pubmed_search('"silver diamine fluoride"[tiab]', mindate="2022", retmax=3)
    assert r["total"] > 0 and r["results"][0]["pmid"]
    a = literature.pubmed_abstracts([r["results"][0]["pmid"]])
    assert a["results"]


def test_clinical_trials():
    r = literature.clinical_trials_search("dental caries", page_size=3)
    assert r["results"]


def test_journal_issn():
    r = literature.journal_profile("0022-0345")  # Journal of Dental Research
    assert r["matches"][0]["name"]


def test_openverse():
    from research_analytics_mcp import video

    r = video.openverse_search("tooth anatomy", n=3)
    assert r["hits"] and r["hits"][0]["license"]
