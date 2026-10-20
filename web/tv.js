import { bannerIcon } from "./icons.js";
import { SyntheticAudio } from "./audio.js";

const params = new URLSearchParams(location.search);
const room = params.get("room") || "demo";
const $ = (id) => document.getElementById(id);
const canvas = $("pitch");
const ctx = canvas.getContext("2d");
const W = canvas.width, H = canvas.height;
const PX = 105, PY = 68, M = 60; // pitch metres, margin px
const sx = (x) => M + (x / PX) * (W - 2 * M);
const sy = (y) => H - M - (y / PY) * (H - 2 * M); // y up, like the data
const MOOD = { calm: "Calm", cheering: "Cheering", tension: "Tension", eruption: "Eruption" };
const WAVES = {
  calm: "M2 8H38",
  cheering: "M2 8q4.5-6 9 0t9 0t9 0t9 0",
  tension: "M2 8h8l3-5l4 10l4-10l4 10l3-5h8",
  eruption: "M2 14L8 4L14 12L20 2L26 12L32 4L38 14",
};

let state = null, frame = null, teams = null;
const audio = new SyntheticAudio();
const live = new Map(); // cue_id -> {el, timer}

$("room-code").textContent = room;
$("app-link").href = `/app?room=${encodeURIComponent(room)}`;

const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/${encodeURIComponent(room)}?role=tv`);
const send = (m) => ws.readyState === 1 && ws.send(JSON.stringify(m));
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.type === "state") onState(m);
  else if (m.type === "frame") frame = m;
  else if (m.type === "banner") onBanner(m);
  else if (m.type === "meters") onMeters(m);
  else if (m.type === "trace") onTrace(m);
};
ws.onclose = () => { $("agents").textContent = "disconnected, reload to reconnect"; };

function onState(s) {
  state = s;
  teams = s.teams;
  document.documentElement.style.setProperty("--home", teams.home.colour);
  document.documentElement.style.setProperty("--away", teams.away.colour);
  $("sb-home").textContent = teams.home.short;
  $("sb-away").textContent = teams.away.short;
  $("play").textContent = s.playing ? "❚❚ Pause" : "▶ Play";
  $("speed").value = String(s.speed);
  $("scrub").max = Math.floor(s.duration);
  $("seed").value = s.seed;
  $("agents").textContent = s.agents === "foundry" ? `Microsoft Foundry (${s.model})` : "local (offline)";
  const ch = $("chapters");
  ch.innerHTML = "";
  for (const c of s.chapters) {
    const b = document.createElement("button");
    b.textContent = `${c.clock} ${c.label}`;
    b.onclick = () => send({ cmd: "seek", t: c.t });
    ch.appendChild(b);
  }
  scoreBug(s.score, s.clock);
}

function scoreBug(score, clock) {
  $("sb-score").textContent = `${score.home}–${score.away}`;
  $("sb-clock").textContent = clock;
  $("time").textContent = clock;
}

function onMeters(m) {
  scoreBug(m.score, m.clock);
  if (!scrubbing) $("scrub").value = Math.floor(m.t);
  const share = m.momentum.home_index;
  $("mom-fill").style.width = `${(share * 100).toFixed(1)}%`;
  const v = m.momentum.value;
  $("mom-label").textContent = Math.abs(v) < 0.3 ? "Momentum: even"
    : `Momentum: ${v > 0 ? teams.home.short : teams.away.short} on top`;
  const a = m.atmosphere;
  const el = $("atmo");
  const prevMood = el.dataset.mood;
  el.className = `atmo ${a.mood}`;
  el.dataset.mood = a.mood;
  el.style.setProperty("--mood", `var(--${a.mood})`);
  el.style.setProperty("--lvl", ((a.level5 - 1) / 4).toFixed(2));
  el.querySelectorAll(".atmo-meter i").forEach((i) => i.classList.toggle("on", Number(i.dataset.l) <= a.level5));
  $("atmo-label").textContent = MOOD[a.mood];
  $("atmo-path").setAttribute("d", WAVES[a.mood]);
  el.title = `${MOOD[a.mood]}: ${a.why} (level ${a.level5}/5)`;
  if (prevMood === "eruption" && a.mood === "eruption") el.style.animation = "none";
  else el.style.animation = "";
  audio.crowd(a.level);
}

function onBanner(b) {
  const slot = document.querySelector(`[data-slot="${b.slot}"]`);
  if (!slot) return;
  const prev = live.get(b.cue_id);
  if (prev) { clearTimeout(prev.timer); prev.el.remove(); }
  const el = document.createElement("div");
  el.className = `banner ${b.banner}`;
  el.innerHTML = `${bannerIcon(b.banner)}<span>${b.label}</span>${b.detail ? `<span class="detail">${b.detail}</span>` : ""}`;
  el.title = b.why;
  slot.replaceChildren(el);
  if (!b.update && b.banner !== "crowd") audio.whistle(b.banner);
  const secs = Math.max(2.5, (b.t_end - b.t_start)) / Math.max(1, Math.sqrt(state?.speed || 1));
  const timer = setTimeout(() => {
    el.classList.add("out");
    setTimeout(() => el.remove(), 300);
    live.delete(b.cue_id);
  }, secs * 1000);
  live.set(b.cue_id, { el, timer });
}

// ---------- pitch ----------
function drawPitch() {
  for (let i = 0; i < 12; i++) {
    ctx.fillStyle = i % 2 ? "#226b35" : "#1f6431";
    ctx.fillRect((W / 12) * i, 0, W / 12 + 1, H);
  }
  ctx.strokeStyle = "rgba(255,255,255,0.75)";
  ctx.lineWidth = 3;
  ctx.strokeRect(sx(0), sy(PY), sx(PX) - sx(0), sy(0) - sy(PY));
  line(52.5, 0, 52.5, PY);
  ctx.beginPath(); ctx.arc(sx(52.5), sy(34), (9.15 / PX) * (W - 2 * M), 0, 2 * Math.PI); ctx.stroke();
  for (const [x0, dir] of [[0, 1], [PX, -1]]) {
    rect(x0, 13.84, x0 + dir * 16.5, 54.16);
    rect(x0, 24.84, x0 + dir * 5.5, 43.16);
    dot(x0 + dir * 11, 34, 3, "rgba(255,255,255,0.8)");
    ctx.lineWidth = 5; line(x0, 30.34, x0, 37.66); ctx.lineWidth = 3;
  }
}
function line(x1, y1, x2, y2) { ctx.beginPath(); ctx.moveTo(sx(x1), sy(y1)); ctx.lineTo(sx(x2), sy(y2)); ctx.stroke(); }
function rect(x1, y1, x2, y2) { ctx.strokeRect(Math.min(sx(x1), sx(x2)), sy(Math.max(y1, y2)), Math.abs(sx(x2) - sx(x1)), Math.abs(sy(y2) - sy(y1))); }
function dot(x, y, r, c) { ctx.beginPath(); ctx.arc(sx(x), sy(y), r, 0, 2 * Math.PI); ctx.fillStyle = c; ctx.fill(); }

let shown = null;
function render() {
  drawPitch();
  if (frame && teams) {
    // ease towards the latest frame so 10 Hz updates look smooth
    if (!shown) shown = structuredClone(frame);
    const k = 0.35;
    const map = new Map(shown.players.map((p) => [p.id, p]));
    shown.players = frame.players.map((p) => {
      const q = map.get(p.id);
      return q ? { ...p, x: q.x + (p.x - q.x) * k, y: q.y + (p.y - q.y) * k } : p;
    });
    shown.ball = [shown.ball[0] + (frame.ball[0] - shown.ball[0]) * k, shown.ball[1] + (frame.ball[1] - shown.ball[1]) * k];
    for (const p of shown.players) {
      const home = p.team === "home";
      dot(p.x, p.y, 15, home ? teams.home.colour : teams.away.colour);
      ctx.lineWidth = 2; ctx.strokeStyle = "rgba(0,0,0,0.5)"; ctx.stroke();
      ctx.fillStyle = home ? "#fff" : "#1a1a1a";
      ctx.font = "700 14px Inter, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(p.n, sx(p.x), sy(p.y) + 1);
    }
    dot(shown.ball[0] + 0.25, shown.ball[1] - 0.25, 7, "rgba(0,0,0,0.35)");
    dot(shown.ball[0], shown.ball[1], 7, "#fff");
  }
  requestAnimationFrame(render);
}
requestAnimationFrame(render);

// ---------- controls ----------
let scrubbing = false;
$("play").onclick = () => { audio.unlock(); send({ cmd: state?.playing ? "pause" : "play" }); };
$("speed").onchange = (e) => send({ cmd: "speed", value: Number(e.target.value) });
$("scrub").oninput = () => { scrubbing = true; };
$("scrub").onchange = (e) => { scrubbing = false; send({ cmd: "seek", t: Number(e.target.value) }); };
$("overlay-on").onchange = (e) => $("overlay").classList.toggle("off", !e.target.checked);
$("sound-on").onchange = (e) => { audio.unlock(); audio.enabled = e.target.checked; if (!e.target.checked) audio.crowd(0); };
$("new").onclick = () => send({ cmd: "new_match", seed: Number($("seed").value) });

// ---------- engine trace: what was shown, and what was left out and why ----------
function onTrace(m) {
  const c = m.counts;
  $("trace-sum").innerHTML = `<b>${c.in}</b> feed events in · <b>${c.banner}</b> banners · <b>${c.feed}</b> feed items · `
    + `<b>${c.analysis}</b> analyses · <b>${c.skip}</b> left out`;
  const ol = $("trace-list");
  for (const d of m.recent) {
    const li = document.createElement("li");
    li.innerHTML = `${d.clock} <span>${d.decision}</span>: ${d.why}`;
    ol.prepend(li);
  }
  while (ol.children.length > 40) ol.lastChild.remove();
}
