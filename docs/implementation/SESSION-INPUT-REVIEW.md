# Session input repair — 25 October 2026

Base: verified main `e3dcfe4fc104acefed000fe1cae8aae89720e770` (PR #25 B4).
Branch: `codex/fix-session-input-validation`. Shared transport repair; no new D2 feature.

## Findings

- S01 / P2: an actual endpoint probe sending `[]` then pause raises `AttributeError`
  at `msg.get` before pause. Malformed JSON, primitives, non-string commands and
  non-object profiles lacked validation too. A bounded decoder now refuses them
  before mutation; the existing `bad_command` response keeps the connection usable.
- S02 / P2: Python considers booleans numbers. Explicit rejection prevents `true`
  becoming playback speed/seek time or `false` becoming a new seed.
- S03 / P2: unknown roles silently became TV clients. Only existing `tv`/`app` roles
  are accepted now; an unknown role closes with 1008 before room creation.

The 4,096-character envelope bound limits JSON parser work. It is not a transport
byte limit, authentication or rate limiter. Ask already truncates questions to 400
characters. Valid command fields and existing clients remain compatible.

## Review and evidence

Codex implementation and separate self-review, without independent/human approval.
Review covered failure paths, host permissions, run/seed/profile preservation,
subsequent valid commands, bounded decoding and payload-free errors.

```powershell
python -m pytest tests/test_ws_input.py tests/test_realtime_session.py -v -ra --strict-markers --strict-config -p no:cacheprovider -W error
node --test tests/web/*.test.mjs
python -m ruff check vmi tests tools
```

Offline, warm demo and plugin autoload disabled: 44 Python passed in 190.77s;
37 Node passed; Ruff and whitespace passed. The run additionally enabled a 45s
faulthandler diagnostic: existing whole-match replay exceeded that interval and
then passed. Two earlier stopped runs have no final result and are not PASS.
Initial new-unit collection failed because the decoder did not exist; the actual
endpoint probe, not that import failure, is the before-repair evidence.

Full suite, coverage, four required CI checks, fixed-SHA technical acceptance and
B4 on merged main remain required. No merge/DONE claimed yet.

Learning: test raw JSON shapes as well as valid command values. A regression must
prove refusal followed by a successful command on the same connection.
