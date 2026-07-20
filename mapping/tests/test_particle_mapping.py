from __future__ import annotations

import hashlib
import json
import runpy
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARTICLE_JSON = ROOT / "mapping/data/zvvnmod-utn57-particles.json"
MAPPING_JSON = ROOT / "mapping/data/zvvnmod-utn57-map.json"
GENERATOR = ROOT / "mapping/scripts/generate-particle-mapping.py"
VERIFIER = ROOT / "mapping/scripts/verify-static-page.py"


class ParticleMappingTests(unittest.TestCase):
    def load_particles(self) -> dict:
        return json.loads(PARTICLE_JSON.read_text())

    def test_compact_particle_data_omits_leading_context_and_uses_rust_names(self) -> None:
        payload = self.load_particles()
        self.assertEqual(payload["schema"], "zvvnmod-utn57-particles-v3")
        self.assertEqual(len(payload["mappings"]), 47)
        self.assertEqual(set(payload), {"schema", "description", "provenance", "mappings"})
        expected_fields = {"id", "pattern", "particleIndices", "sources", "targets", "note"}
        for row in payload["mappings"]:
            with self.subTest(row=row["id"]):
                self.assertEqual(set(row), expected_fields)
                self.assertFalse(row["pattern"].startswith(("mvs ", "nnbsp ")))
                self.assertNotIn("MVS", row["targets"])
                self.assertTrue(all(not source.startswith("U+") for source in row["sources"]))
                self.assertTrue(row["sources"] or row["targets"])

    def test_particle_07_matches_requested_compact_sequences(self) -> None:
        row = self.load_particles()["mappings"][6]
        self.assertEqual(
            row,
            {
                "id": "particle:07",
                "pattern": "i y a r",
                "particleIndices": [0, 1],
                "sources": ["I_INIT", "I_MEDI", "A_MEDI", "R_FINA"],
                "targets": ["I:init", "I:medi", "A:medi", "R:fina"],
                "note": "",
            },
        )

    def test_generated_sequences_use_current_catalogues_and_allow_unequal_lengths(self) -> None:
        particles = self.load_particles()
        mapping = json.loads(MAPPING_JSON.read_text())
        source_ids = {source["id"] for source in mapping["sources"]}
        target_ids = {target["id"] for target in mapping["targets"]}
        unequal = 0
        for row in particles["mappings"]:
            self.assertTrue(set(row["sources"]) <= source_ids)
            self.assertTrue(set(row["targets"]) <= target_ids)
            if len(row["sources"]) != len(row["targets"]):
                unequal += 1
        self.assertGreater(unequal, 0)

    def test_reviewed_particle_source_sequences_are_preserved(self) -> None:
        rows = {row["id"]: row for row in self.load_particles()["mappings"]}
        reviewed = {
            "particle:05": ["A_INIT", "CH_MEDI", "A_MEDI", "N_MEDI", "N_MEDI", "A_MEDI", "A_FINA"],
            "particle:15": ["O_INIT", "O_MEDI", "A_FINA"],
            "particle:16": ["O_INIT", "O_MEDI", "A_FINA"],
            "particle:25": ["N_INIT", "O_MEDI", "G_MEDI", "O_MEDI", "A_FINA"],
            "particle:32": ["D_INIT", "A_MEDI", "N_MEDI", "N_MEDI", "A_MEDI", "A_FINA"],
            "particle:37": ["D_INIT", "A_MEDI", "I_MEDI", "AA_FINA"],
            "particle:44": ["D_INIT", "O_MEDI", "N_MEDI", "N_MEDI", "A_MEDI", "R_FINA"],
        }
        self.assertEqual({row_id: rows[row_id]["sources"] for row_id in reviewed}, reviewed)

    def test_generator_reproduces_committed_particle_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "particles.json"
            subprocess.run(
                ["python3", str(GENERATOR), "--output", str(output)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            generated = json.loads(output.read_text())
            current = self.load_particles()
            self.assertEqual(generated["schema"], current["schema"])
            self.assertEqual(generated["description"], current["description"])
            self.assertEqual(generated["provenance"], current["provenance"])
            self.assertEqual(
                [
                    (row["id"], row["pattern"], row["particleIndices"])
                    for row in generated["mappings"]
                ],
                [
                    (row["id"], row["pattern"], row["particleIndices"])
                    for row in current["mappings"]
                ],
            )

    def test_generator_rejects_observation_drift(self) -> None:
        observations = json.loads(
            (ROOT / "mapping/data/particle-shaping-observations.json").read_text()
        )
        observations["observations"][0]["pattern"] = "tampered"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "observations.json"
            output = Path(directory) / "out.json"
            path.write_text(json.dumps(observations))
            result = subprocess.run(
                [
                    "python3",
                    str(GENERATOR),
                    "--observations",
                    str(path),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checksum mismatch", result.stdout + result.stderr)

    def test_semantic_sequence_helper_omits_unknown_source_counterparts(self) -> None:
        module = runpy.run_path(str(GENERATOR))
        align = module["semantic_zvvnmod_sequence"]
        mapping = json.loads(MAPPING_JSON.read_text())
        self.assertEqual(
            align(["I:init", "I:medi", "A:medi", "R:fina"], mapping),
            ["I_INIT", "I_MEDI", "A_MEDI", "R_FINA"],
        )
        self.assertEqual(align(["Hx:medi", "A:fina"], mapping), ["A_FINA"])

    def test_context_helper_omits_mvs_and_nnbsp_prefixes(self) -> None:
        module = runpy.run_path(str(GENERATOR))
        strip_context = module["strip_leading_particle_context"]
        self.assertEqual(
            strip_context("mvs i y", [1, 2], ["MVS", "I:init", "I:medi"]),
            ("i y", [0, 1], ["I:init", "I:medi"]),
        )
        self.assertEqual(
            strip_context("nnbsp i", [1], ["MVS", "I:init"]),
            ("i", [0], ["I:init"]),
        )
        self.assertEqual(
            strip_context("u u", [0], ["O:init", "U:fina"]),
            ("u u", [0], ["O:init", "U:fina"]),
        )

    def test_particle_markup_and_renderer_support_independent_sequences(self) -> None:
        page = (ROOT / "mapping/index.html").read_text()
        renderer = (ROOT / "mapping/particle-mappings.js").read_text()
        self.assertLess(page.index('id="mapping-workbench"'), page.index('id="particle-mappings"'))
        self.assertIn('src="particle-mappings.js?v=4"', page)
        self.assertIn("Leading MVS/NNBSP context is omitted", page)
        self.assertIn('from "./particle-model.mjs?v=4"', renderer)
        self.assertIn('dataset.action = "add-particle-value"', renderer)
        self.assertIn('"remove-particle-value"', renderer)
        self.assertIn('"move-particle-up"', renderer)
        self.assertIn('"move-particle-down"', renderer)
        self.assertIn("draft.sources, draft.targets, draft.note", renderer)
        self.assertIn("baseline.sources, baseline.targets, baseline.note", renderer)
        self.assertNotIn("innerHTML", renderer)
        self.assertNotIn("defaultZvvnmodCodes", renderer)
        self.assertNotIn("zvvnmodCodes", renderer)

    def test_capture_pipeline_remains_pinned_and_auditable(self) -> None:
        script = (ROOT / "mapping/scripts/capture-particle-observations.py").read_text()
        self.assertIn('MONGFONTBUILDER_COMMIT = "539b455075486f70889e6de9909eac5dea839d8a"', script)
        self.assertIn('MECO_COMMIT = "7edff334d33fc367596d1d33406b33bccb8ddc60"', script)
        self.assertIn('"from": "delehi", "to": "zvvnmod"', script)
        self.assertIn("require_revision", script)
        snapshot = ROOT / "mapping/data/particle-shaping-observations.json"
        self.assertEqual(
            hashlib.sha256(snapshot.read_bytes()).hexdigest(),
            "b480e08b16c7efd531b968612a53e6718a96c11578a9d71670994b7033c793ab",
        )

    def verify_particle(self, payload: dict) -> subprocess.CompletedProcess[str]:
        with tempfile.NamedTemporaryFile("w", suffix=".json") as temporary:
            json.dump(payload, temporary)
            temporary.flush()
            return subprocess.run(
                ["uv", "run", "--script", str(VERIFIER), "--particle-json", temporary.name],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

    def test_verifier_accepts_compact_unequal_particle_override(self) -> None:
        payload = self.load_particles()
        payload["mappings"][6]["sources"] = ["I_INIT"]
        payload["mappings"][6]["targets"] = ["I:init", "I:medi", "R:fina"]
        payload["mappings"][6]["note"] = "Reviewed unequal sequence"
        result = self.verify_particle(payload)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_verifier_rejects_particle_scaffold_and_unknown_value_changes(self) -> None:
        changed_pattern = self.load_particles()
        changed_pattern["mappings"][0]["pattern"] = "tampered"
        result = self.verify_particle(changed_pattern)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("changed generated field pattern", result.stdout + result.stderr)

        unknown = self.load_particles()
        unknown["mappings"][0]["sources"] = ["UNKNOWN_CONST"]
        result = self.verify_particle(unknown)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown particle ZVVNMOD source", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
