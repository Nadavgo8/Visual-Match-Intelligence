# CLAUDE.md

Context for Claude Code. This project was planned and built on claude.ai (Oct 8–21, 2026) and moved here on Oct 21. Everything you need is in this repo; read this file first, then the docs it points to when a task touches them.

## Working with Nadav

- Nadav owns the project. Team of 2; both registered. Work is split between **Developer 1** and **Developer 2** (plan §3); both use AI coding tools (Claude Code, Codex).
- **Reply in the language of the message** (Hebrew or English). Developer guidance docs may be in Hebrew. The product itself (code, file names, UI, prompts, agent output, README, submission materials) is **English only**.
- They want **maximum speed**. Act, then report. Ask only for decisions that change the goal or can't be undone.
- **Zero extra cost is a hard rule.** No purchases, no payment method, no trial that turns into billing, no paid overage, no paid fallback on an error or an exhausted quota. If nothing works at zero cost, report a blocker.
- The demo video is planned in plan §12. Don't raise it outside that.
- Be honest: don't invent findings, quotes or user research. There was no user testing.
- **Git:** `origin` = github.com/Nadavgo8/Visual-Match-Intelligence (MIT). Workflow per plan §9: branch → tests → commit → push the branch → PR → technical review → automatic squash merge after passing gates. Never commit straight to `main`, never force-push. One AI tool per working folder; use a separate worktree for parallel work.
- **Mandatory quality process:** Read `docs/implementation/12-QUALITY-AND-GIT-GATES.md` before each task. Every branch runs the existing test suite and receives code review; behavior changes require meaningful unit tests and review between dependent work steps. Before merge, resolve P0/P1/P2 findings, rerun after fixes/synchronization and record a technical PASS on the tested SHA. Automatically squash merge after the gates pass without routine human approval, as explicitly authorized by the user; never bypass server rules or invent human approval. Verify the merged `main` before marking DONE. Stage transitions require a technical accumulated-change review and tests on the same integrated SHA. Record actual evidence and a regression/process improvement after findings. AI review is not human approval; NOT_RUN is not PASS.
- **Current plan:** `docs/implementation/VMI-FINAL-PLAN-F.md` is the active plan. Its explicit decisions supersede stale summaries below: the demo stays 2D, xG is a delayed linked generator event, and model/runtime selection remains open until D2-00. Documentation work alone does not authorize implementing the whole plan.
- **Task delivery:** Keep implementation, meaningful tests, fixes and review together per task. A separate tests-only PR requires independently useful scope. Start new tasks from updated `main` and wait for dependent merges. Diagnose failures before escalating product decisions; explain changes, rationale, validation and limits in commit bodies. The latest clarification authorizes automatic review and merge inside the active session after the quality gates pass; see `docs/implementation/HANDOFF.md`.

## The hackathon

Microsoft × Premier League **"Inside the Game"** (github.com/microsoft/insidethegamehackathon).

- **Submission closes Wed Oct 28, 08:59 Israel time** (Tue Oct 27, 11:59 pm PT). Aim for Tuesday night. Israel moves to winter time on Oct 25, so the gap to PT is 9 h from then. Stop adding features at least 24 h before submission.
- **The demo must stay free for judges until Nov 10 PT** (Wed Nov 11, 09:59 Israel).
- **Deliverables:** public GitHub repo with a licence (done: MIT), a demo video under 2 minutes, a pitch, and a working test link or build for judges.
- **Must use** at least one Microsoft AI service (Foundry / Agent Framework). Our Oct 18 reading also required Azure hosting; under the zero-cost rule, model and hosting are decided in task D2-00 (rules §4.8 accept a website, a working demo or a test build). Depth over breadth.
- **Judging:** 20% each for technical implementation, agentic design, real-world impact, UX/video, category fit. Ties go to technical implementation. Category: **Multi-Agent** (Foundry also relevant).
- **Data:** synthetic, football-realistic only. No real match data or footage.
- **No Premier League marks:** fully fictional teams, players, crests, music.
- **IP:** stays with the team; Microsoft and PL get a non-exclusive licence.
- Full rules and resources: `docs/context/plan/hackathon-reference.md` (one-stop reference, Israel times) and `hackathon-brief.md`.

## The product: Visual Match Intelligence

Football's sound, made visible, for anyone with hearing difficulty. A hearing fan gets the whistle, the crowd and the commentator through sound; we turn those into calm visual signals on the match screen, plus an optional companion app on the phone. It does not replace captions or sign language. **Never ask about hearing level.**

Current decisions (Oct 21 product doc and Oct 22 plan; history in `docs/context/decisions.md`, behaviour in `docs/spec.md` v2):

- **Match screen (3D) shows only:** two identical **atmosphere edge bars** (turquoise to amber, fill height; atmosphere = 0.8 × crowd + 0.2 × detected attack); **round event markers** (generic whistle, Foul, Offside, Penalty, Kick-off, Half-time, Full-time) in one fixed top area, one at a time; a **momentum bar** under the score bug (7 min, 40/30/30, approved). **No** crowd-surge banner, no card, goal, VAR or sub overlays, no trace on the viewer's screen (it moves to a presenter area).
- **Companion app (optional):** **no notifications.** Feed that separates facts from interpretation; 2–3 sentence stoppage analysis with receipts; **"What did I miss?"**; Ask with one commentator voice (router, data tools, meaning analyst, rules expert, writer). Skippable onboarding (football knowledge → depth, team supported, how much info), editable anytime. Two depths: basic and deep.
- **Commentary style:** B "friend next to you" for basic, C "analyst" for deep, A "emotional broadcaster" only at peaks.
- **Grounded by design:** code builds a fact pack (event IDs) → LLM words it → validator checks every number/name → template fallback. Every answer is labelled live, cached or template; never present a template as AI. **Never claim why the crowd reacted** ("immediately the crowd erupted", not "so the crowd erupted").
- **Attention Engine** (the differentiator) = deterministic routing + timing + depth, with a `why` for every decision, shown as a live trace in the presenter area.
- **Data realism rule:** the generator emits only what real feeds emit (event feed with x/y, whistle detections without reason, noisy crowd level, TRACAB-style tracking, match state). The **engine derives** everything interpretive (in-box, "not called", key passes, whistle reason, ball holder, attack tier, atmosphere, momentum, surges). xG is a separate delayed synthetic generator event under the approved v2 contract, never an engine estimate. Realistic imperfections included. Don't break this when adding features. Details: `docs/spec.md` §7.
- **No foreknowledge:** agents and the app only ever see delivered data; each seed change or seek gets a new `run_id`, and stale answers are dropped.
- **Vibration:** parked (not in the current plan). Don't build it.
- Pitch wording: the momentum bar is a fan feature, **not** an accessibility need (no evidence for that). Don't claim reduced split attention as proven. See the do/don't list in `docs/context/plan/project-brief.md` §19.

## Code

Built (v1): Python 3.12+, FastAPI + WebSocket rooms, vanilla JS with no build step, Microsoft Agent Framework with Foundry wiring (keyless, Entra ID) and offline fallbacks, and an Azure Container Apps + Application Insights script. Planned: Three.js with an npm build for the 3D match screen (no React, no CDN at demo time); a provider-neutral model layer, since **the model and runtime stay open until D2-00**.

```bash
python -m pip install -r requirements-lock.txt   # Python 3.12, in a venv; exact tested versions
uvicorn vmi.api.server:app --reload   # http://localhost:8000 → /tv on a laptop, /app on a phone, same room code
VMI_OFFLINE=1 VMI_WARM_DEMO=0 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests -q -ra --strict-markers --strict-config -p no:cacheprovider -W error
node --test tests/web/*.test.mjs
python -m vmi.mcp_server               # engine tools over MCP
```

Shared setup, test layers, coverage gate, schemas and CI (for every tool, not only Claude): `docs/implementation/02-SETUP-AND-GIT.md`.

- Runs fully offline: without `FOUNDRY_PROJECT_ENDPOINT` + `FOUNDRY_MODEL` (or with `VMI_OFFLINE=1`), every agent falls back to a deterministic local implementation with the same tools and receipts.
- Env: `VMI_DEMO_SEED` (default **12**: 2–1, early goal, VAR-overturned penalty, routine VAR goal check, header winner), `VMI_WARM_DEMO` (pre-writes demo analysis cache), `APPLICATIONINSIGHTS_CONNECTION_STRING`.
- Layout: `vmi/generator/` seeded match + tracking · `vmi/engine/` derivations, match model (momentum weights in `model.py`), Attention Engine, fact packs, replay clock · `vmi/agents/` Explainer workflow, Router / Match analyst / Rules expert, read-only tools · `vmi/api/server.py` · `web/` TV + companion · `prompts/` agent instructions · `infra/deploy.sh` ACA + App Insights + managed identity · `tests/`.
- **Build spec (source of truth for behaviour): `docs/spec.md` v2.** It describes the target; the code still implements v1. README has the architecture diagram.

## Status (Oct 22)

Built (v1): generator, engine, Attention Engine + trace, 2D TV view, companion app, Explainer workflow with validator and fallback, Ask agents, MCP server, demo cache, realism tests, Dockerfile, deploy script. Repo published with an MIT licence.

Next: the work plan, `docs/implementation/VMI-FINAL-PLAN-F.md`. Developer 1 starts with D1-01 (generator core); Developer 2 starts with **D2-00 (model, runtime and judge access, at zero cost)** and builds no permanent model connection before it is decided. Most of the doc package listed in plan §2 has not been created yet; the mandatory quality/Git process is available in `docs/implementation/12-QUALITY-AND-GIT-GATES.md`. CI, coverage gates and branch protections must be implemented and verified in D2-01; the document alone does not enable them.

Open: see `docs/context/decisions.md`, "Still open".

## Docs

| File | What |
|---|---|
| `docs/implementation/VMI-FINAL-PLAN-F.md` | Work plan (Hebrew, Oct 22): goals, zero-cost rule, split, contracts, generator, tasks D1-01…05 and D2-00…06, gates, git, AI prompts, tests, demo. **Start here for "what next".** |
| `docs/implementation/12-QUALITY-AND-GIT-GATES.md` | Mandatory review and unit-test gates per branch and stage; two-developer Git workflow, CI setup requirements, evidence templates and improvement log. Read before executing a task. |
| `docs/implementation/02-SETUP-AND-GIT.md` | Shared setup (locked install), test layers, coverage gate, v2 JSON Schemas, CI checks and their enforcement status |
| `docs/context/product-doc-2026-10-21.pdf` | Six-page product doc (Hebrew) with design illustrations: edge bars, markers, app, engine, research basis |
| `docs/spec.md` | Build spec v2: behaviour, formulas, data realism, sync, targets |
| `docs/context/decisions.md` | Every decision, the 4-round interview, the Oct 21–22 changes, open items. **Start here for "why".** |
| `docs/context/plan/project-brief.md` | Master brief (Hebrew, Oct 20): problem, users, market, research, pitch rules, checklist. Screen design, Azure budget, timeline and split are superseded |
| `docs/context/plan/hackathon-reference.md` | Rules, dates, deliverables, judging, tools, video summaries |
| `docs/context/plan/hackathon-brief.md` | Short rules summary |
| `docs/context/plan/synthetic-event-data.md` | Original event format and realism check (§7). Spec §7 supersedes where they differ |
| `docs/context/plan/dataset-samples.md`, `plan/team-split-and-structure.md` | Early drafts (Oct 9), superseded |
| `docs/context/plan/interview-notes.md` | Stale stub; the real interview is in `decisions.md` |
| `docs/context/research/deaf-fans-research.md` | What deaf/HoH fans miss, evidence levels, what exists |
| `docs/context/research/icons-and-atmosphere-colors.md` | Icon and atmosphere colour research (WCAG). Its mood palette is superseded by the turquoise-to-amber bars |
| `docs/context/research/commentary-from-data.md` | How data-to-text commentary is done credibly |
| `docs/context/research/reactor-aks-aca-session.md` + `reactor-architecture-slide.png` | Microsoft's official sample app and the patterns we borrowed |
| `docs/context/research/inside-the-game-repo-analysis.md` | Rival entry (bikilath/inside-the-game). No licence: ideas only, never code |
