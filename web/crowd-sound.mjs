// How the synthetic crowd sound follows the delivered crowd level. A steady murmur tracks the
// level; a roar layer opens only when the level surges above its recent baseline, so goals,
// penalties and big chances are clearly heard while a loud-but-steady spell is not a roar.

// The baseline follows the level over match time (meters tick several times a second): it
// rises slowly and falls fast, so a surge stands out and a long roar settles.
export function nextBaseline(baseline, level, dt) {
  if (!Number.isFinite(level)) return baseline;
  if (!Number.isFinite(baseline)) return level;
  if (!(dt > 0)) return baseline;
  const tau = level > baseline ? 20 : 4;
  return baseline + (level - baseline) * (1 - Math.exp(-Math.min(dt, 10) / tau));
}

export function crowdMix(level, baseline) {
  if (!Number.isFinite(level)) return { murmur: 0, roar: 0, cutoff: 400 };
  const l = Math.min(1, Math.max(0, level));
  const b = Number.isFinite(baseline) ? baseline : l;
  const surge = Math.min(1, Math.max(0, (l - b - 0.06) / 0.35));
  return {
    murmur: 0.1 + 0.55 * Math.pow(l, 1.4),
    roar: 0.85 * Math.pow(surge, 1.1),
    cutoff: 400 + l * 1600,
  };
}
