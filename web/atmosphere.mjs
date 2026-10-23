// One value and palette for the match screen and companion; never team colors.
export function atmospherePresentation(atmosphere) {
  const a = atmosphere ?? {};
  if (!a.available || !Number.isFinite(a.level)) {
    return { value: null, percent: null, label: "Atmosphere unavailable", color: "rgb(131, 147, 155)" };
  }
  const value = Math.min(1, Math.max(0, a.level));
  const low = [32, 190, 196], high = [245, 179, 67];
  const color = low.map((start, i) => Math.round(start + (high[i] - start) * value));
  const percent = Math.round(value * 100);
  const label = `${a.mode === "crowd_only" ? "Crowd only" : "Atmosphere"} ${percent}%`;
  return { value, percent, label, color: `rgb(${color.join(", ")})` };
}
