"""PII guard and output filter (Phase 3.B).

Two pieces:

* :class:`Redactor` — pure regex‑based scrubber (email, phone, credit
  card, SSN, JWT, generic API key shapes). Pluggable via custom
  :class:`PIIPattern`\\ s.
* :class:`ScrubbedLLMClient` — :class:`agentnet.llm.LLMClient` decorator
  that sanitises prompts before they hit a real provider and,
  optionally, responses on the way back.

The redactor runs before *any* network call, so secrets/PII never leave
the process. For long‑term memory: pass user text through ``scrub`` /
``redact`` before ``store.upsert``.
"""

from __future__ import annotations

from .llm import ScrubbedLLMClient
from .patterns import DEFAULT_PATTERNS, PIIPattern, PIIType
from .redactor import Finding, Redactor

__all__ = [
    "DEFAULT_PATTERNS",
    "Finding",
    "PIIPattern",
    "PIIType",
    "Redactor",
    "ScrubbedLLMClient",
]
