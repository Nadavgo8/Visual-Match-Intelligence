// Developer-only render cadence. Never advances simulation or chooses quality.
export class FrameMetrics {
  constructor(windowMs = 10000, capacity = 4096) {
    this.windowMs = windowMs; this.capacity = capacity; this.reset();
  }
  reset() { this.samples = []; this.previous = null; this.identity = null; }
  observe(now, enabled, identity) {
    if (!enabled || !Number.isFinite(now)) { this.reset(); return; }
    if (identity !== this.identity || (this.previous !== null && now <= this.previous)) this.reset();
    this.identity = identity;
    if (this.previous !== null) this.samples.push({ start: this.previous, end: now, ms: now - this.previous });
    this.previous = now;
    // Retain the interval crossing the window boundary, so duration is measured
    // rather than inferred from a target frame rate. Bound memory separately.
    while (this.samples.length > 1 && this.samples[1].start <= now - this.windowMs) this.samples.shift();
    if (this.samples.length > this.capacity) this.samples.splice(0, this.samples.length - this.capacity);
  }
  report() {
    if (!this.samples.length) return null;
    const duration = this.previous - this.samples[0].start;
    if (duration < this.windowMs) return null;
    const times = this.samples.map(s => s.ms).sort((a, b) => a - b);
    const percentile = fraction => times[Math.ceil(fraction * times.length) - 1];
    return { durationMs: duration, intervals: times.length, fps: times.length * 1000 / duration,
      p50Ms: percentile(.5), p95Ms: percentile(.95), maxMs: times.at(-1) };
  }
}
