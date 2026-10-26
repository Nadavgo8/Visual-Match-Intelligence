import { atmospherePresentation } from "./atmosphere.mjs";

export const MARKERS = Object.freeze({ whistle: 3, foul: 3, offside: 3, penalty: 4,
  stoppage: 3, kick_off: 3, half_time: 4, full_time: 4, drinks_break: 3 });
const PRIORITY = { whistle: 0, kick_off: 1, stoppage: 2, foul: 3, offside: 3,
  drinks_break: 4, penalty: 5, half_time: 6, full_time: 6 };

export function edgePresentation(atmosphere) {
  const view = atmospherePresentation(atmosphere);
  return { ...view, height: view.value === null ? 100 : view.value * 100,
    brightness: view.value === null ? 0.4 : 0.9 + view.value * 0.1,
    available: view.value !== null };
}

// Exactly one marker. Simulation time advances while the ball is out of play;
// pause repeats the same time. No wall-clock timers and no queue of stale cues.
export class MarkerState {
  constructor() { this.clear(); }
  clear() { this.active = null; this.retired = new Set(); }
  retire(id) {
    this.retired.add(id);
    if (this.retired.size > 64) this.retired.delete(this.retired.values().next().value);
  }
  accept(cue, now) {
    if (!cue || typeof cue !== "object") return false;
    const kind = cue.banner ?? cue.type;
    if (!Object.hasOwn(MARKERS, kind) || typeof cue.cue_id !== "string"
      || !Number.isFinite(cue.t_start) || !Number.isFinite(now) || cue.t_start < 0
      || this.retired.has(cue.cue_id)) return false;
    const end = cue.t_start + MARKERS[kind];
    if (now >= end) { this.retire(cue.cue_id); return false; }
    const old = this.active;
    if (old?.cue_id === cue.cue_id) {
      if (!cue.update || cue.t_start !== old.t_start) return false;
    } else {
      if (old && (cue.update || cue.t_start < old.t_start)) return false;
      if (old && now < old.t_end && PRIORITY[kind] < PRIORITY[old.banner]) {
        this.retire(cue.cue_id); return false;
      }
      if (old) this.retire(old.cue_id);
    }
    this.active = { ...cue, banner: kind, t_end: end };
    return true;
  }
  at(now) {
    if (!this.active || !Number.isFinite(now)) return null;
    if (now >= this.active.t_end) { this.retire(this.active.cue_id); this.active = null; }
    return this.active && now >= this.active.t_start ? this.active : null;
  }
}
