"""Market data and financial news.

- Bloomberg headlines from Bloomberg's own public RSS feeds (headline, short summary, link, time).
  Full articles need a Bloomberg subscription; this module never fetches or reproduces article text.
- More public news feeds (CNBC, MarketWatch, CNBC Indonesia, Antara, Fierce Healthcare, STAT), no key.
- FX reference rates from the European Central Bank via Frankfurter (no key) and macro indicators
  from the World Bank API (no key).
- Quotes, daily history, FX and news sentiment from Alpha Vantage (free key: ALPHA_VANTAGE_API_KEY;
  the free tier allows about 25 requests per day).

Bloomberg is a trademark of Bloomberg L.P.; this project is not affiliated with or endorsed by it.
"""

from __future__ import annotations

import math
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from statistics import mean, stdev
from typing import Any

from .http import UpstreamError, get_json, get_text

BLOOMBERG_FEEDS = {
    "markets": "Markets",
    "economics": "Economics",
    "technology": "Technology",
    "industries": "Industries",
    "politics": "Politics",
    "businessweek": "Businessweek",
    "crypto": "Crypto",
    "bview": "Opinion",
}
ALPHA = "https://www.alphavantage.co/query"
_TAG = re.compile(r"<[^>]+>")


# ---------------------------------------------------------------- Bloomberg RSS
def _text(el: ET.Element | None) -> str:
    """Element text including nested markup (some feeds wrap titles in <a>)."""
    return "".join(el.itertext()).strip() if el is not None else ""


def _when(pub: str | None) -> str | None:
    if not pub:
        return None
    dt = None
    try:
        dt = parsedate_to_datetime(pub)
    except (TypeError, ValueError):
        for fmt in ("%b %d, %Y %I:%M%p", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(pub.strip(), fmt)
                break
            except ValueError:
                continue
    if dt is None:
        return None
    return (dt.astimezone(timezone.utc) if dt.tzinfo else dt).isoformat()  # UTC so feeds sort together


def parse_rss(xml_text: str, section: str, source: str = "Bloomberg (public RSS)") -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    items = []
    for it in root.iter("item"):
        summary = _TAG.sub("", _text(it.find("description")))
        title = _text(it.find("title"))
        if not title:
            continue
        items.append({
            "section": BLOOMBERG_FEEDS.get(section, section),
            "title": title,
            "summary": summary[:300] + ("…" if len(summary) > 300 else ""),
            "url": (it.findtext("link") or "").strip(),
            "published": _when(it.findtext("pubDate")),
            "source": source,
        })
    return items


def bloomberg_headlines(sections: list[str] | None = None, query: str | None = None, limit: int = 20) -> dict[str, Any]:
    sections = sections or ["markets"]
    bad = [s for s in sections if s not in BLOOMBERG_FEEDS]
    if bad:
        raise ValueError(f"unknown section(s) {bad}; choose from {list(BLOOMBERG_FEEDS)}")
    items, errors = [], {}
    for s in sections:
        try:
            items += parse_rss(get_text(f"https://feeds.bloomberg.com/{s}/news.rss",
                                        headers={"Accept": "application/rss+xml, application/xml"}), s)
        except (UpstreamError, ET.ParseError) as e:
            errors[s] = str(e)[:200]
    if query:
        words = [w.lower() for w in query.split()]
        items = [i for i in items if all(w in f"{i['title']} {i['summary']}".lower() for w in words)]
    seen, unique = set(), []
    for i in sorted(items, key=lambda i: i["published"] or "", reverse=True):
        if i["url"] not in seen:
            seen.add(i["url"])
            unique.append(i)
    out: dict[str, Any] = {
        "sections": sections, "query": query, "count": min(len(unique), limit), "items": unique[:limit],
        "note": "Headlines and summaries from Bloomberg's public feeds; open the link for the article "
                "(subscription may be required). Cite as Bloomberg with date; do not copy article text.",
    }
    if errors:
        out["errors"] = errors
    return out


# ---------------------------------------------------------------- Alpha Vantage
def _av(params: dict[str, Any]) -> dict[str, Any]:
    key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not key:
        raise UpstreamError("ALPHA_VANTAGE_API_KEY is not set. Get a free key at alphavantage.co/support/#api-key "
                            "and add it to the server env.")
    d = get_json(ALPHA, params={**params, "apikey": key})
    for k in ("Note", "Information", "Error Message"):
        if k in d:
            raise UpstreamError(f"Alpha Vantage: {d[k][:300]}")
    return d


def _num(x: Any) -> float | None:
    try:
        return float(str(x).rstrip("%"))
    except (TypeError, ValueError):
        return None


def quote(symbol: str) -> dict[str, Any]:
    q = _av({"function": "GLOBAL_QUOTE", "symbol": symbol}).get("Global Quote") or {}
    if not q:
        raise UpstreamError(f"no quote for {symbol!r}; try market_symbol_search")
    return {
        "symbol": q.get("01. symbol"), "price": _num(q.get("05. price")), "open": _num(q.get("02. open")),
        "high": _num(q.get("03. high")), "low": _num(q.get("04. low")), "previous_close": _num(q.get("08. previous close")),
        "change": _num(q.get("09. change")), "change_pct": _num(q.get("10. change percent")),
        "volume": _num(q.get("06. volume")), "trading_day": q.get("07. latest trading day"), "source": "Alpha Vantage",
    }


def symbol_search(keywords: str) -> dict[str, Any]:
    m = _av({"function": "SYMBOL_SEARCH", "keywords": keywords}).get("bestMatches", [])
    return {"matches": [{"symbol": x.get("1. symbol"), "name": x.get("2. name"), "type": x.get("3. type"),
                         "region": x.get("4. region"), "currency": x.get("8. currency"),
                         "match_score": _num(x.get("9. matchScore"))} for x in m]}


def history_stats(closes: list[tuple[str, float]]) -> dict[str, Any]:
    """closes: [(date, close)] in ascending date order."""
    if len(closes) < 3:
        raise ValueError("need at least 3 closes")
    vals = [c for _, c in closes]
    rets = [vals[i] / vals[i - 1] - 1 for i in range(1, len(vals))]
    peak, mdd = vals[0], 0.0
    for v in vals:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    return {
        "first": {"date": closes[0][0], "close": vals[0]}, "last": {"date": closes[-1][0], "close": vals[-1]},
        "period_return_pct": round((vals[-1] / vals[0] - 1) * 100, 2),
        "mean_daily_return_pct": round(mean(rets) * 100, 3),
        "annualized_volatility_pct": round(stdev(rets) * math.sqrt(252) * 100, 2) if len(rets) > 1 else None,
        "max_drawdown_pct": round(mdd * 100, 2),
        "high": max(vals), "low": min(vals), "n_days": len(vals),
    }


def daily(symbol: str, days: int = 100) -> dict[str, Any]:
    ts = _av({"function": "TIME_SERIES_DAILY", "symbol": symbol, "outputsize": "compact"}).get("Time Series (Daily)", {})
    if not ts:
        raise UpstreamError(f"no daily series for {symbol!r}")
    closes = sorted((d, float(v["4. close"])) for d, v in ts.items())[-max(3, min(days, 100)):]
    return {"symbol": symbol, "stats": history_stats(closes),
            "closes": [{"date": d, "close": c} for d, c in closes], "source": "Alpha Vantage (daily, unadjusted)"}


def fx_rate(from_currency: str, to_currency: str) -> dict[str, Any]:
    r = _av({"function": "CURRENCY_EXCHANGE_RATE", "from_currency": from_currency.upper(),
             "to_currency": to_currency.upper()}).get("Realtime Currency Exchange Rate", {})
    return {"from": r.get("1. From_Currency Code"), "to": r.get("3. To_Currency Code"),
            "rate": _num(r.get("5. Exchange Rate")), "bid": _num(r.get("8. Bid Price")), "ask": _num(r.get("9. Ask Price")),
            "as_of": r.get("6. Last Refreshed"), "timezone": r.get("7. Time Zone"), "source": "Alpha Vantage"}


def news_sentiment(tickers: str | None = None, topics: str | None = None, limit: int = 20,
                   sources: str | None = None) -> dict[str, Any]:
    """tickers e.g. 'AAPL,MSFT' or 'FOREX:USD'; topics e.g. 'economy_macro,financial_markets,life_sciences'."""
    d = _av({"function": "NEWS_SENTIMENT", "tickers": tickers, "topics": topics, "sort": "LATEST",
             "limit": max(1, min(limit, 1000))})
    feed = d.get("feed", [])
    if sources:
        wanted = [s.strip().lower() for s in sources.split(",")]
        feed = [f for f in feed if any(w in (f.get("source") or "").lower() for w in wanted)]
    items = []
    for f in feed[:limit]:
        t = f.get("time_published") or ""
        try:
            t = datetime.strptime(t, "%Y%m%dT%H%M%S").isoformat()
        except ValueError:
            pass
        items.append({"title": f.get("title"), "source": f.get("source"), "url": f.get("url"), "published": t,
                      "sentiment": f.get("overall_sentiment_label"), "sentiment_score": _num(f.get("overall_sentiment_score")),
                      "tickers": [x.get("ticker") for x in f.get("ticker_sentiment", [])][:8]})
    scores = [i["sentiment_score"] for i in items if i["sentiment_score"] is not None]
    labels: dict[str, int] = {}
    for i in items:
        labels[i["sentiment"]] = labels.get(i["sentiment"], 0) + 1
    return {"count": len(items), "mean_sentiment": round(mean(scores), 3) if scores else None, "labels": labels,
            "items": items, "scale": "Alpha Vantage: <= -0.35 bearish, -0.15..0.15 neutral, >= 0.35 bullish"}


# ---------------------------------------------------------------- other public news feeds (no key)
NEWS_FEEDS = {
    "cnbc_markets": ("CNBC Markets", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    "marketwatch": ("MarketWatch Top Stories", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    "cnbc_indonesia_market": ("CNBC Indonesia Market", "https://www.cnbcindonesia.com/market/rss"),
    "cnbc_indonesia_news": ("CNBC Indonesia News", "https://www.cnbcindonesia.com/news/rss"),
    "antara_ekonomi": ("Antara Ekonomi", "https://www.antaranews.com/rss/ekonomi.xml"),
    "fierce_healthcare": ("Fierce Healthcare", "https://www.fiercehealthcare.com/rss/xml"),
    "statnews": ("STAT News (health & biotech)", "https://www.statnews.com/feed/"),
}


def news_headlines(feeds: list[str] | None = None, query: str | None = None, limit: int = 20) -> dict[str, Any]:
    feeds = feeds or ["cnbc_markets", "cnbc_indonesia_market"]
    bad = [f for f in feeds if f not in NEWS_FEEDS]
    if bad:
        raise ValueError(f"unknown feed(s) {bad}; choose from {list(NEWS_FEEDS)}")
    items, errors = [], {}
    for f in feeds:
        label, url = NEWS_FEEDS[f]
        try:
            items += parse_rss(get_text(url, headers={"Accept": "application/rss+xml, application/xml"}), f, source=label)
        except (UpstreamError, ET.ParseError) as e:
            errors[f] = str(e)[:200]
    if query:
        words = [w.lower() for w in query.split()]
        items = [i for i in items if all(w in f"{i['title']} {i['summary']}".lower() for w in words)]
    seen, unique = set(), []
    for i in sorted(items, key=lambda i: i["published"] or "", reverse=True):
        if i["url"] not in seen:
            seen.add(i["url"])
            unique.append(i)
    out: dict[str, Any] = {"feeds": feeds, "query": query, "count": min(len(unique), limit), "items": unique[:limit],
                           "note": "Headlines from each outlet's public RSS; cite outlet and date, link to the article."}
    if errors:
        out["errors"] = errors
    return out


# ---------------------------------------------------------------- FX without a key (ECB via Frankfurter)
FRANKFURTER = "https://api.frankfurter.dev/v1"


def fx_reference(from_currency: str, to_currency: str = "IDR") -> dict[str, Any]:
    d = get_json(f"{FRANKFURTER}/latest", params={"from": from_currency.upper(), "to": to_currency.upper()})
    return {"from": d.get("base"), "to": to_currency.upper(), "rate": (d.get("rates") or {}).get(to_currency.upper()),
            "as_of": d.get("date"), "source": "European Central Bank reference rate (Frankfurter API)",
            "note": "Daily ECB reference rate, not a live trading rate."}


def fx_history(from_currency: str, to_currency: str = "IDR", start: str = "2025-01-01", end: str | None = None) -> dict[str, Any]:
    d = get_json(f"{FRANKFURTER}/{start}..{end or ''}", params={"from": from_currency.upper(), "to": to_currency.upper()})
    rates = sorted((day, v[to_currency.upper()]) for day, v in (d.get("rates") or {}).items() if to_currency.upper() in v)
    if len(rates) < 3:
        raise UpstreamError("not enough FX data for that period")
    return {"pair": f"{from_currency.upper()}/{to_currency.upper()}", "stats": history_stats(rates),
            "rates": [{"date": a, "rate": b} for a, b in rates], "source": "ECB reference rates (Frankfurter API)"}


# ---------------------------------------------------------------- World Bank macro (no key)
WB_ALIASES = {
    "gdp_growth": "NY.GDP.MKTP.KD.ZG",
    "inflation": "FP.CPI.TOTL.ZG",
    "gdp_per_capita_usd": "NY.GDP.PCAP.CD",
    "population": "SP.POP.TOTL",
    "health_spending_pct_gdp": "SH.XPD.CHEX.GD.ZS",
    "health_spending_per_capita_usd": "SH.XPD.CHEX.PC.CD",
    "out_of_pocket_pct_health": "SH.XPD.OOPC.CH.ZS",
    "physicians_per_1000": "SH.MED.PHYS.ZS",
    "unemployment": "SL.UEM.TOTL.ZS",
    "lending_rate": "FR.INR.LEND",
}


def macro_indicator(indicator: str, country: str = "IDN", years: int = 10) -> dict[str, Any]:
    code = WB_ALIASES.get(indicator, indicator)
    if not re.fullmatch(r"[A-Za-z0-9.]+", code) or not re.fullmatch(r"[A-Za-z]{2,3}(;[A-Za-z]{2,3})*", country):
        raise ValueError("indicator must be an alias or a World Bank code; country an ISO2/ISO3 code (';' for several)")
    d = get_json(f"https://api.worldbank.org/v2/country/{country}/indicator/{code}",
                 params={"format": "json", "mrv": max(1, min(years, 60)), "per_page": 500})
    if not isinstance(d, list) or len(d) < 2 or not d[1]:
        msg = d[0].get("message") if isinstance(d, list) and d and isinstance(d[0], dict) else None
        raise UpstreamError(f"World Bank returned no data for {code} / {country}: {msg}")
    rows = [{"country": r["country"]["value"], "year": int(r["date"]), "value": r["value"]} for r in d[1]]
    rows.sort(key=lambda r: (r["country"], r["year"]))
    return {"indicator": code, "name": d[1][0]["indicator"]["value"], "rows": rows,
            "source": f"World Bank WDI, indicator {code}", "aliases": WB_ALIASES}
