"""Sandbox runtime — placeholder.

The production sandbox uses Docker / gVisor / Kata / Firecracker (see
``docs/modules/sandbox.md``). For Phase 1 we expose a :class:`SandboxProfile`
descriptor and a :class:`NullSandbox` that simply runs a callable in-process.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SandboxProfile:
    name: str
    cpu: str = "1000m"
    memory: str = "2Gi"
    network_egress_allowlist: tuple[str, ...] = ()
    read_only_root: bool = True


LITE = SandboxProfile(name="lite")
STANDARD = SandboxProfile(name="standard")
HARDENED = SandboxProfile(name="hardened")


class NullSandbox:
    """No-op sandbox. Runs the callable directly. For tests / local dev."""

    def __init__(self, profile: SandboxProfile = STANDARD) -> None:
        self.profile = profile

    def run(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
        return fn(*args, **kwargs)


__all__ = ["HARDENED", "LITE", "STANDARD", "NullSandbox", "SandboxProfile"]
