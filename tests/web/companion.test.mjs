import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
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
