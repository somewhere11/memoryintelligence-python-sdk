"""Memory Intelligence SDK - Authentication.

API key resolution and validation.
"""

from __future__ import annotations

import os
import re
from urllib.parse import urlparse

from ._errors import ConfigurationError

# Try to load python-dotenv if available (optional dependency)
_dotenv_loaded = False
try:
    from dotenv import load_dotenv
    # Load .env file from current directory (won't override existing env vars)
    load_dotenv(override=False)
    _dotenv_loaded = True
except ImportError:
    pass  # python-dotenv not installed, skip .env loading

# Production API URL
DEFAULT_API_URL = "https://api.memoryintelligence.io"

# Valid API key prefixes
LIVE_KEY_PREFIX  = "mi_sk_live_"
TEST_KEY_PREFIX  = "mi_sk_test_"
BETA_KEY_PREFIX  = "mi_sk_beta_"  # beta programme keys
VALID_KEY_PREFIXES = (LIVE_KEY_PREFIX, TEST_KEY_PREFIX, BETA_KEY_PREFIX)

# Minimum key length (prefix + some randomness)
MIN_KEY_LENGTH = 32

# URL patterns that indicate localhost/local development
LOCALHOST_PATTERNS = [
    r"localhost",
    r"127\.\d+\.\d+\.\d+",
    r"0\.0\.0\.0",
    r"::1",
    r"\.local$",
    r"\.internal$",
    r":\d+/(?!/)"  # Any port specifier (rough heuristic)
]


def resolve_api_key(explicit_key: str | None) -> str:
    """
    Resolve API key from explicit argument or environment.

    Priority:
        1. Explicit key passed to constructor
        2. MI_API_KEY environment variable
        3. ConfigurationError (key is required)

    Args:
        explicit_key: API key passed directly to constructor

    Returns:
        Resolved API key string

    Raises:
        ConfigurationError: If no API key is found

    Example:
        >>> resolve_api_key("mi_sk_test_abc123...")
        'mi_sk_test_abc123...'
        >>> resolve_api_key(None)  # With MI_API_KEY set
        'mi_sk_live_xyz789...'
    """
    if explicit_key is not None:
        key = explicit_key.strip()
        if key:
            return key

    env_key = os.environ.get("MI_API_KEY")
    if env_key:
        key = env_key.strip()
        if key:
            return key

    raise ConfigurationError(
        "API key is required. Pass it directly, set MI_API_KEY environment variable, "
        "or add MI_API_KEY=your_key to a .env file (requires: pip install memoryintelligence[dotenv]). "
        "Get your API key at https://memoryintelligence.io/portal"
    )


def validate_api_key(api_key: str, base_url: str) -> None:
    """
    Validate API key format and environment compatibility.
    
    Combines format and environment checks into one call.
    
    Args:
        api_key: API key to validate
        base_url: Base URL being used (to check live key + localhost)
        
    Raises:
        ConfigurationError: If key format or environment is invalid
    """
    validate_key_format(api_key)
    validate_key_environment(api_key, base_url)


def resolve_base_url(explicit_url: str | None) -> str:
    """
    Resolve base URL from explicit argument or environment.

    Priority:
        1. Explicit URL passed to constructor
        2. MI_BASE_URL environment variable
        3. Production default (https://api.memoryintelligence.io)

    Args:
        explicit_url: Base URL passed directly to constructor

    Returns:
        Resolved base URL string (normalized, no trailing slash)

    Raises:
        ConfigurationError: If URL is malformed

    Example:
        >>> resolve_base_url("https://custom.example.com")
        'https://custom.example.com'
        >>> resolve_base_url("https://custom.example.com/")  # Trailing slash removed
        'https://custom.example.com'
    """
    url = None

    if explicit_url is not None:
        url = explicit_url.strip()
    else:
        env_url = os.environ.get("MI_BASE_URL")
        if env_url:
            url = env_url.strip()

    if not url:
        return DEFAULT_API_URL

    # Basic URL validation
    if not url.startswith(("http://", "https://")):
        raise ConfigurationError(
            f"Invalid base_url: must start with http:// or https://. Got: {url[:50]}..."
        )

    # Validate URL structure
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            raise ConfigurationError(f"Invalid base_url: missing host. Got: {url}")
    except Exception as e:
        raise ConfigurationError(f"Invalid base_url: {e}") from e

    # Remove trailing slashes for consistency
    return url.rstrip("/")


def validate_key_format(api_key: str) -> None:
    """
    Validate API key format.

    Valid keys must:
        - Start with 'mi_sk_live_' or 'mi_sk_test_'
        - Be at least 32 characters long
        - Not contain whitespace

    Args:
        api_key: API key to validate

    Raises:
        ConfigurationError: If key format is invalid

    Example:
        >>> validate_key_format("mi_sk_test_abc123xyz...")
        # passes silently
        >>> validate_key_format("invalid_key")
        ConfigurationError: Invalid API key format...
    """
    if not api_key:
        raise ConfigurationError("API key cannot be empty.")

    # Check for whitespace
    if api_key != api_key.strip():
        raise ConfigurationError(
            "API key contains leading or trailing whitespace. Please check your key."
        )

    # Check prefix
    if not any(api_key.startswith(prefix) for prefix in VALID_KEY_PREFIXES):
        # Show what we received (safely truncated)
        displayed_key = api_key[:20] + "..." if len(api_key) > 20 else api_key
        raise ConfigurationError(
            f"Invalid API key format. Key must start with 'mi_sk_live_', 'mi_sk_test_', or 'mi_sk_beta_'. "
            f"Got: '{displayed_key}'. Get your API key at https://memoryintelligence.io/dashboard"
        )

    # Check minimum length
    if len(api_key) < MIN_KEY_LENGTH:
        raise ConfigurationError(
            f"API key too short. Expected at least {MIN_KEY_LENGTH} characters, "
            f"got {len(api_key)}. Please provide a complete key."
        )


def validate_key_environment(api_key: str, base_url: str) -> None:
    """
    Validate that live keys are not used with localhost/development URLs.

    This is a safety measure to prevent accidentally using production keys
    in development environments.

    Args:
        api_key: The API key being used
        base_url: The base URL being configured

    Raises:
        ConfigurationError: If live key is used with localhost URL

    Example:
        >>> validate_key_environment(
        ...     "mi_sk_live_abc123...",
        ...     "http://localhost:8000"
        ... )
        ConfigurationError: Live key detected with local base_url...
    """
    is_live_key = api_key.startswith(LIVE_KEY_PREFIX)

    # Check for local/development URLs
    is_localhost = _is_localhost_url(base_url)

    if is_live_key and is_localhost:
        raise ConfigurationError(
            "Live key detected with local base_url. "
            "Use a test key for local development. "
            "Test keys start with 'mi_sk_test_'. "
            "Get test keys at https://memoryintelligence.io/dashboard"
        )


def _is_localhost_url(url: str) -> bool:
    """
    Check if URL points to localhost/development environment.

    Args:
        url: URL string to check

    Returns:
        True if URL appears to be localhost/local development
    """
    url_lower = url.lower()

    for pattern in LOCALHOST_PATTERNS:
        if re.search(pattern, url_lower):
            return True

    return False


def is_live_key(api_key: str) -> bool:
    """
    Check if API key is a live/production key.

    Args:
        api_key: API key to check

    Returns:
        True if key starts with 'mi_sk_live_'

    Example:
        >>> is_live_key("mi_sk_live_abc123")
        True
        >>> is_live_key("mi_sk_test_xyz789")
        False
    """
    return api_key.startswith(LIVE_KEY_PREFIX)


def is_test_key(api_key: str) -> bool:
    """
    Check if API key is a test/development key.

    Args:
        api_key: API key to check

    Returns:
        True if key starts with 'mi_sk_test_'

    Example:
        >>> is_test_key("mi_sk_test_xyz789")
        True
        >>> is_test_key("mi_sk_live_abc123")
        False
    """
    return api_key.startswith(TEST_KEY_PREFIX)


def mask_key(api_key: str) -> str:
    """
    Mask API key for safe logging/display.

    Args:
        api_key: API key to mask

    Returns:
        Masked key showing only first 12 and last 4 characters

    Example:
        >>> mask_key("mi_sk_test_abc123xyz789")
        'mi_sk_test_abc...yz89'
    """
    if len(api_key) <= 16:
        return "***"
    return f"{api_key[:12]}...{api_key[-4:]}"
