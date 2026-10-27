import test from "node:test";
import assert from "node:assert/strict";
import { atmospherePresentation, litSegments } from "../../web/atmosphere.mjs";

test("known combined level maps to the correct percentage, label and palette", () => {
  const a = { available: true, level: 0.53, mode: "combined" };
  const screen = atmospherePresentation(a);
  assert.equal(screen.percent, 53);
  assert.equal(screen.label, "Atmosphere 53%");
  assert.equal(screen.color, "rgb(145, 184, 128)");
  assert.equal(atmospherePresentation({ ...a, level: 0 }).color, "rgb(32, 190, 196)");
  assert.equal(atmospherePresentation({ ...a, level: 1 }).color, "rgb(245, 179, 67)");
});

test("unavailable and malformed measurements are neutral, never a zero reading", () => {
  for (const a of [null, {}, { available: false, level: 0 }, { available: true, level: NaN }]) {
    const view = atmospherePresentation(a);
    assert.equal(view.value, null);
    assert.equal(view.percent, null);
    assert.equal(view.label, "Atmosphere unavailable");
  }
});

test("explicit crowd-only mode is visible and bounds are defensive", () => {
  assert.equal(atmospherePresentation({ available: true, level: 0.5, mode: "crowd_only" }).label, "Crowd only 50%");
  assert.equal(atmospherePresentation({ available: true, level: 2 }).value, 1);
  assert.equal(atmospherePresentation({ available: true, level: -1 }).value, 0);
});

test("companion segments light in proportion and stay dark when unavailable", () => {
  assert.equal(litSegments(0), 0);
  assert.equal(litSegments(0.53), 5);
  assert.equal(litSegments(0.56), 6);
  assert.equal(litSegments(1), 10);
  assert.equal(litSegments(1.7), 10);   // clamped, never more segments than exist
  assert.equal(litSegments(-0.2), 0);
  assert.equal(litSegments(null), 0);   // unavailable is not a reading
  assert.equal(litSegments(NaN), 0);
  assert.equal(litSegments(0.5, 4), 2);
});
