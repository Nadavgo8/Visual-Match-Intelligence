# D1-02 — Reproducible scenarios and 20 Hz tracking

D1-02 introduced generator version `2.1.0`; consult `meta.json` for the current generator version. Wire schema: `2.0`. These are short synthetic test segments, separate from the seeded full-match mode. Segment setup is explicit test preparation, not a claim of calibrated football motion.

After installing the project's existing Python development requirements, run offline from the repository root:

```powershell
$env:VMI_OFFLINE = '1'
$env:VMI_WARM_DEMO = '0'
python -m vmi.generator.fixtures --output out/v2-fixtures
python -m vmi.generator.fixtures --scenario goal_cancelled --seed 12 --output out/one-fixture
```

No login, network, model, paid provider, or additional dependency is needed. Generated output is under ignored `out/`; commit source generators and tests, not rendered full matches.

Each scenario exports `meta.json`, `events.jsonl`, `crowd.jsonl`, `match_state.jsonl`, `keyframes.jsonl`, `tracking-20hz.jsonl` and `quality.json`. `quality-summary.json` lists the reports. Export is byte reproducible for the same seed and generator version. The CLI exits nonzero when an unexpected quality error is found.

| Scenario | Contract or behavior exercised |
|---|---|
| `shots_reversed` | Two shots; second xG delivered first, identified by `shot_id` |
| `xg_missing`, `xg_duplicate` | Explicitly missing analytics or one repeated event; no replacement estimate or double count |
| `source_late`, `source_missing` | Dependant arrives first; bounded linking or an explicitly unresolved source |
| `carry` | Movement with possession, without declaring a dribble |
| `dribble_complete` | Named opponent encounter; attacker keeps control |
| `dribble_failed` | Defender wins the ball, with a linked recovery |
| `dribble_interrupted` | Linked foul and explicit stoppage/decision |
| `dribble_unresolved` | Loose ball, no invented winner |
| `handball` | Reported handball offence and explicit free-kick decision; not all hand contacts are offences |
| `penalty_no_card`, `penalty_card`, `penalty_late_card` | Penalty decision independent of card; card links offence/decision/stoppage; late delivery can follow the kick |
| `assist`, `assist_source_late` | Completed pass to shooter in the same possession; late source enriches a new snapshot only |
| `no_goal`, `rebound` | A preparing pass is not automatically an assist; rebound has no automatic assist |
| `goal_cancelled` | Explicit cancellation linked to shot/result/referee decision; score, official shot/momentum counts and assist are withdrawn; pending goal analysis is cancelled |
| `drinks_break` | Existing pending corner survives a 60-second break; only explicit execution resumes play |

The scenario name and injected anomalies are developer-only metadata; initial agent metadata omits both. Match identifiers do not encode the scenario outcome.

## Streaming contract

`Tracker(match).frames(start, end, hz=20)` is an iterator with samples at `start + index / hz`, inclusive of an end that lies on the grid. It rejects nonfinite/out-of-range windows and frequencies outside the supported integer range 1–100 Hz. The server's nominal frame cadence is now 20 Hz. Rendering and interpolation remain D1-04 work.

Frames contain active players, pitch positions, ball height, play state, possession and quality. Scripted dribbles anchor the identified defender around the actual encounter. The exporter writes each frame as it is generated; it does not allocate a whole match's frames in memory.

Quality reports check versions, duplicate IDs, missing links/analytics, score/result consistency, active player uniqueness, positions, ball height and sampling counts. They also report zero-time setup discontinuities and peak ball speed. Injected anomalies must be named explicitly. Setup discontinuities and speed metrics stay visible; a structural PASS does not assert physically calibrated movement or that all setup transitions are football actions.

## Additions to v2 consumers

- A shot may carry `preparing_pass_id`. A valid key pass requires a completed pass to that shooter, matching nonempty possession IDs, and no delivered opponent control between pass and shot. Goal assists additionally require a confirmed goal. Missing recipient, changed possession, a penalty, ambiguous rebound or disallowed goal cannot create an automatic assist.
- `goal_cancelled` carries `shot_id`, `result_id` and `decision_id`. It cannot precede those facts or cancel a different shot. Applying it twice cannot subtract a goal twice. Its feed update retains the shot's existing cue ID.
- `handball.offence` must be true; `dribble.outcome` must be one of the four declared outcomes. An unknown outcome fails validation rather than being treated as success.
- A drinks break retains `stoppage_id` and `restart_id`; crowd sampling and simulation time continue.

The full-match seed sequence is preserved by keeping scripted cases out of the random match loop. No permanent model connection, room authority, `run_id` or CI implementation is added here. Those remain D2 responsibilities. The final test, review and post-merge evidence is recorded in the work board, handoff and PR.
