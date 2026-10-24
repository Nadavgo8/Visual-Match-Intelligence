import { FrameTimeline } from "./match-motion.mjs";
import { MarkerState } from "./overlay-state.mjs";

// Shared reset boundary for football drawing and accessibility presentation.
export class MatchScreen {
  constructor() {
    this.timeline = new FrameTimeline(); this.markers = new MarkerState();
    this.liveTime = 0; this.state = null; this.waiting = false;
  }
  sync(state, now) {
    const old = this.state;
    const reset = this.waiting || (old && (old.seed !== state.seed
      || old.match_id !== state.match_id || old.run_id !== state.run_id
      || state.t < this.liveTime - 0.01
      || state.t > this.liveTime + Math.max(1, this.timeline.speed * 0.3)));
    if (reset) this.markers.clear();
    this.timeline.sync(state, now);
    this.waiting = false; this.state = state; this.liveTime = state.t;
    return !!reset;
  }
  frame(frame, now) {
    if (!this.timeline.push(frame, now)) return false;
    this.liveTime = frame.t; return true;
  }
  beginJump() { this.waiting = true; this.timeline.beginJump(); this.markers.clear(); }
  accept(cue) { return !this.waiting && this.markers.accept(cue, this.liveTime); }
  marker() { return this.markers.at(this.liveTime); }
  sample(now) { return this.timeline.sample(now); }
  freeze(now) { this.timeline.freeze(now); }
}
