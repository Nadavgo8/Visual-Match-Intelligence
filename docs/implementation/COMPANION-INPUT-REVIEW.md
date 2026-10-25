# Companion input review — 25 October 2026

Scope: a focused repair of existing browser behavior found during the repository
audit. Base: `9c8ee83d5d2caf5af1c99d8f6ff60346f1f757a3`. This does not select a
model, change the wire contract or add D2 product features.

## Findings and repairs

- **P1 — answer metadata entered HTML without escaping.** `QASystem._agents`
  accepts an agent label from the model JSON. The app escaped answer text and
  evidence but interpolated an unknown agent label directly into the receipts
  HTML. A label containing an image with an event handler could introduce active
  markup. Escape the label on both live/local paths, plus timing metadata in
  answers and analysis receipts. Existing structured receipts remain usable.
- **P2 — valid JSON of the wrong shape broke catch-up checkpoints.** Persisted
  numbers, booleans and strings caused `advance` to throw; arrays silently lost
  string-keyed checkpoints when serialized. Accept a non-null, non-array object
  only; discard corrupt storage and persist the next valid checkpoint normally.

The first regression run on the original implementation had **9 pass / 2 fail**:
the primitive checkpoint threw and injected answer markup was present. After
the repair and an added analysis-receipt regression: **12 pass / 0 fail** in the
companion suite. Scoped `companion.mjs` coverage is **100% lines, branches and
functions**. The full Node suite at this independent base has **33 pass**, no
skips; Ruff and whitespace checks pass. Full Python/contract/integration and
coverage checks run on the PR before merge; post-merge checks remain required.

The app tests execute the real `app.js` entrypoint in Node's VM with controlled
DOM and transport boundaries. They inspect its actual HTML output, including
model/name/text/evidence/tool/fallback/timing payloads and quoted attribute data,
and preserve known labels and duplicate-answer behavior. They are not a claim
of a real-browser visual inspection. No external model or network is used.

Author and reviewer: Codex, in separate self-review steps, not an independent
or human approval. Learning: escaping visible answer prose is insufficient;
review every HTML interpolation and validate persisted JSON's shape, not just
whether it parses. Existing storage denial/bounds and room/run isolation tests
continue to execute.
