# D1 performance isolation — 26 October 2026

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
Full suite/CI on the final HEAD remains required.

Primary references:
[Chrome rendering statistics](https://developer.chrome.com/docs/devtools/rendering/performance),
[Chrome Performance/Frames and GPU activity](https://developer.chrome.com/docs/devtools/performance/reference),
[Three.js WebGLRenderer statistics](https://threejs.org/docs/pages/WebGLRenderer).
