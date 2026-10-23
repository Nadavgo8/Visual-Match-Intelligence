import { bannerIcon } from "./icons.js";
import { SyntheticAudio } from "./audio.js";
import { atmospherePresentation } from "./atmosphere.mjs";
import { FrameTimeline } from "./match-motion.mjs";
import { MatchRenderer } from "./match-renderer.mjs";

const params = new URLSearchParams(location.search);
const room = params.get("room") || "demo";
const $ = (id) => document.getElementById(id);
const canvas = $("pitch");
const timeline = new FrameTimeline();
const renderer = new MatchRenderer(canvas);
let state = null, teams = null;
const audio = new SyntheticAudio();
const live = new Map(); // cue_id -> {el, timer}

$("room-code").textContent = room;
$("app-link").href = `/app?room=${encodeURIComponent(room)}`;

const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/${encodeURIComponent(room)}?role=tv`);
const send = (m) => ws.readyState === 1 && ws.send(JSON.stringify(m));
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.type === "state") onState(m);
  else if (m.type === "frame") timeline.push(m, performance.now());
  else if (m.type === "banner") onBanner(m);
  else if (m.type === "meters") onMeters(m);
  else if (m.type === "trace") onTrace(m);
};
ws.onclose = () => { timeline.freeze(performance.now()); $("agents").textContent = "disconnected, reload to reconnect"; };

function onState(s) {
  timeline.sync(s, performance.now());
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
  const view = atmospherePresentation(a);
  el.className = "atmo";
  el.style.setProperty("--mood", view.color);
  el.style.setProperty("--lvl", String(view.value ?? 0.5));
  el.querySelectorAll(".atmo-meter i").forEach((i) => i.classList.toggle("on", Number(i.dataset.l) <= a.level5));
  $("atmo-label").textContent = view.label;
  $("atmo-path").setAttribute("d", "M2 8H38");
  el.title = `${view.label}: ${a.why}`;
  audio.crowd(a.crowd ?? 0);
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

// Football rendering and accessibility overlays have independent lifecycles.
let fpsStart = 0, fpsCount = 0, drawMs = 0;
function render(now) {
  const frame = timeline.sample(now);
  const drawStart = performance.now();
  renderer.draw(frame, teams);
  drawMs += performance.now() - drawStart;
  if (frame) canvas.dataset.simTime = frame.t.toFixed(3);
  fpsCount++;
  if (now - fpsStart >= 2000) {
    $("render-status").textContent = `${Math.round(fpsCount * 1000 / (now - fpsStart))} FPS | ${(drawMs / fpsCount).toFixed(1)} ms draw | 2D source tracking`;
    fpsCount = 0; drawMs = 0; fpsStart = now;
  }
  requestAnimationFrame(render);
}
requestAnimationFrame(render);
function jump(command) { timeline.beginJump(); send(command); }

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
