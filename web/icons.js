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

export function bannerIcon(type) {
  const glyphs = {
    offside: `<path d="M7 23V3m0 1h14l-3 5 3 5H7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M8 5h5v4H8zm5 4h5v4h-5" fill="currentColor"/>`,
    penalty: `<path d="M3 21V7h19v14M7 21V11h11v10" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="12.5" cy="18" r="2" fill="currentColor"/>`,
    drinks_break: `<path d="M7 7h12l-2 16H9L7 7zm1 5h10M15 2l-2 5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>`,
    kick_off: `<circle cx="12.5" cy="12.5" r="9" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M12.5 8l4 3-1.5 5h-5L8.5 11z" fill="currentColor"/>`,
    half_time: `<text x="12.5" y="17" font-size="11" font-weight="800" text-anchor="middle" fill="currentColor" font-family="system-ui,sans-serif">HT</text>`,
    full_time: `<text x="12.5" y="17" font-size="11" font-weight="800" text-anchor="middle" fill="currentColor" font-family="system-ui,sans-serif">FT</text>`,
  };
  if (Object.hasOwn(glyphs, type)) return `<svg viewBox="0 0 25 25" aria-hidden="true">${glyphs[type]}</svg>`;
  return `<svg viewBox="0 0 25 25" aria-hidden="true">${WHISTLE}${BADGES[type] ?? ""}</svg>`;
}

export const FEED_ICONS = {
  goal: "⚽", card_yellow: "🟨", card_red: "🟥", var: "📺", sub: "🔁", penalty: "◎",
  chance: "🎯", injury: "✚", clock: "⏱", whistle: "⏵", momentum: "↗", big_chance: "❗", milestone: "🔢",
};

// Companion chat icons: line style, currentColor, no emoji (they render differently per phone).
const FEED_GLYPHS = {
  goal: `<circle cx="12" cy="12" r="9"/><path d="M12 7l4 3-1.5 5h-5L8 10z"/>`,
  card_yellow: `<rect x="7" y="4" width="10" height="16" rx="2" fill="#f5c542" stroke="none"/>`,
  card_red: `<rect x="7" y="4" width="10" height="16" rx="2" fill="#ff6b5e" stroke="none"/>`,
  var: `<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>`,
  sub: `<path d="M7 4v16"/><path d="M17 4v16"/><path d="M7 12h10"/>`,
  penalty: `<path d="M3 20V7h18v13"/><path d="M7 20v-9h10v9"/><circle cx="12" cy="17" r="1.5"/>`,
  chance: `<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/>`,
  big_chance: `<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><path d="M12 3v3M12 18v3"/>`,
  injury: `<path d="M12 5v14M5 12h14"/>`,
  clock: `<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>`,
  whistle: `<path d="M3 13.5a5.5 5.5 0 1 0 11 0a5.5 5.5 0 1 0-11 0"/><path d="M11 9h10v4.5h-6"/>`,
  momentum: `<path d="M4 17l6-6 4 4 6-7"/><path d="M15 8h5v5"/>`,
  milestone: `<path d="M5 21V4"/><path d="M5 4h11l-2 4 2 4H5"/>`,
};
// An unknown kind draws nothing rather than a misleading glyph.
export function feedIcon(icon, size = 14) {
  if (!Object.hasOwn(FEED_GLYPHS, icon)) return "";
  const g = FEED_GLYPHS[icon];
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${g}</svg>`;
}
export const AVATARS = {
  commentator: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/></svg>`,
  analyst: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20V10"/><path d="M10 20V4"/><path d="M16 20v-7"/><path d="M22 20H2"/></svg>`,
};
