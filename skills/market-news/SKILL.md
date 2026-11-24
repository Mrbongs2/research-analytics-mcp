---
name: market-news
description: Market and news monitor with the research-analytics MCP server — latest Bloomberg headlines (official public RSS, no key), more public news feeds (CNBC, MarketWatch, CNBC Indonesia, Antara, Fierce Healthcare, STAT), FX rates and history (ECB, no key), World Bank macro and health-spending indicators (no key), plus optional stock quotes, price history and news sentiment with a free Alpha Vantage key. Use for "berita Bloomberg", "berita pasar", "market hari ini", "harga saham", "kurs rupiah", "sentimen pasar", "news healthcare/pharma", "update makro", or to add market and news context to market research and journal background.
metadata:
  version: "1.0"
  requires: research-analytics MCP server; works without any key; optional free ALPHA_VANTAGE_API_KEY adds stock quotes, price history and news sentiment
---

# Market & news monitor

Answer in the user's language. Bloomberg is a trademark of Bloomberg L.P.; this toolkit is not
affiliated with it and does **not** give Bloomberg Terminal data. What it gives:

**Without any key**

| Need | Tool |
|:--|:--|
| Latest Bloomberg headlines | `bloomberg_headlines(sections, query, limit)` — markets, economics, technology, industries, politics, businessweek, crypto, bview |
| Other news (global, Indonesia, health) | `news_headlines(feeds, query, limit)` — cnbc_markets, marketwatch, cnbc_indonesia_market, cnbc_indonesia_news, antara_ekonomi, fierce_healthcare, statnews |
| Exchange rate | `market_fx_rate("USD", "IDR")` — ECB daily reference rate when no key is set |
| FX trend, volatility, drawdown | `market_fx_history("USD", "IDR", start="2025-01-01")` |
| Macro & health indicators | `macro_indicator("health_spending_per_capita_usd", "IDN;MYS;THA")` — also gdp_growth, inflation, gdp_per_capita_usd, population, out_of_pocket_pct_health, physicians_per_1000, unemployment, lending_rate, or any World Bank code |

**With a free Alpha Vantage key** (alphavantage.co, no payment; about 25 requests per day)

| Need | Tool |
|:--|:--|
| Stock / index quote | `market_quote(symbol)` |
| Find a ticker | `market_symbol_search("Kalbe Farma")` |
| Price trend, volatility, drawdown | `market_history(symbol, days)` |
| Real-time FX | `market_fx_rate` switches to Alpha Vantage automatically |
| News with sentiment scores | `market_news_sentiment(tickers, topics, limit, sources)` |

Without the key, say that stock prices are unavailable and continue with headlines, FX and macro data.

## Rules

- **Headlines, not articles.** Show title, one-line summary, time and link; cite "Bloomberg, <date>".
  Never paste or reconstruct article text; the full story needs a Bloomberg subscription.
- Prices are delayed/end-of-day from Alpha Vantage, not a trading feed. State the trading day.
- **No investment advice.** Describe what happened and the data; do not recommend buying or selling.
- Never invent a number or headline: everything comes from a tool result, with its time.

## Workflows

### Daily market brief
1. `bloomberg_headlines(["markets", "economics"], limit=15)` → group by theme (rates, FX,
   commodities, equities, policy).
2. Indonesia angle: `news_headlines(["cnbc_indonesia_market","antara_ekonomi"], limit=10)`.
3. Context: `market_fx_rate("USD","IDR")`; with a key, `market_quote` for the indices or stocks the user follows.
4. Output: 5–8 bullets with outlet, time and link, then a small table of FX (and quotes) with dates.

### Topic or company watch
1. `bloomberg_headlines(["markets","industries","technology"], query="<keywords>")` — keywords in
   English work best (e.g. "Indonesia", "pharma", "hospital", "dental").
2. `market_symbol_search` → `market_history(symbol, 100)` for return, volatility, max drawdown.
3. `market_news_sentiment(tickers="<SYMBOL>")` → mean sentiment and the label mix; quote 3–5
   headlines with source and time.

### Health-sector watch
- `news_headlines(["fierce_healthcare","statnews"], query="<topic>")` and
  `bloomberg_headlines(["industries"], query="health")` for industry news.
- `macro_indicator("health_spending_per_capita_usd", "IDN;MYS;THA;VNM;PHL")` and
  `"out_of_pocket_pct_health"` for the ability-to-pay context in market sizing.

### Feed market research and papers
- In the `marketresearch` skill: use `market_fx_rate` for the `local_per_usd` input (record the
  date and source), World Bank indicators for income and health spending, and headlines on
  competitors, funding and regulation for section M4.
- For a paper's background or discussion: recent headlines show current relevance; cite them as news,
  not as evidence, and keep scientific claims tied to the literature.

## Optional visual dashboard

A community Next.js "terminal-style" dashboard exists at github.com/feremabraz/bloomberg-terminal.
It is a UI demo (simulated market moves plus Alpha Vantage quotes; needs Upstash Redis and other
keys), not an MCP server and not Bloomberg data. Run it separately if a visual screen is wanted.
