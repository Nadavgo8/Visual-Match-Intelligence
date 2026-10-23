import { bannerIcon } from "./icons.js";
import { SyntheticAudio } from "./audio.js";
import { edgePresentation } from "./overlay-state.mjs";
import { MatchScreen } from "./match-screen.mjs";
import { MatchRenderer } from "./match-renderer.mjs";

const params = new URLSearchParams(location.search);
const room = params.get("room") || "demo";
const $ = (id) => document.getElementById(id);
const canvas = $("pitch");
const screen = new MatchScreen();
const renderer = new MatchRenderer(canvas);
let state = null, teams = null;
const audio = new SyntheticAudio();

$("room-code").textContent = room;
$("app-link").href = `/app?room=${encodeURIComponent(room)}`;

const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/${encodeURIComponent(room)}?role=tv`);
const send = (m) => ws.readyState === 1 && ws.send(JSON.stringify(m));
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.type === "state") onState(m);
  else if (m.type === "frame" && screen.frame(m, performance.now())) renderMarker();
  else if (m.type === "banner") onBanner(m);
  else if (m.type === "meters") onMeters(m);
  else if (m.type === "trace") onTrace(m);
};
ws.onclose = () => { screen.freeze(performance.now()); $("agents").textContent = "disconnected, reload to reconnect"; };

function onState(s) {
  if (screen.sync(s, performance.now())) clearMarkerElement();
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
  if (!screen.accept(b)) return;
  if (!b.update) audio.whistle(b.banner);
  renderMarker();
}
function renderMarker() {
  const cue = screen.marker(), el = $("event-marker");
  el.hidden = !cue;
  if (!cue) return;
  if (el.dataset.cue === cue.cue_id && el.dataset.kind === cue.banner) return;
  el.dataset.cue = cue.cue_id; el.dataset.kind = cue.banner;
  $("event-icon").innerHTML = bannerIcon(cue.banner);
  $("event-label").textContent = cue.label;
}
function clearMarkerElement() {
  $("event-marker").hidden = true;
  $("event-marker").removeAttribute("data-cue");
}
function jump(command) { screen.beginJump(); clearMarkerElement(); send(command); }

// Football rendering and accessibility overlays have independent lifecycles.
let fpsStart = 0, fpsCount = 0, drawMs = 0;
function render(now) {
  const frame = screen.sample(now);
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
