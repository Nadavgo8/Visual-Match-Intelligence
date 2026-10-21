# Analysis: github.com/bikilath/inside-the-game

Read 2026-10-10 at commit `eb34191`. Cloned, ran the CLI, ran the tests (74 passed), and probed the sample data with small scripts.

## What it is
Another team's (Bikila Hunde, solo by the commit history) entry for the same Microsoft "Inside the Game" hackathon. It's two commits from Oct 1, so it's early. It covers **stages 1–2 of the 5** (Ingest, Interpret), plus part of Explain. There's no AI, no agents, no Azure, no UI and no personalization yet. The README says so itself: Render and Personalize are "To build".

## Structure and stack
Pure Python 3.10 standard library, with no dependencies (the Azure/FastAPI lines in requirements.txt are commented out).

| File | Lines | Role |
|---|---|---|
| `src/match_sim.py` | 534 | Synthetic match generator writing JSONL events, with an optional `--stream` replay at Nx speed |
| `src/analyze.py` | 474 | Stats engine: team/player stats, possession, field tilt, 5-min momentum windows, controlled/contested/chaotic labels, ranked key moments |
| `tests/` | 534 | 74 pytest tests: determinism, schema consistency, realism ranges, ranking logic |
| `data/match_sample.jsonl` | 2,551 | One generated match |

## How the generator works
- Two fictional clubs, both 4-3-3, with fixed base positions per role. Each team gets tactical dials (`press_intensity`, `directness`, `quality`), and each player gets `technique` and `pace`.
- The match is a loop of possession chains: an optional pressure event, a chance of a shot (only if the carrier's base x ≥ 70), an optional carry, a pass, and on failure a tackle/interception/duel/foul plus `possession_change`.
- Pass difficulty = f(distance, progression, pressure), and that drives completion. xG = f(distance, angle, pressure, technique). A momentum variable drifts and biases who keeps the ball.
- Coordinates are always from the attacking team's point of view (attacking towards x=105).
- Seeded and deterministic.

## Quality: what's good
- The code is clean and readable, with good docstrings explaining design choices (e.g. state thresholds are relative to the match median, not absolute).
- The tests are good: they check internal consistency, not just "it runs".
- The event model is close to what we planned (a StatsBomb-like flat event with type-specific fields). Field tilt, pass difficulty and control/chaos states map straight onto the brief's language.

## Weaknesses I found (checked against the sample match and 20 seeds)
1. **Frame bug in defensive actions.** Tackles and interceptions are tagged to the defending team but use the *attacking* team's coordinates. So `high_tackle` (x ≥ 65, "won high up the pitch") actually fires on tackles in the defender's own half. 135 of 277 defensive actions in the sample are labelled "high". Pressure events have the same problem.
2. **The ball teleports.** Each pass starts from a fresh sample around the passer's base position, not where the previous pass ended. The median jump between receiving and passing is 11.7 m. There's no ball trajectory you could animate on a pitch view.
3. **Only wingers and the striker ever shoot** (RW 9, LW 6, ST 5 in the sample), because shooting is gated on base position.
4. **Goalkeeper "line-breaking passes" dominate key moments.** In the sample, 4 of the top 11 moments are the GK's long kicks, because the GK sits at x=5 and every pass forward is "progressive".
5. **The volumes are off for football:** ~145 tackles + ~130 interceptions per match (real total is roughly 30–40 each). Total xG is 0.9–1.9 (real is ~2.5–3). There's no stoppage time and no kick-off after a goal. 20 seeds gave 0–3 goals per side, which is plausible.
6. **No player tracking** (x/y/speed per frame), so the brief's "player speed and distance" feature isn't really supported. Speeds exist only on carries.

## What it means for us
- **It's a competitor, not a threat yet.** Their strong part is our Person A's half (generator + stats). They have nothing on the half that judging weights most (agents, Foundry/Azure, UX/video). Judging gives Tech implementation, Agentic design, Real-world impact, UX and Category 20% each, and stage 1 is a pass/fail check on Microsoft tech, which they don't have yet.
- **Ideas worth adopting** (concepts, not code — the repo has no license, so copying it isn't allowed):
  - team tactical dials (press intensity, directness) that shape the stream
  - momentum as a drifting latent variable
  - control/chaos state relative to the match's own median
  - an importance score for key moments, so agents explain the top N and don't narrate every event
  - realism tests that assert stats fall in real-world ranges (a nice "synthetic data creativity" proof for judges)
- **Where we can beat it** on the data side: one consistent pitch frame, continuous ball paths and tracking frames (so we can render on a pitch view and do speed/distance), shots from any position, kick-offs after goals and stoppage time, and moment scoring that discounts GK clearances.
- **Rules note:** the rules require a new project built after Sept 29, and multiple entries must be substantially different. Forking this repo would put our originality at risk, so we should use it only as reference.
