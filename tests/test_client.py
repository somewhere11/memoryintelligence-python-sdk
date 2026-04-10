"""Tests for MemoryClient and UMONamespace."""

from __future__ import annotations

import pytest

from memoryintelligence import ConfigurationError, LicenseError, MemoryClient
from memoryintelligence._models import (
    ExplainLevel,
    MatchResult,
    MeaningObject,
    RetentionPolicy,
    Scope,
    SearchResponse,
)


class TestUMOProcess:
    """Tests for umo.process() method."""

    def test_process_happy_path(
        self,
        client: MemoryClient,
        httpx_mock,
        mock_transport_response,
    ) -> None:
        """Test successful process call returns MeaningObject."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.memoryintelligence.io/v1/umo/process",
            json=mock_transport_response
        )

        result = client.umo.process(
            "Test content for processing",
            user_ulid="01DEF12345678901234567890"
        )

        assert isinstance(result, MeaningObject)
        assert result.umo_id == "01ABC12345678901234567890"
        assert result.user_ulid == "01DEF12345678901234567890"
        assert len(result.entities) == 1
        assert result.entities[0].text == "John Doe"

    def test_process_user_ulid_from_client(
        self,
        api_key: str,
        httpx_mock,
        mock_transport_response,
    ) -> None:
        """Test user_ulid resolved from client default."""
        # Mock license validation
        httpx_mock.add_response(
            method="POST",
            url="https://api.memoryintelligence.io/v1/license/validate",
            json={"status": "active", "tier": "professional"}
        )
        # Mock process endpoint
        httpx_mock.add_response(
            method="POST",
            url="https://api.memoryintelligence.io/v1/umo/process",
            json=mock_transport_response
        )

        client = MemoryClient(api_key=api_key, user_ulid="01DEF12345678901234567890")
        result = client.umo.process("Content without explicit user_ulid")

        assert isinstance(result, MeaningObject)
        client.close()

    def test_process_no_user_ulid_raises_error(
        self,
        api_key: str,
        httpx_mock,
    ) -> None:
        """Test ConfigurationError when no user_ulid available."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.memoryintelligence.io/v1/license/validate",
            json={"status": "active", "tier": "professional"}
        )

        client = MemoryClient(api_key=api_key)

        with pytest.raises(ConfigurationError) as exc_info:
            client.umo.process("Content without user_ulid")

        assert "user_ulid is required" in str(exc_info.value)
        client.close()

    def test_process_explicit_user_ulid_overrides_default(
        self,
        api_key: str,
        httpx_mock,
        mock_transport_response,
    ) -> None:
        """Test explicit user_ulid overrides client default."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.memoryintelligence.io/v1/license/validate",
            json={"status": "active", "tier": "professional"}
        )
        httpx_mock.add_response(
            method="POST",
            url="https://api.memoryintelligence.io/v1/umo/process",
            json={**mock_transport_response, "user_ulid": "01EXPLICIT12345678901234567890"}
        )

        client = MemoryClient(api_key=api_key, user_ulid="01DEFAULT12345678901234567890")
        result = client.umo.process(
            "Content",
            user_ulid="01EXPLICIT12345678901234567890"
        )

        assert result.user_ulid == "01EXPLICIT12345678901234567890"
        client.close()

    def test_process_scope_requires_scope_id(
        self,
        client: MemoryClient,
    ) -> None:
        """Test scope violation error when scope_id missing."""
        with pytest.raises(ConfigurationError) as exc_info:
            client.umo.process(
                "Content",
                user_ulid="01DEF12345678901234567890",
                scope=Scope.CLIENT
            )

        assert "scope_id required" in str(exc_info.value)

    def test_process_content_is_encrypted(
        self,
        client: MemoryClient,
        httpx_mock,
        mock_transport_response,
    ) -> None:
        """Test content is encrypted before sending."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.memoryintelligence.io/v1/umo/process",
            json=mock_transport_response
        )

        client.umo.process(
            "Test content",
            user_ulid="01DEF12345678901234567890"
        )

        # Get the request that was made
        request = httpx_mock.get_request(method="POST", url="https://api.memoryintelligence.io/v1/umo/process")
        assert request is not None

        import json
        body = json.loads(request.content)
        assert "content" in body
        assert "ciphertext" in body["content"]
        assert "nonce" in body["content"]
        assert "tag" in body["content"]
        assert "key_id" in body["content"]
        assert body["content"]["algorithm"] == "AES-256-GCM"


class TestUMOSearch:
    """Tests for umo.search() method."""

    def test_search_happy_path(
        self,
        client: MemoryClient,
        httpx_mock,
        mock_transport_response,
    ) -> None:
        """Test successful search returns SearchResponse."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.memoryintelligence.io/v1/umo/search",
            json={
                "results": [{"umo": mock_transport_response, "score": 0.95}],
                "total_count": 1
            }
        )

        result = client.umo.search(
            "What did we decide?",
            user_ulid="01DEF12345678901234567890"
        )

        assert isinstance(result, SearchResponse)
        assert result.query == "What did we decide?"
        assert len(result.results) == 1
        assert result.results[0].score == 0.95

    def test_search_with_filters(
        self,
        client: MemoryClient,
        httpx_mock,
        mock_transport_response,
    ) -> None:
        """Test search with date range and topic filters."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.memoryintelligence.io/v1/umo/search",
            json={"results": [], "total_count": 0}
        )

        from datetime import datetime, timezone

        client.umo.search(
            "Budget discussions",
            user_ulid="01DEF12345678901234567890",
            topics=["budget", "finance"],
            date_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
            limit=5
        )

        request = httpx_mock.get_request(url="https://api.memoryintelligence.io/v1/umo/search")
        import json
        body = json.loads(request.content)
        assert body["topics"] == ["budget", "finance"]
        assert body["limit"] == 5
        assert "date_from" in body


class TestUMOMatch:
    """Tests for umo.match() method."""

    def test_match_happy_path(
        self,
        client: MemoryClient,
        httpx_mock,
    ) -> None:
        """Test successful match returns MatchResult."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.memoryintelligence.io/v1/umo/match",
            json={"score": 0.85, "match": True}
        )

        result = client.umo.match(
            "01SOURCE12345678901234567890",
            "01CANDIDATE12345678901234567890"
        )

        assert isinstance(result, MatchResult)
        assert result.score == 0.85
        assert result.match is True
        assert result.source_ulid == "01SOURCE12345678901234567890"
        assert result.candidate_ulid == "01CANDIDATE12345678901234567890"

    def test_match_with_explain(
        self,
        client: MemoryClient,
        httpx_mock,
    ) -> None:
        """Test match with explanation."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.memoryintelligence.io/v1/umo/match",
            json={
                "score": 0.85,
                "match": True,
                "explain": {
                    "human": {"summary": "Strong match"},
                    "audit": {"semantic_score": 0.9}
                }
            }
        )

        result = client.umo.match(
            "01SOURCE12345678901234567890",
            "01CANDIDATE12345678901234567890",
            explain=True
        )

        assert result.explain is not None
        assert result.explain.human.summary == "Strong match"


class TestUMOExplain:
    """Tests for umo.explain() method."""

    def test_explain_happy_path(
        self,
        client: MemoryClient,
        httpx_mock,
    ) -> None:
        """Test successful explain returns Explanation."""
        from memoryintelligence._models import Explanation

        import re
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r"https://api\.memoryintelligence\.dev/v1/umo/explain/01ABC12345678901234567890.*"),
            json={
                "human": {"summary": "This is relevant", "key_reasons": ["Topic match"]},
                "audit": {"semantic_score": 0.88, "reproducible": True}
            }
        )

        result = client.umo.explain("01ABC12345678901234567890")

        assert isinstance(result, Explanation)
        assert result.human.summary == "This is relevant"
        assert result.audit.semantic_score == 0.88


class TestUMODelete:
    """Tests for umo.delete() method."""

    def test_delete_happy_path(
        self,
        client: MemoryClient,
        httpx_mock,
    ) -> None:
        """Test successful delete returns DeleteResult."""
        from memoryintelligence._models import DeleteResult

        httpx_mock.add_response(
            method="DELETE",
            url="https://api.memoryintelligence.io/v1/umo/delete",
            json={"deleted_count": 5, "audit_proof": {}}
        )

        result = client.umo.delete(user_ulid="01DEF12345678901234567890")

        assert isinstance(result, DeleteResult)
        assert result.deleted_count == 5
        assert result.user_ulid == "01DEF12345678901234567890"

    def test_delete_scope_isolation(
        self,
        client: MemoryClient,
        httpx_mock,
    ) -> None:
        """Test delete with specific scope."""
        httpx_mock.add_response(
            method="DELETE",
            url="https://api.memoryintelligence.io/v1/umo/delete",
            json={"deleted_count": 3}
        )

        client.umo.delete(
            user_ulid="01DEF12345678901234567890",
            scope=Scope.CLIENT,
            scope_id="01CLIENT12345678901234567890"
        )

        request = httpx_mock.get_request(url="https://api.memoryintelligence.io/v1/umo/delete")
        import json
        body = json.loads(request.content)
        assert body["scope"] == "client"
        assert body["scope_id"] == "01CLIENT12345678901234567890"


class TestForUser:
    """Tests for for_user() method."""

    def test_for_user_returns_scoped_client(
        self,
        api_key: str,
        httpx_mock,
    ) -> None:
        """Test for_user returns MemoryClient scoped to user."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.memoryintelligence.io/v1/license/validate",
            json={"status": "active", "tier": "professional"}
        )

        client = MemoryClient(api_key=api_key)
        user_client = client.for_user("01USER12345678901234567890")

        # Check user_ulid is set
        assert user_client._user_ulid == "01USER12345678901234567890"

        # Check transport is shared (not new connection)
        assert user_client._transport is client._transport

        # Check encryptor is shared
        assert user_client._encryptor is client._encryptor

        client.close()

    def test_scoped_client_uses_user_ulid(
        self,
        api_key: str,
        httpx_mock,
        mock_transport_response,
    ) -> None:
        """Test scoped client uses user_ulid without explicit arg."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.memoryintelligence.io/v1/license/validate",
            json={"status": "active", "tier": "professional"}
        )
        # Use the expected user_ulid in mock response
        httpx_mock.add_response(
            method="POST",
            url="https://api.memoryintelligence.io/v1/umo/process",
            json={**mock_transport_response, "user_ulid": "01DEFAULT12345678901234567890"}
        )

        client = MemoryClient(api_key=api_key)
        user_client = client.for_user("01DEFAULT12345678901234567890")

        # Should not raise - user_ulid comes from scoped client
        result = user_client.umo.process("Content")
        assert result.user_ulid == "01DEFAULT12345678901234567890"

        client.close()


class TestLicenseChecking:
    """Tests for license enforcement in umo methods."""

    def test_starter_tier_match_raises_license_error(
        self,
        api_key_starter: str,
        httpx_mock,
    ) -> None:
        """Test STARTER tier cannot use match()."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.memoryintelligence.io/v1/license/validate",
            json={"status": "active", "tier": "starter"}
        )

        client = MemoryClient(api_key=api_key_starter)

        with pytest.raises(LicenseError) as exc_info:
            client.umo.match("01A", "01B")

        assert "umo.match requires" in str(exc_info.value)
        assert "ENTERPRISE" in str(exc_info.value)

        client.close()

    def test_starter_tier_explain_raises_license_error(
        self,
        api_key_starter: str,
        httpx_mock,
    ) -> None:
        """Test STARTER tier cannot use explain()."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.memoryintelligence.io/v1/license/validate",
            json={"status": "active", "tier": "starter"}
        )

        client = MemoryClient(api_key=api_key_starter)

        with pytest.raises(LicenseError) as exc_info:
            client.umo.explain("01ABC")

        assert "umo.explain requires" in str(exc_info.value)

        client.close()
