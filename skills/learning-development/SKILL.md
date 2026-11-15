---
name: learning-development
description: Evidence-based training (Learning & Development) for health and professional teams with the research-analytics MCP server — design a module from the literature (Bloom objectives, agenda, evidence), build observation checklists, record training and field observations, evaluate with Kirkpatrick L1–L4 (reaction, pre/post gain, on-the-job checklist, outcomes, inter-rater kappa), and produce training images/videos through Open-Higgsfield (MuAPI). Use for "buat modul pelatihan", "training needs", "evaluasi pelatihan", "pre-test post-test", "checklist observasi", "Kirkpatrick", "video edukasi", "materi training".
metadata:
  version: "1.0"
  requires: research-analytics MCP server; MUAPI_API_KEY only for media generation
---

# Learning & development: training → observation → analytics

## 1. Needs and evidence

1. Ask: target skill/behaviour, audience and level, duration, delivery (onsite/online/blended),
   the workplace metric that should improve.
2. `db_create_project(name, kind="training")`.
3. Evidence: run the `research-journalscopus` search steps (and `medical-analytics` for clinical
   skills), mark the papers you will teach from as `included`, and fill `finding`.

## 2. Design

- `training_blueprint(topic, audience, duration_minutes, level, project=<name>)` → Bloom-levelled
  objective scaffolds, agenda that sums to the duration, evidence list from the included papers,
  assessment and Kirkpatrick plan. Rewrite each objective as *audience can <verb> <what> <standard>*.
- `training_observation_checklist(skill, steps, scale, critical_steps)` for every practical LO.
- Build the pre/post test from the evidence (10–20 items mapped to LOs); the same items both times.

## 3. Media (Open-Higgsfield / MuAPI) — paid

1. `training_storyboard(objectives)` → one scene prompt per LO.
2. `media_generate(endpoint, payload)` **without** confirm first: it returns a dry run. Tell the
   user how many clips/images and that it spends MuAPI credits; wait for a clear yes.
3. Then `media_generate(endpoint, payload, confirm=true, wait_seconds=120)`; if still running,
   `media_result(request_id, wait_seconds=300)`. Reference images: `media_upload(path)` first.
4. `endpoint` is the model slug from the Open-Higgsfield / MuAPI model list (e.g. a text-to-video
   or text-to-image model); do not guess it — ask the user or read their MuAPI dashboard.
5. No real patients or identifiable people; mark generated media as AI-generated in the module.

## 4. Record observations

Use `db_add_observations` or `db_import_observations_csv` with these variable names:

| Level | variable | session |
|:--|:--|:--|
| L1 reaction | `reaction_<item>` (1–5) | `post` |
| L2 learning | `pre_score`, `post_score` | — |
| L3 behaviour | `step_01`, `step_02` … (checklist) with `observer` | `baseline`, `followup` |
| L4 results | `outcome_<metric>` | `baseline`, `followup` |

Have two observers rate at least 20 % of participants for agreement.

## 5. Evaluate

- `training_evaluation_report(project, max_score=100)` → L1 means and % satisfied, L2 paired test
  + Hake normalised gain (high ≥ 0.7, medium 0.3–0.7, low < 0.3), L3 checklist pass rate per
  session and the weakest steps, inter-rater kappa, L4 outcome means per session.
- Deeper questions: `stats_compare_groups` (e.g. by unit or batch), `stats_trend` for outcomes over time.
- Report what improved, what did not (weakest steps → next module), and the limits (no control
  group, short follow-up, self-report at L1).
