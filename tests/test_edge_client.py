"""Tests for EdgeClient with HIPAA and air-gapped modes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from memoryintelligence import ConfigurationError, EdgeClient, LicenseError
from memoryintelligence._license import AIR_GAPPED_GRACE_DAYS


# Valid test API key (must be at least 32 chars)
TEST_API_KEY = "mi_sk_test_" + "a" * 40


class TestEdgeClientInit:
    """Tests for EdgeClient initialization."""

    def test_endpoint_required(self):
        """Test endpoint is required for EdgeClient."""
        with pytest.raises(ConfigurationError) as exc_info:
            EdgeClient(endpoint="")

        assert "endpoint is required" in str(exc_info.value)

    def test_api_key_required_in_non_air_gapped_mode(self):
        """Test API key required when not air-gapped."""
        with pytest.raises(ConfigurationError) as exc_info:
            EdgeClient(
                endpoint="https://mi.internal.com",
                air_gapped=False
            )

        assert "API key required" in str(exc_info.value)

    def test_air_gapped_no_api_key_needed(self, httpx_mock):
        """Test air-gapped mode works without API key."""
        # Mock license endpoint at edge endpoint
        httpx_mock.add_response(
            method="POST",
            url="https://mi.internal.com/v1/license/validate",
            json={
                "status": "active",
                "tier": "enterprise",
                "revoked": False,
                "suspended": False
            }
        )

        # Should not raise - no API key needed in air-gapped mode
        client = EdgeClient(
            endpoint="https://mi.internal.com",
            air_gapped=True
        )
        assert client.air_gapped is True
        assert client._api_key is None
        client.close()

    def test_enterprise_license_required(self, httpx_mock):
        """Test EdgeClient requires ENTERPRISE license tier."""
        # Mock license endpoint returning PROFESSIONAL tier
        httpx_mock.add_response(
            method="POST",
            url="https://mi.internal.com/v1/license/validate",
            json={
                "status": "active",
                "tier": "professional",
                "revoked": False,
                "suspended": False
            }
        )

        with pytest.raises(LicenseError) as exc_info:
            EdgeClient(
                endpoint="https://mi.internal.com",
                api_key=TEST_API_KEY,
            )

        assert "ENTERPRISE" in str(exc_info.value)

    def test_hipaa_mode_stores_flag(self, httpx_mock):
        """Test hipaa_mode flag is stored."""
        httpx_mock.add_response(
            method="POST",
            url="https://mi.internal.com/v1/license/validate",
            json={
                "status": "active",
                "tier": "enterprise",
                "revoked": False,
                "suspended": False
            }
        )

        client = EdgeClient(
            endpoint="https://mi.internal.com",
            api_key=TEST_API_KEY,
            hipaa_mode=True
        )

        assert client.hipaa_mode is True
        client.close()


class TestEdgeClientLicenseGating:
    """Tests for ENTERPRISE feature gating in EdgeClient."""

    def test_aggregate_requires_enterprise(self, httpx_mock):
        """Test aggregate() requires ENTERPRISE license."""
        httpx_mock.add_response(
            method="POST",
            url="https://mi.internal.com/v1/license/validate",
            json={
                "status": "active",
                "tier": "enterprise",
                "revoked": False,
                "suspended": False
            }
        )

        client = EdgeClient(
            endpoint="https://mi.internal.com",
            api_key=TEST_API_KEY,
        )

        # Now mock the aggregate endpoint
        httpx_mock.add_response(
            method="POST",
            url="https://mi.internal.com/v1/aggregate",
            json={
                "results": [{"count": 100, "metric": "avg_score", "value": 0.85}],
                "privacy_guarantee": "k-anonymity"
            }
        )

        result = client.aggregate("What is the average score?")

        assert "results" in result
        assert "privacy_guarantee" in result
        client.close()

    def test_verify_phi_handling_requires_enterprise(self, httpx_mock):
        """Test verify_phi_handling() requires ENTERPRISE license."""
        httpx_mock.add_response(
            method="POST",
            url="https://mi.internal.com/v1/license/validate",
            json={
                "status": "active",
                "tier": "enterprise",
                "revoked": False,
                "suspended": False
            }
        )

        client = EdgeClient(
            endpoint="https://mi.internal.com",
            api_key=TEST_API_KEY,
        )

        # Mock the PHI verify endpoint
        httpx_mock.add_response(
            method="GET",
            url="https://mi.internal.com/v1/phi/verify/01ABC12345678901234567890",
            json={
                "umo_id": "01ABC12345678901234567890",
                "phi_detected": True,
                "phi_types": ["PATIENT_NAME", "MEDICAL_RECORD_NUMBER"],
                "handling_applied": "HASH",
                "audit_proof": "sha256:abc123"
            }
        )

        result = client.verify_phi_handling("01ABC12345678901234567890")

        assert result["phi_detected"] is True
        assert result["handling_applied"] == "HASH"
        client.close()

    def test_export_audit_log_requires_enterprise(self, httpx_mock):
        """Test export_audit_log() requires ENTERPRISE license."""
        httpx_mock.add_response(
            method="POST",
            url="https://mi.internal.com/v1/license/validate",
            json={
                "status": "active",
                "tier": "enterprise",
                "revoked": False,
                "suspended": False
            }
        )

        client = EdgeClient(
            endpoint="https://mi.internal.com",
            api_key=TEST_API_KEY,
        )

        # Mock the audit export endpoint
        httpx_mock.add_response(
            method="POST",
            url="https://mi.internal.com/v1/audit/export",
            json={
                "events": [
                    {"timestamp": "2024-01-01T00:00:00Z", "operation": "process", "user_ulid": "01USER123"}
                ],
                "total_events": 1
            }
        )

        result = client.export_audit_log(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
        )

        assert "events" in result
        client.close()


class TestEdgeClientHipaaMode:
    """Tests for HIPAA mode enforcement."""

    def test_hipaa_mode_enforces_pii_hash(self, httpx_mock, caplog):
        """Test HIPAA mode overrides pii_handling to HASH."""
        import logging

        httpx_mock.add_response(
            method="POST",
            url="https://mi.internal.com/v1/license/validate",
            json={
                "status": "active",
                "tier": "enterprise",
                "revoked": False,
                "suspended": False
            }
        )

        client = EdgeClient(
            endpoint="https://mi.internal.com",
            api_key=TEST_API_KEY,
            hipaa_mode=True
        )

        # Mock the process endpoint to capture the request
        httpx_mock.add_response(
            method="POST",
            url="https://mi.internal.com/v1/umo/process",
            json={
                "umo_id": "01ABC12345678901234567890",
                "user_ulid": "01USER12345678901234567890",
                "entities": [],
                "topics": [],
                "svo_triples": [],
                "key_phrases": [],
                "summary": "Test",
                "sentiment_label": "neutral",
                "sentiment_score": 0.5,
                "validation_status": "validated",
                "scope": "user",
                "scope_id": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "recency_score": 1.0,
                "quality_score": 0.9,
                "provenance": {
                    "semantic_hash": "sha256:abc",
                    "timestamp_anchor": datetime.now(timezone.utc).isoformat(),
                    "hash_chain": "sha256:prev",
                    "lineage": [],
                    "model_version": "v2.0.0"
                },
                "pii": {
                    "detected": False,
                    "types": [],
                    "count": 0,
                    "handling_applied": "hash"
                }
            }
        )

        with caplog.at_level(logging.DEBUG):
            client.umo.process(
                "Test content",
                user_ulid="01USER12345678901234567890",
                pii_handling="extract_and_redact"  # This should be overridden
            )

        # Check the debug log about overriding
        assert "HIPAA mode" in caplog.text
        assert "HASH" in caplog.text

        client.close()

    def test_hipaa_mode_enforces_provenance_audit(self, httpx_mock, caplog):
        """Test HIPAA mode overrides provenance_mode to AUDIT."""
        import logging

        httpx_mock.add_response(
            method="POST",
            url="https://mi.internal.com/v1/license/validate",
            json={
                "status": "active",
                "tier": "enterprise",
                "revoked": False,
                "suspended": False
            }
        )

        client = EdgeClient(
            endpoint="https://mi.internal.com",
            api_key=TEST_API_KEY,
            hipaa_mode=True
        )

        httpx_mock.add_response(
            method="POST",
            url="https://mi.internal.com/v1/umo/process",
            json={
                "umo_id": "01ABC12345678901234567890",
                "user_ulid": "01USER12345678901234567890",
                "entities": [],
                "topics": [],
                "svo_triples": [],
                "key_phrases": [],
                "summary": "Test",
                "sentiment_label": "neutral",
                "sentiment_score": 0.5,
                "validation_status": "validated",
                "scope": "user",
                "scope_id": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "recency_score": 1.0,
                "quality_score": 0.9,
                "provenance": {
                    "semantic_hash": "sha256:abc",
                    "timestamp_anchor": datetime.now(timezone.utc).isoformat(),
                    "hash_chain": "sha256:prev",
                    "lineage": [],
                    "model_version": "v2.0.0"
                },
                "pii": {
                    "detected": False,
                    "types": [],
                    "count": 0,
                    "handling_applied": "hash"
                }
            }
        )

        with caplog.at_level(logging.DEBUG):
            client.umo.process(
                "Test content",
                user_ulid="01USER12345678901234567890",
                provenance_mode="standard"  # This should be overridden
            )

        # Check the debug log about overriding
        assert "AUDIT" in caplog.text

        client.close()


class TestEdgeClientAirGapped:
    """Tests for air-gapped mode."""

    def test_air_gapped_disables_metering(self, httpx_mock):
        """Test air-gapped mode disables metering."""
        httpx_mock.add_response(
            method="POST",
            url="https://mi.internal.com/v1/license/validate",
            json={
                "status": "active",
                "tier": "enterprise",
                "revoked": False,
                "suspended": False
            }
        )

        client = EdgeClient(
            endpoint="https://mi.internal.com",
            air_gapped=True,
            metering_enabled=True  # Even if enabled, air-gapped overrides
        )

        # Metering should be disabled in air-gapped mode
        assert client.metering_enabled is False
        assert client._metering_client is None

        client.close()

    def test_air_gapped_uses_30_day_grace(self, httpx_mock):
        """Test air-gapped mode uses 30-day grace period."""
        httpx_mock.add_response(
            method="POST",
            url="https://mi.internal.com/v1/license/validate",
            json={
                "status": "expired",
                "tier": "enterprise",
                "revoked": False,
                "suspended": False,
                "expires_at": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
            }
        )

        # Should not raise - 20 days < 30 day grace period
        client = EdgeClient(
            endpoint="https://mi.internal.com",
            air_gapped=True
        )

        assert client._license.grace_days == AIR_GAPPED_GRACE_DAYS
        assert AIR_GAPPED_GRACE_DAYS == 30

        client.close()

    def test_air_gapped_beyond_grace_raises_error(self, tmp_path):
        """Test air-gapped mode raises error beyond 30-day grace."""
        from memoryintelligence._license import CachedLicense, LicenseCache, LicenseStatus, LicenseType

        # Pre-populate cache with expired license (35 days ago)
        cache_file = tmp_path / "license_cache.json"
        cache = LicenseCache(cache_file=cache_file)
        expired = CachedLicense(
            license_key="air-gapped",
            status=LicenseStatus.EXPIRED,
            tier=LicenseType.ENTERPRISE,
            expires_at=datetime.now(timezone.utc) - timedelta(days=35),
            validated_at=datetime.now(timezone.utc),
            revoked=False,
            suspended=False,
        )
        cache.save(expired)

        with pytest.raises(LicenseError) as exc_info:
            client = EdgeClient(
                endpoint="https://mi.internal.com",
                air_gapped=True
            )
            client.cache = cache
            # Force re-validation
            client._license.cache = cache
            client._license.validate_on_init()

        assert "expired" in str(exc_info.value).lower()


class TestEdgeClientAggregate:
    """Tests for aggregate() method."""

    def test_aggregate_with_privacy_params(self, httpx_mock):
        """Test aggregate with k-anonymity threshold."""
        httpx_mock.add_response(
            method="POST",
            url="https://mi.internal.com/v1/license/validate",
            json={
                "status": "active",
                "tier": "enterprise",
                "revoked": False,
                "suspended": False
            }
        )

        client = EdgeClient(
            endpoint="https://mi.internal.com",
            api_key=TEST_API_KEY,
        )

        httpx_mock.add_response(
            method="POST",
            url="https://mi.internal.com/v1/aggregate",
            json={
                "results": [{"count": 50, "metric": "avg_score", "value": 0.85}],
                "minimum_cohort_size": 50,
                "privacy_guarantee": "k-anonymity"
            }
        )

        result = client.aggregate(
            "What is the average score?",
            minimum_cohort_size=50,
            return_format="statistics_only"
        )

        assert result["minimum_cohort_size"] == 50
        assert result["privacy_guarantee"] == "k-anonymity"
        client.close()

    def test_aggregate_sends_hipaa_flag(self, httpx_mock):
        """Test aggregate sends hipaa_mode flag."""
        httpx_mock.add_response(
            method="POST",
            url="https://mi.internal.com/v1/license/validate",
            json={
                "status": "active",
                "tier": "enterprise",
                "revoked": False,
                "suspended": False
            }
        )

        client = EdgeClient(
            endpoint="https://mi.internal.com",
            api_key=TEST_API_KEY,
            hipaa_mode=True
        )

        httpx_mock.add_response(
            method="POST",
            url="https://mi.internal.com/v1/aggregate",
            json={"results": []}
        )

        client.aggregate("Test query")

        # Verify request includes hipaa_mode
        request = httpx_mock.get_request(url="https://mi.internal.com/v1/aggregate")
        import json
        body = json.loads(request.content)
        assert body["hipaa_mode"] is True

        client.close()


class TestEdgeClientMetering:
    """Tests for metering functionality."""

    def test_metering_report_non_blocking(self, httpx_mock):
        """Test metering failures don't block processing."""
        httpx_mock.add_response(
            method="POST",
            url="https://mi.internal.com/v1/license/validate",
            json={
                "status": "active",
                "tier": "enterprise",
                "revoked": False,
                "suspended": False
            }
        )

        client = EdgeClient(
            endpoint="https://mi.internal.com",
            api_key=TEST_API_KEY,
            metering_enabled=True
        )

        # Mock aggregate endpoint
        httpx_mock.add_response(
            method="POST",
            url="https://mi.internal.com/v1/aggregate",
            json={"results": []}
        )

        # Mock metering endpoint to fail
        httpx_mock.add_exception(
            Exception("Metering service unavailable"),
            url="https://api.memoryintelligence.io/v1/metering/report"
        )

        # Should not raise despite metering failure
        result = client.aggregate("Test query")
        assert "results" in result

        client.close()
