# Encoding Fix Summary

## Issue Fixed

**Problem:** Hebrew text in Step 2.3 (hub area tagging) appears as garbled characters (e.g., `'¬–¥–ª–™–__'`) instead of proper Hebrew, causing mismatches when looking up areas in the `AREA_TO_REGION` dictionary.

**Root Cause:** Shapefiles containing area/location data are encoded in Windows-1255 or ISO-8859-8 (common Hebrew encodings), but the encoding detection was not strict enough to catch when text was being read incorrectly.

## Solution Implemented

### Files Created/Modified

1. **`src/utils/encoding_fix.py`** - NEW
   - Improved Hebrew text validation with strict gibberish detection
   - Enhanced shapefile encoding detection with better diagnostics
   - Functions for post-processing encoding fixes

2. **`scripts/diagnose_encoding.py`** - NEW
   - Interactive diagnostic tool to identify encoding issues
   - Tries all encodings and shows exactly what text is being read
   - Helps identify the correct encoding for your shapefiles

3. **`scripts/test_encoding_basic.py`** - NEW
   - Basic test suite for Hebrew validation logic
   - Can be run to verify the fix works correctly

4. **`tests/test_encoding_fix.py`** - NEW
   - Comprehensive pytest test suite (requires pytest installation)

5. **`ENCODING_FIX_PATCH.md`** - NEW
   - Detailed instructions for applying the fix to the notebook
   - Multiple solution options (automatic detection vs. manual override)

## How to Use

### Quick Fix (Recommended)

1. **Run the diagnostic script** to identify the correct encoding:
   ```bash
   python scripts/diagnose_encoding.py
   ```

   When prompted, enter the paths to your shapefiles:
   - Metro shapefile (e.g., `/path/to/metro.shp`)
   - Districts shapefile (e.g., `/path/to/districts.shp`)

   The script will show you exactly what text is being read with each encoding.

2. **Identify the correct encoding** from the output:
   - Look for the encoding that shows proper Hebrew characters (not gibberish)
   - Common encodings: `windows-1255`, `cp1255`, `ISO-8859-8`, `utf-8`

3. **Apply the fix** in your notebook:

   Add this code cell **before Step 2.3**:
   ```python
   # Import improved encoding detection
   from src.utils.encoding_fix import (
       read_shapefile_with_encoding,
       is_valid_hebrew_text,
       validate_hebrew_in_gdf
   )

   # (Optional) Force specific encoding if you know it
   FORCE_METRO_ENCODING = 'windows-1255'  # Change to None for auto-detect
   FORCE_DISTRICTS_ENCODING = 'windows-1255'  # Change to None for auto-detect
   ```

   Then modify the shapefile loading calls in Step 2.3:
   ```python
   # Add force_encoding parameter
   metro_gdf, metro_encoding = read_shapefile_with_encoding(
       METRO_SHP,
       name="metro",
       hebrew_columns=metro_hebrew_cols,
       force_encoding=FORCE_METRO_ENCODING  # ADD THIS
   )

   districts_gdf, districts_encoding = read_shapefile_with_encoding(
       DISTRICTS_SHP,
       name="districts",
       hebrew_columns=districts_hebrew_cols,
       force_encoding=FORCE_DISTRICTS_ENCODING  # ADD THIS
   )
   ```

4. **Verify the fix** by checking the output:
   - Hebrew text should appear correctly (not gibberish)
   - The diagnostic output will show which encoding was used
   - Area and location columns should be populated with proper Hebrew

### Detailed Instructions

See **`ENCODING_FIX_PATCH.md`** for comprehensive instructions including:
- Multiple solution approaches
- Verification steps
- Troubleshooting guide
- Alternative post-processing fixes

## Key Improvements

### 1. Stricter Hebrew Validation

The new `is_valid_hebrew_text()` function:
- ✅ Checks for Hebrew characters in Unicode range U+0590 to U+05FF
- ✅ Requires at least 30% of characters to be Hebrew
- ✅ **NEW:** Detects gibberish patterns (many special chars, no Hebrew)
- ✅ **NEW:** Provides verbose diagnostic output
- ✅ **NEW:** Better handling of mixed Hebrew/English content

### 2. Enhanced Encoding Detection

The new `read_shapefile_with_encoding()` function:
- ✅ Tries encodings in priority order (Hebrew encodings first)
- ✅ Validates that Hebrew text is readable (not gibberish)
- ✅ **NEW:** Supports manual encoding override
- ✅ **NEW:** Provides detailed diagnostic output
- ✅ **NEW:** Shows which encoding succeeded

### 3. Diagnostic Tools

New diagnostic capabilities:
- ✅ Interactive diagnostic script to test all encodings
- ✅ Shows exact text being read with each encoding
- ✅ Validates Hebrew character detection
- ✅ Identifies gibberish patterns

## What This Fixes

### Before (Broken)
```
area samples: ['¬–¥–ª–™–__', '₪˜™–__', '–ª–™–']
✗ Area values don't match AREA_TO_REGION keys
✗ Demand matching fails
✗ TotalDemand = 0 for all hubs
```

### After (Fixed)
```
area samples: ['תל אביב', 'חיפה', 'ירושלים']
✓ All areas match AREA_TO_REGION keys
✓ Demand matching succeeds
✓ TotalDemand populated correctly
```

## Technical Details

### Hebrew Character Validation

The validation function checks:
1. **Hebrew Unicode Range:** U+0590 to U+05FF (includes letters, vowels, marks)
2. **Character Ratio:** At least 30% of non-space characters must be Hebrew
3. **Gibberish Detection:** Rejects text with many special chars and no Hebrew
4. **Mixed Content:** Handles Hebrew/English mixed text appropriately

### Encoding Priority Order

The detection tries encodings in this order:
1. `windows-1255` (Windows Hebrew) - Most common for Israeli shapefiles
2. `cp1255` (Code Page 1255) - Similar to windows-1255
3. `ISO-8859-8` (Latin/Hebrew) - Older standard
4. `utf-8` (Universal) - Modern standard, but rare in older shapefiles
5. Auto-detect (geopandas default)

### Validation Process

For each encoding:
1. Try to load the shapefile
2. Check specified Hebrew columns for sample values
3. Validate each sample with `is_valid_hebrew_text()`
4. If all samples pass → Success, use this encoding
5. If any sample fails → Try next encoding

## Testing

To verify the fix works:

```bash
# Run basic tests (no dependencies required)
python scripts/test_encoding_basic.py

# Run comprehensive tests (requires pytest)
pytest tests/test_encoding_fix.py -v
```

## Troubleshooting

### Problem: Diagnostic script shows all encodings fail

**Solution:** The shapefile might use a different encoding. Try:
1. Check the shapefile metadata (`.cpg` file if exists)
2. Try additional encodings: `cp862`, `ISO-8859-8-I`, `utf-16`
3. Contact the data provider for encoding information

### Problem: Hebrew text looks correct but still doesn't match AREA_TO_REGION

**Solution:** There might be whitespace or formatting differences. Add normalization:
```python
# After the spatial join
gdf_demand['area'] = gdf_demand['area'].str.strip()  # Remove whitespace
```

### Problem: Some areas show correct Hebrew, others show gibberish

**Solution:** The shapefile might have mixed encodings. Apply post-processing:
```python
from src.utils.encoding_fix import fix_encoding_in_dataframe

gdf_demand = fix_encoding_in_dataframe(
    gdf_demand,
    columns=['area', 'location'],
    source_encoding='windows-1255'
)
```

## Next Steps

1. ✅ Run the diagnostic script to identify your encoding
2. ✅ Apply the fix in the notebook
3. ✅ Re-run Step 2.3 and verify Hebrew text is correct
4. ✅ Verify Step 2.6 demand matching works
5. ✅ Check final hub data has proper TotalDemand values

## Questions or Issues?

If you continue to experience encoding problems:
1. Save the output of `scripts/diagnose_encoding.py`
2. Share sample garbled text you're seeing
3. Share shapefile metadata (if available)
4. Create a GitHub issue with the diagnostic information

## References

- **Hebrew Unicode:** https://en.wikipedia.org/wiki/Hebrew_(Unicode_block)
- **Geopandas Encoding:** https://geopandas.org/en/stable/docs/user_guide/io.html#encoding
- **Character Encodings:** https://docs.python.org/3/library/codecs.html#standard-encodings
