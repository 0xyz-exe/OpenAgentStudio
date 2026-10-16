import tempfile
import unittest
from pathlib import Path

from app.store import WorkflowStore


class WorkflowStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = WorkflowStore(Path(self.temp_dir.name) / "studio.sqlite3")
        owner = self.store.bootstrap_owner("owner@example.test", "test-hash", "Local")
        self.workspace_id = owner["workspace_id"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_created_workflow_is_persisted_and_round_trips(self):
        definition = {
            "nodes": [{"id": "start", "type": "input", "config": {"value": 5}}],
            "edges": [],
        }
        saved = self.store.create_workflow("Test workflow", definition, self.workspace_id)
        self.assertEqual(saved["name"], "Test workflow")
        self.assertEqual(saved["definition"], definition)
        loaded = self.store.get_workflow(saved["id"], self.workspace_id)
        self.assertEqual(loaded, saved)

    def test_saved_run_is_available_after_store_reopens(self):
        saved = self.store.create_workflow(
            "Test workflow", {"nodes": [], "edges": []}, self.workspace_id
        )
        self.store.create_run(
            saved["id"],
            {"status": "succeeded", "output": 10, "nodes": {}},
            self.workspace_id,
        )
        reopened = WorkflowStore(Path(self.temp_dir.name) / "studio.sqlite3")
        runs = reopened.list_runs(saved["id"], self.workspace_id)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["result"]["output"], 10)

    def test_missing_workflow_returns_none(self):
        self.assertIsNone(self.store.get_workflow("not-found", self.workspace_id))


if __name__ == "__main__":
    unittest.main()
