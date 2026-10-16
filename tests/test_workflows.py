import unittest

from app.workflows import WorkflowError, run_workflow, validate_workflow


class WorkflowValidationTests(unittest.TestCase):
    def test_accepts_valid_linear_workflow(self):
        workflow = {
            "nodes": [
                {"id": "start", "type": "input", "config": {"value": 3}},
                {"id": "double", "type": "multiply", "config": {"factor": 2}},
                {"id": "done", "type": "output", "config": {}},
            ],
            "edges": [
                {"source": "start", "target": "double"},
                {"source": "double", "target": "done"},
            ],
        }
        self.assertEqual(validate_workflow(workflow), ["start", "double", "done"])

    def test_rejects_cycles(self):
        workflow = {
            "nodes": [
                {"id": "start", "type": "input", "config": {"value": 1}},
                {"id": "a", "type": "multiply", "config": {"factor": 2}},
                {"id": "b", "type": "multiply", "config": {"factor": 2}},
                {"id": "done", "type": "output", "config": {}},
            ],
            "edges": [
                {"source": "start", "target": "a"},
                {"source": "a", "target": "b"},
                {"source": "b", "target": "a"},
                {"source": "b", "target": "done"},
            ],
        }
        with self.assertRaisesRegex(WorkflowError, "cycle"):
            validate_workflow(workflow)

    def test_rejects_unknown_node_types(self):
        workflow = {"nodes": [{"id": "x", "type": "shell", "config": {}}], "edges": []}
        with self.assertRaisesRegex(WorkflowError, "unsupported node type"):
            validate_workflow(workflow)


class WorkflowExecutionTests(unittest.TestCase):
    def test_rejects_non_finite_input_values(self):
        workflow = {
            "nodes": [
                {"id": "start", "type": "input", "config": {"value": float("inf")}},
                {"id": "done", "type": "output", "config": {}},
            ],
            "edges": [{"source": "start", "target": "done"}],
        }
        result = run_workflow(workflow)
        self.assertEqual(result["status"], "failed")
        self.assertIn("finite", result["nodes"]["start"]["error"])

    def test_rejects_integer_values_outside_safe_numeric_range(self):
        workflow = {
            "nodes": [
                {"id": "start", "type": "input", "config": {"value": 10**400}},
                {"id": "done", "type": "output", "config": {}},
            ],
            "edges": [{"source": "start", "target": "done"}],
        }
        result = run_workflow(workflow)
        self.assertEqual(result["status"], "failed")
        self.assertIn("finite", result["nodes"]["start"]["error"])

    def test_executes_deterministic_workflow_and_returns_node_results(self):
        workflow = {
            "nodes": [
                {"id": "start", "type": "input", "config": {"value": 3}},
                {"id": "double", "type": "multiply", "config": {"factor": 2}},
                {"id": "done", "type": "output", "config": {}},
            ],
            "edges": [
                {"source": "start", "target": "double"},
                {"source": "double", "target": "done"},
            ],
        }
        result = run_workflow(workflow)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["output"], 6)
        self.assertEqual(result["nodes"]["double"]["output"], 6)


if __name__ == "__main__":
    unittest.main()
