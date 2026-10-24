# Three.js local runtime

Pinned **three 0.186.1**, MIT. The original license is included unchanged.
Only `build/three.module.js`, `build/three.core.js` and `LICENSE` are copied from
the official npm tarball. No CDN, account, paid service or runtime npm install.

Source: [official package](https://www.npmjs.com/package/three/v/0.186.1),
[upstream repository](https://github.com/mrdoob/three.js).

Acquisition: `npm pack three@0.186.1 --pack-destination out`. Verify the tarball
SHA-512 against `npmIntegrity` in `manifest.json` before extracting the three
explicit members. `files` records each member's SHA-256; the Node suite checks
those bytes. Updating the library requires an explicit version/integrity update,
license review and regression/browser tests. The tarball itself stays ignored.

`.gitattributes` preserves the three upstream members byte-for-byte across
Windows/Unix checkouts. Upstream `three.core.js:49957` contains one existing
space-before-tab indentation. Preserve its verified bytes: check authored files
with all whitespace rules; for this one upstream file omit only the
`space-before-tab` category and still check trailing whitespace/blank EOF.

Implementation references: [WebGLRenderer](https://threejs.org/docs/pages/WebGLRenderer.html),
[instancing](https://threejs.org/docs/pages/InstancedMesh.html),
[shadow tradeoffs](https://threejs.org/manual/pages/shadows.html).
