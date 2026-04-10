"""Tests for HTTP status code to exception mapping."""

from __future__ import annotations

import pytest

from memoryintelligence._errors import (
    HTTP_STATUS_EXCEPTIONS,
    AuthenticationError,
    ConflictError,
    ConnectionError,
    EncryptionError,
    LicenseError,
    NotFoundError,
    PaymentRequiredError,
    PIIViolationError,
    PermissionError,
    RateLimitError,
    ServerError,
    TimeoutError,
    ValidationError,
    get_exception_for_status,
)


class TestHTTPStatusExceptions:
    """Tests for HTTP_STATUS_EXCEPTIONS mapping."""

    def test_all_expected_statuses_mapped(self) -> None:
        """Test all expected HTTP statuses have exception mappings."""
        expected_mappings = {
            400: ValidationError,
            401: AuthenticationError,
            402: PaymentRequiredError,
            403: PermissionError,
            404: NotFoundError,
            409: ConflictError,
            422: ValidationError,
            429: RateLimitError,
            451: PIIViolationError,
            500: ServerError,
            502: ServerError,
            503: ServerError,
            504: ServerError,
        }

        for status, expected_class in expected_mappings.items():
            assert status in HTTP_STATUS_EXCEPTIONS
            assert HTTP_STATUS_EXCEPTIONS[status] == expected_class

    def test_unknown_status_returns_server_error(self) -> None:
        """Test unknown status codes map to ServerError."""
        # Status codes not in the mapping should default to ServerError
        unknown_statuses = [418, 501, 505, 599]
        for status in unknown_statuses:
            exc_class = get_exception_for_status(status)
            assert exc_class == ServerError


class TestGetExceptionForStatus:
    """Tests for get_exception_for_status function."""

    def test_400_returns_validation_error(self) -> None:
        """Test 400 maps to ValidationError."""
        assert get_exception_for_status(400) == ValidationError

    def test_401_returns_authentication_error(self) -> None:
        """Test 401 maps to AuthenticationError."""
        assert get_exception_for_status(401) == AuthenticationError

    def test_402_returns_payment_error(self) -> None:
        """Test 402 maps to PaymentRequiredError."""
        assert get_exception_for_status(402) == PaymentRequiredError

    def test_403_returns_permission_error(self) -> None:
        """Test 403 maps to PermissionError."""
        assert get_exception_for_status(403) == PermissionError

    def test_404_returns_not_found_error(self) -> None:
        """Test 404 maps to NotFoundError."""
        assert get_exception_for_status(404) == NotFoundError

    def test_409_returns_conflict_error(self) -> None:
        """Test 409 maps to ConflictError."""
        assert get_exception_for_status(409) == ConflictError

    def test_422_returns_validation_error(self) -> None:
        """Test 422 maps to ValidationError."""
        assert get_exception_for_status(422) == ValidationError

    def test_429_returns_rate_limit_error(self) -> None:
        """Test 429 maps to RateLimitError."""
        assert get_exception_for_status(429) == RateLimitError

    def test_451_returns_pii_violation_error(self) -> None:
        """Test 451 maps to PIIViolationError."""
        assert get_exception_for_status(451) == PIIViolationError

    def test_500_returns_server_error(self) -> None:
        """Test 500 maps to ServerError."""
        assert get_exception_for_status(500) == ServerError

    def test_502_returns_server_error(self) -> None:
        """Test 502 maps to ServerError."""
        assert get_exception_for_status(502) == ServerError

    def test_503_returns_server_error(self) -> None:
        """Test 503 maps to ServerError."""
        assert get_exception_for_status(503) == ServerError

    def test_504_returns_server_error(self) -> None:
        """Test 504 maps to ServerError."""
        assert get_exception_for_status(504) == ServerError


class TestExceptionClasses:
    """Tests for individual exception classes."""

    def test_base_mi_error(self) -> None:
        """Test MIError base class."""
        from memoryintelligence._errors import MIError

        err = MIError("Test error")
        assert str(err) == "Test error"
        assert err.code == "mi_error"

    def test_configuration_error(self) -> None:
        """Test ConfigurationError has correct code."""
        from memoryintelligence._errors import ConfigurationError

        err = ConfigurationError("Missing config")
        assert err.code == "configuration_error"

    def test_validation_error_with_field(self) -> None:
        """Test ValidationError with field attribute."""
        err = ValidationError("Invalid value", field="email")
        assert err.code == "validation_error"
        assert err.field == "email"
        assert str(err) == "Invalid value"

    def test_validation_error_without_field(self) -> None:
        """Test ValidationError without field attribute."""
        err = ValidationError("Invalid request")
        assert err.field == ""

    def test_authentication_error(self) -> None:
        """Test AuthenticationError."""
        err = AuthenticationError("Invalid API key")
        assert err.code == "authentication_error"

    def test_permission_error(self) -> None:
        """Test PermissionError."""
        err = PermissionError("Access denied")
        assert err.code == "permission_error"

    def test_not_found_error(self) -> None:
        """Test NotFoundError."""
        err = NotFoundError("UMO not found")
        assert err.code == "not_found"

    def test_rate_limit_error_with_retry_after(self) -> None:
        """Test RateLimitError with retry_after."""
        err = RateLimitError("Rate limit exceeded", retry_after=60)
        assert err.code == "rate_limit"
        assert err.retry_after == 60

    def test_rate_limit_error_default_retry(self) -> None:
        """Test RateLimitError default retry_after."""
        err = RateLimitError("Rate limit exceeded")
        assert err.retry_after == 60

    def test_server_error_with_request_id(self) -> None:
        """Test ServerError with request_id."""
        err = ServerError("Internal error", request_id="req_123")
        assert err.code == "server_error"
        assert err.request_id == "req_123"

    def test_server_error_without_request_id(self) -> None:
        """Test ServerError without request_id."""
        err = ServerError("Internal error")
        assert err.request_id == ""

    def test_pii_violation_error_with_detected_types(self) -> None:
        """Test PIIViolationError with detected_types."""
        err = PIIViolationError(
            "PII detected in request",
            detected_types=["PATIENT_NAME", "SSN"]
        )
        assert err.code == "pii_violation"
        assert err.detected_types == ["PATIENT_NAME", "SSN"]

    def test_pii_violation_error_default_types(self) -> None:
        """Test PIIViolationError default detected_types."""
        err = PIIViolationError("PII detected")
        assert err.detected_types == []

    def test_conflict_error(self) -> None:
        """Test ConflictError."""
        err = ConflictError("UMO already exists")
        assert err.code == "conflict"

    def test_payment_required_error(self) -> None:
        """Test PaymentRequiredError."""
        err = PaymentRequiredError("License required")
        assert err.code == "payment_required"

    def test_license_error_with_defaults(self) -> None:
        """Test LicenseError with default attributes."""
        err = LicenseError("License expired")
        assert err.code == "license_error"
        assert err.days_expired == 0
        assert err.renew_url == "https://memoryintelligence.io/billing"

    def test_license_error_with_custom_values(self) -> None:
        """Test LicenseError with custom values."""
        err = LicenseError(
            "License expired 10 days ago",
            days_expired=10,
            renew_url="https://custom.url/renew"
        )
        assert err.days_expired == 10
        assert err.renew_url == "https://custom.url/renew"

    def test_encryption_error(self) -> None:
        """Test EncryptionError."""
        err = EncryptionError("Decryption failed")
        assert err.code == "encryption_error"

    def test_timeout_error(self) -> None:
        """Test TimeoutError."""
        err = TimeoutError("Request timed out")
        assert err.code == "timeout"

    def test_connection_error(self) -> None:
        """Test ConnectionError."""
        err = ConnectionError("Could not connect")
        assert err.code == "connection_error"


class TestHTTPTransportExceptionMapping:
    """Tests for HTTP transport exception mapping via httpx mock."""

    def test_400_raises_validation_error(self, httpx_mock) -> None:
        """Test HTTP 400 raises ValidationError."""
        from memoryintelligence._http import SyncTransport

        httpx_mock.add_response(
            method="GET",
            url="https://api.test.com/v1/test",
            status_code=400,
            json={"error": "Invalid request", "field": "user_id"}
        )

        transport = SyncTransport(
            api_key="test_key",
            base_url="https://api.test.com",
            max_retries=0
        )

        with pytest.raises(ValidationError) as exc_info:
            transport.request("GET", "/v1/test")

        assert "Invalid request" in str(exc_info.value)
        transport.close()

    def test_401_raises_authentication_error(self, httpx_mock) -> None:
        """Test HTTP 401 raises AuthenticationError."""
        from memoryintelligence._http import SyncTransport

        httpx_mock.add_response(
            method="GET",
            url="https://api.test.com/v1/test",
            status_code=401,
            json={"error": "Invalid API key"}
        )

        transport = SyncTransport(
            api_key="test_key",
            base_url="https://api.test.com",
            max_retries=0
        )

        with pytest.raises(AuthenticationError) as exc_info:
            transport.request("GET", "/v1/test")

        assert "Invalid API key" in str(exc_info.value)
        transport.close()

    def test_429_raises_rate_limit_error_with_retry_after(self, httpx_mock) -> None:
        """Test HTTP 429 raises RateLimitError with retry_after."""
        from memoryintelligence._http import SyncTransport

        httpx_mock.add_response(
            method="GET",
            url="https://api.test.com/v1/test",
            status_code=429,
            json={"error": "Rate limit exceeded"},
            headers={"retry-after": "120"}
        )

        transport = SyncTransport(
            api_key="test_key",
            base_url="https://api.test.com",
            max_retries=0
        )

        with pytest.raises(RateLimitError) as exc_info:
            transport.request("GET", "/v1/test")

        assert exc_info.value.retry_after == 120
        transport.close()

    def test_500_raises_server_error_with_request_id(self, httpx_mock) -> None:
        """Test HTTP 500 raises ServerError with request_id."""
        from memoryintelligence._http import SyncTransport

        httpx_mock.add_response(
            method="GET",
            url="https://api.test.com/v1/test",
            status_code=500,
            json={"error": "Internal server error"},
            headers={"x-mi-request-id": "req_abc123"}
        )

        transport = SyncTransport(
            api_key="test_key",
            base_url="https://api.test.com",
            max_retries=0
        )

        with pytest.raises(ServerError) as exc_info:
            transport.request("GET", "/v1/test")

        assert exc_info.value.request_id == "req_abc123"
        transport.close()

    def test_451_raises_pii_violation_error(self, httpx_mock) -> None:
        """Test HTTP 451 raises PIIViolationError."""
        from memoryintelligence._http import SyncTransport

        httpx_mock.add_response(
            method="POST",
            url="https://api.test.com/v1/test",
            status_code=451,
            json={
                "error": "PII detected in request",
                "detected_types": ["PATIENT_NAME", "SSN"]
            }
        )

        transport = SyncTransport(
            api_key="test_key",
            base_url="https://api.test.com",
            max_retries=0
        )

        with pytest.raises(PIIViolationError) as exc_info:
            transport.request("POST", "/v1/test")

        assert exc_info.value.detected_types == ["PATIENT_NAME", "SSN"]
        transport.close()

    def test_error_message_from_detail_field(self, httpx_mock) -> None:
        """Test error message extracted from 'detail' field."""
        from memoryintelligence._http import SyncTransport

        httpx_mock.add_response(
            method="GET",
            url="https://api.test.com/v1/test",
            status_code=404,
            json={"detail": "UMO not found"}
        )

        transport = SyncTransport(
            api_key="test_key",
            base_url="https://api.test.com",
            max_retries=0
        )

        with pytest.raises(NotFoundError) as exc_info:
            transport.request("GET", "/v1/test")

        assert "UMO not found" in str(exc_info.value)
        transport.close()

    def test_error_message_from_message_field(self, httpx_mock) -> None:
        """Test error message extracted from 'message' field."""
        from memoryintelligence._http import SyncTransport

        httpx_mock.add_response(
            method="GET",
            url="https://api.test.com/v1/test",
            status_code=403,
            json={"message": "Access denied"}
        )

        transport = SyncTransport(
            api_key="test_key",
            base_url="https://api.test.com",
            max_retries=0
        )

        with pytest.raises(PermissionError) as exc_info:
            transport.request("GET", "/v1/test")

        assert "Access denied" in str(exc_info.value)
        transport.close()

    def test_plain_text_error_response(self, httpx_mock) -> None:
        """Test handling of plain text error responses."""
        from memoryintelligence._http import SyncTransport

        httpx_mock.add_response(
            method="GET",
            url="https://api.test.com/v1/test",
            status_code=500,
            text="Internal Server Error",
            headers={"content-type": "text/plain"}
        )

        transport = SyncTransport(
            api_key="test_key",
            base_url="https://api.test.com",
            max_retries=0
        )

        with pytest.raises(ServerError) as exc_info:
            transport.request("GET", "/v1/test")

        # Should still raise, message may vary based on parsing
        assert "Internal Server Error" in str(exc_info.value) or "HTTP 500" in str(exc_info.value)
        transport.close()
