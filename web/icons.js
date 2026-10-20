// Banner icons: one whistle base, plus a small badge per whistle type (see
// research/icons-and-atmosphere-colors.md). Line style, currentColor.
const WHISTLE = `<path d="M3 13.5a5.5 5.5 0 1 0 11 0a5.5 5.5 0 1 0-11 0" fill="none" stroke="currentColor" stroke-width="2"/>
<path d="M11 9h11v4.5h-6.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
<circle cx="8.5" cy="13.5" r="1.6" fill="currentColor"/>`;

const BADGES = {
  foul: `<path d="M17 16l5 5M22 16l-5 5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>`,
  offside: `<path d="M17 23V14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M17 14h6l-1.5 2.2L23 18.4h-6z" fill="currentColor"/>`,
  penalty: `<path d="M15 21.5a4.5 4.5 0 0 1 9 0" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="19.5" cy="19" r="1.4" fill="currentColor"/>`,
  stoppage: `<rect x="16.5" y="15" width="2.2" height="7" rx="0.8" fill="currentColor"/><rect x="20.5" y="15" width="2.2" height="7" rx="0.8" fill="currentColor"/>`,
  whistle: ``,
  kick_off: `<circle cx="19.5" cy="18.5" r="4" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="19.5" cy="18.5" r="1.3" fill="currentColor"/>`,
  half_time: `<text x="19.5" y="22" font-size="7.5" font-weight="800" text-anchor="middle" fill="currentColor" font-family="Inter,system-ui,sans-serif">HT</text>`,
  full_time: `<text x="19.5" y="22" font-size="7.5" font-weight="800" text-anchor="middle" fill="currentColor" font-family="Inter,system-ui,sans-serif">FT</text>`,
};

const CROWD = `<path d="M4 12v0M8 8v8M12 5v14M16 8v8M20 11v2" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>`;

export function bannerIcon(type) {
  if (type === "crowd") return `<svg viewBox="0 0 24 24" aria-hidden="true">${CROWD}</svg>`;
  return `<svg viewBox="0 0 25 25" aria-hidden="true">${WHISTLE}${BADGES[type] ?? ""}</svg>`;
}

export const FEED_ICONS = {
  goal: "⚽", card_yellow: "🟨", card_red: "🟥", var: "📺", sub: "🔁", penalty: "◎",
  chance: "🎯", injury: "✚", clock: "⏱", whistle: "⏵", momentum: "↗",
};
