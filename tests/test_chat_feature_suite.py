import unittest
from unittest.mock import patch

from service.chat import commands as cmd


class ChatFeatureSuite(unittest.TestCase):
    @patch("service.chat.commands.MetaLoader.loads")
    def test_find_suitable_workflow_reuse(self, mock_loads):
        def _loads(kind):
            if kind == "graphs":
                return [
                    {"id": "wf_flair_llm_ner", "name": "Flair and LLM NER compare", "nodes": ["START", "ner_flair_sent", "ner_llm", "END"]},
                    {"id": "wf_other", "name": "Other workflow", "nodes": ["START", "text_sentence_split", "END"]},
                ]
            if kind == "agents":
                return [
                    {"id": "ner_flair_sent", "name": "Flair NER", "type": "PGM"},
                    {"id": "ner_llm", "name": "LLM NER", "type": "LLM"},
                ]
            return []
        mock_loads.side_effect = _loads
        found = cmd.find_suitable_workflow("compare flair llm chemical disease ner workflow")
        self.assertIsNotNone(found)
        self.assertEqual("wf_flair_llm_ner", found.get("graph_id"))

    @patch("service.chat.commands.MetaLoader.load")
    @patch("autogen.LLMClient")
    def test_preflight_llm_agents_ok(self, mock_client_cls, mock_meta_load):
        def _load(kind, cid):
            if kind == "graphs" and cid == "wf1":
                return {"nodes": ["START", "a_llm", "END"]}
            if kind == "agents" and cid == "a_llm":
                return {"id": "a_llm", "type": "LLM", "model": "deepseek"}
            return None

        mock_meta_load.side_effect = _load
        mock_client = mock_client_cls.return_value
        mock_client.chat.return_value = "OK"
        out = cmd._preflight_llm_agents_for_workflow("wf1", {"deepseek": {"model": "x"}})
        self.assertTrue(out.get("ok"))

    @patch("service.chat.commands.MetaLoader.load")
    @patch("autogen.LLMClient")
    def test_preflight_llm_agents_quota_error(self, mock_client_cls, mock_meta_load):
        def _load(kind, cid):
            if kind == "graphs" and cid == "wf1":
                return {"nodes": ["START", "a_llm", "END"]}
            if kind == "agents" and cid == "a_llm":
                return {"id": "a_llm", "type": "LLM", "model": "deepseek"}
            return None

        mock_meta_load.side_effect = _load
        mock_client = mock_client_cls.return_value
        mock_client.chat.side_effect = RuntimeError("429 insufficient balance")
        out = cmd._preflight_llm_agents_for_workflow("wf1", {"deepseek": {"model": "x"}})
        self.assertFalse(out.get("ok"))
        self.assertTrue(out.get("failures"))

    def test_pin_and_dryrun(self):
        session = {"pins": {}}
        out1 = cmd.execute_slash_command("/pin graph wf_demo", session=session)
        self.assertIn("Pinned Context", out1 or "")
        self.assertEqual(session["pins"].get("graph"), "wf_demo")
        out2 = cmd.execute_slash_command("/pin dataset demo.csv", session=session)
        self.assertIn("Pinned Context", out2 or "")
        out3 = cmd.execute_slash_command("/dryrun /create experiment", session=session)
        self.assertIn("Execution Preview", out3 or "")
        self.assertIn("resolved_runner", out3 or "")
        self.assertIn("resolved_dataset", out3 or "")

    @patch("service.chat.commands.MetaLoader.loads")
    def test_list_meta(self, mock_loads):
        mock_loads.return_value = [{"id": "a1", "name": "Agent One", "type": "LLM"}]
        out = cmd.execute_slash_command("/list agents", session={"pins": {}})
        self.assertIn("Agents", out or "")
        self.assertIn("a1", out or "")

    @patch("service.chat.commands.MetaLoader.load")
    def test_show_meta(self, mock_load):
        mock_load.return_value = {"id": "wf1", "name": "Workflow One"}
        out = cmd.execute_slash_command("/show workflow wf1", session={"pins": {}})
        self.assertIn("Workflow", out or "")
        self.assertIn("wf1", out or "")

    @patch("service.chat.commands.MetaLoader.exists")
    @patch("service.chat.commands.MetaLoader.delete")
    def test_delete_meta(self, mock_delete, mock_exists):
        mock_exists.return_value = True
        mock_delete.return_value = True
        out = cmd.execute_slash_command("/delete experiment e1", session={"pins": {}})
        self.assertIn("Deleted", out or "")

    @patch("service.chat.commands.MetaLoader.load")
    @patch("service.chat.commands.MetaLoader.exists")
    @patch("service.chat.commands.MetaLoader.dump")
    def test_copy_workflow(self, mock_dump, mock_exists, mock_load):
        mock_load.return_value = {"name": "base wf"}
        mock_exists.return_value = False
        out = cmd.execute_slash_command("/copy workflow wf_a wf_b", session={"pins": {}})
        self.assertIn("Workflow Copied", out or "")
        mock_dump.assert_called_once()

    @patch("service.chat.commands.MetaLoader.dump")
    @patch("service.chat.commands.TestLoader.load_by_id_file")
    def test_create_experiment_with_explicit_args(self, mock_load_rows, mock_dump):
        mock_load_rows.return_value = (["text"], [{"text": "a"}])
        out = cmd.execute_slash_command("/create experiment wf_demo demo.csv", session={"pins": {}})
        self.assertIn("Experiment Created", out or "")
        mock_dump.assert_called_once()

    @patch("service.chat.commands.MetaLoader.dump")
    @patch("service.chat.commands.TestLoader.load_by_id_file")
    def test_create_experiment_with_pins(self, mock_load_rows, mock_dump):
        mock_load_rows.return_value = (["text"], [{"text": "a"}])
        session = {"pins": {"graph": "wf_pin", "runner_id": "wf_pin", "dataset": "pin.csv"}}
        out = cmd.execute_slash_command("/create experiment", session=session)
        self.assertIn("Experiment Created", out or "")
        mock_dump.assert_called_once()

    @patch("service.chat.commands.start_optimize_loop")
    def test_optimize(self, mock_opt):
        mock_opt.return_value = "Optimize loop finished"
        out = cmd.execute_slash_command("/optimize exp1 1", session={"pins": {}})
        self.assertEqual("Optimize loop finished", out)

    @patch("service.chat.commands.run_orchestration")
    def test_orchestrate(self, mock_orch):
        mock_orch.return_value = "Agentic Orchestration Result"
        out = cmd.execute_slash_command(
            "/orchestrate build flair vs llm ner workflow and run",
            session={"pins": {}},
            llm_id="deepseek",
        )
        self.assertEqual("Agentic Orchestration Result", out)
        mock_orch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
