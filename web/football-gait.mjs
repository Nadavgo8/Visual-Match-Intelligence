// Presentation only. No clock, event prediction, match decisions or mutable state.
const clamp = (value, min, max) => Math.max(min, Math.min(max, Number.isFinite(value) ? value : min));

export function legAngles(upper, lower, targetY, targetZ) {
  if (!Array.isArray(upper) || !Array.isArray(lower) || upper.length !== 3 || lower.length !== 3
    || !upper.every(Number.isFinite) || !lower.every(Number.isFinite) || !Number.isFinite(targetY) || !Number.isFinite(targetZ)) throw RangeError("Invalid leg coordinates");
  const a = Math.hypot(upper[1], upper[2]), b = Math.hypot(lower[1], lower[2]);
  if (a < 1e-5 || b < 1e-5 || a > 2 || b > 2) throw RangeError("Invalid leg length");
  const distance = clamp(Math.hypot(targetY, targetZ), Math.abs(a - b) + 1e-5, a + b - 1e-5);
  const aim = Math.atan2(targetZ, -targetY);
  const bend = Math.acos(clamp((a * a + b * b - distance * distance) / (2 * a * b), -1, 1));
  const knee = Math.PI - bend;
  const thigh = aim + Math.acos(clamp((a * a + distance * distance - b * b) / (2 * a * distance), -1, 1));
  const restUpper = Math.atan2(upper[2], -upper[1]), restLower = Math.atan2(lower[2], -lower[1]);
  const hip = restUpper - thigh, relativeKnee = restLower - restUpper + knee;
  return { hip, knee: relativeKnee, ankle: -hip - relativeKnee };
}

export function footballGait(speed, cycle, keeper = false) {
  const pace = clamp(speed, 0, 9) / 9, moving = pace > 0.006;
  const phase = clamp(cycle, 0, Number.MAX_SAFE_INTEGER) % 1;
  const stride = moving ? 0.12 + pace * 0.26 : 0;
  const step = offset => {
    const p = (phase + offset) % 1;
    // A level support phase, then a bent-knee return. Unlike a sinusoidal
    // marching leg, the foot clears the grass instead of swinging through it.
    const lift = p < 0.5 ? 0 : Math.sin((p - 0.5) * Math.PI * 2) * (0.05 + pace * 0.18);
    return { z: moving ? Math.cos(p * Math.PI * 2) * stride : 0, lift: moving ? lift : 0 };
  };
  return { left: step(0), right: step(0.5),
    pelvis: -(keeper && !moving ? 0.085 : 0.055) + (moving ? Math.abs(Math.sin(phase * Math.PI * 2)) * 0.014 : 0),
    lean: pace * 0.16, twist: Math.sin(phase * Math.PI * 2) * pace * 0.06,
    armSwing: Math.sin(phase * Math.PI * 2) * pace * 0.48,
    armSpread: keeper && !moving ? 0.86 : 0.22,
    elbow: -0.32 - pace * 0.7 };
}
