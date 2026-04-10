# Enterprise Guide

Deploy Memory Intelligence in regulated environments with EdgeClient.

## Overview

EdgeClient is designed for:

- **HIPAA**: Healthcare - clinical notes, patient data
- **Legal**: Attorney-client privileged documents
- **Finance**: Trading data, internal communications
- **Competitive**: Trade secrets, internal strategy

**Key Principle:** All processing happens in your infrastructure. Only metering/licensing data crosses the network.

## EdgeClient vs MemoryClient

| Feature | MemoryClient | EdgeClient |
|---------|--------------|------------|
| Deployment | Cloud SaaS | On-premises |
| Data leaves network | Yes | No (optional) |
| HIPAA mode | No | Yes |
| Air-gapped | No | Yes |
| Aggregate queries | No | Yes |
| PHI verification | No | Yes |
| License required | Any tier | ENTERPRISE only |

## Quick Start

### Standard Edge Deployment

```python
from memoryintelligence import EdgeClient

edge = EdgeClient(
    endpoint="https://mi.internal.yourcompany.com",
    api_key="mi_sk_enterprise_key",
)

# Use like regular client
umo = edge.umo.process(
    "Internal strategy discussion...",
    user_ulid="01USER12345678901234567890"
)
```

### HIPAA Mode

```python
edge = EdgeClient(
    endpoint="https://mi.internal.hospital.com",
    api_key="mi_sk_enterprise_key",
    hipaa_mode=True,  # Enforces pii_handling=HASH, provenance_mode=AUDIT
)

# Process clinical note - PHI is automatically hashed
umo = edge.umo.process(
    "Patient John Doe presents with chest pain...",
    user_ulid="01PATIENT12345678901234567890"
)

print(umo.pii.handling_applied)  # "hash"
```

### Air-Gapped Deployment

```python
edge = EdgeClient(
    endpoint="https://mi.secure-facility.local",
    air_gapped=True,  # No external network calls
    # No API key needed in air-gapped mode
)
```

## HIPAA Mode

When `hipaa_mode=True`, the following are enforced:

| Setting | Behavior |
|---------|----------|
| `pii_handling` | Always `HASH` (non-negotiable) |
| `provenance_mode` | Always `AUDIT` (non-negotiable) |

```python
# Attempt to override - will be silently changed to HASH
umo = edge.umo.process(
    "Patient data...",
    user_ulid="01USER123",
    pii_handling="extract_and_redact"  # Ignored in HIPAA mode
)
```

## Air-Gapped Mode

For environments with no external network access:

```python
edge = EdgeClient(
    endpoint="https://mi.internal.com",
    air_gapped=True,
)

# Features:
# - No API calls to memoryintelligence.io
# - 30-day grace period (vs 14-day cloud)
# - Metering disabled
# - License validation against local endpoint only
```

## Federated Aggregation

Query across deployments without exposing individual records:

```python
result = edge.aggregate(
    query="What is the average patient age?",
    scope=Scope.ORGANIZATION,
    return_format="statistics_only",
    minimum_cohort_size=50,  # K-anonymity threshold
)

print(result)
# {
#     "results": [{"metric": "avg_age", "value": 54.3, "count": 150}],
#     "privacy_guarantee": "k-anonymity",
#     "minimum_cohort_size": 50,
#     "suppressed_results": 2  # Too small cohorts suppressed
# }
```

## PHI Handling Verification

Verify how PHI was processed:

```python
result = edge.verify_phi_handling("01UMO12345678901234567890")

print(result)
# {
#     "umo_id": "01UMO12345678901234567890",
#     "phi_detected": True,
#     "phi_types": ["PATIENT_NAME", "MEDICAL_RECORD_NUMBER"],
#     "handling_applied": "HASH",
#     "raw_phi_stored": False,
#     "raw_phi_transmitted": False,
#     "audit_proof": {...}
# }
```

## Audit Log Export

Export audit logs for compliance review:

```python
from datetime import datetime, timezone

logs = edge.export_audit_log(
    start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    end_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
    format="json",  # or "csv"
)

# Save to file
import json
with open("audit_log.json", "w") as f:
    json.dump(logs, f, indent=2)
```

## Deployment Architecture

### Single Node

```
┌─────────────────────────────────────┐
│           Your Application          │
│                                     │
│    ┌─────────────────────────┐      │
│    │      EdgeClient         │      │
│    └─────────────────────────┘      │
│                   │                 │
│                   ▼                 │
│    ┌─────────────────────────┐      │
│    │   MI Edge Container     │      │
│    │   (Your Infrastructure) │      │
│    └─────────────────────────┘      │
└─────────────────────────────────────┘
         │
         ▼
   Optional metering to MI Cloud
```

### Multi-Node with Aggregation

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Edge Node 1 │    │  Edge Node 2 │    │  Edge Node 3 │
│  Hospital A  │    │  Hospital B  │    │  Hospital C  │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  Aggregate API  │
                  │  (Federated)    │
                  └─────────────────┘
```

## Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mi-edge
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mi-edge
  template:
    metadata:
      labels:
        app: mi-edge
    spec:
      containers:
      - name: mi-edge
        image: memoryintelligence/edge:latest
        ports:
        - containerPort: 8080
        env:
        - name: MI_HIPAA_MODE
          value: "true"
        - name: MI_ENCRYPTION_KEY
          valueFrom:
            secretKeyRef:
              name: mi-secrets
              key: encryption-key
```

## Metering

EdgeClient can report usage to MI cloud for billing:

```python
edge = EdgeClient(
    endpoint="https://mi.internal.com",
    api_key="mi_sk_enterprise_key",
    metering_enabled=True,  # Report usage (default)
)

# Metering is non-blocking - failures don't affect processing
```

Disable for air-gapped:

```python
edge = EdgeClient(
    endpoint="https://mi.internal.com",
    air_gapped=True,  # Automatically disables metering
)
```

## Grace Periods

| Mode | Grace Period |
|------|--------------|
| Cloud | 14 days |
| Air-gapped | 30 days |

```python
# Expired license with 20 days - works in air-gapped
edge = EdgeClient(
    endpoint="https://mi.internal.com",
    air_gapped=True,
    # License expired 20 days ago - still works (30-day grace)
)

# Expired license with 35 days - raises LicenseError
```

## Troubleshooting

### ENTERPRISE License Required

```
LicenseError: edge_client requires ENTERPRISE tier
```

**Fix:** Upgrade license or use MemoryClient.

### Endpoint Required

```
ConfigurationError: endpoint is required for EdgeClient
```

**Fix:** Provide your internal MI endpoint:
```python
EdgeClient(endpoint="https://mi.yourcompany.com")
```

### Connection Refused

```
ConnectionError: Could not connect to API
```

**Fix:** Verify your MI Edge container is running and accessible.

## Support

- **Enterprise Support:** enterprise@memoryintelligence.io
- **Documentation:** [docs.memoryintelligence.io/enterprise](https://docs.memoryintelligence.io/enterprise)
- **SLA:** [memoryintelligence.io/sla](https://memoryintelligence.io/sla)
