# Synthetic crowd atlas — generation record

Created for VMI on 2026-10-25 with the built-in OpenAI image generation tool,
with real transparent output requested. No CLI, API key, paid asset marketplace,
real spectator photography, reference-image texture or team marks were used.
These are generated anonymous adults, not photographs of actual supporters.
The original selected RGBA file is copied byte-for-byte; alpha bounds are measured
into atlas.json, not retouched. The alpha-tested material rejects low-alpha edge
matte pixels and uses explicit source-driven pose rows. This is photographic
imagery on instanced planes in a 3D stadium, not individually rigged crowd bodies.

## Initial generation prompt

Use case: photorealistic-natural. Asset type: production texture atlas for anonymous synthetic football stadium spectators in an accessible Three.js replay. Generate ONE transparent PNG atlas, landscape 4:3 aspect ratio, ideally 2048 x 1536. EXACT REGULAR GRID of 4 equal columns and 3 equal rows, twelve isolated full-body cutouts, each wholly inside its own cell with generous transparent margins and feet aligned near cell bottom. No lines, no labels, no background, no stadium, no chairs, no text, no watermarks or logos. Same four anonymous adults repeated consistently by column: column1 light-skinned adult man in navy jacket and beige trousers; column2 light-skinned adult woman dark hair, muted grey jacket and jeans; column3 dark-skinned adult man muted charcoal sweatshirt and dark trousers; column4 brown-skinned adult woman in muted blue jacket and navy trousers. Everyday understated clothing with realistic fabric texture; no sports brands. Row1 all SEATED on invisible seats, naturally bent knees, hands resting on thighs, neutral attentive faces. Row2 same people STANDING upright, arms relaxed down, neutral attentive faces. Row3 same people STANDING with both arms clearly raised above head, hands open, same neutral faces, no smiles or anger. This is a visual encoding of measured crowd amplitude, not inferred emotions. Entire heads, fingers and feet must be visible; no overlap between cells. Realistic human proportions, clean consistent scale: standing head roughly upper 20% of cell, feet lower 95%; seated heads lower, around 35% of cell. Frontal view from slightly above, soft neutral daylight, crisp natural photographic realism, high-quality antialiased alpha cutouts. Camera and lighting consistent across all twelve sprites.

## Layout correction

Edit this production sprite atlas. Keep the same four adult identities, clothes, neutral faces, three poses and photographic realism. Change ONLY technical atlas layout/cleanliness: make EXACT 4 equal-width columns and 3 equal-height rows, every sprite horizontally centered in its own cell, FEET at 95% of each cell's height. Uniform human scale across rows: seated bodies occupy only the lower 60% of their cells (empty transparent space above), standing arms-down bodies occupy the lower 80%, and raised-arm bodies the lower 94%. Thus feet and anatomical body scale match when a game swaps atlas rows. All hands and feet fully inside the cell, generous horizontal transparent margins, no sprite crossing a grid boundary. True transparent alpha with clean natural edges; remove all yellow/red/blue matte fringes and isolated speckles. No visible grid lines, no backgrounds, no chairs, no labels. Do not enlarge seated people to fill their cells. Do not shrink raised-arm people. Exact regular grid and consistent body scale are essential. Landscape4:3 ratio.

## Selected final edit

Technical sprite-atlas layout correction only. Keep all 12 anonymous realistic people and exact clothes/poses. SHRINK EVERY FIGURE TO 65% OF ITS CURRENT SIZE, then arrange in 4 equal columns by 3 equal rows. Center every smaller figure within its cell both horizontally and vertically. This must leave LARGE FULLY TRANSPARENT GUTTERS between every row and column, including between the feet in row2 and the raised fingertips in row3. No person may touch any grid boundary. No change to photographic realism, no replacement with drawings. Row1 seated, row2 standing arms down, row3 standing arms above head. Crucial: make the people SMALLER with generous space all around; do NOT fill the cells or stretch them. Complete fingers and shoes visible. Transparent backdrop, no grid lines or labels.

The requested uniform layout/scale was not exact in the generated result.
Runtime metadata therefore uses observed pixel bounds and explicit metric pose
heights (1.35m seated, 1.82m standing, 2.08m including raised hands). Hash, actual
dimensions and generated source identifier are recorded in provenance.json.

## V2 — twelve identities, 25 October 2026

The production briefs below summarize the two selected built-in generation
requests. They are generation records, not evidence of participant research.
The original PNG bytes remain unchanged. Measured UV rectangles, pixel sizes
and SHA-256 hashes are in `atlas-a-v2.json`, `atlas-b-v2.json` and their
`provenance-*-v2.json` companions. A rejected layout-edit candidate is not shipped.

**Group A brief:** A transparent production texture atlas of anonymous fictional
adult football spectators, photographic natural lighting, six distinct people
per row, consistent identities and understated unbranded clothes across poses.
Include a young man in navy, a blonde woman in burgundy, a Black man in olive,
an Asian woman in navy, an older grey-haired man in navy and a red-haired woman
in tan. Full bodies, complete hands and shoes, no background, text or marks.
Seated attentive people with hands on thighs; standing with arms relaxed;
standing with hands raised. Keep identities, anatomy, scale and camera consistent.
The requested six-row layout was not exact: only the complete first three pose
rows are used, giving eighteen source cutouts and six identities.

Selected original source: `exec-1cb56fb4-5a0b-4cd0-9f28-edfa1917d5a2.png`.

**Group B brief:** A new transparent six-column, three-row atlas, eighteen isolated
full-body adult supporters, six additional distinct identities with varied ages,
skin tones, hair and neutral everyday clothes, consistent by column. First row
seated, second standing with arms relaxed, third standing with raised hands.
Natural photographic detail, neutral attentive faces, no logos, slogans,
stadium, seats or background. Complete figures and generous transparent gutters.

Selected original source: `exec-55d5b550-8e3c-4be7-a7ff-0c6a49c73550.png`.

The image model did not produce perfectly separated regular cells. Runtime UVs
use measured silhouettes. A small empty top-centre gutter in the raised pose is
masked in the material to exclude neighbouring-row boots; this is documented
in provenance and does not retouch the source image. Twelve identities and
colour variation reduce repetition; this is not twelve thousand unique humans.
These remain alpha-tested photographic planes in a 3D stadium. They are not
individually rigged spectator bodies. Posture and motion encode delivered crowd
amplitude only, with no inferred cause or emotion.
