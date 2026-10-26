# D1 source motion audit and implementation

26 October 2026. Initial base: `26d1ce3`, synchronized to verified `fb61a8e`;
generator changes `2.3.0` → `2.4.0`;
record schema remains backward-compatible `2.0`. This is implementation evidence,
not visual acceptance or a claim that every football family is fully simulated.

## Reproduced cause and focused correction

On generator 2.3, seed 12, sampling the 50 ms immediately before each source knot
found 1,021 player displacements above 15 m/s. The largest was 1,855.2 m/s at
`t=3009.89`, when the tracking fallback mirrored the formation at half-time.
The kick-off taker also jumped 12.61 m in the final 50 ms before `t=2.29`.
`Tracker.frame` reconstructed a moving formation independently at every sample,
then pulled previous/next holders to the ball. Passing tests of event counts and
holder coincidence did not test continuity around those boundaries.

Generator 2.4 freezes complete metric player paths at source knots. Actual touches
and explicit dribble encounters are hard anchors. Other positions are targets
from role, ball location and possession phase: width in possession, connected
midfield support underneath the ball, compact ball-side cover out of possession.
Each movement must fit both the next contact's reachability disk and the previous
position's velocity disk. The 9 m/s ceiling is an engineering bound, not a claim
that this is a calibrated biomechanics or tactical model. Impossible contacts
raise an error; no renderer speed clamp can repair them.

Restarts now have dead-ball retrieval, a stationary setup interval, release,
flight and a different player's touch before open play. This fixes the thrower
and kick-off/free-kick/goal-kick taker immediately carrying their own restart.
The seed-12 throw-in at `66.98` previously still reported taker A2 controlling
the ball at `67.08`. The stopped ball at `314.69` previously drifted more than
one metre in 0.5 seconds toward its future restart position. Corner crosses also
previously emitted their pass at reception and had zero flight height.

Turnovers and second balls now stage the recovering actor's actual contact,
rather than moving an arbitrary future holder onto the next ball keyframe.
Keeper possession retains the save's lateral coordinate instead of moving from
the save to midfield-side `y=34` in the next carry. A chosen live post rebound
remains in play and is recovered; it no longer automatically produces a goal kick.

## Producer/consumer contract and determinism

Ordinary matches advertise `meta.motion_model = "source-paths-1"`. Their delivered
tracking players optionally contain `motion: {heading, speed, distance}`:
heading is radians in world XZ (`atan2(dx,-dy)`), speed is metres/source-second,
and distance is cumulative source path metres. `Tracker` computes these from
immutable path segments, never from which frames the viewer previously requested.
Renderers may use them for exact pause/seek gait; they must interpolate distance
when interpolating two delivered positions. Physical paths do not expose the
future event feed, referee outcome or delayed analytics.

Old frames without `motion` remain valid. Short event/latency scenarios retain
their documented setup cuts and do not claim this continuous-path contract.
The immutable annotated `demo-v2.2.json.gz` benchmark and checksum are unchanged.
xG remains a separately delivered, linked generator record; no TV xG is added.
No model, provider, service, paid quota or browser state is involved.

A separate P1 export regression found that substitution mutated the bench
player's base coordinates before exporting initial public metadata. A bench CM
could therefore disclose their future LB slot before substitution. Initial bases
are now snapshotted with initial roles; tracking privately inherits the actual
occupied slot from the explicit substitution. The regression checks both public
metadata and the before/after active roster.

## Practical family matrix

`L` means law; `P` means plausible coaching pattern; `E` means an engineering
choice. The scenario column is a deterministic test recipe, not a claim that
every recipe is already a named scenario API. Shared path, roster and delivery
checks apply to every row. Full-match tests are supplemented by the focused
regressions listed below; coverage of a family is not proof of every variant.

| Family | Initial state | Actors | Ball path | Support | End possession | Events | Forbidden contradiction | Deterministic recipe |
|---|---|---|---|---|---|---|---|---|
| 1 Build-up defence (P) | Controlled own third | GK/CB, press and cover | Short release or carry | Width, safe backward option | Same team unless lost | Pass/carry | Everyone rushes into box; GK attack boost | Own-third carrier, press from centre |
| 2 Centre progression (P) | Controlled middle third | Holder, receiver, nearest presser | Pass into reachable space | Staggered midfield support | Receiver or explicit interception | Pass/interception | Receiver teleports from formation | Centre pass; sample both contact boundaries |
| 3 Wing progression/cross (P) | Wide final third | Winger, target, marker, GK | Driven/lofted delivery | Near/far options and deeper cover | Contact, loose or out | Cross/pass, next action | Fixed box headcount; flat high cross | Corner-flight regression plus wide pass |
| 4 Short pass (E/P) | Active control | Two different players | Release → ground flight → receive | Local passing angle | Receiver, same possession | Pass | Ball remains controlled in flight | Four restart-release regressions |
| 5 Through/long ball (L/P) | Forward option | Passer, timed runner, defenders | Reachable flight; height if lofted | Runner and covering defender | Receive, interception or loose | Pass, optional offside | Decide offside from reception position alone | Forward ball, compare kick-time defensive line |
| 6 Carry/dribble (P) | Active outfield holder | Carrier and distinct defender | Short touches/duel | Nearby release; others cover | Retained, lost, loose or stopped | Carry/dribble/foul | Defender remote; unresolved means controlled | Existing four dribble outcomes, both directions |
| 7 Free ball/turnover/counter (P) | Loose or opponent gain | Recoverer, pressure, outlets | Loose interval → real recovery | Advance after gain; recover after loss | New team only on control | Ball loose/recovery/interception | Possession flips before contact | Seeds 3/8/15 previous-touch reachability |
| 8 Final-third shot/block (P) | Attacker in shooting range | Shooter, blocker, GK | Strike → contact → result | Follow-up and defensive cover | Loose, saved or out | Shot/result/block | Blocker absent; outcome at shot creation | Force blocked result; verify contact separately |
| 9 Miss/post/goal (L/E) | Shot in flight | Shooter/GK, follow-up | Miss crosses line; post can rebound; goal crosses goal plane | Follow rebound; stop after goal | Loose/recovered or stopped | Result, recovery or stop | Every post is goal kick; goal before crossing | Live post-rebound regression |
| 10 Catch/parry/rebound (P/L) | On-target shot | GK and nearby follow-up actors | Catch retains; parry creates loose path | React to loose ball | GK only for retention | Save/result/recovery | Parry labelled controlled catch | Save subtype fixture with repeat shot |
| 11 Corner (L/P) | Award, ball outside play | Taker, targets, defenders/GK | Stationary corner → lofted release → contact | Runs plus rest defence | Contact/clearance/loose | Award/taken/pass/clearance | Pass logged at arrival; same taker carries | Corner release/height regression |
| 12 Direct/indirect FK (L) | Whistle and award | Taker, receivers, legal wall | Stationary → kick; indirect requires other touch for goal | Options, defensive spacing | Receive/shot/loose | Decision/award/taken | Offside restart treated as direct scoring FK | Explicit indirect touch-before-goal recipe |
| 13 Penalty (L) | Award, ball stationary on mark | Identified taker, GK on line; others outside box/behind mark | Signal, then forward strike | Enter only after kick | Save/rebound or stop | Award/taken/shot/result | Signal itself is the kick; keeper starts metres off line | Penalty timing and encroachment recipe |
| 14 Throw-in/goal kick (L) | Ball out, correct team awarded | Taker and different receiver | Throw overhead into field; goal kick kicked/moves | Legal opponent distance | Second player's control | Award/taken/pass | Double touch; goalkeeper catches direct teammate throw | Restart release tests, both sides |
| 15 Offence/advantage/offside/whistle (L) | Live play | Offender/victim/referee | Continue for advantage or stop at whistle | Maintain phase until stopped | No forced turnover for advantage | Foul/offside/whistle/decision | Audio whistle contains invented reason; position alone is offside offence | Delay factual decision beyond whistle; failed advantage |
| 16 Yellow/red (L) | Offence and sanction | Identified offender | Current phase or stopped ball | Re-form after dismissal | Roster loses sent-off player | Card linked to offence | Red player returns or is replaced | Dismiss before next frame, sample both sides |
| 17 Substitution/drinks (L/E) | Actual stoppage, restart pending | Off/on actors; active squad | Stationary wait then original restart | Substitute inherits occupied role | Original award survives break | Sub/drinks/taken | 23 active actors; break silently takes restart | Existing drinks/sub/GK-replacement tests |
| 18 Kick-off/half/full-time (L/E) | Centre set or period ending | Active lineups, referee | Kick-off release; dead ball at period end | Own halves at kick; walk/change ends during interval | New control or stopped | Period/taken/whistle | Half-time formation mirror teleport; moving after full-time | Every-knot continuity including half-time |

## Primary sources and their implementation implications

Current IFAB pages were checked as 2026/27 on 26 October. Laws are constraints;
coaching sessions are examples, not mandatory formations.

- [IFAB Law 9](https://www.theifab.com/laws/latest/the-ball-in-and-out-of-play/):
  full boundary crossing/referee stop ends live play; a rebound which remains
  inside stays live. [Law 11](https://www.theifab.com/laws/latest/offside/):
  assess relevant position at a teammate's touch and involvement; offside gives
  an indirect free kick. No direct offside offence from throw-in, corner or goal kick.
- [Law 8](https://www.theifab.com/laws/latest/the-start-and-restart-of-play/),
  [Law 13](https://www.theifab.com/laws/latest/free-kicks/),
  [Law 14](https://www.theifab.com/laws/latest/the-penalty-kick/),
  [Law 15](https://www.theifab.com/laws/latest/the-throw-in/),
  [Law 16](https://www.theifab.com/laws/latest/the-goal-kick/),
  [Law 17](https://www.theifab.com/laws/latest/the-corner-kick/): separate award,
  setup, signal and actual legal execution; do not let a taker dribble a restart
  before another player touches it. Restart position/distance constraints depend
  on kind; ordinary free-kick distance is 9.15 m, throw-in opponents 2 m.
- [Law 3](https://www.theifab.com/laws/latest/the-players/): roster changes must
  preserve at most eleven per side and a goalkeeper; a player sent off after
  kick-off cannot be replaced. [Law 5](https://www.theifab.com/laws/latest/the-referee/)
  distinguishes advantage from a stop. [Law 12](https://www.theifab.com/laws/latest/fouls-and-misconduct/)
  distinguishes misconduct/sanctions and keeper possession; do not reuse the old
  six-second keeper-hold rule (current handling limit is eight seconds, then corner).
- FIFA's [possession and switching session](https://www.fifatrainingcentre.com/media/native/test/FIFA_Session_Plan_Flores.pdf)
  supports width, depth and passing triangles; [press and cover session](https://www.fifatrainingcentre.com/en/practice/talent-coach-programme/press-and-regain/3v3-plus-3-possession-game-pressing-and-switching-play.php)
  supports compact, staggered cover. The source support heuristic uses these
  broad patterns without turning coaching drills into laws or fixed box counts.
- FIFA's [goalkeeper intervention taxonomy](https://www.fifatrainingcentre.com/en/resources-tools/football-language/goalkeeping/out-of-possession/goal-prevention/intervention-type/index.php)
  distinguishes retention, deflection and follow-up retention. A single generic
  save marker cannot prove that these physical variants are implemented.
- [SkillCorner original format documentation](https://github.com/skillcorner/opendata)
  distinguishes metric XY tracking, detected/extrapolated positions, body pose
  and dynamic events. This implementation stays synthetic and copies no match data.
  [Three.js AnimationMixer](https://threejs.org/docs/pages/AnimationMixer.html)
  documents absolute time sampling; gait/clip time should likewise come from
  source time/distance for seek reproducibility.

## Boundaries and remaining acceptance

This patch corrects the reproduced source motion/restart failures, not every law
or animation variant in the matrix. In particular, generic free-kick records
still need explicit direct/indirect semantics, kick-off/penalty formation legality
needs separate staging acceptance, offside requires kick-time geometry rather
than random classification, and save/block/header body mechanics need distinct
physical contact evidence. Acceleration, collisions and tactical quality are
not calibrated by the 9 m/s ceiling. Visual acceptance remains PR #12 work.

Measured remaining phase-2 gaps, source 2.4 seed 12: sampling source velocity
50 ms either side of every knot produced a maximum velocity change divided by
0.1 s of **179.9999 m/s²** at `4659.92`, H19. Piecewise-linear paths therefore
do not yet enforce a physical acceleration or turn-rate bound. Across **2,210**
controlled contact knots the holder's planar ball/root offset was **0.0 m**
(minimum and maximum). Explicit body/foot contact offsets are still needed in
source truth; a renderer root shift would conceal the problem. Stationary heading
does retain the last nonzero source-path heading, independently of viewer history.

Crowd rendering must consume the same delivered `C` as the atmosphere meter;
`A=0.8C+0.2T` does not mean attack makes the physical crowd louder. Missing crowd
is unavailable, never measured silence. Run changes reset smoothing; repeated
paused time must repeat the pose; a seek must reproduce source phase. These are
consumer acceptance checks, not additional generator emotion labels or invented
causes for crowd reactions.

Validation evidence is recorded below after actual execution. No full-suite or
visual PASS is implied by the implementation description.

## Executed validation checkpoint

- Baseline source motion/actions: **53 passed**.
- Initial restart/continuity/setup regressions: **6 failed, 4 passed** before fixes.
- Corner release/flight regression failed before the corner correction; post
  rebound regression failed before the live-ball correction.
- Focused source/schema/scenario block before the final P1 export fix:
  **166 passed**. Final focused and 100-seed checks are recorded in the commit
  handoff, not inferred from this earlier run.
- Stationary-heading regression: **1 failed → 1 passed**.
- Initial-roster regression reproduced `(28,58)` leaking instead of `(0,0)`.
- Final core command after the P1 fix: `python -B -m pytest
  tests/test_generator_motion_v2.py tests/test_full_match_actions.py -q
  -p no:cacheprovider --tb=short`: **74 passed in 27.18 s**. Environment:
  `VMI_OFFLINE=1`, `VMI_WARM_DEMO=0`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`;
  interpreter is the existing `vmi-quality-baseline-20261022` Python environment.
- The final standalone 100-seed probe **completed: 100 seeds PASS in 423.39 s**,
  mean **1040.59 passes/match**, tool session `32113`, exit `0`. Executable source
  was identical to `353bb35`; the commit checkpoint originally recorded progress
  through seed 60. It checks event contracts/links, every source segment's per-player
  9 m/s bound, separate shot outcomes/xG and unexposed bench bases. The agent-verified
  receipt and reproduction script are saved locally under
  `out/motion-source-100-seeds-353bb35.{md,py}`; no rerun was needed to persist them.
- Existing frontend suite on synchronized main: **37 passed**. This does not
  validate the unmerged 3D renderer.
- `ruff` and `git diff --check` passed at this checkpoint. Frozen benchmark SHA256
  remains `04d9e2119d9adf5a56ed87cb6cf1d6cd5e960160afea8dc5c7d1368d1e351572`.
- Two broad/full-suite attempts were interrupted during iteration; neither is
  recorded as PASS. Parent review/CI and merged-main B4 remain required.

Review improvement: an event-count/holder-coincidence PASS must be accompanied
by checks on both sides of every source knot, reachability from the previous
touch, and initial metadata before/after actual substitutions. A published event's
rounded source timestamp is the roster boundary; private unrounded simulator
time must not be used as a consumer's event-time oracle.

## PR #30 CI fixture regressions

[CI run 40291600377](https://github.com/Nadavgo8/Visual-Match-Intelligence/actions/runs/40291600377)
on `353bb35` completed **472 passed, 3 failed in 561.91 s**. These failures are
not recorded as a technical PASS:

1. The valid-agent-draft test asserted that the first scorer was Reyes, while
   constructing its facts from the evolving demo seed. The validator correctly
   rejected that invented scorer in generator 2.4. Its goal-pack fixture now uses
   the existing checksum-pinned 2.2 benchmark, whose first scorer is Reyes.
2. The asynchronous snapshot test independently asserted `25:00 score 1-0`,
   but seed 12 now produces `0-1` then. The commentary fixture now uses that same
   annotated benchmark; the exact frozen-answer, timeout, injection and validation
   assertions remain unchanged. Normal live-room tests still use the current generator.
3. The VAR feed regression built a real continuous `_Sim` kickoff, then placed
   H9 at `(94,34)` instantaneously. Source validation correctly rejected the
   unreachable contact at `t=5.5`. This isolated feed/VAR test now uses the existing
   `_Segment` scripted fixture with documented setup cuts and explicit final delivery
   padding. Real generated matches retain the same 9 m/s bound and its regressions.

No agent, validator, engine or generator production behavior was changed for these
CI fixes. The annotated goal-pack fixture advances only to `1200 s`, after the
fixed first goal, instead of replaying an unnecessary full match.

The three reported regressions plus `test_generator_motion_v2.py` and
`test_full_match_actions.py` completed **77 passed in 10.92 s** after the fixture
repairs, with `-ra --strict-markers --strict-config -p no:cacheprovider -W error`.
`ruff check vmi tests tools` and `git diff --check` passed. The initial sandboxed
attempt stalled at Windows asyncio's loopback socketpair initialization
(`socket.accept`, confirmed by a 30-second faulthandler stack). The same offline
command completed after authorized sandbox escalation; this was not a product
failure or a relaxed assertion. The prior default-sandbox attempts were interrupted
and do not count as PASS. Fresh full CI and integrated-main B4 remain required.

Future tests with independently annotated score/name facts must use a pinned or
explicit fixture; seed reproducibility is versioned, not an unchanging narrative.

## Verified main synchronization (26 October)

Merged main `8df01f18cb9c8e28dd1c91f002f85959ec25c5fd` after parent confirmed
its B4 run `40299302501`; merge tree `b4e1e9cbe8713fc6bc938f7f17082a3ba7b4e983`
had no conflicts. The incoming change fixes companion measurement reset behavior;
it does not change generator source or the pinned benchmark.

Post-sync validation used one local Python process, with the same offline
environment and authorized Windows sandbox escalation described above:

```text
python -B -u -m pytest tests/test_agents.py::test_workflow_uses_a_valid_agent_draft tests/test_commentary_agents.py::test_answer_is_built_from_the_moment_the_question_was_asked tests/test_engine.py::test_overturned_penalty_is_detected_from_the_feed tests/test_generator_motion_v2.py tests/test_full_match_actions.py -q -ra --strict-markers --strict-config -p no:cacheprovider -W error --tb=short
77 passed in 12.80 s
node --test tests/web/*.test.mjs
40 passed, 0 failed
python -B -m ruff check vmi tests tools
All checks passed!
git diff --check
PASS
```

No local full-suite or 100-seed rerun was requested for this synchronization.
Fresh full CI, parent technical review and post-merge B4 remain pending; these
focused checks do not establish complete motion acceptance. Local test processes
ended before the user's pending manual performance benchmark.
