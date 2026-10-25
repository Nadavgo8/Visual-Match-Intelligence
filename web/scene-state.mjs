// Metres throughout. The renderer never supplies football facts or wall-clock motion.
export const worldPosition = (x, y, height = 0) => [x - 52.5, height, 34 - y];
// A 20 Hz transport at 32x delivers 1.6 source seconds between packets.
// Match the sampler's two-second source-discontinuity boundary, not wall time.
const MAX_POSE_INTERVAL = 2;
export const qualitySettings = (quality, dpr = 1) => quality === "low"
  ? { pixelRatio: Math.min(1, dpr), shadows: false, shadowSize: 0 }
  : { pixelRatio: Math.min(1.5, dpr), shadows: true, shadowSize: 2048 };

export function playerPose(previous, player, t) {
  const dt = previous ? t - previous.t : 0;
  const dx = previous ? player.x - previous.x : 0;
  const dz = previous ? previous.y - player.y : 0;
  // A teleport, repeated timestamp or seek is not a sprint. No stale velocity.
  const speed = dt > 0 && dt <= MAX_POSE_INTERVAL ? Math.min(9, Math.hypot(dx, dz) / dt) : 0;
  const heading = speed > 0.1 ? Math.atan2(dx, dz) : previous?.heading ?? (player.team === "home" ? Math.PI / 2 : -Math.PI / 2);
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
    const x = Math.max(-47, Math.min(47, (ball[0] - 52.5) * 0.9)), z = Math.max(-30, Math.min(30, (34 - ball[1]) * 0.95));
    // Aim above the turf to retain audience context in the upper frame. The
    // action remains below centre, with the ball inside its tested safe margin.
    return { position: [x - 6, 16 * distance, z + 25 * distance], target: [x, 6, z], fov: 40 };
  }
  const targetX = reducedMotion ? 0 : Math.max(-5, Math.min(5, (ball[0] - 52.5) * 0.1));
  return { position: [targetX, 72 * distance, 84 * distance], target: [targetX, 0, 0], fov: 46 };
}

export class SceneMotion {
  constructor() { this.reset(); }
  reset() { this.players = new Map(); this.identity = null; this.t = null; }
  update(frame) {
    const identity = `${frame.match_id}/${frame.run_id ?? ""}`;
    if (identity !== this.identity || frame.t < this.t || frame.t - this.t > MAX_POSE_INTERVAL) this.players.clear();
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
