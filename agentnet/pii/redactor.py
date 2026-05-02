"""Apply PII patterns to a string."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .patterns import DEFAULT_PATTERNS, PIIPattern, PIIType


@dataclass(frozen=True)
class Finding:
    pii_type: PIIType
    start: int
    end: int
    placeholder: str


class Redactor:
    """Apply ordered PII regex patterns to text.

    The default constructor uses :data:`DEFAULT_PATTERNS`; pass
    ``patterns=`` to replace or ``extra=`` to append.
    """

    def __init__(
        self,
        *,
        patterns: Iterable[PIIPattern] | None = None,
        extra: Iterable[PIIPattern] = (),
    ) -> None:
        base = tuple(patterns) if patterns is not None else DEFAULT_PATTERNS
        self._patterns: tuple[PIIPattern, ...] = base + tuple(extra)

    @property
    def patterns(self) -> tuple[PIIPattern, ...]:
        return self._patterns

    def find(self, text: str) -> list[Finding]:
        """Return all non‑overlapping findings in *text*.

        Patterns run in declared order and earlier matches mask later
        ones, so e.g. a JWT isn't double‑tagged as an API key.
        """

        if not text:
            return []
        masked = [False] * len(text)
        findings: list[Finding] = []
        for pattern in self._patterns:
            for match in pattern.pattern.finditer(text):
                start, end = match.span()
                if any(masked[start:end]):
                    continue
                for i in range(start, end):
                    masked[i] = True
                findings.append(
                    Finding(
                        pii_type=pattern.pii_type,
                        start=start,
                        end=end,
                        placeholder=pattern.placeholder,
                    )
                )
        findings.sort(key=lambda f: f.start)
        return findings

    def redact(self, text: str) -> str:
        """Return *text* with every detected PII span replaced."""

        if not text:
            return text
        findings = self.find(text)
        if not findings:
            return text
        out: list[str] = []
        cursor = 0
        for finding in findings:
            out.append(text[cursor : finding.start])
            out.append(finding.placeholder)
            cursor = finding.end
        out.append(text[cursor:])
        return "".join(out)

    def has_pii(self, text: str) -> bool:
        return bool(self.find(text))

    def redact_payload(self, payload: Any) -> Any:
        """Walk a JSON‑like structure and redact every string leaf.

        Useful for memory upserts: ``record.payload = redactor.redact_payload(record.payload)``.
        """

        if isinstance(payload, str):
            return self.redact(payload)
        if isinstance(payload, dict):
            return {k: self.redact_payload(v) for k, v in payload.items()}
        if isinstance(payload, list):
            return [self.redact_payload(v) for v in payload]
        if isinstance(payload, tuple):
            return tuple(self.redact_payload(v) for v in payload)
        return payload


__all__ = ["Finding", "Redactor"]
