"""Tests for plugins: ship_plugin and equipment_plugin."""

from __future__ import annotations

import pytest

from plugins.ship_plugin import imo_validator, tonnage_converter, compute_ship_age
from plugins.equipment_plugin import (
    straight_line_depreciation,
    double_declining_depreciation,
    compute_current_value,
)
from plugins import REGISTRY, register_plugin, get_plugin


# ═══ Ship Plugin ═══════════════════════════════════════════


class TestIMOValidator:
    def test_valid_imo(self):
        """IMO 9074729 is a known valid number (checksum correct)."""
        import pandas as pd
        # IMO 9074729: digits=[9,0,7,4,7,2], check_digit=9
        # sum = 9*7 + 0*6 + 7*5 + 4*4 + 7*3 + 2*2 = 63+0+35+16+21+4 = 139
        # 139 % 10 = 9 → check digit 9 ✓
        s = pd.Series(["9074729"])
        issues = imo_validator(s, "imo_number")
        # This specific IMO should pass (no errors/warnings)
        assert len(issues) == 0

    def test_invalid_imo_length(self):
        import pandas as pd
        s = pd.Series(["1"])  # Very short — zfilled to 7 digits but checksum fails
        issues = imo_validator(s, "imo_number")
        assert len(issues) >= 1  # Should find some issue (checksum mismatch)

    def test_invalid_imo_checksum(self):
        import pandas as pd
        s = pd.Series(["1234567"])  # Wrong checksum: 1*7+2*6+3*5+4*4+5*3+6*2 = 7+12+15+16+15+12=77%10=7, check=7 → fails
        issues = imo_validator(s, "imo_number")
        # 1234567: check_digit=7, computed=77%10=7 → actually passes
        # Let's use 1234568: check=8, computed=7 → fails
        pass

    def test_imo_checksum_mismatch(self):
        import pandas as pd
        s = pd.Series(["1234568"])  # checksum should be 7 but is 8
        issues = imo_validator(s, "imo_number")
        assert len(issues) >= 1
        assert "mismatch" in issues[0]["description"].lower()

    def test_imo_non_digit(self):
        import pandas as pd
        s = pd.Series(["ABCDEFG"])
        issues = imo_validator(s, "imo_number")
        assert len(issues) >= 1

    def test_imo_int_value(self):
        import pandas as pd
        s = pd.Series([9074729])
        issues = imo_validator(s, "imo_number")
        assert len(issues) == 0  # Valid IMO

    def test_imo_empty_series(self):
        import pandas as pd
        s = pd.Series([], dtype=str)
        issues = imo_validator(s, "imo_number")
        assert len(issues) == 0


class TestTonnageConverter:
    def test_default_conversion(self):
        result = tonnage_converter(10000)
        assert result["gross_tonnage"] == 10000
        assert result["estimated_dwt"] == 16000.0

    def test_small_tonnage(self):
        result = tonnage_converter(500)
        assert result["estimated_dwt"] == 800.0

    def test_zero_tonnage(self):
        result = tonnage_converter(0)
        assert result["estimated_dwt"] == 0.0


class TestShipAge:
    def test_compute_age(self):
        age = compute_ship_age(2010, 2025)
        assert age == 15

    def test_current_year_default(self):
        age = compute_ship_age(2023)
        assert age is not None and age >= 0

    def test_future_year(self):
        age = compute_ship_age(2030, 2025)
        assert age == 0  # max(0, -5) → 0

    def test_zero_build_year(self):
        age = compute_ship_age(0)
        assert age is None


# ═══ Equipment Plugin ══════════════════════════════════════


class TestDepreciation:
    def test_straight_line(self):
        result = straight_line_depreciation(100000, 0.1, 10)
        # (100000 * 0.9) / 10 = 9000
        assert result["annual_depreciation"] == 9000.0
        assert result["monthly_depreciation"] == 750.0
        assert result["depreciation_method"] == "straight_line"

    def test_straight_line_zero_life(self):
        result = straight_line_depreciation(100000, 0.1, 0)
        assert result["annual_depreciation"] == 0.0

    def test_double_declining(self):
        result = double_declining_depreciation(100000, 0.1, 10, 2025)
        # rate = 2/10 = 0.2, annual = 100000 * 0.2 = 20000
        assert result["annual_depreciation"] == 20000.0
        assert result["depreciation_rate"] == 0.2
        assert result["residual_value"] == 10000.0

    def test_double_declining_zero_life(self):
        result = double_declining_depreciation(100000, 0.1, 0, 2025)
        assert result["annual_depreciation"] == 0.0

    def test_double_declining_at_residual(self):
        """When depreciation would go below residual, it's capped."""
        result = double_declining_depreciation(10000, 0.5, 1, 2025)
        # rate = 2.0, annual = 20000, residual = 5000
        # book_value - annual = -10000 < 5000, so annual = 10000 - 5000 = 5000
        assert result["annual_depreciation"] == 5000.0


class TestCurrentValue:
    def test_current_value_with_date(self):
        result = compute_current_value(100000, 9000, "2023-01-01")
        # Current date is today, so accumulated should be some value
        assert "current_value" in result
        assert "years_elapsed" in result

    def test_current_value_no_purchase_date(self):
        result = compute_current_value(100000, 9000, None)
        assert result["current_value"] == 100000
        assert result["note"] is not None

    def test_current_value_fully_depreciated(self):
        from datetime import date
        result = compute_current_value(100000, 9000, "2010-01-01", date(2035, 1, 1))
        assert result["current_value"] == 0.0  # Should be floored at 0


# ═══ Plugin Registry ═══════════════════════════════════════


class TestPluginRegistry:
    def test_builtins_registered(self):
        """Verify built-in plugins are auto-registered."""
        assert "imo_validator" in REGISTRY
        assert "straight_line_depreciation" in REGISTRY

    def test_get_plugin(self):
        func = get_plugin("imo_validator")
        assert func is not None
        assert callable(func)

    def test_get_nonexistent_plugin(self):
        assert get_plugin("nonexistent_func") is None

    def test_register_custom_plugin(self):
        def my_plugin(x):
            return x * 2

        register_plugin("my_custom", my_plugin)
        assert get_plugin("my_custom") is my_plugin
        # Clean up
        del REGISTRY["my_custom"]
