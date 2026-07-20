# Mapping inventory page

Static reference and editing page for preparing the UTN57 ↔ ZVVNMOD mapping Map.

## Contents

- `data/utn57-written-units.html`: the rendered Hudum Written units table from Mongolian Font Builder.
- `data/zvvnmod-unicode-names.csv`: the authoritative ZVVNMOD name inventory snapshot.
- `data/zvvnmod-codes.json`: browser data grouped by base written-unit ID and joining position.
- `data/zvvnmod-utn57-map.json`: editable runtime alignments with ordered ZVVNMOD source and UTN57 target catalogues.
- `data/mongfontbuilder-particles.json`: exact Mongfontbuilder particle dictionary snapshot used by the particle generator.
- `data/mongfontbuilder-aliases.json`: exact Mongfontbuilder alias dictionary used to derive nominal Unicode code points.
- `data/particle-shaping-observations.json`: recorded Mongfontbuilder HarfBuzz glyph output and meco raw ZVVNMOD output for each MNG particle pattern.
- `data/zvvnmod-utn57-particles.json`: generated nominal-context particle alignments shown below the workbench.
- `assets/writtenunits-Regular.ttf`: UTN57 written-unit display font from Mongolian Font Builder.
- `assets/zvvnmod.ttf`: generated from meco's formal `zvvnmod.sfd`.

The two inventory tables remain unchanged above an aligned three-column mapping workbench. Its ZVVNMOD source catalogue contains the 77 single codes, the special `NIRUGU` code, and the two retained chachlag forms `N_AA_FINA` and `HX_AA_FINA`; other merged codes are already represented by decomposed sequences and are omitted. Generated direct mappings are review drafts, not authoritative linguistic rules. Unmatched codes remain as rows with the opposite side blank.

## Mapping JSON workflow

Generate the initial name-matched rows from both checked-in inventories:

```bash
python3 mapping/scripts/generate-default-mapping.py
```

ZVVNMOD catalogue IDs and mapping values use the Rust constant names; PUA code points remain catalogue metadata. Every row stores only its current ordered sequences and note:

```json
{
  "id": "source:A_INIT",
  "sources": ["A_INIT"],
  "targets": ["A:init"],
  "note": ""
}
```

Either `sources` or `targets` may be empty for an unmatched inventory item, but both cannot be empty in the same row. Their lengths are independent. The browser can add, remove, reorder, or replace values on either side. The checked-in Git rows are the Restore baseline, and `direct`, `unmapped`, and `special` are runtime display states derived by comparing the current row with that baseline; they are not serialized.

Main and particle edits download together as `zvvnmod-utn57-workbench-v2`. The combined root contains one `sha256:…` digest of the exact Git-loaded mapping and particle payloads. Import rejects a file made against a different baseline while avoiding duplicated per-row default arrays. To publish reviewed values, replace the corresponding checked-in JSON payload; Git provides history.

## Particle mapping generation

The page appends 47 MNG particle patterns from Mongfontbuilder below the editable workbench. The recorded observations were produced by:

1. building Mongfontbuilder's Hudum test font with its own `MongFeaComposer` and `ufo2ft` pipeline;
2. shaping every MNG particle nominal sequence with HarfBuzz to obtain UTN57 glyph/written-unit shapes;
3. converting the same nominal sequence through meco's `delehi → zvvnmod` path;
4. retaining those meco outputs as implementation-specific, checksum-locked provenance rather than treating them as the editable mapping;
5. deriving the initial editable ZVVNMOD sequence from UTN57 shape semantics and omitting shapes without a unique ZVVNMOD counterpart;
6. removing leading particle context (`MVS` in the UTN model and `NNBSP` in a 2010/vendor-side model) from the compact mapping body.

The observations can be independently rebuilt. With Docker available, run the capture script inside the pinned Mongfontbuilder development environment:

```bash
cd /path/to/mongfontbuilder
uv run --group dev python /path/to/satsrag.github.io/mapping/scripts/capture-particle-observations.py \
  --mongfontbuilder /path/to/mongfontbuilder \
  --meco /path/to/meco \
  --output /path/to/satsrag.github.io/mapping/data/particle-shaping-observations.json \
  --check
```

The capture script rejects dirty checkouts or either checkout unless `HEAD` is exactly Mongfontbuilder `539b455075486f70889e6de9909eac5dea839d8a` and meco `7edff334d33fc367596d1d33406b33bccb8ddc60`. It requires the checked-in particle and alias snapshots to be byte-identical to the pinned Mongfontbuilder files, forces a fresh Hudum font build, builds meco itself in a digest-pinned Maven/JDK container, and immediately launches that artifact in a digest-pinned JRE container. It does not accept an external meco service URL or JAR. The downstream generator locks SHA-256 digests for all input snapshots and derives nominal Unicode code points from the alias snapshot, so changing raw nominal code points, HarfBuzz glyph output, meco output, source objects, or paths fails verification until the reviewed locks are intentionally updated.

Regenerate the initial compact particle rows from the reviewed snapshots and observations:

```bash
python3 mapping/scripts/generate-particle-mapping.py
```

Particle rows use the same compact current-value model:

```json
{
  "id": "particle:07",
  "pattern": "i y a r",
  "particleIndices": [0, 1],
  "sources": ["I_INIT", "I_MEDI", "A_MEDI", "R_FINA"],
  "targets": ["I:init", "I:medi", "A:medi", "R:fina"],
  "note": ""
}
```

The two ordered sequences are independently editable and may have different lengths. The generated scaffold contains 47 rows; reviewed Git current values may diverge from the generator's initial sequence suggestions.

## Font regeneration

From a meco checkout:

```bash
./mapping/scripts/generate-zvvnmod-font.sh /path/to/meco
```

The checked-in font was generated from meco commit `7edff334d33fc367596d1d33406b33bccb8ddc60` with FontForge 20230101 in a digest-pinned Ubuntu 24.04 image. The script rejects a different meco revision or output checksum.

See [`NOTICE.md`](NOTICE.md) for sources and licenses.
