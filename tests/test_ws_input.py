"""Malformed transport data must never become playback or profile state."""

import json

import pytest

from vmi.api.messages import MAX_COMMAND_CHARS, decode_command


@pytest.mark.parametrize("raw", ["{", "[]", "null", "7", '"play"', "true", "{}",
    '{"cmd":[]}', '{"cmd":null}', '{"cmd":"unknown"}',
    '{"cmd":"profile","profile":[]}', '{"cmd":"profile","profile":null}',
    '[' * 1100 + ']' * 1100])
def test_malformed_command_is_refused(raw):
    with pytest.raises(ValueError):
        decode_command(raw)


@pytest.mark.parametrize("command", [
    {"cmd": "play"}, {"cmd": "pause"}, {"cmd": "speed", "value": 8},
    {"cmd": "seek", "t": 12.5}, {"cmd": "new_match", "seed": 7},
    {"cmd": "catch_up", "since_t": None, "id": "c1"},
    {"cmd": "profile"}, {"cmd": "profile", "profile": {"depth": "deep"}},
    {"cmd": "ask", "q": "score?", "id": "q1"},
])
def test_valid_command_fields_are_preserved(command):
    assert decode_command(json.dumps(command)) == command


def test_command_size_boundary_is_checked_before_json_decoding():
    raw = '{"cmd":"pause"}'
    assert decode_command(raw.ljust(MAX_COMMAND_CHARS)) == {"cmd": "pause"}
    with pytest.raises(ValueError):
        decode_command(raw.ljust(MAX_COMMAND_CHARS + 1))
