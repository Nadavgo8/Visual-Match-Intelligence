import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
test("vendored Three.js matches pinned, licensed npm package bytes", async () => {
  const root = new URL("../../web/vendor/three/", import.meta.url);
  const manifest = JSON.parse(await readFile(new URL("manifest.json", root)));
  assert.equal(manifest.version, "0.186.1"); assert.equal(manifest.license, "MIT");
  for (const [name, sha] of Object.entries(manifest.files)) {
    assert.equal(createHash("sha256").update(await readFile(new URL(name, root))).digest("hex"), sha);
  }
});
