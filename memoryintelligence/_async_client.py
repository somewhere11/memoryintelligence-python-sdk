"""Memory Intelligence SDK - Async Client.

Async/await version of MemoryClient for modern Python frameworks.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, AsyncIterator

from ._http import AsyncTransport
from ._auth import resolve_api_key, resolve_base_url, validate_api_key
from ._models import (
    Scope,
    RetentionPolicy,
    PIIHandling,
    ProvenanceMode,
    ExplainLevel,
    MeaningObject,
    SearchResponse,
    SearchResult,
    MatchResult,
    DeleteResult,
    VerifyResult,
    Explanation,
    ExplainHuman,
    ExplainAudit,
    Entity,
    Topic,
    SVOTriple,
    Provenance,
    PIIDetection,
)
from ._errors import ScopeViolationError

logger = logging.getLogger("memoryintelligence")


class AsyncMemoryClient:
    """
    Async client for Memory Intelligence SDK.
    
    Identical API to MemoryClient but with async/await support.
    Ideal for FastAPI, aiohttp, Starlette, and async frameworks.
    
    Usage:
        from memoryintelligence import AsyncMemoryClient
        
        async with AsyncMemoryClient(api_key="mi_sk_...") as mi:
            umo = await mi.process("Meeting notes", user_ulid="01ABC...")
            results = await mi.search("What happened?", user_ulid="01ABC...")
    
    Or without context manager:
        mi = AsyncMemoryClient(api_key="mi_sk_...")
        try:
            umo = await mi.process("Content", user_ulid="01ABC...")
        finally:
            await mi.close()
    """
    
    def __init__(
        self,
        api_key: str | None = None,
        *,
        org_ulid: str | None = None,
        user_ulid: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        device_id: str | None = None,
        actor_type: str | None = None,
    ):
        """
        Initialize async client.

        Args:
            api_key: MI API key (or set MI_API_KEY env var)
            org_ulid: Organization ULID (optional)
            user_ulid: Default user ULID for single-user apps
            base_url: Custom API URL (or set MI_BASE_URL env var)
            timeout: Request timeout in seconds
            max_retries: Max retry attempts for transient errors
            device_id: Persistent device fingerprint for provenance.
                       Auto-generated and cached at ~/.config/mi/device_id
                       if not provided. Sent as X-MI-Device-ID header.
            actor_type: Default actor type ("human", "agent", "system").
                        Sent as X-MI-Actor-Type header. Server infers
                        from API key metadata if not set.
        """
        from ._client import _resolve_device_id

        self._api_key = resolve_api_key(api_key)
        self._base_url = resolve_base_url(base_url)
        validate_api_key(self._api_key, self._base_url)

        self._org_ulid = org_ulid
        self._default_user_ulid = user_ulid
        self._device_id = _resolve_device_id(device_id)
        self._actor_type = actor_type

        self._transport = AsyncTransport(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=timeout,
            max_retries=max_retries,
            device_id=self._device_id,
            actor_type=self._actor_type,
        )

        logger.debug(f"AsyncMemoryClient initialized (base_url={self._base_url})")
    
    async def __aenter__(self) -> "AsyncMemoryClient":
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def close(self) -> None:
        """Close the async HTTP client."""
        await self._transport.close()
    
    def for_user(self, user_ulid: str) -> "AsyncMemoryClient":
        """
        Create a scoped client for a specific user.
        
        For multi-tenant backends - avoids passing user_ulid on every call.
        
        Args:
            user_ulid: User's ULID
            
        Returns:
            New AsyncMemoryClient scoped to that user
            
        Example:
            async with AsyncMemoryClient(api_key="mi_sk_...") as mi:
                user = mi.for_user("01ABC...")
                umo = await user.process("Content")  # No user_ulid needed
        """
        return AsyncMemoryClient(
            api_key=self._api_key,
            org_ulid=self._org_ulid,
            user_ulid=user_ulid,
            base_url=self._base_url,
        )
    
    # ========================================================================
    # CORE OPERATIONS
    # ========================================================================
    
    async def process(
        self,
        content: str,
        user_ulid: str | None = None,
        *,
        retention_policy: RetentionPolicy = RetentionPolicy.MEANING_ONLY,
        pii_handling: PIIHandling = PIIHandling.EXTRACT_AND_REDACT,
        provenance_mode: ProvenanceMode = ProvenanceMode.STANDARD,
        scope: Scope = Scope.USER,
        scope_id: str | None = None,
        source: str = "api",
        metadata: dict[str, Any] | None = None,
    ) -> MeaningObject:
        """
        Process raw content into a Meaning Object (async).
        
        Args:
            content: Raw text content
            user_ulid: Owner's ULID (uses default if set)
            retention_policy: What to retain (default: meaning_only)
            pii_handling: PII handling mode
            provenance_mode: Provenance tracking level
            scope: Governance scope
            scope_id: Scope identifier
            source: Source identifier
            metadata: Additional context
            
        Returns:
            MeaningObject with entities, topics, embedding, provenance
        """
        user = user_ulid or self._default_user_ulid
        if not user:
            raise ValueError("user_ulid required (pass directly or use for_user())")
        
        if scope in (Scope.CLIENT, Scope.PROJECT, Scope.TEAM) and not scope_id:
            raise ScopeViolationError(f"scope_id required for {scope.value} scope")
        
        payload = {
            "content": content,
            "user_ulid": user,
            "retention_policy": retention_policy.value,
            "pii_handling": pii_handling.value,
            "provenance_mode": provenance_mode.value,
            "scope": scope.value,
            "scope_id": scope_id,
            "source": source,
            "metadata": metadata or {},
        }
        
        if self._org_ulid:
            payload["org_ulid"] = self._org_ulid
        
        response = await self._transport.request("POST", "/v1/process", json=payload)
        return self._parse_meaning_object(response)
    
    async def search(
        self,
        query: str,
        user_ulid: str | None = None,
        *,
        scope: Scope = Scope.USER,
        scope_id: str | None = None,
        explain: bool | ExplainLevel = False,
        limit: int = 10,
        offset: int = 0,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        topics: list[str] | None = None,
        entities: list[str] | None = None,
        budget_tokens: int | None = None,
    ) -> SearchResponse:
        """
        Search for relevant meaning objects (async).
        
        Args:
            query: Natural language search query
            user_ulid: Searcher's ULID (uses default if set)
            scope: Search scope
            scope_id: Scope identifier
            explain: Include explanation
            limit: Maximum results
            offset: Pagination offset
            date_from: Filter start date
            date_to: Filter end date
            topics: Filter by topics
            entities: Filter by entities
            budget_tokens: Max tokens in response
            
        Returns:
            SearchResponse with ranked results
        """
        user = user_ulid or self._default_user_ulid
        if not user:
            raise ValueError("user_ulid required")
        
        if scope in (Scope.CLIENT, Scope.PROJECT, Scope.TEAM) and not scope_id:
            raise ScopeViolationError(f"scope_id required for {scope.value} scope")
        
        explain_level = (
            ExplainLevel.FULL if explain is True
            else ExplainLevel.NONE if explain is False
            else explain
        )
        
        payload = {
            "query": query,
            "user_ulid": user,
            "scope": scope.value,
            "scope_id": scope_id,
            "explain": explain_level.value,
            "limit": limit,
            "offset": offset,
            "budget_tokens": budget_tokens,
        }
        
        if date_from:
            payload["date_from"] = date_from.isoformat()
        if date_to:
            payload["date_to"] = date_to.isoformat()
        if topics:
            payload["topics"] = topics
        if entities:
            payload["entities"] = entities
        if self._org_ulid:
            payload["org_ulid"] = self._org_ulid
        
        response = await self._transport.request("POST", "/v1/search", json=payload)
        return self._parse_search_response(response, query, scope)
    
    async def search_iter(
        self,
        query: str,
        user_ulid: str | None = None,
        *,
        scope: Scope = Scope.USER,
        scope_id: str | None = None,
        explain: bool | ExplainLevel = False,
        batch_size: int = 50,
        max_results: int | None = None,
    ) -> AsyncIterator[SearchResult]:
        """
        Auto-paginating search iterator (async).
        
        Yields results one at a time, automatically fetching next pages.
        
        Args:
            query: Search query
            user_ulid: User's ULID
            scope: Search scope
            scope_id: Scope identifier
            explain: Include explanations
            batch_size: Results per API call
            max_results: Stop after this many results (None = unlimited)
            
        Yields:
            SearchResult objects
            
        Example:
            async for result in mi.search_iter("project updates", user_ulid="01ABC..."):
                print(result.umo.summary)
        """
        offset = 0
        count = 0
        
        while True:
            response = await self.search(
                query=query,
                user_ulid=user_ulid,
                scope=scope,
                scope_id=scope_id,
                explain=explain,
                limit=batch_size,
                offset=offset,
            )
            
            if not response.results:
                break
            
            for result in response.results:
                yield result
                count += 1
                if max_results and count >= max_results:
                    return
            
            offset += len(response.results)
            
            if len(response.results) < batch_size:
                break
    
    async def match(
        self,
        source_ulid: str,
        candidate_ulid: str,
        *,
        explain: bool | ExplainLevel = False,
        threshold: float = 0.7,
    ) -> MatchResult:
        """Compare two UMOs for relevance (async)."""
        explain_level = (
            ExplainLevel.FULL if explain is True
            else ExplainLevel.NONE if explain is False
            else explain
        )
        
        payload = {
            "source_ulid": source_ulid,
            "candidate_ulid": candidate_ulid,
            "explain": explain_level.value,
            "threshold": threshold,
        }
        
        if self._org_ulid:
            payload["org_ulid"] = self._org_ulid
        
        response = await self._transport.request("POST", "/v1/match", json=payload)
        return self._parse_match_result(response, source_ulid, candidate_ulid)
    
    async def explain(
        self,
        umo_id: str,
        *,
        level: ExplainLevel = ExplainLevel.FULL,
    ) -> Explanation:
        """Get explanation for a UMO (async)."""
        payload = {"umo_id": umo_id, "level": level.value}
        
        if self._org_ulid:
            payload["org_ulid"] = self._org_ulid
        
        response = await self._transport.request("GET", f"/v1/explain/{umo_id}", params=payload)
        return self._parse_explanation(response)
    
    async def delete(
        self,
        user_ulid: str | None = None,
        *,
        scope: Scope = Scope.ALL,
        scope_id: str | None = None,
    ) -> DeleteResult:
        """Delete all meaning for a user/scope (async)."""
        user = user_ulid or self._default_user_ulid
        if not user:
            raise ValueError("user_ulid required")
        
        payload = {
            "user_ulid": user,
            "scope": scope.value,
            "scope_id": scope_id,
        }
        
        if self._org_ulid:
            payload["org_ulid"] = self._org_ulid
        
        response = await self._transport.request("DELETE", "/v1/delete", json=payload)
        
        return DeleteResult(
            deleted_count=response.get("deleted_count", 0),
            user_ulid=user,
            scope=scope,
            scope_id=scope_id,
            audit_proof=response.get("audit_proof", {}),
        )
    
    async def verify_provenance(self, content_hash: str) -> VerifyResult:
        """Verify provenance of content (async)."""
        response = await self._transport.request(
            "GET",
            f"/v1/provenance/verify/{content_hash}"
        )
        
        return VerifyResult(
            valid=response.get("valid", False),
            semantic_hash=response.get("semantic_hash", content_hash),
            timestamp_anchor=datetime.fromisoformat(
                response.get("timestamp_anchor", datetime.utcnow().isoformat())
            ),
            original_author_ulid=response.get("original_author_ulid"),
            first_published=datetime.fromisoformat(response["first_published"])
                if response.get("first_published") else None,
            hash_chain_valid=response.get("hash_chain_valid", True),
            audit_proof=response.get("audit_proof", {}),
        )
    
    # ========================================================================
    # BATCH OPERATIONS
    # ========================================================================
    
    async def process_batch(
        self,
        items: list[dict[str, Any]],
        user_ulid: str | None = None,
        *,
        retention_policy: RetentionPolicy = RetentionPolicy.MEANING_ONLY,
        pii_handling: PIIHandling = PIIHandling.EXTRACT_AND_REDACT,
        scope: Scope = Scope.USER,
        fail_fast: bool = False,
    ) -> list[MeaningObject | Exception]:
        """
        Process multiple items in batch (async).
        
        Args:
            items: List of dicts with 'content' and optional 'metadata'
            user_ulid: Owner's ULID
            retention_policy: Retention mode
            pii_handling: PII handling mode
            scope: Governance scope
            fail_fast: Stop on first error (default: continue)
            
        Returns:
            List of MeaningObject or Exception for each item
            
        Example:
            results = await mi.process_batch([
                {"content": "Meeting notes 1"},
                {"content": "Meeting notes 2", "metadata": {"source": "zoom"}},
            ], user_ulid="01ABC...")
        """
        import asyncio
        
        user = user_ulid or self._default_user_ulid
        if not user:
            raise ValueError("user_ulid required")
        
        async def process_one(item: dict) -> MeaningObject | Exception:
            try:
                return await self.process(
                    content=item["content"],
                    user_ulid=user,
                    retention_policy=retention_policy,
                    pii_handling=pii_handling,
                    scope=scope,
                    metadata=item.get("metadata"),
                )
            except Exception as e:
                if fail_fast:
                    raise
                return e
        
        return await asyncio.gather(*[process_one(item) for item in items])
    
    # ========================================================================
    # PARSING HELPERS
    # ========================================================================
    
    def _parse_meaning_object(self, data: dict[str, Any]) -> MeaningObject:
        """Parse API response into MeaningObject."""
        return MeaningObject(
            umo_id=data["umo_id"],
            user_ulid=data["user_ulid"],
            entities=[
                Entity(
                    text=e["text"],
                    type=e["type"],
                    confidence=e.get("confidence", 1.0),
                    first_seen=datetime.fromisoformat(e["first_seen"]) if e.get("first_seen") else None,
                    resolved_ulid=e.get("resolved_ulid"),
                )
                for e in data.get("entities", [])
            ],
            topics=[
                Topic(
                    name=t["name"],
                    confidence=t.get("confidence", 1.0),
                    parent=t.get("parent"),
                )
                for t in data.get("topics", [])
            ],
            svo_triples=[
                SVOTriple(
                    subject=s["subject"],
                    verb=s["verb"],
                    object=s["object"],
                    confidence=s.get("confidence", 1.0),
                )
                for s in data.get("svo_triples", [])
            ],
            key_phrases=data.get("key_phrases", []),
            summary=data.get("summary"),
            embedding=data.get("embedding"),
            embedding_model=data.get("embedding_model", ""),
            sentiment_label=data.get("sentiment_label"),
            sentiment_score=data.get("sentiment_score", 0.0),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None,
            ingested_at=datetime.fromisoformat(data.get("ingested_at", datetime.utcnow().isoformat())),
            recency_score=data.get("recency_score", 1.0),
            quality_score=data.get("quality_score", 0.0),
            validation_status=data.get("validation_status", "pending"),
            provenance=Provenance(
                semantic_hash=data["provenance"]["semantic_hash"],
                timestamp_anchor=datetime.fromisoformat(data["provenance"]["timestamp_anchor"]),
                hash_chain=data["provenance"]["hash_chain"],
                lineage=data["provenance"].get("lineage", []),
                model_version=data["provenance"].get("model_version", ""),
            ) if data.get("provenance") else None,
            pii=PIIDetection(
                detected=data["pii"]["detected"],
                types=data["pii"].get("types", []),
                count=data["pii"].get("count", 0),
                handling_applied=PIIHandling(data["pii"].get("handling_applied", "detect_only")),
            ) if data.get("pii") else None,
            scope=Scope(data.get("scope", "user")),
            scope_id=data.get("scope_id"),
        )
    
    def _parse_search_response(
        self,
        data: dict[str, Any],
        query: str,
        scope: Scope
    ) -> SearchResponse:
        """Parse API response into SearchResponse."""
        results = []
        for r in data.get("results", []):
            umo = self._parse_meaning_object(r["umo"])
            explain = self._parse_explanation(r["explain"]) if r.get("explain") else None
            results.append(SearchResult(
                umo=umo,
                score=r["score"],
                explain=explain,
            ))
        
        return SearchResponse(
            results=results,
            query=query,
            scope=scope,
            total_count=data.get("total_count", len(results)),
            audit_proof=data.get("audit_proof"),
        )
    
    def _parse_match_result(
        self,
        data: dict[str, Any],
        source_ulid: str,
        candidate_ulid: str
    ) -> MatchResult:
        """Parse API response into MatchResult."""
        return MatchResult(
            score=data["score"],
            match=data["match"],
            source_ulid=source_ulid,
            candidate_ulid=candidate_ulid,
            explain=self._parse_explanation(data["explain"]) if data.get("explain") else None,
        )
    
    def _parse_explanation(self, data: dict[str, Any]) -> Explanation:
        """Parse explanation data."""
        return Explanation(
            human=ExplainHuman(
                summary=data.get("human", {}).get("summary", ""),
                key_reasons=data.get("human", {}).get("key_reasons", []),
                what_changed=data.get("human", {}).get("what_changed"),
            ),
            audit=ExplainAudit(
                semantic_score=data.get("audit", {}).get("semantic_score", 0.0),
                temporal_score=data.get("audit", {}).get("temporal_score", 0.0),
                entity_score=data.get("audit", {}).get("entity_score", 0.0),
                graph_score=data.get("audit", {}).get("graph_score", 0.0),
                topic_match=data.get("audit", {}).get("topic_match", []),
                model_version=data.get("audit", {}).get("model_version", ""),
                hash_chain=data.get("audit", {}).get("hash_chain", ""),
                reproducible=data.get("audit", {}).get("reproducible", True),
            ),
        )
