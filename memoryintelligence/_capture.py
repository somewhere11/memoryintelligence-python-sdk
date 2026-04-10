"""
Memory Intelligence SDK — Ambient Capture Primitives
======================================================

Provides three patterns for automatic memory capture without requiring
explicit mi.capture() calls at every relevant point in application code:

  CaptureBuffer        — internal thread-safe buffer with auto-flush
  @mi.capture          — function decorator (sync + async)
  mi.session()         — context manager
  mi.CaptureMiddleware — ASGI middleware (FastAPI / Starlette)

All primitives route through CaptureBuffer → mi.umo.batch() internally.
They never call mi.umo.process() per item — batching is automatic.

Quick start
-----------
Decorator::

    @mi.capture(user_id="01ABC...", source="chat_handler")
    async def handle_message(msg: str) -> str:
        return await llm.generate(msg)

Session::

    async with mi.session(user_id="01ABC...") as session:
        session.add(user_message)
        response = await process(user_message)
        session.add(response)

Middleware (FastAPI / Starlette)::

    app.add_middleware(
        mi.CaptureMiddleware,
        user_resolver=lambda request: request.state.user.id,
        should_capture=lambda req, resp: req.url.path.startswith("/chat"),
        source="api_middleware",
    )
"""

from __future__ import annotations

import asyncio
import functools
import logging
import threading
import time
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, List, Optional, TypeVar, Union

logger = logging.getLogger("memoryintelligence.capture")

F = TypeVar("F", bound=Callable[..., Any])


# =============================================================================
# PENDING ITEM
# =============================================================================

@dataclass
class _PendingItem:
    """One item waiting in the capture buffer."""
    content:         str
    user_id:         str
    source:          str          = "sdk"
    capture_trigger: str          = "explicit"
    metadata:        dict         = field(default_factory=dict)
    retention_policy: str         = "meaning_only"


# =============================================================================
# CAPTURE BUFFER
# =============================================================================

class CaptureBuffer:
    """
    Thread-safe buffer that accumulates capture items and flushes them to
    mi.umo.batch() in groups.

    Flushing happens when:
    - ``flush_interval`` seconds have elapsed since the last flush, OR
    - ``max_size`` items have accumulated (whichever comes first).

    The background flush loop starts the first time an item is added and
    stops automatically when the buffer is closed.

    Args:
        client:         MemoryClient instance to flush to.
        flush_interval: Seconds between automatic flushes (default 5).
        max_size:       Maximum buffered items before an immediate flush (default 20).
        on_error:       Optional callback invoked with the exception if a flush
                        fails. If not provided, errors are logged and dropped.
    """

    def __init__(
        self,
        client: Any,                           # MemoryClient; typed as Any to avoid circular import
        flush_interval: float = 5.0,
        max_size:       int   = 20,
        on_error:       Optional[Callable[[Exception], None]] = None,
    ) -> None:
        self._client        = client
        self._flush_interval = flush_interval
        self._max_size      = max_size
        self._on_error      = on_error

        self._items:    List[_PendingItem] = []
        self._lock      = threading.Lock()
        self._closed    = False
        self._loop:     Optional[asyncio.AbstractEventLoop] = None
        self._flush_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, item: _PendingItem) -> None:
        """
        Add a single item to the buffer.

        If the buffer reaches ``max_size`` after this addition, an immediate
        flush is scheduled without waiting for the timer.
        """
        if self._closed:
            raise RuntimeError("CaptureBuffer is closed; cannot add new items.")

        with self._lock:
            self._items.append(item)
            should_flush = len(self._items) >= self._max_size

        # Ensure background loop is running
        self._ensure_flush_loop()

        if should_flush:
            self._schedule_flush()

    async def flush(self) -> int:
        """
        Flush all buffered items to the API immediately.

        Returns the number of items flushed. Safe to call from any context.
        """
        with self._lock:
            if not self._items:
                return 0
            batch   = self._items[:]
            self._items = []

        if not batch:
            return 0

        try:
            await self._send_batch(batch)
        except Exception as exc:
            logger.error(f"CaptureBuffer flush failed ({len(batch)} items): {exc}")
            if self._on_error:
                self._on_error(exc)
            # Re-queue items so they aren't silently dropped
            with self._lock:
                self._items = batch + self._items
            return 0

        return len(batch)

    def close(self) -> None:
        """
        Stop the background flush loop and prevent new additions.
        Does NOT flush remaining items — call ``flush()`` first if needed.
        """
        self._closed = True
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_flush_loop(self) -> None:
        """Start the background flush loop if not already running."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return   # No running loop — caller is sync, flush will be manual
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = loop.create_task(self._flush_loop())

    def _schedule_flush(self) -> None:
        """Schedule an immediate flush on the running event loop."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.flush())
        except RuntimeError:
            pass   # No running loop; rely on timer

    async def _flush_loop(self) -> None:
        """Background coroutine: flush every ``flush_interval`` seconds."""
        try:
            while not self._closed:
                await asyncio.sleep(self._flush_interval)
                if self._items:
                    await self.flush()
        except asyncio.CancelledError:
            pass

    async def _send_batch(self, items: List[_PendingItem]) -> None:
        """Send a batch of items to the MI API via umo.batch()."""
        batch_dicts = [
            {
                "content":          item.content,
                "user_ulid":        item.user_id,
                "source":           item.source,
                "capture_trigger":  item.capture_trigger,
                "retention_policy": item.retention_policy,
                "metadata":         item.metadata,
            }
            for item in items
        ]

        # umo.batch() is synchronous — run in executor to avoid blocking
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.umo.batch(batch_dicts),
        )


# =============================================================================
# @mi.capture DECORATOR
# =============================================================================

def capture_decorator(
    client: Any,
    *,
    user_id:          str,
    source:           str   = "decorator",
    retention_policy: str   = "meaning_only",
    content_extractor: Optional[Callable[[Any], Optional[str]]] = None,
    metadata:         Optional[dict] = None,
    buffer:           Optional[CaptureBuffer] = None,
) -> Callable[[F], F]:
    """
    Return a decorator that captures the return value of a function as a memory.

    Works with both sync and async functions.

    Args:
        client:            MemoryClient instance.
        user_id:           ULID of the memory owner.
        source:            Source label stored in the UMO (default "decorator").
        retention_policy:  What to retain after processing (default "meaning_only").
        content_extractor: Optional callable to extract a string from the return
                           value. If None, ``str(return_value)`` is used. Return
                           ``None`` from the extractor to skip capture for a
                           particular invocation.
        metadata:          Extra metadata attached to every captured UMO.
        buffer:            CaptureBuffer to use. If None, a new one is created
                           per-decorator (not recommended for high-throughput use;
                           pass a shared buffer).

    Example::

        @mi.capture(user_id="01ABC...", source="chat")
        async def handle(msg: str) -> str:
            return await llm(msg)

        # Custom extractor — only capture if response is long enough
        @mi.capture(
            user_id="01ABC...",
            content_extractor=lambda r: r["text"] if len(r["text"]) > 50 else None,
        )
        def analyse(doc) -> dict:
            ...
    """
    _buffer = buffer or CaptureBuffer(client)
    _meta   = metadata or {}

    def decorator(fn: F) -> F:
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                result = await fn(*args, **kwargs)
                _maybe_capture(result)
                return result
            return async_wrapper  # type: ignore[return-value]
        else:
            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                result = fn(*args, **kwargs)
                _maybe_capture(result)
                return result
            return sync_wrapper  # type: ignore[return-value]

    def _maybe_capture(result: Any) -> None:
        if content_extractor is not None:
            content = content_extractor(result)
        else:
            content = str(result) if result is not None else None

        if content is None or not content.strip():
            return

        _buffer.add(_PendingItem(
            content          = content,
            user_id          = user_id,
            source           = source,
            capture_trigger  = "decorator",
            retention_policy = retention_policy,
            metadata         = _meta,
        ))

    return decorator


# =============================================================================
# mi.session() CONTEXT MANAGER
# =============================================================================

class CaptureSession:
    """
    Accumulates content items during a block and flushes them as a batch
    when the block exits.

    Use when a logical unit of memory spans multiple content fragments
    (e.g. a conversation turn with both user input and model response).

    Example (async)::

        async with mi.session(user_id="01ABC...") as session:
            session.add(user_message)
            response = await llm(user_message)
            session.add(response)
        # Flushes here as a single batch

    Example (sync)::

        with mi.session_sync(user_id="01ABC...") as session:
            session.add(event.body)
    """

    def __init__(
        self,
        client: Any,
        *,
        user_id:          str,
        source:           str  = "session",
        retention_policy: str  = "meaning_only",
        metadata:         Optional[dict] = None,
    ) -> None:
        self._client          = client
        self._user_id         = user_id
        self._source          = source
        self._retention_policy = retention_policy
        self._metadata        = metadata or {}
        self._items:          List[_PendingItem] = []

    def add(self, content: str, metadata: Optional[dict] = None) -> None:
        """
        Add a content fragment to this session.

        Args:
            content:  Text to capture. Empty strings are silently skipped.
            metadata: Per-item metadata merged with the session-level metadata.
        """
        if not content or not content.strip():
            return
        merged = {**self._metadata, **(metadata or {})}
        self._items.append(_PendingItem(
            content          = content,
            user_id          = self._user_id,
            source           = self._source,
            capture_trigger  = "decorator",   # session is a decorator-family primitive
            retention_policy = self._retention_policy,
            metadata         = merged,
        ))

    async def _flush_async(self) -> int:
        """Flush all accumulated items to the API."""
        if not self._items:
            return 0
        buf = CaptureBuffer(self._client, max_size=len(self._items) + 1)
        for item in self._items:
            buf.add(item)
        flushed = await buf.flush()
        self._items = []
        return flushed

    def _flush_sync(self) -> int:
        """Synchronous flush via asyncio.run() (for use in sync contexts)."""
        if not self._items:
            return 0
        try:
            loop = asyncio.get_running_loop()
            # Already in an event loop — schedule as a task and return
            loop.create_task(self._flush_async())
            return len(self._items)
        except RuntimeError:
            return asyncio.run(self._flush_async())


@asynccontextmanager
async def capture_session(
    client: Any,
    *,
    user_id:          str,
    source:           str  = "session",
    retention_policy: str  = "meaning_only",
    metadata:         Optional[dict] = None,
):
    """
    Async context manager. Yields a CaptureSession; flushes on exit.

    Usage::

        async with mi.session(user_id=uid) as s:
            s.add(text)
    """
    session = CaptureSession(
        client,
        user_id=user_id,
        source=source,
        retention_policy=retention_policy,
        metadata=metadata,
    )
    try:
        yield session
    finally:
        await session._flush_async()


@contextmanager
def capture_session_sync(
    client: Any,
    *,
    user_id:          str,
    source:           str  = "session",
    retention_policy: str  = "meaning_only",
    metadata:         Optional[dict] = None,
):
    """
    Synchronous context manager variant. Yields a CaptureSession; flushes on exit.

    Usage::

        with mi.session_sync(user_id=uid) as s:
            s.add(text)
    """
    session = CaptureSession(
        client,
        user_id=user_id,
        source=source,
        retention_policy=retention_policy,
        metadata=metadata,
    )
    try:
        yield session
    finally:
        session._flush_sync()


# =============================================================================
# ASGI MIDDLEWARE
# =============================================================================

class CaptureMiddleware:
    """
    ASGI middleware that automatically captures request/response pairs as memories.

    Install once in your FastAPI or Starlette app::

        from memoryintelligence import MemoryClient
        from memoryintelligence._capture import CaptureMiddleware

        mi = MemoryClient(api_key="mi_sk_...")

        app.add_middleware(
            CaptureMiddleware,
            client=mi,
            user_resolver=lambda request: request.state.user.id,
        )

    Or via mi.CaptureMiddleware shorthand (if the client exposes it)::

        app.add_middleware(
            mi.CaptureMiddleware,
            user_resolver=lambda request: request.state.user.id,
        )

    Args:
        app:              The ASGI application to wrap.
        client:           MemoryClient instance.
        user_resolver:    Callable that takes a Starlette Request and returns
                          a user ULID string. Return None to skip capture for
                          that request (e.g. unauthenticated requests).
        should_capture:   Optional callable(request, response) → bool. Called
                          after the response is available. Return False to skip
                          capture. Default: capture all requests.
        content_extractor: Optional callable(request, response_body_bytes) → str.
                           Default: use the decoded response body as content.
        source:           Source label (default "middleware").
        retention_policy: What to retain (default "meaning_only").
        flush_interval:   Buffer flush interval in seconds (default 5).
        max_buffer_size:  Buffer size threshold for immediate flush (default 20).
        skip_paths:       List of path prefixes to always skip (e.g. ["/health",
                          "/docs", "/metrics"]). Default excludes common infra paths.
    """

    _DEFAULT_SKIP_PATHS = ["/health", "/docs", "/redoc", "/openapi.json", "/metrics", "/favicon.ico"]

    def __init__(
        self,
        app:               Any,
        *,
        client:            Any,
        user_resolver:     Callable[[Any], Optional[str]],
        should_capture:    Optional[Callable[[Any, Any], bool]] = None,
        content_extractor: Optional[Callable[[Any, bytes], Optional[str]]] = None,
        source:            str   = "middleware",
        retention_policy:  str   = "meaning_only",
        flush_interval:    float = 5.0,
        max_buffer_size:   int   = 20,
        skip_paths:        Optional[List[str]] = None,
    ) -> None:
        self.app               = app
        self._client           = client
        self._user_resolver    = user_resolver
        self._should_capture   = should_capture
        self._content_extractor = content_extractor
        self._source           = source
        self._retention_policy = retention_policy
        self._skip_paths       = skip_paths if skip_paths is not None else self._DEFAULT_SKIP_PATHS
        self._buffer           = CaptureBuffer(
            client,
            flush_interval=flush_interval,
            max_size=max_buffer_size,
        )

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Check skip paths early
        path = scope.get("path", "")
        if any(path.startswith(p) for p in self._skip_paths):
            await self.app(scope, receive, send)
            return

        # Intercept the response body
        response_body_chunks: List[bytes] = []
        response_status = 200

        async def send_interceptor(message: dict) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message.get("status", 200)
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                if chunk:
                    response_body_chunks.append(chunk)
            await send(message)

        # Build a minimal request-like object for the resolvers
        # (avoids requiring starlette as a hard dependency)
        class _MinimalRequest:
            def __init__(self, scope: dict) -> None:
                self.scope  = scope
                self.url    = _URL(scope.get("path", ""), scope.get("query_string", b""))
                self.method = scope.get("method", "")
                self.state  = _State(scope.get("state", {}))
                self.headers = {
                    k.decode(): v.decode()
                    for k, v in scope.get("headers", [])
                }

        class _URL:
            def __init__(self, path: str, qs: bytes) -> None:
                self.path = path
        class _State:
            def __init__(self, d: dict) -> None:
                self.__dict__.update(d)

        request = _MinimalRequest(scope)
        await self.app(scope, receive, send_interceptor)

        # Only capture 2xx responses
        if response_status < 200 or response_status >= 300:
            return

        # Resolve user — skip if None (unauthenticated / anonymous)
        try:
            user_id = self._user_resolver(request)
        except Exception:
            return
        if not user_id:
            return

        # Extract content
        body_bytes = b"".join(response_body_chunks)
        if self._content_extractor is not None:
            try:
                content = self._content_extractor(request, body_bytes)
            except Exception:
                return
        else:
            try:
                content = body_bytes.decode("utf-8", errors="replace")
            except Exception:
                return

        if not content or not content.strip():
            return

        # Apply should_capture filter
        if self._should_capture is not None:
            try:
                if not self._should_capture(request, body_bytes):
                    return
            except Exception:
                return

        self._buffer.add(_PendingItem(
            content          = content,
            user_id          = user_id,
            source           = self._source,
            capture_trigger  = "middleware",
            retention_policy = self._retention_policy,
        ))
