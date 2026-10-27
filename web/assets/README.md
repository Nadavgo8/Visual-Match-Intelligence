# Local scene assets

These assets are stored locally. Viewing the match makes no asset requests to
third-party sites and requires no account, CDN, paid service or model download.

## Athlete anatomy and rig — CC0 1.0

Source: [MakeHuman Community](https://github.com/makehumancommunity/makehuman),
commit `a8bc2d54ff0ac92e78ff71431b1023eda42bf482`.

Only graphical data is used: `makehuman/data/3dobjs/base.obj`, the
`universal-male-young-maxmuscle-averageweight.target` morph, and
`makehuman/data/rigs/default.mhskel` / `default_weights.mhw`.
The source mesh header explicitly declares CC0. The full asset license is
preserved in [athlete/CC0.txt](athlete/CC0.txt). MakeHuman **program code** is
AGPL; no MakeHuman program code is copied, imported or distributed here.

The original VMI converter [build_athlete_asset.py](../../scripts/build_athlete_asset.py)
triangulates body geometry, applies the athletic morph, normalizes height,
collapses the rig to 22 retained bones, combines/normalizes four skin weights,
adds shirt/short/sock/boot regions, and merges original eye/hair detail into the
same skinned mesh. The resulting clothed fictional athlete has 13,965 vertices
and 27,716 triangles. Source and output hashes are recorded in
[athlete/provenance.json](athlete/provenance.json).

Rebuild from the five pinned source assets in `out/reference-assets`, verify
their recorded hashes, then run `python scripts/build_athlete_asset.py`.
The converter itself does not download anything. Generated file bytes are
preserved across Windows/Unix by `.gitattributes` and checked by tests.

## Turf material — CC0 1.0

[Grass004 by Lennart Demes / ambientCG](https://ambientcg.com/view?id=Grass004),
1K JPG color and OpenGL normal maps. [License](https://docs.ambientcg.com/license/).
Only the two used maps are included; upstream programs, previews and project
files are excluded. Source archive URL/hash and individual map SHA-256 values
are recorded in [turf/provenance.json](turf/provenance.json).

Pitch markings, stadium, crowd geometry/shader, kits and numbers are original
VMI code. No real team/league/sponsor mark, player likeness or broadcast footage
is used. The image supplied by the user is a visual target, not a texture asset.

## Synthetic spectator atlas

The current crowd uses [group A](crowd/spectators-a-v2.png) and
[group B](crowd/spectators-b-v2.png), original RGBA images generated with the
built-in image tool for VMI. Twelve anonymous fictional adults have seated,
standing and raised-hand poses; neutral faces do not label emotions.
Photographic cutouts are instanced as planes inside the 3D stadium. The existing
procedural geometry remains available when no atlas is supplied to the builder.
The actual runtime loads the local atlas and validates its measured bounds.

[Prompts and method](crowd/PROMPTS.md), [metadata A](crowd/atlas-a-v2.json),
[metadata B](crowd/atlas-b-v2.json), [source A](crowd/provenance-a-v2.json) and
[source B](crowd/provenance-b-v2.json) document the original files. The earlier
four-identity v1 asset remains a tested historical fixture. No real spectator
photograph or reference-image content is used. No source retouching, network
dependency during viewing, purchase or API-key workflow was introduced.
