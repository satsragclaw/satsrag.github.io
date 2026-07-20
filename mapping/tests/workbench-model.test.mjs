import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  hasSameGeneratedScaffold,
  mappingMode,
  normalizeMappingPayload,
  serializeMappingPayload,
  updateMappingEntry,
} from "../workbench-model.mjs";

const fixture = JSON.parse(
  await readFile(new URL("../data/zvvnmod-utn57-map.json", import.meta.url), "utf8"),
);

const ROW_KEYS = ["id", "note", "sources", "targets"];

function assertCompactRow(row) {
  assert.deepEqual(Object.keys(row).sort(), ROW_KEYS);
  assert.equal(Object.hasOwn(row, "defaultSources"), false);
  assert.equal(Object.hasOwn(row, "defaultTargets"), false);
  assert.equal(Object.hasOwn(row, "mode"), false);
}

test("v3 uses Rust constants as ZVVNMOD IDs and compact mapping rows", () => {
  const normalized = normalizeMappingPayload(structuredClone(fixture));
  assert.equal(normalized.schema, "zvvnmod-utn57-map-v3");
  assert.equal(normalized.sources[0].id, "A_INIT");
  assert.equal(normalized.sources[0].codepoint, "U+E000");
  assert.equal(Object.hasOwn(normalized.sources[0], "const"), false);
  assert.equal(normalized.mappings[0].id, "source:A_INIT");
  assert.deepEqual(normalized.mappings[0].sources, ["A_INIT"]);
  normalized.mappings.forEach(assertCompactRow);
});

test("editing both sides preserves independent ordered sequences of different lengths", () => {
  const row = fixture.mappings.find((entry) => entry.id === "target:A:isol");
  const edited = updateMappingEntry(
    row,
    ["A_INIT", "O_INIT", "I_MEDI"],
    ["A:isol"],
    "manual alignment",
  );
  assert.deepEqual(edited, {
    id: "target:A:isol",
    sources: ["A_INIT", "O_INIT", "I_MEDI"],
    targets: ["A:isol"],
    note: "manual alignment",
  });
});

test("mode is derived against the Git-loaded baseline and never serialized", () => {
  const direct = fixture.mappings.find((entry) => entry.id === "source:A_INIT");
  assert.equal(mappingMode(direct, direct), "direct");

  const rightOnly = fixture.mappings.find((entry) => entry.id === "target:Gx:init");
  assert.equal(mappingMode(rightOnly, rightOnly), "unmapped");

  const edited = updateMappingEntry(direct, ["O_INIT"], ["O:init"], "");
  assert.equal(mappingMode(direct, edited), "special");
  assertCompactRow(edited);
});

test("normalization accepts left-only and right-only rows but rejects both empty", () => {
  const normalized = normalizeMappingPayload(structuredClone(fixture));
  assert.ok(normalized.mappings.some((entry) => entry.sources.length === 0 && entry.targets.length));
  assert.ok(normalized.mappings.some((entry) => entry.sources.length && entry.targets.length === 0));

  const empty = structuredClone(fixture);
  empty.mappings[0].sources = [];
  empty.mappings[0].targets = [];
  assert.throws(() => normalizeMappingPayload(empty), /both sides empty/i);
});

test("normalization rejects unknown Rust source constants and target IDs", () => {
  const unknownSource = structuredClone(fixture);
  unknownSource.mappings[0].sources = ["NOT_A_RUST_CONST"];
  assert.throws(() => normalizeMappingPayload(unknownSource), /unknown ZVVNMOD source/i);

  const unknownTarget = structuredClone(fixture);
  unknownTarget.mappings[0].targets = ["Unknown:medi"];
  assert.throws(() => normalizeMappingPayload(unknownTarget), /unknown UTN57 target/i);
});

test("normalization is fail-closed for compact schema fields and catalogue order", () => {
  const extraMapping = structuredClone(fixture);
  extraMapping.mappings[0].mode = "direct";
  assert.throws(() => normalizeMappingPayload(extraMapping), /mapping fields/i);

  const extraSource = structuredClone(fixture);
  extraSource.sources[0].const = "A_INIT";
  assert.throws(() => normalizeMappingPayload(extraSource), /source fields/i);

  const sourceOrder = structuredClone(fixture);
  sourceOrder.sources[0].order = 99;
  assert.throws(() => normalizeMappingPayload(sourceOrder), /source order/i);
});

test("Git baseline scaffold permits value edits but rejects catalogue or row identity changes", () => {
  const override = structuredClone(fixture);
  override.mappings[0] = updateMappingEntry(
    override.mappings[0],
    ["O_INIT", "I_MEDI"],
    ["Hx:medi"],
    "reviewed",
  );
  assert.equal(hasSameGeneratedScaffold(fixture, override), true);

  const changedCatalogue = structuredClone(override);
  changedCatalogue.sources[0].glyph = "tampered";
  assert.equal(hasSameGeneratedScaffold(fixture, changedCatalogue), false);

  const changedId = structuredClone(override);
  changedId.mappings[0].id = "source:O_INIT";
  assert.equal(hasSameGeneratedScaffold(fixture, changedId), false);

  const reordered = structuredClone(override);
  [reordered.mappings[0], reordered.mappings[1]] = [reordered.mappings[1], reordered.mappings[0]];
  assert.equal(hasSameGeneratedScaffold(fixture, reordered), false);
});

test("serialization round-trips compact variable-length alignments", () => {
  const payload = normalizeMappingPayload(structuredClone(fixture));
  payload.mappings[0] = updateMappingEntry(
    payload.mappings[0],
    ["A_INIT", "O_INIT"],
    ["A:init"],
    "manual mapping",
  );
  const roundTrip = normalizeMappingPayload(JSON.parse(serializeMappingPayload(payload)));
  assert.deepEqual(roundTrip.mappings[0], {
    id: "source:A_INIT",
    sources: ["A_INIT", "O_INIT"],
    targets: ["A:init"],
    note: "manual mapping",
  });
});
