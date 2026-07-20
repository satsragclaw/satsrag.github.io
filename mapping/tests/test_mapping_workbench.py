from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAPPING_DATA = ROOT / "mapping/data"
MAPPING_JSON = MAPPING_DATA / "zvvnmod-utn57-map.json"
CODES_JSON = MAPPING_DATA / "zvvnmod-codes.json"
PAGE_HTML = ROOT / "mapping/index.html"


class MappingDataTests(unittest.TestCase):
    def load_mapping(self) -> dict:
        return json.loads(MAPPING_JSON.read_text())

    def test_compact_rust_named_mapping_preserves_inventory_alignment(self) -> None:
        mapping = self.load_mapping()
        codes = json.loads(CODES_JSON.read_text())
        retained_merged = {"N_AA_FINA", "HX_AA_FINA"}
        expected_sources = [
            code["const"]
            for group in codes["groups"]
            for entries in group["single"].values()
            for code in entries
        ] + [
            code["const"]
            for group in codes["groups"]
            for entries in group["merged"].values()
            for code in entries
            if code["const"] in retained_merged
        ] + [code["const"] for group in codes["groups"] for code in group["special"]]
        source_ids = [source["id"] for source in mapping["sources"]]

        self.assertEqual(mapping["schema"], "zvvnmod-utn57-map-v3")
        self.assertEqual(len(source_ids), 80)
        self.assertEqual(set(source_ids), set(expected_sources))
        self.assertEqual(len(mapping["mappings"]), 97)
        self.assertEqual(sum(not entry["sources"] for entry in mapping["mappings"]), 5)
        self.assertEqual(sum(not entry["targets"] for entry in mapping["mappings"]), 2)
        self.assertTrue(all(entry["sources"] or entry["targets"] for entry in mapping["mappings"]))
        self.assertTrue(
            all(set(entry) == {"id", "sources", "targets", "note"} for entry in mapping["mappings"])
        )
        self.assertTrue(all("const" not in source for source in mapping["sources"]))
        self.assertEqual(mapping["sources"][0]["codepoint"], "U+E000")

    def test_targets_are_ordered_and_every_mapping_value_exists(self) -> None:
        mapping = self.load_mapping()
        source_ids = {source["id"] for source in mapping["sources"]}
        targets = mapping["targets"]
        target_ids = [target["id"] for target in targets]
        self.assertEqual(target_ids[0], "A:isol")
        self.assertEqual(len(target_ids), len(set(target_ids)))
        self.assertEqual([target["order"] for target in targets], list(range(len(targets))))
        self.assertTrue(all(value in source_ids for row in mapping["mappings"] for value in row["sources"]))
        self.assertTrue(all(value in set(target_ids) for row in mapping["mappings"] for value in row["targets"]))

    def test_current_mapping_keeps_generated_rows_and_reviewed_alignments(self) -> None:
        payload = self.load_mapping()
        entries = {entry["id"]: entry for entry in payload["mappings"]}
        sources = {source["id"]: source for source in payload["sources"]}
        self.assertEqual(entries["source:A_INIT"]["targets"], ["A:init"])
        self.assertNotIn("source:B_I_ISOL", entries)
        self.assertEqual(sources["HX_AA_FINA"]["name"], "Hx f Aa f")
        self.assertEqual(entries["source:HX_AA_FINA"]["targets"], ["Hx:fina", "Aa:fina"])
        self.assertEqual(entries["source:NIRUGU"]["targets"], [])
        self.assertEqual(entries["source:IR_FINA"]["targets"], [])
        reviewed = {
            "target:A:isol": ["A_INIT", "AA_FINA"],
            "target:Aa:isol": ["AA_FINA"],
            "target:B2:fina": ["O_MEDI", "AA_FINA"],
            "target:Cr:init": ["O_INIT", "O_MEDI"],
            "target:Dd:medi": ["O_MEDI", "A_MEDI"],
            "target:Dd:fina": ["O_MEDI", "A_FINA"],
            "target:G:fina": ["I_MEDI", "AA_FINA"],
            "target:H:medi": ["A_MEDI", "A_MEDI"],
            "target:Hx:medi": ["M_MEDI", "M_MEDI"],
            "target:K2:init": ["K_INIT"],
            "target:K2:medi": ["K_MEDI"],
            "target:K2:fina": ["K_FINA"],
        }
        self.assertEqual({row_id: entries[row_id]["sources"] for row_id in reviewed}, reviewed)

    def test_workbench_markup_and_controller_use_git_baseline(self) -> None:
        page = PAGE_HTML.read_text()
        controller = (ROOT / "mapping/workbench.js").read_text()
        self.assertLess(page.index('id="utn57"'), page.index('id="zvvnmod"'))
        self.assertLess(page.index('id="zvvnmod"'), page.index('id="mapping-workbench"'))
        self.assertIn('src="workbench.js?v=6"', page)
        self.assertIn('src="particle-mappings.js?v=4"', page)
        self.assertIn("mappingMode(sourceCombinedPayload.mapping.mappings[index], entry)", controller)
        self.assertIn("const baseline = sourceCombinedPayload.mapping.mappings[index];", controller)
        self.assertIn("baseline.sources,", controller)
        self.assertIn("baseline.targets,", controller)
        self.assertIn("baseline.note,", controller)
        self.assertNotIn("defaultSources", controller)
        self.assertNotIn("defaultTargets", controller)
        self.assertIn('schema: "zvvnmod-utn57-workbench-v2"', controller)
        self.assertIn("async function gitBaselineDigest(", controller)
        self.assertIn('crypto.subtle.digest("SHA-256", bytes)', controller)
        self.assertIn("expectedBaseline: sourceCombinedPayload.baseline", controller)

    def test_controller_retains_sequence_accessibility_and_operation_guards(self) -> None:
        controller = (ROOT / "mapping/workbench.js").read_text()
        self.assertIn('select.setAttribute("aria-label", `${noun} ${position + 1}`)', controller)
        self.assertIn('addSelect.setAttribute("aria-label", `${noun} to add`)', controller)
        self.assertIn("function focusDraftTarget(", controller)
        self.assertIn("function focusEditButton(", controller)
        self.assertIn("function guardActiveDraft(", controller)
        self.assertGreaterEqual(controller.count("guardActiveDraft("), 6)
        self.assertIn("function beginOperation()", controller)
        self.assertIn("function finishOperation()", controller)
        self.assertIn("serializeCombinedPayload(combinedPayload)", controller)
        self.assertIn("normalizeCombinedPayload(JSON.parse(await file.text()), {", controller)

    def test_dual_sequence_styles_and_ultra_narrow_header_remain(self) -> None:
        styles = (ROOT / "mapping/styles.css").read_text()
        self.assertIn(".mapping-editor-grid", styles)
        self.assertIn(".sequence-editor-row", styles)
        self.assertIn(".source-select", styles)
        self.assertIn("@media (max-width: 420px)", styles)
        self.assertIn('.brand::before { content: "S";', styles)
        self.assertIn("select:focus-visible", styles)

    def run_verifier_with(self, payload: dict) -> subprocess.CompletedProcess[str]:
        with tempfile.NamedTemporaryFile("w", suffix=".json") as temporary:
            json.dump(payload, temporary)
            temporary.flush()
            return subprocess.run(
                [
                    "uv",
                    "run",
                    "--script",
                    str(ROOT / "mapping/scripts/verify-static-page.py"),
                    "--mapping-json",
                    temporary.name,
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

    def test_verifier_accepts_compact_unequal_length_override(self) -> None:
        payload = self.load_mapping()
        entry = next(item for item in payload["mappings"] if item["sources"] == ["N_MEDI"])
        entry["sources"] = ["N_MEDI", "A_INIT", "O_INIT"]
        entry["targets"] = ["Hx:medi"]
        entry["note"] = "Reviewed exception"
        result = self.run_verifier_with(payload)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_verifier_rejects_unknown_values_and_schema_fields(self) -> None:
        unknown_target = self.load_mapping()
        unknown_target["mappings"][0]["targets"] = ["Unknown:medi"]
        result = self.run_verifier_with(unknown_target)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown UTN57 target", result.stdout + result.stderr)

        unknown_source = self.load_mapping()
        unknown_source["mappings"][0]["sources"] = ["UNKNOWN_CONST"]
        result = self.run_verifier_with(unknown_source)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown ZVVNMOD source", result.stdout + result.stderr)

        extra = self.load_mapping()
        extra["mappings"][0]["mode"] = "direct"
        result = self.run_verifier_with(extra)
        self.assertNotEqual(result.returncode, 0)

    def test_verifier_rejects_catalogue_and_row_identity_changes(self) -> None:
        base = self.load_mapping()
        mutations = []
        changed_source = json.loads(json.dumps(base))
        changed_source["sources"][0]["glyph"] = "tampered"
        mutations.append(changed_source)
        changed_id = json.loads(json.dumps(base))
        changed_id["mappings"][0]["id"] = "source:O_INIT"
        mutations.append(changed_id)
        reordered = json.loads(json.dumps(base))
        reordered["mappings"][0], reordered["mappings"][1] = (
            reordered["mappings"][1],
            reordered["mappings"][0],
        )
        mutations.append(reordered)
        for payload in mutations:
            result = self.run_verifier_with(payload)
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
