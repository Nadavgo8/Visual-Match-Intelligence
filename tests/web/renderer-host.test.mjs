import test from "node:test";
import assert from "node:assert/strict";
import { createRenderer } from "../../web/renderer-host.mjs";

// DOM/canvas boundary fake; real fallback drawing and host lifecycle stay intact.
const context = new Proxy({}, { get: (_target, key) => key === "createLinearGradient"
  ? () => ({ addColorStop() {} }) : () => {} });
function canvasFixture() {
  const document = { createElement: () => ({ width: 0, height: 0, getContext: () => context }) };
  let replacement;
  const make = () => ({ ownerDocument: document, clientWidth: 640, clientHeight: 360, width: 640, height: 360,
    dataset: {}, getContext: () => context, setAttribute(name, value) { this[name] = value; },
    cloneNode() { const copy = make(); Object.assign(copy.dataset, this.dataset); return copy; },
    replaceWith(node) { replacement = node; } });
  return { canvas: make(), get replacement() { return replacement; } };
}
globalThis.window = { devicePixelRatio: 1 };
test("failed module or WebGL construction uses a labelled working fallback canvas", async () => {
  for (const load of [async () => { throw new Error("module unavailable"); },
    async () => ({ Match3D: class { constructor() { throw new Error("WebGL2 unavailable"); } } })]) {
    const fixture = canvasFixture(), status = { textContent: "" };
    const host = await createRenderer(fixture.canvas, status, load);
    assert.strictEqual(host.canvas, fixture.replacement); assert.notStrictEqual(host.canvas, fixture.canvas);
    assert.equal(host.canvas.dataset.renderer, "2d"); assert.match(host.canvas["aria-label"], /2D fallback/);
    assert.match(status.textContent, /3D unavailable/); assert.equal(host.mode, "2D fallback");
    host.draw(null, null); host.setQuality("low"); host.setCamera("wide"); host.setReducedMotion(true); host.dispose();
  }
});
test("context loss replaces only the canvas, releases GPU once and tolerates repeated loss", async () => {
  const fixture = canvasFixture(), status = { textContent: "" };
  Object.assign(fixture.canvas.dataset, { engine: "three.js", renderer: "3d", quality: "high",
    camera: "broadcast", crowdLevel: "1", crowdStanding: "0.68", drawCalls: "81", triangles: "3458062" });
  let lose, disposed = 0, calls = 0;
  class Fake3D {
    constructor(_canvas, onLost) { lose = onLost; this.mode = "3D stadium"; }
    dispose() { disposed++; } draw() { calls++; }
  }
  const host = await createRenderer(fixture.canvas, status, async () => ({ Match3D: Fake3D }));
  assert.equal(host.mode, "3D stadium"); host.draw(null, null); assert.equal(calls, 1);
  lose(); const replacement = host.canvas; lose();
  assert.equal(disposed, 1); assert.strictEqual(host.canvas, replacement);
  assert.deepEqual(host.canvas.dataset, { renderer: "2d" });
  host.draw(null, null);
});
test("prepared texture ownership is released if WebGL construction fails", async () => {
  const fixture = canvasFixture(), status = { textContent: "" }; let disposed = 0;
  const host = await createRenderer(fixture.canvas, status, async () => ({
    prepareAssets: async () => ({ dispose() { disposed++; } }),
    Match3D: class { constructor() { throw Error("No GPU context"); } },
  }));
  assert.equal(host.mode, "2D fallback"); assert.equal(disposed, 1);
});
