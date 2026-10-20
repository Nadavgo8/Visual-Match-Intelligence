"""MCP server over the engine's read-only match tools.

Any MCP client (GitHub Copilot, a Foundry agent, Claude, an IDE) can query a
generated match the same way our own agents do:

    python -m vmi.mcp_server                 # stdio
    python -m vmi.mcp_server --http 8765     # streamable HTTP at /mcp

Each tool takes the match `seed` and the `minute` to look from, so answers only
use what had been delivered by that point of the match.
"""

from __future__ import annotations

import argparse
from functools import lru_cache

from mcp.server.fastmcp import FastMCP

from .agents.tools import MatchTools
from .engine.replay import Replay
from .generator.match import generate_match

mcp = FastMCP("visual-match-intelligence",
              instructions="Read-only tools over a synthetic football match: score, events, stats, momentum, "
                           "players, crowd loudness and the Laws of the Game. Every result lists evidence IDs.")


@lru_cache(maxsize=32)
def _tools(seed: int, minute: int) -> MatchTools:
    match = generate_match(seed)
    r = Replay(match)
    # match minute -> timeline seconds: find the first event at or after that minute
    target = match.duration
    for e in match.events:
        clock = e["clock"].strip("'")
        m = int(clock.split("+")[0]) if "+" in clock else int(clock.split(":")[0])
        if m >= minute:
            target = e["t"]
            break
    r.advance(target)
    return MatchTools(r.model)


@mcp.tool()
def get_score_and_clock(seed: int = 12, minute: int = 90) -> dict:
    """Score, clock and period of match `seed` at `minute`."""
    return _tools(seed, minute).get_score_and_clock()


@mcp.tool()
def get_events(seed: int = 12, minute: int = 90, from_minute: int = 0, to_minute: int = 120, types: str = "") -> dict:
    """Notable events between two minutes (goals, cards, VAR, subs, big chances). `types` is an optional comma list."""
    return _tools(seed, minute).get_events(from_minute, to_minute, types)


@mcp.tool()
def get_team_stats(seed: int = 12, minute: int = 90, last_minutes: int = 0) -> dict:
    """Shots, xG (our location-based estimate), possession, passes, corners, fouls and cards."""
    return _tools(seed, minute).get_team_stats(last_minutes)


@mcp.tool()
def get_momentum(seed: int = 12, minute: int = 90) -> dict:
    """Momentum over the last 7 minutes: possession 40%, key passes 30%, shots 30%."""
    return _tools(seed, minute).get_momentum()


@mcp.tool()
def get_attack_pattern(team: str, seed: int = 12, minute: int = 90, last_minutes: int = 15) -> dict:
    """Which flank a team's passes into the box came from recently."""
    return _tools(seed, minute).get_attack_pattern(team, last_minutes)


@mcp.tool()
def get_player(name_or_number: str, seed: int = 12, minute: int = 90) -> dict:
    """A player's position and involvement so far."""
    return _tools(seed, minute).get_player(name_or_number)


@mcp.tool()
def get_crowd_peaks(seed: int = 12, minute: int = 90) -> dict:
    """When the crowd was loudest recently and what was logged just before. Loudness only, never why."""
    return _tools(seed, minute).get_crowd_peaks()


@mcp.tool()
def get_rule(topic: str) -> dict:
    """Plain-language Laws of the Game for a topic (offside, penalty, VAR, cards, advantage...)."""
    return _tools(12, 0).get_rule(topic)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--http", type=int, help="serve streamable HTTP on this port instead of stdio")
    args = ap.parse_args()
    if args.http:
        mcp.settings.port = args.http
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
