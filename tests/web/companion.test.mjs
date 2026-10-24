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
