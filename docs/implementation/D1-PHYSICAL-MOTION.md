# Physical source motion, generator 2.5

Status: implementation and targeted validation in progress. This is not full
football, anatomy or visual acceptance. The annotated 2.2 benchmark is unchanged.

## Concrete changes

Source 2.4 put the controlled ball at the player's root and allowed instantaneous
velocity changes. Independent regressions reproduced zero root/contact separation
and a 7.13 m/s velocity change across 100 ms. Its low defensive support rule also
collapsed CB, fullback, midfield and forward targets to the same x=8 m line.

Ordinary matches now plan immutable cubic Hermite body paths (`source-paths-2`).
Shared velocities continue through compatible runs. True reversals brake; source
bookkeeping alone does not reset velocity. Scheduling creates real time for
constrained contacts. Speed extrema are checked at endpoints and the real roots
of the cubic derivative of squared speed; acceleration is linear, so its endpoint
norms bound the interval. Engineering ceilings are 9 m/s and 8 m/s². These values
are design limits, not measured athlete calibration. Acceleration may change at
knots; the implementation claims C1 velocity continuity, not continuous jerk.

Body roots and ball touch points are separate. A 0.55 m horizontal reach is planned
from local carry/release geometry; boundary cases keep the root inside the pitch.
During control, the ball follows that same body path and contact offset. Tracking,
the lightweight engine observation and fixture exports use the same ball sampler.
Engine observations sample the actual holder root without optional gait/contact
metadata; rendered frames retain all optional source animation fields.
Delayed linked xG and delivered facts remain separate from private physical truth.

Role-specific defensive depths preserve goal cover, midfield screens and forward
outlets near the team's goal. They are tactical engineering heuristics, not a
fixed count of players in the box or a claim of complete professional tactics.

## Optional tracking contract (schema 2.0)

Existing `player.motion.heading`, `speed`, `distance` retain their meanings:
actual velocity direction in world XZ radians (`atan2(dx,-dy)`), metres/source
second, and cumulative metric path distance. New optional fields are:

| Field | Meaning |
|---|---|
| `motion.facing` | Body orientation in world XZ radians, separately bounded at 6 rad/source second. It can differ from travel direction during turning/backpedalling. |
| `motion.gait_cycles` | Cumulative full left+right gait cycles: integral of `v / clamp(0.8 + 0.5*v, 0.8, 4.4)` over source time. |

Both cumulative metrics start at actual entry for a substitute. Endpoint totals
use deterministic adaptive eight-point Gaussian quadrature. Partial values use
bounded monotone cumulative tables described below.
The sampler does not integrate viewer history. In particular, never divide total
distance by the *current* speed-dependent stride length to obtain a gait phase.

`player.contact` is optional and has exactly these fields:

| Field | Meaning |
|---|---|
| `kind` | `control`, `receive`, `release`, `save`, `throw`, `block`, or `challenge`. |
| `effector` | `foot`, `hands`, or `head`. |
| `start_t`, `end_t` | Current physical action interval in source seconds. It is emitted only after its actual start. |
| `target` | `[pitch_x, pitch_y, height]` in metres. Height uses the existing ball ground-clearance reference, not the rendered ball centre or a joint position. For an action, the actual touch point at start; for control, the current ball point. |
| `phase` | Elapsed fraction, 0–1. Release/receive follow-through currently lasts 0.32 source seconds. Control has start=end=current sample time and phase=1. |
| `heading` | World XZ radians toward the physical touch target at touch time. |

The target after release is a historical impact point for follow-through, not a
new ball position. Consumers must not move the ball there or infer a shot outcome.
There is no future recipient, referee result, goal classification or xG field.
Existing frames without these optional fields remain valid.

Developer fixture exports preserve private Hermite nodes separately in
`player-paths.jsonl`; `keyframes.jsonl` alone cannot reconstruct this motion
model. `tracking-20hz.jsonl` contains only sampled delivered frames, never the
complete future path. A regression reloads private paths and compares sampled
frames through control, release and reverse sampling.

## Research boundary

[Khronos glTF Appendix C.5](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#interpolation-cubic-spline)
defines cubic Hermite interpolation with time-scaled tangents; the physical
certificates, gait model and tactical depths here are our engineering choices.
[IFAB Law 15](https://www.theifab.com/laws/latest/the-throw-in/)
requires a throw-in with both hands from behind and over the head. Current source
action labels must be supported by actual source height/contact geometry; a hand
label alone does not prove a legal throw-in or a correct whole-body animation.

Further acceptance still needs rendered body/foot contact, planted-foot world
velocity, turn/collision behavior, professional support/pressing patterns and
visual review. Source certificates do not establish these by themselves.


## Shared family acceptance matrix

P = plausible football pattern; E = engineering choice; L = IFAB rule. Rows are
acceptance targets, not claims that every legal/tactical detail is implemented.
Ordinary source uses the physical planner; legacy named scenarios remain explicit
setup cuts for isolated event/latency tests.

| Family | Initial state | Actors | Ball path | Support (P) | End possession | Events | Forbidden contradiction | Deterministic situation |
|---|---|---|---|---|---|---|---|---|
| Defensive/central/wing build-up | Live controlled ball in own/middle third | Carrier, outlet, nearby presser | Bounded carry or actual release/receipt (E) | Cover, midfield screen, width/outlet layers | Same team until actual turnover | carry/pass | All roles on one x=8 line; root=ball | Low-defence snapshot, both directions |
| Short/through/long pass/cross | Controlled ball; receiver can approach | Passer, actual receiver/interceptor | Setup waits before fixed flight; height by current source (E) | Offer angle, run beyond, retain cover | Actual recipient/control or free ball | pass/recovery/interception | Stretch flight to wait for actor; completed outcome delivered before receipt | Distant H2 cross; ordinary seed 12 touch audit |
| Carry/dribble/turnover/counter | Live control or loose ball | Carrier, challenging defender, support runners | C1 root/control path; explicit challenge/contact (E) | Nearby options; defensive cover and forward outlets | Winner at actual touch; otherwise loose | carry/dribble/tackle | Both bodies at same root; synthetic renderer turnover | Existing isolated dribble outcome cases plus source knot checks |
| Final third/shot/miss/goal/block | Shooter controls at release | Shooter, keeper or actual blocker | Fixed shot flight, then real deflection/rebound | Attacking depth and recovery cover | Save/recovery/out/goal stoppage | shot, separate result, delayed xG, block | Ball changes before action; future result in motion | Distant keeper .60s shot; block/contact/rebound pair |
| Keeper catch/parry/rebound | Incoming shot | Keeper plus rebound contender | Hands at source contact; catch lift or later deflection (E) | Recovery/clearance outlet | Keeper control or actual rebound winner | save/recovery | Save event at different source point; every hand receipt labelled save | Save contact and parry sampling |
| Corner/free kick/throw/goal kick | Stopped ball; awarded restart | Retriever/taker, receiver, opponents | Pickup/carry/placement/stationary setup/release/flight (E) | Options/cover; legal setup separately tested (L) | New possession only on execution | stop/award/taken/set_piece/pass | Award means execution; unmanned dead-ball transfer | Whole retrieval interval; both-direction throw height |
| Penalty/offside/advantage | Relevant private kick/incident snapshot | Kicker/receiver/defenders/referee decision | Reuse encounter/release planner | Rule-constrained setup needed (L) | Actual live/stopped state | offence/decision/whistle/card | RNG offside without geometry; illegal penalty line; card interrupts advantage | Known follow-on gaps below, not PASS |
| Cards/red/sub/drinks | Actual disciplinary or stoppage state | Active roster; outgoing/incoming | Stop/control preserved; no fake play | Vacated role inherited only after entry | Stopped until actual restart | card/sub/drinks/restart | Sent-off/bench actor active; changed initial roster; moving stopped ball | Roster-before/after and snapshot alias regressions |
| Kick-off/half-time/ends | Period boundary and stopped ball | Actual active roster/taker | Reachable setup; physical halftime walk, no sampled reset teleport (E) | Direction changes by period | Execution starts next possession | period/kick-off/whistle | Source time confused with clock; instantaneous side switch | Continuous source knot/direction tests |

[IFAB Law 9](https://www.theifab.com/laws/latest/the-ball-in-and-out-of-play/)
defines referee stoppage and whole-ball boundary crossing. Retrieval transport is
our physical implementation choice, not a rule requiring the taker to fetch it.
[Law 8](https://www.theifab.com/laws/latest/the-start-and-restart-of-play/) and
[Law 13](https://www.theifab.com/laws/latest/free-kicks/) distinguish restart
procedures; a generic decision must not stand in for the actual kick.

Known law-family follow-on (independently reproduced, outside this shared-path
checkpoint): [Law 11](https://www.theifab.com/laws/latest/offside/) needs a frozen
kick snapshot plus actual involvement; current random branch can report a player
behind the ball. [Law 14](https://www.theifab.com/laws/latest/the-penalty-kick/)
needs reachable legal keeper/other-player setup; current ordinary penalty can put
the keeper ahead of the line and defenders close to the mark.
[Law 12](https://www.theifab.com/laws/latest/fouls-and-misconduct/) requires a
sanction following advantage at the next stoppage; the current immediate card
path remains a reproduced follow-on. These are not waived by trajectory tests.

## Review and evidence checkpoint

Independent finite-difference review sampled 600 deterministic random Hermite
segments, accepted 252 and checked 9,828 interior positions: speed <=9.0001 m/s,
acceleration <=8.001 m/s², with pitch bounds. This verifies the certificate, not
full-match causality or legal football.

The first acceleration-only mutation check exposed a weak test (the rejected
long run also exceeded speed). Independent regressions now reject 2m in 1s while
accepting 2m in 1.3s, and bound a slow 90-degree body turn. Separate process-only
mutations to acceleration=80 and turn speed=60 each fail their regression. No
product file was mutated for those review probes.

Shared causality reproductions: a nominal 2.30s cross previously lasted 14.42s;
an ordinary foul had actors 54.97m apart; a stopped ball moved 12m in 1s without
an actor. Current focused checks delay release, stage reachable opposing roots,
and sample actual hands retrieval while public play remains stopped. A first
foul fix still overlapped roots (independent regression failed); the corrected
incident has 1.10m root separation. Full collision/avoidance acceptance remains
open. Contact rounding uses explicit effector identity with centimetre source
canonicalization; it does not reinterpret arbitrary positions as touches.

Current offline evidence (26 October, uncommitted 2.5 checkpoint on verified
`d3a9a8176abb1ce308df34539b969e0d495f7ba6`): affected physics/motion/actions/
contracts/schema/export suite **200 passed in 225.25s**. After outcome-delivery
availability and lightweight observation refinements, focused physics plus the
ordinary action geometry audit **38 passed in 17.85s**. Existing Node suite
**40 passed**, Ruff and whitespace checks passed. Full coverage and review remain
pending; the first full attempt was stopped while computing a full replay to fix
unnecessary gait integration in engine observations, and is not a PASS.

Unprofiled seed-12 measurement, same generated match reused for the acceptance
manifest: generation 7.965s, Tracker initialization 0.236s; 1,000 full frames at
20Hz source timestamps 600..649.95 averaged 2.593ms (p95 4.480ms). Source retained
3,375 ball keys and 33,801 player path nodes, approximately 31.8MB recursively
measured Python source objects; process RSS after sampling was approximately
128.7MB. It did not retain 120,000 rendered frames. All ordinary pass/shot/restart/
save/block/clearance action geometry in that match had real source contacts.
These are local CPU timings and object counts, not browser FPS or network latency.
The ignored receipt `out/physical-motion-profile-final-seed12.json` also contains
representative current event IDs/times/coordinates for browser acceptance after B4.

Pass event source time is the physical kick. Its completion/outside classification
is delivered only after the actual encounter/decision; the existing 0.5..3s feed
latency is now measured after those facts become available. Other event latency
bounds remain unchanged. No ordering is imposed between independent provider
packets after the underlying physical fact exists. The frozen 2.2 fixture remains
checksum-identical; it is not regenerated to obtain these results.


Full-run status at the Draft checkpoint: sessions 40317 and 74547 were interrupted
without a full result. The diagnostic single full-match validator replay for seed
3 passed with coverage in **273.20s** (session 54703, exit 0). A 30s stack was in
source staging; the prior 120s stack was in replay momentum tick, demonstrating
progress rather than proving a deadline loop. No engine scheduling fix is claimed.
Full-suite/coverage on the exact committed head will run in required Ubuntu CI;
local partial coverage must not be treated as that gate. Per-file physics/tracking
coverage and meaningful uncovered branches remain part of review before merge.

The body-path certificate now explicitly rejects outside endpoints and reversed
time, including a case with both inner Bezier controls inside the pitch but an
outside endpoint. Ordinary scheduling already supplies inside, ordered roots;
this guard makes the certificate's boundary claim explicit.

Ball flight remains a deterministic horizontal segment with a parabolic source
height, not a calibrated gravity/spin/drag solver. The body speed/acceleration
certificate does not certify ball flight forces or all-body collision avoidance.


Final focused coverage: **39 passed in 61.40s**; physics 258/264 lines (97.73%)
and 106/114 branches (92.98%). Tracking's focused-only coverage is 85.84% lines /
81.03% branches; its legacy and goalkeeper-substitution paths require the full
suite, and these partial numbers are not a global coverage PASS. Manual uncovered
path review added unreachable-source rejection and an optional-support case where
forcing an intermediate stop would be infeasible; both passed in 0.96s. Full CI
and accumulated technical review on the committed head remain required.


## Partner main synchronization and integral correction (27 October)

Core source head `f5dcb503c3aedd19b2676d58a16f52db2a054920` passed all four checks
in [CI 40386092735](https://github.com/Nadavgo8/Visual-Match-Intelligence/actions/runs/40386092735):
519 Python tests in 1292.82s, 40 Node tests; full coverage 94.53% lines / 90.07%
branches, changed 556/561 lines and 211/220 branches, critical changed 12/12 and
12/12. Parent's independent read-only reviewer gave the scoped core a technical
PASS. This does not cover later integration or imply B4/visual/law acceptance.

Merged partner main `ab53c72834a1d09f2c9c784ae4817cf861948951` without conflicts,
keeping the D2 model/agent work, marker/chat behavior and seed-2 demo default.
The story lock is a real unresolved integration failure: at merge head 04175f0, source 2.5 seed 2 was
4-0 (Dumont 9:16, 28:07; Ferreira 56:15; Ibsen 80:43), while the newly approved
2.4 demo requires 2-1 and its exact VAR-penalty narrative. The two demo tests
returned 1 passed / 1 failed in 46.15s. No story assertion, default seed or frozen
benchmark was weakened. Story changes require the user's decision; source 2.4
motion cannot silently replace the physical upgrade to obtain this narrative.

Independent review then found that recomputing Gauss nodes over each requested
partial interval can decrease distance and gait cycles on a certified strong
turn. Candidate 96 of random seed 20261027 decreases distance 5.146904455 to
5.146286783; the new independent monotonicity regression failed before the fix.

The correction separates accurate canonical endpoint integration from lazily
built partial tables. Each positive cell uses a cumulative Hermite polynomial
whose endpoint slopes are limited to [0, 3*cell mean]; its derivative is
nonnegative throughout. Quarter/midpoint integral comparisons adaptively split
cells, with depth capped at eight (256 cells). Both LRU caches hold at most 256
entries, keyed only by local curve geometry and duration. They never contain a
viewer's last sample or carry accumulated viewer state. Exact endpoint totals
match cached source-node totals, including after seek and cache eviction.
The interpolation is a controlled numerical approximation, not a new exact
analytic arc-length claim.

Four initial regression/accuracy tests passed in 7.97s; the deterministic
800-candidate review probe accepted 310 certified curves and checked 62,000
successive samples without a backwards metric. Dense independent measurements
use differences of sampled positions (not the velocity helper) and check both
distance and cadence against 3e-5 tolerance on strong turns/reversals. The whole
physical regression file, including bounded-cache/eviction and segment-boundary
checks, passed 44 tests in 26.21s. New full CI remains required after integration.


## Follow-up contact review and performance limit

A reproduced ordinary handball still had only a foot challenge at ground level.
The source now selects the offence before staging: a real attempted chip leaves
the victim's foot, flies 0.45s to a 1.1m hand contact, and deflects as a free ball
for 0.3s before the whistle. The outfield defender never gets controlled hand
possession. Pass completion is reported only after the encounter, and the offence
timestamp remains the actual hand contact. Its real impact position determines
whether the restart is a penalty, including when the chip crosses the penalty-area
boundary in either direction. Renderer labels are not used to create this action.

The first boundary assertion incorrectly used the deliberately noisy operator
location (88.4m) to check an exact 89m physical impact. It now asserts the exact
source impact and the linked penalty decision; feed logging noise remains intact.
All 49 focused physical regressions passed in 19.07s, including both handball
orientations, source release/height/loose-ball progression, box-boundary decisions,
adaptive-cell boundaries and a fast run crossing the stride-length cap. The dense
reference tolerance remains 3e-5; no test/CI threshold was lowered.

Numerical optimization replaces repeated velocity-object evaluation with cached
polynomial coefficients, uses an exact rest-to-rest chord endpoint, splits the
cadence integral at known 7.2m/s stride-cap crossings, and reuses positive dyadic
Simpson samples when constructing partial cells. Canonical endpoint integration
remains adaptive Gauss. This improves correctness cost, but current cold-cache
performance is still an explicit P2: seed12 generation 32.33s, 1,000 rendered
frames mean 10.79ms, p95 8.46ms, p99 298.22ms, maximum 738.50ms. Rare synchronous
partial-table construction exceeds a 20Hz frame budget. Both caches stayed at
256 entries, largest observed table 93 cells, source objects approximately31MB,
process RSS approximately118MB, with no audited action geometry failures. Receipt:
`out/physical-motion-profile-monotone-final-seed12.json` (ignored, uncommitted
checkpoint measurement). An earlier slower measurement was 67.65s generation;
one coordinated profile was stopped for the parent's CPU window and is incomplete.

This checkpoint is not merge-ready: cold-cache spikes and the unresolved approved
demo narrative remain open. The previous head's full green CI does not verify
these new changes. A new full unchanged CI suite and accumulated review are still
required; no independent source merge or B4/visual acceptance is claimed.

After the handball correction, the selected demo/chat/action suites returned
65 passed, one failed and eight deselected in 106.47s. The sole failure is still
the unchanged seed-2 story assertion: this checkpoint produces 2-0, with Dumont's
9:16/28:07 goals and Marsh's 70:15 goal overturned at 71:57. These facts describe
the unapproved current simulation, not a replacement approved narrative. All 51
Node tests passed in 1.70s; Ruff and `git diff --check` passed. The local focused
command excluded the eight existing replay-heavy chat cases, which remain in the
unchanged full CI gate. No complete current-head Python PASS is claimed.
