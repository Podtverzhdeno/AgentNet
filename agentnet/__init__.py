"""AgentNet — multi-agent AI platform skeleton.

This package contains the LangGraph-based orchestrator skeleton plus mock
implementations of every module described in `docs/modules/`. Real
implementations will replace the mocks one phase at a time (see
`docs/ROADMAP.md`).
"""

from .graph import build_graph, run_session
from .state import GraphState, SessionRequest, SessionResult

__all__ = ["GraphState", "SessionRequest", "SessionResult", "build_graph", "run_session"]
__version__ = "0.1.0"
