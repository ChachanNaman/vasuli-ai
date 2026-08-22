"""Regression test for the Gemini MapComposite -> dict conversion bug: a live
run surfaced 'action_params must be an object' after a Groq -> Gemini
fallback, because `dict(function_call.args)` only converts the top level —
nested object fields stayed as MapComposite and failed the diagnosis
agent's `isinstance(x, dict)` contract check.
"""

from __future__ import annotations

from app.agents.llm_client import _proto_to_python


class FakeMapComposite:
    """Stand-in for proto.marshal.collections.maps.MapComposite — supports
    .items() but is not a dict subclass, same as the real thing."""

    def __init__(self, data: dict):
        self._data = data

    def items(self):
        return self._data.items()


class FakeRepeatedComposite:
    """Stand-in for proto.marshal.collections.repeated.RepeatedComposite —
    iterable but not a list subclass."""

    def __init__(self, data: list):
        self._data = data

    def __iter__(self):
        return iter(self._data)


def test_proto_to_python_converts_flat_map():
    result = _proto_to_python(FakeMapComposite({"a": 1, "b": "two"}))
    assert result == {"a": 1, "b": "two"}
    assert isinstance(result, dict)


def test_proto_to_python_converts_nested_map():
    nested = FakeMapComposite({"retry_window_minutes": 45})
    result = _proto_to_python(FakeMapComposite({"action_params": nested}))
    assert result == {"action_params": {"retry_window_minutes": 45}}
    assert isinstance(result["action_params"], dict)


def test_proto_to_python_converts_repeated_composite():
    result = _proto_to_python(FakeRepeatedComposite([1, 2, 3]))
    assert result == [1, 2, 3]
    assert isinstance(result, list)


def test_proto_to_python_passes_through_primitives():
    assert _proto_to_python("hello") == "hello"
    assert _proto_to_python(42) == 42
    assert _proto_to_python(None) is None
    assert _proto_to_python(0.95) == 0.95


def test_proto_to_python_handles_empty_nested_object():
    result = _proto_to_python(FakeMapComposite({"action_params": FakeMapComposite({})}))
    assert result == {"action_params": {}}
    assert isinstance(result["action_params"], dict)
