import pytest

from research_analytics_mcp import analytics, database, literature, market, training


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("RA_MCP_DB", str(tmp_path / "t.db"))


# ---------------------------------------------------------------- literature helpers
def test_abstract_reconstruction():
    inv = {"Caries": [0], "is": [1], "common": [2]}
    assert literature.abstract_from_inverted_index(inv) == "Caries is common"


def test_normalize_doi():
    assert literature.normalize_doi("https://doi.org/10.1000/ABC") == "10.1000/abc"
    assert literature.normalize_doi("doi:10.1/x") == "10.1/x"


def test_evidence_level():
    assert literature.evidence_level(["Journal Article", "Randomized Controlled Trial"])["level"] == 2
    assert literature.evidence_level(["Journal Article"])["design"] == "not stated"


# ---------------------------------------------------------------- database
def test_papers_dedupe_and_matrix(tmp_path):
    database.create_project("sdf")
    r = database.add_papers("sdf", [
        {"title": "Silver diamine fluoride in children", "doi": "10.1/a", "authors": ["Lee A", "Kim B"], "year": 2022, "source": "OpenAlex"},
        {"title": "Another paper", "pmid": "123", "year": 2021, "source": "PubMed"},
    ])
    assert r == {"added": 2, "merged_duplicates": 0}
    r = database.add_papers("sdf", [{"title": "Silver Diamine Fluoride in Children.", "pmid": "999", "source": "PubMed"}])
    assert r["merged_duplicates"] == 1
    p = database.list_papers("sdf", search="Silver")[0]
    assert p["pmid"] == "999" and "PubMed" in p["source"]
    database.update_paper(p["id"], {"status": "included", "method": "RCT", "evidence_level": 2})
    m = database.literature_matrix("sdf")
    assert len(m) == 1 and m[0]["author_year"] == "Lee A et al. (2022)" and m[0]["finding"] == "not stated"
    out = database.export_matrix_csv("sdf", str(tmp_path / "m.csv"))
    assert out["rows"] == 1
    database.log_search("sdf", "PubMed", "x", 40)
    pr = database.prisma_counts("sdf")
    assert pr["included"] == 1 and pr["records_identified"] == 40


def test_journal_quartile_needs_source():
    database.create_project("j")
    with pytest.raises(ValueError):
        database.save_journal("j", {"name": "X", "quartile": "Q1"})
    assert database.save_journal("j", {"name": "X", "quartile": "Q1", "quartile_source": "SCImago 2026-11-15"})["journal_id"]


def test_observations_wide_csv(tmp_path):
    database.create_project("obs", kind="observation")
    f = tmp_path / "o.csv"
    f.write_text("pasien,kelompok,plak,gingiva\nP1,A,1.2,0\nP2,B,\"2,5\",1\n", encoding="utf-8")
    r = database.import_observations_csv("obs", str(f), {"pasien": "subject", "kelompok": "group"})
    assert r["inserted"] == 4
    rows = database.query_observations("obs", variable="plak")
    assert [x["value_num"] for x in rows] == [1.2, 2.5]


# ---------------------------------------------------------------- analytics
ROWS = [{"g": "A", "y": v} for v in (5.1, 4.9, 5.3, 5.0, 5.2, 4.8)] + [{"g": "B", "y": v} for v in (6.1, 6.3, 5.9, 6.0, 6.2, 6.4)]


def test_describe():
    d = analytics.describe(ROWS)
    assert d["columns"]["y"]["type"] == "numeric" and d["columns"]["g"]["type"] == "categorical"


def test_compare_two_groups():
    r = analytics.compare_groups(ROWS, "g", "y")
    assert r["p_value"] < 0.001 and r["test"] in ("Welch t-test", "Mann-Whitney U")


def test_compare_three_groups():
    rows = ROWS + [{"g": "C", "y": v} for v in (7.0, 7.2, 6.9, 7.1, 7.3, 6.8)]
    assert analytics.compare_groups(rows, "g", "y", parametric=True)["test"] == "One-way ANOVA"


def test_paired_and_gain():
    rows = [{"pre": a, "post": b} for a, b in [(40, 70), (50, 75), (55, 80), (60, 85), (45, 72), (52, 78)]]
    r = analytics.paired_compare(rows, "pre", "post", max_score=100)
    assert r["mean_change"] > 0 and r["normalized_gain"]["category"] in ("medium", "high")


def test_crosstab_fisher():
    rows = [{"a": "y", "b": "y"}] * 3 + [{"a": "n", "b": "n"}] * 3 + [{"a": "y", "b": "n"}]
    r = analytics.crosstab(rows, "a", "b")
    assert "fisher_exact" in r


def test_kappa_perfect():
    rows = [{"a": x, "b": x} for x in "yynny"]
    assert analytics.cohen_kappa(rows, "a", "b")["kappa"] == 1.0


def test_sample_size_lemeshow():
    assert analytics.sample_size("proportion", proportion=0.5, margin=0.05)["n"] == 385


def test_trend_rising():
    rows = [{"t": y, "v": 10 + 2 * i} for i, y in enumerate(range(2015, 2025))]
    assert analytics.trend(rows, "t", "v")["direction"] == "rising"


# ---------------------------------------------------------------- market
def test_market_example_runs():
    res = market.market_model(market.example_assumptions())
    s = res["scenarios"]
    assert s["low"]["value"] < s["base"]["value"] < s["high"]["value"]
    assert res["consistency_check"].startswith("ok")


def test_market_requires_sources():
    A = market.example_assumptions()
    A["population"]["source"] = ""
    with pytest.raises(ValueError):
        market.market_model(A)


def test_regional_split():
    regs = [
        {"region": "A", "population": 10e6, "income_per_capita": 100, "providers": 100},
        {"region": "B", "population": 8e6, "income_per_capita": 80, "providers": 5},
        {"region": "C", "population": 1e6, "income_per_capita": 60, "providers": 2},
    ]
    out = market.regional_split({"base": 1000.0}, regs)
    assert abs(sum(r["value_base"] for r in out["regions"]) - 1000) < 0.1
    assert any(r["white_space"] for r in out["regions"])


# ---------------------------------------------------------------- training
def test_blueprint_and_checklist():
    database.create_project("tr", kind="training")
    b = training.training_blueprint("hand hygiene", "nurses", 90, project="tr")
    assert sum(a["minutes"] for a in b["agenda"]) == 90
    c = training.observation_checklist("hand hygiene", ["wet", "soap", "rub 20 s", "rinse", "dry"], critical_steps=[3])
    assert c["items"][2]["critical"] is True


def test_kirkpatrick_report():
    database.create_project("tr2", kind="training")
    rows = []
    for i, (pre, post) in enumerate([(40, 70), (50, 80), (55, 85), (60, 82), (45, 75)]):
        s = f"P{i}"
        rows += [{"subject": s, "variable": "pre_score", "value": pre}, {"subject": s, "variable": "post_score", "value": post},
                 {"subject": s, "variable": "reaction_overall", "value": 4 + i % 2}]
        for step in range(1, 4):
            for obs in ("O1", "O2"):
                rows.append({"subject": s, "session": "followup", "observer": obs, "variable": f"step_{step:02d}", "value": 1})
    database.add_observations("tr2", rows)
    rep = training.kirkpatrick_report("tr2")
    assert "L1_reaction" in rep and "L2_learning" in rep and "L3_behaviour_checklist" in rep
    assert rep["inter_rater"]["kappa"] == 1.0


def test_media_dry_run_needs_no_key(monkeypatch):
    monkeypatch.delenv("MUAPI_API_KEY", raising=False)
    r = training.media_generate("some-text-to-video", {"prompt": "x"})
    assert r["dry_run"] is True


def test_server_registers_tools():
    import asyncio

    from research_analytics_mcp import server

    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    assert {"search_openalex", "search_pubmed", "db_literature_matrix", "market_size_model", "media_generate"} <= names


# ---------------------------------------------------------------- teaching video
def test_lesson_plan_flags_unsourced_numbers(tmp_path):
    from research_analytics_mcp import video

    database.create_project("vid", kind="training")
    database.add_papers("vid", [{"title": "Bass technique trial", "authors": ["Ali R"], "year": 2023, "status": "included"}])
    pid = database.list_papers("vid")[0]["id"]
    scenes = [
        {"purpose": "hook", "narration": "Gigi berlubang masih sering terjadi pada anak."},
        {"purpose": "objectives", "narration": "Setelah video ini Anda dapat menyikat gigi dengan metode Bass."},
        {"purpose": "demo", "narration": "Sikat selama 2 menit, dua kali sehari.", "paper_ids": [pid]},
        {"purpose": "demo", "narration": "Gunakan pasta 1000 ppm fluoride."},
        {"purpose": "summary", "narration": "Ingat tiga langkah utama."},
        {"purpose": "quiz", "narration": "Berapa lama Anda menyikat gigi?"},
    ]
    plan = video.lesson_plan("Metode Bass", scenes, out_dir=str(tmp_path), project="vid")
    assert plan["scenes"][2]["issues"] == [] and plan["scenes"][2]["references"] == ["Ali R (2023)"]
    assert any("PERLU SUMBER" in x for x in plan["scenes"][3]["issues"])
    assert plan["ready_for_render"] is False and (tmp_path / "edit-plan.md").exists()
    cap = video.captions(plan["scenes"], out_dir=str(tmp_path))
    srt = (tmp_path / "captions.srt").read_text()
    assert cap["cues"] >= 6 and srt.startswith("1\n00:00:00,000 --> ")
    assert all(len(line) <= 42 for line in srt.splitlines())


def test_video_probe(tmp_path):
    import shutil
    import subprocess

    from research_analytics_mcp import video

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    f = tmp_path / "t.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=1",
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest", "-pix_fmt", "yuv420p", str(f)], check=True)
    p = video.probe(str(f))
    assert p["video"]["width"] == 320 and p["video"]["fps"] == 30.0 and p["audio"] and p["ready_for_concat"]


# ---------------------------------------------------------------- markets & news
RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>Bloomberg Markets</title>
<item><title><![CDATA[Rupiah Gains as Bank Indonesia Holds Rates]]></title>
<description><![CDATA[<p>The rupiah rose after the central bank kept its benchmark rate.</p>]]></description>
<link>https://www.bloomberg.com/news/articles/x1</link><pubDate>Tue, 24 Nov 2026 10:30:00 GMT</pubDate></item>
<item><title>Oil Falls</title><description>Crude slid.</description>
<link>https://www.bloomberg.com/news/articles/x2</link><pubDate>Tue, 24 Nov 2026 09:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_parse_bloomberg_rss():
    from research_analytics_mcp import markets

    items = markets.parse_rss(RSS, "markets")
    assert items[0]["title"].startswith("Rupiah") and items[0]["summary"].startswith("The rupiah")
    assert items[0]["published"].startswith("2026-11-24T10:30") and items[0]["section"] == "Markets"


def test_bloomberg_query_filter(monkeypatch):
    from research_analytics_mcp import markets

    monkeypatch.setattr(markets, "get_text", lambda url, **kw: RSS)
    r = markets.bloomberg_headlines(["markets", "economics"], query="rupiah bank")
    assert r["count"] == 1 and r["items"][0]["url"].endswith("x1")  # de-duplicated across sections
    with pytest.raises(ValueError):
        markets.bloomberg_headlines(["sports"])


def test_history_stats():
    from research_analytics_mcp import markets

    s = markets.history_stats([("d1", 100.0), ("d2", 110.0), ("d3", 99.0), ("d4", 105.0)])
    assert s["period_return_pct"] == 5.0 and s["max_drawdown_pct"] == -10.0


def test_alpha_vantage_needs_key(monkeypatch):
    from research_analytics_mcp import markets
    from research_analytics_mcp.http import UpstreamError

    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)
    with pytest.raises(UpstreamError, match="ALPHA_VANTAGE_API_KEY"):
        markets.quote("IBM")


def test_rss_nested_title_and_odd_date():
    from research_analytics_mcp import markets

    xml = """<rss><channel><item><title><a href="/x">Health insurance costs rise</a></title>
    <link>https://example.org/x</link><description>Survey.</description><pubDate>Nov 23, 2026 3:17pm</pubDate></item>
    <item><title>Rupiah firm</title><link>https://example.org/y</link><pubDate>Tue, 24 Nov 2026 17:35:00 +0700</pubDate></item>
    </channel></rss>"""
    items = markets.parse_rss(xml, "fierce_healthcare", source="Fierce Healthcare")
    assert items[0]["title"] == "Health insurance costs rise" and items[0]["published"] == "2026-11-23T15:17:00"
    assert items[1]["published"] == "2026-11-24T10:35:00+00:00"


def test_news_feed_validation():
    from research_analytics_mcp import markets

    with pytest.raises(ValueError):
        markets.news_headlines(["not_a_feed"])
    with pytest.raises(ValueError):
        markets.macro_indicator("inflation", country="IDN/../x")
