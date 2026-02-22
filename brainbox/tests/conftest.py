"""Shared test fixtures."""

import pytest


@pytest.fixture(autouse=True)
def _override_api_key_auth():
    """Disable API key auth for all tests by default.

    Individual test modules (like test_auth.py) can remove this override
    to test actual auth behavior.
    """
    try:
        from brainbox.api import app
        from brainbox.auth import require_api_key

        app.dependency_overrides[require_api_key] = lambda: None
        yield
        app.dependency_overrides.pop(require_api_key, None)
    except ImportError:
        # If brainbox.api can't be imported (e.g., missing optional deps),
        # skip the override — tests that don't import app won't need it
        yield
