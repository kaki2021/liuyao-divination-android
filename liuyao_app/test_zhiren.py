"""知人离线单元测试，不读取真实人物资料，也不调用付费模型。"""
import tempfile
import unittest
from pathlib import Path
from .zhiren_store import ZhirenStore, ZhirenError
from .zhiren_match import matches


class ZhirenTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ZhirenStore(Path(self.temp.name) / "people.sqlite3")

    @staticmethod
    def person(name="小王"):
        return dict(name=name, city="成都", industry="软件", occupation="开发",
                    categories=["朋友"], skills=["AI Agent"], interests=["露营"],
                    needs=["合作"], contact="", relationship="", notes="私人备注")

    def test_save_match_and_owner_isolation(self):
        saved = self.store.save_person("a", {"person": self.person()}, "req-1")
        self.assertEqual(saved["name"], "小王")
        self.assertEqual(self.store.list_people("b"), [])
        result = matches("成都 AI 交流会", self.store.list_people("a"))
        self.assertEqual(result["matches"][0]["person_id"], saved["person_id"])
        self.assertTrue(result["matches"][0]["reasons"])

    def test_update_requires_version(self):
        saved = self.store.save_person("a", {"person": self.person()}, "req-1")
        data = self.person("新称呼")
        updated = self.store.save_person("a", {"person": data, "person_id": saved["person_id"],
                                              "expected_version": 1}, "req-2")
        self.assertEqual(updated["version"], 2)
        with self.assertRaises(ZhirenError):
            self.store.save_person("a", {"person": data, "person_id": saved["person_id"],
                                         "expected_version": 1}, "req-3")

    def test_idempotency_and_no_phantom_notification(self):
        saved = self.store.save_person("a", {"person": self.person()}, "req-1")
        self.assertEqual(saved, self.store.save_person("a", {"person": self.person()}, "req-1"))
        post = self.store.save_post("a", {"kind": "活动", "content": "周末露营",
                                       "recipient_ids": [saved["person_id"]]}, "post-1")
        self.assertEqual(post["delivery_status"], "not_sent")
        self.assertEqual(self.store.list_posts("a")[0]["recipient_ids"], [saved["person_id"]])
        with self.assertRaises(ZhirenError):
            self.store.save_post("b", {"kind": "活动", "content": "周末露营",
                                       "recipient_ids": [saved["person_id"]]}, "post-2")

    def test_card_field_allowlist(self):
        card = self.store.save_card("a", {"name": "名片A", "audience": "朋友",
                                          "fields": ["name", "skills"]}, "card-1")
        self.assertEqual(self.store.list_cards("a")[0]["card_id"], card["card_id"])
        with self.assertRaises(ZhirenError):
            self.store.save_card("a", {"name": "秘密", "audience": "朋友",
                                       "fields": ["notes"]}, "card-2")


if __name__ == "__main__":
    unittest.main()
