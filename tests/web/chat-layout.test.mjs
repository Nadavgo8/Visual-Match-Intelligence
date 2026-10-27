import test from "node:test";
import assert from "node:assert/strict";
import { eventTone, feedLayout, readableText, teamInitials } from "../../web/companion.mjs";

test("feed items map to card, bubble or timeline row by speaker, tier and thread", () => {
  assert.equal(feedLayout({ speaker: "commentator", tier: 1 }), "card");
  assert.equal(feedLayout({ speaker: "commentator", tier: 2 }), "bubble");
  assert.equal(feedLayout({ speaker: "commentator", tier: 3 }), "row");
  assert.equal(feedLayout({ speaker: "analyst", tier: 1 }), "bubble");    // interpretation is never a logged-event card
  assert.equal(feedLayout({ speaker: "commentator", tier: 3, reply_to: "cue_0001" }), "bubble");  // a reply keeps its quote
  assert.equal(feedLayout({}), "bubble");
  assert.equal(feedLayout(null), "bubble");
});

test("event card tone follows the moment", () => {
  assert.equal(eventTone("goal"), "goal");
  for (const i of ["var", "card_red", "penalty"]) assert.equal(eventTone(i), "tense");
  for (const i of ["whistle", "card_yellow", undefined]) assert.equal(eventTone(i), "calm");
});

test("crest initials come from the team name", () => {
  assert.equal(teamInitials("Harbour City"), "HC");
  assert.equal(teamInitials("Northvale Rovers"), "NR");
  assert.equal(teamInitials("Athletic Club of Bay"), "ACO");
  assert.equal(teamInitials("Rovers"), "RO");
  assert.equal(teamInitials("  "), "?");
  assert.equal(teamInitials(null), "?");
});

test("crest text picks the higher-contrast ink for the team colour", () => {
  assert.equal(readableText("#e8e3d3"), "#0a0e13");  // pale kit
  assert.equal(readableText("#1E5AA8"), "#ffffff");  // deep blue
  assert.equal(readableText("#ffd23f"), "#0a0e13");
  assert.equal(readableText("#000000"), "#ffffff");
  assert.equal(readableText("not a colour"), "#ffffff");
});
