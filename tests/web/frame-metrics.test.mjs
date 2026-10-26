import test from 'node:test';
import assert from 'node:assert/strict';
import { FrameMetrics } from '../../web/frame-metrics.mjs';

test('cadence requires a full observation window, with frame-time percentiles', () => {
  const m = new FrameMetrics();
  for (let t = 0; t <= 9980; t += 20) m.observe(t, true, 'high');
  assert.equal(m.report(), null);
  m.observe(10000, true, 'high');
  assert.deepEqual(m.report(), { durationMs: 10000, intervals: 500, fps: 50, p50Ms: 20, p95Ms: 20, maxMs: 20 });
  // A visible stall must be counted, not dropped as an outlier.
  m.observe(11000, true, 'high');
  assert.equal(m.report().maxMs, 1000);
  assert.ok(m.report().fps < 46);
});
test('pause, hidden/unfocused view, renderer changes and nonmonotonic clocks restart evidence', () => {
  for (const interrupt of [m => m.observe(10001, false, 'a'), m => m.observe(10001, true, 'b'),
    m => m.observe(9999, true, 'a'), m => m.observe(NaN, true, 'a')]) {
    const m = new FrameMetrics();
    m.observe(0, true, 'a'); m.observe(10000, true, 'a');
    assert.ok(m.report()); interrupt(m); assert.equal(m.report(), null);
  }
});
test('rolling evidence is bounded and does not hide a one-FPS measurement', () => {
  const m = new FrameMetrics();
  for (let t = 0; t <= 100000; t += 1000) m.observe(t, true, 'a');
  assert.equal(m.report().fps, 1); assert.equal(m.report().p95Ms, 1000);
  assert.ok(m.samples.length <= 11);
  const capped = new FrameMetrics(10000, 8);
  for (let t = 0; t <= 1000; t++) capped.observe(t, true, 'a');
  assert.equal(capped.samples.length, 8); assert.equal(capped.report(), null);
});
