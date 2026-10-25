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
    const x = Math.max(-47, Math.min(47, (ball[0] - 52.5) * 0.9));
    const near = Math.max(0, Math.min(1, (68 - ball[1]) / 68));
    // Keep the camera beyond the near touchline rather than crossing the pitch
    // behind a far-side ball. Zoom compensates for distance so the action stays
    // readable, with receivers visible and the crowd confined to the backdrop.
    return { position: [x - 6, 22 * distance, (60 + 20 * near) * distance],
      target: [x, -2 + 8 * near, 34 - ball[1]], fov: (18 + 16 * near) * 0.9 };
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
