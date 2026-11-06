import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import agent


class SalesAgentTests(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.client.__enter__.return_value = self.client
        self.client.recall.return_value.model_dump.return_value = {
            "results": [{"text": "Alex prefers Spanish."}]
        }
        self.memory_patch = patch("agent.memory", return_value=self.client)
        self.memory_patch.start()
        self.addCleanup(self.memory_patch.stop)

    def test_brief_uses_recall_and_reflect_in_existing_bank(self):
        self.client.reflect.return_value = SimpleNamespace(text="Alex prefers Spanish.")
        result = agent.brief_rep("Alex")
        self.assertIn("Spanish", result["brief"])
        self.assertEqual(self.client.recall.call_args.kwargs["bank_id"], "lead-alex-rivera")
        self.assertEqual(self.client.reflect.call_args.kwargs["bank_id"], "lead-alex-rivera")
        self.assertIn("Spanish", self.client.reflect.call_args.kwargs["context"])

    @patch("agent.generate", return_value={"reply": "Hola, Alex.", "language": "Spanish"})
    def test_reply_retains_both_turns_after_generation(self, generate):
        def check_save(**kwargs):
            generate.assert_called_once()
            self.assertIn("¿Podemos hablar?", kwargs["content"])
            self.assertIn("Hola, Alex.", kwargs["content"])
        self.client.retain.side_effect = check_save
        result = agent.continue_call("Alex", "¿Podemos hablar?")
        self.assertTrue(result["saved"])
        self.assertEqual(generate.call_args.args[1]["language"], "auto")
        self.assertIn("Spanish", str(generate.call_args.args[1]["facts"]))

    @patch("agent.generate", return_value={"reply": "Hola", "language": "Spanish"})
    def test_failed_save_does_not_claim_success_or_expose_exception(self, generate):
        self.client.retain.side_effect = RuntimeError("secret upstream detail")
        result = agent.continue_call("Alex", "Hola")
        self.assertFalse(result["saved"])
        self.assertEqual(result["reply"], "Hola")
        self.assertNotIn("secret", str(result))

    @patch("agent.generate", return_value={"email": "Hola Alex", "linkedin": "Hola", "x": "Hola"})
    def test_outreach_returns_three_drafts_and_raw_facts_without_retaining(self, generate):
        result = agent.draft_outbound("Alex")
        self.assertEqual(set(result["drafts"]), {"email", "linkedin", "x"})
        self.assertEqual(result["facts"]["results"][0]["text"], "Alex prefers Spanish.")
        self.client.retain.assert_not_called()

    @patch("agent.generate", return_value={"email": "Hola", "linkedin": "Hola", "x": "a" * 281})
    def test_rejects_overlong_x_draft(self, generate):
        with self.assertRaises(RuntimeError):
            agent.draft_outbound("Alex")

    def test_comparison_reads_separate_empty_bank_and_never_retains(self):
        self.client.reflect.return_value = SimpleNamespace(text="## Brief\n\n**Language:** Unknown")
        self.client.recall.return_value.model_dump.side_effect = [
            {"results": [{"text": "Alex prefers Spanish"}]}, {"results": []}
        ]
        result = agent.compare_briefs()
        self.assertEqual(result["generic"]["facts"]["results"], [])
        self.assertEqual([c.kwargs["bank_id"] for c in self.client.recall.call_args_list],
                         [agent.BANK_ID, agent.EMPTY_BANK_ID])
        self.client.retain.assert_not_called()

    def test_markdown_formats_and_strips_active_html(self):
        html = agent.formatted_brief('## Brief\n\n**Alex** prefers Spanish.\n\n<img src=x onerror="alert(1)">')
        self.assertIn("<h2>Brief</h2>", html)
        self.assertIn("<strong>Alex</strong>", html)
        self.assertNotIn("<img", html)
        self.assertNotIn("onerror", html)
        compact = agent.formatted_brief("**Profile**\n* Spanish\n* Operations lead")
        self.assertIn("<ul>", compact)
        self.assertNotIn("* Spanish", compact)

    def test_meeting_confirmation_is_retained_and_recalled(self):
        result = agent.confirm_meeting("Alex Rivera", "2026-11-10T16:30")
        saved = self.client.retain.call_args.kwargs
        self.assertEqual(saved["bank_id"], agent.BANK_ID)
        self.assertIn("confirmed", saved["content"])
        self.assertIn("10 November 2026 at 16:30", result["new_fact"])
        self.assertIn("finance director", result["new_fact"])
        self.client.recall.assert_called_once()

    @patch("agent.generate", return_value={"reply": "Confirmado.", "language": "Spanish",
           "confirmed_meeting": {"at": "2026-11-10T16:30", "attendees": "the finance director"}})
    def test_confirmed_time_in_conversation_is_saved_as_a_fact(self, generate):
        result = agent.continue_call("Alex Rivera", "Confirmo el 10 de noviembre a las 16:30.")
        self.assertIn("16:30", result["new_fact"])
        self.assertIn("Confirmed fact:", self.client.retain.call_args.kwargs["content"])

    def test_invalid_confirmation_does_not_write_memory(self):
        with self.assertRaises(ValueError):
            agent.confirm_meeting("Alex Rivera", "not a date")
        self.client.retain.assert_not_called()


if __name__ == "__main__":
    unittest.main()
