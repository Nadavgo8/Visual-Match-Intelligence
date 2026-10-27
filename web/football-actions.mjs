// Cosmetic contact poses from two already-delivered tracking observations.
// No event feed, future frame, result classification or wall clock is consulted.
const near = (ball, player, radius) => player && Array.isArray(ball)
  && Math.hypot(ball[0] - player.x, ball[1] - player.y) <= radius;
const controlled = frame => frame?.possession?.status === "controlled"
  ? frame.possession.holder_id : null;

// Tracking can sample either side of a short control interval. In that case a
// current-frame reach is safe to show; claiming that a kick occurred is not.
export function nearbyBallPose(frame, player) {
  if (player.role === "GK" || !frame.ball_in_play || frame.possession?.status !== "loose"
    || !Number.isFinite(frame.ball_height) || frame.ball_height < 0 || frame.ball_height > .35
    || !Array.isArray(frame.ball) || !frame.ball.every(Number.isFinite)) return null;
  const dx=frame.ball[0]-player.x, dz=player.y-frame.ball[1], distance=Math.hypot(dx,dz);
  if(distance>=.8) return null;
  return {kind:"reach",weight:.65*(1-distance/.8),heading:distance>1e-5?Math.atan2(dx,dz):null};
}

export class FootballActions {
  constructor() { this.reset(); }
  reset() { this.previous = null; this.active = new Map(); }
  update(frame) {
    const old = this.previous, dt = old ? frame.t - old.t : 0;
    const identity = `${frame.match_id}/${frame.run_id ?? ""}`;
    const continuous = old && identity === old.identity && dt >= 0 && dt <= .25;
    if (!continuous || !frame.ball_in_play) this.active.clear();
    const players = new Map(frame.players.map(p => [p.id, p]));
    for (const [id, action] of this.active) if (!players.has(id) || frame.t - action.t >= .42) this.active.delete(id);
    if (continuous && dt > 0 && frame.ball_in_play && old.inPlay && Array.isArray(frame.ball) && Array.isArray(old.ball)) {
      const holder = controlled(frame), previousHolder = old.holder;
      const departed = old.players.get(previousHolder), present = players.get(previousHolder);
      const travel = Math.hypot(frame.ball[0] - old.ball[0], frame.ball[1] - old.ball[1]);
      const contested = [...old.players.values()].some(p => p.team !== departed?.team && near(old.ball,p,1.5));
      if (previousHolder && !holder && frame.possession?.status === "loose"
        && !contested && old.height <= .35 && departed?.role !== "GK" && present && present.role !== "GK" && near(old.ball, departed, .8)
        && near(old.ball, present, 1.2) && travel / dt > 2) {
        this.active.set(previousHolder, { kind: "release", t: frame.t,
          heading: Math.atan2(frame.ball[0] - old.ball[0], old.ball[1] - frame.ball[1]) });
      }
      const receiver = players.get(holder);
      if (!previousHolder && old.status === "loose" && frame.ball_height <= .35 && receiver?.role !== "GK"
        && near(frame.ball, receiver, .8) && travel / dt > .5) {
        this.active.set(holder, { kind: "receive", t: frame.t,
          heading: Math.atan2(old.ball[0] - receiver.x, receiver.y - old.ball[1]) });
      }
    }
    this.previous = { identity, t: frame.t, holder: controlled(frame),
      status: frame.possession?.status, inPlay: !!frame.ball_in_play,
      ball: Array.isArray(frame.ball) ? [...frame.ball] : null, height:frame.ball_height,
      players: new Map(frame.players.map(p => [p.id, { ...p }])) };
    const result = new Map();
    for (const [id, action] of this.active) result.set(id, { ...action,
      weight: (1 - Math.max(0, frame.t - action.t) / .42) ** 2 });
    return result;
  }
}
