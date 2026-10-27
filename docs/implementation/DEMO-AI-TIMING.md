# Demo AI timing corrections

The final demo audit found two causal timing defects on main `ab53c72`:

| Trigger | Previous behavior | Correction |
| --- | --- | --- |
| Ask completes after the same run advances | The answer's visible clock used the current match time, although its facts came from the earlier frozen snapshot | Use the answer's existing `snapshot_clock`; retain the run-change discard guard |
| A stoppage-analysis model never completes | The actual analysis workflow had no application deadline, despite the existing 20-second product limit | Bound the whole workflow with that shared limit, cancel the pending call and use the existing validated, labelled template |

Caller cancellation, including seek/reset, still propagates instead of producing
a fallback for an old run. No model, prompt, provider, retry or cost policy changes.
Responses without snapshot metadata keep the previous clock fallback.

Regression evidence:

- The real workflow with a hung fake model reproduced the missing deadline.
  After correction, a controlled deadline cancels the actual call once and
  returns a validated template with no model and an explicit timeout reason.
  Deadline arming is event-driven so SDK startup speed cannot make the test flaky.
- A real WebSocket endpoint and replay reproduced a same-run answer labelled
  `13:21` despite its `12:34` snapshot. The corrected payload retains `12:34`.
- An independently cancelled analysis propagates `CancelledError`.
- All 68 affected agent/session tests passed in 84.21 seconds; all 51 Node
  tests passed in 0.269 seconds. Ruff and whitespace checks passed.
- A separate Sol 6.1 High read-only review found no blocking issue. This is
  AI review, not human approval or evidence of a live model call.

The first sandboxed test process stalled before producing results and was
stopped after verifying its exact process identity. The diagnostic rerun ran
successfully; the stalled attempt is not counted as a test result.

Full current-head CI, coverage, protected merge and merged-main verification
remain required. Cold match generation and startup warm-up can still block
the shared event loop; that separate integration issue is not fixed here.
No live Foundry call, final visual acceptance or new FPS measurement is claimed.
