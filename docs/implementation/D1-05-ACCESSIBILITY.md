# D1-05 — agreed screen layout and simulation-time signals

Reference: the user-supplied six-page Hebrew product document is byte-identical to
[the repository copy](../context/product-doc-2026-10-21.pdf), SHA-256
`01785fc8b77e4bcb1fa71ff2ffcdbcfd037d379f2034dc8babd497521e0964a3`.
All six pages, including illustrations, were inspected. Pages 1–3 define the screen
layout; the active [plan](VMI-FINAL-PLAN-F.md) adds exact timing and retains the 2D
demo. The illustration is a synthetic design reference, not a required video asset.

| Agreed detail | Implementation and verification |
|---|---|
| Two identical thin edge rails, almost full height, with safe margins | Shared atmosphere variables on both sides; same fill, palette and brightness, verified through computed browser styles |
| Turquoise to amber, local gentle glow, no pulse or flash | Bounded height/brightness and static gradient; only linear transitions; optional reduced motion disables transitions |
| One dark round symbol, light outline/icon, short caption | Single DOM status element in the upper right, outside the score bug; distinct original SVG glyphs |
| Compact score bug and momentum underneath | Small two-row HUD upper left; relative momentum remains the shared seven-minute value |
| Clear centre; no crowd-surge or VAR overlay | Old banner slots and surge producer removed; no xG, dribble, card or player-name overlays |
| Presenter trace outside the viewing screen | Replay chapters, seed, source status and trace are in closed presenter details below the screen |
| Optional adjustments; ready without calibration | Intensity, symbol size and reduce-motion menu; no colour picker or hearing-level question |
| Companion remains optional | Explicit optional link; no dependency on opening the phone |

## Timing and event selection

Generic whistles wait exactly two simulation seconds from **receipt of the audio
detection**, including fractional deadlines. Replay processes a linked reason at
the same deadline before displaying a generic symbol. Display starts when the
information is known, not at a backdated occurrence time. A late reason preserves
the same cue ID and original display start. Ordinary markers last three simulation
seconds; penalty and period end last four. Drinks break has a three-second marker;
its expiration never restarts football play.

The client samples the source frame time, so pause freezes lifetime while football
stoppages do not. No `setTimeout` controls symbol lifetime. Seek/reset clears active
and retired cues. Expired or superseded updates cannot resurrect old symbols.
Only one marker is active; higher-priority specific decisions supersede general
whistles/restarts. A late kick-off cannot hide an already active foul. Period end
has highest priority. There is no deferred queue of obsolete overlays. Retired IDs
and pending-whistle records are bounded to 64 entries.

## Checks and remaining scope

Nine new Python cases cover fractional deadlines, deadline ties, late enrichment,
drinks restart preservation, approved symbols and removal of crowd banners. Seven
failed before the implementation and all nine passed after it. Node behavior tests
cover exact 3/4-second boundaries, paused packets, dead-ball expiry, one marker,
priority, late updates, reset, malformed/forbidden types, bounded memory and shared
edge presentation. Deliberate expiry-boundary and priority mutations are caught.

```powershell
python -m pytest tests -q -ra --strict-markers --strict-config -p no:cacheprovider -W error
node --test tests/web/*.test.mjs
```

Browser QA uses the actual server/WS path. An ignored local fixture-server harness
selects existing generator scenarios without changing the production API. The
handball fixture exposed the delayed-kick-off priority defect and verified the fix.
The marker remained Foul while paused; its bounding box was separate from the score
bug. Actual measured viewport dimensions and final-SHA results belong in the PR.

This branch starts from verified main `52ad4a5`, independently of unmerged D1-04.
The original 2D canvas remains its baseline; the new renderer is isolated in D1-04.
No D2 model/runtime, transport authorization, catch-up implementation or stage-4
load/soak result is claimed. Technical evidence is reviewed by the authoring Codex
session, not a human or an invented independent reviewer.
