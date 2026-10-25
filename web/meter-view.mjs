import { edgePresentation } from "./overlay-state.mjs";

// Both edge bars inherit this one measured value. Missing data is explicitly
// unavailable, including after a source reset with no replacement meters.
export function renderAtmosphere(edges, label, atmosphere) {
  const view = edgePresentation(atmosphere);
  edges.style.setProperty("--edge-color", view.color);
  edges.style.setProperty("--edge-fill", `${view.height}%`);
  edges.style.setProperty("--edge-brightness", String(view.brightness));
  edges.dataset.available = String(view.available);
  edges.setAttribute("aria-label", `${view.label}; both sides show the same atmosphere`);
  edges.title = view.label;
  label.title = atmosphere?.why ?? "No measurement for this replay state";
  label.textContent = view.label;
}

export function renderMomentum(fill, share) {
  const available = Number.isFinite(share) && share >= 0 && share <= 1;
  fill.style.width = `${((available ? share : 0.5) * 100).toFixed(1)}%`;
  fill.parentElement.dataset.available = String(available);
  fill.parentElement.setAttribute("aria-label", available
    ? `Seven-minute momentum: home ${Math.round(share * 100)} percent` : "Momentum unavailable");
}

export function renderReplayTime(input, time, scrubbing = false) {
  if (!scrubbing && Number.isFinite(time) && time >= 0) input.value = Math.floor(time);
}
