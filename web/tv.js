import { bannerIcon } from "./icons.js";
import { SyntheticAudio } from "./audio.js";
import { MarkerState, edgePresentation } from "./overlay-state.mjs";
import { openSession, hostTokenStore } from "./session.mjs";

const params = new URLSearchParams(location.search);
const room = params.get("room") || "demo";
const $ = (id) => document.getElementById(id);
const canvas = $("pitch");
const ctx = canvas.getContext("2d");
const W = canvas.width, H = canvas.height;
const PX = 105, PY = 68, M = 60; // pitch metres, margin px
const sx = (x) => M + (x / PX) * (W - 2 * M);
const sy = (y) => H - M - (y / PY) * (H - 2 * M); // y up, like the data

let state = null, frame = null, teams = null;
const audio = new SyntheticAudio();
const markers = new MarkerState();
let liveTime = 0, waitingForState = false;

$("room-code").textContent = room;
$("app-link").href = `/app?room=${encodeURIComponent(room)}`;

let isHost = false;
const session = openSession({ room, role: "tv", hostToken: hostTokenStore(room), onMessage, onStatus });
const send = (m) => session.send(m);
function onMessage(m) {
  if (m.type === "snapshot") {
    waitingForState = true; isHost = m.host;
    onState(m.state);
    if (m.meters) onMeters(m.meters);
  }
  else if (m.type === "state") onState(m);
  else if (m.type === "frame" && !waitingForState) { frame = m; liveTime = m.t; renderMarker(); }
  else if (m.type === "banner") onBanner(m);
  else if (m.type === "meters") onMeters(m);
  else if (m.type === "trace") onTrace(m);
  else if (m.type === "error") $("agents").textContent = m.message;
}
function onStatus(s) {
  // No frames arrive while disconnected; never animate play that wasn't delivered.
  if (s === "disconnected") { clearTransient(); $("agents").textContent = "disconnected, reconnecting…"; }
}
function hostControls() {
  for (const el of document.querySelectorAll("#play, #speed, #scrub, #seed, #new, #chapters button")) el.disabled = !isHost;
}

function onState(s) {
  if (waitingForState || (state && (state.seed !== s.seed || s.t < liveTime - 0.01 || Math.abs(s.t - liveTime) > Math.max(3, s.speed * 0.3)))) clearTransient();
  waitingForState = false; liveTime = s.t;
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
    b.onclick = () => jump({ cmd: "seek", t: c.t });
    ch.appendChild(b);
  }
  hostControls();
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
  $("mom-label").textContent = "Momentum";
  $("mom-fill").parentElement.setAttribute("aria-label", `Seven-minute momentum: home ${Math.round(share * 100)} percent`);
  const a = m.atmosphere, view = edgePresentation(a), el = $("atmosphere-edges");
  el.style.setProperty("--edge-color", view.color);
  el.style.setProperty("--edge-fill", `${view.height}%`);
  el.style.setProperty("--edge-brightness", String(view.brightness));
  el.dataset.available = String(view.available);
  el.setAttribute("aria-label", `${view.label}; both sides show the same atmosphere`);
  el.title = view.label;
  $("atmo-label").title = a.why;
  $("atmo-label").textContent = view.label;
  audio.crowd(a.crowd ?? 0);
}

function onBanner(b) {
  if (waitingForState || !markers.accept(b, liveTime)) return;
  if (!b.update) audio.whistle(b.banner);
  renderMarker();
}
function renderMarker() {
  const cue = markers.at(liveTime), el = $("event-marker");
  el.hidden = !cue;
  if (!cue) return;
  if (el.dataset.cue === cue.cue_id && el.dataset.kind === cue.banner) return;
  el.dataset.cue = cue.cue_id; el.dataset.kind = cue.banner;
  $("event-icon").innerHTML = bannerIcon(cue.banner);
  $("event-label").textContent = cue.label;
}
function clearTransient() {
  markers.clear(); $("event-marker").hidden = true;
  $("event-marker").removeAttribute("data-cue");
  frame = null; shown = null;
}
function jump(command) { clearTransient(); waitingForState = true; send(command); }

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
$("scrub").onchange = (e) => { scrubbing = false; jump({ cmd: "seek", t: Number(e.target.value) }); };
$("overlay-on").onchange = (e) => $("overlay").classList.toggle("off", !e.target.checked);
$("sound-on").onchange = (e) => { audio.unlock(); audio.enabled = e.target.checked; if (!e.target.checked) audio.crowd(0); };
$("new").onclick = () => jump({ cmd: "new_match", seed: Number($("seed").value) });

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

// Optional settings; defaults work without a calibration step or storage access.
$("reduce-motion").checked = matchMedia("(prefers-reduced-motion: reduce)").matches;
function displaySettings() {
  $("stage").style.setProperty("--signal-intensity", $("signal-intensity").value);
  $("stage").style.setProperty("--symbol-size", $("symbol-size").value);
  $("stage").classList.toggle("reduce-motion", $("reduce-motion").checked);
}
for (const id of ["signal-intensity", "symbol-size", "reduce-motion"]) $(id).addEventListener("input", displaySettings);
displaySettings();
