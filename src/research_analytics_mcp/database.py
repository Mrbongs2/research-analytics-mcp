"""Local research database (SQLite): projects, papers (literature matrix + screening),
notes, journal shortlist, field observations and training evaluations.

Location: $RA_MCP_DB, default ~/.research-analytics-mcp/research.db
"""

from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from .literature import normalize_doi

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, kind TEXT, description TEXT, created TEXT
);
CREATE TABLE IF NOT EXISTS papers (
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  title TEXT NOT NULL, authors TEXT, year INTEGER, venue TEXT, doi TEXT, pmid TEXT, openalex_id TEXT,
  source TEXT, cited_by INTEGER, abstract TEXT, oa_url TEXT,
  method TEXT, data_context TEXT, finding TEXT, limitation TEXT, theme TEXT, evidence_level INTEGER,
  status TEXT DEFAULT 'candidate', exclusion_reason TEXT, added TEXT
);
CREATE INDEX IF NOT EXISTS papers_doi ON papers(project_id, doi);
CREATE TABLE IF NOT EXISTS searches (
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  database TEXT, query TEXT, hits INTEGER, run_date TEXT
);
CREATE TABLE IF NOT EXISTS notes (
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  paper_id INTEGER REFERENCES papers(id) ON DELETE SET NULL, text TEXT NOT NULL, tags TEXT, created TEXT
);
CREATE TABLE IF NOT EXISTS journals (
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL, issn TEXT, publisher TEXT, h_index INTEGER, citedness REAL, is_oa INTEGER,
  apc_usd REAL, scopus_status TEXT DEFAULT 'unchecked', quartile TEXT, quartile_source TEXT, fit_reason TEXT
);
CREATE TABLE IF NOT EXISTS observations (
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  session TEXT, subject TEXT, grp TEXT, variable TEXT NOT NULL, value_num REAL, value_text TEXT,
  unit TEXT, observer TEXT, observed_at TEXT, notes TEXT
);
CREATE INDEX IF NOT EXISTS obs_var ON observations(project_id, variable);
"""

TABLES = ("projects", "papers", "searches", "notes", "journals", "observations")
PAPER_FIELDS = ["title", "authors", "year", "venue", "doi", "pmid", "openalex_id", "source", "cited_by", "abstract", "oa_url", "method", "data_context", "finding", "limitation", "theme", "evidence_level", "status", "exclusion_reason"]
STATUSES = ("candidate", "screened", "included", "excluded")


def db_path() -> Path:
    p = Path(os.getenv("RA_MCP_DB", Path.home() / ".research-analytics-mcp" / "research.db")).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open, yield, commit (or roll back on error) and always close."""
    con = sqlite3.connect(db_path())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _rows(cur: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in cur]


def project_id(con: sqlite3.Connection, project: str | int) -> int:
    if isinstance(project, int) or str(project).isdigit():
        row = con.execute("SELECT id FROM projects WHERE id=?", (int(project),)).fetchone()
    else:
        row = con.execute("SELECT id FROM projects WHERE name=?", (project,)).fetchone()
    if not row:
        raise ValueError(f"project {project!r} not found; create it with db_create_project")
    return row["id"]


def _title_key(t: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())[:120]


# ---------------------------------------------------------------- projects
def create_project(name: str, kind: str = "literature", description: str = "") -> dict[str, Any]:
    with connect() as con:
        con.execute(
            "INSERT OR IGNORE INTO projects(name, kind, description, created) VALUES (?,?,?,?)",
            (name, kind, description, _now()),
        )
        return dict(con.execute("SELECT * FROM projects WHERE name=?", (name,)).fetchone())


def list_projects() -> list[dict[str, Any]]:
    with connect() as con:
        return _rows(
            con.execute(
                """SELECT p.*, (SELECT COUNT(*) FROM papers WHERE project_id=p.id) AS papers,
                   (SELECT COUNT(*) FROM observations WHERE project_id=p.id) AS observations
                   FROM projects p ORDER BY p.id"""
            )
        )


# ---------------------------------------------------------------- papers
def add_papers(project: str | int, papers: list[dict[str, Any]]) -> dict[str, Any]:
    """Insert papers, de-duplicating on DOI, then PMID, then normalised title. Missing fields in an
    existing row are filled from the new record (so a PubMed hit adds its PMID to an OpenAlex row)."""
    added, merged = 0, 0
    with connect() as con:
        pid = project_id(con, project)
        existing = _rows(con.execute("SELECT id, doi, pmid, title FROM papers WHERE project_id=?", (pid,)))
        by_doi = {e["doi"]: e["id"] for e in existing if e["doi"]}
        by_pmid = {e["pmid"]: e["id"] for e in existing if e["pmid"]}
        by_title = {_title_key(e["title"]): e["id"] for e in existing}
        for p in papers:
            rec = {k: p.get(k) for k in PAPER_FIELDS}
            if not rec["title"]:
                continue
            rec["doi"] = normalize_doi(rec["doi"])
            if isinstance(rec["authors"], list):
                rec["authors"] = "; ".join(a for a in rec["authors"] if a)
            rec["status"] = rec["status"] or "candidate"
            hit = by_doi.get(rec["doi"]) or by_pmid.get(rec["pmid"]) or by_title.get(_title_key(rec["title"]))
            if hit:
                cur = dict(con.execute("SELECT * FROM papers WHERE id=?", (hit,)).fetchone())
                fill = {k: v for k, v in rec.items() if v not in (None, "") and cur.get(k) in (None, "")}
                if rec.get("source") and rec["source"] not in (cur.get("source") or ""):
                    fill["source"] = f"{cur['source']}; {rec['source']}" if cur.get("source") else rec["source"]
                if fill:
                    con.execute(
                        f"UPDATE papers SET {', '.join(f'{k}=?' for k in fill)} WHERE id=?", (*fill.values(), hit)
                    )
                merged += 1
                continue
            cols = [k for k, v in rec.items() if v is not None]
            cur = con.execute(
                f"INSERT INTO papers(project_id, added, {', '.join(cols)}) VALUES (?,?,{','.join('?' * len(cols))})",
                (pid, _now(), *[rec[c] for c in cols]),
            )
            new_id = cur.lastrowid
            if rec["doi"]:
                by_doi[rec["doi"]] = new_id
            if rec["pmid"]:
                by_pmid[rec["pmid"]] = new_id
            by_title[_title_key(rec["title"])] = new_id
            added += 1
    return {"added": added, "merged_duplicates": merged}


def update_paper(paper_id: int, fields: dict[str, Any]) -> dict[str, Any]:
    fields = {k: v for k, v in fields.items() if k in PAPER_FIELDS}
    if "status" in fields and fields["status"] not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    if not fields:
        raise ValueError(f"nothing to update; allowed fields: {PAPER_FIELDS}")
    with connect() as con:
        con.execute(f"UPDATE papers SET {', '.join(f'{k}=?' for k in fields)} WHERE id=?", (*fields.values(), paper_id))
        row = con.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone()
        if not row:
            raise ValueError(f"paper {paper_id} not found")
        return dict(row)


def list_papers(
    project: str | int, status: str | None = None, theme: str | None = None, search: str | None = None, limit: int = 200
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM papers WHERE project_id=?"
    args: list[Any] = []
    with connect() as con:
        args.append(project_id(con, project))
        if status:
            sql += " AND status=?"
            args.append(status)
        if theme:
            sql += " AND theme=?"
            args.append(theme)
        if search:
            sql += " AND (title LIKE ? OR abstract LIKE ?)"
            args += [f"%{search}%"] * 2
        sql += " ORDER BY COALESCE(cited_by,0) DESC LIMIT ?"
        args.append(limit)
        return _rows(con.execute(sql, args))


def literature_matrix(project: str | int, status: str = "included") -> list[dict[str, Any]]:
    rows = list_papers(project, status=status or None, limit=1000)
    matrix = []
    for i, r in enumerate(sorted(rows, key=lambda r: (r["theme"] or "", -(r["year"] or 0))), 1):
        first = (r["authors"] or "").split(";")[0].strip() or "n/a"
        matrix.append(
            {
                "#": i,
                "author_year": f"{first}{' et al.' if ';' in (r['authors'] or '') else ''} ({r['year'] or 'n.d.'})",
                "title": r["title"],
                "journal": r["venue"],
                "method": r["method"] or "not stated",
                "data_context": r["data_context"] or "not stated",
                "finding": r["finding"] or "not stated",
                "limitation_gap": r["limitation"] or "not stated",
                "theme": r["theme"],
                "evidence_level": r["evidence_level"],
                "cited_by": r["cited_by"],
                "doi_pmid": r["doi"] or (f"PMID {r['pmid']}" if r["pmid"] else None),
                "source": r["source"],
                "paper_id": r["id"],
            }
        )
    return matrix


def log_search(project: str | int, database: str, query: str, hits: int, run_date: str | None = None) -> dict[str, Any]:
    with connect() as con:
        pid = project_id(con, project)
        con.execute(
            "INSERT INTO searches(project_id, database, query, hits, run_date) VALUES (?,?,?,?,?)",
            (pid, database, query, hits, run_date or _now()[:10]),
        )
    return {"logged": True}


def prisma_counts(project: str | int) -> dict[str, Any]:
    with connect() as con:
        pid = project_id(con, project)
        searches = _rows(con.execute("SELECT database, query, hits, run_date FROM searches WHERE project_id=?", (pid,)))
        status = {r["status"]: r["n"] for r in con.execute(
            "SELECT status, COUNT(*) n FROM papers WHERE project_id=? GROUP BY status", (pid,))}
        reasons = _rows(con.execute(
            """SELECT COALESCE(exclusion_reason,'not given') reason, COUNT(*) n FROM papers
               WHERE project_id=? AND status='excluded' GROUP BY reason ORDER BY n DESC""", (pid,)))
    identified = sum(s["hits"] or 0 for s in searches)
    stored = sum(status.values())
    return {
        "records_identified": identified,
        "by_database": searches,
        "records_after_dedup_stored": stored,
        "duplicates_or_not_imported": max(identified - stored, 0) if identified else None,
        "screened": stored - status.get("candidate", 0),
        "excluded": status.get("excluded", 0),
        "exclusion_reasons": reasons,
        "included": status.get("included", 0),
        "note": "Hits are what each database reported; only the records you imported are stored, so "
        "'duplicates_or_not_imported' mixes both unless you imported every hit.",
    }


# ---------------------------------------------------------------- notes & journals
def add_note(project: str | int, text: str, paper_id: int | None = None, tags: list[str] | None = None) -> dict[str, Any]:
    with connect() as con:
        pid = project_id(con, project)
        cur = con.execute(
            "INSERT INTO notes(project_id, paper_id, text, tags, created) VALUES (?,?,?,?,?)",
            (pid, paper_id, text, ",".join(tags or []), _now()),
        )
        return {"note_id": cur.lastrowid}


def list_notes(project: str | int, tag: str | None = None) -> list[dict[str, Any]]:
    with connect() as con:
        pid = project_id(con, project)
        if tag:
            return _rows(con.execute("SELECT * FROM notes WHERE project_id=? AND (',' || tags || ',') LIKE ?",
                                     (pid, f"%,{tag},%")))
        return _rows(con.execute("SELECT * FROM notes WHERE project_id=? ORDER BY id", (pid,)))


def save_journal(project: str | int, journal: dict[str, Any]) -> dict[str, Any]:
    allowed = ["name", "issn", "publisher", "h_index", "citedness", "is_oa", "apc_usd", "scopus_status", "quartile", "quartile_source", "fit_reason"]
    rec = {k: journal.get(k) for k in allowed if journal.get(k) is not None}
    if "name" not in rec:
        raise ValueError("journal needs a name")
    if rec.get("quartile") and not rec.get("quartile_source"):
        raise ValueError("a quartile needs quartile_source (e.g. 'SCImago, checked 2026-11-15')")
    with connect() as con:
        pid = project_id(con, project)
        cur = con.execute(
            f"INSERT INTO journals(project_id, {', '.join(rec)}) VALUES (?,{','.join('?' * len(rec))})",
            (pid, *rec.values()),
        )
        return {"journal_id": cur.lastrowid}


# ---------------------------------------------------------------- observations
def add_observations(project: str | int, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Each row: variable (required), value (number or text), subject, group, session, unit, observer,
    observed_at (ISO date), notes."""
    n = 0
    with connect() as con:
        pid = project_id(con, project)
        for r in rows:
            if not r.get("variable"):
                continue
            v = r.get("value")
            num = None
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                num = float(v)
            elif isinstance(v, str):
                try:
                    num = float(v.replace(",", "."))
                except ValueError:
                    num = None
            con.execute(
                """INSERT INTO observations(project_id, session, subject, grp, variable, value_num, value_text,
                   unit, observer, observed_at, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (pid, r.get("session"), r.get("subject"), r.get("group"), r["variable"], num,
                 None if num is not None else (None if v is None else str(v)), r.get("unit"), r.get("observer"),
                 r.get("observed_at") or _now()[:10], r.get("notes")),
            )
            n += 1
    return {"inserted": n}


def query_observations(
    project: str | int, variable: str | None = None, group: str | None = None, session: str | None = None, limit: int = 5000
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM observations WHERE project_id=?"
    args: list[Any] = []
    with connect() as con:
        args.append(project_id(con, project))
        for col, val in (("variable", variable), ("grp", group), ("session", session)):
            if val:
                sql += f" AND {col}=?"
                args.append(val)
        sql += " ORDER BY observed_at, id LIMIT ?"
        args.append(limit)
        return _rows(con.execute(sql, args))


# ---------------------------------------------------------------- export / import
def export_csv(project: str | int, table: str, path: str) -> dict[str, Any]:
    if table not in TABLES or table == "projects":
        raise ValueError(f"table must be one of {TABLES[1:]}")
    out = Path(path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    if table == "papers":
        rows = list_papers(project, limit=100000)
    else:
        with connect() as con:
            rows = _rows(con.execute(f"SELECT * FROM {table} WHERE project_id=?", (project_id(con, project),)))
    with out.open("w", newline="", encoding="utf-8") as f:
        if rows:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    return {"path": str(out), "rows": len(rows)}


def export_matrix_csv(project: str | int, path: str, status: str = "included") -> dict[str, Any]:
    rows = literature_matrix(project, status)
    out = Path(path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        if rows:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    return {"path": str(out), "rows": len(rows)}


def import_observations_csv(project: str | int, path: str, mapping: dict[str, str] | None = None) -> dict[str, Any]:
    """Load a long-format CSV (one row per measurement). ``mapping`` renames CSV columns to
    observation fields, e.g. {"pasien": "subject", "skor": "value", "kelompok": "group"}.
    A wide CSV (one column per variable) is melted when no 'variable' column exists: every column
    not mapped to subject/group/session/observer/observed_at becomes a variable."""
    mapping = mapping or {}
    meta = {"subject", "group", "session", "observer", "observed_at", "unit", "notes"}
    with Path(path).expanduser().open(newline="", encoding="utf-8-sig") as f:
        raw = list(csv.DictReader(f))
    rows: list[dict[str, Any]] = []
    for r in raw:
        r = {mapping.get(k, k): v for k, v in r.items()}
        if "variable" in r:
            rows.append(r)
        else:
            base = {k: r[k] for k in meta if k in r}
            for k, v in r.items():
                if k not in meta and v not in (None, ""):
                    rows.append({**base, "variable": k, "value": v})
    return add_observations(project, rows)


def dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1, default=str)
