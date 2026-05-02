"""Tests for the skill registry mock."""

from __future__ import annotations

from agentnet.skills import Skill, SkillRegistry


def _skill(skill_id: str = "skill.demo.v1") -> Skill:
    return Skill(id=skill_id, name="Demo", version="1.0.0", tags=["demo", "test"])


def test_register_and_get() -> None:
    registry = SkillRegistry()
    registry.register(_skill())
    assert registry.get("skill.demo.v1") is not None


def test_search_by_tag() -> None:
    registry = SkillRegistry()
    registry.register(_skill())
    assert len(registry.search(tag="demo")) == 1
    assert len(registry.search(tag="missing")) == 0


def test_deprecate() -> None:
    registry = SkillRegistry()
    skill = registry.register(_skill())
    assert registry.deprecate(skill.id)
    assert skill.metrics.get("status") == "deprecated"
