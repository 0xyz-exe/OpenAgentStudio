"""Small deny-by-default registry of bounded built-in tools."""

from __future__ import annotations

import json
import math
from typing import Any


class ToolError(ValueError):
    """Raised when a tool is unknown or its arguments/result violate its contract."""


_MULTIPLY_ID = "math.multiply"

_MULTIPLY_SPEC = {
    "id": _MULTIPLY_ID,
    "title": "Multiply two finite numbers",
    "description": "Returns the product of two numeric values without side effects.",
    "permission": "Pure arithmetic; no network, filesystem, or process access.",
    "input_schema": {
        "type": "object",
        "properties": {
            "left": {"type": "number", "minimum": -1e308, "maximum": 1e308},
            "right": {"type": "number", "minimum": -1e308, "maximum": 1e308},
        },
        "required": ["left", "right"],
        "additionalProperties": False,
    },
    "timeout_seconds": 1,
    "max_output_bytes": 256,
}


def get_tool(tool_id: str) -> dict[str, Any] | None:
    """Return an independent public definition for a registered tool."""
    if tool_id != _MULTIPLY_ID:
        return None
    return json.loads(json.dumps(_MULTIPLY_SPEC))


def list_tools() -> list[dict[str, Any]]:
    return [get_tool(_MULTIPLY_ID) or {}]


def _finite_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value) and abs(value) <= 1e308
    except (OverflowError, TypeError):
        return False


def execute_tool(tool_id: str, arguments: dict[str, Any]) -> dict[str, int | float]:
    """Validate then invoke a registered deterministic tool."""
    spec = get_tool(tool_id)
    if spec is None:
        raise ToolError("tool is not registered")
    if not isinstance(arguments, dict) or set(arguments) != {"left", "right"}:
        raise ToolError("arguments must contain only left and right")
    if not all(_finite_number(value) for value in arguments.values()):
        raise ToolError("arguments must be finite numbers within the supported range")
    try:
        result = arguments["left"] * arguments["right"]
    except OverflowError as exc:
        raise ToolError("tool result exceeds the supported numeric range") from exc
    if not _finite_number(result):
        raise ToolError("tool result exceeds the supported numeric range")
    output = {"value": result}
    encoded = json.dumps(output, allow_nan=False).encode("utf-8")
    if len(encoded) > spec["max_output_bytes"]:
        raise ToolError("tool output exceeds the configured size limit")
    return output
