import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import agent
import leads
from import_leads import parse_lead_csv


class PipelineTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        database = patch("leads.DATABASE", Path(temp.name) / "leads.sqlite3")
        database.start()
        self.addCleanup(database.stop)
        self.client = MagicMock()
        self.client.__enter__.return_value = self.client
        self.client.recall.return_value.model_dump.return_value = {"results": [{"text": "Alex prefers Spanish."}]}
        memory = patch("agent.memory", return_value=self.client)
        memory.start()
        self.addCleanup(memory.stop)
        self.csv = "name,company,language,note\nCSV One,One,English,First note\nCSV Two,Two,Spanish,Second note\nCSV Three,Three,English,Third note\n"

    def test_queue_retains_exact_draft_before_contacted_and_visible_transcript(self):
        draft = "Hola Alex, nos vemos a las 16:30. Sofia Alvarez | Helio"
        def before_save(**kwargs):
            self.assertEqual(leads.get_lead("Alex Rivera")["stage"], "Meeting")
            self.assertIn(draft, kwargs["content"])
            self.assertIn("Not sent or delivered", kwargs["content"])
        self.client.retain.side_effect = before_save
        result = agent.queue_outbound("Alex Rivera", "email", draft)
        self.assertEqual(result["stage"], "Contacted")
        self.assertEqual(result["transcripts"][-1]["text"], draft)
        self.assertEqual(result["transcripts"][-1]["kind"], "outbound")

    def test_failed_queue_leaves_stage_and_transcripts_unchanged(self):
        self.client.retain.side_effect = RuntimeError("private upstream details")
        with self.assertRaises(RuntimeError):
            agent.queue_outbound("Alex Rivera", "linkedin", "Hola Alex")
        self.assertEqual(leads.get_lead("Alex Rivera")["stage"], "Meeting")
        self.assertEqual(leads.transcripts_for("lead-alex-rivera"), [])

    @patch("agent.generate", return_value={"reply": "Claro, continuemos en español.", "language": "Spanish"})
    def test_saved_reply_moves_contacted_to_responded_with_both_turns(self, generate):
        agent.queue_outbound("Alex Rivera", "email", "Hola Alex")
        result = agent.continue_call("Alex Rivera", "¿Podemos continuar en español?")
        self.assertTrue(result["saved"])
        self.assertEqual(result["stage"], "Responded")
        text = result["transcripts"][-1]["text"]
        self.assertIn("¿Podemos continuar en español?", text)
        self.assertIn("Claro, continuemos en español.", text)
        self.assertEqual(len(result["transcripts"]), 2)

    @patch("agent.generate", return_value={"reply": "Hola", "language": "Spanish"})
    def test_failed_reply_does_not_advance_contacted(self, generate):
        agent.queue_outbound("Alex Rivera", "email", "Hola Alex")
        self.client.retain.side_effect = RuntimeError("failed")
        self.assertFalse(agent.continue_call("Alex Rivera", "Hola")["saved"])
        self.assertEqual(leads.get_lead("Alex Rivera")["stage"], "Contacted")
        self.assertEqual(len(leads.transcripts_for("lead-alex-rivera")), 1)

    def test_meeting_sets_stage_after_save_and_survives_reopening_registry(self):
        agent.queue_outbound("Alex Rivera", "email", "Hola")
        result = agent.confirm_meeting("Alex Rivera", "2026-11-10T16:30", "finance director")
        self.assertEqual(result["stage"], "Meeting")
        self.assertEqual(leads.get_lead("Alex Rivera")["stage"], "Meeting")
        self.assertEqual(leads.transcripts_for("lead-alex-rivera")[-1]["kind"], "meeting")

    def test_three_imports_have_unique_banks_new_stage_and_retained_notes(self):
        result = agent.import_csv(self.csv)
        self.assertEqual(len(result["created"]), 3)
        self.assertEqual(result["errors"], [])
        self.assertEqual({lead["stage"] for lead in result["created"]}, {"New"})
        self.assertEqual(len({call.kwargs["bank_id"] for call in self.client.retain.call_args_list}), 3)
        self.assertTrue(all("note" in call.kwargs["content"] for call in self.client.retain.call_args_list))
        self.assertEqual(result["counts"]["New"], 4)  # Luis plus the three imports.
        self.assertEqual(sum(result["counts"].values()), 7)

    def test_bad_later_csv_row_prevents_any_bank_creation(self):
        with self.assertRaises(ValueError):
            agent.import_csv(self.csv + "Bad,Row,English\n")
        self.client.create_bank.assert_not_called()

    def test_csv_supports_bom_header_quotes_and_no_header(self):
        rows = parse_lead_csv('\ufeffname,company,language,note\n"Name, One",Company,English,"Asked for pricing, after 5pm"\n')
        self.assertEqual(rows[0][1]["note"], "Asked for pricing, after 5pm")
        self.assertEqual(parse_lead_csv("Name,Company,English,Note")[0][1]["name"], "Name")

    def test_duplicate_import_skips_without_new_banks(self):
        agent.import_csv(self.csv)
        self.client.reset_mock()
        result = agent.import_csv(self.csv)
        self.assertEqual(len(result["errors"]), 3)
        self.assertEqual(result["created"], [])
        self.client.create_bank.assert_not_called()

    def test_key_notes_use_hindsight_structured_reflection(self):
        notes = {"objection": "Unknown", "language": "Spanish preference", "next_step": "Meet at 16:30", "next_time": "Include finance director"}
        self.client.reflect.return_value = SimpleNamespace(structured_output=notes)
        result = agent.key_notes("Alex Rivera")
        self.assertEqual(result["key_notes"], notes)
        self.assertEqual(self.client.reflect.call_args.kwargs["bank_id"], "lead-alex-rivera")

    def test_won_stage_is_explicit_rep_update_retained_to_memory(self):
        result = agent.set_stage("Alex Rivera", "Won")
        self.assertEqual(result["stage"], "Won")
        self.assertEqual(result["counts"]["Won"], 1)
        self.assertIn("Rep marked", self.client.retain.call_args.kwargs["content"])
