import { bannerIcon } from "./icons.js";
import { SyntheticAudio } from "./audio.js";
import { renderAtmosphere, renderMomentum, renderReplayTime } from "./meter-view.mjs?v=3.3";
import { MatchScreen } from "./match-screen.mjs?v=3.2";
import { createRenderer } from "./renderer-host.mjs?v=3.15";
import { openSession, hostTokenStore } from "./session.mjs?v=1.1";
import { prependTrace, clearTrace } from "./trace-view.mjs?v=3.3";
import {MeterTimeline} from "./meter-timeline.mjs?v=3.15";
import {FrameMetrics} from "./frame-metrics.mjs?v=3.16";
import {LivePerformance} from "./live-performance.mjs?v=3.17";

const params = new URLSearchParams(location.search);
const room = params.get("room") || "demo";
const $ = (id) => document.getElementById(id);
const meterTimeline=new MeterTimeline();let appliedMeters=null;
const livePerformance=new LivePerformance();
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
  const started=livePerformance.capture.active?performance.now():null;
  let acceptedFrame=false;
  try {
  if (m.type === "snapshot") {
    isHost = m.host;
    $("connection-note").textContent = "";
    onState({ ...m.state, run_id: m.run_id }, true);
    if (m.meters) onMeters({...m.meters,run_id:m.run_id});
  }
  else if (m.type === "state") onState(m);
  else if (m.type === "frame") {acceptedFrame=screen.frame(m,performance.now());if(acceptedFrame)renderMarker();}
  else if (m.type === "banner") onBanner(m);
  else if (m.type === "meters") onMeters(m);
  else if (m.type === "trace") onTrace(m);
  else if (m.type === "error") {$("agents").textContent = m.message;livePerformance.invalidate(`Server error: ${m.message}`);}
  } finally {if(started!==null&&(m.type!=="frame"||acceptedFrame))livePerformance.message(m,performance.now(),performance.now()-started);}
}
function onStatus(s) {
  if (s === "disconnected") {
    livePerformance.invalidate("WebSocket disconnected during the measurement.");
    screen.freeze(performance.now());
    isHost = false; hostControls();
    $("connection-note").textContent = "Connection lost. Replay paused; reconnecting…";
    $("agents").textContent = "disconnected, reconnecting…";
  }
}
function hostControls() {
  for (const el of document.querySelectorAll("#play, #speed, #scrub, #seed, #new, #chapters button, #live-perf")) el.disabled = !isHost;
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
  if(livePerformance.state(s)){send({cmd:"speed",value:1});send({cmd:"play"});}
}

function scoreBug(score, clock) {
  $("sb-score").textContent = `${score.home}–${score.away}`;
  $("sb-clock").textContent = clock;
  $("time").textContent = clock;
}

function onMeters(m) {
  meterTimeline.push(m,state?.run_id);
}
function applyMeters(m) {
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
  meterTimeline.reset();appliedMeters=null;
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
const frameMetrics = new FrameMetrics();
function render(now) {
  const frame = screen.sample(now);
  const meters=frame ? meterTimeline.sample(frame.t,frame.run_id) : null;
  if(meters!==appliedMeters){
    if(meters)applyMeters(meters);
    else {renderAtmosphere($("atmosphere-edges"),$("atmo-label"),null);renderer.setAtmosphere(null);audio.crowd(0);}
    appliedMeters=meters;
  }
  const drawStart = performance.now();
  renderer.draw(frame, teams);
  const canvas = renderer.canvas;
  const drawElapsed=performance.now()-drawStart;
  const liveResult=livePerformance.phase==="seek"||livePerformance.phase==="play"||livePerformance.phase==="capture" ? livePerformance.observe(now,{frame,state,drawMs:drawElapsed,environment:{
    visible:document.visibilityState==="visible",focused:document.hasFocus(),viewport:[innerWidth,innerHeight],
    css:[canvas.clientWidth,canvas.clientHeight],buffer:[canvas.width,canvas.height],dpr:devicePixelRatio,
    renderer:renderer.mode,quality:canvas.dataset.quality,camera:canvas.dataset.camera,run:frame?.run_id,speed:state?.speed,
    visualSignals:$("overlay-on").checked,reducedMotion:$("reduce-motion").checked}}):null;
  if(liveResult){
    liveResult.scene={actors:canvas.dataset.actors,drawCalls:canvas.dataset.drawCalls,triangles:canvas.dataset.triangles};
    $("live-perf-result").textContent=JSON.stringify(liveResult,null,2);$("live-perf-result").hidden=false;
    $("copy-live-perf").disabled=false;$("live-perf-status").textContent=liveResult.valid
      ? `Finished: ${liveResult.fps.toFixed(1)} render submissions FPS. Result is not proof of presented frames.`:liveResult.reason;
    send({cmd:"pause"});
  }
  frameMetrics.observe(now, !!frame && !!state?.playing && document.visibilityState === "visible" && document.hasFocus(),
    `${frame?.run_id}/${renderer.mode}/${canvas.dataset.quality}/${canvas.dataset.camera}/${canvas.width}x${canvas.height}`);
  drawMs += drawElapsed;
  if (frame) canvas.dataset.simTime = frame.t.toFixed(3);
  else delete canvas.dataset.simTime;
  fpsCount++;
  if (now - fpsStart >= 2000) {
    $("render-status").textContent = `${Math.round(fpsCount * 1000 / (now - fpsStart))} FPS | ${(drawMs / fpsCount).toFixed(1)} ms draw | ${renderer.mode}`;
    const cadence = frameMetrics.report();
    $("frame-metrics").textContent = cadence
      ? `${(cadence.durationMs / 1000).toFixed(1)}s active visible window: ${cadence.fps.toFixed(1)} FPS · frame p50 ${cadence.p50Ms.toFixed(1)} / p95 ${cadence.p95Ms.toFixed(1)} / max ${cadence.maxMs.toFixed(1)} ms`
      : "Cadence: need 10 seconds playing in a visible, focused tab with unchanged display settings.";
    const pct=value=>Number.isFinite(value) ? `${Math.round(value*100)}%` : "unavailable";
    const a=meters?.atmosphere,available=canvas.dataset.crowdAvailable==="true";
    $("scene-diagnostics").textContent=`Source ${frame?.t?.toFixed(2) ?? "—"}s · run ${frame?.run_id ?? "—"} · C ${pct(a?.crowd)} · T ${pct(a?.attack)} · A ${pct(a?.level)} · pose targets (seated / seated raised / standing raised): `
      +(available ? [canvas.dataset.crowdSeated,canvas.dataset.crowdSeatedRaised,canvas.dataset.crowdStanding].map(v=>pct(Number(v))).join(" / ") : "unavailable");
    fpsCount = 0; drawMs = 0; fpsStart = now;
  }
  requestAnimationFrame(render);
}
requestAnimationFrame(render);

// ---------- controls ----------
let scrubbing = false;
let liveDprQuery=null;
const invalidateLiveDpr=()=>livePerformance.invalidate("Device pixel ratio changed.");
$("live-perf").onclick=()=>{
  if(!isHost||livePerformance.phase==="capture"||livePerformance.phase==="seek"||livePerformance.phase==="play")return;
  $("render-quality").value="high";renderer.setQuality("high");$("camera-view").value="broadcast";renderer.setCamera("broadcast");
  $("overlay-on").checked=true;$("overlay").classList.remove("off");
  liveDprQuery?.removeEventListener("change",invalidateLiveDpr);liveDprQuery=matchMedia(`(resolution: ${devicePixelRatio}dppx)`);
  liveDprQuery.addEventListener("change",invalidateLiveDpr);
  livePerformance.prepare(state.seed,performance.now());$("live-perf-result").hidden=true;$("copy-live-perf").disabled=true;
  $("live-perf-status").textContent="Preparing live replay at 10:00. Keep the tab visible; warmup + measurement takes about 23 seconds.";
  jump({cmd:"seek",t:600});
};
$("copy-live-perf").onclick=async()=>{try{await navigator.clipboard.writeText($("live-perf-result").textContent);$("live-perf-status").textContent="Live result copied.";}
  catch{$("live-perf-status").textContent="Copy unavailable; select the visible JSON result.";}};
window.addEventListener("blur",()=>livePerformance.invalidate("The tab lost focus."));
window.addEventListener("resize",()=>livePerformance.invalidate("The viewport changed."));
document.addEventListener("visibilitychange",()=>{if(document.visibilityState!=="visible")livePerformance.invalidate("The tab was hidden.");});
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
