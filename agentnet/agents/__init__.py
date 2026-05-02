"""Worker agents.

Every agent is a callable ``(state) -> partial_state`` that knows how to
update one slice of the state (for example ``state.research``). The mock
implementations return deterministic synthetic outputs so the rest of the
graph can be exercised without an LLM. They will be replaced by real LLM
agents in later phases.

See ``docs/modules/agents.md`` for the contract and per-agent files for
their specifications.
"""

from .analytics import analytics_node, make_analytics_node
from .architect import architect_node, make_architect_node
from .research import make_research_node, research_node
from .security import make_security_node, security_node

__all__ = [
    "analytics_node",
    "architect_node",
    "make_analytics_node",
    "make_architect_node",
    "make_research_node",
    "make_security_node",
    "research_node",
    "security_node",
]
