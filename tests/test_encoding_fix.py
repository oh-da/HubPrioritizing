"""
Test suite for encoding detection and Hebrew text validation.

Run with: pytest tests/test_encoding_fix.py -v
"""

import pytest
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.encoding_fix import (
    is_valid_hebrew_text,
    validate_hebrew_in_gdf,
    fix_encoding_in_dataframe
)
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point


class TestHebrewValidation:
    """Test Hebrew text validation functions."""

    def test_valid_hebrew_text(self):
        """Test that valid Hebrew text is recognized."""
        # Pure Hebrew
        assert is_valid_hebrew_text("תל אביב")
        assert is_valid_hebrew_text("חיפה")
        assert is_valid_hebrew_text("ירושלים")

        # Mixed Hebrew and English
        assert is_valid_hebrew_text("Tel Aviv - תל אביב")

    def test_invalid_hebrew_gibberish(self):
        """Test that gibberish is rejected."""
        # Garbled text patterns
        assert not is_valid_hebrew_text("'¬–¥–ª–™–__'")
        assert not is_valid_hebrew_text("₪˜™–__")
        assert not is_valid_hebrew_text("–ª–™–")

        # Too many special characters, no Hebrew
        assert not is_valid_hebrew_text("!@#$%^&*()")

    def test_valid_hebrew_text_empty(self):
        """Test that empty/None text is accepted."""
        assert is_valid_hebrew_text("")
        assert is_valid_hebrew_text(None)
        assert is_valid_hebrew_text("   ")  # Whitespace only

    def test_valid_hebrew_text_english(self):
        """Test that pure English is rejected when checking for Hebrew."""
        # Pure English should fail the Hebrew ratio check
        assert not is_valid_hebrew_text("Tel Aviv")
        assert not is_valid_hebrew_text("Haifa")
        assert not is_valid_hebrew_text("Jerusalem")

    def test_valid_hebrew_text_verbose(self, capsys):
        """Test verbose mode provides diagnostic output."""
        is_valid_hebrew_text("תל אביב", verbose=True)
        captured = capsys.readouterr()

        assert "Text:" in captured.out
        assert "Hebrew:" in captured.out
        assert "Valid Hebrew" in captured.out or "✓" in captured.out


class TestGeoDataFrameValidation:
    """Test GeoDataFrame Hebrew validation."""

    def test_validate_hebrew_in_gdf_valid(self):
        """Test validation of GeoDataFrame with valid Hebrew."""
        # Create sample GeoDataFrame
        data = {
            'name': ['תל אביב', 'חיפה', 'ירושלים'],
            'zone': ['מרכז', 'צפון', 'מרכז'],
            'geometry': [Point(0, 0), Point(1, 1), Point(2, 2)]
        }
        gdf = gpd.GeoDataFrame(data, crs='EPSG:4326')

        # Should validate successfully
        assert validate_hebrew_in_gdf(gdf, ['name', 'zone'])

    def test_validate_hebrew_in_gdf_gibberish(self):
        """Test validation rejects GeoDataFrame with gibberish."""
        # Create sample GeoDataFrame with garbled text
        data = {
            'name': ["'¬–¥–ª–™–__'", "₪˜™–__", "–ª–™–"],
            'zone': ['!@#$', '^&*()', '###'],
            'geometry': [Point(0, 0), Point(1, 1), Point(2, 2)]
        }
        gdf = gpd.GeoDataFrame(data, crs='EPSG:4326')

        # Should fail validation
        assert not validate_hebrew_in_gdf(gdf, ['name', 'zone'])

    def test_validate_hebrew_in_gdf_missing_columns(self):
        """Test validation handles missing columns gracefully."""
        data = {
            'name': ['תל אביב', 'חיפה'],
            'geometry': [Point(0, 0), Point(1, 1)]
        }
        gdf = gpd.GeoDataFrame(data, crs='EPSG:4326')

        # Should not fail even if column doesn't exist
        assert validate_hebrew_in_gdf(gdf, ['name', 'nonexistent'])


class TestEncodingFix:
    """Test encoding fix functionality."""

    def test_fix_encoding_in_dataframe(self):
        """Test fixing encoding in DataFrame columns."""
        # This test would require actual encoded data
        # For now, test that function doesn't break with normal data
        df = pd.DataFrame({
            'area': ['תל אביב', 'חיפה'],
            'value': [1, 2]
        })

        df_fixed = fix_encoding_in_dataframe(df, ['area'])

        # Should not change already-correct Hebrew
        assert df_fixed['area'].tolist() == df['area'].tolist()

    def test_fix_encoding_missing_columns(self):
        """Test encoding fix handles missing columns."""
        df = pd.DataFrame({
            'value': [1, 2]
        })

        df_fixed = fix_encoding_in_dataframe(df, ['nonexistent'])

        # Should not raise error
        assert df_fixed.equals(df)


class TestHebrewPatterns:
    """Test specific Hebrew character patterns."""

    def test_hebrew_unicode_range(self):
        """Test that Hebrew Unicode characters are properly detected."""
        # Test individual Hebrew characters
        hebrew_chars = ['א', 'ב', 'ג', 'ד', 'ה', 'ו', 'ז', 'ח', 'ט', 'י']

        for char in hebrew_chars:
            # Single character might not meet ratio threshold
            # So test with multiple chars
            text = char * 5
            assert is_valid_hebrew_text(text)

    def test_mixed_content(self):
        """Test mixed Hebrew and English content."""
        # Should pass if enough Hebrew
        assert is_valid_hebrew_text("תל אביב Tel Aviv")

        # Should fail if too little Hebrew
        assert not is_valid_hebrew_text("Tel Aviv תל")

    def test_special_chars_with_hebrew(self):
        """Test that special characters with Hebrew are handled correctly."""
        # Special chars with Hebrew should be ok
        assert is_valid_hebrew_text("תל אביב (מרכז)")
        assert is_valid_hebrew_text("חיפה - צפון")
        assert is_valid_hebrew_text("ירושלים, ישראל")


def test_imports():
    """Test that all utilities can be imported."""
    from src.utils.encoding_fix import (
        is_valid_hebrew_text,
        validate_hebrew_in_gdf,
        read_shapefile_with_encoding,
        diagnose_encoding_issue,
        fix_encoding_in_dataframe
    )

    assert callable(is_valid_hebrew_text)
    assert callable(validate_hebrew_in_gdf)
    assert callable(read_shapefile_with_encoding)
    assert callable(diagnose_encoding_issue)
    assert callable(fix_encoding_in_dataframe)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
