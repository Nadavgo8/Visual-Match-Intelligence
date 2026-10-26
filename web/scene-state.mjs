// Metres throughout. The renderer never supplies football facts or wall-clock motion.
import {validMotion} from './match-motion.mjs?v=3.18';
export const worldPosition = (x, y, height = 0) => [x - 52.5, height, 34 - y];
// A 20 Hz transport at 32x delivers 1.6 source seconds between packets.
// Match the sampler's two-second source-discontinuity boundary, not wall time.
const MAX_POSE_INTERVAL = 2;
export function qualitySettings(quality,dpr=1) {
  const ratio=Number.isFinite(dpr) && dpr>0 ? dpr : 1;
  return quality === "low"
    ? {pixelRatio:Math.min(1,ratio),shadows:false,shadowSize:0}
    : {pixelRatio:Math.min(1.5,Math.max(1,ratio)),shadows:true,shadowSize:2048};
}

export function playerPose(previous, player, t) {
  // Generator2.4 supplies analytic source paths. Gait and facing at a given
  // source time must not depend on which frames this viewer previously saw.
  if(validMotion(player.motion)){
    const {heading,speed,distance}=player.motion,phase=distance/2.2*Math.PI*2;
    return {t,x:player.x,y:player.y,heading,speed,distance,
      stride:Math.sin(phase)*Math.min(.65,speed*.09),
      knee:Math.max(0,-Math.sin(phase))*Math.min(.8,speed*.1),
      bob:Math.abs(Math.cos(phase))*Math.min(.04,speed*.005)};
  }
  const dt = previous ? t - previous.t : 0;
  const dx = previous ? player.x - previous.x : 0;
  const dz = previous ? previous.y - player.y : 0;
  // A teleport, repeated timestamp or seek is not a sprint. No stale velocity.
  const speed = dt > 0 && dt <= MAX_POSE_INTERVAL ? Math.min(9, Math.hypot(dx, dz) / dt) : 0;
  const wanted = speed > 0.1 ? Math.atan2(dx, dz) : previous?.heading ?? (player.team === "home" ? Math.PI / 2 : -Math.PI / 2);
  let heading = wanted;
  if (previous && Number.isFinite(previous.heading) && dt > 0 && dt <= MAX_POSE_INTERVAL) {
    const turn = Math.atan2(Math.sin(wanted - previous.heading), Math.cos(wanted - previous.heading));
    heading = previous.heading + Math.max(-9 * dt, Math.min(9 * dt, turn));
    heading = Math.atan2(Math.sin(heading), Math.cos(heading));
  }
  const phase = t * 10;
  const stride = Math.sin(phase) * Math.min(0.65, speed * 0.09);
  const distance = (previous?.distance ?? 0) + (dt > 0 && dt <= MAX_POSE_INTERVAL ? Math.hypot(dx, dz) : 0);
  return { t, x: player.x, y: player.y, heading, speed, stride, distance,
    knee: Math.max(0, -Math.sin(phase)) * Math.min(0.8, speed * 0.1),
    bob: Math.abs(Math.cos(phase)) * Math.min(0.04, speed * 0.005) };
}

export function cameraView(aspect, reducedMotion = false, ball = [52.5, 34], mode = "broadcast") {
  const safeAspect = Math.max(0.2, Number.isFinite(aspect) ? aspect : 16 / 9);
  // Keep the complete metric pitch in frame at narrow sizes as well as 16:9.
  const distance = Math.max(1, (16 / 9) / safeAspect);
  if (!reducedMotion && mode === "broadcast") {
    // A central broadcast gantry looks INTO the playing area at either end.
    // Centring the goal-line ball itself wasted half the frame on end stands.
    const x = Math.max(-35, Math.min(35, (ball[0] - 52.5) * 0.85));
    const far = Math.max(0, Math.min(1, (ball[1] - 34) / 34));
    // Near-side action otherwise pushes the opposite stand above the frame.
    // Tilt up without widening the action or changing any delivered position.
    const near = Math.max(0, Math.min(1, (34 - ball[1]) / 34));
    const target = [x, 3.8 + Math.min(4, 12 * near) - 7.8 * far, 34 - ball[1]];
    const position = [x * 0.38, 30 * distance, 70 * distance];
    // Metric framing: approximately 44m across the action plane. This gives
    // human silhouettes room to read, while retaining receivers 20m either
    // side. The elevated view separates the ball from overlapping bodies.
    const depth = Math.hypot(...position.map((value, i) => value - target[i]));
    const fov = 2 * Math.atan(22 * distance / (safeAspect * depth)) * 180 / Math.PI;
    return { position, target, fov };
  }
  const targetX = reducedMotion ? 0 : Math.max(-5, Math.min(5, (ball[0] - 52.5) * 0.1));
  return { position: [targetX, 72 * distance, 84 * distance], target: [targetX, 0, 0], fov: 46 };
}

export class SceneMotion {
  constructor() { this.reset(); }
  reset() { this.players = new Map(); this.identity = null; this.t = null; this.ball = null; this.ballRoll = { x: 0, z: 0 }; }
  update(frame) {
    const identity = `${frame.match_id}/${frame.run_id ?? ""}`;
    if (identity !== this.identity || frame.t < this.t || frame.t - this.t > MAX_POSE_INTERVAL) {
      this.players.clear(); this.ball = null; this.ballRoll = { x: 0, z: 0 };
    }
    if (Array.isArray(frame.ball)) {
      if (this.ball && frame.t > this.t) {
        // Cosmetic rolling follows displacement, not elapsed match time: a
        // ball resting at a stoppage must not spin in place. Keep angles bounded.
        this.ballRoll.x = (this.ballRoll.x + (this.ball[1] - frame.ball[1]) / 0.16) % (Math.PI * 2);
        this.ballRoll.z = (this.ballRoll.z - (frame.ball[0] - this.ball[0]) / 0.16) % (Math.PI * 2);
      }
      this.ball = [...frame.ball];
    }
    this.identity = identity; this.t = frame.t;
    const next = new Map();
    for (const p of frame.players) {
      const old = this.players.get(p.id);
      // Sampling the same paused frame must preserve exactly the previous pose.
      next.set(p.id, old && old.t === frame.t ? old : playerPose(old, p, frame.t));
    }
    this.players = next;
    return next;
  }
}
