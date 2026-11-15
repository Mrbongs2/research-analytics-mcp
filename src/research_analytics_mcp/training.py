"""Learning & development: evidence-based training design, observation checklists, Kirkpatrick
evaluation from recorded observations, and training media through Open-Higgsfield's gateway
(MuAPI, https://github.com/Anil-matcha/Open-Higgsfield-AI).

Media generation is paid: ``media_generate`` only sends a request when ``confirm=True``.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from . import analytics, database
from .http import UpstreamError, request

BLOOM = {
    "remember": ["define", "list", "recall", "identify"],
    "understand": ["explain", "describe", "classify", "summarise"],
    "apply": ["perform", "demonstrate", "use", "carry out"],
    "analyze": ["differentiate", "examine", "compare", "interpret"],
    "evaluate": ["judge", "justify", "appraise", "decide"],
    "create": ["design", "plan", "develop", "construct"],
}
LEVEL_TO_BLOOM = {
    "beginner": ["remember", "understand", "apply"],
    "intermediate": ["understand", "apply", "analyze"],
    "advanced": ["analyze", "evaluate", "create"],
}


# ---------------------------------------------------------------- design
def training_blueprint(
    topic: str,
    audience: str,
    duration_minutes: int = 120,
    level: str = "intermediate",
    n_objectives: int = 4,
    project: str | None = None,
    delivery: str = "blended",
) -> dict[str, Any]:
    """Skeleton for a training module. Evidence comes from the project's *included* papers so
    every teaching point can carry a citation; objectives are scaffolds to be rewritten."""
    levels = LEVEL_TO_BLOOM.get(level, LEVEL_TO_BLOOM["intermediate"])
    objectives = []
    for i in range(n_objectives):
        b = levels[min(i * len(levels) // max(n_objectives, 1), len(levels) - 1)]
        objectives.append({
            "id": f"LO{i + 1}",
            "bloom_level": b,
            "suggested_verbs": BLOOM[b],
            "template": f"By the end, {audience} can <{BLOOM[b][0]}> <specific {topic} skill/knowledge> <to what standard>.",
        })
    d = duration_minutes
    agenda = [
        {"block": "Opening: why it matters, baseline (pre-test)", "minutes": round(d * 0.10)},
        {"block": "Core content (mapped to LOs, with evidence)", "minutes": round(d * 0.35)},
        {"block": "Demonstration / worked case", "minutes": round(d * 0.15)},
        {"block": "Guided practice with observation checklist", "minutes": round(d * 0.25)},
        {"block": "Post-test and reflection", "minutes": round(d * 0.10)},
        {"block": "Close: action plan for the workplace", "minutes": d - sum(round(d * x) for x in (0.10, 0.35, 0.15, 0.25, 0.10))},
    ]
    evidence = []
    if project:
        papers = database.list_papers(project, status="included", limit=1000)
        papers.sort(key=lambda p: (p["evidence_level"] if p["evidence_level"] is not None else 9, -(p["cited_by"] or 0)))
        evidence = [
            {"paper_id": p["id"], "cite": f"{(p['authors'] or 'n/a').split(';')[0]} ({p['year']})", "title": p["title"],
             "finding": p["finding"] or "fill from abstract", "evidence_level": p["evidence_level"]}
            for p in papers[:15]
        ]
    return {
        "topic": topic, "audience": audience, "level": level, "delivery": delivery, "duration_minutes": d,
        "learning_objectives": objectives,
        "agenda": agenda,
        "evidence_base": evidence or "No project given or no included papers: run the literature workflow first.",
        "assessment": {
            "pre_post_test": "Same item bank before and after; 10-20 items mapped to LOs; record as observations "
                             "variable='pre_score'/'post_score', subject=<participant id>.",
            "skills_check": "Observation checklist per LO (observation_checklist tool); two observers on >=20% of "
                            "participants to compute Cohen's kappa.",
        },
        "evaluation_plan_kirkpatrick": {
            "L1_reaction": "Survey 1-5 right after the session (variables prefixed 'reaction_').",
            "L2_learning": "Pre/post score -> paired test + normalised gain.",
            "L3_behaviour": "Checklist on the job at 4-8 weeks (session='followup').",
            "L4_results": "One workplace metric before/after (e.g. error rate, patient satisfaction), variable 'outcome_<name>'.",
        },
        "media_plan": "Short scenario videos/images per LO can be generated with media_generate (Open-Higgsfield/MuAPI) after the user approves cost.",
    }


def observation_checklist(
    skill: str, steps: list[str], scale: str = "done_not_done", critical_steps: list[int] | None = None
) -> dict[str, Any]:
    scales = {
        "done_not_done": {"values": [0, 1], "labels": ["not done", "done"]},
        "three_point": {"values": [0, 1, 2], "labels": ["not done", "done incorrectly / partly", "done correctly"]},
        "five_point": {"values": [1, 2, 3, 4, 5], "labels": ["novice", "advanced beginner", "competent", "proficient", "expert"]},
    }
    if scale not in scales:
        raise ValueError(f"scale must be one of {list(scales)}")
    crit = set(critical_steps or [])
    items = [
        {"item": f"S{i}", "step": s, "critical": i in crit, "variable": f"step_{i:02d}"}
        for i, s in enumerate(steps, 1)
    ]
    return {
        "skill": skill, "scale": scales[scale], "items": items,
        "pass_rule": "All critical steps at the top value and >=80% of the maximum total score." if crit
        else ">=80% of the maximum total score.",
        "how_to_record": "db_add_observations rows: {subject, session, observer, variable: 'step_01', value}.",
    }


def kirkpatrick_report(project: str, max_score: float | None = 100, pass_threshold: float = 0.8) -> dict[str, Any]:
    """Summarise a training evaluation from observations stored in the project."""
    obs = database.query_observations(project, limit=100000)
    if not obs:
        return {"error": "no observations in this project"}
    out: dict[str, Any] = {"project": project}

    reaction = defaultdict(list)
    for o in obs:
        if o["variable"].startswith("reaction_") and o["value_num"] is not None:
            reaction[o["variable"]].append(o["value_num"])
    if reaction:
        out["L1_reaction"] = {k: {"n": len(v), "mean": round(mean(v), 2), "share_4_or_5": round(sum(x >= 4 for x in v) / len(v), 3)}
                              for k, v in reaction.items()}

    pre = {o["subject"]: o["value_num"] for o in obs if o["variable"] == "pre_score" and o["value_num"] is not None}
    post = {o["subject"]: o["value_num"] for o in obs if o["variable"] == "post_score" and o["value_num"] is not None}
    pairs = [{"pre": pre[s], "post": post[s]} for s in pre if s in post]
    if len(pairs) >= 3:
        out["L2_learning"] = analytics.paired_compare(pairs, "pre", "post", max_score=max_score)

    steps = [o for o in obs if o["variable"].startswith("step_") and o["value_num"] is not None]
    if steps:
        per = defaultdict(lambda: defaultdict(list))
        for o in steps:
            per[o["session"] or "default"][o["subject"]].append(o["value_num"])
        step_max = max(o["value_num"] for o in steps) or 1
        sessions = {}
        for sess, subj in per.items():
            scores = {s: sum(v) / (len(v) * step_max) for s, v in subj.items()}
            sessions[sess] = {"participants": len(scores), "mean_score_pct": round(100 * mean(scores.values()), 1),
                              "pass_rate": round(sum(x >= pass_threshold for x in scores.values()) / len(scores), 3)}
        hardest = defaultdict(list)
        for o in steps:
            hardest[o["variable"]].append(o["value_num"] / step_max)
        out["L3_behaviour_checklist"] = {
            "by_session": sessions,
            "weakest_steps": sorted(({"step": k, "mean_pct": round(100 * mean(v), 1)} for k, v in hardest.items()),
                                    key=lambda r: r["mean_pct"])[:5],
        }
        two_obs = defaultdict(dict)
        for o in steps:
            if o["observer"]:
                two_obs[(o["subject"], o["session"], o["variable"])][o["observer"]] = o["value_num"]
        rated = [v for v in two_obs.values() if len(v) >= 2]
        if len(rated) >= 5:
            obs_names = sorted({k for v in rated for k in v})[:2]
            rows = [{"a": v.get(obs_names[0]), "b": v.get(obs_names[1])} for v in rated if all(n in v for n in obs_names)]
            if len(rows) >= 2:
                out["inter_rater"] = {"observers": obs_names, **analytics.cohen_kappa(rows, "a", "b")}

    outcomes = defaultdict(lambda: defaultdict(list))
    for o in obs:
        if o["variable"].startswith("outcome_") and o["value_num"] is not None:
            outcomes[o["variable"]][o["session"] or "default"].append(o["value_num"])
    if outcomes:
        out["L4_results"] = {k: {s: {"n": len(v), "mean": round(mean(v), 3)} for s, v in d.items()} for k, d in outcomes.items()}
    out["note"] = "Variables: reaction_*, pre_score/post_score, step_NN (checklist), outcome_* with session labels such as 'baseline'/'followup'."
    return out


# ---------------------------------------------------------------- Open-Higgsfield / MuAPI
def _muapi() -> tuple[str, dict[str, str]]:
    key = os.getenv("MUAPI_API_KEY")
    if not key:
        raise UpstreamError("MUAPI_API_KEY is not set. Get a key at muapi.ai (the gateway Open-Higgsfield uses) "
                            "and add it to the server env.")
    base = os.getenv("MUAPI_BASE_URL", "https://api.muapi.ai").rstrip("/")
    return base, {"x-api-key": key}


def _urls(obj: Any) -> list[str]:
    found: list[str] = []
    if isinstance(obj, str) and obj.startswith("http"):
        found.append(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k not in ("input", "params", "request"):
                found += _urls(v)
    elif isinstance(obj, list):
        for v in obj:
            found += _urls(v)
    return list(dict.fromkeys(found))


def media_generate(endpoint: str, payload: dict[str, Any], confirm: bool = False, wait_seconds: int = 0) -> dict[str, Any]:
    """POST {base}/api/v1/{endpoint} with payload (e.g. {"prompt": ..., "aspect_ratio": "16:9"}).
    endpoint is the model slug shown in Open-Higgsfield / MuAPI docs. Without confirm=True this is
    a dry run that shows what would be sent."""
    endpoint = endpoint.strip("/")
    if not confirm:
        return {"dry_run": True, "would_post": f"/api/v1/{endpoint}", "payload": payload,
                "next": "This spends MuAPI credits. Ask the user, then call again with confirm=true."}
    base, headers = _muapi()
    r = request("POST", f"{base}/api/v1/{endpoint}", json=payload, headers=headers, retries=0).json()
    rid = r.get("request_id") or r.get("id")
    res = {"request_id": rid, "status": r.get("status", "submitted"), "response": r}
    if rid and wait_seconds:
        res = media_result(rid, wait_seconds=wait_seconds)
    return res


def media_result(request_id: str, wait_seconds: int = 0, poll_every: int = 5) -> dict[str, Any]:
    base, headers = _muapi()
    deadline = time.time() + max(0, min(wait_seconds, 600))
    while True:
        r = request("GET", f"{base}/api/v1/predictions/{request_id}/result", headers=headers).json()
        status = str(r.get("status", "")).lower()
        if status in ("completed", "succeeded", "success", "failed", "error") or time.time() >= deadline:
            return {"request_id": request_id, "status": status or "unknown", "outputs": _urls(r.get("outputs") or r.get("output") or r),
                    "error": r.get("error")}
        time.sleep(poll_every)


def media_upload(file_path: str) -> dict[str, Any]:
    base, headers = _muapi()
    p = Path(file_path).expanduser()
    with p.open("rb") as f:
        r = request("POST", f"{base}/api/v1/upload_file", files={"file": (p.name, f)}, headers=headers, retries=0).json()
    return {"url": (_urls(r) or [None])[0], "response": r}


def storyboard(objectives: list[str], style: str = "realistic clinical training video, neutral lighting", seconds_per_scene: int = 8) -> dict[str, Any]:
    """Turn learning objectives into scene prompts for text-to-video, one scene per objective plus an intro."""
    scenes = [{"scene": 0, "purpose": "hook", "prompt": f"{style}; establishing shot of the workplace where the skill is used",
               "seconds": seconds_per_scene}]
    for i, lo in enumerate(objectives, 1):
        scenes.append({"scene": i, "purpose": lo,
                       "prompt": f"{style}; a professional demonstrates: {lo}; clear hand movements, close-up on key step",
                       "seconds": seconds_per_scene, "on_screen_text": lo})
    return {"scenes": scenes, "total_seconds": seconds_per_scene * len(scenes),
            "rules": "No real patient faces or identifiable people; label generated clips as AI-generated in the module."}
