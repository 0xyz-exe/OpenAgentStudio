import pytest

from app.tools import ToolError, execute_tool, get_tool, list_tools


def test_builtin_catalog_is_explicit_and_bounded():
    catalog = list_tools()
    assert [tool["id"] for tool in catalog] == ["math.multiply"]
    tool = get_tool("math.multiply")
    assert tool["input_schema"]["additionalProperties"] is False
    assert tool["max_output_bytes"] <= 4096
    assert tool["timeout_seconds"] <= 1


def test_multiply_tool_returns_a_finite_structured_result():
    assert execute_tool("math.multiply", {"left": 7, "right": 3}) == {"value": 21}


@pytest.mark.parametrize(
    "arguments",
    [
        {"left": True, "right": 3},
        {"left": float("inf"), "right": 3},
        {"left": 1, "right": 2, "run_shell": True},
        {"left": "7", "right": 3},
        {"left": 1e308, "right": 1e308},
    ],
)
def test_multiply_tool_rejects_invalid_or_unsafe_inputs(arguments):
    with pytest.raises(ToolError):
        execute_tool("math.multiply", arguments)


def test_unknown_tool_is_rejected():
    with pytest.raises(ToolError, match="not registered"):
        execute_tool("shell", {"command": "whoami"})
