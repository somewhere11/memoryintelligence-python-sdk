"""Memory Intelligence SDK - HTTP transport.

Synchronous and asynchronous HTTP transport with retry logic.
This is the only module that touches httpx.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import httpx
from ulid import ULID

from ._errors import (
    ConnectionError,
    HTTP_STATUS_EXCEPTIONS,
    RateLimitError,
    ServerError,
    TimeoutError,
    get_exception_for_status,
)
from ._version import __version__

logger = logging.getLogger("memoryintelligence")


class _BaseTransport:
    """Base class with common transport logic."""

    # Status codes that trigger retry
    RETRY_STATUSES = {408, 429, 500, 502, 503, 504}
    # Status codes that do NOT retry
    NO_RETRY_STATUSES = {400, 401, 402, 403, 404, 409, 422}

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        device_id: str | None = None,
        actor_type: str | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.device_id = device_id
        self.actor_type = actor_type

    def _get_headers(self) -> dict[str, str]:
        """Get headers required for every request.

        Includes X-MI-Device-ID and X-MI-Actor-Type when set on the
        transport.  The server uses these for zero-friction provenance
        inference — if present they override the server's ambient signal
        chain (User-Agent, IP fingerprint, etc.).
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-MI-SDK-Version": __version__,
            "Content-Type": "application/json",
            "X-MI-Encrypted": "true",
            "Accept": "application/json",
        }
        if self.device_id:
            headers["X-MI-Device-ID"] = self.device_id
        if self.actor_type:
            headers["X-MI-Actor-Type"] = self.actor_type
        return headers

    def _generate_request_id(self) -> str:
        """Generate a fresh ULID for request tracking."""
        return str(ULID())

    def _calculate_backoff(self, attempt: int, retry_after: int | None = None) -> float:
        """
        Calculate backoff delay with exponential backoff and jitter.

        Args:
            attempt: Current retry attempt (0-indexed)
            retry_after: Optional Retry-After header value (seconds)

        Returns:
            Delay in seconds
        """
        if retry_after is not None and retry_after > 0:
            return retry_after

        # Exponential backoff: min(0.5 * 2^attempt, 30)
        delay = min(0.5 * (2 ** attempt), 30.0)
        # Add ±25% jitter
        jitter = delay * 0.25 * (2 * random.random() - 1)
        return delay + jitter

    def _should_retry(self, status_code: int) -> bool:
        """Determine if a request should be retried based on status code."""
        if status_code in self.NO_RETRY_STATUSES:
            return False
        if status_code in self.RETRY_STATUSES:
            return True
        # Default: don't retry unknown status codes
        return False

    def _raise_for_status(
        self,
        status_code: int,
        response_body: dict[str, Any] | None,
        request_id: str,
        retry_after: int | None = None,
    ) -> None:
        """
        Raise appropriate exception for HTTP status code.

        Args:
            status_code: HTTP status code
            response_body: Parsed JSON response body
            request_id: Request ID from X-MI-Request-ID header
            retry_after: Retry-After header value (for rate limiting)
        """
        if 200 <= status_code < 300:
            return

        exc_class = get_exception_for_status(status_code)
        message = f"HTTP {status_code}"

        # Extract error message from response body if available
        if response_body:
            if "error" in response_body:
                message = response_body["error"]
            elif "message" in response_body:
                message = response_body["message"]
            elif "detail" in response_body:
                message = response_body["detail"]

        # Build exception with appropriate attributes
        if exc_class == RateLimitError:
            raise RateLimitError(message, retry_after=retry_after or 60)
        elif exc_class == ServerError:
            raise ServerError(message, request_id=request_id)
        elif exc_class.__name__ == "ValidationError":
            field = response_body.get("field", "") if response_body else ""
            from ._errors import ValidationError
            raise ValidationError(message, field=field)
        elif exc_class.__name__ == "PIIViolationError":
            detected_types = response_body.get("detected_types", []) if response_body else []
            from ._errors import PIIViolationError
            raise PIIViolationError(message, detected_types=detected_types)
        else:
            raise exc_class(message)


class SyncTransport(_BaseTransport):
    """Synchronous HTTP transport."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        device_id: str | None = None,
        actor_type: str | None = None,
    ):
        super().__init__(api_key, base_url, timeout, max_retries, device_id, actor_type)
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self._get_headers(),
        )

    def request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Make HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path (without base URL)
            **kwargs: Additional arguments for httpx

        Returns:
            Parsed JSON response body

        Raises:
            Various MIError subclasses based on HTTP status
        """
        request_id = self._generate_request_id()
        headers = kwargs.pop("headers", {})
        headers["X-MI-Request-ID"] = request_id

        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.request(
                    method,
                    path,
                    headers=headers,
                    **kwargs,
                )

                # Get retry-after header if present
                retry_after = None
                if "retry-after" in response.headers:
                    try:
                        retry_after = int(response.headers["retry-after"])
                    except ValueError:
                        pass

                # Get request ID from response if server returned it
                response_request_id = response.headers.get("x-mi-request-id", request_id)

                # Check if we should retry
                if response.status_code in self.RETRY_STATUSES and attempt < self.max_retries:
                    if self._should_retry(response.status_code):
                        delay = self._calculate_backoff(attempt, retry_after)
                        logger.debug(
                            f"Retrying request (attempt {attempt + 1}/{self.max_retries}) "
                            f"after {delay:.1f}s - status {response.status_code}"
                        )
                        time.sleep(delay)
                        continue

                # Parse response body
                response_body = None
                try:
                    if response.content:
                        response_body = response.json()
                except Exception:
                    response_body = {"message": response.text} if response.text else None

                # Raise appropriate exception for error status codes
                self._raise_for_status(
                    response.status_code,
                    response_body,
                    response_request_id,
                    retry_after,
                )

                # Success - return response body
                return response_body or {}

            except httpx.TimeoutException as e:
                last_exception = TimeoutError(f"Request timed out: {e}")
                if attempt < self.max_retries:
                    delay = self._calculate_backoff(attempt)
                    logger.debug(
                        f"Retrying request (attempt {attempt + 1}/{self.max_retries}) "
                        f"after {delay:.1f}s - timeout"
                    )
                    time.sleep(delay)
                else:
                    raise last_exception

            except httpx.ConnectError as e:
                raise ConnectionError(f"Could not connect to API: {e}") from e

            except httpx.RequestError as e:
                last_exception = ConnectionError(f"Request failed: {e}")
                if attempt < self.max_retries:
                    delay = self._calculate_backoff(attempt)
                    logger.debug(
                        f"Retrying request (attempt {attempt + 1}/{self.max_retries}) "
                        f"after {delay:.1f}s - connection error"
                    )
                    time.sleep(delay)
                else:
                    raise last_exception

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        return {}

    def close(self) -> None:
        """Close transport connections."""
        self._client.close()


class AsyncTransport(_BaseTransport):
    """Asynchronous HTTP transport."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        device_id: str | None = None,
        actor_type: str | None = None,
    ):
        super().__init__(api_key, base_url, timeout, max_retries, device_id, actor_type)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self._get_headers(),
        )

    async def request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Make async HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path (without base URL)
            **kwargs: Additional arguments for httpx

        Returns:
            Parsed JSON response body

        Raises:
            Various MIError subclasses based on HTTP status
        """
        import asyncio

        request_id = self._generate_request_id()
        headers = kwargs.pop("headers", {})
        headers["X-MI-Request-ID"] = request_id

        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await self._client.request(
                    method,
                    path,
                    headers=headers,
                    **kwargs,
                )

                # Get retry-after header if present
                retry_after = None
                if "retry-after" in response.headers:
                    try:
                        retry_after = int(response.headers["retry-after"])
                    except ValueError:
                        pass

                # Get request ID from response if server returned it
                response_request_id = response.headers.get("x-mi-request-id", request_id)

                # Check if we should retry
                if response.status_code in self.RETRY_STATUSES and attempt < self.max_retries:
                    if self._should_retry(response.status_code):
                        delay = self._calculate_backoff(attempt, retry_after)
                        logger.debug(
                            f"Retrying request (attempt {attempt + 1}/{self.max_retries}) "
                            f"after {delay:.1f}s - status {response.status_code}"
                        )
                        await asyncio.sleep(delay)
                        continue

                # Parse response body
                response_body = None
                try:
                    if response.content:
                        response_body = response.json()
                except Exception:
                    response_body = {"message": response.text} if response.text else None

                # Raise appropriate exception for error status codes
                self._raise_for_status(
                    response.status_code,
                    response_body,
                    response_request_id,
                    retry_after,
                )

                # Success - return response body
                return response_body or {}

            except httpx.TimeoutException as e:
                last_exception = TimeoutError(f"Request timed out: {e}")
                if attempt < self.max_retries:
                    delay = self._calculate_backoff(attempt)
                    logger.debug(
                        f"Retrying request (attempt {attempt + 1}/{self.max_retries}) "
                        f"after {delay:.1f}s - timeout"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise last_exception

            except httpx.ConnectError as e:
                raise ConnectionError(f"Could not connect to API: {e}") from e

            except httpx.RequestError as e:
                last_exception = ConnectionError(f"Request failed: {e}")
                if attempt < self.max_retries:
                    delay = self._calculate_backoff(attempt)
                    logger.debug(
                        f"Retrying request (attempt {attempt + 1}/{self.max_retries}) "
                        f"after {delay:.1f}s - connection error"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise last_exception

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        return {}

    async def close(self) -> None:
        """Close transport connections."""
        await self._client.aclose()
