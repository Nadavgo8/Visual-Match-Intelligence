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
