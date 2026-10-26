"""Validate the command envelope before any room state or host action is touched."""

import json

MAX_COMMAND_CHARS = 4096
COMMANDS = frozenset({"play", "pause", "speed", "seek", "new_match", "catch_up", "profile", "ask"})


def decode_command(raw: str) -> dict:
    if len(raw) > MAX_COMMAND_CHARS:
        raise ValueError("command too large")
    try:
        message = json.loads(raw)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid JSON command") from exc
    if not isinstance(message, dict):
        raise ValueError("command must be an object")
    command = message.get("cmd")
    if not isinstance(command, str) or command not in COMMANDS:
        raise ValueError("unknown command")
    if command == "profile" and not isinstance(message.get("profile", {}), dict):
        raise ValueError("profile must be an object")
    return message
