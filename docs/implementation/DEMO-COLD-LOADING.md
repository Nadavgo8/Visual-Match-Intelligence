# Cold match preparation without stopping connected rooms

Baseline: main `ffd8cd0`. A controlled source fake reproduced a cold
`new_match` blocking the event loop: the source waited for a callback that
could not run until generation returned. This is independent of render FPS.

The correction reuses the generator, Replay and room contract:

- One source worker, at most four distinct pending loads, shared by seed.
  Joining admitted work and using a cached source remain possible at capacity.
- Eight cached sources; active rooms retain their own Match after eviction.
  Cached reads do not wait behind a different seed's generation lock.
- Cancelling one waiter does not cancel shared work or release its slot early.
  The actual worker completion releases admission, including across closed
  request loops; failed preparation can retry.
- A room receives its prepared Match directly. A backward seek reuses it.
  A newer match request, seek or room expiry invalidates a late completion.
- Connections recheck the room and capacity after loading, so simultaneous
  arrivals cannot create two rooms or exceed the limit.
- Warm-up scans a private Replay in the worker and returns materialized
  analyses; it never mutates a live room from a thread. Shutdown cancels the
  owned warm-up task. An already running synchronous source operation finishes
  in its worker; it is not claimed to be forcibly interruptible.

Seventeen focused regressions passed in 1.94 seconds after the causal failure
was reproduced. All 42 tests in the initial loader/session/API selection passed
under coverage in 66.98 seconds; the additional host-busy test then passed with
the full loader selection. Changed critical server coverage in that scoped run
was 72/73 lines and 20/22 branches; this is not the full repository gate. All
51 Node tests, Ruff and whitespace checks passed. A separate Sol 6.1 High
read-only review found no blocking issue. Final-head full CI/coverage, protected
merge and B4 remain required. Event-driven test
gates use deadlines only to bound a broken implementation; no external calls,
paid services, changed football decisions or new model are involved.

Review improvement: every new await before room replacement must recheck the
request and run; every shared worker must bound actual jobs, not only waiters.
This does not claim new visual, FPS or public-deployment acceptance.
