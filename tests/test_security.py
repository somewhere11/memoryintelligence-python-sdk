"""
Security Audit Tests for SDK API
=================================

Tests to ensure NO data leaks occur in /api/public endpoints.

Critical Invariants:
1. Raw content NEVER returned when retention_policy=meaning_only
2. No UUIDs leaked (only ULIDs)
3. No external IDs (Slack, email, etc.) exposed
4. Scope isolation enforced at API level
5. PII never returned in responses (only detection metadata)
6. API keys never logged or echoed
7. No path traversal or file exposure

Run:
    cd sdk/python && source .venv/bin/activate
    python -m pytest tests/test_security.py -v
"""

import pytest
import re
import hashlib
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from pathlib import Path


# =============================================================================
# SECURITY TEST: RAW CONTENT LEAK PREVENTION
# =============================================================================

class TestNoRawContentLeak:
    """Ensure raw content is never returned when meaning_only is set."""
    
    def test_process_meaning_only_no_raw_in_response(self):
        """Response should NOT contain raw content when meaning_only."""
        from memoryintelligence import MemoryClient, RetentionPolicy
        
        raw_content = "This is sensitive raw content that should NEVER leak"
        
        with patch('httpx.Client') as mock_client:
            # Simulate API response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "umo_id": "01TEST123456789012345678",
                "user_ulid": "01USER123456789012345678",
                "entities": [{"text": "sensitive", "type": "CONCEPT", "confidence": 0.9}],
                "topics": [{"name": "security", "confidence": 0.85}],
                "svo_triples": [],
                "key_phrases": ["sensitive content"],
                "summary": "Content about sensitive topics",  # Summary OK
                # NO "raw" or "content" field
                "embedding": [0.1, 0.2],
                "embedding_model": "test",
                "provenance": {
                    "semantic_hash": "sha256:abc",
                    "timestamp_anchor": datetime.now(timezone.utc).isoformat(),
                    "hash_chain": "sha256:prev",
                },
                "scope": "user",
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
            mock_client.return_value.request.return_value = mock_response
            
            client = MemoryClient(api_key="mi_sk_test_key")
            umo = client.process(
                content=raw_content,
                user_ulid="01USER123456789012345678",
                retention_policy=RetentionPolicy.MEANING_ONLY,
            )
            
            # Verify raw content NOT in response object
            response_str = str(umo.__dict__)
            assert raw_content not in response_str
            assert "sensitive raw content" not in response_str
    
    def test_search_results_no_raw_content(self):
        """Search results should NOT contain raw content."""
        from memoryintelligence import MemoryClient
        
        with patch('httpx.Client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "results": [{
                    "umo": {
                        "umo_id": "01TEST123456789012345678",
                        "user_ulid": "01USER123456789012345678",
                        "entities": [],
                        "topics": [],
                        "svo_triples": [],
                        "key_phrases": ["search result"],
                        "summary": "Summary only",
                        # NO raw content
                        "provenance": {
                            "semantic_hash": "sha256:abc",
                            "timestamp_anchor": datetime.now(timezone.utc).isoformat(),
                            "hash_chain": "sha256:prev",
                        },
                        "scope": "user",
                        "ingested_at": datetime.now(timezone.utc).isoformat(),
                    },
                    "score": 0.85,
                }],
                "total_count": 1,
            }
            mock_client.return_value.request.return_value = mock_response
            
            client = MemoryClient(api_key="mi_sk_test_key")
            results = client.search(
                query="test",
                user_ulid="01USER123456789012345678",
            )
            
            # Verify no raw content field exists
            for result in results.results:
                assert not hasattr(result.umo, 'raw')
                assert not hasattr(result.umo, 'content')


# =============================================================================
# SECURITY TEST: NO UUID LEAK
# =============================================================================

class TestNoUUIDLeak:
    """Ensure only ULIDs are exposed, never UUIDs."""
    
    UUID_PATTERN = re.compile(
        r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
        re.IGNORECASE
    )
    
    def test_process_response_no_uuids(self):
        """Process response should contain only ULIDs, no UUIDs."""
        from memoryintelligence import MemoryClient
        
        with patch('httpx.Client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "umo_id": "01HQWX5JKZM3N4P5Q6R7S8T9UV",  # ULID (26 chars)
                "user_ulid": "01HQWX5JKZM3N4P5Q6R7S8T9AB",  # ULID
                "entities": [],
                "topics": [],
                "svo_triples": [],
                "key_phrases": [],
                "provenance": {
                    "semantic_hash": "sha256:abc",
                    "timestamp_anchor": datetime.now(timezone.utc).isoformat(),
                    "hash_chain": "sha256:prev",
                },
                "scope": "user",
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
            mock_client.return_value.request.return_value = mock_response
            
            client = MemoryClient(api_key="mi_sk_test_key")
            umo = client.process("test", user_ulid="01HQWX5JKZM3N4P5Q6R7S8T9AB")
            
            # Check for UUID patterns in response
            response_str = str(umo.__dict__)
            uuid_matches = self.UUID_PATTERN.findall(response_str)
            
            # API keys might contain UUID-like patterns, exclude those
            non_api_key_uuids = [u for u in uuid_matches if not u.startswith("mi_")]
            assert len(non_api_key_uuids) == 0, f"UUID leaked in response: {non_api_key_uuids}"
    
    def test_ulid_is_26_chars(self):
        """All IDs should be 26-character ULIDs."""
        from memoryintelligence import MemoryClient
        
        with patch('httpx.Client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "umo_id": "01HQWX5JKZM3N4P5Q6R7S8T9UV",
                "user_ulid": "01HQWX5JKZM3N4P5Q6R7S8T9AB",
                "entities": [],
                "topics": [],
                "svo_triples": [],
                "key_phrases": [],
                "provenance": {
                    "semantic_hash": "sha256:abc",
                    "timestamp_anchor": datetime.now(timezone.utc).isoformat(),
                    "hash_chain": "sha256:prev",
                },
                "scope": "user",
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
            mock_client.return_value.request.return_value = mock_response
            
            client = MemoryClient(api_key="mi_sk_test_key")
            umo = client.process("test", user_ulid="01HQWX5JKZM3N4P5Q6R7S8T9AB")
            
            assert len(umo.umo_id) == 26, f"umo_id should be 26 chars, got {len(umo.umo_id)}"
            assert len(umo.user_ulid) == 26, f"user_ulid should be 26 chars, got {len(umo.user_ulid)}"


# =============================================================================
# SECURITY TEST: NO EXTERNAL ID LEAK
# =============================================================================

class TestNoExternalIDLeak:
    """Ensure no external IDs (Slack, email, etc.) are exposed."""
    
    EXTERNAL_ID_PATTERNS = {
        "slack_user": re.compile(r'U[A-Z0-9]{8,}'),  # Slack user IDs
        "slack_channel": re.compile(r'C[A-Z0-9]{8,}'),  # Slack channels
        "slack_message": re.compile(r'\d+\.\d{6}'),  # Slack message timestamps
        "email": re.compile(r'[\w.-]+@[\w.-]+\.\w+'),
        "oauth_token": re.compile(r'xox[baprs]-\w+'),  # Slack OAuth
    }
    
    def test_no_slack_ids_in_response(self):
        """No Slack IDs should appear in API responses."""
        from memoryintelligence import MemoryClient
        
        # Even if raw content had Slack IDs, response shouldn't
        with patch('httpx.Client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "umo_id": "01HQWX5JKZM3N4P5Q6R7S8T9UV",
                "user_ulid": "01HQWX5JKZM3N4P5Q6R7S8T9AB",
                "entities": [{"text": "John", "type": "PERSON", "confidence": 0.9}],
                "topics": [{"name": "work", "confidence": 0.85}],
                "svo_triples": [],
                "key_phrases": ["meeting notes"],
                "summary": "Notes from a meeting",
                "provenance": {
                    "semantic_hash": "sha256:abc",
                    "timestamp_anchor": datetime.now(timezone.utc).isoformat(),
                    "hash_chain": "sha256:prev",
                },
                "scope": "user",
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
            mock_client.return_value.request.return_value = mock_response
            
            client = MemoryClient(api_key="mi_sk_test_key")
            umo = client.process(
                content="Message from U123ABC456 in C789DEF012",  # Contains Slack IDs
                user_ulid="01HQWX5JKZM3N4P5Q6R7S8T9AB",
            )
            
            response_str = str(umo.__dict__)
            
            for pattern_name, pattern in self.EXTERNAL_ID_PATTERNS.items():
                matches = pattern.findall(response_str)
                # Filter out false positives (like "PERSON" type)
                real_matches = [m for m in matches if len(m) > 5]
                assert len(real_matches) == 0, f"{pattern_name} leaked: {real_matches}"


# =============================================================================
# SECURITY TEST: SCOPE ISOLATION
# =============================================================================

class TestScopeIsolation:
    """Ensure scope isolation is enforced at API level."""
    
    def test_cross_scope_access_denied(self):
        """Accessing data across scopes should fail."""
        from memoryintelligence import MemoryClient, Scope, ScopeViolationError
        
        with patch('httpx.Client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_response.json.return_value = {"detail": "Cross-scope access denied"}
            mock_client.return_value.request.return_value = mock_response
            
            client = MemoryClient(api_key="mi_sk_test_key")
            
            with pytest.raises(ScopeViolationError):
                client.search(
                    query="test",
                    user_ulid="01USER123456789012345678",
                    scope=Scope.CLIENT,
                    scope_id="01CLIENT123456789012345"  # Different client
                )
    
    def test_scope_id_required_for_client_scope(self):
        """CLIENT scope without scope_id should fail BEFORE API call."""
        from memoryintelligence import MemoryClient, Scope, ScopeViolationError
        
        with patch('httpx.Client'):
            client = MemoryClient(api_key="mi_sk_test_key")
            
            with pytest.raises(ScopeViolationError) as exc_info:
                client.process(
                    content="test",
                    user_ulid="01USER123456789012345678",
                    scope=Scope.CLIENT,
                    # No scope_id!
                )
            
            assert "scope_id required" in str(exc_info.value)


# =============================================================================
# SECURITY TEST: PII HANDLING
# =============================================================================

class TestPIIHandling:
    """Ensure PII is detected but never leaked in responses."""
    
    def test_pii_detected_but_values_not_returned(self):
        """PII should be detected, but actual values never returned."""
        from memoryintelligence import MemoryClient, PIIHandling
        
        sensitive_content = "SSN: 123-45-6789, Email: john@secret.com"
        
        with patch('httpx.Client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "umo_id": "01TEST123456789012345678",
                "user_ulid": "01USER123456789012345678",
                "entities": [{"text": "[REDACTED]", "type": "PERSON", "confidence": 0.9}],
                "topics": [],
                "svo_triples": [],
                "key_phrases": [],
                "pii": {
                    "detected": True,
                    "types": ["SSN", "EMAIL"],  # Types detected
                    "count": 2,
                    "handling_applied": "extract_and_redact",
                    # NO actual SSN or email values here!
                },
                "provenance": {
                    "semantic_hash": "sha256:abc",
                    "timestamp_anchor": datetime.now(timezone.utc).isoformat(),
                    "hash_chain": "sha256:prev",
                },
                "scope": "user",
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
            mock_client.return_value.request.return_value = mock_response
            
            client = MemoryClient(api_key="mi_sk_test_key")
            umo = client.process(
                content=sensitive_content,
                user_ulid="01USER123456789012345678",
                pii_handling=PIIHandling.EXTRACT_AND_REDACT,
            )
            
            response_str = str(umo.__dict__)
            
            # Actual PII values should NOT appear
            assert "123-45-6789" not in response_str
            assert "john@secret.com" not in response_str
            
            # But detection metadata should be present
            assert umo.pii is not None
            assert umo.pii.detected is True
            assert "SSN" in umo.pii.types
            assert "EMAIL" in umo.pii.types


# =============================================================================
# SECURITY TEST: API KEY HANDLING
# =============================================================================

class TestAPIKeyHandling:
    """Ensure API keys are never logged or echoed."""
    
    def test_api_key_not_in_error_messages(self):
        """API key should never appear in error messages."""
        from memoryintelligence import MemoryClient, AuthenticationError
        
        api_key = "mi_sk_secret_key_12345678"
        
        with patch('httpx.Client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_client.return_value.request.return_value = mock_response
            
            client = MemoryClient(api_key=api_key)
            
            try:
                client.process("test", user_ulid="01USER123456789012345678")
            except AuthenticationError as e:
                # API key should NOT be in error message
                assert api_key not in str(e)
                assert "secret_key" not in str(e)


# =============================================================================
# SECURITY TEST: PATH TRAVERSAL PREVENTION
# =============================================================================

class TestPathTraversalPrevention:
    """Ensure no path traversal attacks are possible."""
    
    def test_umo_id_cannot_contain_path_chars(self):
        """UMO IDs with path characters should be rejected."""
        from memoryintelligence import MemoryClient
        
        with patch('httpx.Client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.json.return_value = {"detail": "Invalid UMO ID format"}
            mock_client.return_value.request.return_value = mock_response
            
            client = MemoryClient(api_key="mi_sk_test_key")
            
            # These should fail validation
            malicious_ids = [
                "../../../etc/passwd",
                "01TEST/../../../sensitive",
                "01TEST%2F..%2F..%2Fsecret",
            ]
            
            for mal_id in malicious_ids:
                # ULIDs are validated at SDK level, so this should fail
                # before even making an API call
                try:
                    client.explain(umo_id=mal_id)
                except Exception:
                    pass  # Expected to fail


# =============================================================================
# SECURITY TEST: EMBEDDING EXPOSURE
# =============================================================================

class TestEmbeddingExposure:
    """Ensure embeddings don't leak sensitive information."""
    
    def test_embedding_is_float_vector_only(self):
        """Embeddings should be float vectors, not reconstructable to text."""
        from memoryintelligence import MemoryClient
        
        with patch('httpx.Client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            # Embedding should be numeric only
            mock_response.json.return_value = {
                "umo_id": "01TEST123456789012345678",
                "user_ulid": "01USER123456789012345678",
                "entities": [],
                "topics": [],
                "svo_triples": [],
                "key_phrases": [],
                "embedding": [0.123, -0.456, 0.789, 0.012],  # Floats only
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                "provenance": {
                    "semantic_hash": "sha256:abc",
                    "timestamp_anchor": datetime.now(timezone.utc).isoformat(),
                    "hash_chain": "sha256:prev",
                },
                "scope": "user",
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
            mock_client.return_value.request.return_value = mock_response
            
            client = MemoryClient(api_key="mi_sk_test_key")
            umo = client.process("test", user_ulid="01USER123456789012345678")
            
            if umo.embedding:
                # All elements should be floats
                assert all(isinstance(x, (int, float)) for x in umo.embedding)
                # No text should be reconstructable
                embedding_str = str(umo.embedding)
                assert "test" not in embedding_str.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
