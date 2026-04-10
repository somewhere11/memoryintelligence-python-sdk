"""Memory Intelligence SDK - Utilities.

Convenience utilities for common SDK tasks:
- Logging configuration
- Webhook signature verification
- Search query builder
- Debug helpers
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from ._models import Scope, ExplainLevel


# ============================================================================
# LOGGING
# ============================================================================

def enable_debug_logging(*, stream: bool = True, file: str | None = None) -> None:
    """
    Enable debug logging for the SDK.
    
    Useful for troubleshooting API issues, seeing requests/responses.
    
    Args:
        stream: Log to stdout/stderr (default: True)
        file: Optional file path to write logs
        
    Example:
        import memoryintelligence
        memoryintelligence.enable_debug_logging()
        
        mi = memoryintelligence.MemoryClient(api_key="mi_sk_...")
        mi.process("Test")  # Will log request/response details
    """
    logger = logging.getLogger("memoryintelligence")
    logger.setLevel(logging.DEBUG)
    
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    if stream:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    if file:
        handler = logging.FileHandler(file)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(formatter)
        logger.addHandler(handler)


def disable_debug_logging() -> None:
    """Disable debug logging (reset to WARNING level)."""
    logger = logging.getLogger("memoryintelligence")
    logger.setLevel(logging.WARNING)
    logger.handlers = []


# ============================================================================
# WEBHOOKS
# ============================================================================

@dataclass
class WebhookEvent:
    """A verified webhook event from Memory Intelligence."""
    id: str
    type: str  # e.g., "umo.created", "umo.deleted", "usage.threshold"
    timestamp: datetime
    data: dict[str, Any]
    org_ulid: str | None = None
    user_ulid: str | None = None


class WebhookVerificationError(Exception):
    """Webhook signature verification failed."""
    pass


def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str,
    *,
    tolerance_seconds: int = 300,
) -> WebhookEvent:
    """
    Verify webhook signature and parse event.
    
    Memory Intelligence webhooks use HMAC-SHA256 signatures.
    
    Args:
        payload: Raw request body (bytes)
        signature: X-MI-Signature header value
        secret: Your webhook secret (from dashboard)
        tolerance_seconds: Max age of webhook (default: 5 minutes)
        
    Returns:
        Verified WebhookEvent
        
    Raises:
        WebhookVerificationError: If signature is invalid or payload too old
        
    Example:
        from memoryintelligence import verify_webhook_signature
        
        @app.post("/webhooks/mi")
        async def handle_mi_webhook(request: Request):
            payload = await request.body()
            signature = request.headers.get("X-MI-Signature")
            
            event = verify_webhook_signature(
                payload=payload,
                signature=signature,
                secret=os.environ["MI_WEBHOOK_SECRET"],
            )
            
            if event.type == "umo.created":
                print(f"New UMO: {event.data['umo_id']}")
    """
    import json
    
    # Parse signature header: t=timestamp,v1=signature
    parts = {}
    for part in signature.split(","):
        if "=" in part:
            key, value = part.split("=", 1)
            parts[key] = value
    
    if "t" not in parts or "v1" not in parts:
        raise WebhookVerificationError("Invalid signature format")
    
    timestamp = int(parts["t"])
    expected_sig = parts["v1"]
    
    # Check timestamp tolerance
    now = int(datetime.utcnow().timestamp())
    if abs(now - timestamp) > tolerance_seconds:
        raise WebhookVerificationError(
            f"Webhook timestamp too old ({abs(now - timestamp)}s > {tolerance_seconds}s)"
        )
    
    # Compute expected signature
    signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
    computed_sig = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(computed_sig, expected_sig):
        raise WebhookVerificationError("Signature mismatch")
    
    # Parse payload
    data = json.loads(payload)
    
    return WebhookEvent(
        id=data.get("id", ""),
        type=data.get("type", ""),
        timestamp=datetime.fromtimestamp(timestamp),
        data=data.get("data", {}),
        org_ulid=data.get("org_ulid"),
        user_ulid=data.get("user_ulid"),
    )


# ============================================================================
# SEARCH BUILDER (Fluent API)
# ============================================================================

@dataclass
class SearchBuilder:
    """
    Fluent builder for complex search queries.
    
    Provides a chainable API for building searches with IDE autocompletion.
    
    Example:
        from memoryintelligence import MemoryClient, SearchBuilder
        
        mi = MemoryClient(api_key="mi_sk_...")
        
        results = (
            SearchBuilder(mi)
            .query("project updates")
            .user("01ABC...")
            .scope(Scope.PROJECT, "01XYZ...")
            .topics(["engineering", "planning"])
            .entities(["John", "Budget"])
            .date_range(last_30_days)
            .with_explanation()
            .limit(20)
            .execute()
        )
    """
    _client: Any  # MemoryClient or AsyncMemoryClient
    _query: str = ""
    _user_ulid: str | None = None
    _scope: Scope = Scope.USER
    _scope_id: str | None = None
    _explain: ExplainLevel = ExplainLevel.NONE
    _limit: int = 10
    _offset: int = 0
    _date_from: datetime | None = None
    _date_to: datetime | None = None
    _topics: list[str] = field(default_factory=list)
    _entities: list[str] = field(default_factory=list)
    _budget_tokens: int | None = None
    
    def query(self, q: str) -> "SearchBuilder":
        """Set the search query."""
        self._query = q
        return self
    
    def user(self, user_ulid: str) -> "SearchBuilder":
        """Set the user ULID."""
        self._user_ulid = user_ulid
        return self
    
    def scope(self, scope: Scope, scope_id: str | None = None) -> "SearchBuilder":
        """Set the search scope."""
        self._scope = scope
        self._scope_id = scope_id
        return self
    
    def topics(self, topics: list[str]) -> "SearchBuilder":
        """Filter by topics."""
        self._topics = topics
        return self
    
    def entities(self, entities: list[str]) -> "SearchBuilder":
        """Filter by entities."""
        self._entities = entities
        return self
    
    def date_range(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None
    ) -> "SearchBuilder":
        """Filter by date range."""
        self._date_from = from_date
        self._date_to = to_date
        return self
    
    def with_explanation(self, level: ExplainLevel = ExplainLevel.FULL) -> "SearchBuilder":
        """Include explanation in results."""
        self._explain = level
        return self
    
    def limit(self, n: int) -> "SearchBuilder":
        """Set max results."""
        self._limit = n
        return self
    
    def offset(self, n: int) -> "SearchBuilder":
        """Set pagination offset."""
        self._offset = n
        return self
    
    def budget(self, tokens: int) -> "SearchBuilder":
        """Set token budget."""
        self._budget_tokens = tokens
        return self
    
    def execute(self):
        """Execute the search (sync)."""
        return self._client.search(
            query=self._query,
            user_ulid=self._user_ulid,
            scope=self._scope,
            scope_id=self._scope_id,
            explain=self._explain,
            limit=self._limit,
            offset=self._offset,
            date_from=self._date_from,
            date_to=self._date_to,
            topics=self._topics or None,
            entities=self._entities or None,
            budget_tokens=self._budget_tokens,
        )
    
    async def execute_async(self):
        """Execute the search (async)."""
        return await self._client.search(
            query=self._query,
            user_ulid=self._user_ulid,
            scope=self._scope,
            scope_id=self._scope_id,
            explain=self._explain,
            limit=self._limit,
            offset=self._offset,
            date_from=self._date_from,
            date_to=self._date_to,
            topics=self._topics or None,
            entities=self._entities or None,
            budget_tokens=self._budget_tokens,
        )


# ============================================================================
# REQUEST HOOKS
# ============================================================================

RequestHook = Callable[[str, str, dict[str, Any]], dict[str, Any] | None]
ResponseHook = Callable[[str, str, dict[str, Any], dict[str, Any]], dict[str, Any] | None]


@dataclass
class Hooks:
    """
    Request/response hooks for middleware functionality.
    
    Allows injecting custom logic before requests and after responses.
    
    Example:
        from memoryintelligence import MemoryClient, Hooks
        
        def log_requests(method, path, payload):
            print(f"Request: {method} {path}")
            return payload  # Return modified payload or None
        
        def log_responses(method, path, payload, response):
            print(f"Response: {response.get('umo_id')}")
            return response
        
        hooks = Hooks(before_request=log_requests, after_response=log_responses)
        mi = MemoryClient(api_key="mi_sk_...", hooks=hooks)
    """
    before_request: RequestHook | None = None
    after_response: ResponseHook | None = None


# ============================================================================
# RAW RESPONSE WRAPPER
# ============================================================================

@dataclass
class RawResponse:
    """
    Wrapper providing access to raw HTTP response.
    
    Useful for debugging or accessing headers.
    """
    status_code: int
    headers: dict[str, str]
    body: dict[str, Any]
    request_id: str
    elapsed_ms: float


# ============================================================================
# ENVIRONMENT HELPERS
# ============================================================================

def get_api_key() -> str | None:
    """Get API key from environment (MI_API_KEY)."""
    return os.environ.get("MI_API_KEY")


def get_base_url() -> str:
    """Get base URL from environment or default."""
    return os.environ.get("MI_BASE_URL", "https://api.memoryintelligence.io")


def is_test_key(api_key: str) -> bool:
    """Check if API key is a test key."""
    return api_key.startswith("mi_sk_test_")


def is_live_key(api_key: str) -> bool:
    """Check if API key is a live key."""
    return api_key.startswith("mi_sk_live_")
