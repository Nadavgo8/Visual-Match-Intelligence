// Presentation only: sample delivered positions; never infer a football outcome.
const finite = Number.isFinite;
export function validFrame(f) {
  return !!f && finite(f.t) && f.t >= 0 && typeof f.match_id === "string"
    && Array.isArray(f.ball) && f.ball.length === 2 && f.ball.every(finite)
    && f.ball[0] >= -5 && f.ball[0] <= 110 && f.ball[1] >= -5 && f.ball[1] <= 73
    && finite(f.ball_height) && f.ball_height >= 0 && f.ball_height <= 30
    && Array.isArray(f.players) && f.players.length <= 22
    && f.players.every(p => p && typeof p === "object")
    && new Set(f.players.map(p => p.id)).size === f.players.length
    && f.players.every(p => typeof p.id === "string" && ["home", "away"].includes(p.team)
      && finite(p.x) && p.x >= 0 && p.x <= 105 && finite(p.y) && p.y >= 0 && p.y <= 68);
}

export function interpolate(a, b, t) {
  if (!a) return b;
  if (!b || t <= a.t) return a;
  if (t >= b.t) return b;
  // Don't slide across source discontinuities or fabricate a substituted player.
  if (a.match_id !== b.match_id || b.t - a.t > 2) return a;
  const u = (t - a.t) / (b.t - a.t);
  const blend = (x, y) => x + (y - x) * u;
  const next = new Map(b.players.map(p => [p.id, p]));
  return { ...a, t, ball: a.ball.map((x, i) => blend(x, b.ball[i])),
    ball_height: blend(a.ball_height, b.ball_height),
    players: a.players.map(p => {
      const q = next.get(p.id);
      return q ? { ...p, x: blend(p.x, q.x), y: blend(p.y, q.y) } : p;
    }) };
}

export function pitchProjection(width, height) {
  const scale = Math.min((width - 64) / 105, (height - 130) / 68);
  const left = (width - 105 * scale) / 2, top = (height - 68 * scale) / 2 + 24;
  return { scale, left, top, point: (x, y) => [left + x * scale, top + (68 - y) * scale] };
}

export function ballAppearance(height, scale) {
  const h = Math.max(0, Math.min(30, finite(height) ? height : 0));
  return { lift: Math.min(20, h * scale * 0.45), radius: 4.5 + Math.min(1.8, h * 0.22),
    shadowRadius: 4.2 + Math.min(4, h * 0.5), shadowOpacity: 0.42 / (1 + h * 0.15) };
}

export class FrameTimeline {
  constructor() { this.frames = []; this.playing = false; this.speed = 1; this.waiting = false; }
  beginJump() { this.frames = []; this.waiting = true; }
  sync(s, now) {
    const last = this.frames.at(-1);
    const changed = this.seed !== s.seed || this.match !== s.match_id || this.run !== s.run_id;
    const jumped = last && (s.t < last.t - 0.01 || s.t > last.t + Math.max(1, this.speed * 0.3));
    if (this.waiting || changed || jumped) this.frames = [];
    else if (last && (this.playing !== !!s.playing || this.speed !== s.speed)) this.frames = [last];
    this.waiting = false; this.seed = s.seed; this.match = s.match_id; this.run = s.run_id;
    this.playing = !!s.playing; this.speed = s.speed; this.received = now;
  }
  push(f, now) {
    if (this.waiting || !validFrame(f) || (this.match && f.match_id !== this.match)
      || (this.run !== undefined && f.run_id !== this.run)) return false;
    const last = this.frames.at(-1);
    if (last && f.t <= last.t) return false;
    this.frames.push(structuredClone(f));
    if (this.frames.length > 4) this.frames.shift();
    this.received = now;
    return true;
  }
  sample(now) {
    const b = this.frames.at(-1), a = this.frames.at(-2);
    if (!b || !a || !this.playing) return b ?? null;
    const delay = Math.min(0.25 * this.speed, b.t - a.t);
    const t = Math.min(b.t, b.t - delay + Math.max(0, now - this.received) * this.speed / 1000);
    return interpolate(a, b, t);
  }
  freeze(now) {
    const f = this.sample(now);
    this.frames = f ? [f] : []; this.playing = false;
  }
}
