import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { AnswerLog, DEFAULT_PROFILE, FeedStore, itemLabel, normaliseProfile } from "../../web/companion.mjs";

test("skipping onboarding gives the documented defaults", () => {
  assert.deepEqual(normaliseProfile(null), { knowledge: "follow", depth: "basic", team: null, amount: "balanced" });
  assert.deepEqual(normaliseProfile(DEFAULT_PROFILE), normaliseProfile({}));
});

test("expert means deep; anything unknown falls back instead of reaching the server", () => {
  assert.deepEqual(normaliseProfile({ knowledge: "expert", team: "away", amount: "everything" }),
    { knowledge: "expert", depth: "deep", team: "away", amount: "everything" });
  assert.deepEqual(normaliseProfile({ knowledge: "guru", team: "both", amount: "all" }), normaliseProfile({}));
  assert.equal(normaliseProfile({ depth: "deep" }).knowledge, "expert"); // profile saved before `knowledge` existed
});

test("late xG updates the same feed item instead of adding a new one", () => {
  const feed = new FeedStore();
  assert.equal(feed.upsert({ cue_id: "c1", text: "Shot saved." }), "insert");
  assert.equal(feed.upsert({ cue_id: "c1", text: "Shot saved (xG 0.31).", update: true }), "update");
  assert.equal(feed.items.size, 1);
  assert.equal(feed.items.get("c1").text, "Shot saved (xG 0.31).");
  feed.reset([{ cue_id: "c2" }]);
  assert.deepEqual([...feed.items.keys()], ["c2"]);
  assert.equal(feed.upsert({ cue_id: "c1" }), "insert");
});

test("an answer is shown once per question", () => {
  const log = new AnswerLog();
  assert.equal(log.accept("q1"), true);
  assert.equal(log.accept("q1"), false);
  assert.equal(log.accept(undefined), false);
});

test("facts and interpretation are labelled differently", () => {
  assert.equal(itemLabel("feed"), "Fact");
  assert.equal(itemLabel("analysis"), "Analysis · interpretation");
});

test("the companion never notifies, vibrates or plays sound", () => {
  const src = readFileSync(new URL("../../web/app.js", import.meta.url), "utf8");
  for (const api of ["Notification", "navigator.vibrate", "new Audio", "AudioContext", "serviceWorker", "showNotification"]) {
    assert.equal(src.includes(api), false, api);
  }
});

function memoryStorage() {
  const data = new Map();
  return { getItem: (k) => data.get(k) ?? null, setItem: (k, v) => data.set(k, String(v)) };
}

test("catch-up checkpoints are kept per room, match and run, and only move forward", async () => {
  const { CatchUpCheckpoints, scopeOf } = await import("../../web/companion.mjs");
  const cp = new CatchUpCheckpoints(memoryStorage());
  const a = scopeOf("demo", 12, "r1"), b = scopeOf("demo", 12, "r2"), c = scopeOf("demo", 7, "r1");
  assert.equal(cp.get(a), null); // first use: the server covers the last 5 minutes
  assert.equal(cp.advance(a, 300), true);
  assert.equal(cp.advance(a, 200), false); // never backwards
  assert.equal(cp.advance(a, Number.NaN), false);
  assert.equal(cp.get(a), 300);
  assert.equal(cp.get(b), null); // a new run starts its own checkpoint
  assert.equal(cp.get(c), null); // so does another match
});

test("catch-up checkpoints stay bounded and survive blocked storage", async () => {
  const { CatchUpCheckpoints } = await import("../../web/companion.mjs");
  const cp = new CatchUpCheckpoints(memoryStorage(), "k", 3);
  for (let i = 1; i <= 5; i++) cp.advance(`s${i}`, i);
  assert.deepEqual(Object.keys(cp.all()), ["s3", "s4", "s5"]);
  const blocked = new CatchUpCheckpoints({ getItem() { throw new Error("no"); }, setItem() { throw new Error("no"); } });
  assert.equal(blocked.get("x"), null);
  assert.equal(blocked.advance("x", 5), true); // doesn't throw; simply not remembered
});

test("valid JSON with the wrong storage shape is discarded and replaced by durable checkpoints", async () => {
  const { CatchUpCheckpoints, scopeOf } = await import("../../web/companion.mjs");
  const scope = scopeOf("demo", 12, "r1");
  for (const raw of ["42", "true", '"text"', "[]", '[{"old":1}]', "null", "{broken"]) {
    const storage = memoryStorage(); storage.setItem("k", raw);
    const cp = new CatchUpCheckpoints(storage, "k");
    assert.equal(cp.get(scope), null, raw);
    assert.equal(cp.advance(scope, 300), true, raw);
    assert.equal(new CatchUpCheckpoints(storage, "k").get(scope), 300, raw);
    assert.deepEqual(JSON.parse(storage.getItem("k")), { [scope]: 300 }, raw);
  }
});

// Run the real app entrypoint with controlled DOM/transport boundaries. Rendering
// and escaping are not reimplemented by this harness; the received HTML is asserted.
async function appHarness() {
  const companion = await import("../../web/companion.mjs");
  const {atmospherePresentation, litSegments} = await import("../../web/atmosphere.mjs");
  const {AVATARS, feedIcon} = await import("../../web/icons.js");
  const nodes = new Map(); let receive; const sent = [];
  const win = { addEventListener() {}, scrollY: 0, innerHeight: 0, scrollTo() { win.scrolled = (win.scrolled ?? 0) + 1; } };
  // A small DOM: enough tree behaviour to check where chat messages land.
  const element = () => ({ _html: "", get innerHTML() { return this._html; },
    set innerHTML(v) { this._html = v; if (v === "") this.children.length = 0; },
    textContent: "", id: "", className: "", hidden: false, children: [], parentNode: null,
    addEventListener() {}, scrollIntoView() {}, attributes: {}, setAttribute(k,v) { this.attributes[k]=v; },
    appendChild(c) { return this.insertBefore(c, null); },
    insertBefore(c, ref) { c.remove(); const i = ref ? this.children.indexOf(ref) : -1;
      if (i < 0) this.children.push(c); else this.children.splice(i, 0, c); c.parentNode = this; return c; },
    remove() { if (this.parentNode) { const a = this.parentNode.children; a.splice(a.indexOf(this), 1); this.parentNode = null; } },
    replaceWith(n) { const p = this.parentNode; if (!p) return; p.children[p.children.indexOf(this)] = n; n.parentNode = p; this.parentNode = null; },
    querySelector() { return null; }, style: { setProperty() {} }, classList: { toggle() {} } });
  const inChat = id => nodes.get("chat")?.children.find((c) => c.id === id);
  const node = id => { const c = inChat(id); if (c) return c; if (!nodes.has(id)) nodes.set(id, element()); return nodes.get(id); };
  const doc = { getElementById: node,
    addEventListener() {}, createElement: element, documentElement: element(), querySelector: selector => node(selector) };
  const src = readFileSync(new URL("../../web/app.js", import.meta.url), "utf8").replace(/^import .*;\r?\n/gm, "");
  const context = { ...companion, AVATARS, feedIcon, atmospherePresentation, litSegments, URLSearchParams,
    location: { search: "?room=qa" }, localStorage: memoryStorage(), document: doc,
    window: win, openSession(options) { receive = options.onMessage; return { send(m) { sent.push(m); return true; } }; } };
  runInNewContext(src, context);
  const ask = (q) => { node("q").value = q; node("ask-form").onsubmit({ preventDefault() {} }); };
  return { receive, node, win, doc, sent, ask, html: id => node(id).innerHTML, receipts: context.receiptsHtml,
    order: () => node("chat").children.map((c) => c.id) };
}

const meterSample = { type:'meters', score:{home:1,away:0}, clock:'2:09',
  atmosphere:{available:true,level:.38,why:'Prior run pressure'},momentum:{home_index:.73} };
const emptySnapshot = (run_id='new') => ({type:'snapshot',run_id,state:{seed:13,score:{home:0,away:0},clock:'0:00',
  teams:{home:{name:'Home',colour:'#123'},away:{name:'Away',colour:'#eee'}}},meters:null,feed:[]});

test('a replacement snapshot without measurements clears prior atmosphere and momentum', async () => {
  const app=await appHarness(); app.receive(meterSample);
  assert.equal(app.node('atmo-chip').textContent,'38%');
  assert.equal(app.node('atmo-chip').attributes['aria-label'],'Atmosphere 38%');
  assert.equal(app.node('atmo-segs').innerHTML.split('class="on"').length-1,4);  // 4 of 10 segments lit
  app.node('atmo-segs').innerHTML='kept';
  app.receive({...meterSample,atmosphere:{available:true,level:.41}});
  assert.equal(app.node('atmo-segs').innerHTML,'kept');  // same lit count: segments are not rebuilt
  assert.equal(app.node('mom').style.width,'73%');
  app.receive(emptySnapshot());
  assert.equal(app.node('atmo-chip').textContent,'Unavailable');
  assert.equal(app.node('atmo-chip').attributes['aria-label'],'Atmosphere unavailable');
  assert.equal(app.node('atmo-segs').innerHTML.includes('class="on"'),false);  // no stale segments
  assert.equal(app.node('atmo-chip').title,'');
  assert.equal(app.node('.mom').attributes['aria-label'],'Momentum unavailable');
  assert.equal(app.node('score').textContent,'0–0'); assert.equal(app.node('clock').textContent,'0:00');
});
test('same-run reconnect clears absent data and a complete snapshot restores its own measurements', async () => {
  const app=await appHarness(); app.receive({...emptySnapshot('same'),meters:meterSample});
  assert.equal(app.node('atmo-chip').textContent,'38%');
  app.receive(emptySnapshot('same'));
  assert.equal(app.node('atmo-chip').textContent,'Unavailable');
  app.receive({...emptySnapshot('next'),meters:{...meterSample,atmosphere:{available:true,level:.8},momentum:{home_index:.2}}});
  assert.equal(app.node('atmo-chip').textContent,'80%');
  assert.equal(app.node('mom').style.width,'20%');
});
test('missing meter components are unavailable rather than stale values or exceptions', async () => {
  const app=await appHarness(); app.receive(meterSample);
  assert.doesNotThrow(()=>app.receive({...meterSample,atmosphere:null,momentum:null}));
  assert.equal(app.node('atmo-chip').textContent,'Unavailable');
  assert.equal(app.node('.mom').attributes['aria-label'],'Momentum unavailable');
});

test("answer metadata from a model is literal text, including unknown agent names", async () => {
  const app = await appHarness();
  const payload = '<img src=x onerror="bad()"> &';
  app.receive({ type: "answer", id: "q1", agent: payload, source: "agent", model: payload,
    text: payload, evidence: [payload], tool_calls: [payload], fallback_reason: payload, latency_ms: payload });
  const html = app.html("m-q1");
  assert.equal(html.includes("<img"), false);
  assert.ok(html.includes("&lt;img src=x onerror=&quot;bad()&quot;&gt; &amp;"));
  assert.equal(html.includes("<details"), false);  // no receipts block in the chat
});

test("known agent labels and answer deduplication remain intact", async () => {
  const app = await appHarness();
  app.receive({ type: "answer", id: "q1", agent: "match_analyst", source: "local", text: "First", latency_ms: 12 });
  const html = app.html("m-q1");
  assert.ok(html.includes("<b>Kai</b>") && html.includes("Fact · written by code"));
  app.receive({ type: "answer", id: "q1", agent: "router", text: "Replacement" });
  assert.equal(app.html("m-q1"), html);
});

test("analysis shows who wrote it, never a receipts block, and its text stays literal", async () => {
  const app = await appHarness();
  app.receive(snapshotWith([]));
  const payload = '<svg onload="bad()"> &';
  app.receive({ type: "analysis", cue_id: "a1", clock: "1:00", t: 60, moment: "goal", text: payload,
    receipts: { source: "agent" }, sentences: [], facts: [] });
  app.receive({ type: "analysis", cue_id: "a2", clock: "2:00", t: 120, moment: "goal", text: "x",
    receipts: { source: "template" }, sentences: [], facts: [] });
  assert.ok(app.html("m-a1").includes("interpretation · AI") && app.html("m-a2").includes("interpretation · written by code"));
  assert.equal(app.html("m-a1").includes("<svg onload") || app.html("m-a1").includes("<details"), false);
  assert.ok(app.html("m-a1").includes("&lt;svg onload=&quot;bad()&quot;&gt; &amp;"));
});

// ---------- unified match chat ----------
import { SPEAKERS, insertIndex, isNearBottom, speakerOf, suggestionsFor } from "../../web/companion.mjs";

const feedItem = (cue, t, extra = {}) => ({ type: "feed", cue_id: cue, clock: `${Math.floor(t / 60)}:00`, t, delivered: t,
  icon: "chance", team: "home", text: `item ${cue}`, evidence: [`e_${cue}`], tier: 3, speaker: "commentator", reply_to: null, ...extra });
const snapshotWith = (feed, run_id = "r1") => ({ ...emptySnapshot(run_id), feed });

test("two named voices, told apart by name, role and label as well as colour", () => {
  assert.deepEqual([SPEAKERS.commentator.name, SPEAKERS.commentator.label], ["Kai", "Fact"]);
  assert.deepEqual([SPEAKERS.analyst.name, SPEAKERS.analyst.label], ["Ada", "Interpretation"]);
  assert.equal(speakerOf("<script>"), SPEAKERS.commentator);  // unknown speakers fall back to the commentator
});

test("chat order: oldest first, and equal times keep arrival order", () => {
  assert.equal(insertIndex([], 5), 0);
  assert.equal(insertIndex([1, 3, 5], 4), 2);
  assert.equal(insertIndex([1, 3, 3, 5], 3), 3);  // after the existing 3s
  assert.equal(insertIndex([1, 3], 9), 2);
});

test("following means the bottom of the chat is within 80 px", () => {
  assert.equal(isNearBottom(920, 1000), true);
  assert.equal(isNearBottom(919, 1000), false);
  assert.equal(isNearBottom(0, 0), true);
});

test("suggested questions follow the latest big moment, at most three, never repeated", () => {
  assert.deepEqual(suggestionsFor("sub"), ["What changed after the substitution?", "Who's on top?", "Why was that offside?"]);
  assert.deepEqual(suggestionsFor(null), ["Who's on top?", "Why was that offside?", "Match stats"]);
  for (const icon of ["goal", "penalty", "var", "card_red", "card_yellow", "momentum", "unknown"]) {
    const s = suggestionsFor(icon);
    assert.ok(s.length <= 3 && new Set(s).size === s.length, icon);
  }
});

test("Kai, Ada and the fan share one chronological chat; a question sits after what the fan had seen", async () => {
  const app = await appHarness();
  app.receive(snapshotWith([feedItem("b", 20), feedItem("a", 10)]));
  assert.deepEqual(app.order(), ["m-a", "m-b"]);
  app.ask("Who scored?");
  assert.equal(JSON.stringify(app.sent.at(-1)), JSON.stringify({ cmd: "ask", q: "Who scored?", id: "q1" }));
  app.receive(feedItem("c", 30, { speaker: "analyst", icon: "momentum", text: "Home are on top right now." }));
  assert.deepEqual(app.order(), ["m-a", "m-b", "m-u1", "m-q1", "m-c"]);
  assert.ok(app.html("m-c").includes("<b>Ada</b>") && app.html("m-c").includes("Interpretation"));
  app.receive({ type: "answer", id: "q1", speaker: "analyst", agent: "meaning_analyst", source: "agent", model: "m",
    text: "Home lead through Dumont.", latency_ms: 5 });
  assert.deepEqual(app.order(), ["m-a", "m-b", "m-u1", "m-q1", "m-c"]);  // answered in place, nothing moved
  assert.ok(app.html("m-q1").includes("<b>Ada</b>") && app.html("m-q1").includes("Interpretation · AI"));
  assert.equal(app.node("announce").textContent, "Ada answered: Home lead through Dumont.");
});

test("Ada's analysis quotes and links the commentator message it replies to", async () => {
  const app = await appHarness();
  app.receive(snapshotWith([feedItem("g", 100, { icon: "goal", tier: 1, text: "GOAL! Dumont scores." })]));
  app.receive({ type: "analysis", cue_id: "x", clock: "1:48", t: 108, moment: "goal", reply_to: "g", speaker: "analyst",
    text: "That restores the lead.", sentences: [], facts: [], receipts: { source: "template", validation: "passed", latency_ms: 0 } });
  const html = app.html("m-x");
  assert.ok(html.includes('href="#m-g"') && html.includes("<b>Ada</b>") && html.includes("After the goal · interpretation"));
  app.receive({ type: "analysis", cue_id: "y", clock: "1:50", t: 110, moment: "goal", reply_to: "missing",
    text: "No target.", sentences: [], facts: [], receipts: { source: "template", validation: "passed", latency_ms: 0 } });
  assert.equal(app.html("m-y").includes("class=\"reply\""), false);  // a reply to something not shown has no quote
});

test("reading older messages: live updates show a new-messages button instead of scrolling", async () => {
  const app = await appHarness();
  app.receive(snapshotWith([feedItem("a", 10)]));
  app.doc.documentElement.scrollHeight = 2000; app.win.innerHeight = 500; app.win.scrollY = 0; app.win.scrolled = 0;
  app.receive(feedItem("b", 20));
  app.receive(feedItem("c", 30));
  assert.equal(app.node("jump").hidden, false);
  assert.equal(app.node("jump").textContent, "2 new messages ↓");
  assert.equal(app.win.scrolled, 0);
  app.receive({ ...feedItem("c", 30), text: "item c (xG 0.3)", update: true });  // late xG: not a new message
  assert.equal(app.node("jump").textContent, "2 new messages ↓");
  app.win.scrollY = 1500;  // back at the bottom: new messages follow automatically
  app.receive(feedItem("d", 40));
  assert.equal(app.win.scrolled, 1);
  assert.equal(app.node("jump").hidden, true);
});

test("tier-1 moments are emphasised and announced; quieter items are not announced", async () => {
  const app = await appHarness();
  app.receive(snapshotWith([]));
  app.receive(feedItem("p", 50, { tier: 1, icon: "penalty", text: "Penalty to Home!" }));
  assert.ok(app.node("m-p").className.includes("tier1"));
  assert.equal(app.node("announce").textContent, "Kai, 0:00: Penalty to Home!");
  app.receive(feedItem("s", 60, { tier: 3, text: "Shot saved." }));
  assert.equal(app.node("announce").textContent, "Kai, 0:00: Penalty to Home!");
  assert.ok(app.html("suggest").includes("Why was it a penalty?"));
});

test("a reconnect keeps the fan's questions; a jump to a new run restarts the chat with a notice", async () => {
  const app = await appHarness();
  app.receive(snapshotWith([feedItem("a", 10)], "r1"));
  app.ask("What happened?");
  app.receive(snapshotWith([feedItem("a", 10), feedItem("b", 20)], "r1"));
  assert.deepEqual(app.order(), ["m-a", "m-u1", "m-q1", "m-b"]);
  app.receive(snapshotWith([feedItem("z", 900)], "r2"));
  assert.deepEqual(app.order(), ["m-n2", "m-z"]);
  assert.ok(app.node("m-n2").textContent.includes("chat started again"));
  app.receive({ type: "answer", id: "q1", text: "late", source: "local" });  // answer for the old run: nowhere to go
  assert.deepEqual(app.order().length, 2);
});

test("chat text from the feed is literal, never HTML", async () => {
  const app = await appHarness();
  app.receive(snapshotWith([feedItem("h", 10, { text: '<img src=x onerror="bad()">', clock: "<b>", reply_to: "a\"b" })]));
  assert.equal(app.html("m-h").includes("<img"), false);
  assert.ok(app.html("m-h").includes("&lt;img"));
});

test("Ada's rules answers are labelled Rules, not interpretation", async () => {
  const app = await appHarness();
  app.receive(snapshotWith([]));
  app.ask("Was that offside?");
  app.receive({ type: "answer", id: "q1", speaker: "analyst", agent: "rules_expert", source: "local", text: "Law 11.", latency_ms: 1 });
  assert.ok(app.html("m-q1").includes("Rules · written by code") && app.html("m-q1").includes("<b>Ada</b>"));
});

test("Kai closes Ada's analysis with one reply, placed right after hers", async () => {
  const app = await appHarness();
  app.receive(snapshotWith([feedItem("g", 100, { icon: "goal", tier: 1, text: "GOAL! Ferreira scores." })]));
  app.receive({ type: "analysis", cue_id: "x", clock: "1:48", t: 108, moment: "goal", reply_to: "g", text: "Look at the pass.",
    receipts: { source: "template" }, followup: { text: "And the noise level jumped.", evidence: ["crowd@1"] } });
  app.receive(feedItem("later", 120));
  assert.deepEqual(app.order(), ["m-g", "m-x", "m-x-k", "m-later"]);
  const k = app.html("m-x-k");
  assert.ok(k.includes("<b>Kai</b>") && k.includes('href="#m-x"') && k.includes("And the noise level jumped."));
  app.receive({ type: "analysis", cue_id: "y", clock: "1:58", t: 118, moment: "injury", text: "No follow-up." });
  assert.equal(app.order().includes("m-y-k"), false);
});

test("chat text uses short dashes and an unknown icon shows nothing, not a dot", async () => {
  const app = await appHarness();
  app.receive(snapshotWith([feedItem("d", 10, { icon: "new_kind", text: "One thing — and another" })]));
  const html = app.html("m-d");
  assert.ok(html.includes("One thing - and another") && !html.includes("—"));
  assert.ok(html.includes('<span class="ic"></span>'));  // a routine row with an empty icon slot
});

test("an answer replies to the fan's question, quoting it", async () => {
  const app = await appHarness();
  app.receive(snapshotWith([]));
  app.ask("Who had the most key passes?");
  app.receive({ type: "answer", id: "q1", speaker: "commentator", agent: "match_analyst", source: "local", text: "Brandt, 6." });
  const html = app.html("m-q1");
  assert.ok(html.includes('href="#m-u1"') && html.includes("↳ You"), html);
});

test("the biggest moments render as a logged-event card, routine facts as a timeline row", async () => {
  const app = await appHarness();
  app.receive(snapshotWith([
    feedItem("g", 3437, { tier: 1, icon: "goal", clock: "57:17", text: "Goal! <b>Dube</b>" }),
    feedItem("r", 3500, { tier: 3, icon: "chance", clock: "58:20", text: "Shot wide." }),
    feedItem("v", 3600, { tier: 1, icon: "var", clock: "60:00", text: "VAR check." }),
  ]));
  const card = app.node("m-g");
  assert.ok(card.className.includes("event goal"));
  assert.ok(card.innerHTML.includes(">Goal<") && card.innerHTML.includes("57'"));
  assert.ok(card.innerHTML.includes("<b>Kai</b>") && card.innerHTML.includes("Fact · logged match event"));
  assert.ok(card.innerHTML.includes("Goal! &lt;b&gt;Dube&lt;/b&gt;"));  // literal, never HTML
  assert.ok(app.node("m-v").className.includes("event tense"));
  const row = app.node("m-r");
  assert.ok(row.className.includes("row") && row.innerHTML.includes("58'"));
  assert.ok(row.innerHTML.includes('<b>Kai</b>, fact, 58:20'));  // the speaker is still announced
  assert.ok(row.innerHTML.includes('<span class="min" aria-hidden="true">'));  // the clock is read once
  app.receive(feedItem("g2", 3700, { tier: 1, icon: "goal", clock: "45+2'", reply_to: "r", text: "Goal again" }));
  const reply = app.node("m-g2");
  assert.ok(reply.className.includes("event goal") && reply.innerHTML.includes('href="#m-r"'));  // still a card, with its quote
  assert.ok(reply.innerHTML.includes(">45+2'<") && !reply.innerHTML.includes("''"));
});
