"""Built‑in PII regex patterns.

Patterns are intentionally conservative: they aim to minimise false
positives in long, free‑form prompts while still catching the most
obvious leakers (emails, phone numbers, credit cards, SSNs, JWTs and
generic ``sk-…`` / ``ghp_…`` API keys).

Add custom patterns via :class:`PIIPattern` and pass them to
:class:`Redactor`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class PIIType(StrEnum):
    EMAIL = "email"
    PHONE = "phone"
    CREDIT_CARD = "credit_card"
    SSN = "ssn"
    JWT = "jwt"
    API_KEY = "api_key"
    OTHER = "other"


@dataclass(frozen=True)
class PIIPattern:
    """A named regex describing one class of PII."""

    pii_type: PIIType
    pattern: re.Pattern[str]
    placeholder: str

    @classmethod
    def make(cls, pii_type: PIIType, regex: str, placeholder: str) -> PIIPattern:
        return cls(
            pii_type=pii_type,
            pattern=re.compile(regex),
            placeholder=placeholder,
        )


# `re.X` flag would force us to escape every literal whitespace; keep
# patterns simple and inline.
DEFAULT_PATTERNS: tuple[PIIPattern, ...] = (
    # Order matters: more specific patterns run first so a JWT isn't
    # mistakenly tagged as a generic API key.
    PIIPattern.make(
        PIIType.EMAIL,
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "[REDACTED:EMAIL]",
    ),
    PIIPattern.make(
        PIIType.JWT,
        r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b",
        "[REDACTED:JWT]",
    ),
    PIIPattern.make(
        PIIType.API_KEY,
        # GitHub PATs (ghp_/ghs_/gho_/ghr_/ghu_), Anthropic (sk-ant-), OpenAI (sk-)
        r"\b(?:ghp_|ghs_|gho_|ghr_|ghu_|sk-(?:ant-)?)[A-Za-z0-9_-]{20,}\b",
        "[REDACTED:KEY]",
    ),
    PIIPattern.make(
        PIIType.CREDIT_CARD,
        r"\b(?:\d{4}[ -]?){3}\d{4}\b",
        "[REDACTED:CC]",
    ),
    PIIPattern.make(
        PIIType.SSN,
        r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b",
        "[REDACTED:SSN]",
    ),
    PIIPattern.make(
        PIIType.PHONE,
        # +<country> NXX-NXX-XXXX, (NXX) NXX-XXXX, NXX-NXX-XXXX, NXX.NXX.XXXX
        r"(?<!\d)(?:\+?\d{1,3}[ .-]?)?" r"(?:\(\d{3}\)|\d{3})[ .-]?\d{3}[ .-]?\d{4}\b",
        "[REDACTED:PHONE]",
    ),
)


__all__ = ["DEFAULT_PATTERNS", "PIIPattern", "PIIType"]
