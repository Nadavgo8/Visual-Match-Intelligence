import { FEED_ICONS } from "./icons.js";
import { atmospherePresentation } from "./atmosphere.mjs";
import { openSession } from "./session.mjs";
import { AnswerLog, DEFAULT_PROFILE, FeedStore, itemLabel, normaliseProfile } from "./companion.mjs";

const params = new URLSearchParams(location.search);
const room = params.get("room") || "demo";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const MOMENT = { goal: "After the goal", var_check: "While VAR checks", var_decision: "VAR decision",
  half_time: "Half-time", full_time: "Full-time", substitution: "Substitution", injury: "Injury stoppage" };
const KEY = "vmi.profile.v1";

let teams = null;
let profile = load();
const items = new Map(); // cue_id -> {t, el}
const feedStore = new FeedStore();
const answers = new AnswerLog();

function load() {
  try { const p = JSON.parse(localStorage.getItem(KEY)); return p ? normaliseProfile(p) : null; } catch { return null; }
}
function save(p) {
  try { localStorage.setItem(KEY, JSON.stringify(p)); } catch { /* private mode: keep in memory */ }
}

$("room-code").textContent = room;
let onboarded = false;
const session = openSession({
  room, role: "app",
  onStatus(s) {
    $("conn").hidden = s !== "disconnected";
    if (s !== "connected") return;
    // The server forgets a phone's settings when it disconnects: send them again on every connection.
    if (profile) send({ cmd: "profile", profile });
    else if (!onboarded) { onboarded = true; openOnboarding(); }
  },
  onMessage(m) {
    ({ snapshot: onSnapshot, state: onState, meters: onMeters, feed: (x) => addFeed(x, true), backlog: onBacklog,
       analysis: onAnalysis, answer: onAnswer, answer_discarded: onAnswerDiscarded })[m.type]?.(m);
  },
});
const send = (m) => session.send(m);

function onSnapshot(s) {
  onState(s.state);
  if (s.meters) onMeters(s.meters);
  onBacklog({ feed: s.feed || [] });
}

function onState(s) {
  teams = s.teams;
  document.documentElement.style.setProperty("--home", teams.home.colour);
  document.documentElement.style.setProperty("--away", teams.away.colour);
  $("home").textContent = teams.home.name;
  $("away").textContent = teams.away.name;
  document.querySelector(".t-home").textContent = teams.home.name;
  document.querySelector(".t-away").textContent = teams.away.name;
  $("score").textContent = `${s.score.home}–${s.score.away}`;
  $("clock").textContent = s.clock;
  $("agents").textContent = s.agents === "foundry" ? `Microsoft Foundry (${s.model})` : "local (offline)";
}

function onMeters(m) {
  $("score").textContent = `${m.score.home}–${m.score.away}`;
  $("clock").textContent = m.clock;
  const chip = $("atmo-chip");
  const a = atmospherePresentation(m.atmosphere);
  chip.textContent = a.label;
  chip.className = "chip";
  chip.style.background = a.color;
  chip.style.color = "#071b20";
  chip.title = m.atmosphere.why;
  $("mom").style.width = `${(m.momentum.home_index * 100).toFixed(0)}%`;
}

// ---------- feed ----------
function place(id, t, el) {
  const old = items.get(id);
  if (old && Number(old.el.dataset.t) === t) {  // same item, same moment: replace in place, don't move it
    old.el.replaceWith(el);
    el.dataset.t = t;
    items.set(id, { t, el });
    return;
  }
  if (old) old.el.remove();
  items.set(id, { t, el });
  const list = $("feed");
  // newest first; analysis cards sit just above the item they explain
  const after = [...list.children].find((c) => Number(c.dataset.t) < t);
  el.dataset.t = t;
  list.insertBefore(el, after || null);
  $("feed-empty").hidden = true;
}

function addFeed(f, fresh) {
  // Late information (such as xG) updates the same item quietly: no highlight, no new message.
  const isNew = feedStore.upsert(f) === "insert" && fresh;
  const li = document.createElement("li");
  li.className = `item tier${f.tier}${f.mine ? " mine" : ""}${isNew ? " new" : ""}`;
  const sources = (f.evidence || []).map((e) => `<code>${esc(e)}</code>`).join(" ");
  li.innerHTML = `<span class="clk">${esc(f.clock)}</span><span aria-hidden="true">${FEED_ICONS[f.icon] ?? "•"}</span><span class="txt">${esc(f.text)}</span>`
    + `<details class="sources"><summary><span class="kind">${itemLabel("feed")}</span></summary>Logged events: ${sources || "none"}</details>`;
  place(f.cue_id, f.t, li);
}

function onBacklog(m) {
  items.clear();
  feedStore.reset(m.feed);
  $("feed").innerHTML = "";
  $("feed-empty").hidden = m.feed.length > 0;
  for (const f of m.feed) addFeed(f, false);
}

function receiptsHtml(sentences, facts, r) {
  const byId = Object.fromEntries((facts || []).map((f) => [f.id, f]));
  const rows = sentences.map((s) => `<li>${esc(s.s)}<br>${s.evidence.map((e) =>
    `<code title="${esc(JSON.stringify(byId[e] ?? (e === "state" ? "score and clock" : e)))}">${esc(e)}</code>`).join(" ")}</li>`).join("");
  const src = r.source === "agent" ? `Explainer agent on ${esc(r.model)}` : "template (deterministic)";
  const rej = r.rejected ? ` · agent draft rejected: ${esc(r.rejected.join("; "))}` : "";
  return `<details class="receipts"><summary>Receipts · ${src} · validator ${r.validation === "passed" ? "✓ passed" : "✗"} · ${r.latency_ms} ms${rej}</summary><ul>${rows}</ul></details>`;
}

function onAnalysis(a) {
  const li = document.createElement("li");
  li.className = "card new";
  li.innerHTML = `<h3>${esc(MOMENT[a.moment] ?? "Analysis")} · ${esc(a.clock)} <span class="kind">${itemLabel("analysis")}</span></h3><p>${esc(a.text)}</p>${receiptsHtml(a.sentences, a.facts, a.receipts)}`;
  place(a.cue_id, a.t + 0.01, li);
}

// ---------- ask ----------
let qid = 0;
function bubble(cls, html) {
  const li = document.createElement("li");
  li.className = `msg ${cls}`;
  li.innerHTML = html;
  $("chat").appendChild(li);
  li.scrollIntoView({ block: "end", behavior: "smooth" });
  return li;
}
function ask(q) {
  q = q.trim();
  if (!q) return;
  bubble("me", esc(q));
  const pending = bubble("bot", "<span class='muted'>Thinking…</span>");
  pending.id = `q${++qid}`;
  if (!send({ cmd: "ask", q, id: pending.id })) {
    pending.innerHTML = "<span class='muted'>Not connected right now, so the question wasn't sent. Try again when the app reconnects.</span>";
  }
}
function onAnswer(a) {
  if (!answers.accept(a.id)) return;
  const el = document.getElementById(a.id) || bubble("bot", "");
  const who = { match_analyst: "Match analyst", rules_expert: "Rules expert", router: "Router", both: "Analyst + rules" }[a.agent] ?? a.agent;
  const src = a.source === "agent" ? `${who} agent on ${esc(a.model)}` : `${who} (local)`;
  const ev = (a.evidence || []).map((e) => `<code>${esc(e)}</code>`).join(" ");
  el.innerHTML = `${esc(a.text)}<details class="receipts"><summary>Receipts · ${src} · ${a.latency_ms} ms</summary>
    <ul><li>Tools: ${esc((a.tool_calls || []).join(", ") || "none")}</li><li>Evidence: ${ev || "none"}</li>${a.fallback_reason ? `<li>Fallback: ${esc(a.fallback_reason)}</li>` : ""}</ul></details>`;
}
function onAnswerDiscarded(a) {
  const el = document.getElementById(a.id);
  if (el) el.innerHTML = "<span class='muted'>The match jumped before this answer was ready, so it was dropped. Ask again.</span>";
}
$("ask-form").onsubmit =(e) => { e.preventDefault(); ask($("q").value); $("q").value = ""; };
$("suggest").onclick = (e) => { if (e.target.tagName === "BUTTON") ask(e.target.textContent); };

// ---------- tabs ----------
function tab(which) {
  const feed = which === "feed";
  $("feed-view").hidden = !feed; $("ask-view").hidden = feed;
  $("tab-feed").classList.toggle("on", feed); $("tab-ask").classList.toggle("on", !feed);
  $("tab-feed").setAttribute("aria-selected", feed); $("tab-ask").setAttribute("aria-selected", !feed);
  if (!feed) $("q").focus();
}
$("tab-feed").onclick = () => tab("feed");
$("tab-ask").onclick = () => tab("ask");

// ---------- onboarding / settings ----------
function openOnboarding() {
  const f = $("onboard-form");
  if (profile) {
    $("ob-title").textContent = "Settings";
    f.knowledge.value = profile.knowledge || (profile.depth === "deep" ? "expert" : "follow");
    f.team.value = profile.team || "";
    f.amount.value = profile.amount;
  }
  $("onboard").showModal();
}
$("onboard").addEventListener("close", () => {
  const f = $("onboard-form");
  profile = normaliseProfile($("onboard").returnValue === "skip" ? DEFAULT_PROFILE
    : { knowledge: f.knowledge.value, team: f.team.value || null, amount: f.amount.value });
  save(profile);
  send({ cmd: "profile", profile });
});
$("settings-btn").onclick = openOnboarding;
