# D1-04 — deterministic 2D presentation

The match renderer draws original procedural artwork: a metric 105 × 68 pitch,
distinct numbered kits (away stripe and separate goalkeeper kits), goal nets and a
source-height ball with a restrained size change and ground shadow. It needs no
images, downloaded fonts, CDN, build step or purchased assets.

`match-renderer.mjs` owns Canvas drawing. `match-motion.mjs` owns bounded source
sampling. Accessibility signals remain separate DOM elements, to be replaced in
D1-05. The background is cached and refreshed on resize; device pixel ratio is
capped at two. Pitch projection preserves the same scale on both axes.

While playing, two delivered frames are interpolated with one packet of buffering,
capped at 250 ms of wall time. Positions never extrapolate beyond the newest
received frame. Sampling depends on simulation speed and elapsed time, not the
number of animation callbacks. Pausing uses the source endpoint and freezes;
resume/speed changes discard old interpolation history. Disconnect freezes the
current sampled frame. Repeated paused packets cannot restart animation.

Seek/chapter/load clears the buffer and ignores packets until the ordered state
reply. State includes the already public current match identity; foreign matches,
out-of-order samples, invalid coordinates, duplicate players and excessive rosters
are rejected. Substitutions change at their source endpoint rather than blending
two identities. If D2 supplies `run_id`, it is checked; this task does not invent or
claim the D2 transport's run IDs, reconnection or host authorization.

Node's dependency-free tests cover independently calculated position/height
midpoints, endpoint clamping, refresh independence, pause/resume, speed, seek,
identity changes, malformed packets, roster changes and bounded buffering. The API
test verifies that state/frame identities agree and change when the seed changes.

```powershell
node --test tests/web/*.test.mjs
python -m pytest tests -q -ra --strict-markers --strict-config -p no:cacheprovider -W error
```

Live FPS appears only among presenter controls. Actual viewport measurements and
visual scenarios belong in the PR evidence; a unit test is not an FPS claim. The
full stage-4 load/soak/performance gate remains separate.

## Integration with the approved accessibility layout

D1-05 was implemented independently from verified main and merged as PR #8.
D1-04 now integrates that main rather than rebuilding its layout. `MatchScreen`
composes the source frame buffer and one-marker state so seek, match/run changes
and remote jumps clear both layers together. Six integration cases protect that
boundary, including invalid frames that must not advance symbol time and paused
markers that must expire after a football stoppage resumes clock advancement.
The source renderer retains its metric projection, kits and height; the reviewed
edge rails, compact score bug, circular symbols and closed presenter tools remain.

After integration, 184 Python tests passed in 64.39s and 28 Node tests passed before
the integration commit. The browser showed the combined design with no JS errors.
The foreground FPS requirement is still **NOT VERIFIED**: this session observes
1 FPS with approximately 0.4–1.3 ms per draw. Neither a fast draw duration nor green
unit tests count as a 30 FPS measurement. PR #7 remains Draft; final-SHA evidence
will be recorded there, and it must not merge until this requirement is verified.
