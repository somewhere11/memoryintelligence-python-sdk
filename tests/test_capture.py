"""
Tests for sdk/python/memoryintelligence/_capture.py
=====================================================

Covers:
  - CaptureBuffer: add / flush / max-size threshold / error re-queue / closed guard
  - capture_decorator: sync and async wrapping, content_extractor skip, None-return skip
  - CaptureSession / capture_session: accumulate, flush on exit, empty-string skip
  - capture_session_sync: sync variant
  - CaptureMiddleware: skip paths, non-2xx skip, user_resolver None skip, should_capture
    filter, normal 2xx capture, non-HTTP ASGI passthrough

All tests mock mi.umo.batch() at the client level — no HTTP calls are made.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from memoryintelligence._capture import (
    CaptureBuffer,
    CaptureSession,
    CaptureMiddleware,
    _PendingItem,
    capture_decorator,
    capture_session,
    capture_session_sync,
)


# =============================================================================
# Helpers
# =============================================================================

USER_ULID = "01JTEST00000000000000000AA"


def _make_client(batch_side_effect=None):
    """Return a mock MemoryClient with a mock umo.batch()."""
    client = MagicMock()
    client.umo.batch = MagicMock(return_value=None)
    if batch_side_effect is not None:
        client.umo.batch.side_effect = batch_side_effect
    return client


def _make_item(content: str = "hello world") -> _PendingItem:
    return _PendingItem(content=content, user_id=USER_ULID)


# =============================================================================
# CaptureBuffer — unit tests
# =============================================================================

class TestCaptureBuffer:
    """Tests for CaptureBuffer behaviour."""

    # ------------------------------------------------------------------
    # add / accumulation
    # ------------------------------------------------------------------

    async def test_add_accumulates_items(self):
        """Items added to the buffer are held until flush."""
        client = _make_client()
        buf = CaptureBuffer(client, flush_interval=60, max_size=100)
        buf.add(_make_item("first"))
        buf.add(_make_item("second"))
        assert len(buf._items) == 2

    async def test_add_raises_after_close(self):
        """Adding to a closed buffer raises RuntimeError."""
        client = _make_client()
        buf = CaptureBuffer(client)
        buf.close()
        with pytest.raises(RuntimeError, match="closed"):
            buf.add(_make_item())

    # ------------------------------------------------------------------
    # flush
    # ------------------------------------------------------------------

    async def test_flush_drains_buffer_and_calls_batch(self):
        """flush() sends all items to umo.batch() and returns the count."""
        client = _make_client()
        buf = CaptureBuffer(client, flush_interval=60, max_size=100)
        buf.add(_make_item("alpha"))
        buf.add(_make_item("beta"))

        count = await buf.flush()

        assert count == 2
        assert buf._items == []
        client.umo.batch.assert_called_once()
        sent = client.umo.batch.call_args[0][0]   # positional list[dict]
        assert len(sent) == 2
        assert sent[0]["content"] == "alpha"
        assert sent[1]["content"] == "beta"

    async def test_flush_empty_buffer_returns_zero(self):
        """flush() on an empty buffer is a no-op and returns 0."""
        client = _make_client()
        buf = CaptureBuffer(client)
        count = await buf.flush()
        assert count == 0
        client.umo.batch.assert_not_called()

    async def test_flush_includes_all_pending_item_fields(self):
        """Each dict sent to batch includes all _PendingItem fields."""
        client = _make_client()
        buf = CaptureBuffer(client, flush_interval=60, max_size=100)
        item = _PendingItem(
            content="test content",
            user_id=USER_ULID,
            source="test_source",
            capture_trigger="decorator",
            retention_policy="full",
            metadata={"k": "v"},
        )
        buf.add(item)
        await buf.flush()

        sent = client.umo.batch.call_args[0][0][0]
        assert sent["content"]          == "test content"
        assert sent["user_ulid"]        == USER_ULID
        assert sent["source"]           == "test_source"
        assert sent["capture_trigger"]  == "decorator"
        assert sent["retention_policy"] == "full"
        assert sent["metadata"]         == {"k": "v"}

    # ------------------------------------------------------------------
    # max_size threshold
    # ------------------------------------------------------------------

    async def test_max_size_triggers_immediate_flush(self):
        """Reaching max_size schedules an immediate flush task."""
        client = _make_client()
        buf = CaptureBuffer(client, flush_interval=60, max_size=2)

        buf.add(_make_item("one"))
        buf.add(_make_item("two"))  # hits max_size=2

        # Yield to the event loop so the scheduled flush task can run
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert client.umo.batch.call_count >= 1

    # ------------------------------------------------------------------
    # error handling
    # ------------------------------------------------------------------

    async def test_flush_failure_requeues_items(self):
        """If umo.batch() raises, items are put back in the buffer."""
        client = _make_client(batch_side_effect=RuntimeError("network error"))
        buf = CaptureBuffer(client, flush_interval=60, max_size=100)
        buf.add(_make_item("important"))

        count = await buf.flush()

        assert count == 0
        assert len(buf._items) == 1   # re-queued
        assert buf._items[0].content == "important"

    async def test_flush_failure_calls_on_error_callback(self):
        """on_error callback receives the exception when flush fails."""
        errors = []
        client = _make_client(batch_side_effect=RuntimeError("boom"))
        buf = CaptureBuffer(client, flush_interval=60, max_size=100, on_error=errors.append)
        buf.add(_make_item())

        await buf.flush()

        assert len(errors) == 1
        assert isinstance(errors[0], RuntimeError)

    # ------------------------------------------------------------------
    # close
    # ------------------------------------------------------------------

    async def test_close_cancels_flush_task(self):
        """close() cancels the background flush task if running."""
        client = _make_client()
        buf = CaptureBuffer(client, flush_interval=60, max_size=100)
        # Trigger task creation
        buf.add(_make_item())
        buf._ensure_flush_loop()
        assert buf._flush_task is not None
        # cancel() is requested; yield the event loop so the task can process it
        buf.close()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert buf._flush_task.cancelled() or buf._flush_task.done()


# =============================================================================
# capture_decorator — unit tests
# =============================================================================

class TestCaptureDecorator:
    """Tests for capture_decorator() factory."""

    async def test_async_function_return_value_is_captured(self):
        """Decorator captures the return value of an async function."""
        client = _make_client()
        buf = CaptureBuffer(client, flush_interval=60, max_size=100)

        @capture_decorator(client, user_id=USER_ULID, buffer=buf)
        async def generate_text() -> str:
            return "async result"

        result = await generate_text()

        assert result == "async result"
        assert len(buf._items) == 1
        assert buf._items[0].content == "async result"
        assert buf._items[0].capture_trigger == "decorator"

    def test_sync_function_return_value_is_captured(self):
        """Decorator captures the return value of a sync function."""
        client = _make_client()
        buf = CaptureBuffer(client, flush_interval=60, max_size=100)

        @capture_decorator(client, user_id=USER_ULID, buffer=buf)
        def compute() -> str:
            return "sync result"

        result = compute()

        assert result == "sync result"
        assert len(buf._items) == 1
        assert buf._items[0].content == "sync result"

    async def test_content_extractor_none_skips_capture(self):
        """Returning None from content_extractor skips adding to buffer."""
        client = _make_client()
        buf = CaptureBuffer(client, flush_interval=60, max_size=100)

        @capture_decorator(
            client,
            user_id=USER_ULID,
            buffer=buf,
            content_extractor=lambda r: None,  # always skip
        )
        async def handler() -> dict:
            return {"data": "some output"}

        result = await handler()

        assert result == {"data": "some output"}
        assert len(buf._items) == 0   # nothing captured

    async def test_content_extractor_transforms_result(self):
        """content_extractor can extract a substring from the return value."""
        client = _make_client()
        buf = CaptureBuffer(client, flush_interval=60, max_size=100)

        @capture_decorator(
            client,
            user_id=USER_ULID,
            buffer=buf,
            content_extractor=lambda r: r.get("text"),
        )
        async def api_call() -> dict:
            return {"text": "extracted content", "score": 0.9}

        await api_call()

        assert buf._items[0].content == "extracted content"

    async def test_none_return_value_skips_capture(self):
        """If the function returns None (no extractor), nothing is buffered."""
        client = _make_client()
        buf = CaptureBuffer(client, flush_interval=60, max_size=100)

        @capture_decorator(client, user_id=USER_ULID, buffer=buf)
        async def noop():
            return None

        await noop()
        assert len(buf._items) == 0

    async def test_empty_string_return_skips_capture(self):
        """Empty / whitespace-only return values are not captured."""
        client = _make_client()
        buf = CaptureBuffer(client, flush_interval=60, max_size=100)

        @capture_decorator(client, user_id=USER_ULID, buffer=buf)
        async def blank():
            return "   "

        await blank()
        assert len(buf._items) == 0

    def test_decorator_preserves_function_name(self):
        """functools.wraps ensures the wrapped function name is preserved."""
        client = _make_client()

        @capture_decorator(client, user_id=USER_ULID)
        def my_handler():
            return "x"

        assert my_handler.__name__ == "my_handler"

    async def test_source_label_stored_on_item(self):
        """source kwarg is forwarded to the buffered item."""
        client = _make_client()
        buf = CaptureBuffer(client, flush_interval=60, max_size=100)

        @capture_decorator(client, user_id=USER_ULID, source="chat", buffer=buf)
        async def chat_handler():
            return "response text"

        await chat_handler()
        assert buf._items[0].source == "chat"

    async def test_metadata_attached_to_item(self):
        """metadata kwarg is forwarded to the buffered item."""
        client = _make_client()
        buf = CaptureBuffer(client, flush_interval=60, max_size=100)
        meta = {"session_id": "xyz", "version": 2}

        @capture_decorator(client, user_id=USER_ULID, metadata=meta, buffer=buf)
        async def fn():
            return "output"

        await fn()
        assert buf._items[0].metadata == meta


# =============================================================================
# CaptureSession / capture_session — unit tests
# =============================================================================

class TestCaptureSession:
    """Tests for CaptureSession and capture_session context manager."""

    def test_add_accumulates_items(self):
        """session.add() stores items internally."""
        client = _make_client()
        session = CaptureSession(client, user_id=USER_ULID)
        session.add("fragment one")
        session.add("fragment two")
        assert len(session._items) == 2

    def test_add_skips_empty_strings(self):
        """Empty and whitespace-only content is silently skipped."""
        client = _make_client()
        session = CaptureSession(client, user_id=USER_ULID)
        session.add("")
        session.add("   ")
        assert len(session._items) == 0

    def test_add_merges_per_item_metadata(self):
        """Per-item metadata is merged with session-level metadata."""
        client = _make_client()
        session = CaptureSession(client, user_id=USER_ULID, metadata={"session": "s1"})
        session.add("content", metadata={"turn": 1})
        merged = session._items[0].metadata
        assert merged == {"session": "s1", "turn": 1}

    async def test_capture_session_flushes_on_exit(self):
        """async context manager flushes accumulated items on exit."""
        client = _make_client()

        async with capture_session(client, user_id=USER_ULID) as session:
            session.add("line one")
            session.add("line two")

        client.umo.batch.assert_called_once()
        sent = client.umo.batch.call_args[0][0]
        assert len(sent) == 2
        assert sent[0]["content"] == "line one"
        assert sent[1]["content"] == "line two"

    async def test_capture_session_empty_does_not_call_batch(self):
        """If no items are added, batch is never called."""
        client = _make_client()

        async with capture_session(client, user_id=USER_ULID):
            pass   # nothing added

        client.umo.batch.assert_not_called()

    async def test_capture_session_flushes_even_on_exception(self):
        """Items are flushed even if the body raises (finally semantics)."""
        client = _make_client()

        with pytest.raises(ValueError):
            async with capture_session(client, user_id=USER_ULID) as session:
                session.add("pre-error content")
                raise ValueError("test error")

        client.umo.batch.assert_called_once()

    def test_capture_session_sync_flushes_on_exit(self):
        """Synchronous context manager flushes on exit via asyncio.run()."""
        client = _make_client()

        with capture_session_sync(client, user_id=USER_ULID) as session:
            session.add("sync content")

        client.umo.batch.assert_called_once()
        sent = client.umo.batch.call_args[0][0]
        assert sent[0]["content"] == "sync content"

    async def test_session_items_have_correct_trigger(self):
        """CaptureSession items are tagged with capture_trigger='decorator'."""
        client = _make_client()
        session = CaptureSession(client, user_id=USER_ULID)
        session.add("some text")
        assert session._items[0].capture_trigger == "decorator"

    async def test_session_source_label_propagates(self):
        """source kwarg is forwarded to each buffered item."""
        client = _make_client()

        async with capture_session(client, user_id=USER_ULID, source="pipeline") as s:
            s.add("content")

        sent = client.umo.batch.call_args[0][0]
        assert sent[0]["source"] == "pipeline"


# =============================================================================
# CaptureMiddleware — ASGI unit tests
# =============================================================================

def _make_scope(path: str = "/chat", method: str = "POST") -> dict:
    """Build a minimal ASGI HTTP scope dict."""
    return {
        "type":         "http",
        "path":         path,
        "method":       method,
        "headers":      [],
        "query_string": b"",
        "state":        {},
    }


async def _make_app(status: int = 200, body: bytes = b"response body"):
    """Return a minimal ASGI app that replies with the given status and body."""
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": status, "headers": []})
        await send({"type": "http.response.body",  "body": body, "more_body": False})
    return app


async def _call_middleware(middleware: CaptureMiddleware, scope: dict):
    """Invoke middleware with no-op receive/send."""
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        messages.append(msg)

    await middleware(scope, receive, send)
    return messages


class TestCaptureMiddleware:
    """Tests for CaptureMiddleware ASGI behaviour."""

    async def test_captures_2xx_response(self):
        """200 responses with a valid user are added to the buffer."""
        client = _make_client()
        app = await _make_app(status=200, body=b"chat output")

        middleware = CaptureMiddleware(
            app,
            client=client,
            user_resolver=lambda req: USER_ULID,
        )

        await _call_middleware(middleware, _make_scope("/chat"))
        assert len(middleware._buffer._items) == 1
        assert middleware._buffer._items[0].content == "chat output"
        assert middleware._buffer._items[0].capture_trigger == "middleware"

    async def test_skips_default_infra_paths(self):
        """Requests to /health, /docs, /metrics etc. are not captured."""
        client = _make_client()
        app = await _make_app()

        middleware = CaptureMiddleware(
            app,
            client=client,
            user_resolver=lambda req: USER_ULID,
        )

        for path in ["/health", "/docs", "/redoc", "/openapi.json", "/metrics", "/favicon.ico"]:
            await _call_middleware(middleware, _make_scope(path))

        assert len(middleware._buffer._items) == 0

    async def test_skips_custom_skip_paths(self):
        """Custom skip_paths list is respected."""
        client = _make_client()
        app = await _make_app()

        middleware = CaptureMiddleware(
            app,
            client=client,
            user_resolver=lambda req: USER_ULID,
            skip_paths=["/internal", "/admin"],
        )

        await _call_middleware(middleware, _make_scope("/internal/config"))
        assert len(middleware._buffer._items) == 0

    async def test_skips_non_2xx_responses(self):
        """4xx and 5xx responses are not captured."""
        client = _make_client()

        for status in [400, 401, 403, 404, 500, 502]:
            app = await _make_app(status=status, body=b"error")
            middleware = CaptureMiddleware(
                app,
                client=client,
                user_resolver=lambda req: USER_ULID,
            )
            await _call_middleware(middleware, _make_scope("/chat"))

        assert len(middleware._buffer._items) == 0

    async def test_skips_when_user_resolver_returns_none(self):
        """If user_resolver returns None, the request is not captured."""
        client = _make_client()
        app = await _make_app()

        middleware = CaptureMiddleware(
            app,
            client=client,
            user_resolver=lambda req: None,  # unauthenticated
        )

        await _call_middleware(middleware, _make_scope("/chat"))
        assert len(middleware._buffer._items) == 0

    async def test_skips_when_user_resolver_raises(self):
        """If user_resolver raises, the request is silently skipped."""
        client = _make_client()
        app = await _make_app()

        def bad_resolver(req):
            raise AttributeError("no user on request")

        middleware = CaptureMiddleware(app, client=client, user_resolver=bad_resolver)
        await _call_middleware(middleware, _make_scope("/chat"))
        assert len(middleware._buffer._items) == 0

    async def test_should_capture_filter_blocks_capture(self):
        """should_capture returning False prevents capture."""
        client = _make_client()
        app = await _make_app(body=b"filtered out")

        middleware = CaptureMiddleware(
            app,
            client=client,
            user_resolver=lambda req: USER_ULID,
            should_capture=lambda req, body: False,
        )

        await _call_middleware(middleware, _make_scope("/chat"))
        assert len(middleware._buffer._items) == 0

    async def test_should_capture_filter_allows_capture(self):
        """should_capture returning True allows capture to proceed."""
        client = _make_client()
        app = await _make_app(body=b"allowed content")

        middleware = CaptureMiddleware(
            app,
            client=client,
            user_resolver=lambda req: USER_ULID,
            should_capture=lambda req, body: True,
        )

        await _call_middleware(middleware, _make_scope("/chat"))
        assert len(middleware._buffer._items) == 1

    async def test_content_extractor_transforms_body(self):
        """content_extractor can rewrite what gets buffered."""
        client = _make_client()
        app = await _make_app(body=b'{"text": "extracted"}')

        import json as _json
        middleware = CaptureMiddleware(
            app,
            client=client,
            user_resolver=lambda req: USER_ULID,
            content_extractor=lambda req, body: _json.loads(body)["text"],
        )

        await _call_middleware(middleware, _make_scope("/chat"))
        assert middleware._buffer._items[0].content == "extracted"

    async def test_non_http_scope_is_passed_through(self):
        """Non-HTTP ASGI scopes (websocket, lifespan) are forwarded untouched."""
        client = _make_client()

        received_scopes = []

        async def tracking_app(scope, receive, send):
            received_scopes.append(scope["type"])

        middleware = CaptureMiddleware(
            tracking_app,
            client=client,
            user_resolver=lambda req: USER_ULID,
        )

        ws_scope = {"type": "websocket", "path": "/ws", "headers": []}
        await middleware(ws_scope, AsyncMock(), AsyncMock())

        assert "websocket" in received_scopes
        assert len(middleware._buffer._items) == 0

    async def test_source_label_on_captured_item(self):
        """source kwarg propagates to buffered item."""
        client = _make_client()
        app = await _make_app(body=b"some text")

        middleware = CaptureMiddleware(
            app,
            client=client,
            user_resolver=lambda req: USER_ULID,
            source="api_gateway",
        )

        await _call_middleware(middleware, _make_scope("/chat"))
        assert middleware._buffer._items[0].source == "api_gateway"

    async def test_empty_response_body_not_captured(self):
        """An empty response body produces nothing in the buffer."""
        client = _make_client()
        app = await _make_app(body=b"")

        middleware = CaptureMiddleware(
            app,
            client=client,
            user_resolver=lambda req: USER_ULID,
        )

        await _call_middleware(middleware, _make_scope("/chat"))
        assert len(middleware._buffer._items) == 0

    async def test_whitespace_only_body_not_captured(self):
        """Whitespace-only response bodies are not captured."""
        client = _make_client()
        app = await _make_app(body=b"   \n  ")

        middleware = CaptureMiddleware(
            app,
            client=client,
            user_resolver=lambda req: USER_ULID,
        )

        await _call_middleware(middleware, _make_scope("/chat"))
        assert len(middleware._buffer._items) == 0
