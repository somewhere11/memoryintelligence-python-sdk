"""Memory Intelligence SDK - Edge Client.

On-premises / VPC deployment for regulated industries.
Data never leaves your infrastructure—only metering crosses the network.

Problem Solved: Proprietary Data Paralysis
    - HIPAA: Clinical notes processed locally
    - Legal: Attorney-client privileged documents
    - Finance: Trading data, internal communications
    - Competitive: Trade secrets, internal strategy

Usage:
    from memoryintelligence import EdgeClient

    # Connect to your on-prem MI container
    mi = EdgeClient(
        endpoint="https://mi.internal.yourcompany.com",
        api_key="mi_sk_...",  # For metering only
        hipaa_mode=True
    )

    # Process locally—data never leaves
    umo = mi.umo.process(clinical_note, patient_ulid="01ABC...")

Author: Memory Intelligence Team
Version: 2.0.0
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ._client import MemoryClient, UMONamespace
from ._crypto import SDKEncryptor
from ._errors import ConfigurationError, LicenseError
from ._http import SyncTransport
from ._license import AIR_GAPPED_GRACE_DAYS, LicenseManager, LicenseType
from ._models import (
    PIIHandling,
    ProvenanceMode,
    RetentionPolicy,
    Scope,
)

if TYPE_CHECKING:
    from ._models import DeleteResult, Explanation, MatchResult, MeaningObject, SearchResponse

logger = logging.getLogger("memoryintelligence")


class EdgeUMONamespace(UMONamespace):
    """
    UMONamespace for EdgeClient with HIPAA enforcement.
    Overrides process() to enforce pii_handling=HASH and provenance_mode=AUDIT.
    """

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
        source: str = "edge",
        metadata: dict | None = None,
    ) -> MeaningObject:
        """
        Process content with HIPAA enforcement.

        In HIPAA mode:
            - pii_handling is always HASH (non-negotiable)
            - provenance_mode is always AUDIT (non-negotiable)
        """
        edge_client: EdgeClient = self._client  # type: ignore

        # HIPAA enforcement: override settings
        if edge_client.hipaa_mode:
            if pii_handling != PIIHandling.HASH:
                logger.debug(
                    f"HIPAA mode: overriding pii_handling from {pii_handling} to HASH"
                )
            if provenance_mode != ProvenanceMode.AUDIT:
                logger.debug(
                    f"HIPAA mode: overriding provenance_mode from {provenance_mode} to AUDIT"
                )
            pii_handling = PIIHandling.HASH
            provenance_mode = ProvenanceMode.AUDIT

        # Call parent implementation
        return super().process(
            content=content,
            user_ulid=user_ulid,
            retention_policy=retention_policy,
            pii_handling=pii_handling,
            provenance_mode=provenance_mode,
            scope=scope,
            scope_id=scope_id,
            source=source,
            metadata=metadata,
        )


class EdgeClient(MemoryClient):
    """
    Edge deployment client for regulated industries.

    All processing happens in your infrastructure.
    Only metering/licensing data crosses the network (optional).

    Key Features:
        - HIPAA mode: Enhanced PHI detection, audit logging
        - Air-gapped mode: No network calls at all
        - Federated aggregation: Query across deployments without sharing data

    Args:
        endpoint: Your internal MI container endpoint (required)
        api_key: MI API key (for metering, can be disabled)
        hipaa_mode: Enable HIPAA-compliant processing (non-negotiable settings)
        air_gapped: Disable all external network calls
        metering_enabled: Whether to report usage to MI cloud
        timeout: Request timeout in seconds
        encryption_key: Custom encryption key (base64-encoded)

    Raises:
        LicenseError: If license tier is not ENTERPRISE
        ConfigurationError: If endpoint not provided

    Example:
        # Standard edge deployment with HIPAA
        mi = EdgeClient(
            endpoint="https://mi.internal.yourcompany.com",
            api_key="mi_sk_...",
            hipaa_mode=True
        )

        # Air-gapped (no external calls)
        mi = EdgeClient(
            endpoint="https://mi.internal.yourcompany.com",
            air_gapped=True
        )
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str | None = None,
        hipaa_mode: bool = False,
        air_gapped: bool = False,
        metering_enabled: bool = True,
        timeout: float = 30.0,
        encryption_key: str | None = None,
    ):
        # Validate required endpoint
        if not endpoint:
            raise ConfigurationError(
                "endpoint is required for EdgeClient. "
                "Provide your internal MI container URL."
            )

        self.endpoint = endpoint.rstrip("/")
        self.hipaa_mode = hipaa_mode
        self.air_gapped = air_gapped
        self.metering_enabled = metering_enabled and not air_gapped

        # Store settings before calling parent init
        self._edge_timeout = timeout
        self._edge_encryption_key = encryption_key

        # Initialize with None - we'll set up manually
        self._api_key = api_key
        self._base_url = self.endpoint
        self._user_ulid = None
        self._org_ulid = None
        self._org_ulid = None
        self._user_ulid = None

        # For air-gapped mode, API key is optional
        if not air_gapped:
            from ._auth import resolve_api_key, validate_key_format
            if api_key is None:
                raise ConfigurationError(
                    "API key required for non-air-gapped edge deployment. "
                    "Use air_gapped=True for offline mode."
                )
            self._api_key = resolve_api_key(api_key)
            validate_key_format(self._api_key)

        # Initialize transport to edge endpoint
        self._transport = SyncTransport(
            api_key=self._api_key or "air-gapped",
            base_url=self.endpoint,
            timeout=timeout,
            max_retries=3,
        )

        # Encryption (default for all)
        self._encryptor = SDKEncryptor(key=encryption_key)

        # Log ephemeral warning if using auto-generated key
        if self._encryptor.is_ephemeral():
            from ._crypto import log_ephemeral_warning
            log_ephemeral_warning()

        # License with extended grace period for air-gapped
        grace_days = AIR_GAPPED_GRACE_DAYS if air_gapped else None
        self._license = LicenseManager(
            self._api_key or "air-gapped",
            self._transport,
            air_gapped=air_gapped,
            grace_days=grace_days,
        )
        self._license.validate_on_init()

        # CRITICAL: Check license tier - EdgeClient requires ENTERPRISE
        self._license.check_feature("edge_client")

        if not air_gapped:
            self._license.schedule_background_revalidation()

        # Override UMO namespace with Edge-specific one
        self.umo = EdgeUMONamespace(self)

        # Set up metering client if enabled
        if self.metering_enabled and self._api_key:
            self._metering_client = SyncTransport(
                api_key=self._api_key,
                base_url="https://api.memoryintelligence.io",
                timeout=5.0,  # Fast timeout for metering
                max_retries=1,
            )
        else:
            self._metering_client = None

        logger.info(
            f"EdgeClient initialized (endpoint={endpoint}, "
            f"hipaa={hipaa_mode}, air_gapped={air_gapped})"
        )

    def aggregate(
        self,
        query: str,
        scope: Scope = Scope.ORGANIZATION,
        return_format: str = "statistics_only",
        minimum_cohort_size: int = 50,
    ) -> dict[str, Any]:
        """
        Aggregate insights across records without exposing individual data.

        Federated querying with differential privacy for regulated data.

        Args:
            query: Natural language query for aggregation
            scope: Aggregation scope (typically ORGANIZATION)
            return_format: "statistics_only" (no individual records)
            minimum_cohort_size: K-anonymity threshold

        Returns:
            Aggregated statistics with privacy guarantees

        Raises:
            LicenseError: If ENTERPRISE license not available
        """
        self._license.check_feature("edge_client")

        payload = {
            "query": query,
            "scope": scope.value,
            "return_format": return_format,
            "minimum_cohort_size": minimum_cohort_size,
            "hipaa_mode": self.hipaa_mode,
        }

        response = self._transport.request("POST", "/v1/aggregate", json=payload)

        # Report usage if metering enabled
        if self.metering_enabled and self._metering_client:
            self._report_usage("aggregate", "aggregate")

        return response

    def verify_phi_handling(self, umo_id: str) -> dict[str, Any]:
        """
        Verify how PHI was handled for a specific UMO.

        Returns audit proof showing:
        - What PHI types were detected
        - How each was handled (hashed, redacted)
        - Proof that raw PHI was never stored/transmitted

        Args:
            umo_id: ULID of the processed memory

        Returns:
            PHI handling audit proof
        """
        self._license.check_feature("edge_client")

        response = self._transport.request("GET", f"/v1/phi/verify/{umo_id}")
        return response

    def export_audit_log(
        self,
        start_date: datetime,
        end_date: datetime,
        format: str = "json",
    ) -> dict[str, Any]:
        """
        Export audit log for compliance review.

        Returns complete processing audit trail for the date range.

        Args:
            start_date: Audit period start
            end_date: Audit period end
            format: Export format ("json", "csv")

        Returns:
            Audit log with all processing events
        """
        self._license.check_feature("edge_client")

        payload = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "format": format,
        }

        response = self._transport.request("POST", "/v1/audit/export", json=payload)
        return response

    def _report_usage(self, operation: str, user_ulid: str) -> None:
        """Report usage to MI cloud for metering (non-blocking)."""
        if not self._metering_client:
            return

        try:
            from datetime import timezone
            self._metering_client.request(
                "POST",
                "/v1/metering/report",
                json={
                    "operation": operation,
                    "user_ulid": user_ulid,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "hipaa_mode": self.hipaa_mode,
                },
            )
        except Exception as e:
            # Metering failures should never block processing
            logger.debug(f"Metering report failed (non-blocking): {e}")

    def close(self) -> None:
        """Close HTTP clients."""
        self._transport.close()
        self._license.stop_background_revalidation()
        if self._metering_client:
            self._metering_client.close()
