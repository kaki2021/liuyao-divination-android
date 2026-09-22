"""SQLite and HTTP checks for optional people context and computed foundations.

The provider is a synthetic contract fixture. These checks establish data
boundaries and retention, not the truth of divination outcomes or live API
availability.
"""
import copy
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "software_prep"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from case_store import Actor, CaseStore
from liuyao_app.pipeline import calculate_chart, run_analysis
from liuyao_app.server import Application, Server, case_diagnostics
from liuyao_app.test_pipeline import BoundProvider


INPUT = {
    "question": "我准备卖掉余粮，想问能否成交。",
    "lines": ["young_yang", "old_yin", "young_yang", "young_yin", "young_yang", "young_yin"],
    "actual_cast_time": "2026-09-18T10:00:00+08:00",
}
PROFILE = {
    "subject": "other", "querent_age": 30, "subject_age": 8,
    "relationship": "所问对象是我的孩子",
    "background": "本次相关背景私密标记 PROFILE_PRIVATE_5821；由家长代为询问。",
}


class OmittedKinshipProvider(BoundProvider):
    """The model chooses a relation; code derives its fixed kinship mapping."""
    def __call__(self, *args, **kwargs):
        response = super().__call__(*args, **kwargs)
        if self.calls[-1]["stage"] == "selection":
            out = copy.deepcopy(response["parsed_json"])
            del out["candidates"][0]["six_relative"]
            response.update(parsed_json=out, raw_text=json.dumps(out, ensure_ascii=False))
        return response


class FoundationProfileFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "cases.sqlite3"
        self.actor = Actor("profile-owner", "profile-session")
        self.store = CaseStore(self.path)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def create(self, profile=None):
        data = copy.deepcopy(INPUT)
        if profile is not None:
            data["person_info"] = copy.deepcopy(profile)
        created = self.store.create_case(self.actor, data, idempotency_key=uuid.uuid4().hex)
        return created["case_id"], data

    def analyze(self, case_id, provider=None, revision=1):
        provider = provider or BoundProvider()
        result = run_analysis(self.path, self.actor, case_id, "deepseek", "fixture-model", revision,
                              provider_call=provider)
        self.assertEqual(result["status"], "completed", result.get("error"))
        self.assertEqual([call["stage"] for call in provider.calls],
                         ["intent", "selection", "interpretation", "report"])
        return result, provider

    def test_existing_case_without_people_information_reaches_report(self):
        case_id, data = self.create()
        result, provider = self.analyze(case_id)
        self.assertEqual(result["clarifying_questions"], [])
        for call in provider.calls[:2]:
            self.assertNotIn("USER_PERSON_INFO", [item["evidence_id"] for item in call["input"]["user_evidence"]])
        run = self.store.export_case(self.actor, case_id)["analysis_runs"][0]
        self.assertEqual(run["input_snapshot"]["input"], data)
        self.assertEqual(len(run["ai_events"]), 4)

    def test_other_person_context_reaches_intent_selection_and_interpretation(self):
        case_id, _ = self.create(PROFILE)
        _, provider = self.analyze(case_id)
        evidence = []
        for call in provider.calls[:2]:
            person = next(item for item in call["input"]["user_evidence"] if item["evidence_id"] == "USER_PERSON_INFO")
            self.assertEqual(person["origin"], "user_background")
            self.assertIn("提问者起卦时年龄：30周岁", person["text"])
            self.assertIn("所问对象起卦时年龄：8周岁", person["text"])
            self.assertIn(PROFILE["relationship"], person["text"])
            self.assertIn(PROFILE["background"], person["text"])
            evidence.append(person)
        self.assertEqual(evidence[0], evidence[1])
        contextual = [fact for fact in provider.calls[2]["input"]["facts"] if fact["kind"] == "context"]
        self.assertEqual(sum(fact["value"] == evidence[0]["text"] for fact in contextual), 1)

    def test_recording_age_does_not_switch_the_chart_or_five_element_matrix(self):
        expected = calculate_chart(INPUT)
        for profile in (PROFILE, {**PROFILE, "subject_age": 13}, {"subject": "self", "querent_age": 30}):
            with self.subTest(profile=profile):
                case_id, _ = self.create(profile)
                result, _ = self.analyze(case_id)
                actual=copy.deepcopy(result["chart"])
                actual["comprehensive_analysis"].pop("use_selection",None)
                self.assertEqual(actual, expected)

    def test_omitted_kinship_is_derived_once_and_the_original_reply_is_retained(self):
        case_id, _ = self.create(PROFILE)
        result, provider = self.analyze(case_id, OmittedKinshipProvider())
        selected = result["stage_outputs"]["selection"]["candidates"][0]
        self.assertEqual(selected["relation"], "controlled_by_me")
        self.assertEqual(selected["six_relative"], "wealth")
        facts = {fact["fact_id"]: fact for fact in provider.calls[2]["input"]["facts"]}
        self.assertEqual(facts["FUNCTION_SELECTION"]["value"], "wealth")
        expected_positions = [line["position"] for line in result["chart"]["main"]["lines"]
                              if line["relative_code"] == "wealth"]
        self.assertEqual(json.loads(facts["MATCHING_LINES"]["value"]), expected_positions)
        run = self.store.export_case(self.actor, case_id)["analysis_runs"][0]
        attempt = next(event["attempt"] for event in run["ai_events"] if event["attempt"]["stage"] == "selection")
        self.assertNotIn("six_relative", json.loads(attempt["raw_output"])["candidates"][0])
        self.assertTrue(any("derived by server" in change for change in attempt["model_run_metadata"]["normalization_changes"]))
        self.assertEqual(attempt["validation_errors"], [])

    def test_ai_receives_exactly_the_basic_facts_retained_for_the_screen(self):
        case_id, _ = self.create()
        result, provider = self.analyze(case_id)
        basic = result["chart"]["basic_analysis"]
        self.assertTrue(basic["sections"])
        self.assertTrue(all(section["items"] for section in basic["sections"]))
        projected = provider.calls[2]["input"]["facts"]
        by_id = {fact["fact_id"]: fact for fact in projected}
        self.assertEqual(len(by_id), len(projected), "A fact must not be projected twice")
        self.assertEqual([by_id[fact["fact_id"]] for fact in basic["facts"]], basic["facts"])
        self.assertIn("CHART_PALACE_STAGE", by_id)
        self.assertIn("CAL_DAY_TO_LINE_1", by_id)
        self.assertIn("REL_YING_TO_SHI", by_id)
        run = self.store.export_case(self.actor, case_id)["analysis_runs"][0]
        self.assertEqual(run["outcome"]["result"]["chart_snapshot"]["basic_analysis"], basic)

    def test_local_demo_has_basic_analysis_without_any_ai_call(self):
        case_id, _ = self.create(PROFILE)
        def forbidden(*args, **kwargs):
            self.fail("Deterministic analysis must not call a provider")
        result = run_analysis(self.path, self.actor, case_id, "demo", "", 1, provider_call=forbidden)
        self.assertTrue(result["is_demo"])
        self.assertTrue(result["chart"]["basic_analysis"]["sections"])
        self.assertEqual(result["stage_outputs"], {})
        self.assertEqual(self.store.export_case(self.actor, case_id)["analysis_runs"][0]["ai_events"], [])

    def test_profile_correction_changes_new_context_without_rewriting_the_prior_run(self):
        case_id, data = self.create(PROFILE)
        first, first_provider = self.analyze(case_id)
        old_run = copy.deepcopy(self.store.export_case(self.actor, case_id)["analysis_runs"][0])
        revised = copy.deepcopy(data)
        revised["person_info"]["subject_age"] = 9
        revised["person_info"]["background"] = "更正：是另一项家庭事务。"
        self.store.revise_case(self.actor, case_id, revised, reason="更正起卦时年龄和背景",
                               expected_revision_seq=1, idempotency_key="profile-correction")
        second, second_provider = self.analyze(case_id, revision=2)
        exported = self.store.export_case(self.actor, case_id)
        self.assertEqual(exported["analysis_runs"][0], old_run)
        self.assertEqual(exported["analysis_runs"][1]["input_snapshot"]["input"], revised)
        self.assertNotEqual(first["analysis_run_id"], second["analysis_run_id"])
        self.assertEqual(first["chart"], second["chart"])
        first_text = first_provider.calls[0]["input"]["user_evidence"][1]["text"]
        second_text = second_provider.calls[0]["input"]["user_evidence"][1]["text"]
        self.assertIn("所问对象起卦时年龄：8周岁", first_text)
        self.assertIn("所问对象起卦时年龄：9周岁", second_text)
        self.assertNotIn(PROFILE["background"], second_text)

    def test_full_export_preserves_profile_but_diagnostics_exclude_it(self):
        case_id, data = self.create(PROFILE)
        self.analyze(case_id)
        exported = self.store.export_case(self.actor, case_id)
        self.assertEqual(exported["original_input"]["person_info"], data["person_info"])
        diagnostics = case_diagnostics(exported, "foundation-fixture")
        serialized = json.dumps(diagnostics, ensure_ascii=False)
        for private in (INPUT["question"], PROFILE["relationship"], PROFILE["background"],
                        "person_info", "USER_PERSON_INFO", "querent_age", "subject_age"):
            self.assertNotIn(private, serialized)
        self.assertEqual(len(diagnostics["analysis_runs"][0]["attempts"]), 4)


class FoundationProfileHTTPTests(unittest.TestCase):
    def test_http_save_and_reopen_show_foundation_before_any_analysis(self):
        with tempfile.TemporaryDirectory() as temporary:
            app = Application(temporary)
            server = Server(("127.0.0.1", 0), app)
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
            thread.start()
            cookie = ""

            def request(method, path, data=None, expected=200):
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                headers = {"Cookie": cookie, "X-App-Request": "1", "X-Idempotency-Key": uuid.uuid4().hex}
                body = None
                if data is not None:
                    headers["Content-Type"] = "application/json"
                    body = json.dumps(data, ensure_ascii=False).encode()
                connection.request(method, path, body, headers)
                response = connection.getresponse()
                content = response.read()
                received_headers = dict(response.getheaders())
                connection.close()
                self.assertEqual(response.status, expected, content)
                return content, received_headers

            try:
                _, headers = request("GET", "/")
                cookie = headers["Set-Cookie"].split(";")[0]
                content, _ = request("POST", "/api/cases", {"input": {**INPUT, "person_info": PROFILE}}, expected=201)
                saved = json.loads(content)
                self.assertTrue(saved["chart"]["basic_analysis"]["sections"])
                content, _ = request("GET", "/api/cases/" + saved["case_id"])
                reopened = json.loads(content)
                self.assertEqual(reopened["chart"]["basic_analysis"], saved["chart"]["basic_analysis"])
                self.assertEqual(reopened["case"]["original_input"]["person_info"], PROFILE)
                self.assertEqual(reopened["case"]["analysis_runs"], [])
                content, _ = request("GET", "/api/cases/" + saved["case_id"] + "/diagnostics")
                self.assertNotIn(PROFILE["background"], content.decode())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
                app.close()


if __name__ == "__main__":
    unittest.main()
