"""Memory Intelligence SDK - Core Client.

Main client for Memory Intelligence with UMO namespace pattern.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ._auth import (
    resolve_api_key,
    resolve_base_url,
    validate_key_environment,
    validate_key_format,
)
from ._crypto import SDKEncryptor, log_ephemeral_warning
from ._errors import ConfigurationError
from ._http import AsyncTransport, SyncTransport
from ._license import LicenseManager
from ._models import (
    BatchResult,
    BatchItemResult,
    BatchUploadItemResult,
    BatchUploadResult,
    DeleteResult,
    ExplainLevel,
    MatchResult,
    MeaningObject,
    PIIHandling,
    ProvenanceMode,
    RetentionPolicy,
    UploadResult,
    Scope,
    SearchResponse,
)
from ._version import __version__

if TYPE_CHECKING:
    from ._models import Explanation

logger = logging.getLogger("memoryintelligence")


def _resolve_device_id(explicit: str | None = None) -> str:
    """
    Resolve a persistent device identifier for provenance attribution.

    The device_id travels in the X-MI-Device-ID header on every request,
    letting the server attribute memories to a specific machine without
    the developer having to think about it.

    Resolution chain (first non-None wins):
      1. Explicit argument (passed to MemoryClient)
      2. MI_DEVICE_ID environment variable
      3. Persisted file at ~/.config/mi/device_id
      4. Auto-generate a new UUID, persist it, return it

    The persisted file ensures the same machine always sends the same ID
    across process restarts, virtualenvs, and SDK upgrades.
    """
    import os
    import uuid
    from pathlib import Path

    # 1. Explicit
    if explicit:
        return explicit

    # 2. Environment variable
    env_id = os.environ.get("MI_DEVICE_ID")
    if env_id:
        return env_id

    # 3. Persisted file
    config_dir = Path.home() / ".config" / "mi"
    device_file = config_dir / "device_id"
    try:
        if device_file.exists():
            stored = device_file.read_text().strip()
            if stored:
                return stored
    except OSError:
        pass  # Permissions, read-only FS, etc. — fall through

    # 4. Auto-generate and persist
    new_id = f"pydev_{uuid.uuid4().hex[:16]}"
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        device_file.write_text(new_id + "\n")
        logger.debug(f"Generated device_id: {new_id} → {device_file}")
    except OSError as e:
        logger.debug(f"Could not persist device_id (non-fatal): {e}")

    return new_id


class UMONamespace:
    """
    Bound to a MemoryClient instance. Exposes all UMO operations.
    Access via: mi.umo.process(), mi.umo.search(), etc.
    """

    def __init__(self, client: "MemoryClient"):
        self._client = client

    def _resolve_user_ulid(self, explicit: str | None) -> str:
        """
        Resolve user_ulid from explicit argument or client default.

        Args:
            explicit: Explicit user_ulid passed to method

        Returns:
            Resolved user_ulid

        Raises:
            ConfigurationError: If no user_ulid available
        """
        ulid = explicit or self._client._user_ulid
        if not ulid:
            raise ConfigurationError(
                "user_ulid is required. Pass it directly or initialize with "
                "MemoryClient(user_ulid=...) or use mi.for_user(ulid)."
            )
        return ulid

    def process(
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
        metadata: dict | None = None,
        actor_type: str | None = None,
        device_id: str | None = None,
    ) -> MeaningObject:
        """
        Process raw content into a Meaning Object.

        This is the core operation: content goes in, meaning comes out,
        raw content is discarded (by default).

        Args:
            content: Raw text content to process
            user_ulid: Owner's ULID (optional if set on client)
            retention_policy: What to retain (default: meaning_only)
            pii_handling: How to handle PII (default: extract_and_redact)
            provenance_mode: Provenance tracking level (default: standard)
            scope: Governance scope (default: user)
            scope_id: Scope identifier (e.g., client_ulid for Scope.CLIENT)
            source: Source identifier (e.g., "slack", "email")
            metadata: Additional context
            actor_type: Override actor type ("human", "agent", "system").
                        Server infers from API key and headers if not set.
            device_id: Override device fingerprint. Server auto-generates
                       a caller fingerprint from API key + User-Agent + IP
                       if not set.

        Returns:
            MeaningObject with entities, topics, embedding, provenance

        Raises:
            PIIViolationError: If PII detected and pii_handling=REJECT
            ScopeViolationError: If scope_id required but not provided
            LicenseError: If license tier insufficient
        """
        # Check license
        self._client._license.check_feature("umo.process")

        # Resolve user_ulid
        resolved_user_ulid = self._resolve_user_ulid(user_ulid)

        # Validate scope_id requirement
        if scope in (Scope.CLIENT, Scope.PROJECT, Scope.TEAM) and not scope_id:
            raise ConfigurationError(
                f"scope_id required for {scope.value} scope"
            )

        # Encrypt content
        encrypted = self._client._encryptor.encrypt_content(
            content, resolved_user_ulid
        )

        # Build payload
        payload = {
            "content": {
                "ciphertext": encrypted.ciphertext,
                "nonce": encrypted.nonce,
                "tag": encrypted.tag,
                "key_id": encrypted.key_id,
                "algorithm": encrypted.algorithm,
            },
            "user_ulid": resolved_user_ulid,
            "retention_policy": retention_policy.value,
            "pii_handling": pii_handling.value,
            "provenance_mode": provenance_mode.value,
            "scope": scope.value,
            "scope_id": scope_id,
            "source": source,
            "metadata": metadata or {},
        }

        # Provenance overrides — only include when explicitly set so the
        # server's inference chain handles the common case automatically.
        if actor_type:
            payload["actor_type"] = actor_type
        if device_id:
            payload["device_id"] = device_id

        if self._client._org_ulid:
            payload["org_ulid"] = self._client._org_ulid

        # Make request
        response = self._client._transport.request(
            "POST",
            "/v1/umo/process",
            json=payload,
        )

        return self._client._parse_meaning_object(response)

    def search(
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
        Search for relevant meaning objects.

        Multi-signal ranking: semantic + temporal + entity + graph.
        Returns compressed meaning (95% smaller than raw).

        Args:
            query: Natural language search query
            user_ulid: Searcher's ULID (optional if set on client)
            scope: Search scope (default: user)
            scope_id: Scope identifier for scoped searches
            explain: Include explanation (default: False)
            limit: Maximum results (default: 10)
            offset: Pagination offset
            date_from: Filter by date range start
            date_to: Filter by date range end
            topics: Filter by topics
            entities: Filter by entities
            budget_tokens: Maximum tokens in response (for cost control)

        Returns:
            SearchResponse with ranked results and explanations

        Raises:
            ScopeViolationError: If scope_id required but not provided
            LicenseError: If license tier insufficient
        """
        # Check license
        self._client._license.check_feature("umo.search")

        # Resolve user_ulid
        resolved_user_ulid = self._resolve_user_ulid(user_ulid)

        # Validate scope_id requirement
        if scope in (Scope.CLIENT, Scope.PROJECT, Scope.TEAM) and not scope_id:
            raise ConfigurationError(
                f"scope_id required for {scope.value} scope"
            )

        # Normalize explain parameter
        if isinstance(explain, bool):
            explain_level = ExplainLevel.FULL if explain else ExplainLevel.NONE
        else:
            explain_level = explain

        # Build payload
        payload: dict[str, Any] = {
            "query": query,
            "user_ulid": resolved_user_ulid,
            "scope": scope.value,
            "scope_id": scope_id,
            "explain": explain_level.value,
            "limit": limit,
            "offset": offset,
        }

        if date_from:
            payload["date_from"] = date_from.isoformat()
        if date_to:
            payload["date_to"] = date_to.isoformat()
        if topics:
            payload["topics"] = topics
        if entities:
            payload["entities"] = entities
        if budget_tokens:
            payload["budget_tokens"] = budget_tokens
        if self._client._org_ulid:
            payload["org_ulid"] = self._client._org_ulid

        # Make request
        response = self._client._transport.request(
            "POST",
            "/v1/umo/search",
            json=payload,
        )

        return self._client._parse_search_response(response, query, scope)

    def match(
        self,
        source_ulid: str,
        candidate_ulid: str,
        *,
        explain: bool | ExplainLevel = False,
        threshold: float = 0.7,
    ) -> MatchResult:
        """
        Compare two meaning objects for relevance.

        Used for recommendations: "Is this content relevant to this user?"

        Args:
            source_ulid: User or memory ULID (the "who")
            candidate_ulid: Candidate memory ULID (the "what")
            explain: Include explanation (default: False)
            threshold: Match threshold (default: 0.7)

        Returns:
            MatchResult with score and explanation

        Raises:
            LicenseError: If license tier insufficient (STARTER cannot use)
        """
        # Check license - match requires PROFESSIONAL or ENTERPRISE
        self._client._license.check_feature("umo.match")

        # Normalize explain parameter
        if isinstance(explain, bool):
            explain_level = ExplainLevel.FULL if explain else ExplainLevel.NONE
        else:
            explain_level = explain

        # Build payload
        payload: dict[str, Any] = {
            "source_ulid": source_ulid,
            "candidate_ulid": candidate_ulid,
            "explain": explain_level.value,
            "threshold": threshold,
        }

        if self._client._org_ulid:
            payload["org_ulid"] = self._client._org_ulid

        # Make request
        response = self._client._transport.request(
            "POST",
            "/v1/umo/match",
            json=payload,
        )

        return self._client._parse_match_result(response, source_ulid, candidate_ulid)

    def explain(
        self,
        umo_id: str,
        *,
        level: ExplainLevel = ExplainLevel.FULL,
    ) -> "Explanation":
        """
        Get detailed explanation for any meaning object.

        Returns human-readable + machine-verifiable explanation.

        Args:
            umo_id: ULID of the meaning object
            level: Explanation level (default: full)

        Returns:
            Explanation with human and audit components

        Raises:
            LicenseError: If license tier insufficient (STARTER cannot use)
            NotFoundError: If UMO not found
        """
        # Check license - explain requires PROFESSIONAL or ENTERPRISE
        self._client._license.check_feature("umo.explain")

        # Build payload
        payload: dict[str, Any] = {
            "umo_id": umo_id,
            "level": level.value,
        }

        if self._client._org_ulid:
            payload["org_ulid"] = self._client._org_ulid

        # Make request
        response = self._client._transport.request(
            "GET",
            f"/v1/umo/explain/{umo_id}",
            params=payload,
        )

        return self._client._parse_explanation(response)

    def delete(
        self,
        user_ulid: str | None = None,
        *,
        scope: Scope = Scope.ALL,
        scope_id: str | None = None,
    ) -> DeleteResult:
        """
        Delete all meaning for a user/scope.

        GDPR compliance in one API call. Provenance proves deletion.

        Args:
            user_ulid: User whose data to delete (optional if set on client)
            scope: Scope to delete (default: ALL)
            scope_id: Specific scope to delete (for partial deletion)

        Returns:
            DeleteResult with count and audit proof
        """
        # Check license
        self._client._license.check_feature("umo.delete")

        # Resolve user_ulid
        resolved_user_ulid = self._resolve_user_ulid(user_ulid)

        # Build payload
        payload: dict[str, Any] = {
            "user_ulid": resolved_user_ulid,
            "scope": scope.value,
            "scope_id": scope_id,
        }

        if self._client._org_ulid:
            payload["org_ulid"] = self._client._org_ulid

        # Make request
        response = self._client._transport.request(
            "DELETE",
            "/v1/umo/delete",
            json=payload,
        )

        return DeleteResult(
            deleted_count=response.get("deleted_count", 0),
            user_ulid=resolved_user_ulid,
            scope=scope,
            scope_id=scope_id,
            audit_proof=response.get("audit_proof", {}),
        )

    def batch(
        self,
        items: list[dict],
        *,
        user_ulid: str | None = None,
        retention_policy: RetentionPolicy = RetentionPolicy.MEANING_ONLY,
        pii_handling: PIIHandling = PIIHandling.EXTRACT_AND_REDACT,
        scope: Scope = Scope.USER,
        actor_type: str | None = None,
        device_id: str | None = None,
    ) -> BatchResult:
        """
        Process multiple content items in a single request.

        Each item is processed independently — one failure does not
        block the rest. Accepts up to 50 items per call.

        Args:
            items: List of content items. Each can be:
                   - A string (uses shared user_ulid/scope)
                   - A dict with 'content' and optional overrides
            user_ulid: Default user ULID for all items (optional if set on client)
            retention_policy: Default retention policy
            pii_handling: Default PII handling
            scope: Default scope
            actor_type: Default actor type for all items ("human", "agent", "system").
                        Per-item overrides via dict items are respected.
            device_id: Default device fingerprint. Per-item overrides are respected.

        Returns:
            BatchResult with per-item results and success/failure counts

        Example:
            result = mi.umo.batch([
                "Meeting notes from Monday standup",
                "Design review feedback on v2 mockups",
                {"content": "Private note", "scope": "user"},
            ])
            print(f"Captured {result.succeeded}/{result.total}")
        """
        self._client._license.check_feature("umo.process")

        resolved_user_ulid = self._resolve_user_ulid(user_ulid)

        # Normalize items: accept strings or dicts
        normalized_items = []
        for item in items:
            if isinstance(item, str):
                entry = {
                    "content": item,
                    "user_ulid": resolved_user_ulid,
                    "retention_policy": retention_policy.value,
                    "pii_handling": pii_handling.value,
                    "scope": scope.value,
                }
                # Apply batch-level provenance defaults for string items
                if actor_type:
                    entry["actor_type"] = actor_type
                if device_id:
                    entry["device_id"] = device_id
                normalized_items.append(entry)
            elif isinstance(item, dict):
                entry = {
                    "content": item["content"],
                    "user_ulid": item.get("user_ulid", resolved_user_ulid),
                    "retention_policy": item.get("retention_policy", retention_policy.value),
                    "pii_handling": item.get("pii_handling", pii_handling.value),
                    "scope": item.get("scope", scope.value),
                    "metadata": item.get("metadata", {}),
                }
                # Per-item actor_type/device_id override batch-level defaults
                _item_actor = item.get("actor_type", actor_type)
                _item_device = item.get("device_id", device_id)
                if _item_actor:
                    entry["actor_type"] = _item_actor
                if _item_device:
                    entry["device_id"] = _item_device
                normalized_items.append(entry)
            else:
                raise ConfigurationError(
                    f"Batch items must be strings or dicts, got {type(item).__name__}"
                )

        if self._client._org_ulid:
            for entry in normalized_items:
                entry.setdefault("org_ulid", self._client._org_ulid)

        payload = {"items": normalized_items}

        response = self._client._transport.request(
            "POST",
            "/v1/umo/batch",
            json=payload,
        )

        # Parse results
        results = []
        for r in response.get("results", []):
            umo = None
            if r.get("umo"):
                umo = self._client._parse_meaning_object(r["umo"])
            results.append(BatchItemResult(
                index=r["index"],
                success=r["success"],
                umo_id=r.get("umo_id"),
                error=r.get("error"),
                umo=umo,
            ))

        return BatchResult(
            results=results,
            total=response.get("total", len(items)),
            succeeded=response.get("succeeded", 0),
            failed=response.get("failed", 0),
        )

    def upload(
        self,
        file_path: str,
        *,
        user_ulid: str | None = None,
        scope: str = "user",
        metadata: dict | None = None,
    ) -> UploadResult:
        """
        Upload a media file and process into a UMO.

        Supports audio (.mp3, .wav, .m4a, .flac, .ogg),
        video (.mp4, .mov, .avi, .mkv), image (.png, .jpg, .gif),
        and documents (.pdf).

        The file is uploaded, text is extracted via the appropriate
        handler (Whisper for audio/video, OCR for images, pdfplumber
        for PDFs), then processed through the full intelligence pipeline.

        Args:
            file_path: Path to the file to upload
            user_ulid: Owner's ULID (optional if set on client)
            scope: Governance scope (default: "user")
            metadata: Additional context (optional)

        Returns:
            UploadResult with UMO ID, extracted text stats, and metadata

        Example:
            result = mi.umo.upload("interview.mp4")
            print(f"Transcribed: {result.extracted_text_length} chars")
            print(f"Entities: {result.entities}")
        """
        import json as _json
        from pathlib import Path as _Path

        self._client._license.check_feature("umo.process")
        resolved_user_ulid = self._resolve_user_ulid(user_ulid)

        path = _Path(file_path)
        if not path.exists():
            raise ConfigurationError(f"File not found: {file_path}")

        # Build multipart form data — bypass JSON Content-Type
        form_data = {
            "user_ulid": resolved_user_ulid,
            "scope": scope,
        }
        if self._client._org_ulid:
            form_data["org_ulid"] = self._client._org_ulid
        if metadata:
            form_data["metadata_json"] = _json.dumps(metadata)

        with open(path, "rb") as f:
            # Use transport's raw httpx client for multipart upload
            # (the standard request() method sets Content-Type: application/json)
            request_id = self._client._transport._generate_request_id()
            headers = {
                "Authorization": f"Bearer {self._client._api_key}",
                "X-MI-SDK-Version": __version__,
                "X-MI-Request-ID": request_id,
                "Accept": "application/json",
            }
            # Include provenance headers so the server can infer actor/device
            if self._client._device_id:
                headers["X-MI-Device-ID"] = self._client._device_id
            if self._client._actor_type:
                headers["X-MI-Actor-Type"] = self._client._actor_type
            response = self._client._transport._client.request(
                "POST",
                "/v1/umo/upload",
                headers=headers,
                files={"file": (path.name, f)},
                data=form_data,
            )

        if response.status_code >= 400:
            body = response.json() if response.content else {}
            self._client._transport._raise_for_status(
                response.status_code, body, request_id,
            )

        data = response.json()
        return UploadResult(**data)

    def batch_upload(
        self,
        items: list,
        *,
        user_ulid: str | None = None,
        scope: str = "user",
    ) -> BatchUploadResult:
        """
        Upload a mix of text and media files in a single request.

        Each item processes independently — one failure does not block
        the rest. Accepts up to 50 items and 10 files per call.

        Args:
            items: List where each element is one of:
                   - A string → processed as inline text
                   - A pathlib.Path or file path string ending in a known extension
                     → uploaded and processed as media
                   - A dict with "type" and either "content" (text) or "path" (file)
            user_ulid: Owner's ULID (optional if set on client)
            scope: Governance scope (default: "user")

        Returns:
            BatchUploadResult with per-item results and success/failure counts

        Example:
            from pathlib import Path
            result = mi.umo.batch_upload([
                "Meeting notes from Monday standup",
                Path("interview.mp3"),
                Path("whiteboard.png"),
                {"type": "text", "content": "Design review feedback"},
                {"type": "file", "path": "report.pdf", "metadata": {"source": "email"}},
            ])
            print(f"Captured {result.succeeded}/{result.total}")
            for item in result.results:
                print(f"  [{item.index}] {item.type}: {item.umo_id}")
        """
        import json as _json
        from pathlib import Path as _Path

        self._client._license.check_feature("umo.process")
        resolved_user_ulid = self._resolve_user_ulid(user_ulid)

        # Known media extensions for auto-detection
        MEDIA_EXTS = {
            ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma", ".aac", ".opus",
            ".webm", ".mp4", ".mov", ".avi", ".mkv",
            ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp",
            ".pdf",
        }

        # Normalize items into manifest + file list
        manifest = []
        file_handles = []
        file_paths = []

        for item in items:
            if isinstance(item, str):
                # String: check if it looks like a file path
                p = _Path(item)
                if p.suffix.lower() in MEDIA_EXTS and p.exists():
                    fidx = len(file_paths)
                    file_paths.append(p)
                    manifest.append({"type": "file", "file_index": fidx})
                else:
                    manifest.append({"type": "text", "content": item})

            elif hasattr(item, "__fspath__") or isinstance(item, _Path):
                # Path object
                p = _Path(item)
                if not p.exists():
                    raise ConfigurationError(f"File not found: {item}")
                fidx = len(file_paths)
                file_paths.append(p)
                manifest.append({"type": "file", "file_index": fidx})

            elif isinstance(item, dict):
                item_type = item.get("type", "text")
                if item_type == "text":
                    manifest.append({
                        "type": "text",
                        "content": item["content"],
                        "metadata": item.get("metadata", {}),
                    })
                elif item_type == "file":
                    p = _Path(item["path"])
                    if not p.exists():
                        raise ConfigurationError(f"File not found: {item['path']}")
                    fidx = len(file_paths)
                    file_paths.append(p)
                    entry = {"type": "file", "file_index": fidx}
                    if item.get("metadata"):
                        entry["metadata"] = item["metadata"]
                    manifest.append(entry)
                else:
                    raise ConfigurationError(
                        f"Unknown item type '{item_type}'. Use 'text' or 'file'."
                    )
            else:
                raise ConfigurationError(
                    f"Batch items must be strings, Paths, or dicts, got {type(item).__name__}"
                )

        # Build multipart request
        form_data = {
            "items_json": _json.dumps(manifest),
            "user_ulid": resolved_user_ulid,
            "scope": scope,
        }
        if self._client._org_ulid:
            form_data["org_ulid"] = self._client._org_ulid

        # Open all files
        try:
            opened_files = []
            for p in file_paths:
                fh = open(p, "rb")
                file_handles.append(fh)
                opened_files.append(("files", (p.name, fh)))

            # Use raw httpx client for multipart (standard transport sets JSON content-type)
            request_id = self._client._transport._generate_request_id()
            headers = {
                "Authorization": f"Bearer {self._client._api_key}",
                "X-MI-SDK-Version": __version__,
                "X-MI-Request-ID": request_id,
                "Accept": "application/json",
            }
            # Include provenance headers for server-side inference
            if self._client._device_id:
                headers["X-MI-Device-ID"] = self._client._device_id
            if self._client._actor_type:
                headers["X-MI-Actor-Type"] = self._client._actor_type
            response = self._client._transport._client.request(
                "POST",
                "/v1/umo/batch-upload",
                headers=headers,
                files=opened_files if opened_files else None,
                data=form_data,
            )
        finally:
            for fh in file_handles:
                fh.close()

        if response.status_code >= 400:
            body = response.json() if response.content else {}
            self._client._transport._raise_for_status(
                response.status_code, body, request_id,
            )

        data = response.json()
        return BatchUploadResult(
            results=[BatchUploadItemResult(**r) for r in data.get("results", [])],
            total=data.get("total", len(items)),
            succeeded=data.get("succeeded", 0),
            failed=data.get("failed", 0),
        )

    # ── Human-readable aliases ──────────────────────────────────────────────
    # These map the natural vocabulary (capture, ask, verify, forget, read)
    # to the internal method names (process, search, explain, delete).
    # Designed for non-developer and getting-started-guide ergonomics.

    capture = process
    """Alias for process(). Store raw content as a Unified Memory Object."""

    ask = search
    """Alias for search(). Retrieve memories by semantic meaning."""

    verify = explain
    """Alias for explain(). Understand what a memory contains and its scores."""

    forget = delete
    """Alias for delete(). GDPR-compliant removal with cryptographic receipt."""


class MemoryClient:
    """
    Official Python client for Memory Intelligence.

    Quick start:
        mi = MemoryClient()           # reads MI_API_KEY from env
        umo = mi.umo.process("Meeting notes", user_ulid="01ABC...")
        results = mi.umo.search("What did we decide?", user_ulid="01ABC...")

    Multi-tenant:
        user = mi.for_user("01ABC...")
        umo = user.umo.process("Meeting notes")
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        user_ulid: str | None = None,
        org_ulid: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        encryption_key: str | None = None,
        device_id: str | None = None,
        actor_type: str | None = None,
    ):
        # Auth
        self._api_key = resolve_api_key(api_key)
        self._base_url = resolve_base_url(base_url)
        validate_key_format(self._api_key)
        validate_key_environment(self._api_key, self._base_url)

        # Identity
        self._user_ulid = user_ulid
        self._org_ulid = org_ulid

        # Provenance: device_id is auto-resolved if not provided.
        # Priority: explicit arg > MI_DEVICE_ID env > ~/.config/mi/device_id file > auto-generate
        self._device_id = _resolve_device_id(device_id)
        self._actor_type = actor_type  # None = let server infer from API key / User-Agent

        # Transport
        self._transport = SyncTransport(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=timeout,
            max_retries=max_retries,
            device_id=self._device_id,
            actor_type=self._actor_type,
        )

        # Encryption priority: explicit key > MI_ENCRYPTION_KEY env > derive from API key.
        # Derivation (PBKDF2, fixed salt) lets the server independently reconstruct
        # the same key — zero key management, rotates with API key rotation.
        import os as _os
        if encryption_key is not None:
            self._encryptor = SDKEncryptor(key=encryption_key)
        elif _os.environ.get("MI_ENCRYPTION_KEY"):
            self._encryptor = SDKEncryptor()  # picks up MI_ENCRYPTION_KEY
        else:
            self._encryptor = SDKEncryptor.from_api_key(self._api_key)

        # License
        self._license = LicenseManager(self._api_key, self._transport)
        self._license.validate_on_init()
        self._license.schedule_background_revalidation()

        # UMO namespace
        self.umo = UMONamespace(self)

    def for_user(self, user_ulid: str) -> "MemoryClient":
        """
        Return a client scoped to a specific user.
        Shares HTTP transport and encryption — no new connections.

        Args:
            user_ulid: User ULID to scope to

        Returns:
            MemoryClient instance scoped to user
        """
        scoped = MemoryClient.__new__(MemoryClient)
        scoped.__dict__ = self.__dict__.copy()
        scoped._user_ulid = user_ulid
        scoped.umo = UMONamespace(scoped)
        return scoped

    def close(self) -> None:
        """Close the HTTP client."""
        self._transport.close()
        self._license.stop_background_revalidation()

    def __enter__(self) -> "MemoryClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _parse_meaning_object(self, data: dict[str, Any]) -> MeaningObject:
        """Parse API response into MeaningObject."""
        from ._models import (
            Entity,
            ExplainAudit,
            ExplainHuman,
            Explanation,
            PIIDetection,
            Provenance,
            SVOTriple,
            Topic,
        )

        # Parse entities
        entities = [
            Entity(
                text=e["text"],
                type=e["type"],
                confidence=e.get("confidence", 1.0),
                first_seen=datetime.fromisoformat(e["first_seen"]) if e.get("first_seen") else None,
                resolved_ulid=e.get("resolved_ulid"),
            )
            for e in data.get("entities", [])
        ]

        # Parse topics
        topics = [
            Topic(
                name=t["name"],
                confidence=t.get("confidence", 1.0),
                parent=t.get("parent"),
            )
            for t in data.get("topics", [])
        ]

        # Parse SVO triples
        svo_triples = [
            SVOTriple(
                subject=s["subject"],
                verb=s["verb"],
                object=s["object"],
                confidence=s.get("confidence", 1.0),
            )
            for s in data.get("svo_triples", [])
        ]

        # Parse provenance
        provenance = None
        if data.get("provenance"):
            prov = data["provenance"]
            provenance = Provenance(
                semantic_hash=prov["semantic_hash"],
                timestamp_anchor=datetime.fromisoformat(prov["timestamp_anchor"]),
                hash_chain=prov["hash_chain"],
                lineage=prov.get("lineage", []),
                model_version=prov.get("model_version", ""),
            )

        # Parse PII
        pii = None
        if data.get("pii"):
            pii_data = data["pii"]
            pii = PIIDetection(
                detected=pii_data["detected"],
                types=pii_data.get("types", []),
                count=pii_data.get("count", 0),
                handling_applied=pii_data.get("handling_applied", "detect_only"),
            )

        return MeaningObject(
            umo_id=data["umo_id"],
            user_ulid=data["user_ulid"],
            entities=entities,
            topics=topics,
            svo_triples=svo_triples,
            key_phrases=data.get("key_phrases", []),
            summary=data.get("summary"),
            embedding=data.get("embedding"),
            embedding_model=data.get("embedding_model", ""),
            sentiment_label=data.get("sentiment_label"),
            sentiment_score=data.get("sentiment_score", 0.0),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None,
            ingested_at=datetime.fromisoformat(data.get("ingested_at", datetime.now().isoformat())),
            recency_score=data.get("recency_score", 1.0),
            quality_score=data.get("quality_score", 0.0),
            validation_status=data.get("validation_status", "pending"),
            provenance=provenance,
            pii=pii,
            scope=Scope(data.get("scope", "user")),
            scope_id=data.get("scope_id"),
        )

    def _parse_search_response(
        self,
        data: dict[str, Any],
        query: str,
        scope: Scope,
    ) -> SearchResponse:
        """Parse API response into SearchResponse."""
        from ._models import SearchResult

        results = [
            SearchResult(
                umo=self._parse_meaning_object(r["umo"]),
                score=r["score"],
                explain=self._parse_explanation(r["explain"]) if r.get("explain") else None,
            )
            for r in data.get("results", [])
        ]

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
        candidate_ulid: str,
    ) -> MatchResult:
        """Parse API response into MatchResult."""
        return MatchResult(
            score=data["score"],
            match=data["match"],
            source_ulid=source_ulid,
            candidate_ulid=candidate_ulid,
            explain=self._parse_explanation(data["explain"]) if data.get("explain") else None,
        )

    def _parse_explanation(self, data: dict[str, Any] | None) -> "Explanation | None":
        """Parse explanation data."""
        if not data:
            return None

        from ._models import ExplainAudit, ExplainHuman, Explanation

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


class AsyncMemoryClient:
    """
    Asynchronous Python client for Memory Intelligence.

    Same API as MemoryClient but all umo.* methods are async.

    Quick start:
        async with AsyncMemoryClient() as mi:
            umo = await mi.umo.process("Notes", user_ulid="01ABC...")
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        user_ulid: str | None = None,
        org_ulid: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        encryption_key: str | None = None,
    ):
        # Auth
        self._api_key = resolve_api_key(api_key)
        self._base_url = resolve_base_url(base_url)
        validate_key_format(self._api_key)
        validate_key_environment(self._api_key, self._base_url)

        # Identity
        self._user_ulid = user_ulid
        self._org_ulid = org_ulid

        # Transport
        self._transport = AsyncTransport(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=timeout,
            max_retries=max_retries,
        )

        # Encryption priority: explicit key > MI_ENCRYPTION_KEY env > derive from API key.
        # Derivation (PBKDF2, fixed salt) lets the server independently reconstruct
        # the same key — zero key management, rotates with API key rotation.
        import os as _os
        if encryption_key is not None:
            self._encryptor = SDKEncryptor(key=encryption_key)
        elif _os.environ.get("MI_ENCRYPTION_KEY"):
            self._encryptor = SDKEncryptor()  # picks up MI_ENCRYPTION_KEY
        else:
            self._encryptor = SDKEncryptor.from_api_key(self._api_key)

        # Note: Async license validation happens on first request
        # We can't do async validation in __init__
        self._license = None
        self._license_validated = False

        # UMO namespace
        self.umo = AsyncUMONamespace(self)

    async def _ensure_license(self) -> LicenseManager:
        """Ensure license is validated (async)."""
        if not self._license_validated:
            self._license = LicenseManager(self._api_key, self._transport)
            await self._license.validate_on_init_async()
            await self._license.schedule_background_revalidation_async()
            self._license_validated = True
        return self._license

    def for_user(self, user_ulid: str) -> "AsyncMemoryClient":
        """
        Return a client scoped to a specific user.
        Shares HTTP transport and encryption — no new connections.
        """
        scoped = AsyncMemoryClient.__new__(AsyncMemoryClient)
        scoped.__dict__ = self.__dict__.copy()
        scoped._user_ulid = user_ulid
        scoped.umo = AsyncUMONamespace(scoped)
        return scoped

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._transport.close()
        if self._license:
            await self._license.stop_background_revalidation_async()

    async def __aenter__(self) -> "AsyncMemoryClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # Parser methods (sync, same as MemoryClient)
    _parse_meaning_object = MemoryClient._parse_meaning_object
    _parse_search_response = MemoryClient._parse_search_response
    _parse_match_result = MemoryClient._parse_match_result
    _parse_explanation = MemoryClient._parse_explanation


class AsyncUMONamespace:
    """Async version of UMONamespace."""

    def __init__(self, client: AsyncMemoryClient):
        self._client = client

    def _resolve_user_ulid(self, explicit: str | None) -> str:
        """Resolve user_ulid from explicit argument or client default."""
        ulid = explicit or self._client._user_ulid
        if not ulid:
            raise ConfigurationError(
                "user_ulid is required. Pass it directly or initialize with "
                "AsyncMemoryClient(user_ulid=...) or use mi.for_user(ulid)."
            )
        return ulid

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
        metadata: dict | None = None,
    ) -> MeaningObject:
        """Async version of process."""
        license = await self._client._ensure_license()
        license.check_feature("umo.process")

        resolved_user_ulid = self._resolve_user_ulid(user_ulid)

        if scope in (Scope.CLIENT, Scope.PROJECT, Scope.TEAM) and not scope_id:
            raise ConfigurationError(f"scope_id required for {scope.value} scope")

        encrypted = self._client._encryptor.encrypt_content(
            content, resolved_user_ulid
        )

        payload = {
            "content": {
                "ciphertext": encrypted.ciphertext,
                "nonce": encrypted.nonce,
                "tag": encrypted.tag,
                "key_id": encrypted.key_id,
                "algorithm": encrypted.algorithm,
            },
            "user_ulid": resolved_user_ulid,
            "retention_policy": retention_policy.value,
            "pii_handling": pii_handling.value,
            "provenance_mode": provenance_mode.value,
            "scope": scope.value,
            "scope_id": scope_id,
            "source": source,
            "metadata": metadata or {},
        }

        if self._client._org_ulid:
            payload["org_ulid"] = self._client._org_ulid

        response = await self._client._transport.request(
            "POST",
            "/v1/umo/process",
            json=payload,
        )

        return self._client._parse_meaning_object(response)

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
        """Async version of search."""
        license = await self._client._ensure_license()
        license.check_feature("umo.search")

        resolved_user_ulid = self._resolve_user_ulid(user_ulid)

        if scope in (Scope.CLIENT, Scope.PROJECT, Scope.TEAM) and not scope_id:
            raise ConfigurationError(f"scope_id required for {scope.value} scope")

        if isinstance(explain, bool):
            explain_level = ExplainLevel.FULL if explain else ExplainLevel.NONE
        else:
            explain_level = explain

        payload: dict[str, Any] = {
            "query": query,
            "user_ulid": resolved_user_ulid,
            "scope": scope.value,
            "scope_id": scope_id,
            "explain": explain_level.value,
            "limit": limit,
            "offset": offset,
        }

        if date_from:
            payload["date_from"] = date_from.isoformat()
        if date_to:
            payload["date_to"] = date_to.isoformat()
        if topics:
            payload["topics"] = topics
        if entities:
            payload["entities"] = entities
        if budget_tokens:
            payload["budget_tokens"] = budget_tokens
        if self._client._org_ulid:
            payload["org_ulid"] = self._client._org_ulid

        response = await self._client._transport.request(
            "POST",
            "/v1/umo/search",
            json=payload,
        )

        return self._client._parse_search_response(response, query, scope)

    async def match(
        self,
        source_ulid: str,
        candidate_ulid: str,
        *,
        explain: bool | ExplainLevel = False,
        threshold: float = 0.7,
    ) -> MatchResult:
        """Async version of match."""
        license = await self._client._ensure_license()
        license.check_feature("umo.match")

        if isinstance(explain, bool):
            explain_level = ExplainLevel.FULL if explain else ExplainLevel.NONE
        else:
            explain_level = explain

        payload: dict[str, Any] = {
            "source_ulid": source_ulid,
            "candidate_ulid": candidate_ulid,
            "explain": explain_level.value,
            "threshold": threshold,
        }

        if self._client._org_ulid:
            payload["org_ulid"] = self._client._org_ulid

        response = await self._client._transport.request(
            "POST",
            "/v1/umo/match",
            json=payload,
        )

        return self._client._parse_match_result(response, source_ulid, candidate_ulid)

    async def explain(
        self,
        umo_id: str,
        *,
        level: ExplainLevel = ExplainLevel.FULL,
    ) -> "Explanation":
        """Async version of explain."""
        license = await self._client._ensure_license()
        license.check_feature("umo.explain")

        payload: dict[str, Any] = {
            "umo_id": umo_id,
            "level": level.value,
        }

        if self._client._org_ulid:
            payload["org_ulid"] = self._client._org_ulid

        response = await self._client._transport.request(
            "GET",
            f"/v1/umo/explain/{umo_id}",
            params=payload,
        )

        return self._client._parse_explanation(response)

    async def delete(
        self,
        user_ulid: str | None = None,
        *,
        scope: Scope = Scope.ALL,
        scope_id: str | None = None,
    ) -> DeleteResult:
        """Async version of delete."""
        license = await self._client._ensure_license()
        license.check_feature("umo.delete")

        resolved_user_ulid = self._resolve_user_ulid(user_ulid)

        payload: dict[str, Any] = {
            "user_ulid": resolved_user_ulid,
            "scope": scope.value,
            "scope_id": scope_id,
        }

        if self._client._org_ulid:
            payload["org_ulid"] = self._client._org_ulid

        response = await self._client._transport.request(
            "DELETE",
            "/v1/umo/delete",
            json=payload,
        )

        return DeleteResult(
            deleted_count=response.get("deleted_count", 0),
            user_ulid=resolved_user_ulid,
            scope=scope,
            scope_id=scope_id,
            audit_proof=response.get("audit_proof", {}),
        )

    # ── Human-readable aliases (async) ──────────────────────────────────────
    capture = process
    """Alias for process(). Store raw content as a Unified Memory Object."""

    ask = search
    """Alias for search(). Retrieve memories by semantic meaning."""

    verify = explain
    """Alias for explain(). Understand what a memory contains and its scores."""

    forget = delete
    """Alias for delete(). GDPR-compliant removal with cryptographic receipt."""
