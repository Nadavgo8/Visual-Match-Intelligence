"""Foundry client factory. Returns None when Foundry is not configured, so the app
runs fully offline on the deterministic agents."""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)


def foundry_client():
    """A Microsoft Agent Framework chat client for a Foundry project, or None.

    Configure with FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL. Auth is keyless
    (Entra ID): managed identity in Azure, `az login` locally.
    """
    endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
    model = os.getenv("FOUNDRY_MODEL")
    if not endpoint or not model or os.getenv("VMI_OFFLINE") == "1":
        return None, None
    try:
        from agent_framework.foundry import FoundryChatClient
        from azure.identity.aio import DefaultAzureCredential

        client = FoundryChatClient(project_endpoint=endpoint, model=model, credential=DefaultAzureCredential())
        return client, model
    except Exception as e:  # missing package or bad config: stay offline rather than crash
        log.warning("Foundry unavailable, using local agents: %s", e)
        return None, None


def explainer_agent(client, model: str):
    from pathlib import Path

    from agent_framework import Agent

    prompt = (Path(__file__).resolve().parents[2] / "prompts" / "explainer.md").read_text()
    agent = Agent(client, prompt, name="explainer")
    agent.model_name = model
    return agent
