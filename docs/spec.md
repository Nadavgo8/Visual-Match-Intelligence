# Visual Match Intelligence: build spec (v1, 2026-10-20)

Visual Match Intelligence turns the parts of a football broadcast that hearing fans get through sound (whistles, the crowd, the commentator) into visual signals on the screen and a calm companion app on the phone. It is for anyone with hearing difficulty. It does not replace captions or sign language. It never asks about hearing level.

All data is **synthetic**: a seeded match generator produces the event feed, tracking, crowd audio level and match state. There is no footage. The "broadcast" is a 2D pitch replay labelled *synthetic*.

## 1. Surfaces

### TV view (the broadcast)
The 2D pitch replay with a score bug, plus three overlay elements and nothing else:

| Element | What it shows | Rules |
|---|---|---|
| **Whistle banners** | One banner per whistle, by type: Foul, Offside, Penalty, Stoppage (injury, VAR, other), Kick-off, Half-time, Full-time | Every banner is independent and never merged. Foul, Offside, Penalty and Stoppage each have their own fixed slot in the left column. Kick-off, Half-time and Full-time share one slot at the top centre, since they can never happen together. Icon plus a 1–2 word English label. Shown for 3 s (4 s for Penalty, Half-time and Full-time). Restart whistles get no banner, except kick-offs. The whistle is heard (detected) before the feed says why: if the feed hasn't explained it within 2 s, a generic *Whistle* banner shows in the Stoppage slot and moves to its type's slot the moment the reason arrives. |
| **Crowd surge banner** | "Crowd erupts" when the crowd level jumps sharply | Triggered by a rise of at least 0.22 on the 0–1 crowd level within 3 s, reaching at least 0.55, at most once every 12 s. It says only that the crowd got louder, never why. |
| **Atmosphere indicator** | One overall level for the whole stadium (no home/away split) | **Level** (5 steps) drives the meter height, brightness and saturation, so it reads in greyscale. **Mood** (Calm, Cheering, Tension, Eruption) sets the hue, a text label and a wave shape, so colour is never the only signal (WCAG 1.4.1). Nothing flashes faster than once per second (WCAG 2.3.1). Colours follow `research/icons-and-atmosphere-colors.md`. |
| **Momentum bar** | Who is on top in the last 7 minutes | See §3. A thin bar under the score bug. |

No cards, goals, VAR or subs appear as overlays. Those go to the companion app.

### Companion app (phone)
No notifications, ever. Three parts:
1. **Event feed:** goals, VAR phases, cards, subs, big chances and momentum swings, one line each.
2. **Stoppage analysis:** a 2–3 sentence card at half-time, VAR checks, injuries, subs and after goals. Every sentence has receipts (the event IDs behind it), viewable with a tap.
3. **Ask:** a chat that answers anything about this match, the rules, stats and tactics. Off-topic questions are politely declined.

**Onboarding (once), editable in Settings anytime:**
1. *How well do you know football?* New to it / I follow it / I know it inside out → depth **basic** for the first two, **deep** for the third.
2. *Which team are you supporting?* Home / Away / Neutral → the feed and analysis say "your team".
3. *How much do you want from the app?* Just the big moments / Balanced / Everything → how much the feed and analysis show.

## 2. The Attention Engine

Deterministic code, no AI. For every event it decides **routing, timing and depth**, and records a `why` for each decision:

| Route | What it means |
|---|---|
| `screen` | A whistle or crowd-surge banner on the TV view. This is fixed by the rules in §1. |
| `feed` | A line in the companion feed. Filtered by the user's "how much" setting. |
| `analysis` | A stoppage analysis card, released only while the ball is out of play and the stoppage is long enough to read it (VAR ≥ 20 s, sub, injury, goal celebration, half-time). |
| `none` | Nothing. Passes, carries, clearances and restarts are visible on the pitch or don't matter. |

Every feed item and analysis has a tier, and the user's "how much" answer sets the highest tier they see:

| Tier | Feed | Analysis | Shown for |
|---|---|---|---|
| 1, big | goals, penalties, VAR decisions, red cards, kick-off, half/full-time | goals, VAR checks and decisions, half/full-time | everyone |
| 2, balanced | yellow cards, VAR checks, subs, added time, big chances (xG ≥ 0.3) | substitutions | Balanced and Everything |
| 3, everything | saves and shots off the post, injuries, momentum swings | injuries | Everything |

Depth (basic or deep) picks the commentary style. Vibration on the phone is not built yet: what it buzzes on is still an open decision.

## 3. Momentum (proposed weights)

A rolling window over the **last 7 minutes of match time**, recomputed every second:

- **P** = home share of possession time in the window
- **K** = home share of key passes (a key pass is a pass whose next action is a shot by the receiver), smoothed: (k_home + 1) / (k_home + k_away + 2)
- **S** = home share of shots, smoothed the same way
- **Home index** I = 0.4·P + 0.3·K + 0.3·S, and the away index is 1 − I
- **Momentum** M = 2·I − 1, from −1 (all away) to +1 (all home). The bar shows I as the home share.

Why these weights: possession is the most frequent signal but the weakest sign of danger, while key passes and shots are rarer but mean more, so 40/30/30 stops sterile possession from owning the bar. The +1 smoothing stops a single shot from swinging the bar to 100%. These are proposals, easy to change in `vmi/engine/momentum.py`.

**Worked example** (minutes 59–66):
- Home had the ball for 4:12 of the 6:00 in play → P = 0.70
- Key passes: home 3, away 0 → K = (3+1)/(3+0+2) = 0.80
- Shots: home 2, away 1 → S = (2+1)/(3+2) = 0.60
- I = 0.4·0.70 + 0.3·0.80 + 0.3·0.60 = 0.28 + 0.24 + 0.18 = **0.70**
- The bar shows **70% home**, M = +0.40. At |M| ≥ 0.3 the label reads "Home on top", and a swing across that line goes to the feed for users on "Everything".

## 4. Commentary: grounded by design

1. **Fact pack (code):** when the engine opens an analysis, code walks the `related` links back from the trigger event and builds a small JSON of facts, each with its event ID, plus score, minute and minutes left. Deep users also get engine stats (momentum, shots, recent pattern).
2. **Wording (Foundry agent):** the model writes 2–3 sentences using only the pack, and returns each sentence with its evidence IDs. Style **B** ("a friend explaining what happened and why it matters") for basic, **C** (analyst) for deep, and a touch of **A** (broadcast excitement) only at peaks: goals, penalties, red cards.
3. **Validator (code):** every sentence needs evidence that exists in the pack, and every number in the text must appear in the pack. If anything fails, a template writes the card instead, so there is always a correct text.
4. **The crowd rule:** the text may say the crowd reacted *right after* something, never *why* it reacted.

## 5. Agents

Built with Microsoft Agent Framework on Microsoft Foundry. When no Foundry endpoint is configured, the same interfaces run on deterministic local implementations, so everything works offline. The stoppage analysis runs as an Agent Framework **Workflow** (writer → validator → template fallback), and the read-only engine tools are also served as an **MCP server** (`python -m vmi.mcp_server`) so any MCP client can query a match. The demo match's analysis texts are written once at startup and cached for every profile.

| Agent | Job | Tools |
|---|---|---|
| **Explainer** | Writes stoppage analysis from a fact pack | none (input is the pack) |
| **Match analyst** | Answers questions about this match: what happened, stats, tactics | read-only engine tools: score, events in a minute range, team stats, momentum, player summary |
| **Rules expert** | Answers Laws of the Game questions, linked to the current match when relevant | rules knowledge base, the event being asked about |
| **Router** | Sends each question to the analyst or the rules expert, or declines off-topic questions | handoff |

Guardrails: at most 6 tool calls and about 45 s per answer, every answer carries receipts (event IDs, model, latency), and off-topic questions are declined.

## 6. Data realism

The analysis has to be good **because the engine works it out**, not because we wrote the answers into the synthetic data. So the generator emits only what real sources produce today, and every record carries its `source`:

| Stream | Real-world equivalent | What the generator emits | What it never emits |
|---|---|---|---|
| `event` (`source: event_feed`) | Official event feed (Opta / StatsBomb style), logged live by operators | passes (start, end, recipient, complete or not), shots (location, body part, outcome), tackles, interceptions, clearances, **fouls only when awarded**, set pieces, offsides, cards, subs, VAR phases with incident, original decision and outcome, injury stoppages, period start and end | xG, "in the box", "not called", key pass flags, danger, why anything happened |
| `whistle` (`source: audio`) | Whistle detection on the referee / stadium audio | time, number of blasts, length, detection confidence | the reason for the whistle |
| `crowd` (`source: audio`) | Stadium microphones, 1 reading per second | `crowd_level` 0–1 relative to this match, with noise | mood, boos, chants, home/away split, what the crowd reacted to |
| `tracking` (`source: tracking`) | Optical tracking, 10 per second | x/y of 22 players and the ball, with small jitter | speeds, pressure, formation labels |
| `match_state` (`source: event_feed`) | Scoreboard / feed state | score, period, ball in or out of play, players on pitch | stoppage reason |

**Everything interpretive is derived by the engine:** `in_box` from coordinates, xG from shot location and angle, "the referee didn't give it" from a VAR penalty check whose original decision was no penalty, key passes from a pass followed by the receiver's shot, the whistle reason from the next feed event, danger and momentum from events and positions, and crowd surges from the level series.

**Realistic imperfections:** feed events arrive 0.5–3 s after they happen (the replay delivers them late, so the engine works on a delayed feed like a real one), about 3% of passes have no recipient, about 5% of shots have no body part, locations carry ±1 m of operator error, the crowd level is noisy, and whistle detections have a confidence below 1.

`t` is seconds on one monotonic match timeline (half-time compressed to 60 s), and `clock` is the displayed match clock. The generator also keeps a private "truth" (for example the true chance quality) that it uses to simulate outcomes, but that truth is never emitted.

## 7. Stack (defaults chosen for speed)

Python 3.12+ with FastAPI for the generator, engine, agents and API. One web frontend with no build step: `/tv` and `/app` views, with live push over WebSocket. Agents on Microsoft Foundry through Agent Framework. Hosting on Azure Container Apps with Application Insights (OpenTelemetry). During judging the app keeps one replica (no cold start); the model must be one that is not retiring before Nov 10 (e.g. GPT-5 mini). Everything runs locally with `uvicorn` and no Azure account.
