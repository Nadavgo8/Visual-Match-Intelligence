# Companion meter reset — 26 October 2026

## Finding and scope

During the D1 3D integration audit, replacing seed 12 at 2:09 with seed 13
reset the match screen to 0:00 and unavailable atmosphere. The companion
showed the new clock and empty feed but retained **Atmosphere 38%** from the
previous run. This is a P2 stale-evidence defect, independent of 3D rendering.

Cause: `onSnapshot` applied meters only when present, but never cleared the
previous meter presentation when the replacement snapshot contained null.
The same defect affected reconnect/seek snapshots without measurements.

## Repair

- Clear atmosphere, its explanatory title and momentum before applying every
  replacement snapshot. A snapshot with meters then restores its own values.
- Render missing atmosphere/momentum components as unavailable; do not throw
  on null or retain an old reading. Neutral momentum uses a uniformly gray
  track/fill and an explicit unavailable accessible label, not a claimed 50%.
- Keep score, clock, feed, checkpoints and question behavior intact. No source
  formula, football contract, model/provider or D2 feature scope is changed.
- Version the app entrypoint and stylesheet together.

## Validation and review

The real `app.js` entrypoint runs in the existing harness with controlled DOM
and transport boundaries and the real atmosphere presenter. Three regression
tests failed before the fix (old 38% retained; null component exception), then
passed: new run with no measurements; same-run reconnect and later populated
snapshot; missing meter components. Existing assertions remain intact.

Local Node suite: **40 passed in 2.38s**. Full Python/CI and coverage on the
final tested SHA, actual browser recheck, protected merge and main B4 remain
required; no earlier test result is presented as completing those gates.

Author/reviewer: Codex, separate implementation and self-review phases; no
claim of independent human approval. Review checked null/absent values,
complete replacement data, same-run reconnect, neutral presentation, cache
versions and literal-text assignment. Do not equate an empty snapshot with
measured crowd silence.

Review improvement: every replacement snapshot must be tested after a
nonempty prior state, including missing derived measurements. Checking only
the first load or new feed contents misses stale visual evidence.
