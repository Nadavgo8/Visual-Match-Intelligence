import { bannerIcon } from "./icons.js";
import { SyntheticAudio } from "./audio.js";
import { renderAtmosphere, renderMomentum, renderReplayTime } from "./meter-view.mjs?v=3.3";
import { MatchScreen } from "./match-screen.mjs?v=3.2";
import { createRenderer } from "./renderer-host.mjs?v=3.11";
import { openSession, hostTokenStore } from "./session.mjs?v=1.1";
import { prependTrace, clearTrace } from "./trace-view.mjs?v=3.3";

const params = new URLSearchParams(location.search);
const room = params.get("room") || "demo";
const $ = (id) => document.getElementById(id);
const screen = new MatchScreen(resetVisualState);
const renderer = await createRenderer($("pitch"), $("renderer-note"));
let state = null, teams = null;
const audio = new SyntheticAudio();

$("room-code").textContent = room;
$("app-link").href = `/app?room=${encodeURIComponent(room)}`;

let isHost = false;
const session = openSession({ room, role: "tv", hostToken: hostTokenStore(room), onMessage, onStatus });
const send = (m) => session.send(m);
function onMessage(m) {
  if (m.type === "snapshot") {
    isHost = m.host;
    $("connection-note").textContent = "";
    onState({ ...m.state, run_id: m.run_id }, true);
    if (m.meters) onMeters(m.meters);
  }
  else if (m.type === "state") onState(m);
  else if (m.type === "frame" && screen.frame(m, performance.now())) renderMarker();
  else if (m.type === "banner") onBanner(m);
  else if (m.type === "meters") onMeters(m);
  else if (m.type === "trace") onTrace(m);
  else if (m.type === "error") $("agents").textContent = m.message;
}
function onStatus(s) {
  if (s === "disconnected") {
    screen.freeze(performance.now());
    isHost = false; hostControls();
    $("connection-note").textContent = "Connection lost. Replay paused; reconnecting…";
    $("agents").textContent = "disconnected, reconnecting…";
  }
}
function hostControls() {
  for (const el of document.querySelectorAll("#play, #speed, #scrub, #seed, #new, #chapters button")) el.disabled = !isHost;
}

function onState(s, snapshot = false) {
  const now = performance.now();
  if (snapshot) screen.snapshot(s, now); else screen.sync(s, now);
  state = s;
  teams = s.teams;
  document.documentElement.style.setProperty("--home", teams.home.colour);
  document.documentElement.style.setProperty("--away", teams.away.colour);
  $("sb-home").textContent = teams.home.short;
  $("sb-away").textContent = teams.away.short;
  $("play").textContent = s.playing ? "❚❚ Pause" : "▶ Play";
  $("speed").value = String(s.speed);
  $("scrub").max = Math.floor(s.duration);
  renderReplayTime($("scrub"), s.t, scrubbing);
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
  renderReplayTime($("scrub"), m.t, scrubbing);
  renderMomentum($("mom-fill"), m.momentum?.home_index);
  const a = m.atmosphere;
  renderAtmosphere($("atmosphere-edges"), $("atmo-label"), a);
  audio.crowd(a?.crowd ?? 0);
  renderer.setAtmosphere(a);
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
function resetVisualState() {
  scrubbing = false;
  clearTrace($("trace-list"), $("trace-sum"));
  clearMarkerElement();
  renderAtmosphere($("atmosphere-edges"), $("atmo-label"), null);
  renderMomentum($("mom-fill"), null);
  renderer.setAtmosphere(null); audio.crowd(0);
}
function jump(command) { screen.beginJump(); send(command); }

// Football rendering and accessibility overlays have independent lifecycles.
let fpsStart = 0, fpsCount = 0, drawMs = 0;
function render(now) {
  const frame = screen.sample(now);
  const drawStart = performance.now();
  renderer.draw(frame, teams);
  const canvas = renderer.canvas;
  drawMs += performance.now() - drawStart;
  if (frame) canvas.dataset.simTime = frame.t.toFixed(3);
  else delete canvas.dataset.simTime;
  fpsCount++;
  if (now - fpsStart >= 2000) {
    $("render-status").textContent = `${Math.round(fpsCount * 1000 / (now - fpsStart))} FPS | ${(drawMs / fpsCount).toFixed(1)} ms draw | ${renderer.mode}`;
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
  $("trace-sum").textContent = `${c.in} feed events in · ${c.banner} banners · ${c.feed} feed items · `
    + `${c.analysis} analyses · ${c.skip} left out`;
  const ol = $("trace-list");
  prependTrace(ol, m.recent);
}

// Optional settings; defaults work without a calibration step or storage access.
$("reduce-motion").checked = matchMedia("(prefers-reduced-motion: reduce)").matches;
function displaySettings() {
  $("stage").style.setProperty("--signal-intensity", $("signal-intensity").value);
  $("stage").style.setProperty("--symbol-size", $("symbol-size").value);
  $("stage").classList.toggle("reduce-motion", $("reduce-motion").checked);
  renderer.setReducedMotion($("reduce-motion").checked);
}
$("render-quality").onchange = e => renderer.setQuality(e.target.value);
$("camera-view").onchange = e => renderer.setCamera(e.target.value);
window.addEventListener("pagehide", event => { if (!event.persisted) renderer.dispose(); });
for (const id of ["signal-intensity", "symbol-size", "reduce-motion"]) $(id).addEventListener("input", displaySettings);
displaySettings();
