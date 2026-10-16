"""Validated, deterministic execution of a deliberately small workflow subset."""

from collections import defaultdict, deque
from math import isfinite
from typing import Any


class WorkflowError(ValueError):
    """Raised when a workflow is structurally or semantically invalid."""


_ALLOWED_TYPES = {"input", "multiply", "output"}
_MAX_NODES = 100
_MAX_EDGES = 200
_MAX_SAFE_INTEGER = 10**308


def _is_finite_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return abs(value) <= _MAX_SAFE_INTEGER
    return isinstance(value, float) and isfinite(value)


def validate_workflow(workflow: dict[str, Any]) -> list[str]:
    if not isinstance(workflow, dict):
        raise WorkflowError("workflow must be an object")
    nodes = workflow.get("nodes")
    edges = workflow.get("edges")
    if not isinstance(nodes, list) or not nodes or len(nodes) > _MAX_NODES:
        raise WorkflowError(f"nodes must contain between 1 and {_MAX_NODES} entries")
    if not isinstance(edges, list) or len(edges) > _MAX_EDGES:
        raise WorkflowError(f"edges must contain at most {_MAX_EDGES} entries")

    by_id: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise WorkflowError("each node must be an object")
        node_id, node_type = node.get("id"), node.get("type")
        if not isinstance(node_id, str) or not node_id or len(node_id) > 80:
            raise WorkflowError("node id must be a non-empty string of at most 80 characters")
        if node_id in by_id:
            raise WorkflowError(f"duplicate node id: {node_id}")
        if node_type not in _ALLOWED_TYPES:
            raise WorkflowError(f"unsupported node type: {node_type}")
        if not isinstance(node.get("config", {}), dict):
            raise WorkflowError(f"node {node_id} config must be an object")
        by_id[node_id] = node

    inputs = [n for n in nodes if n["type"] == "input"]
    outputs = [n for n in nodes if n["type"] == "output"]
    if len(inputs) != 1 or len(outputs) != 1:
        raise WorkflowError("workflow requires exactly one input and one output node")

    outgoing: dict[str, list[str]] = defaultdict(list)
    indegree = {node_id: 0 for node_id in by_id}
    seen_edges: set[tuple[str, str]] = set()
    for edge in edges:
        if not isinstance(edge, dict):
            raise WorkflowError("each edge must be an object")
        source, target = edge.get("source"), edge.get("target")
        if source not in by_id or target not in by_id:
            raise WorkflowError("edge references unknown node")
        pair = (source, target)
        if pair in seen_edges:
            raise WorkflowError("duplicate edge")
        seen_edges.add(pair)
        if by_id[source]["type"] == "output" or by_id[target]["type"] == "input":
            raise WorkflowError("invalid edge direction")
        outgoing[source].append(target)
        indegree[target] += 1

    ready = deque(node_id for node_id in by_id if indegree[node_id] == 0)
    order: list[str] = []
    while ready:
        node_id = ready.popleft()
        order.append(node_id)
        for target in outgoing[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    if len(order) != len(by_id):
        raise WorkflowError("workflow contains a cycle")

    if any(len(outgoing[node_id]) > 1 for node_id in by_id):
        raise WorkflowError("branching is not supported yet")
    if any(indegree[node_id] > 1 for node_id in by_id):
        raise WorkflowError("joining paths is not supported yet")
    if order[0] != inputs[0]["id"] or order[-1] != outputs[0]["id"]:
        raise WorkflowError("workflow must form a single input-to-output path")
    if len(edges) != len(nodes) - 1:
        raise WorkflowError("workflow must connect every node in a single path")
    return order


def run_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    order = validate_workflow(workflow)
    node_by_id = {node["id"]: node for node in workflow["nodes"]}
    results: dict[str, dict[str, Any]] = {}
    value: Any = None

    for node_id in order:
        node = node_by_id[node_id]
        config = node.get("config", {})
        try:
            if node["type"] == "input":
                value = config.get("value")
                if not isinstance(value, (int, float, str, bool, type(None))):
                    raise WorkflowError("input value must be a JSON scalar")
                if isinstance(value, (int, float)) and not _is_finite_number(value):
                    raise WorkflowError(
                        "input number must be finite and within the safe numeric range"
                    )
            elif node["type"] == "multiply":
                factor = config.get("factor")
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise WorkflowError("multiply input must be a number")
                if not _is_finite_number(factor):
                    raise WorkflowError(
                        "multiply factor must be a finite number within the safe numeric range"
                    )
                value = value * factor
                if isinstance(value, (int, float)) and not _is_finite_number(value):
                    raise WorkflowError(
                        "multiply result must be finite and within the safe numeric range"
                    )
            results[node_id] = {"status": "succeeded", "output": value}
        except (WorkflowError, OverflowError) as exc:
            results[node_id] = {"status": "failed", "error": str(exc)}
            return {"status": "failed", "output": None, "nodes": results}

    return {"status": "succeeded", "output": value, "nodes": results}
