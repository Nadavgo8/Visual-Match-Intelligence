# D1-03 — Atmosphere and momentum

The default meter is `A = 0.8 × C + 0.2 × T`. `C` is the mean of the latest three consecutive valid one-second crowd readings. `T` is conservative controlled possession: 0 without a detected attack, 0.3 within six metres outside the opponent's box and its width, 0.65 inside the box, and 1 inside the six-yard box. These are interface design rules, not calibrated danger/xG estimates or emotion measurements.

Both surfaces consume one meter payload and the same turquoise-to-amber presentation function. A valid silent crowd is 0; it is not amplified. With silence, the attack contributes at most 0.2. An unavailable crowd makes the combined value null, with `available=false`, rather than inventing a zero reading. The UI uses a labelled neutral presentation and a color transition.

## Input and timing rules

- Tracking carries the current `period`, active player roles and position/height, and separate `quality.sample_t` and `possession.sample_t` timestamps. Roles are sampled at the current simulation time, including emergency goalkeeper substitutions; initial metadata is not changed by future roles.
- A controlled possession must identify an active player and team, and tracking, measurement and possession must each be no more than **500 ms old, inclusive**. Missing, future or unreliable data cannot light the attack component.
- Moving upward to a tier requires **300 ms of observed stability** in the same possession/holder/team. Repeated copies of a single packet do not prove that stability. A gap exceeding 500 ms restarts observation.
- Goalkeeper possession, a stoppage, loss of control and unavailable data reset the attack component immediately. A lower tier is applied immediately; returning upward needs stability again. Direction changes with the observed current period.
- Quality status must be `measured` and confidence at least 0.8. This is an explicit engineering threshold for these synthetic inputs, not a calibrated detector claim. Crowd freshness is at most three seconds for the one-second source; missing/invalid readings break the smoothing sequence.
- Delivered stops and control-loss evidence reset the meter in the same ingest call. Meter expiry deadlines run even without another input packet. A one-microsecond scheduling offset preserves the inclusive 500 ms boundary. Polling expiry does not add another possession-time sample.
- `xg` and successful dribbles add no independent bonus. A drinks break remains out of play until the linked restart executes.

`Tracker.observation()` provides the same current ball, possession and quality as the rendered frame with only its active holder. Replay requests these observations lazily at 20 Hz and merges them with delivered events. It does not store a full match of tracking frames. The engine rejects a record whose occurrence/delivery time is still in the future at the requested snapshot. Static data exports remain developer inspection tools, not agent tools.

## Explicit crowd-only mode

The default never silently changes weights when tracking is missing: `T=0`, so the known crowd contributes `0.8 × C`. A separately selected `crowd_only` mode uses `A=C` and reports that mode in the payload and UI label. Select it explicitly with `Replay(match, atmosphere_mode="crowd_only")` or `VMI_ATMOSPHERE_MODE=crowd_only` on the local server. Unknown modes fail rather than falling back. No provider/runtime choice is made.

## Momentum and deadlines

The independent seven-minute momentum formula stays 40% possession, 30% valid key passes and 30% valid shots, with the existing +1 smoothing. All consumers use the same result. Possession time is sampled once per second from fresh delivered tracking, including goalkeeper possession, and excludes stopped/unknown intervals. The window includes its lower time boundary. Neutral fallback is marked `possession_available=false`; explanations do not describe that fallback as measured 50% possession.

Review also reproduced a pre-existing final-summary defect: an analysis due at a fractional second could fall after the last integer tick and disappear. Replay now releases analysis at its actual simulation deadline, without another possession tick. Delivered events at the same time are processed first, so a cancellation can still suppress queued goal commentary. The regression failed before the fix and passes afterward.

## Verification and scope

Python tests cover independently calculated 80/20 examples, region boundaries, 299/300/301 ms, 499/500/501 ms, independent sample ages, keeper/defence, direction, jitter, missing inputs, recovery, quiet versus missing crowd, explicit mode, stale-data expiry, seven-minute boundaries and fractional final deadlines. Node's built-in test runner verifies percentages, palette values, malformed/unavailable input and mode labels without npm dependencies:

```powershell
python -m pytest tests -q -ra --strict-markers --strict-config -p no:cacheprovider -W error
node --test tests/web/atmosphere.test.mjs
```

Use the isolated environment and dedicated pytest temp root recorded in the handoff for this machine. Generator version is now `2.2.0` because the tracking projection gained delivered-time role/quality fields; wire schema stays `2.0`. D1-04 still owns the polished 2D rendering/FPS checks and D1-05 the physical edge bars, one active marker and presenter separation. No stage performance/soak gate or CI coverage target is claimed by this task.
