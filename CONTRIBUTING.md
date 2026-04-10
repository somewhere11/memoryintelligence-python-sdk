# Contributing to Memory Intelligence SDK

Thank you for your interest in contributing to the Memory Intelligence Python SDK!

## Getting Started

1. Fork the repository and clone your fork
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Install development dependencies:
   ```bash
   pip install -e .[dev]
   ```

## Testing

The SDK includes comprehensive testing guidelines. When contributing new features or bug fixes, please follow these standards:

### Test Coverage Requirements

- All public API functions must have unit tests
- Error handling must be tested for expected error conditions
- Telemetry output must be verified in test cases
- New features should include 100% test coverage

### Running Tests

```bash
pytest --cov=memoryintelligence --cov-report=term-missing
```

### Telemetry Verification

When testing features with telemetry:

```python
# Set log level to DEBUG
import logging
logging.basicConfig(level=logging.DEBUG)

# Test your code
# Verify expected log messages appear
```

## Code Guidelines

- Use `ruff` for linting: `ruff check .`
- Use `mypy` for type checking: `mypy .`
- Follow PEP 8 guidelines with 100 character line length
- Write clear, concise docstrings using Google style

## Pull Request Process

1. Create a branch for your feature/bugfix
2. Write tests for your changes
3. Ensure all tests pass
4. Update documentation as needed
5. Submit a pull request with a clear description of the changes

## Versioning

This project follows Semantic Versioning. When contributing:

- Bug fixes: patch version increment (1.0.0 → 1.0.1)
- New features: minor version increment (1.0.0 → 1.1.0)
- Breaking changes: major version increment (1.0.0 → 2.0.0)

## Documentation

Update the SDK documentation when:
- Adding new public APIs
- Changing existing API signatures
- Modifying behavior that affects users

## Security

Please report security issues directly to security@memoryintelligence.io. Do not report security issues through GitHub issues.