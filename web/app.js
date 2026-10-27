import { AVATARS, feedIcon } from "./icons.js?v=3";
import { atmospherePresentation, litSegments } from "./atmosphere.mjs?v=2";
import { openSession } from "./session.mjs?v=1.1";
import { AnswerLog, CatchUpCheckpoints, DEFAULT_PROFILE, EVENT_LABELS, FeedStore, eventTone, feedLayout, insertIndex, isNearBottom, normaliseProfile, readableText, scopeOf, speakerOf, suggestionsFor, teamInitials } from "./companion.mjs?v=1.3";

const params = new URLSearchParams(location.search);
const room = params.get("room") || "demo";
const $ = (id) => document.getElementById(id);
// Chat text uses short dashes: an em dash from a model reads as a long gap on a phone.
const esc = (s) => String(s ?? "").replace(/\s*—\s*/g, " - ").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const MOMENT = { goal: "After the goal", var_check: "While VAR checks", var_decision: "VAR decision",
  half_time: "Half-time", full_time: "Full-time", substitution: "Substitution", injury: "Injury stoppage" };
const KEY = "vmi.profile.v1";

let teams = null;
let profile = load();
const feedStore = new FeedStore();
const answers = new AnswerLog();
const checkpoints = new CatchUpCheckpoints();
let scope = null, runId = null, newestDelivered = null, catchUps = 0;
const catchUpWhere = new Map(); // request id -> chat bubble element

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
       analysis: onAnalysis, answer: onAnswer, answer_discarded: onAnswerDiscarded, catch_up: onCatchUp,
       error: onError })[m.type]?.(m);
  },
});
const send = (m) => session.send(m);

function onSnapshot(s) {
  scope = scopeOf(room, s.state.seed, s.run_id);  // a seek or a new match starts a new checkpoint
  newestDelivered = null;
  if (runId !== null && s.run_id !== runId) {
    // The match jumped: everything said so far belongs to another moment, so the chat restarts.
    clearChat();
    addNotice("The match jumped to a new point, so the chat started again from here.");
  }
  runId = s.run_id;
  onState(s.state);
  // A snapshot replaces the prior run's evidence, including a same-run
  // reconnect whose replacement snapshot has no measurements yet.
  renderMeters(null, null);
  if (s.meters) onMeters(s.meters);
  onBacklog({ feed: s.feed || [] });
}

function onState(s) {
  teams = s.teams;
  document.documentElement.style.setProperty("--home", teams.home.colour);
  document.documentElement.style.setProperty("--away", teams.away.colour);
  $("home").textContent = teams.home.name;
  $("away").textContent = teams.away.name;
  for (const side of ["home", "away"]) {
    $(`${side}-crest`).textContent = teamInitials(teams[side].name);
    $(`${side}-crest`).style.color = readableText(teams[side].colour);
  }
  document.querySelector(".t-home").textContent = teams.home.name;
  document.querySelector(".t-away").textContent = teams.away.name;
  $("score").textContent = `${s.score.home}–${s.score.away}`;
  $("clock").textContent = s.clock;
  $("agents").textContent = s.agents === "foundry" ? `Microsoft Foundry (${s.model})` : "local (offline)";
}

function onMeters(m) {
  $("score").textContent = `${m.score.home}–${m.score.away}`;
  $("clock").textContent = m.clock;
  renderMeters(m.atmosphere, m.momentum);
}
function renderMeters(atmosphere, momentum) {
  const chip = $("atmo-chip");
  const a = atmospherePresentation(atmosphere);
  chip.textContent = a.percent === null ? "Unavailable" : `${a.label.replace(/^Atmosphere /, "")}`;
  chip.title = atmosphere?.why ?? "";
  chip.setAttribute("aria-label", a.label);
  document.querySelector(".strip").style.setProperty("--atmo", a.percent === null ? "var(--muted)" : a.color);
  const lit = litSegments(a.value);
  $("atmo-segs").innerHTML = Array.from({ length: 10 }, (_, i) => `<span${i < lit ? ' class="on"' : ""}></span>`).join("");
  const available = Number.isFinite(momentum?.home_index);
  const value = available ? Math.min(1, Math.max(0, momentum.home_index)) : .5;
  $("mom").style.width = `${(value * 100).toFixed(0)}%`;
  const bar = document.querySelector(".mom");
  bar.classList.toggle("unavailable", !available);
  bar.setAttribute("aria-label", available ? `Seven-minute momentum: home ${Math.round(value * 100)} percent` : "Momentum unavailable");
}

// ---------- the chat timeline ----------
// One list, oldest first. Agent messages are ordered by when they reached the room; a question
// goes after the newest message the fan had seen. Live messages never replace or move the fan's
// own questions and answers.
const entries = new Map(); // key -> {order, el, agent}
let lastOrder = 0, userSeq = 0, unread = 0;

function following() {
  const doc = document.documentElement;
  return isNearBottom((window.scrollY || 0) + (window.innerHeight || 0), doc.scrollHeight || 0);
}
function toBottom() {
  const smooth = !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  window.scrollTo?.({ top: document.documentElement.scrollHeight, behavior: smooth ? "smooth" : "auto" });
  unread = 0;
  $("jump").hidden = true;
}

function put(key, order, el, { agent = false, fresh = false, follow = false } = {}) {
  const wasFollowing = following();
  const old = entries.get(key);
  el.id = `m-${key}`;
  if (old && old.order === order) {  // same message, same moment: replace in place (late xG, a re-sent analysis)
    old.el.replaceWith(el);
    entries.set(key, { order, el, agent });
    return;
  }
  if (old) { old.el.remove(); entries.delete(key); }
  const list = $("chat");
  const sorted = [...entries.values()].sort((a, b) => a.order - b.order);
  const at = insertIndex(sorted.map((e) => e.order), order);
  list.insertBefore(el, sorted[at]?.el || null);
  entries.set(key, { order, el, agent });
  lastOrder = Math.max(lastOrder, order);
  $("chat-empty").hidden = true;
  if (!fresh) return;
  if (follow || wasFollowing) toBottom();
  else { unread += 1; $("jump").textContent = `${unread} new message${unread > 1 ? "s" : ""} ↓`; $("jump").hidden = false; }
}

function clearChat() {
  entries.clear();
  $("chat").innerHTML = "";
  lastOrder = 0;
  unread = 0;
  $("jump").hidden = true;
  $("chat-empty").hidden = false;
}
function dropAgentMessages() {
  for (const [key, e] of entries) if (e.agent) { e.el.remove(); entries.delete(key); }
}
function addNotice(text) {
  const li = document.createElement("li");
  li.className = "notice";
  li.textContent = text;
  put(`n${++userSeq}`, lastOrder + 0.0001, li);
}
function announce(text) { $("announce").textContent = text; }

function header(speakerKey, clock, label) {
  const s = speakerOf(speakerKey);
  return `<div class="who"><b>${esc(s.name)}</b>`
    + ` <span class="role">· ${esc(s.role.toLowerCase())}</span>${clock ? ` <span class="clk">${esc(clock)}</span>` : ""}`
    + ` <span class="kind">${esc(label ?? s.label)}</span></div>`;
}
// One agent message: avatar, then name and role over the bubble.
function agentHtml(speakerKey, clock, label, inner) {
  const key = speakerKey === "analyst" ? "analyst" : "commentator";
  return `<span class="avatar" aria-hidden="true">${AVATARS[key]}</span><div class="body">${header(key, clock, label)}`
    + `<div class="bubble">${inner}</div></div>`;
}
const minute = (clock) => esc(String(clock ?? "").split(":")[0]) + "'";
// A reply quotes what it answers, linked to it, so the thread reads like a conversation.
function replyQuote(replyTo) {
  const target = replyTo && entries.get(replyTo);
  if (!target) return "";
  const who = target.el.querySelector?.(".who b")?.textContent ?? (target.el.className.includes("me") ? "You" : "");
  const said = (target.el.querySelector?.(".txt")?.textContent ?? "").trim().slice(0, 80);
  return `<a class="reply" href="#m-${esc(replyTo)}">↳ ${esc(who)}${who ? ": " : ""}${esc(said)}</a>`;
}
function agentItem(speakerKey, extra) {
  const li = document.createElement("li");
  li.className = `msg agent ${speakerKey === "analyst" ? "ada" : "kai"}${extra ? ` ${extra}` : ""}`;
  return li;
}

function addFeed(f, fresh) {
  // Late information (such as xG) updates the same message quietly: no highlight, no new message.
  const isNew = feedStore.upsert(f) === "insert" && fresh;
  const speaker = f.speaker === "analyst" ? "analyst" : "commentator";
  const layout = feedLayout(f);
  let li;
  if (layout === "card") {
    li = document.createElement("li");
    li.className = `msg event ${eventTone(f.icon)} tier${f.tier}${f.mine ? " mine" : ""}${isNew ? " new" : ""}`;
    li.innerHTML = `<div class="head"><span class="label">${feedIcon(f.icon, 16)}${esc(EVENT_LABELS[f.icon] ?? "Big moment")}</span>`
      + `<span class="min">${minute(f.clock)}</span></div><p class="txt">${esc(f.text)}</p>`
      + `<div class="foot who"><b>Kai</b><span>· Fact · logged match event</span></div>`;
  } else if (layout === "row") {
    li = document.createElement("li");
    li.className = `msg row tier${f.tier}${f.mine ? " mine" : ""}${isNew ? " new" : ""}`;
    li.innerHTML = `<span class="min">${minute(f.clock)}</span><span class="ic">${feedIcon(f.icon)}</span>`
      + `<span class="who sr-only"><b>Kai</b>, fact, ${esc(f.clock)}: </span><span class="txt">${esc(f.text)}</span>`;
  } else {
    li = agentItem(speaker, `tier${f.tier}${f.mine ? " mine" : ""}${isNew ? " new" : ""}`);
    li.innerHTML = agentHtml(speaker, f.clock, speaker === "analyst" ? "Interpretation" : "Fact",
      replyQuote(f.reply_to) + `<p class="txt">${esc(f.text)}</p>`);
  }
  put(f.cue_id, Number.isFinite(f.delivered) ? f.delivered : f.t, li, { agent: true, fresh: isNew });
  if (isNew && f.tier <= 2) renderSuggestions(f.icon);
  if (isNew && f.tier === 1) announce(`${speakerOf(speaker).name}, ${f.clock}: ${f.text}`);
  if (Number.isFinite(f.delivered)) newestDelivered = Math.max(newestDelivered ?? 0, f.delivered);
  markSeen();
}

function onBacklog(m) {
  dropAgentMessages();
  feedStore.reset(m.feed);
  for (const f of [...m.feed].sort((a, b) => (a.delivered ?? a.t) - (b.delivered ?? b.t))) addFeed(f, false);
  $("chat-empty").hidden = entries.size > 0;
  const big = [...m.feed].reverse().find((f) => f.tier <= 2);
  renderSuggestions(big?.icon);
}

// Every message still says who wrote it: an AI model, or code. A template is never shown as AI.
const sourceTag = (source) => (source === "agent" ? "AI" : "written by code");

function onAnalysis(a) {
  const fresh = !entries.has(a.cue_id);
  const li = agentItem("analyst", fresh ? "new" : "");
  li.innerHTML = agentHtml("analyst", a.clock, `${MOMENT[a.moment] ?? "Analysis"} · interpretation · ${sourceTag(a.receipts?.source)}`,
    replyQuote(a.reply_to) + `<p class="txt">${esc(a.text)}</p>`);
  put(a.cue_id, a.t + 0.01, li, { agent: true, fresh });
  // Kai's closing turn to Ada: the last message of the exchange, never answered in turn.
  if (a.followup?.text) {
    const k = agentItem("commentator", fresh ? "new" : "");
    k.innerHTML = agentHtml("commentator", a.clock, "Fact · written by code",
      replyQuote(a.cue_id) + `<p class="txt">${esc(a.followup.text)}</p>`);
    put(`${a.cue_id}-k`, a.t + 0.02, k, { agent: true, fresh });
  }
}

// ---------- asking ----------
let qid = 0;
function userBubble(text) {
  const li = document.createElement("li");
  li.className = "msg me";
  li.innerHTML = `<span class="sr-only">You asked: </span><span class="txt">${esc(text)}</span>`;
  const order = lastOrder + 0.0001;
  const key = `u${++userSeq}`;
  put(key, order, li, { fresh: true, follow: true });
  return { order, key };
}
const askedBy = new Map(); // answer key -> the fan's question it replies to
function pendingBubble(question, text) {
  const li = document.createElement("li");
  li.className = "msg agent pending";
  li.innerHTML = `<span class="muted">${esc(text)}</span>`;
  const key = `q${++qid}`;
  askedBy.set(key, question.key);
  put(key, question.order + 0.00001, li, { fresh: true, follow: true });
  return key;
}
function ask(q) {
  q = q.trim();
  if (!q) return;
  const key = pendingBubble(userBubble(q), "Kai and Ada are checking the match…");
  if (!send({ cmd: "ask", q, id: key })) {
    $(`m-${key}`).innerHTML = "<span class='muted'>Not connected right now, so the question wasn't sent. Try again when the app reconnects.</span>";
  }
}
function onAnswer(a) {
  if (!answers.accept(a.id)) return;
  const el = document.getElementById(`m-${a.id}`);
  if (!el) return;  // asked before the chat restarted
  const speaker = a.speaker === "analyst" ? "analyst" : "commentator";
  const s = speakerOf(speaker);
  el.className = `msg agent ${speaker === "analyst" ? "ada" : "kai"} answer`;
  const label = a.agent === "rules_expert" ? "Rules" : s.label;  // the Laws of the Game are not interpretation
  el.innerHTML = agentHtml(speaker, a.clock, a.source === "agent" ? `${label} · AI` : `${label} · written by code`,
    replyQuote(askedBy.get(a.id)) + `<p class="txt">${esc(a.text)}</p>`);
  announce(`${s.name} answered: ${a.text}`);
  if (following()) toBottom();
}
function onAnswerDiscarded(a) {
  const el = document.getElementById(`m-${a.id}`);
  if (el) el.innerHTML = "<span class='muted'>The match jumped before this answer was ready, so it was dropped. Ask again.</span>";
}
$("ask-form").onsubmit = (e) => { e.preventDefault(); ask($("q").value); $("q").value = ""; };

function renderSuggestions(icon) {
  const chips = [`<button type="button" data-catch-up>What did I miss?</button>`,
    ...suggestionsFor(icon).map((q) => `<button type="button">${esc(q)}</button>`)];
  $("suggest").innerHTML = chips.join("");
}
renderSuggestions(null);
$("suggest").onclick = (e) => {
  if (e.target.tagName !== "BUTTON") return;
  if (e.target.dataset.catchUp !== undefined) catchUp(pendingBubble(userBubble("What did I miss?"), "Catching up…"));
  else ask(e.target.textContent);
};
$("jump").onclick = toBottom;

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

// ---------- what did I miss? ----------
// The viewer has seen the chat when it is on screen with the newest message in view.
function markSeen() {
  if (!scope || newestDelivered === null || document.visibilityState !== "visible") return;
  if (!following()) return;
  checkpoints.advance(scope, newestDelivered);
}
window.addEventListener("scroll", () => {
  if (following()) { unread = 0; $("jump").hidden = true; }
  markSeen();
}, { passive: true });
document.addEventListener("visibilitychange", markSeen);

function catchUp(key) {
  const id = `c${++catchUps}`;
  const where = $(`m-${key}`);
  catchUpWhere.set(id, where);
  if (!send({ cmd: "catch_up", id, since_t: scope ? checkpoints.get(scope) : null })) {
    catchUpWhere.delete(id);
    where.innerHTML = "<span class='muted'>Not connected right now, so there's no summary. Try again when the app reconnects.</span>";
  }
}
function onCatchUp(c) {
  const where = catchUpWhere.get(c.id);
  if (!where) return;
  catchUpWhere.delete(c.id);
  where.className = "msg agent kai answer";
  where.innerHTML = agentHtml("commentator", null, "Summary · written by code from logged events",
    replyQuote(askedBy.get(where.id?.slice(2))) + `<p class="txt"><b>${esc(c.from_clock)}–${esc(c.to_clock)}:</b> ${esc(c.text)}</p>`);
  if (scope) checkpoints.advance(scope, c.to_t);  // only a received summary moves the checkpoint
}
function onError(e) {
  for (const [id, where] of catchUpWhere) {  // a refused summary leaves the checkpoint where it was
    catchUpWhere.delete(id);
    where.innerHTML = `<span class='muted'>${esc(e.message || "That didn't work.")}</span>`;
  }
}
