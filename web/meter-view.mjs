import { edgePresentation } from "./overlay-state.mjs";

// Both edge bars inherit this one measured value. Missing data is explicitly
// unavailable, including after a source reset with no replacement meters.
export function renderAtmosphere(edges, label, atmosphere, {animate = true} = {}) {
  const view = edgePresentation(atmosphere);
  // CSS interpolation is only decoration between continuous live samples.
  // Missing/replacement data and paused source time must settle immediately.
  const continuous = animate && view.available && edges.dataset.available === "true";
  edges.style.setProperty("--edge-transition", continuous ? "height .35s linear,filter .35s linear" : "none");
  edges.style.setProperty("--edge-color", view.color);
  edges.style.setProperty("--edge-fill", `${view.height}%`);
  edges.style.setProperty("--edge-brightness", String(view.brightness));
  edges.dataset.available = String(view.available);
  edges.setAttribute("aria-label", `${view.label}; both sides show the same atmosphere`);
  edges.title = view.label;
  label.title = atmosphere?.why ?? "No measurement for this replay state";
  label.textContent = view.label;
}

export function renderMomentum(fill, share, {animate = true} = {}) {
  const available = Number.isFinite(share) && share >= 0 && share <= 1;
  const continuous = animate && available && fill.parentElement.dataset.available === "true";
  fill.style.setProperty("--momentum-transition", continuous ? "width .4s linear" : "none");
  fill.style.width = `${((available ? share : 0.5) * 100).toFixed(1)}%`;
  fill.parentElement.dataset.available = String(available);
  fill.parentElement.setAttribute("aria-label", available
    ? `Seven-minute momentum: home ${Math.round(share * 100)} percent` : "Momentum unavailable");
}

export function renderReplayTime(input, time, scrubbing = false) {
  if (!scrubbing && Number.isFinite(time) && time >= 0) input.value = Math.floor(time);
}
