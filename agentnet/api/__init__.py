"""HTTP / SSE API for AgentNet (Phase 2.D).

Mirrors the contracts in ``docs/API_CONTRACTS.md``. The API is a thin
FastAPI surface around the existing :func:`agentnet.run_session`
coroutine plus a per-session in-memory event bus that broadcasts node
updates to SSE subscribers.

Endpoints (MVP subset):

* ``POST   /api/session/start``           — start a session, returns
  ``session_id`` immediately. Execution runs in the background.
* ``GET    /api/session/{id}/state``      — latest persisted state.
* ``GET    /api/session/{id}/stream``     — SSE stream of node updates.
* ``POST   /api/session/{id}/approve``    — record a HITL decision
  (full ``interrupt``-based pause/resume lands in a later phase; for
  now we persist the decision into the bus and acknowledge).
* ``GET    /api/sessions``                — list known thread ids.
* ``GET    /api/healthz``                 — liveness probe.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Literal

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from langgraph.checkpoint.base import BaseCheckpointSaver
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from .. import __version__
from ..audit import AuditRecorder, NewEvent
from ..auth import StaticTenantResolver, TenantResolver
from ..graph import build_graph, get_session_state
from ..llm import LLMClient, make_llm_client
from ..observability import get_logger
from ..persistence import async_checkpointer, list_thread_ids
from ..state import DEFAULT_TENANT, GraphState, SessionRequest

log = get_logger(__name__)


# --------------------------------------------------------------------------- #
# Schemas                                                                     #
# --------------------------------------------------------------------------- #


class StartSessionRequest(BaseModel):
    task: str = Field(..., description="Idea / задача от пользователя")
    mode: Literal["auto", "confirm-each-step", "manual"] = "auto"
    max_iterations: int = Field(3, ge=1, le=10)
    score_threshold: float = Field(0.8, ge=0.0, le=1.0)
    thread_id: str | None = Field(
        default=None,
        description="Optionally reuse an existing thread id; otherwise a new one is generated.",
    )
    tenant_id: str | None = Field(
        default=None,
        description=(
            "Override the tenant resolved from the request headers. Server enforces "
            "that the override matches the authenticated tenant; otherwise 403."
        ),
    )


class StartSessionResponse(BaseModel):
    session_id: str
    next: str = "planner"
    status: Literal["started", "queued"] = "started"


class ApprovalRequest(BaseModel):
    step_id: int
    decision: Literal["approve", "reject"]
    comment: str | None = None


class ApprovalResponse(BaseModel):
    session_id: str
    step_id: int
    decision: Literal["approve", "reject"]
    status: Literal["recorded"] = "recorded"


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str = __version__


# --------------------------------------------------------------------------- #
# Event bus                                                                   #
# --------------------------------------------------------------------------- #


@dataclass
class _SessionChannel:
    buffer: list[dict[str, Any]] = field(default_factory=list)
    subscribers: set[asyncio.Queue[dict[str, Any]]] = field(default_factory=set)
    done: asyncio.Event = field(default_factory=asyncio.Event)


class SessionEventBus:
    """In-memory pub/sub keyed by ``session_id``.

    *Each* SSE subscriber gets its own queue. New subscribers also get a
    replay of buffered events so a client that connects mid-flight
    doesn't miss the early node updates. ``mark_done`` unblocks idle
    subscribers so the SSE response can close cleanly.
    """

    def __init__(self) -> None:
        self._channels: dict[str, _SessionChannel] = defaultdict(_SessionChannel)
        self._lock = asyncio.Lock()

    async def publish(self, session_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            ch = self._channels[session_id]
            ch.buffer.append(event)
            for q in ch.subscribers:
                q.put_nowait(event)

    async def mark_done(self, session_id: str) -> None:
        async with self._lock:
            ch = self._channels[session_id]
        ch.done.set()
        async with self._lock:
            for q in ch.subscribers:
                q.put_nowait({"event": "session.end"})

    async def subscribe(
        self, session_id: str, *, replay: bool = True
    ) -> AsyncIterator[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        async with self._lock:
            ch = self._channels[session_id]
            if replay:
                for ev in ch.buffer:
                    q.put_nowait(ev)
            ch.subscribers.add(q)
        try:
            while True:
                if ch.done.is_set() and q.empty():
                    return
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15.0)
                except TimeoutError:
                    if ch.done.is_set():
                        return
                    yield {"event": "ping"}
                    continue
                yield ev
                if ev.get("event") == "session.end":
                    return
        finally:
            async with self._lock:
                ch.subscribers.discard(q)


# --------------------------------------------------------------------------- #
# Background runner                                                           #
# --------------------------------------------------------------------------- #


async def _run_session_streaming(
    request: StartSessionRequest,
    thread_id: str,
    tenant_id: str,
    checkpointer: BaseCheckpointSaver[Any],
    bus: SessionEventBus,
    llm: LLMClient | None = None,
) -> None:
    """Run a session via ``graph.astream`` and publish per-node events."""

    graph = build_graph(checkpointer=checkpointer, llm=llm)
    initial: GraphState = {
        "idea": request.task,
        "iteration": 1,
        "max_iterations": request.max_iterations,
        "score_threshold": request.score_threshold,
        "mode": request.mode,
        "session_id": thread_id,
        "tenant_id": tenant_id,
    }
    config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}

    await bus.publish(
        thread_id,
        {
            "event": "session.start",
            "thread_id": thread_id,
            "tenant_id": tenant_id,
            "mode": request.mode,
            "task": request.task,
        },
    )
    try:
        async for chunk in graph.astream(initial, config=config, stream_mode="updates"):
            for node, value in chunk.items():
                await bus.publish(
                    thread_id,
                    {"event": "node.update", "node": str(node), "value": value},
                )
    except Exception as exc:  # noqa: BLE001 — publish error event, don't propagate
        log.error("api.session.error", thread_id=thread_id, error=str(exc))
        await bus.publish(
            thread_id,
            {"event": "session.error", "thread_id": thread_id, "error": str(exc)},
        )
    finally:
        try:
            final = await _aget_state(thread_id, checkpointer)
        except Exception:  # noqa: BLE001
            final = None
        await bus.publish(
            thread_id,
            {"event": "session.end", "thread_id": thread_id, "state": final},
        )
        await bus.mark_done(thread_id)


async def _aget_state(
    thread_id: str, checkpointer: BaseCheckpointSaver[Any]
) -> dict[str, Any] | None:
    """Async version of :func:`get_session_state` that works with both
    :class:`MemorySaver` and :class:`AsyncSqliteSaver` backends."""

    from langchain_core.runnables import RunnableConfig

    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    aget_tuple = getattr(checkpointer, "aget_tuple", None)
    if aget_tuple is not None:
        tup = await aget_tuple(config)
    else:
        tup = checkpointer.get_tuple(config)
    if tup is None:
        return None
    return dict(tup.checkpoint.get("channel_values", {}))


async def _alist_thread_ids(checkpointer: BaseCheckpointSaver[Any]) -> list[str]:
    """List thread ids from any checkpointer that exposes ``alist``."""

    alist = getattr(checkpointer, "alist", None)
    if alist is None:
        return list_thread_ids(checkpointer)
    seen: set[str] = set()
    async for tup in alist(None):
        tid = tup.config.get("configurable", {}).get("thread_id")
        if tid:
            seen.add(tid)
    return sorted(seen)


async def _aget_thread_tenant(thread_id: str, checkpointer: BaseCheckpointSaver[Any]) -> str | None:
    """Async tenant lookup that works with both sync and async savers."""

    state = await _aget_state(thread_id, checkpointer)
    if not state:
        return None
    tenant = state.get("tenant_id")
    return tenant if isinstance(tenant, str) else None


# --------------------------------------------------------------------------- #
# App factory                                                                 #
# --------------------------------------------------------------------------- #


def make_app(
    *,
    checkpointer_uri: str | None = None,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
    llm: LLMClient | None = None,
    llm_spec: str | None = None,
    tenant_resolver: TenantResolver | None = None,
    audit_recorder: AuditRecorder | None = None,
) -> FastAPI:
    """Create a FastAPI app.

    * ``checkpointer`` (preferred in tests): use a pre-built checkpointer
      such as :class:`MemorySaver`. The lifespan does not open / close
      anything in this case.
    * ``checkpointer_uri``: any URI accepted by
      :func:`agentnet.persistence.async_checkpointer`. The default is
      ``AGENTNET_CHECKPOINTER`` env var, or ``memory`` when unset.
    * ``tenant_resolver``: extracts the tenant id from request headers.
      Defaults to :class:`StaticTenantResolver` (single‑tenant mode) so
      the API stays usable out of the box.
    """

    bus = SessionEventBus()
    resolved_llm = llm if llm is not None else make_llm_client(llm_spec)
    resolver: TenantResolver = tenant_resolver or StaticTenantResolver(DEFAULT_TENANT)
    recorder = audit_recorder

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.bus = bus
        app.state.llm = resolved_llm
        app.state.tenant_resolver = resolver
        app.state.audit_recorder = recorder
        if checkpointer is not None:
            app.state.checkpointer = checkpointer
            yield
            return
        uri = checkpointer_uri or os.environ.get("AGENTNET_CHECKPOINTER") or "memory"
        async with async_checkpointer(uri) as cp:
            app.state.checkpointer = cp
            yield

    app = FastAPI(title="AgentNet", version=__version__, lifespan=lifespan)

    def get_tenant(request: Request) -> str:
        active: TenantResolver = getattr(request.app.state, "tenant_resolver", resolver)
        try:
            return active.resolve(dict(request.headers))
        except PermissionError as exc:
            raise HTTPException(
                status_code=401,
                detail={"error": {"code": "unauthorized", "message": str(exc)}},
            ) from exc

    def _audit(
        request: Request,
        *,
        tenant: str,
        actor: str,
        action: str,
        resource: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        rec: AuditRecorder | None = getattr(request.app.state, "audit_recorder", None)
        if rec is None:
            return
        rec.record(
            NewEvent(
                actor=actor,
                action=action,
                resource=resource,
                tenant_id=tenant,
                payload=payload or {},
            )
        )

    @app.get("/api/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        return HealthResponse()

    async def _ensure_owned_or_404(
        cp: BaseCheckpointSaver[Any], session_id: str, tenant: str
    ) -> dict[str, Any]:
        """Fetch the state and enforce tenant ownership; otherwise 404.

        We reply 404 (not 403) for foreign sessions so that one tenant
        cannot probe whether another tenant's id exists.
        """

        state = await _aget_state(session_id, cp)
        if state is None:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "session_not_found", "session_id": session_id}},
            )
        owner = state.get("tenant_id") or DEFAULT_TENANT
        if owner != tenant:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "session_not_found", "session_id": session_id}},
            )
        return state

    @app.post(
        "/api/session/start",
        response_model=StartSessionResponse,
        status_code=202,
    )
    async def session_start(
        body: StartSessionRequest,
        background_tasks: BackgroundTasks,
        request: Request,
        tenant: str = Depends(get_tenant),
    ) -> StartSessionResponse:
        if body.tenant_id is not None and body.tenant_id != tenant:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": "tenant_mismatch",
                        "message": "tenant_id in body does not match authenticated tenant",
                    }
                },
            )
        thread_id = body.thread_id or f"sess-{uuid.uuid4().hex[:12]}"
        SessionRequest(
            task=body.task,
            mode=body.mode,
            max_iterations=body.max_iterations,
            score_threshold=body.score_threshold,
            tenant_id=tenant,
        )
        cp: BaseCheckpointSaver[Any] = request.app.state.checkpointer
        active_llm: LLMClient | None = getattr(request.app.state, "llm", None)
        background_tasks.add_task(
            _run_session_streaming, body, thread_id, tenant, cp, bus, active_llm
        )
        log.info(
            "api.session.start",
            thread_id=thread_id,
            tenant_id=tenant,
            mode=body.mode,
            llm=getattr(active_llm, "model", None),
        )
        _audit(
            request,
            tenant=tenant,
            actor=tenant,
            action="session.start",
            resource=thread_id,
            payload={
                "task": body.task,
                "mode": body.mode,
                "max_iterations": body.max_iterations,
                "score_threshold": body.score_threshold,
            },
        )
        return StartSessionResponse(session_id=thread_id)

    @app.get("/api/session/{session_id}/state")
    async def session_state(
        session_id: str,
        request: Request,
        tenant: str = Depends(get_tenant),
    ) -> dict[str, Any]:
        cp: BaseCheckpointSaver[Any] = request.app.state.checkpointer
        return await _ensure_owned_or_404(cp, session_id, tenant)

    @app.get("/api/session/{session_id}/stream")
    async def session_stream(
        session_id: str,
        request: Request,
        tenant: str = Depends(get_tenant),
    ) -> EventSourceResponse:
        cp: BaseCheckpointSaver[Any] = request.app.state.checkpointer
        # If we already have state for this session, enforce ownership
        # eagerly. Streams started for a brand-new (not-yet-persisted)
        # session are allowed: the runner publishes the tenant on the
        # session.start event, so the wire is still tenant‑identifiable.
        owner = await _aget_thread_tenant(session_id, cp)
        if owner is not None and owner != tenant:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "session_not_found", "session_id": session_id}},
            )

        async def event_generator() -> AsyncIterator[dict[str, Any]]:
            async for ev in bus.subscribe(session_id):
                if await request.is_disconnected():
                    break
                # sse-starlette str()s non-string `data`, so JSON-encode
                # ourselves to keep the wire format machine-parseable.
                yield {
                    "event": ev.get("event", "message"),
                    "data": json.dumps(ev, default=str, ensure_ascii=False),
                }

        return EventSourceResponse(event_generator())

    @app.post("/api/session/{session_id}/approve", response_model=ApprovalResponse)
    async def session_approve(
        session_id: str,
        body: ApprovalRequest,
        request: Request,
        tenant: str = Depends(get_tenant),
    ) -> ApprovalResponse:
        cp: BaseCheckpointSaver[Any] = request.app.state.checkpointer
        # Approval may arrive before the first checkpoint is persisted
        # (HITL queue semantics). Only enforce ownership when we already
        # have state for the session.
        owner = await _aget_thread_tenant(session_id, cp)
        if owner is not None and owner != tenant:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "session_not_found", "session_id": session_id}},
            )
        await bus.publish(
            session_id,
            {
                "event": "approval.recorded",
                "step_id": body.step_id,
                "decision": body.decision,
                "comment": body.comment,
                "tenant_id": tenant,
            },
        )
        _audit(
            request,
            tenant=tenant,
            actor=tenant,
            action="session.approve",
            resource=session_id,
            payload={
                "step_id": body.step_id,
                "decision": body.decision,
                "comment": body.comment,
            },
        )
        return ApprovalResponse(session_id=session_id, step_id=body.step_id, decision=body.decision)

    @app.get("/api/sessions")
    async def sessions_list(
        request: Request,
        tenant: str = Depends(get_tenant),
    ) -> dict[str, Any]:
        cp: BaseCheckpointSaver[Any] = request.app.state.checkpointer
        all_threads = await _alist_thread_ids(cp)
        owned: list[str] = []
        for tid in all_threads:
            owner = await _aget_thread_tenant(tid, cp)
            if (owner or DEFAULT_TENANT) == tenant:
                owned.append(tid)
        return {"tenant_id": tenant, "threads": sorted(owned)}

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            payload = detail
        else:
            payload = {"error": {"code": "http_error", "message": str(detail)}}
        return JSONResponse(status_code=exc.status_code, content=payload)

    # keep an unused but documented reference to get_session_state
    _ = get_session_state

    return app


# Module-level app convenient for ``uvicorn agentnet.api:app``
app = make_app()


__all__ = [
    "ApprovalRequest",
    "ApprovalResponse",
    "HealthResponse",
    "SessionEventBus",
    "StartSessionRequest",
    "StartSessionResponse",
    "app",
    "make_app",
]
