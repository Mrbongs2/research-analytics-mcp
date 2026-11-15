"""Teaching-video helpers: lesson plan with evidence checks, captions (SRT + Remotion JSON),
ffprobe inspection, and Creative Commons media search (Openverse, no key needed)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from . import database
from .http import get_json

FORMATS = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350)}
OPENVERSE = "https://api.openverse.org/v1"
_NUM = re.compile(r"\d+(?:[.,]\d+)?\s*(?:%|mg|ml|mcg|µg|ppm|mmhg|detik|menit|jam|hari|minggu|bulan|tahun|kali|x)\b", re.IGNORECASE)


def _words(t: str) -> int:
    return len(re.findall(r"\w+", t or ""))


# ---------------------------------------------------------------- lesson plan
def lesson_plan(
    title: str,
    scenes: list[dict[str, Any]],
    fmt: str = "16:9",
    words_per_minute: int = 140,
    out_dir: str | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    """scenes: [{narration, on_screen_text?, visual?, purpose?, objective?, paper_ids?: [int], duration_s?}]."""
    if fmt not in FORMATS:
        raise ValueError(f"fmt must be one of {list(FORMATS)}")
    included: dict[int, dict[str, Any]] = {}
    if project:
        included = {p["id"]: p for p in database.list_papers(project, limit=100000)}
    plan, warnings, t = [], [], 0.0
    for i, s in enumerate(scenes, 1):
        narr = s.get("narration", "")
        est = round(_words(narr) / words_per_minute * 60 + 0.8, 1)
        dur = float(s.get("duration_s") or max(3.0, est))
        ids = [int(x) for x in s.get("paper_ids") or []]
        refs, issues = [], []
        for pid in ids:
            p = included.get(pid)
            if project and not p:
                issues.append(f"paper_id {pid} not in project")
            elif p:
                if p["status"] != "included":
                    issues.append(f"paper_id {pid} is '{p['status']}', not included")
                refs.append(f"{(p['authors'] or 'n/a').split(';')[0]} ({p['year']})")
        numbers = _NUM.findall(narr) + _NUM.findall(s.get("on_screen_text") or "")
        if numbers and not ids:
            issues.append(f"clinical numbers without a source: {', '.join(dict.fromkeys(numbers))} -> [PERLU SUMBER]")
        if "[PERLU SUMBER]" in narr:
            issues.append("narration contains [PERLU SUMBER]")
        if _words(s.get("on_screen_text") or "") > 12:
            issues.append("on-screen text > 12 words (redundancy principle: keep keywords only)")
        if abs(dur - est) > 3 and s.get("duration_s"):
            issues.append(f"duration {dur}s vs ~{est}s needed for the narration")
        plan.append({
            "scene": i, "purpose": s.get("purpose"), "objective": s.get("objective"),
            "start_s": round(t, 2), "duration_s": dur, "end_s": round(t + dur, 2),
            "narration": narr, "words": _words(narr), "on_screen_text": s.get("on_screen_text"),
            "visual": s.get("visual"), "paper_ids": ids, "references": refs, "issues": issues,
            "voiceover_file": f"voiceover/scene-{i:02d}.mp3",
        })
        t += dur
    purposes = " ".join((s.get("purpose") or "").lower() for s in scenes)
    if t > 360:
        warnings.append(f"total {t / 60:.1f} min > 6 min: split into segments (one objective per video)")
    if not any(k in purposes for k in ("objective", "tujuan")):
        warnings.append("no scene states the learning objectives (add one after the hook)")
    if not any(k in purposes for k in ("summary", "ringkasan", "recap")):
        warnings.append("no summary scene")
    if not any(k in purposes for k in ("quiz", "kuis")):
        warnings.append("no quiz/check-for-understanding scene")
    unresolved = sum(1 for p in plan if p["issues"])
    w, h = FORMATS[fmt]
    result = {
        "title": title, "format": fmt, "resolution": f"{w}x{h}", "fps": 30,
        "total_seconds": round(t, 1), "scenes": plan, "warnings": warnings,
        "scenes_with_issues": unresolved,
        "ready_for_render": unresolved == 0 and not any("objective" in x for x in warnings),
        "reminder": "Clinical review by a qualified professional and patient consent are required before publishing.",
    }
    if out_dir:
        out = Path(out_dir).expanduser()
        out.mkdir(parents=True, exist_ok=True)
        (out / "lesson-plan.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        lines = [f"# {title}", "", f"Format {fmt} ({w}x{h}), 30 fps, total {t:.0f} s", ""]
        for p in plan:
            lines += [f"## Scene {p['scene']:02d} ({p['start_s']}-{p['end_s']} s) {p['purpose'] or ''}".rstrip(),
                      f"- Narration: {p['narration']}", f"- On screen: {p['on_screen_text'] or '-'}",
                      f"- Visual: {p['visual'] or '-'}", f"- Sources: {', '.join(p['references']) or '-'}"]
            lines += [f"- ⚠ {x}" for x in p["issues"]]
            lines.append("")
        if warnings:
            lines += ["## Warnings", *[f"- {x}" for x in warnings], ""]
        (out / "edit-plan.md").write_text("\n".join(lines), encoding="utf-8")
        result["files"] = [str(out / "lesson-plan.json"), str(out / "edit-plan.md")]
    return result


# ---------------------------------------------------------------- captions
def _chunks(text: str, max_line: int = 42, max_lines: int = 2) -> list[str]:
    words, cues, line, lines = text.split(), [], "", []
    for w in words:
        if not line or len(line) + len(w) + 1 <= max_line:
            line = f"{line} {w}".strip()
            continue
        lines.append(line)
        line = w
        if len(lines) == max_lines:
            cues.append("\n".join(lines))
            lines = []
    if line:
        lines.append(line)
    if lines:
        cues.append("\n".join(lines))
    return cues


def _ts(ms: int) -> str:
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def captions(scenes: list[dict[str, Any]], out_dir: str | None = None, max_cps: float = 17.0) -> dict[str, Any]:
    """scenes: [{narration, duration_s} or {narration, start_s, end_s}] (e.g. the output of video_lesson_plan).
    Time is split across cues by character count; for word-level timing use Whisper on the real audio."""
    cues, t, fast = [], 0.0, 0
    for s in scenes:
        start = float(s.get("start_s", t))
        end = float(s["end_s"]) if "end_s" in s else start + float(s.get("duration_s") or 0)
        if end <= start:
            raise ValueError("each scene needs duration_s or start_s/end_s")
        parts = _chunks(s.get("narration", ""))
        total = sum(len(p) for p in parts) or 1
        cur = start
        for p in parts:
            d = (end - start) * len(p) / total
            if len(p.replace("\n", " ")) / d > max_cps:
                fast += 1
            cues.append({"text": p, "startMs": int(cur * 1000), "endMs": int((cur + d) * 1000)})
            cur += d
        t = end
    srt = "\n".join(f"{i}\n{_ts(c['startMs'])} --> {_ts(c['endMs'])}\n{c['text']}\n" for i, c in enumerate(cues, 1))
    remotion = [{"text": c["text"].replace("\n", " "), "startMs": c["startMs"], "endMs": c["endMs"],
                 "timestampMs": (c["startMs"] + c["endMs"]) // 2, "confidence": None} for c in cues]
    res: dict[str, Any] = {"cues": len(cues), "cues_faster_than_max_cps": fast, "srt_preview": srt[:600]}
    if fast:
        res["warning"] = f"{fast} cue(s) exceed {max_cps} characters/second: lengthen the scene or shorten the narration."
    if out_dir:
        out = Path(out_dir).expanduser()
        out.mkdir(parents=True, exist_ok=True)
        (out / "captions.srt").write_text(srt, encoding="utf-8")
        (out / "captions.json").write_text(json.dumps(remotion, ensure_ascii=False, indent=1), encoding="utf-8")
        res["files"] = [str(out / "captions.srt"), str(out / "captions.json")]
    else:
        res["srt"] = srt
        res["remotion_captions"] = remotion
    return res


# ---------------------------------------------------------------- ffprobe
def probe(path: str) -> dict[str, Any]:
    exe = shutil.which("ffprobe")
    if not exe:
        raise RuntimeError("ffprobe not found: install ffmpeg (e.g. brew install ffmpeg / apt install ffmpeg)")
    p = Path(path).expanduser()
    if not p.is_file():
        raise FileNotFoundError(str(p))
    r = subprocess.run(
        [exe, "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt,sample_rate,channels:format=duration,size,bit_rate",
         "-of", "json", str(p)],
        capture_output=True, text=True, timeout=60, check=False,
    )
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[:300])
    d = json.loads(r.stdout)
    fmt = d.get("format", {})
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), None)
    fps = None
    if v and v.get("r_frame_rate") and "/" in v["r_frame_rate"]:
        n, den = v["r_frame_rate"].split("/")
        fps = round(int(n) / int(den), 3) if int(den) else None
    return {
        "file": str(p), "duration_s": round(float(fmt.get("duration", 0)), 3), "size_mb": round(int(fmt.get("size", 0)) / 1e6, 2),
        "video": v and {"codec": v.get("codec_name"), "width": v.get("width"), "height": v.get("height"), "fps": fps,
                        "pix_fmt": v.get("pix_fmt")},
        "audio": a and {"codec": a.get("codec_name"), "sample_rate": a.get("sample_rate"), "channels": a.get("channels")},
        "ready_for_concat": bool(v and a and v.get("pix_fmt") == "yuv420p" and fps in (30.0, 29.97)),
    }


# ---------------------------------------------------------------- Openverse
def openverse_search(query: str, kind: str = "image", license: str = "commercial", n: int = 10,
                     source: str | None = None) -> dict[str, Any]:
    """Creative Commons / public-domain images or audio (Wikimedia Commons, Flickr, museums, Freesound).
    license: commercial (CC0, PDM, BY, BY-SA) | pd (CC0, PDM only) | any."""
    if kind not in ("image", "audio"):
        raise ValueError("kind must be image or audio")
    params: dict[str, Any] = {"q": query, "page_size": max(1, min(n, 20)), "mature": "false", "source": source}
    params.update({"commercial": {"license_type": "commercial,modification"}, "pd": {"license": "cc0,pdm"}, "any": {}}[license])
    data = get_json(f"{OPENVERSE}/{'images' if kind == 'image' else 'audio'}/", params=params)
    hits = []
    for r in data.get("results", []):
        lic = (r.get("license") or "").lower()
        hits.append({
            "id": r.get("id"), "title": r.get("title"), "creator": r.get("creator"),
            "license": lic.upper() if lic in ("cc0", "pdm") else f"CC {lic.upper()} {r.get('license_version') or ''}".strip(),
            "attribution_required": lic not in ("cc0", "pdm"),
            "attribution": r.get("attribution"), "page": r.get("foreign_landing_url"), "source": r.get("source"),
            "url": r.get("url"), "width": r.get("width"), "height": r.get("height"),
            "duration_s": round(r["duration"] / 1000, 1) if r.get("duration") else None,
        })
    return {"query": query, "total": data.get("result_count"), "hits": hits,
            "note": "Check medical accuracy of each image; CC BY/BY-SA needs the attribution line in the credits."}
