"""Extensible registry for specialist agents."""
from __future__ import annotations
from .base_agent import BaseAgent


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent, name: str | None = None) -> BaseAgent:
        key = (name or agent.name).strip().casefold()
        if not key:
            raise ValueError("Agent name is required.")
        self._agents[key] = agent
        return agent

    def unregister(self, name: str) -> bool:
        return self._agents.pop(name.casefold(), None) is not None

    def get(self, name: str) -> BaseAgent | None:
        return self._agents.get(name.casefold())

    def list_agents(self) -> list[str]:
        return sorted(self._agents)

    def metrics(self) -> dict[str, dict[str, float | int]]:
        return {name: agent.get_metrics() for name, agent in self._agents.items()}
