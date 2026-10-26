# D1 performance isolation — 26 October 2026

## Latest result — manual protocol 2

The user supplied the complete protocol-2 result recorded at **09:46:05 UTC**.
Same reported viewport **2048×852**, CSS/buffer **1240×697**, High/Broadcast,
DPR .9375 / buffer ratio 1, Chrome155 / Intel Iris Plus D3D11, seed12
generator2.3, source600–630. All three stages remained visible and focused;
no visibility changes were recorded.

| Stage | Duration / samples | FPS submissions | Frame p95 / max | CPU submission mean |
|---|---|---:|---:|---:|
| Light animation | 20.0159s / 1202 | 60.05 | 17 / 20ms | .083ms |
| Minimal WebGL | 20.0161s / 1202 | 60.05 | 17 / 19.7ms | .293ms |
| Full local replay | 20.0159s / 1036 | **51.76** | **33.3 / 83.4ms** | **5.921ms** |

Full source advanced **603.0304→623.0297**, with1036 distinct samples.
CPU means: source interpolation .043ms, overlay .017ms, pose .056ms,
athlete animation .958ms, Three.js submission4.451ms, remaining camera/crowd/
ball .339ms. Scene counters remained87calls /1,469,498triangles /36geometries /
49textures. CPU submission is not GPU completion; a rare83.4ms frame remains
visible in the evidence rather than filtered out.

**Local High drawing exceeds30FPS average in this manual run.** This is not
a claimed optimization speedup from the automated1Hz run: execution conditions
differed, and no scene quality or rendering algorithm changed between them.
Both manual controls are healthy, so the earlier shared1Hz ceiling is not an
intrinsic limit of this browser/GPU under manual operation. Its exact automatic
scheduling cause remains unproven. CPU throttling, OS power saving, remote
sharing and external load remain unverified, not guessed.

The full original JSON is in the user's reply. A clearly labelled transcription
of its summary is saved in `out/visual-reference-review/performance-manual-20261026.json`.
**Presented-frame/DevTools and live TV/companion acceptance remain open.**
The existing TV now has a separate Start live performance test under Presenter
tools: it seeks the current seed to600s, plays1x, warms3s, measures20s, records
accepted WebSocket rates/callback CPU separately, stores a copyable result and
pauses. It does not infer network transit latency or companion synchronization
from render cadence. Do not repeat the three controls to obtain this final
transport-inclusive measurement.

The live capture checks the same 20s window for source and accepted tracking
delivery, including its two boundaries. Gaps over500ms, source regression,
missing source time or source/receipt drift over500ms invalidate it. This is a
freshness check, not a one-way network-latency measurement. Warmup messages do
not inflate reported throughput. A1Hz render loop with healthy20Hz transport
remains a valid LOW-FPS result; a50Hz loop redrawing a frozen source fails.
Source observation duration is recorded separately from render duration to
avoid mistaking a slow first interval for a stopped clock.

Review: Sol6.1 High reproduced a stale scene passing after one late clock jump,
and normal1Hz playback falsely failing the old endpoint comparison. Regression
tests were run red before the fixes (four failures including the window-scope
assertion), then green. A real TV-entrypoint harness verifies one animation
chain, seek/speed/play ordering, old-run rejection, same-window counts, copyable
failure and retry. These are measurement fixes; no actors, crowd states,
resolution or rendering quality were removed or reduced.

Live integration smoke on generator2.4 / PR30-verified source: same Chrome
viewport2048×852, CSS/buffer1337×752, High/Broadcast,22actors,87calls and
1,469,498triangles. A quiet20.316s controlled capture recorded0.98445FPS,
source604.68→623.98, rendered-source drift12.4ms, accepted tracking16.76Hz,
p95receipt68.1ms /max85ms, callback CPU mean.228ms and render-submit CPU
mean10.37ms. This is a valid measurement of LOW controlled cadence, not30FPS
acceptance. It is not compared as an optimization with the smaller local
benchmark. Raw receipt: `out/visual-reference-review/performance-live-controlled-20261026.json`.
After automatic pause, TV and companion both showed10:24,0–1, atmosphere29%
and home momentum41%. This confirms the replacement snapshot agrees; it does
not prove ongoing companion latency throughout capture. One separate manual
live capture has been requested in room`quality-live-final`, with its companion
already connected. Local heavy tests remain stopped during that user window.

Manual UX repair: the user could not find Start because Presenter tools was
collapsed below the match. Adding `&performance=live` opens that developer
panel. Start now scrolls the match into view; completion scrolls to Copy only
after measurement. At least95% of the canvas must be inside the viewport,
in addition to document visibility/focus. This avoids accepting a mostly
offscreen game just because its controls were visible. The earlier controlled
smoke predates this extra visibility gate and remains diagnostic evidence.

Source-consumer integration now reads generator2.4's optional heading, speed
and cumulative distance; source gait matches direct/reverse seek and20/60Hz
sampling. This does not yet make the entire rig pose seek-identical: legacy
contact poses still depend on adjacent observations, and source acceleration
and foot/ball contact geometry remain a separate physical-motion phase.

## Protocol and one-page manual fallback

Open **http://127.0.0.1:17761/static/performance.html** and press
**Start performance test**. Keep that page visible and focused without
interaction for about 70 seconds. It runs these stages sequentially, at the
same CSS and drawing-buffer size, with three seconds of warmup and a separate
twenty-second window for each:

1. A lightly animated 2D canvas.
2. One moving WebGL cube using the vendored Three.js renderer.
3. The actual High/Broadcast VMI 3D renderer, full active roster, crowd and
   accessibility overlay, driven by a pinned local replay.

Copy or download the result using the page buttons. It also saves the last
result locally in this browser, without transmitting it. A hidden page, lost
focus, resize or DPR change invalidates the session immediately, including
transient changes between callbacks. A single rAF chain owns the run; repeated
Start presses cannot create another chain. Errors release stage resources and
permit a fresh attempt. Unsupported long-task observation is explicit.

The source fixture is seed 12, generator **2.3.0**, source seconds **600–630**,
601 samples at 20Hz. SHA256:
`14d3f73aca88d78e8151fdb65d7c27ad42a916d38a77950a1848e668706ae446`.
Regenerate deliberately with `python -m scripts.export_performance_fixture
web/diagnostics/performance-replay.json --seed 12 --start 600 --duration 30`.
Changing generator version changes the baseline; record that rather than
comparing different trajectories as though only rendering changed.

This is **drawing isolation**, not a transport or full-product acceptance test.
The local replay prevents server scheduling or network stalls from changing
the diagnostic's source clock. The live TV/companion stream still needs its
own final acceptance measurement.

## Matched-condition run

Run completed **2026-10-26 09:20:22 UTC**, protocol 1. No screenshots, browser
polling, local test suite, probe or build ran during its windows. Parent and
development agents paused local heavy work. Audit duplicate tabs were closed.

- Chrome 155, Windows, 8 logical processors; browser reports 16GB device memory.
- ANGLE / Intel Iris Plus Graphics 0x8A52 / Direct3D11, WebGL2, antialias true.
  This identifies an Intel hardware path; it is not an independent GPU trace.
- Viewport **2048×852**, each canvas **1240×697 CSS and actual buffer pixels**.
  Device DPR .9375, High buffer ratio 1, Broadcast. Visible/focused throughout;
  no visibility change was recorded. The window was not inferred from a tab
  selection command alone: conditions were sampled and changes latched in-page.
- DevTools CPU throttling, OS power-saving, remote sharing and external system
  load remain **UNVERIFIED**. Page code cannot reliably establish them.

| Stage | Duration / intervals | rAF/render submissions FPS | Frame p95 | CPU submission mean |
|---|---|---:|---:|---:|
| Light animation | 20.3151s / 20 | .98449 | 1016.3ms | .07ms |
| Minimal WebGL | 20.3157s / 20 | .98446 | 1016.3ms | 1.06ms |
| Full local replay | 20.3159s / 20 | .98445 | 1016.3ms | 12.015ms |

Full source advanced from **604.0626 to 623.3625**, with 20 distinct source
samples. This was an active replay, not an old rendered image. Final primary
render counters: **87 calls, 1,469,498 triangles, 36 geometries, 49 textures**.
These are Three.js primary-render counters; additional shadow work must be
examined separately, not assumed absent from the frame cost.

Evidence: `out/visual-reference-review/performance-three-stage-20261026.json`.
Screen capture after the completed run timed out twice. No repeated screenshot
loop, extension reconnection or further identical automated attempt was made.

## Interpretation and next decision

The essentially identical 1016ms callback interval across very different CPU
submission costs supports a **common scheduling/presentation constraint** as a
hypothesis. It does not establish that VMI is fast enough, nor exclude real
scene costs on this GPU. The earlier 5.8/10.9FPS readings were not a matched
comparison and must not be used to claim a speedup or a healthy scene.

**30FPS on the full intended demo remains NOT VERIFIED.** No quality setting,
roster, crowd pose, ball path, simulation outcome or source clock was changed
to obtain a green number. No rendering optimization or FPS improvement is
claimed from this protocol change.

Protocol 2 adds CPU categories for local sampling, overlay updates, pose,
athlete animation, Three.js submission and remaining camera/crowd/ball work.
All are CPU elapsed times, including possible driver waiting; they are not
GPU completion timings. Inspect Chrome Performance/Frames for presented,
partial and dropped frames and confirm **No throttling** before drawing a
final frame-rate conclusion. The control interface did not expose that panel
after F12 in this run; it remains unverified rather than guessed.

After repeated automation/capture failures, the single manual action is the
Start→wait→Copy result flow above. Do not ask for repeated extension repair.
While the manual run is pending, keep local heavy tests/builds stopped;
remote CI and read-only review can continue. If both controls are healthy and
the full scene alone is slow, use the recorded categories and a short browser
profile to select optimizations that preserve the image, then repeat the same
trajectory and dimensions. Vercel hosting is not a substitute for this check.

## Review and tests

ASTRA medium found three P2 measurement defects during read-only review:
transient hidden/blur changes could escape sampled checks; exception cleanup
left Start blocked and GPU resources alive; unsupported long-task observation
looked like zero tasks. All three were repaired before the saved run.
Five capture tests cover warmup/window duration, genuine stalls, changed
conditions, duplicate timestamps, bounded samples, latched transient changes,
stable completed results and separate CPU phase reporting. The pinned replay
test checks its bytes, roster completeness, valid frames and actual motion.
The follow-up review also caught a stale DPR ratio between retries and a
back/forward-cache lifecycle defect. Start now recalculates the ratio and
requires identical surfaces across stages; persisted restoration reloads the
disposed page. Four tests run the real entrypoint against controlled boundaries
to check transient events, changed DPR, GPU error/retry and restoration.
Full suite/CI on the final HEAD remains required.

Primary references:
[Chrome rendering statistics](https://developer.chrome.com/docs/devtools/rendering/performance),
[Chrome Performance/Frames and GPU activity](https://developer.chrome.com/docs/devtools/performance/reference),
[Three.js WebGLRenderer statistics](https://threejs.org/docs/pages/WebGLRenderer).
