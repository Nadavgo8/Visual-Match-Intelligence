// Synthetic stadium sound for hearing viewers of the demo: crowd noise driven by
// the crowd level, and a whistle per banner. Generated in the browser; no
// recorded audio or music.
export class SyntheticAudio {
  constructor() { this.ctx = null; this.enabled = false; this.gain = null; }

  unlock() {
    if (this.ctx) return;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    this.ctx = new AC();
    // brown noise -> low-pass = crowd murmur
    const len = this.ctx.sampleRate * 2;
    const buf = this.ctx.createBuffer(1, len, this.ctx.sampleRate);
    const d = buf.getChannelData(0);
    let last = 0;
    for (let i = 0; i < len; i++) { last = (last + 0.02 * (Math.random() * 2 - 1)) / 1.02; d[i] = last * 3.5; }
    const src = this.ctx.createBufferSource();
    src.buffer = buf; src.loop = true;
    this.filter = this.ctx.createBiquadFilter();
    this.filter.type = "lowpass"; this.filter.frequency.value = 600;
    this.gain = this.ctx.createGain(); this.gain.gain.value = 0;
    src.connect(this.filter).connect(this.gain).connect(this.ctx.destination);
    src.start();
  }

  crowd(level) {
    if (!this.ctx || !this.gain) return;
    const t = this.ctx.currentTime;
    const g = this.enabled ? Math.pow(level, 1.6) * 0.9 : 0;
    this.gain.gain.setTargetAtTime(g, t, 0.4);
    this.filter.frequency.setTargetAtTime(400 + level * 1600, t, 0.4);
  }

  whistle(type) {
    if (!this.ctx || !this.enabled) return;
    const blasts = type === "full_time" ? 3 : type === "half_time" || type === "stoppage" ? 2 : 1;
    const long = ["penalty", "half_time", "full_time"].includes(type);
    let t = this.ctx.currentTime + 0.02;
    for (let i = 0; i < blasts; i++) {
      const dur = long ? 0.9 : 0.35;
      const osc = this.ctx.createOscillator();
      const trem = this.ctx.createOscillator();
      const tg = this.ctx.createGain();
      const g = this.ctx.createGain();
      osc.frequency.value = 2900; trem.frequency.value = 32; tg.gain.value = 120;
      trem.connect(tg).connect(osc.frequency);
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(0.18, t + 0.02);
      g.gain.setValueAtTime(0.18, t + dur - 0.05);
      g.gain.linearRampToValueAtTime(0, t + dur);
      osc.connect(g).connect(this.ctx.destination);
      osc.start(t); trem.start(t); osc.stop(t + dur); trem.stop(t + dur);
      t += dur + 0.18;
    }
  }
}
