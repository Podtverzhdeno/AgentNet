"""Scheduler — placeholder.

Real implementation lives in ``docs/modules/scheduler.md``. The placeholder
exposes an in-memory list of schedules so that other modules can depend on
the API surface without pulling in APScheduler / Celery yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Schedule:
    id: str
    cron: str
    session_template: dict[str, Any]
    tenant: str = "default"
    enabled: bool = True


@dataclass
class InMemoryScheduler:
    schedules: dict[str, Schedule] = field(default_factory=dict)

    def add(self, schedule: Schedule) -> Schedule:
        self.schedules[schedule.id] = schedule
        return schedule

    def remove(self, schedule_id: str) -> bool:
        return self.schedules.pop(schedule_id, None) is not None

    def list(self) -> list[Schedule]:
        return list(self.schedules.values())


__all__ = ["InMemoryScheduler", "Schedule"]
