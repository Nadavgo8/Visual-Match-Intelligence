// Companion app state (D2-03), kept free of the DOM so it can be tested with node --test.

export const DEFAULT_PROFILE = Object.freeze({ knowledge: "follow", depth: "basic", team: null, amount: "balanced" });

const KNOWLEDGE = new Set(["new", "follow", "expert"]);
const AMOUNTS = new Set(["big", "balanced", "everything"]);

// Settings from the onboarding form or storage, with anything unknown replaced by the default.
export function normaliseProfile(p) {
  const knowledge = KNOWLEDGE.has(p?.knowledge) ? p.knowledge : (p?.depth === "deep" ? "expert" : DEFAULT_PROFILE.knowledge);
  return {
    knowledge,
    depth: knowledge === "expert" ? "deep" : "basic",
    team: p?.team === "home" || p?.team === "away" ? p.team : null,
    amount: AMOUNTS.has(p?.amount) ? p.amount : DEFAULT_PROFILE.amount,
  };
}

// One entry per cue_id. Late information (for example xG for a shot) updates the same entry:
// the view replaces it in place, without highlighting it as new or moving it.
export class FeedStore {
  constructor() { this.items = new Map(); }

  reset(list = []) {
    this.items.clear();
    for (const item of list) this.items.set(item.cue_id, item);
  }

  upsert(item) {
    const known = this.items.has(item.cue_id);
    this.items.set(item.cue_id, item);
    return known ? "update" : "insert";
  }
}

// An answer is shown once for the question it answers; a repeat for the same id is ignored,
// so a reply built from an earlier snapshot is never rewritten by later information.
export class AnswerLog {
  constructor() { this.answered = new Set(); }

  accept(id) {
    if (!id || this.answered.has(id)) return false;
    this.answered.add(id);
    return true;
  }
}

// What the viewer is reading: a logged fact, or an interpretation built on facts.
export function itemLabel(kind) {
  return kind === "analysis" ? "Analysis · interpretation" : "Fact";
}

// "What did I miss?" checkpoints: where the next summary starts, kept separately for each
// room, match and run. A checkpoint only moves forward, and only after the viewer saw the
// top of the feed or received a summary; a failed request never moves it.
export const scopeOf = (room, seed, runId) => `${room}|${seed}|${runId}`;

export class CatchUpCheckpoints {
  constructor(storage = globalThis.localStorage, key = "vmi.caughtup.v1", keep = 20) {
    this.storage = storage; this.key = key; this.keep = keep;
  }

  all() {
    try {
      const value = JSON.parse(this.storage?.getItem(this.key));
      return value !== null && typeof value === "object" && !Array.isArray(value) ? value : {};
    } catch { return {}; }
  }

  get(scope) {
    const v = this.all()[scope];
    return Number.isFinite(v) ? v : null;
  }

  advance(scope, t) {
    if (!scope || !Number.isFinite(t)) return false;
    const all = this.all();
    if (Number.isFinite(all[scope]) && all[scope] >= t) return false;
    delete all[scope];  // re-insert last, so the oldest scopes are dropped first
    all[scope] = t;
    const scopes = Object.keys(all);
    for (const old of scopes.slice(0, Math.max(0, scopes.length - this.keep))) delete all[old];
    try { this.storage?.setItem(this.key, JSON.stringify(all)); } catch { /* private mode: no checkpoint kept */ }
    return true;
  }
}

// ---------- unified match chat ----------
// Two named voices: Kai says what happened (logged facts), Ada says what it means (interpretation).
export const SPEAKERS = Object.freeze({
  commentator: Object.freeze({ name: "Kai", role: "Commentator", label: "Fact" }),
  analyst: Object.freeze({ name: "Ada", role: "Analyst", label: "Interpretation" }),
});
export const speakerOf = (key) => SPEAKERS[key] ?? SPEAKERS.commentator;

// Index at which an entry with this order goes in a list sorted oldest first.
// Equal orders keep arrival order, so a burst of same-second events never reshuffles.
export function insertIndex(orders, order) {
  let lo = 0, hi = orders.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (orders[mid] <= order) lo = mid + 1; else hi = mid;
  }
  return lo;
}

// The viewer is following the latest messages when the bottom of the chat is (almost) on screen.
export const NEAR_BOTTOM_PX = 80;
export function isNearBottom(viewBottom, contentHeight, slack = NEAR_BOTTOM_PX) {
  return contentHeight - viewBottom <= slack;
}

// Suggested questions follow the latest big moment, so a fan can ask about it with one tap.
const SUGGEST_AFTER = {
  goal: ["Why does it matter?", "Who's on top?"],
  penalty: ["Why was it a penalty?", "Who's on top?"],
  var: ["Why did VAR get involved?", "What happened?"],
  card_red: ["What does the red card change?", "Who's on top?"],
  card_yellow: ["Why was that a booking?", "Who's on top?"],
  sub: ["What changed after the substitution?", "Who's on top?"],
  momentum: ["Why is the momentum changing?", "Match stats"],
};
const SUGGEST_DEFAULT = ["Who's on top?", "Why was that offside?", "Match stats"];
export function suggestionsFor(icon, max = 3) {
  const out = [...(SUGGEST_AFTER[icon] ?? []), ...SUGGEST_DEFAULT];
  return [...new Set(out)].slice(0, max);
}

// ---------- match chat layout ----------
// How a feed item is drawn: the biggest moments as a logged-event card (with its reply quote,
// if any), routine facts as a one-line timeline row, everything else as a chat bubble. Who
// said it is shown in all three. A routine reply stays a bubble so its quote has room.
export function feedLayout(f) {
  if (f?.speaker === "analyst") return "bubble";
  if (f?.tier === 1) return "card";
  return f?.tier >= 3 && !f?.reply_to ? "row" : "bubble";
}

// The match minute for a card or row: "37:58" -> "37'"; added time ("45+2'") is already a minute.
export function minuteOf(clock) {
  const c = String(clock ?? "").trim();
  if (!c) return "";
  return c.includes("'") ? c : `${c.split(":")[0]}'`;
}

export const EVENT_LABELS = Object.freeze({
  goal: "Goal", penalty: "Penalty", chance: "Shot", big_chance: "Big chance", var: "VAR", card_red: "Red card", card_yellow: "Yellow card",
  whistle: "Whistle", sub: "Substitution", injury: "Injury", clock: "Added time",
});
// Tone of a logged-event card: a goal is warm; a review, sending-off, penalty or the penalty
// kick itself (a tier-1 "chance") is tense; the rest calm.
const TENSE = new Set(["var", "card_red", "penalty", "chance"]);
export function eventTone(icon) {
  if (icon === "goal") return "goal";
  return TENSE.has(icon) ? "tense" : "calm";
}

// Up to three letters for a crest: "Harbour City" -> "HC", "Northvale Rovers" -> "NR".
export function teamInitials(name) {
  const words = String(name ?? "").match(/[\p{L}\p{N}]+/gu) ?? [];
  if (!words.length) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return words.slice(0, 3).map((w) => [...w][0]).join("").toUpperCase();
}

// Dark or white text on a team colour, whichever has more contrast (WCAG relative luminance).
export function readableText(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex ?? "").trim());
  if (!m) return "#ffffff";
  const lin = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  const [r, g, b] = [0, 2, 4].map((i) => lin(parseInt(m[1].slice(i, i + 2), 16)));
  const L = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return (L + 0.05) / 0.05 > 1.05 / (L + 0.05) ? "#0a0e13" : "#ffffff";
}
