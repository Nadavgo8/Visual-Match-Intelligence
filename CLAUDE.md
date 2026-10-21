# CLAUDE.md

Context for Claude Code. This project was planned and built on claude.ai (Oct 8–21, 2026) and moved here on Oct 21. Everything you need is in this repo; read this file first, then the docs it points to when a task touches them.

## Working with Nadav

- Nadav owns the project. Team of 2; both registered. Who does what doesn't matter to them.
- **Reply in the language of the message** (Hebrew or English). The product itself (UI, prompts, agent output, README) is **English only**.
- They want **maximum speed**. Act, then report. Ask only for decisions that change the goal or can't be undone.
- **Do not bring up the demo video** until Nadav does. They have said "video later" many times.
- Be honest: don't invent findings, quotes or user research. There was no user testing.
- No git remote yet. **Don't push anywhere** without Nadav. When they create an empty GitHub repo: `git remote add origin <url> && git push -u origin main`.

## The hackathon

Microsoft × Premier League **"Inside the Game"** (github.com/microsoft/insidethegamehackathon).

- **Submission closes Wed Oct 28, 08:59 Israel time** (Tue Oct 27, 11:59 pm PT). Aim for Tuesday night. Israel moves to winter time on Oct 25, so the gap to PT is 9 h from then.
- **Live link must keep working until Nov 10 PT** (Wed Nov 11, 09:59 Israel).
- **Deliverables:** public GitHub repo with a licence, a demo video under 2 minutes, a pitch, and a live test link for judges.
- **Must use** at least one Microsoft AI service (Foundry / Agent Framework) and **Azure hosting**. Depth over breadth.
- **Judging:** 20% each for technical implementation, agentic design, real-world impact, UX/video, category fit. Ties go to technical implementation. Category: **Multi-Agent** (Foundry also relevant).
- **Data:** synthetic, football-realistic only. No real match data or footage.
- **No Premier League marks:** fully fictional teams, players, crests, music.
- **IP:** stays with the team; Microsoft and PL get a non-exclusive licence. Licence choice is still open.
- Full rules and resources: `docs/context/plan/hackathon-reference.md` (one-stop reference, Israel times) and `hackathon-brief.md`.

## The product: Visual Match Intelligence

Football's sound, made visible, for anyone with hearing difficulty. A hearing fan gets the whistle, the crowd and the commentator through sound; we turn those into calm visual signals on the TV plus a companion app on the phone. It does not replace captions or sign language. **Never ask about hearing level.**

Final decisions (Oct 20 interview; full record in `docs/context/decisions.md`):

- **TV view shows only:** whistle banners by type (Foul, Offside, Penalty, Stoppage, Kick-off, Half-time, Full-time), each independent, never merged, in a fixed slot; a crowd-surge banner (loudness only); **one** overall atmosphere indicator (no home/away); a momentum bar (rolling 7 min of possession, key passes, shots). **No card banner.** Goals, VAR, cards, subs go to the app.
- **Companion app:** **no notifications.** Event feed; 2–3 sentence stoppage analysis with receipts; Ask chat on the match, rules, stats and tactics (decline off-topic). One-time onboarding (football knowledge → depth, team supported, how much info), editable anytime. Two depths: basic and deep.
- **Commentary style:** B "friend next to you" for basic, C "analyst" for deep, A "emotional broadcaster" only at peaks.
- **Grounded by design:** code builds a fact pack (event IDs) → LLM words it → validator checks every number/name → template fallback. **Never claim why the crowd reacted** ("immediately the crowd erupted", not "so the crowd erupted").
- **Attention Engine** (the differentiator) = deterministic routing + timing + depth, with a `why` for every decision, shown as a live trace.
- **Data realism rule:** the generator emits only what real feeds emit (event feed with x/y, whistle detections without reason, noisy crowd level, tracking, match state). The **engine derives** everything interpretive (in-box, xG, "not called", key passes, whistle reason, momentum, surges). Realistic imperfections included. Don't break this when adding features. Details: `docs/spec.md` §6.
- **Vibration:** Android only (Web Vibration API), skipped silently elsewhere. **What it vibrates on is undecided; don't build it until Nadav answers.**
- Pitch wording: momentum bar is a fan feature, **not** an accessibility need (no evidence for that). See the do/don't list in `docs/context/plan/project-brief.md` §19.

## Code

Python 3.12+, FastAPI + WebSocket rooms, vanilla JS (no build step), Microsoft Agent Framework on Foundry (keyless, Entra ID), Azure Container Apps + Application Insights.

```bash
pip install -r requirements-dev.txt
uvicorn vmi.api.server:app --reload   # http://localhost:8000 → /tv on a laptop, /app on a phone, same room code
pytest -q                              # 32 tests, all pass offline (checked Oct 21)
python -m vmi.mcp_server               # engine tools over MCP
```

- Runs fully offline: without `FOUNDRY_PROJECT_ENDPOINT` + `FOUNDRY_MODEL` (or with `VMI_OFFLINE=1`), every agent falls back to a deterministic local implementation with the same tools and receipts.
- Env: `VMI_DEMO_SEED` (default **12**: 2–1, early goal, VAR-overturned penalty, routine VAR goal check, header winner), `VMI_WARM_DEMO` (pre-writes demo analysis cache), `APPLICATIONINSIGHTS_CONNECTION_STRING`.
- Layout: `vmi/generator/` seeded match + tracking · `vmi/engine/` derivations, match model, momentum, Attention Engine, fact packs, replay clock · `vmi/agents/` Explainer workflow, Router / Match analyst / Rules expert, read-only tools · `vmi/api/server.py` · `web/` TV + companion · `prompts/` agent instructions · `infra/deploy.sh` ACA + App Insights + managed identity · `tests/`.
- **Build spec (source of truth for behaviour): `docs/spec.md`.** README has the architecture diagram.

## Status (Oct 21)

Done: v1 end to end locally (generator, engine, Attention Engine + trace, TV view, companion app, Explainer workflow with validator and fallback, Ask agents, MCP server, demo cache, realism tests, Dockerfile, deploy script).

Pending:
1. **Live Foundry + Azure never run.** Free Trial reportedly gives 0 model quota → upgrade to Pay-As-You-Go (keeps the credit), check Foundry quota, deploy a model not retiring before Nov 10 (GPT-5 mini). Set a budget alert. Keep min-replicas 1 during judging (cold start 15–25 s). Then run `infra/deploy.sh`.
2. **Momentum weights 40/30/30** awaiting Nadav's OK (`docs/spec.md` §3).
3. **Vibration trigger decision** (see above).
4. **GitHub repo + licence** not created; repo name, team name, submitter, final product name open.
5. Later, when Nadav raises it: video, pitch. Optional: Foundry groundedness evaluation.

Milestones, cut order if behind, risks and the submission checklist: `docs/context/plan/project-brief.md` §17–21.

## Context docs (`docs/context/`)

| File | What |
|---|---|
| `decisions.md` | Every decision, the 4-round interview, open items. **Start here for "why".** |
| `plan/project-brief.md` | Master brief (Hebrew): problem, users, market, solution, engine, agents, Azure, judging, risks, timeline, pitch rules, checklist |
| `plan/hackathon-reference.md` | Rules, dates, deliverables, judging, tools, video summaries |
| `plan/hackathon-brief.md` | Short rules summary |
| `plan/synthetic-event-data.md` | Original event format and realism check (§7). Spec §6 supersedes where they differ |
| `plan/dataset-samples.md`, `plan/team-split-and-structure.md` | Early drafts (Oct 9), mostly superseded |
| `plan/interview-notes.md` | Stale stub; the real interview is in `decisions.md` |
| `research/deaf-fans-research.md` | What deaf/HoH fans miss, evidence levels, what exists |
| `research/icons-and-atmosphere-colors.md` | Icon and atmosphere colour research (WCAG) |
| `research/commentary-from-data.md` | How data-to-text commentary is done credibly |
| `research/reactor-aks-aca-session.md` + `reactor-architecture-slide.png` | Microsoft's official sample app and the patterns we borrowed |
| `research/inside-the-game-repo-analysis.md` | Rival entry (bikilath/inside-the-game). No licence: ideas only, never code |
