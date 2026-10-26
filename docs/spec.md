# Visual Match Intelligence: build spec (v2, 2026-10-22)

Visual Match Intelligence turns the parts of a football broadcast that hearing fans get through sound (whistles, the crowd, the commentator) into visual signals on the match screen, plus an optional companion app on the phone. It is for anyone with hearing difficulty. It does not replace captions or sign language. It never asks about hearing level. The match screen works on its own; the phone is never required.

All data is **synthetic**: a seeded generator produces the event feed, tracking, crowd level and match state. There is no footage. The match is rendered from synthetic tracking and labelled *synthetic*. **The match and its facts are deterministic; only the wording may vary.** The same seed and generator version give the same events and positions. A language model never decides a result, an atmosphere level or whether a marker shows.

**Sources.** v2 follows the product doc of Oct 21 ([`context/product-doc-2026-10-21.pdf`](context/product-doc-2026-10-21.pdf), Hebrew) and the work plan of Oct 22 ([`implementation/VMI-FINAL-PLAN.md`](implementation/VMI-FINAL-PLAN.md), Hebrew). Task IDs in brackets, such as [D1-03], point to that plan. Why each change was made: [`context/decisions.md`](context/decisions.md).

**Status.** This spec describes the target. The code still implements v1: a 2D pitch, rectangular whistle banners in fixed slots, a crowd-surge banner, a mood-coloured atmosphere meter and the trace on the TV view. Parts marked *(built)* exist in v1; the rest is still to build.

## 1. Surfaces

### Match screen (`/tv`) [D1-04, D1-05]
The 3D match (§9) with a score bug, plus three overlay elements and nothing else:

| Element | Rules |
|---|---|
| **Atmosphere edge bars** | Two identical thin bars against the left and right edges of the screen, with a small margin so a TV can't crop them. The track runs almost the full height. Both always show the same value (§3); they never stand for the two teams. Fill height and brightness change continuously with the level, and the hue runs along a fixed palette from soft turquoise (low) to warm amber (high). Fill height carries the level too, so colour is never the only signal (WCAG 1.4.1). No flashing, pulsing or celebration bursts (WCAG 2.3.1). When crowd data is missing, the bars ease to a neutral state; they never read it as a quiet crowd. |
| **Event markers** | Round: a dark circle, a light icon, a subtle border and a short English label. Distinct icons for a generic whistle, Foul, Offside and Penalty, plus Kick-off, Half-time and Full-time. One fixed area in the top margin, as far from the action as possible and outside the score bug. **One marker at a time.** Shown for 3 s of match time (4 s for Penalty and the end of a period); pausing freezes them. The whistle is detected before the feed says why: the engine waits up to 2 s for the reason *(built)*; with no reason it shows the generic whistle marker, and replaces it in place when the reason arrives. A newer whistle replaces the current marker. When several things compete, the engine shows what is needed now and leaves the rest to the app feed. Restart whistles get no marker, except kick-offs *(built)*. A whistle that stops play for VAR shows the generic whistle marker, never a VAR label. |
| **Momentum** | A thin bar under the score bug (§4) *(built)*. A computed reading of the last 7 minutes, not a prediction of the next goal. |

Never on the match screen: cards, goals, VAR, subs, a crowd-surge banner (removed: the edge bars carry crowd surges), floating player names, the Attention Engine trace, or any technical information.

**Display settings:** an optional menu on the match screen with bar intensity, marker size and reduce motion. No mandatory calibration screen and no colour picker.

### Presenter area [D1-05, D2-02]
The trace of Attention Engine decisions, playback control (pause, seek, seed, demo chapters) and technical information move here, off the viewer's screen. Only the host controls playback; the companion app never changes the match. Demo chapters are picked here, and nothing in this area is sent to the app or to the agents (§8).

### Companion app (`/app`, optional) [D2-03]
No notifications, ever, and nothing that invites the viewer to look away during live play: explanations wait in the feed.

1. **Feed:** goals, VAR phases, cards, subs, big chances and momentum swings, one line each *(built)*, plus stoppage analysis cards of 2–3 sentences *(built)*. Facts and interpretation are visibly separate. Evidence (the event IDs behind a sentence) opens on tap *(built)*.
2. **What did I miss?** [D2-04]: a short summary on request (rules below).
3. **Ask:** one commentator voice that answers anything about this match, the rules, stats and tactics *(built, as a chat)*. Off-topic questions are politely declined.

**Onboarding (once), editable in Settings anytime** *(built)*, and now skippable, starting from defaults:
1. *How well do you know football?* New to it / I follow it / I know it inside out → depth **basic** for the first two, **deep** for the third.
2. *Which team are you supporting?* Home / Away / Neutral → the feed and analysis say "your team".
3. *How much do you want from the app?* Just the big moments / Balanced / Everything → how much the feed and analysis show.

**What did I miss?**
- On request only. The window closes the moment the button is pressed; events that arrive later don't change an answer being built.
- The window starts where the user last saw the top of the feed or last got a summary. On first use: the last 5 minutes, or since kick-off if less has been played.
- The answer states the time range it covers. If nothing important happened, it says so.
- It uses delivered events only. Which events go in is decided by code; AI only words it, under the same validator and template fallback (§5).
- The checkpoint is stored per match and per run. A failed summary doesn't mark events as read.

## 2. The Attention Engine

Deterministic code, no AI *(built)*. For every delivered record it decides **routing, timing and depth**, and records a `why` for each decision. The trace of these decisions is shown in the presenter area.

| Route | What it means |
|---|---|
| `screen` | An event marker on the match screen, by the rules in §1. |
| `meters` | Atmosphere (§3) and momentum (§4), once per second. |
| `feed` | A line in the app feed, filtered by the user's "how much" setting. |
| `analysis` | A stoppage analysis card, released only while the ball is out of play and the stoppage is long enough to read it (VAR ≥ 20 s, sub, injury, goal celebration, half-time). |
| `none` | Nothing. Passes, carries, clearances and restarts are visible on the pitch or don't matter. |

Every feed item and analysis has a tier, and the user's "how much" answer sets the highest tier they see:

| Tier | Feed | Analysis | Shown for |
|---|---|---|---|
| 1, big | goals, penalties, VAR decisions, red cards, kick-off, half/full-time | goals, VAR checks and decisions, half/full-time | everyone |
| 2, balanced | yellow cards, VAR checks, subs, added time, big chances (xG ≥ 0.3) | substitutions | Balanced and Everything |
| 3, everything | saves and shots off the post, injuries, momentum swings | injuries | Everything |

Depth (basic or deep) picks the commentary style. Crowd surges are still detected from the level series, but only as facts for the feed and the fact pack, never as a banner. Phone vibration is parked: neither the Oct 21 doc nor the Oct 22 plan includes it.

## 3. Atmosphere [D1-03]

**A = 0.8 · C + 0.2 · T**, with both components on 0–1 and A shown as 0–100.

- **C** is the smoothed crowd level (v1 smooths with the mean of the last three one-second readings).
- **T** is a capped attack component:

| Situation | T |
|---|---:|
| No detected attack, or the data isn't reliable | 0 |
| Controlled possession near the opponent's box: up to 6 m outside it, within its width | 0.3 |
| Controlled possession inside the opponent's penalty box | 0.65 |
| Controlled possession inside the opponent's six-yard box | 1 |

T counts only when all of these hold: the ball is in play; possession is identified and held by an outfield player; the ball is near the opponent's goal for the current attacking direction (which swaps at half-time); tracking and possession data are at most 500 ms old in simulation time. Moving up to a higher tier needs 300 ms of stability, which filters jitter on the box line. Losing the ball, a goalkeeper in possession, a stoppage or missing data drops T to 0 at once. A team holding the ball near its own goal gets 0.

**No inflation.** A quiet crowd stays quiet: with no crowd noise, the attack adds at most 20 points. "No crowd noise" means a valid reading of silence. **Missing crowd data is marked unavailable, never treated as quiet**, and the bars ease to a neutral state.

**Crowd-only mode.** If possession and direction can't be identified reliably, the bars show A = C and the mode is labelled. It is a declared mode, never a silent change of weights.

This is a conservative design rule to try. It is not xG and not a danger metric, and it prefers missing an unclear moment to lighting up false pressure. The 80/20 split is a design ratio, not a research finding. The v1 "mood" labels (Calm, Cheering, Tension, Eruption) are replaced by the level-graded palette.

**Required tests:** a goalkeeper holding the ball in their own box gives T = 0; defenders passing near their own goal give T = 0; a controlled attack near the opponent's goal gives T by tier; losing the ball, a stoppage and stale data each cancel T; a quiet crowd isn't boosted; missing crowd data isn't read as quiet; entering the box, leaving it and jitter on the box line; sides swap at half-time; a loud crowd with no attack; a quiet crowd with an attack; both bars always show the same value.

## 4. Momentum (approved Oct 21)

A rolling window over the **last 7 minutes of match time**, recomputed every second *(built)*:

- **P** = home share of possession time in the window
- **K** = home share of key passes (a key pass is a pass whose next action is a shot by the receiver), smoothed: (k_home + 1) / (k_home + k_away + 2)
- **S** = home share of shots, smoothed the same way
- **Home index** I = 0.4·P + 0.3·K + 0.3·S, and the away index is 1 − I
- **Momentum** M = 2·I − 1, from −1 (all away) to +1 (all home). The bar shows I as the home share.

Why these weights: possession is the most frequent signal but the weakest sign of danger, while key passes and shots are rarer but mean more, so 40/30/30 stops sterile possession from owning the bar. The +1 smoothing stops a single shot from swinging the bar to 100%. The weights live in `vmi/engine/model.py`. The app and the score bug use this same definition when they explain the bar.

**Worked example** (minutes 59–66):
- Home had the ball for 4:12 of the 6:00 in play → P = 0.70
- Key passes: home 3, away 0 → K = (3+1)/(3+0+2) = 0.80
- Shots: home 2, away 1 → S = (2+1)/(3+2) = 0.60
- I = 0.4·0.70 + 0.3·0.80 + 0.3·0.60 = 0.28 + 0.24 + 0.18 = **0.70**
- The bar shows **70% home**, M = +0.40. At |M| ≥ 0.3 the label reads "Home on top", and a swing across that line goes to the feed for users on "Everything".

## 5. Commentary: grounded by design

1. **Fact pack (code)** *(built)*: when the engine opens an analysis, code walks the `related` links back from the trigger event and builds a small JSON of facts, each with its event ID, plus score, minute and minutes left. Deep users also get engine stats (momentum, shots, recent pattern). Every pack holds only records delivered by that moment.
2. **Wording (model)** *(built)*: the model writes 2–3 sentences using only the pack, and returns each sentence with its evidence IDs. Style **B** ("a friend explaining what happened and why it matters") for basic, **C** (analyst) for deep, and a touch of **A** (broadcast excitement) only at peaks: goals, penalties, red cards.
3. **Validator (code)** *(built)*: every sentence needs evidence that exists in the pack, and every number and name in the text must appear in the pack. If anything fails, a template writes the card instead, so there is always a correct text.
4. **The crowd rule:** the text may say the crowd reacted *right after* something, never *why* it reacted. No invented motives for players or feelings for the crowd.
5. **Facts vs interpretation:** conclusions that aren't facts carry an *interpretation* label. The commentator doesn't add an opinion after every pass.
6. **Honest labels:** every text records how it was made (live model, cached model output, or template), and the app never presents a cached or template text as a live AI answer.

## 6. Agents [D2-05]

The viewer talks to **one commentator voice**. Behind it:

| Role | Job | Status |
|---|---|---|
| **Router** | Sends each question to the right expert, or declines off-topic questions | built |
| **Data analyst** | Brings the numbers through read-only engine tools: score, events in a minute range, team stats, momentum, player summary | built (as "Match analyst") |
| **Meaning analyst** | Explains what the facts suggest, always starting "Interpretation:". For meaning questions ("who's on top?", "what changed?") code gathers the facts through the data tools and the meaning analyst makes the only model call, so it fits the 20 s limit; the router can also hand it the match analyst's facts | built (D2-05) |
| **Rules expert** | Answers Laws of the Game questions, linked to the current match when relevant (rules knowledge base, the event being asked about) | built |
| **Writer** | Merges the parts into one short answer at the viewer's depth and style. This is the router's final step, adding no facts of its own | built (D2-05, as the router's last step) |
| **Explainer** | Writes stoppage analysis from a fact pack, as an Agent Framework **Workflow** (writer → validator → template fallback) | built |

The read-only engine tools are also served as an **MCP server** (`python -m vmi.mcp_server`) *(built)*.

**Rules for every answer:**
- It is built against a snapshot of the moment the question was asked. Agents never see undelivered events, and have no access to the generator or to a full-match export.
- The validator checks evidence IDs, names, numbers, and that each fact is used as the right kind of fact.
- At most 6 tool calls and **20 s in total** per question; past that, the defined fallback answers.
- When there isn't enough information or the model is unavailable, a fallback says so instead of guessing.
- Before an automatic explanation is published, the engine checks again that play is still stopped and the run is still current.
- A failure or an exhausted quota never switches to a paid provider and never triggers unlimited retries.

No automated check can rule out every hallucination, so the test set includes trick questions (future events, false premises, missing data) and answers are also reviewed by hand.

**Model and runtime: open, by design.** Task D2-00 decides which model, where it runs and how judges reach it, under the zero-cost rule (§10). Candidates in plan §7: a local model (for example Phi-4-mini) through Ollama and Agent Framework; Copilot SDK on Copilot Free (personal use; shared use only after its terms are checked); Foundry on Azure with a verified zero-charge benefit; another free provider. Templates are a fallback only, never a substitute for the AI. GitHub Models closed on Jul 30, 2026. Agents connect through a **provider-neutral layer**: it takes a question or explanation request, a snapshot, the profile and a time limit, and returns text, fact references and a status, logging provider, model, fallback use and errors. v1 already has Foundry wiring (keyless, Entra ID) and deterministic local implementations behind the same interfaces, so everything runs offline.

## 7. Data realism

The analysis has to be good **because the engine works it out**, not because we wrote the answers into the synthetic data. So the generator emits only what real sources produce today, and every record carries its `source`:

| Stream | Real-world equivalent | What the generator emits | What it never emits |
|---|---|---|---|
| `event` (`source: event_feed`) | Official event feed (Opta / StatsBomb style), logged live by operators | passes (start, end, recipient, complete or not), shots (location, body part, outcome), tackles, interceptions, clearances, **fouls only when awarded**, set pieces, offsides, cards, subs, VAR phases with incident, original decision and outcome, injury stoppages, period start and end | xG, "in the box", "not called", key pass flags, danger, why anything happened |
| `whistle` (`source: audio`) | Whistle detection on the referee / stadium audio | time, number of blasts, length, detection confidence | the reason for the whistle |
| `crowd` (`source: audio`) | Stadium microphones, 1 reading per second | `crowd_level` 0–1 relative to this match, with noise; readings can be missing | mood, boos, chants, home/away split, what the crowd reacted to |
| `tracking` (`source: tracking`) | Optical tracking (TRACAB style), **20 per second** [D1-02] | active players with x/y and role, the ball's x/y and height, `ball_in_play`, a `possession` sample (`status` controlled / loose / stopped, team, `holder_id`, possession ID) and a measurement-quality flag with its sample time | attack zone, pressure, formation labels, danger |
| `match_state` (`source: event_feed`) | Scoreboard / feed state | score, period, ball in or out of play, players on pitch, attacking direction per period | stoppage reason |

This is the merged D1-01/D1-02 contract; the JSON Schemas in `contracts/v2/` document it. The engine still derives the attack tier, atmosphere and everything interpretive from these samples.

**Everything interpretive is derived by the engine:** `in_box` from coordinates, xG from shot location and angle, "the referee didn't give it" from a VAR penalty check whose original decision was no penalty, key passes from a pass followed by the receiver's shot, the whistle reason from the next feed event, **the ball holder and their role** from positions, the ball-owning team and the team sheet, **the attack tier T and the atmosphere** (§3), danger and momentum from events and positions, and crowd surges from the level series. The event feed arrives late, so the attack component has to come from tracking to meet its 500 ms freshness rule.

**Realistic imperfections:** feed events arrive 0.5–3 s after they happen (the replay delivers them late, so the engine works on a delayed feed like a real one), about 3% of passes have no recipient, about 5% of shots have no body part, locations carry ±1 m of operator error, the crowd level is noisy and can drop out, tracking quality dips for short spells, and whistle detections have a confidence below 1.

The generator also keeps a private "truth" (for example the true chance quality) that it uses to simulate outcomes, but that truth is never emitted.

### Generator [D1-01, D1-02]

One shared generator with one owner (Developer 1). It separates: (1) the internal match state (who has the ball, who is active, the current move, ball live or dead); (2) move planning (pass, carry, shot, loss, stoppage); (3) continuous motion of the ball and players; (4) the outcome, decided inside the simulation; and (5) the emitted feeds, with defined delays and noise.

**Invariants:** the ball's path matches the pass, and the ball is free in flight, never glued to a player who has already passed it; ground and aerial paths with ball height; speed and acceleration limits come from config; sides swap at half-time; a sent-off player never comes back, and a substitute appears only after the sub; the goalkeeper and the defence move sensibly; no live attack continues during a stoppage.

**Modes:** full match (seeded); test scenario (one defined move); demo (chapters of one consistent match, with visible jumps in time); load test (a fast feed, never shown as normal football pace).

**Checks:** the same seed and version give the same output; invariants and distributions over 100 seeds; a report of goals, shots, passes, stoppages and possession; detection of position jumps, missing players and a score that doesn't match the events. Short fixtures live in the repo; full-match tracking is generated by a command. The existing realism ranges stay as sanity checks, not research calibration. The full list of events to cover is in plan §5.

## 8. Time and sync [D2-02]

- `t` is seconds on one monotonic simulation timeline (half-time compressed to 60 s), and `clock` is the displayed match clock derived from it *(built)*.
- Every record has both the time it happened and the time it was delivered. Interpretation and agents use delivered records only.
- Every seed change or seek starts a new `run_id`. Async answers from an older run are dropped.
- Server messages carry sequence numbers. A newer tracking frame may replace an older one, but a significant event is never dropped silently.
- A seek clears temporary markers and rebuilds the screen and the feed. Pause freezes the match and marker lifetimes.
- A dropped connection is shown as disconnected; the screen never invents play. On reconnect, the client first gets a full snapshot, then live updates, with a bounded backoff between attempts.
- The full-time summary card stays after the last tick.
- **No foreknowledge:** the final result, end-of-match details and future demo chapters are never sent to the app or the agents while a match is being watched. The landing page's raw-data links (`/api/match/{seed}/{stream}`) are for transparency and development only, and agents have no route to them.

## 9. Match screen rendering [D1-04]

- Three.js, installed with npm and bundled by a build step. Versions are locked after a compatibility check, and nothing is loaded from a CDN during a demo. The existing vanilla JS modules stay; no move to React.
- A 105 × 68 m pitch; players with a body, limbs, kits and a basic run animation (not numbered circles); a synthetic stadium, goals, lighting and shadows; distinct team colours.
- A high broadcast camera that follows smoothly, with no automatic cuts.
- Ball paths come from the generator; the renderer never decides the outcome of a move. Run animation is driven by simulation time and distance, so it behaves correctly on pause and seek.
- A low-quality mode reduces shadows and resolution on the same data.
- Original procedural assets only: no bought models, no unlicensed assets.

The illustration in the product doc shows the design direction; it is not a promise of broadcast photorealism.

## 10. Stack, cost and hosting

- Python 3.12+ with FastAPI for the generator, engine, agents and API, and one WebSocket protocol for the match screen and the app *(built)*. Three.js through npm for the match screen (§9).
- **Zero extra cost is a hard rule.** No purchases or subscriptions, no payment method, no trial that turns into billing, no paid overage, and no relying on remembering to cancel. A free tier is acceptable only if its terms fit and nothing switches to billing automatically; when its quota runs out, calls stop or a labelled fallback shows. Hackathon credits and perks are not an approved budget. If no option meets both the quality bar and zero cost, that is reported as a blocker.
- **Hosting** is decided in D2-00 and D2-06: verified free hosting, or a local test build (the rules accept a website, a working demo or a test build). Judges must never pay or need a paid account. Azure (Container Apps with one replica for the in-memory rooms, managed identity, Application Insights; `infra/deploy.sh` *(built)*) is used only if a zero-charge path is verified, including the registry, storage, build, monitoring and traffic.
- CI runs the Python tests and the frontend build on every PR, on a runner verified to be free.
- Everything runs locally with `uvicorn` and no cloud account *(built)*.

## 11. Performance targets

Initial acceptance targets, to be measured on documented hardware. None of them has been measured yet.

- 3D at 60 fps if possible, and at least 30 fps in the basic quality mode.
- Match screen and app clocks within 500 ms of each other on a normal network.
- A marker processed locally within 250 ms of the input it needs arriving (separate from the up-to-2 s wait for a whistle's reason).
- A load test of three rooms, each with one match screen and two app clients.
- A 30-minute continuous run with no unbounded growth of queues or tasks.
- If a local model is chosen, it is tested running alongside the 3D view, measuring its effect on memory and frame rate.
