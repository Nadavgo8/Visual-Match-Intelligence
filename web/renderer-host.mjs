import { MatchRenderer } from "./match-renderer.mjs";

// WebGL capability/loss affects presentation, never the feed or the accessibility DOM.
export async function createRenderer(canvas, status, load3D = () => import("./match-3d.mjs")) {
  let current, fallback = false;
  const useFallback = () => {
    if (fallback) return;
    fallback = true; current?.dispose?.();
    // A WebGL canvas cannot acquire a 2D context, so replace just that canvas.
    const replacement = canvas.cloneNode(false); canvas.replaceWith(replacement); canvas = replacement;
    current = new MatchRenderer(canvas); current.mode = "2D fallback";
    canvas.setAttribute("aria-label", "2D fallback replay of a synthetic match");
    canvas.dataset.renderer = "2d"; status.textContent = "3D unavailable on this device. Using 2D replay.";
  };
  try {
    const { Match3D } = await load3D(); current = new Match3D(canvas, useFallback);
  } catch { useFallback(); }
  return {
    get canvas() { return canvas; }, get mode() { return current.mode; },
    draw: (frame, teams) => current.draw(frame, teams),
    setQuality: value => current.setQuality?.(value),
    setReducedMotion: value => { current.reducedMotion = value; },
    setCamera: value => { current.cameraMode = value; },
    dispose: () => current.dispose?.(),
  };
}
