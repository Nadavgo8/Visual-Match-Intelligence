import test from "node:test";
import assert from "node:assert/strict";
import { crowdMix, nextBaseline } from "../../web/crowd-sound.mjs";

// Feed a level series through the baseline the way the TV does: one entry per match second,
// sampled at three meters ticks a second like the live replay.
function play(levels) {
  let b = NaN;
  return levels.map((l) => { let m; for (let i = 0; i < 3; i++) { m ??= crowdMix(l, b); b = nextBaseline(b, l, 1 / 3); } return m; });
}

test("a steady crowd murmurs and never roars", () => {
  const out = play(Array(60).fill(0.37));
  assert.ok(out.every((m) => m.roar === 0));
  assert.ok(out.at(-1).murmur > 0.1);
});

test("a goal surge roars, then settles while the crowd stays loud", () => {
  const out = play([...Array(30).fill(0.37), 0.5, 0.7, 0.9, ...Array(60).fill(0.95)]);
  assert.ok(Math.max(...out.slice(30, 40).map((m) => m.roar)) > 0.8, "a full roar within the first seconds");
  assert.ok(out.slice(33, 43).every((m) => m.roar > 0.6), "held for ten seconds while the crowd erupts");
  assert.ok(out[33].murmur > out[29].murmur);
  assert.ok(out.at(-1).roar < 0.3, `settles: ${out.at(-1).roar}`);
});

test("a smaller surge (a big chance) is heard, but quieter than a goal", () => {
  const chance = play([...Array(30).fill(0.37), 0.7])[30].roar;
  const goal = play([...Array(30).fill(0.37), 0.95])[30].roar;
  assert.ok(chance > 0.3 && chance < goal);
});

test("missing or out-of-range levels are safe", () => {
  assert.deepEqual(crowdMix(null, 0.4), { murmur: 0, roar: 0, cutoff: 400 });  // no crowd data: silence
  assert.equal(crowdMix(2, 0.3).cutoff, 2000);
  assert.equal(nextBaseline(0.4, undefined), 0.4);
  assert.equal(nextBaseline(NaN, 0.5), 0.5);
  assert.equal(nextBaseline(0.4, 0.9, NaN), 0.4);  // no elapsed match time (first tick, seek): unchanged
  assert.equal(nextBaseline(0.4, 0.9, -5), 0.4);
});
