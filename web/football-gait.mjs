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

export function gaitCycleLength(speed) { return clamp(0.8 + 0.5 * Math.max(0, speed), 0.8, 4.4); }

export function footballGait(speed, cycle, keeper = false, cycleLength = 2.2, supportSpan = .65) {
  const pace = clamp(speed, 0, 9) / 9, moving = pace > 0.006;
  const phase = clamp(cycle, 0, Number.MAX_SAFE_INTEGER) % 1;
  const length = clamp(cycleLength, 0.8, 4.4), duty = Math.min(0.60, clamp(supportSpan,.1,.65) / length);
  const span = length * duty;
  const step = offset => {
    const p = (phase + offset) % 1;
    // During contact, linear retraction cancels source travel exactly at a
    // constant speed. Short running stance keeps the reach within the leg.
    const airborne = p >= duty, u = airborne ? (p - duty) / (1 - duty) : p / duty;
    const z = airborne ? span * (-0.5 + u * u * (3 - 2 * u)) : span * (0.5 - u);
    const lift = airborne ? Math.sin(u * Math.PI) * (0.05 + pace * 0.18) : 0;
    return { z: moving ? z : 0, lift: moving ? lift : 0, planted: !moving || !airborne };
  };
  return { left: step(0), right: step(0.5),
    pelvis: -(keeper && !moving ? 0.085 : 0.055) + (moving ? Math.abs(Math.sin(phase * Math.PI * 2)) * 0.014 : 0),
    lean: pace * 0.16, twist: Math.sin(phase * Math.PI * 2) * pace * 0.06,
    // Opposite arm travels back while the foot travels forward. A relaxed
    // elbow is a small anatomical flexion, not an extra bend on the mesh's
    // already-bent rest forearm (the rig converts this to a relative angle).
    armSwing: Math.cos(phase * Math.PI * 2) * pace * 0.68,
    armSpread: keeper && !moving ? 0.72 : 0.12 + pace * 0.07,
    elbow: keeper && !moving ? 0.45 : 0.12 + pace * 1.05 };
}
