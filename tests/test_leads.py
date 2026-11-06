import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import agent
import leads


class AddLeadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        registry = patch("leads.DATABASE", Path(self.temp.name) / "leads.sqlite3")
        registry.start()
        self.addCleanup(registry.stop)
        self.client = MagicMock()
        self.client.__enter__.return_value = self.client
        memory = patch("agent.memory", return_value=self.client)
        memory.start()
        self.addCleanup(memory.stop)
        self.data = {"name": "Priya Nair", "company": "Harbour Dental", "language": "English",
                     "note": "Asked for pricing after 5pm"}

    def test_add_retains_original_note_in_new_bank_before_listing(self):
        def retain(**kwargs):
            self.assertEqual(len(leads.list_leads()), 4)
            self.assertIn(self.data["note"], kwargs["content"])
            self.assertIn("Priya Nair prefers English", kwargs["content"])
        self.client.retain.side_effect = retain
        result = agent.add_lead(self.data)
        bank_id = result["lead"]["id"]
        self.assertTrue(bank_id.startswith("lead-priya-nair-"))
        self.assertEqual(self.client.create_bank.call_args.kwargs["bank_id"], bank_id)
        self.assertEqual(self.client.retain.call_args.kwargs["bank_id"], bank_id)
        self.assertEqual(leads.get_lead(bank_id)["company"], "Harbour Dental")
        self.assertEqual(len(leads.list_leads()), 5)
        self.client.reflect.return_value = SimpleNamespace(text="Priya asked for pricing after 5pm.")
        self.client.recall.return_value.model_dump.return_value = {"results": [{"text": self.data["note"]}]}
        brief = agent.brief_rep(bank_id)
        self.assertEqual(brief["bank_id"], bank_id)
        self.assertIn("pricing after 5pm", brief["brief"])

    def test_registry_survives_reopening_database(self):
        added = agent.add_lead(self.data)["lead"]
        with leads.connect() as database:
            self.assertEqual(database.execute("SELECT state FROM leads WHERE id=?", (added["id"],)).fetchone()["state"], "ready")
        self.assertEqual(leads.list_leads()[-1], added)

    def test_failed_retain_stays_hidden_and_retry_reuses_bank(self):
        self.client.retain.side_effect = RuntimeError("upstream failure")
        with self.assertRaises(RuntimeError):
            agent.add_lead(self.data)
        first_bank = self.client.create_bank.call_args.kwargs["bank_id"]
        self.assertEqual(len(leads.list_leads()), 4)
        self.client.retain.side_effect = None
        result = agent.add_lead(self.data)
        self.assertEqual(result["lead"]["id"], first_bank)
        self.assertEqual(len(leads.list_leads()), 5)

    def test_duplicate_is_rejected_without_another_bank(self):
        agent.add_lead(self.data)
        with self.assertRaises(leads.DuplicateLeadError):
            agent.add_lead(self.data)
        self.assertEqual(self.client.create_bank.call_count, 1)

    def test_invalid_lead_never_calls_hindsight(self):
        for field, value in (("name", ""), ("note", ""), ("company", 123), ("language", "invalid")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                agent.add_lead({**self.data, field: value})
        self.client.create_bank.assert_not_called()
        self.client.retain.assert_not_called()


if __name__ == "__main__":
    unittest.main()
