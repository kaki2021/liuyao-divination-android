"""The model selects a contextual relation; the server derives kinship."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "software_prep"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validate_ai_contract import ContractError, check_schema, load_pack
from liuyao_app.runtime_contract import runtime_output_schema
from liuyao_app.selection_projection import project_selection


class SelectionProjectionTests(unittest.TestCase):
    def selection(self, **fields):
        candidate = {
            "candidate_id": "PRIMARY", "object_role": "本次目标", "function": "用户实际用途",
            "relation": "controlled_by_me", "purpose": "primary",
            "rule_refs": ["interpretation.functional_role"],
            "evidence_quotes": [{"evidence_id": "USER_QUESTION", "quote": "本次问题"}],
            "assumptions": [],
        }
        candidate.update(fields)
        return {
            "binding": {"analysis_run_id": "RUN", "input_snapshot_id": "INPUT"},
            "status": "ready", "candidates": [candidate], "selected_primary_id": "PRIMARY",
            "route_requests": [], "unresolved": [], "clarifying_questions": [],
        }

    def test_all_five_relations_are_projected_without_mutation(self):
        # Independent explicit expectations guard mapping direction.
        for relation, expected in (
            ("generates_me", "parents"), ("same_as_me", "siblings"),
            ("generated_by_me", "offspring"), ("controlled_by_me", "wealth"),
            ("controls_me", "official_ghost"),
        ):
            with self.subTest(relation=relation):
                original = self.selection(relation=relation)
                before = copy.deepcopy(original)
                output, changes = project_selection(original)
                self.assertEqual(output["candidates"][0]["six_relative"], expected)
                self.assertEqual(original, before)
                self.assertEqual(len(changes), 1)
                self.assertIn("$.candidates[0].six_relative", changes[0])
                del output["candidates"][0]["six_relative"]
                self.assertEqual(output, original)
                self.assertIsNot(output["candidates"], original["candidates"])

    def test_explicit_correct_values_stay_compatible(self):
        original = self.selection(six_relative="wealth")
        output, changes = project_selection(original)
        self.assertEqual(output, original)
        self.assertEqual(changes, [])
        self.assertIsNot(output, original)

    def test_explicit_conflicting_or_null_values_are_not_repaired(self):
        for value in ("parents", "siblings", None, [], "UNKNOWN"):
            with self.subTest(value=value):
                original = self.selection(six_relative=value)
                before = copy.deepcopy(original)
                with self.assertRaisesRegex(ContractError, r"candidates\[0\]\.six_relative"):
                    project_selection(original)
                self.assertEqual(original, before)

    def test_subject_references_receive_null_without_becoming_siblings(self):
        for reference in ("shi", "shi_body"):
            with self.subTest(reference=reference):
                output, changes = project_selection(self.selection(subject_reference=reference, relation=None))
                self.assertIsNone(output["candidates"][0]["six_relative"])
                self.assertEqual(len(changes), 1)
                original = self.selection(subject_reference=reference, relation=None, six_relative=None)
                self.assertEqual(project_selection(original), (original, []))

    def test_subject_reference_contradictions_are_rejected(self):
        for fields in (
            {"subject_reference": "shi", "relation": "same_as_me"},
            {"subject_reference": "shi_body", "relation": None, "six_relative": "siblings"},
        ):
            with self.subTest(fields=fields), self.assertRaises(ContractError):
                project_selection(self.selection(**fields))

    def test_invalid_relation_does_not_gain_a_plausible_kinship(self):
        for relation in (None, "UNDEFINED", [], {}):
            with self.subTest(relation=relation):
                original = self.selection(relation=relation)
                self.assertEqual(project_selection(original), (original, []))
        original = self.selection(subject_reference="shi", relation=None)
        del original["candidates"][0]["relation"]
        self.assertEqual(project_selection(original), (original, []))

    def test_multiple_candidates_keep_the_declared_choice_and_evidence(self):
        original = self.selection()
        candidate = copy.deepcopy(original["candidates"][0])
        candidate.update(candidate_id="SUPPORT", relation="generates_me", purpose="supporting")
        original["candidates"].append(candidate)
        output, changes = project_selection(original)
        self.assertEqual(output["selected_primary_id"], "PRIMARY")
        self.assertEqual([c["six_relative"] for c in output["candidates"]], ["wealth", "parents"])
        self.assertEqual(output["candidates"][1]["evidence_quotes"], candidate["evidence_quotes"])
        self.assertEqual(len(changes), 2)

    def test_optional_runtime_field_becomes_required_validated_internal_data(self):
        pack = load_pack()
        original = self.selection()
        check_schema(original, runtime_output_schema("selection", pack, {}))
        with self.assertRaises(ContractError):
            check_schema(original, pack["stages"]["selection"]["output_schema"])
        output, _ = project_selection(original)
        check_schema(output, pack["stages"]["selection"]["output_schema"])
        check_schema(output, runtime_output_schema("selection", pack, {}))

    def test_invalid_surrounding_structure_is_not_invented(self):
        for original in ({}, {"candidates": None}, {"candidates": [None, "invalid"]}):
            with self.subTest(original=original):
                self.assertEqual(project_selection(original), (original, []))


if __name__ == "__main__":
    unittest.main()
