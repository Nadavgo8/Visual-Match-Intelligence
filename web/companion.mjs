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
