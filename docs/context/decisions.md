# Decisions log (Oct 8 – Oct 22, 2026)

Everything Nadav decided while planning this project, in order. The original conversation was mostly in Hebrew; this is an English record of it. Later entries override earlier ones. Where this file and an older doc disagree, this file wins. Where this file and Nadav disagree, Nadav wins.

`docs/context/plan/interview-notes.md` is a stale stub from a first attempt at the interview. The real interview ran in the project chat and is recorded below.

## How the idea evolved (Oct 8–13)

- Oct 8: Nadav shared the official rules. Goal (Oct 10): **a polished portfolio project that is also a valid entry.**
- Oct 10: Explored a fan Q&A agent, then accessibility. Chose **accessibility for deaf and hard-of-hearing fans**, focused on what the fan misses because it is *sound*: the referee's whistle and the crowd. Plus a **Q&A chat with deeper analysis**. The chat lives on the **phone as a second screen** while the match is on TV.
- Oct 13: Nadav wrote the vision (Hebrew, summarised): don't replace captions or sign language; give a way to experience nearly the whole match with minimum split attention. Four capability areas (atmosphere, match events, tactical insight, smart commentary). The screen stays clean most of the time. The **Attention Engine** decides what is meaningful, when to show it, how, where (screen / vibration / app) and when to show nothing. This is the main differentiator. Open questions then: visual language, depth of information, proof of value.
- Oct 13: Footage rule means **all input is synthetic structured JSON**, no video. The "broadcast" is a 2D pitch replay rendered from synthetic tracking. Event format: `docs/context/plan/synthetic-event-data.md`.
- Oct 18: Reviewed Microsoft's Reactor session (Brian Benz sample app, `aka.ms/football-results-dashboard`). Patterns borrowed: deterministic numbers with the LLM only for wording and tool choice; evidence IDs on every claim ("receipts"); OpenTelemetry traces; ACA over AKS; managed identity; big prompts kept in `prompts/`. Notes: `docs/context/research/reactor-aks-aca-session.md`; slide: `reactor-architecture-slide.png`.
- Oct 18: Asked whether all Microsoft tools are required (no, at least one Microsoft AI service plus Azure hosting; depth over breadth) and whether the project is theirs (IP stays with the team; Microsoft and PL get a non-exclusive licence). See `docs/context/plan/hackathon-reference.md`.

## The interview (Oct 20, four rounds, in the project chat)

### Round 1: the problem and the user
1. **User:** everyone with hearing difficulty. It is a hearing-accessibility solution. Never ask about hearing level.
2. **First-hand evidence:** none; research instead → `docs/context/research/deaf-fans-research.md`.
3. **What fans miss most:** all of it (atmosphere, whistles and refereeing, commentary). Tactical context somewhat lower priority but still missing.
4. **If only one capability ships:** tactical context is the least important.
5. **Where:** a broadcast on a TV or any screen (including a phone), plus a **companion chat app on the phone**. Not in the stadium.
6. **Concrete "left out" moment:** research it (forums, groups, studies).
7. **Screen rules:** banners (whistles etc.) pop up when needed, **independent of each other**, each in its own fixed position. Deep commentary and tactics **only in the app**. Crowd atmosphere and momentum meters **on the screen**.
8. **Vibration:** only if simple.
9. **Personalisation:** knowledge, favourite team, amount of information. Two depth levels: **basic and deep**.
10. **User testing before the deadline:** no. So never claim user findings.

### Round 2: the solution on screen and in the app
1. Split-screen demo idea OK, but **the video is later, not now.**
2. **Banners:** whistles by type, and **crowd noise level only** (loudness; we cannot tell whose noise or why).
3. **Banner form:** icons; research how others do it → `docs/context/research/icons-and-atmosphere-colors.md`.
4. Show every banner that is needed. Boos are just crowd noise (no classification of noise).
5. **Atmosphere:** one overall indicator for the match, **no home/away split**. Colours researched (tense / pressure / joy / cheering).
6. **Momentum:** rolling **last 7 minutes**, from **possession, key passes and shots**.
7. **App:** **no notifications.** Event feed, analysis during stoppages, and answering the viewer's questions.
8. **Settings:** onboarding questionnaire on first app open (not every match), editable in settings anytime.
9. **Commentary style:** asked for an example (given in round 3).
10. **No card banner.** No merging: offside is offside, foul is foul.

Research finding raised: **no evidence that deaf fans want a momentum bar.** Keep it as a fan feature; never pitch it as an accessibility need.

### Round 3: content, agents, app
1. **Commentary style:** B (a friend sitting next to you explaining) for basic depth, C (analyst) for deep, A (emotional broadcaster) only at peaks like goals and penalties.
2. **Attention Engine role:** yes, it decides **timing and depth** (what goes to the feed, when analysis comes, at what level), plus routing. Not merging banners.
3. Goals, VAR, cards and subs go to the **feed**, not the screen.
4. **Analysis** at half-time, VAR checks, injuries, subs and after goals; **2–3 sentences**.
5. **Onboarding questions:** our call. Never ask about hearing level.
6. **Chat must answer everything:** rules, what happened at a minute, stats, tactics. Decline off-topic.
7. **Language: English for everything** in the product.
8. **Demo match:** a **seeded generator**, with a fixed demo seed (now **12**).
9. **Momentum weights:** asked for an example. Proposed 40/30/30 with a worked example (`docs/spec.md` §3). **Awaiting Nadav's OK.**
10. **Start building as fast as possible.**

Commentary grounding (Nadav pushed back twice, and this is now a hard rule):
- Code builds a **fact pack** (every fact has an event ID) → LLM words it → **validator** checks every number and name is in the pack → **template fallback** if rejected.
- **Never claim why the crowd reacted.** Say "the referee didn't blow, and **immediately** the crowd erupted", not "**so** the crowd erupted".
- **Data realism rule (Oct 20):** Nadav wants top-quality analysis that is credible against a *real* feed, not easy because we planted the answers. The generator emits **only what real sources emit** (official event feed with x/y, optical tracking, a noisy crowd level, match state). The **engine derives everything interpretive**: in-box from coordinates, "not called" from a foul with no whistle followed by a VAR review, xG from shot location, pressure and momentum from positions and events, crowd surge timing from the level series. Add realistic imperfections: feed delays, missing qualifiers, noisy crowd. Spec §6 is the source of truth.

### Round 4: team, access, submission
1. Both registered (Oct 20).
2. **Name:** "ViSense", for now.
3. **Work split:** doesn't matter to them.
4. **Azure:** no subscription; will use a free account. Keep cost near zero (scale to zero, cheap model, local-first). See Azure caveat below.
5. **GitHub repo and licence:** will open and decide later, with Claude's advice.
6. **Fully fictional teams and players.** No Premier League names or marks.
7. Demo sound: both ways (synthetic sound with and without our layer). Video is later.
8. **Vibration: Android only** (Web Vibration API), silently skipped elsewhere. *What* it vibrates on is still open.
9. **Category:** Multi-Agent (Foundry also relevant; "really it's both").
10. **Video: later. Do not raise it.**

## After the interview (Oct 20)

- **Full brief** written: `docs/context/plan/project-brief.md` (Hebrew, v1.0). §16 lists technical additions; all were applied by the build: GPT-5 mini (not a model retiring before Nov 10), min-replicas 1 during judging, demo analysis cache, Explainer as an Agent Framework Workflow, engine tools as an MCP server, visible Attention Engine trace, generator realism tests, and the two spec/code mismatches resolved (crowd surge threshold now 0.22 in both; Kick-off/Half-time/Full-time share one top-centre slot).
- **Azure caveat:** Free Trial subscriptions reportedly get **0 TPM** model quota. Upgrade to **Pay-As-You-Go** (keeps the $200 / 30-day credit) and check Foundry quota first. Community sources, not verified on the official quota page.
- **v1 built** (Oct 20): runs end to end locally, 32 tests pass, demo seed 12. Foundry and Azure wired but never run live.

- **Repo published** (Oct 21): github.com/Nadavgo8/Visual-Match-Intelligence, **MIT licence** (GitHub's starter licence, kept).

## Product update (Oct 21) and final work plan (Oct 22)

Sources: the six-page product doc [`product-doc-2026-10-21.pdf`](product-doc-2026-10-21.pdf) and the work plan [`../implementation/VMI-FINAL-PLAN.md`](../implementation/VMI-FINAL-PLAN.md), both in Hebrew. They override the Oct 20 decisions above where they differ. Behaviour details: `docs/spec.md` v2. Nadav confirmed on Oct 22 that the plan's scope (including 3D) and timeline stand.

What changed:
- **Match screen.** Two identical **atmosphere edge bars** (turquoise to amber, fill height) replace the single atmosphere meter and its mood colours. The **crowd-surge banner is removed**; the bars carry surges. Whistle banners become **round event markers** in one fixed top area, **one at a time** (was: one fixed slot per type, several at once). Still no card, goal, VAR or sub overlays, and now no VAR marker of any kind. Momentum stays under the score bug. The Attention Engine trace moves to a presenter area, off the viewer's screen.
- **Atmosphere = 0.8 × crowd + 0.2 × detected attack** (was: crowd loudness only). Attack tiers 0 / 0.3 / 0.65 / 1 by zone. It is a design rule to try, not xG. Missing crowd data is never read as quiet, and crowd-only mode is labelled.
- **Momentum weights 40/30/30 approved** (product doc p.5).
- **3D match** with Three.js and an npm build step, replacing the 2D pitch. Original procedural assets only.
- **Tracking at 20 per second.** The product doc named 10 per second as a starting point; the Oct 22 plan raised it.
- **App.** Adds **"What did I miss?"**. Onboarding can be skipped. Facts and interpretation are visibly separate. One commentator voice sits over a router, data tools, a meaning analyst, a rules expert and a writer. Answer timeout drops to 20 s (was about 45 s). The phone is optional: the match screen stands on its own.
- **Zero extra cost is a hard rule.** No payment method, no trial that turns into billing, no paid overage. This replaces the Oct 20 plan to upgrade Azure to Pay-As-You-Go.
- **Model and hosting are deliberately left open.** Task D2-00, the first task of Developer 2, decides them with a test set and pass criteria. Azure and Foundry are used only with a verified zero-charge path; otherwise a free host or a test build (rules §4.8).
- **Sync and honesty:** run IDs, snapshots on reconnect, no future data to the agents or the app, and answers labelled as live, cached or template.
- **Work split:** Developer 1 owns the generator, engine, 3D and overlay; Developer 2 owns the model decision, real-time sync, app, agents, CI and hosting (plan §3). This replaces "work split doesn't matter". Which person is which developer isn't recorded here.
- **Git workflow:** branch → tests → commit → push → PR → partner review → squash merge (plan §9). Data contract changes need both developers.
- **Video:** now in the plan (§12). Developer 1 leads capture; Developer 2 leads the script and the agents explanation.
- **Vibration:** in neither document. Parked; don't build it.

Calls made while writing spec v2 (Claude, Oct 22; Developer 1 can revisit them in D1-02):
- The plan asks for "explicit possession state" in tracking. To keep the data realism rule, tracking emits what optical feeds such as TRACAB emit: ball-owning team, ball alive or dead, ball height and speeds. The engine derives which player holds the ball from positions. The event feed arrives 0.5–3 s late, so it couldn't meet the 500 ms freshness rule for the attack component anyway. **Superseded on Oct 23 by the merged D1-01 contract** (approved by the user with Developer 1): tracking samples carry an explicit `possession` with `holder_id`; see `contracts/v2/stream.schema.json`.
- A whistle that stops play for VAR shows the generic whistle marker, never a VAR label.

## Demo match (Oct 27)

- Generator fixes kept changing seed 12 (2–1, then 6–0, then 0–2). Nadav chose **seed 2** as the demo match: Harbour City 2–1 Northvale Rovers, with a VAR-overturned penalty (37:16, scored 37:58), a second home goal (43:34) and an away goal kept after a VAR check (65:08 / 66:38).
- The story is locked by `tests/test_demo_match.py`, so a generator change that alters it fails CI. Changing the demo on purpose means updating that test and the demo script together. The model evaluation keeps its own frozen fixture (generator 2.2, seed 12).
- Any seed still works; the seed only sets which match a room starts with.
- Later on Oct 27 Nadav asked for a different generated match each time: a new room now starts on a **random** seed. For recording, `VMI_DEMO=1` makes every new room the demo match and pre-writes its analyses; `/tv?demo` loads it for one room. The TV also has a **Random match** button.

## Unified match chat (Oct 27)

- Nadav merged the app's Feed and Ask tabs into **one chronological chat** and approved **two named voices**, replacing "one commentator voice": **Kai** (commentator: what happened, labelled Fact) and **Ada** (analyst: what it means, labelled Interpretation; also answers rules questions). Nadav also explicitly overrode the 24-hour feature freeze for this change.
- **Built on what exists, no rewrite.** Kai's automatic lines are the Attention Engine's feed items and stay **written by code** (Nadav's call). Ada's automatic messages are the existing stoppage analyses (fact pack → LLM → validator → template) and the engine's momentum call. When Ada stays silent, that is the engine's existing decision, logged with a `why`.
- **Agent-to-agent replies come only from fixed engine rules**, never from one agent invoking the other. Each analysis replies to the commentator item for the event it explains. A goal links back to Ada's momentum call for the same team if that call came in the previous 10 minutes; it is only a link, with no claim about cause. Nothing replies to an analysis, so a thread is at most two hops and can't loop.
- **Who answers a question** is chosen in code from the question and the agent that answered. A "why", meaning or rules question goes to Ada; anything else goes to Kai.
- Not built: an LLM-based router, or contextual follow-ups that resolve "that goal" against earlier chat messages.
- **Later the same day: human voices, still not entirely LLM (Claude's recommendation; Nadav asked, and can switch).** Kai's live lines are picked in code from several hand-written phrasings per event, fixed per event (`vmi/agents/voices.py`). They are built only from facts the engine attaches (`say`), and deep depth keeps the engine's precise wording. Ada's analysis no longer re-announces the event or mentions the crowd; it reacts to Kai. Kai may close with **one** line drawn from the same fact pack: the measured crowd jump with no cause, the minutes left, or a half-time or full-time sign-off. So an exchange is at most Kai → Ada → Kai, and the last turn is never answered. Why not all LLM: about 12 s p95 lag after a goal, quota, and demo reliability. The LLM still writes Ada's analyses and the answers to questions.
- Nadav asked for player and chance call-outs. Ada replies to a missed shot with **"big chance missed"** once its delivered synthetic xG is at least **0.25** (said once per shot). Kai notes a player reaching **3 and 5 shots or key passes**. Counts are what has been delivered so far, and the engine derives key passes. Half-time and full-time analyses are now a fuller report of up to 6 sentences; other moments stay at 3.
- Player leaders: a new read-only tool `get_leaders` (goals, shots, shots on target, key passes, xG, passes completed, fouls), with a no-model answer for "who had the most…" questions; a tie is reported as a shared lead. Half-time and full-time reports name a clear leader for shots and key passes. Chat text drops the word "synthetic" (the whole product is declared synthetic elsewhere) and uses short dashes.
- The receipts block and the logged-event ids are no longer shown in the chat. Every message still says who wrote it: "AI" or "written by code".

## Still open (as of Oct 22)

| # | Decision | Owner | Note |
|---|---|---|---|
| 1 | Model, runtime and judge access | Developer 2 (D2-00), then both | Zero cost; candidates and pass criteria in plan §7. Worth checking: Azure for Students (advertised as no card, $100 credit) if either of you is eligible. Not verified |
| 2 | Which person is Developer 1 and Developer 2 | team | |
| 3 | Team name, who submits | Nadav | |
| 4 | Final product name | Nadav | |
| 5 | Vibration | Nadav | parked; not in the current plan |
