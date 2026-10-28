// Synthetic stadium sound for hearing viewers of the demo: crowd noise driven by
// the crowd level (a murmur, plus a roar when the level surges), and a whistle per
// banner. Generated in the browser; no recorded audio or music.
import { crowdMix, nextBaseline } from "./crowd-sound.mjs";

export class SyntheticAudio {
  constructor() { this.ctx = null; this.enabled = false; this.gain = null; this.baseline = NaN; this.lastT = NaN; }

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
    this.out = this.ctx.createDynamicsCompressor();  // a goal roar must not clip
    this.out.connect(this.ctx.destination);
    src.connect(this.filter).connect(this.gain).connect(this.out);
    src.start();
    // white noise through two voice-band filters = many voices shouting at once
    const white = this.ctx.createBuffer(1, len, this.ctx.sampleRate);
    const w = white.getChannelData(0);
    for (let i = 0; i < len; i++) w[i] = Math.random() * 2 - 1;
    this.roarGain = this.ctx.createGain(); this.roarGain.gain.value = 0;
    for (const [f, q] of [[700, 0.8], [1800, 1.1]]) {
      const n = this.ctx.createBufferSource();
      n.buffer = white; n.loop = true;
      const bp = this.ctx.createBiquadFilter();
      bp.type = "bandpass"; bp.frequency.value = f; bp.Q.value = q;
      n.connect(bp).connect(this.roarGain);
      n.start(0, Math.random() * 2);
    }
    this.roarGain.connect(this.out);
  }

  crowd(level, matchT = NaN) {
    if (!this.ctx || !this.gain) return;
    const mix = crowdMix(level, this.baseline);
    if (this.enabled) { this.baseline = nextBaseline(this.baseline, level, matchT - this.lastT); this.lastT = matchT; }
    const t = this.ctx.currentTime;
    const on = this.enabled ? 1 : 0;
    this.gain.gain.setTargetAtTime(mix.murmur * on, t, 0.4);
    this.filter.frequency.setTargetAtTime(mix.cutoff, t, 0.4);
    // a roar swells fast and fades slowly
    const roar = mix.roar * on;
    this.roarGain.gain.setTargetAtTime(roar, t, roar > this.roarGain.gain.value ? 0.12 : 1.2);
  }

  // After a seek or a new match the old baseline says nothing about the new moment.
  reset() { this.baseline = NaN; this.lastT = NaN; }

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
      osc.connect(g).connect(this.out);
      osc.start(t); trem.start(t); osc.stop(t + dur); trem.stop(t + dur);
      t += dur + 0.18;
    }
  }
}
