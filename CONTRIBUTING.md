# Contributing

1. Fork, create a branch, `uv venv && uv pip install -e ".[dev]"`.
2. Add or change a tool in `src/research_analytics_mcp/` and register it in `server.py`.
3. Add an offline test in `tests/test_offline.py`; live API checks go in `tests/test_network.py`
   (marked `network`).
4. `ruff check . && pytest -m "not network"` must pass.
5. If a skill's workflow changes, update its `skills/<name>/SKILL.md`.

Rules for new data sources: free/public APIs only, every result carries a `source` field, and
nothing may present an estimate or assumption as observed data.
