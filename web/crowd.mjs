// Stadium crowd for the 2D match screen. It has no simulation of its own: every reaction
// follows the delivered atmosphere meter (level, its attack part and attacking team) and
// the delivered score, so the crowd can never disagree with the edge bars or the score bug.
// Deterministic (no Math.random) and batched: a few canvas paths per frame for ~1000 fans.

const ROW_GAP = 13, SEAT_GAP = 12.5, GROUP_SEATS = 8;
const LONG_ROWS = 3, END_ROWS = 2, FIRST_ROW = 12; // px from the touchline / goal line
const WAVE_PX_S = 900;          // how fast a reaction spreads along a stand
const RISE_S = 0.45, FALL_S = 2.8; // excitement eases up quickly and settles slowly
export const CELEBRATE_S = 7;

const clamp = (v, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));
const smooth = (v) => { const x = clamp(v); return x * x * (3 - 2 * x); };
// Deterministic 0..1 noise from an integer.
export function hash(n) {
  let x = Math.imul((n | 0) ^ 0x9e3779b9, 0x85ebca6b);
  x ^= x >>> 13; x = Math.imul(x, 0xc2b2ae35); x ^= x >>> 16;
  return (x >>> 0) / 4294967296;
}

const NEUTRAL = ["#4b5661", "#5e6872", "#3c454e"];
const HAIR = ["#2b2018", "#4a3426", "#17191c", "#7d6040"];
const STAND = "#0f1a20";

/**
 * Seats around the pitch rectangle (canvas px). Long sides get three compact rows; the
 * ends get two shorter rows behind each goal. Seats are split into small groups with an
 * aisle between them; each group is the unit that reacts.
 */
export function buildCrowd({ W, H, left, right, top, bottom }) {
  const groups = [], fans = [];
  let seat = 0;
  const length = right - left, midY = (top + bottom) / 2;
  const addGroup = (side, cx, cy) => {
    const u = (cx - left) / length;
    // Home fans fill most of the ground; away fans hold the right end and a bottom corner;
    // a small neutral block sits on the top halfway line.
    let team = "home";
    if (side === "right" || (side === "bottom" && u > 0.72)) team = "away";
    else if (side === "top" && u > 0.44 && u < 0.56) team = null;
    const id = groups.length;
    groups.push({ id, side, cx, cy, team, jitter: hash(id * 7 + 3) * 0.3, phase: hash(id * 11 + 5),
                  excitement: 0, armed: 0, pending: null, armAt: 0 });
    return id;
  };
  const addFan = (g, x, y, nx, ny) => {
    const i = ++seat;
    if (hash(i * 13 + 1) < 0.06) return; // a few empty seats
    const team = groups[g].team, neutral = !team || hash(i * 17 + 2) < 0.18;
    fans.push({ x, y, nx, ny, g, th: 0.05 + 0.95 * hash(i * 19 + 4), phase: hash(i * 23 + 6) * Math.PI * 2,
                tone: neutral ? 6 + Math.floor(hash(i * 29) * 3) : (team === "away" ? 3 : 0) + Math.floor(hash(i * 31) * 3),
                hair: Math.floor(hash(i * 37) * HAIR.length) });
  };
  for (const side of ["top", "bottom"]) {
    const dir = side === "top" ? -1 : 1, edge = side === "top" ? top : bottom;
    const span = SEAT_GAP * GROUP_SEATS, count = Math.floor((length - 8) / span);
    const x0 = left + (length - count * span) / 2;
    for (let k = 0; k < count; k++) {
      const g = addGroup(side, x0 + (k + 0.5) * span, edge + dir * (FIRST_ROW + ROW_GAP));
      for (let r = 0; r < LONG_ROWS; r++)
        for (let s = 1; s < GROUP_SEATS; s++) // seat 0 is the aisle
          addFan(g, x0 + k * span + (s + (r % 2) * 0.5) * SEAT_GAP, edge + dir * (FIRST_ROW + r * ROW_GAP), 0, -dir);
    }
  }
  const endHalf = Math.min(250, (bottom - top) * 0.32), span = SEAT_GAP * GROUP_SEATS;
  const count = Math.floor((2 * endHalf) / span), y0 = midY - (count * span) / 2;
  for (const side of ["left", "right"]) {
    const dir = side === "left" ? -1 : 1, edge = side === "left" ? left : right;
    for (let k = 0; k < count; k++) {
      const g = addGroup(side, edge + dir * (FIRST_ROW + ROW_GAP / 2), y0 + (k + 0.5) * span);
      for (let r = 0; r < END_ROWS; r++)
        for (let s = 1; s < GROUP_SEATS; s++)
          addFan(g, edge + dir * (FIRST_ROW + r * ROW_GAP), y0 + k * span + (s + (r % 2) * 0.5) * SEAT_GAP, -dir, 0);
    }
  }
  const depthL = FIRST_ROW + (LONG_ROWS - 1) * ROW_GAP + 8, depthE = FIRST_ROW + (END_ROWS - 1) * ROW_GAP + 8;
  const bands = [
    [left - 4, top - depthL, length + 8, depthL - FIRST_ROW + 6],
    [left - 4, bottom + FIRST_ROW - 6, length + 8, depthL - FIRST_ROW + 6],
    [left - depthE, y0 - 4, depthE - FIRST_ROW + 6, count * span + 8],
    [right + FIRST_ROW - 6, y0 - 4, depthE - FIRST_ROW + 6, count * span + 8],
  ];
  return { W, H, left, right, top, bottom, length, groups, fans, bands };
}

// Goal a team attacks in a period, as a canvas x (home attacks right in the first half).
export function goalX(crowd, team, period) {
  if ((team !== "home" && team !== "away") || !Number.isInteger(period) || period < 1) return null;
  return (team === "home") === (period % 2 === 1) ? crowd.right : crowd.left;
}

/** Per-group excitement driven by meters; `now` is wall-clock seconds. */
export class CrowdReactions {
  constructor(crowd) { this.crowd = crowd; this.enabled = true; this.palette = null; this.reset(); }

  reset() {
    this.input = null; this.score = null; this.celebration = null;
    for (const g of this.crowd.groups) { g.excitement = 0; g.armed = 0; g.pending = null; g.armAt = 0; }
  }

  setTeams(home, away) {
    if (this.teams === `${home}|${away}`) return;
    this.teams = `${home}|${away}`;
    const shades = (c) => [0.18, 0.3, 0.42].map((k) => mix(c, STAND, k));
    this.palette = [...shades(home), ...shades(away), ...NEUTRAL];
  }

  // A meters message from the server: the only input.
  meters(m, now) {
    const a = m?.atmosphere ?? {};
    const level = a.available && Number.isFinite(a.level) ? clamp(a.level) : 0;
    const attack = Number.isFinite(a.attack) ? clamp(a.attack) : 0;
    const focus = attack > 0 ? goalX(this.crowd, a.attack_team, m.period) : null;
    const score = m?.score;
    if (score && this.score) {
      for (const team of ["home", "away"]) {
        if (score[team] > this.score[team]) {
          this.celebration = { team, focus: goalX(this.crowd, team, m.period), until: now + CELEBRATE_S };
        }
      }
    }
    if (score) this.score = { home: score.home, away: score.away };
    this.input = { level, attack, team: focus == null ? null : a.attack_team, focus };
    this.retarget(now);
  }

  target(g) {
    const i = this.input;
    if (!i || !this.enabled) return 0;
    let t = smooth((i.level - 0.2) / 0.8) * 0.6;
    if (i.focus != null) {
      // Fans nearest the attacked goal react first and most; a louder ground reacts wider.
      const reach = 0.3 + 0.35 * i.level, d = Math.abs(g.cx - i.focus) / this.crowd.length;
      const fan = g.team === i.team ? 1 : g.team ? 0.35 : 0.6;
      t += i.attack * Math.max(0, 1 - d / reach) * fan * 0.55;
    }
    const c = this.celebration;
    if (c) t = g.team === c.team ? 1 : g.team ? Math.min(t, 0.12) : Math.max(t, 0.45);
    return clamp(t);
  }

  focus() { return this.celebration ? this.celebration.focus : this.input?.focus ?? null; }

  retarget(now) {
    const focus = this.focus();
    for (const g of this.crowd.groups) {
      const t = this.target(g);
      if (t > g.armed + 0.02) {
        // Rises travel outwards from the action, so neighbouring groups follow a moment later.
        if (g.pending == null) g.armAt = now + g.jitter + (focus == null ? 0 : Math.abs(g.cx - focus) / WAVE_PX_S);
        g.pending = t;
      } else { g.armed = t; g.pending = null; }
    }
  }

  step(now, dt) {
    if (this.celebration && now >= this.celebration.until) { this.celebration = null; this.retarget(now); }
    const up = 1 - Math.exp(-clamp(dt, 0, 0.25) / RISE_S), down = 1 - Math.exp(-clamp(dt, 0, 0.25) / FALL_S);
    for (const g of this.crowd.groups) {
      if (g.pending != null && now >= g.armAt) { g.armed = g.pending; g.pending = null; }
      g.excitement += (g.armed - g.excitement) * (g.armed > g.excitement ? up : down);
    }
  }

  celebrating(g) { return !!this.celebration && g.team === this.celebration.team; }
}

// Pose of one fan: 0..1 standing and arms raised, from its group's excitement.
export function pose(fan, excitement) {
  return { stand: smooth((excitement - fan.th * 0.85) / 0.18),
           arms: smooth((excitement - 0.5 - fan.th * 0.45) / 0.15) };
}

function mix(hex, other, k) {
  const p = (h) => { const n = parseInt(String(h).replace("#", "").padEnd(6, "0").slice(0, 6), 16) || 0; return [n >> 16, (n >> 8) & 255, n & 255]; };
  const a = p(hex), b = p(other);
  return `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * k)).join(",")})`;
}

/** Draws the stands and fans in a handful of batched paths. */
export function drawCrowd(ctx, reactions, now, { reduceMotion = false } = {}) {
  const { fans, groups, bands } = reactions.crowd;
  const palette = reactions.palette ?? [...NEUTRAL, ...NEUTRAL, ...NEUTRAL];
  ctx.fillStyle = "rgba(10,20,27,0.62)";
  ctx.beginPath();
  for (const [x, y, w, h] of bands) ctx.rect(x, y, w, h);
  ctx.fill();
  const n = fans.length;
  const px = reactions._px ??= new Float32Array(n), py = reactions._py ??= new Float32Array(n);
  const sc = reactions._sc ??= new Float32Array(n), ar = reactions._ar ??= new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const f = fans[i], g = groups[f.g], { stand, arms } = pose(f, g.excitement);
    let bounce = 0;
    if (!reduceMotion) {
      // Celebrating groups jump together; each group a beat apart. Calm fans barely shift.
      if (reactions.celebrating(g)) bounce = Math.max(0, Math.sin(now * 10.5 + g.phase * 2.4)) * arms;
      const sway = 0.35 * Math.sin(now * 0.7 + f.phase) * (1 - stand);
      px[i] = f.x + f.ny * sway; py[i] = f.y + f.nx * sway;
    } else { px[i] = f.x; py[i] = f.y; }
    // Standing fans look larger from above and lean towards the pitch.
    const lean = 2.2 * stand;
    px[i] += f.nx * lean; py[i] += f.ny * lean;
    sc[i] = 1 + 0.28 * stand + 0.12 * bounce;
    ar[i] = arms;
  }
  for (let tone = 0; tone < palette.length; tone++) {
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const f = fans[i];
      if (f.tone !== tone) continue;
      const along = f.nx === 0, rx = (along ? 5.3 : 3.4) * sc[i], ry = (along ? 3.4 : 5.3) * sc[i];
      ctx.moveTo(px[i] + rx, py[i]); ctx.ellipse(px[i], py[i], rx, ry, 0, 0, Math.PI * 2);
    }
    ctx.fillStyle = palette[tone];
    ctx.fill();
  }
  ctx.beginPath();
  for (let i = 0; i < n; i++) {
    if (ar[i] < 0.05) continue;
    // Raised arms seen from above: a V opening out from the shoulders.
    const f = fans[i], along = f.nx === 0, out = (1 + 2.6 * ar[i]) * sc[i], fwd = (1 + 2 * ar[i]) * sc[i];
    for (const s of [-1, 1]) {
      const bx = px[i] + (along ? s * 4 * sc[i] : 0), by = py[i] + (along ? 0 : s * 4 * sc[i]);
      ctx.moveTo(bx, by);
      ctx.lineTo(bx + (along ? s * out : 0) + f.nx * fwd, by + (along ? 0 : s * out) + f.ny * fwd);
    }
  }
  ctx.lineWidth = 1.8; ctx.lineCap = "round"; ctx.strokeStyle = "rgba(214,184,152,0.9)";
  ctx.stroke();
  for (let hair = 0; hair < HAIR.length; hair++) {
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const f = fans[i];
      if (f.hair !== hair) continue;
      const r = 2.4 * sc[i], hx = px[i] + f.nx * 0.6, hy = py[i] + f.ny * 0.6;
      ctx.moveTo(hx + r, hy); ctx.arc(hx, hy, r, 0, Math.PI * 2);
    }
    ctx.fillStyle = HAIR[hair];
    ctx.fill();
  }
}
