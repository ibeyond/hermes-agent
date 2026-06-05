"""Tests for HERMES_NO_BROWSER environment variable in hermes_cli.auth.

When HERMES_NO_BROWSER=1 is set, no automatic browser opening should occur
in any OAuth flow. The URL is still printed to the terminal so the user
can manually open it if desired.
"""

from __future__ import annotations

import pytest

from hermes_cli.auth import _get_hermes_no_browser


class TestGetHermesNoBrowser:
    """Test _get_hermes_no_browser() function."""

    def test_defaults_to_false(self, monkeypatch):
        """Default behavior: HERMES_NO_BROWSER not set → returns False."""
        monkeypatch.delenv("HERMES_NO_BROWSER", raising=False)
        assert _get_hermes_no_browser() is False

    def test_set_to_one_returns_true(self, monkeypatch):
        """HERMES_NO_BROWSER=1 → returns True."""
        monkeypatch.setenv("HERMES_NO_BROWSER", "1")
        assert _get_hermes_no_browser() is True

    def test_set_to_zero_returns_false(self, monkeypatch):
        """HERMES_NO_BROWSER=0 → returns False (only 1 triggers)."""
        monkeypatch.setenv("HERMES_NO_BROWSER", "0")
        assert _get_hermes_no_browser() is False

    def test_set_to_empty_string_returns_false(self, monkeypatch):
        """HERMES_NO_BROWSER='' → returns False."""
        monkeypatch.setenv("HERMES_NO_BROWSER", "")
        assert _get_hermes_no_browser() is False

    def test_set_to_other_value_returns_false(self, monkeypatch):
        """HERMES_NO_BROWSER=true → returns False (only exact '1' triggers)."""
        monkeypatch.setenv("HERMES_NO_BROWSER", "true")
        assert _get_hermes_no_browser() is False

    def test_case_sensitive(self, monkeypatch):
        """HERMES_NO_BROWSER is case-sensitive."""
        monkeypatch.setenv("HERMES_NO_BROWSER", "TRUE")
        assert _get_hermes_no_browser() is False