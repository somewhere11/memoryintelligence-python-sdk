"""Tests for license module."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from memoryintelligence._errors import LicenseError
from memoryintelligence._license import (
    AIR_GAPPED_GRACE_DAYS,
    CLOUD_GRACE_DAYS,
    CachedLicense,
    LicenseCache,
    LicenseManager,
    LicenseStatus,
    LicenseType,
)


class TestLicenseCache:
    """Tests for LicenseCache."""

    def test_save_and_load(self, tmp_path) -> None:
        """Test saving and loading license cache."""
        cache_file = tmp_path / "license_cache.json"
        cache = LicenseCache(cache_file=cache_file)

        cached = CachedLicense(
            license_key="TEST-KEY-123",
            status=LicenseStatus.ACTIVE,
            tier=LicenseType.PROFESSIONAL,
            expires_at=None,
            validated_at=datetime.now(timezone.utc),
            revoked=False,
            suspended=False,
        )

        cache.save(cached)
        loaded = cache.load()

        assert loaded is not None
        assert loaded.license_key == "TEST-KEY-123"
        assert loaded.tier == LicenseType.PROFESSIONAL
        assert loaded.status == LicenseStatus.ACTIVE

    def test_load_empty_cache(self, tmp_path) -> None:
        """Test loading non-existent cache returns None."""
        cache_file = tmp_path / "nonexistent.json"
        cache = LicenseCache(cache_file=cache_file)

        loaded = cache.load()
        assert loaded is None

    def test_is_stale_fresh_cache(self, tmp_path) -> None:
        """Test fresh cache is not stale."""
        cache_file = tmp_path / "license_cache.json"
        cache = LicenseCache(cache_file=cache_file)

        cached = CachedLicense(
            license_key="TEST",
            status=LicenseStatus.ACTIVE,
            tier=LicenseType.PROFESSIONAL,
            expires_at=None,
            validated_at=datetime.now(timezone.utc),
        )

        assert not cache.is_stale(cached, grace_hours=24)

    def test_is_stale_old_cache(self, tmp_path) -> None:
        """Test old cache is stale."""
        cache_file = tmp_path / "license_cache.json"
        cache = LicenseCache(cache_file=cache_file)

        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        cached = CachedLicense(
            license_key="TEST",
            status=LicenseStatus.ACTIVE,
            tier=LicenseType.PROFESSIONAL,
            expires_at=None,
            validated_at=old_time,
        )

        assert cache.is_stale(cached, grace_hours=24)

    def test_is_stale_none_cache(self) -> None:
        """Test None cache is stale."""
        cache = LicenseCache()
        assert cache.is_stale(None)

    def test_clear_cache(self, tmp_path) -> None:
        """Test clearing cache."""
        cache_file = tmp_path / "license_cache.json"
        cache = LicenseCache(cache_file=cache_file)

        cached = CachedLicense(
            license_key="TEST",
            status=LicenseStatus.ACTIVE,
            tier=LicenseType.PROFESSIONAL,
            expires_at=None,
            validated_at=datetime.now(timezone.utc),
        )

        cache.save(cached)
        assert cache_file.exists()

        cache.clear()
        assert not cache_file.exists()


class TestLicenseManagerValidation:
    """Tests for LicenseManager.validate_on_init()."""

    def test_valid_license_passes(self, tmp_path) -> None:
        """Test valid license passes validation."""
        mock_transport = Mock()
        mock_transport.request.return_value = {
            "status": "active",
            "tier": "professional",
            "revoked": False,
            "suspended": False
        }

        manager = LicenseManager(
            "mi_sk_test_key",
            mock_transport,
        )

        info = manager.validate_on_init()

        assert info.license_key == "mi_sk_test_key"
        assert info.tier == LicenseType.PROFESSIONAL
        assert info.status == LicenseStatus.ACTIVE

    def test_revoked_license_raises_error(self, tmp_path) -> None:
        """Test revoked license raises LicenseError."""
        mock_transport = Mock()
        mock_transport.request.return_value = {
            "status": "active",
            "tier": "professional",
            "revoked": True,
            "suspended": False
        }

        manager = LicenseManager(
            "mi_sk_test_key",
            mock_transport,
        )

        with pytest.raises(LicenseError) as exc_info:
            manager.validate_on_init()

        assert "revoked" in str(exc_info.value).lower()

    def test_suspended_license_raises_error(self, tmp_path) -> None:
        """Test suspended license raises LicenseError."""
        mock_transport = Mock()
        mock_transport.request.return_value = {
            "status": "active",
            "tier": "professional",
            "revoked": False,
            "suspended": True
        }

        manager = LicenseManager(
            "mi_sk_test_key",
            mock_transport,
        )

        with pytest.raises(LicenseError) as exc_info:
            manager.validate_on_init()

        assert "suspended" in str(exc_info.value).lower()

    def test_expired_within_grace_period_warns(self, tmp_path, caplog) -> None:
        """Test expired license within grace period logs warning."""
        import logging

        mock_transport = Mock()
        mock_transport.request.return_value = {
            "status": "expired",
            "tier": "professional",
            "revoked": False,
            "suspended": False,
            "expires_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        }

        manager = LicenseManager(
            "mi_sk_test_key",
            mock_transport,
        )

        with caplog.at_level(logging.WARNING):
            info = manager.validate_on_init()

        assert info.days_expired == 5
        assert "expired 5 days ago" in caplog.text
        assert "Renew at" in caplog.text

    def test_expired_beyond_grace_raises_error(self, tmp_path) -> None:
        """Test expired license beyond grace period raises error."""
        mock_transport = Mock()
        mock_transport.request.return_value = {
            "status": "expired",
            "tier": "professional",
            "revoked": False,
            "suspended": False,
            "expires_at": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
        }

        manager = LicenseManager(
            "mi_sk_test_key",
            mock_transport,
            grace_days=CLOUD_GRACE_DAYS,
        )

        with pytest.raises(LicenseError) as exc_info:
            manager.validate_on_init()

        assert "expired 20 days ago" in str(exc_info.value)
        assert "Renew at" in str(exc_info.value)

    def test_air_gapped_longer_grace(self, tmp_path) -> None:
        """Test air-gapped mode has longer grace period."""
        cache_file = tmp_path / "license_cache.json"
        cache = LicenseCache(cache_file=cache_file)

        # Pre-populate cache with expired license
        expired = CachedLicense(
            license_key="mi_sk_test_key",
            status=LicenseStatus.EXPIRED,
            tier=LicenseType.ENTERPRISE,
            expires_at=datetime.now(timezone.utc) - timedelta(days=20),
            validated_at=datetime.now(timezone.utc),
            revoked=False,
            suspended=False,
        )
        cache.save(expired)

        mock_transport = Mock()

        manager = LicenseManager(
            "mi_sk_test_key",
            mock_transport,
            air_gapped=True,
            grace_days=AIR_GAPPED_GRACE_DAYS,
        )
        manager.cache = cache

        # Should not raise (20 days < 30 day grace)
        info = manager.validate_on_init()
        assert info.days_expired == 20

    def test_uses_cached_result_if_fresh(self, tmp_path) -> None:
        """Test uses cache if fresh (less than 24 hours)."""
        cache_file = tmp_path / "license_cache.json"
        cache = LicenseCache(cache_file=cache_file)

        cached = CachedLicense(
            license_key="mi_sk_test_key",
            status=LicenseStatus.ACTIVE,
            tier=LicenseType.PROFESSIONAL,
            expires_at=None,
            validated_at=datetime.now(timezone.utc),  # Fresh
            revoked=False,
            suspended=False,
        )
        cache.save(cached)

        # Mock transport that would fail if called
        mock_transport = Mock()
        mock_transport.request.side_effect = Exception("Should not be called")

        manager = LicenseManager(
            "mi_sk_test_key",
            mock_transport,
            grace_days=CLOUD_GRACE_DAYS,
        )
        manager.cache = cache

        # Should use cache, not make API call
        info = manager.validate_on_init()
        assert info.tier == LicenseType.PROFESSIONAL


class TestLicenseFeatureGating:
    """Tests for license feature checking."""

    def test_check_feature_allows_valid_feature(self) -> None:
        """Test check_feature allows valid feature."""
        mock_transport = Mock()
        mock_transport.request.return_value = {
            "status": "active",
            "tier": "professional",
            "revoked": False,
            "suspended": False
        }

        manager = LicenseManager("key", mock_transport)
        manager.validate_on_init()

        # Should not raise
        manager.check_feature("umo.process")
        manager.check_feature("umo.search")

    def test_starter_tier_match_raises(self) -> None:
        """Test STARTER tier cannot use match."""
        mock_transport = Mock()
        mock_transport.request.return_value = {
            "status": "active",
            "tier": "starter",
            "revoked": False,
            "suspended": False
        }

        manager = LicenseManager("key", mock_transport)
        manager.validate_on_init()

        with pytest.raises(LicenseError) as exc_info:
            manager.check_feature("umo.match")

        assert "umo.match requires" in str(exc_info.value)
        assert "ENTERPRISE" in str(exc_info.value)

    def test_starter_tier_explain_raises(self) -> None:
        """Test STARTER tier cannot use explain."""
        mock_transport = Mock()
        mock_transport.request.return_value = {
            "status": "active",
            "tier": "starter",
            "revoked": False,
            "suspended": False
        }

        manager = LicenseManager("key", mock_transport)
        manager.validate_on_init()

        with pytest.raises(LicenseError) as exc_info:
            manager.check_feature("umo.explain")

        assert "umo.explain requires" in str(exc_info.value)

    def test_starter_tier_process_allowed(self) -> None:
        """Test STARTER tier can use process."""
        mock_transport = Mock()
        mock_transport.request.return_value = {
            "status": "active",
            "tier": "starter",
            "revoked": False,
            "suspended": False
        }

        manager = LicenseManager("key", mock_transport)
        manager.validate_on_init()

        # Should not raise
        manager.check_feature("umo.process")

    def test_enterprise_tier_edge_client_allowed(self) -> None:
        """Test ENTERPRISE tier can use edge_client."""
        mock_transport = Mock()
        mock_transport.request.return_value = {
            "status": "active",
            "tier": "enterprise",
            "revoked": False,
            "suspended": False
        }

        manager = LicenseManager("key", mock_transport)
        manager.validate_on_init()

        # Should not raise
        manager.check_feature("edge_client")

    def test_professional_tier_edge_client_raises(self) -> None:
        """Test PROFESSIONAL tier cannot use edge_client."""
        mock_transport = Mock()
        mock_transport.request.return_value = {
            "status": "active",
            "tier": "professional",
            "revoked": False,
            "suspended": False
        }

        manager = LicenseManager("key", mock_transport)
        manager.validate_on_init()

        with pytest.raises(LicenseError) as exc_info:
            manager.check_feature("edge_client")

        assert "ENTERPRISE" in str(exc_info.value)
