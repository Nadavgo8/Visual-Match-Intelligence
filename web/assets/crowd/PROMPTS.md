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
