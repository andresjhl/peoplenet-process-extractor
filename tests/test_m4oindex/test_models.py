"""Tests for models and _normalize_is_root."""
from __future__ import annotations

import pytest

from peoplenet_process_extractor.m4oindex.models import (
    ALLOWED_DIAGNOSTIC_CODES,
    DIAGNOSTIC_LEVELS,
    DIAGNOSTIC_SEVERITIES,
    _normalize_is_root,
)


class TestNormalizeIsRoot:
    @pytest.mark.parametrize("value,expected", [
        (True, True),
        (False, False),
        (1, True),
        (0, False),
        ("1", True),
        ("0", False),
    ])
    def test_valid_values(self, value, expected):
        assert _normalize_is_root(value) == expected

    @pytest.mark.parametrize("value", [
        None, "true", "false", 2, -1, "", "yes", "no", 1.0,
    ])
    def test_invalid_returns_none(self, value):
        assert _normalize_is_root(value) is None

    def test_bool_before_int(self):
        # True == 1 as int, but bool subclasses int; must return True (bool), not True==1
        result = _normalize_is_root(True)
        assert result is True
        assert isinstance(result, bool)

    def test_false_before_int_zero(self):
        result = _normalize_is_root(False)
        assert result is False
        assert isinstance(result, bool)


class TestDiagnosticMaps:
    def test_every_code_has_level(self):
        for code in ALLOWED_DIAGNOSTIC_CODES:
            assert code in DIAGNOSTIC_LEVELS, f"Code '{code}' missing from DIAGNOSTIC_LEVELS"

    def test_every_code_has_severity(self):
        for code in ALLOWED_DIAGNOSTIC_CODES:
            assert code in DIAGNOSTIC_SEVERITIES, f"Code '{code}' missing from DIAGNOSTIC_SEVERITIES"

    def test_levels_are_valid(self):
        valid = {"resource", "document", "table", "row", "consistency", "duplicate"}
        for code, level in DIAGNOSTIC_LEVELS.items():
            assert level in valid, f"Code '{code}' has invalid level '{level}'"

    def test_severities_are_valid(self):
        for code, sev in DIAGNOSTIC_SEVERITIES.items():
            assert sev in ("error", "warning"), f"Code '{code}' has invalid severity '{sev}'"

    def test_no_extra_codes_in_levels(self):
        for code in DIAGNOSTIC_LEVELS:
            assert code in ALLOWED_DIAGNOSTIC_CODES, f"'{code}' in DIAGNOSTIC_LEVELS but not in ALLOWED_DIAGNOSTIC_CODES"
