---
name: market-news
description: Market and news monitor with the research-analytics MCP server — latest Bloomberg headlines (official public RSS, by section and keyword), stock/index quotes, daily history with return, volatility and drawdown, FX rates (e.g. USD/IDR), and news sentiment (Alpha Vantage). Use for "berita Bloomberg", "berita pasar", "market hari ini", "harga saham", "kurs rupiah", "sentimen pasar", "news healthcare/pharma", "update makro", or to add market and news context to market research and journal background.
metadata:
  version: "1.0"
  requires: research-analytics MCP server; ALPHA_VANTAGE_API_KEY for quotes, history, FX and sentiment (Bloomberg headlines need no key)
---

# Market & news monitor

Answer in the user's language. Bloomberg is a trademark of Bloomberg L.P.; this toolkit is not
affiliated with it and does **not** give Bloomberg Terminal data. What it gives:

| Need | Tool | Key |
|:--|:--|:--|
| Latest Bloomberg headlines | `bloomberg_headlines(sections, query, limit)` | none |
| Quote | `market_quote(symbol)` | Alpha Vantage |
| Find a ticker | `market_symbol_search("Kalbe Farma")` | Alpha Vantage |
| Trend, volatility, drawdown | `market_history(symbol, days)` | Alpha Vantage |
| Exchange rate | `market_fx_rate("USD", "IDR")` | Alpha Vantage |
| News with sentiment | `market_news_sentiment(tickers, topics, limit, sources)` | Alpha Vantage |

Alpha Vantage free keys allow about 25 requests per day: plan calls, reuse results, and say when
the limit is hit.

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
2. Optional context: `market_fx_rate("USD","IDR")`, `market_quote` for the indices or stocks the
   user follows.
3. Output: 5–8 bullets with time and link, then a small table of quotes/FX with the trading day.

### Topic or company watch
1. `bloomberg_headlines(["markets","industries","technology"], query="<keywords>")` — keywords in
   English work best (e.g. "Indonesia", "pharma", "hospital", "dental").
2. `market_symbol_search` → `market_history(symbol, 100)` for return, volatility, max drawdown.
3. `market_news_sentiment(tickers="<SYMBOL>")` → mean sentiment and the label mix; quote 3–5
   headlines with source and time.

### Feed market research and papers
- In the `marketresearch` skill: use `market_fx_rate` for the `local_per_usd` input (record the
  timestamp as its source), and headlines on competitors, funding, regulation for section M4.
- For a paper's background or discussion: recent headlines show current relevance; cite them as news,
  not as evidence, and keep scientific claims tied to the literature.

## Optional visual dashboard

A community Next.js "terminal-style" dashboard exists at github.com/feremabraz/bloomberg-terminal.
It is a UI demo (simulated market moves plus Alpha Vantage quotes; needs Upstash Redis and other
keys), not an MCP server and not Bloomberg data. Run it separately if a visual screen is wanted.
