"""Skill registry — mock implementation.

A real implementation would persist to Postgres + git (see
``docs/modules/skills.md``). The mock keeps everything in memory so the
shape of the API can be exercised in tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Skill:
    id: str
    name: str
    version: str
    tags: list[str] = field(default_factory=list)
    plan_template: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> Skill:
        self._skills[skill.id] = skill
        return skill

    def get(self, skill_id: str) -> Skill | None:
        return self._skills.get(skill_id)

    def search(self, *, tag: str | None = None, query: str | None = None) -> list[Skill]:
        results = list(self._skills.values())
        if tag:
            results = [s for s in results if tag in s.tags]
        if query:
            q = query.lower()
            results = [s for s in results if q in s.name.lower() or q in s.id.lower()]
        return results

    def deprecate(self, skill_id: str) -> bool:
        skill = self._skills.get(skill_id)
        if not skill:
            return False
        skill.metrics["status"] = "deprecated"
        return True

    def __len__(self) -> int:
        return len(self._skills)


__all__ = ["Skill", "SkillRegistry"]
