# Licensing Guide

Memory Intelligence SDK uses a tiered licensing model with feature gating.

## License Tiers

| Tier | Features | Grace Period |
|------|----------|--------------|
| **TRIAL** | All features, 7-day limit | - |
| **STARTER** | `process`, `search` | 14 days |
| **PROFESSIONAL** | All cloud features | 14 days |
| **ENTERPRISE** | All features + EdgeClient | 30 days (air-gapped) |

## Feature Matrix

| Feature | TRIAL | STARTER | PROFESSIONAL | ENTERPRISE |
|---------|-------|---------|--------------|------------|
| `umo.process()` | ✅ | ✅ | ✅ | ✅ |
| `umo.search()` | ✅ | ✅ | ✅ | ✅ |
| `umo.match()` | ✅ | ❌ | ✅ | ✅ |
| `umo.explain()` | ✅ | ❌ | ✅ | ✅ |
| `edge.aggregate()` | ❌ | ❌ | ❌ | ✅ |
| `edge.verify_phi_handling()` | ❌ | ❌ | ❌ | ✅ |
| `edge.export_audit_log()` | ❌ | ❌ | ❌ | ✅ |

## Checking Your License

```python
from memoryintelligence import MemoryClient

mi = MemoryClient()

# Check license info
info = mi._license.validate_on_init()
print(f"Tier: {info.tier}")
print(f"Status: {info.status}")
print(f"Expires: {info.expires_at}")
```

## License Errors

Attempting to use a restricted feature raises `LicenseError`:

```python
from memoryintelligence import MemoryClient, LicenseError

mi = MemoryClient()  # STARTER tier

try:
    mi.umo.match("01A", "01B")  # ❌ Requires PROFESSIONAL+
except LicenseError as e:
    print(f"License error: {e}")
    # Output: umo.match() requires PROFESSIONAL or ENTERPRISE tier
```

## Grace Periods

Expired licenses have grace periods before enforcement:

| Mode | Grace Period |
|------|--------------|
| Cloud | 14 days |
| Air-gapped | 30 days |

During grace period, a warning is logged but operations continue.

## Upgrading

To upgrade your license tier, visit:

[https://memoryintelligence.io/billing](https://memoryintelligence.io/billing)

## Support

- **Billing:** billing@memoryintelligence.io
- **Support:** support@memoryintelligence.io
