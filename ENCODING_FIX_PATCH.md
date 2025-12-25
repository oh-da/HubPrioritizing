# Encoding Fix for Step 2.3: Hub Area Tagging

## Problem Description

Hebrew text in the `area` and `location` columns is appearing as garbled characters (e.g., `'¬–¥–ª–™–__'` instead of proper Hebrew). This prevents proper matching with the `AREA_TO_REGION` dictionary in Step 2.6, causing demand matching to fail.

## Root Cause

The shapefiles (metro.shp and districts.shp) are encoded in Windows-1255 or ISO-8859-8 (common for Hebrew data), but the encoding detection is not working correctly, causing the text to be read with the wrong encoding.

## Solution

### Step 1: Diagnose the Encoding Issue

Run the diagnostic script to identify the correct encoding for your shapefiles:

```bash
python scripts/diagnose_encoding.py
```

This will:
1. Try multiple encodings (Windows-1255, CP1255, ISO-8859-8, UTF-8, auto-detect)
2. Show you exactly what text is being read with each encoding
3. Validate whether Hebrew characters are properly decoded
4. Help you identify the correct encoding

### Step 2: Apply the Fix in the Notebook

#### Option A: Automatic Encoding Detection (Recommended)

Add this code cell **BEFORE Step 2.3** in the notebook:

```python
# ============================================================================
# ENCODING FIX: Import improved encoding detection
# ============================================================================
from src.utils.encoding_fix import (
    read_shapefile_with_encoding,
    is_valid_hebrew_text,
    validate_hebrew_in_gdf
)

print("✓ Loaded improved encoding detection utilities")
```

Then **replace** the existing `read_shapefile_with_encoding()` function definition in Step 2.3 with:

```python
# REMOVED: Local function definition
# Now using imported version from src.utils.encoding_fix
```

The imported version has improved validation that:
- More strictly checks for gibberish patterns (many special characters, no Hebrew)
- Provides better diagnostic output showing exactly what's being read
- Validates that at least 30% of characters are in the Hebrew Unicode range

#### Option B: Manual Encoding Override (If you know the correct encoding)

If you've run the diagnostic script and identified the correct encoding, you can force it by adding this to the **MASTER CONFIGURATION** section (cell after imports):

```python
# ============================================================================
# ENCODING OVERRIDE (Optional)
# ============================================================================
# If you know the correct encoding, specify it here to skip auto-detection
FORCE_METRO_ENCODING = 'windows-1255'      # or 'cp1255', 'ISO-8859-8', 'utf-8', None
FORCE_DISTRICTS_ENCODING = 'windows-1255'  # or 'cp1255', 'ISO-8859-8', 'utf-8', None

print(f"Encoding overrides:")
print(f"  Metro: {FORCE_METRO_ENCODING or 'auto-detect'}")
print(f"  Districts: {FORCE_DISTRICTS_ENCODING or 'auto-detect'}")
```

Then modify the shapefile loading calls in Step 2.3:

```python
# Load metro shapefile with forced encoding
metro_hebrew_cols = ['METRO_NAME', 'ZONE_NAME', 'MetroName', 'ZoneName', 'NAME', 'SHEM']
metro_gdf, metro_encoding = read_shapefile_with_encoding(
    METRO_SHP,
    name="metro",
    hebrew_columns=metro_hebrew_cols,
    force_encoding=FORCE_METRO_ENCODING  # ADD THIS LINE
)

# Load districts shapefile with forced encoding
districts_hebrew_cols = ['MACHOZ', 'SHEM_MACHOZ', 'SHEM_NAFA', 'District', 'NAME', 'SHEM']
districts_gdf, districts_encoding = read_shapefile_with_encoding(
    DISTRICTS_SHP,
    name="districts",
    hebrew_columns=districts_hebrew_cols,
    force_encoding=FORCE_DISTRICTS_ENCODING  # ADD THIS LINE
)
```

### Step 3: Verify the Fix

After applying the fix, re-run Step 2.3 and check the output:

```
Metro values: [...]
Zone values: [...]
area samples: [...]
location samples: [...]
```

**Verify that:**
1. ✅ Hebrew text appears correctly (not gibberish)
2. ✅ The encoding detection shows which encoding was used
3. ✅ The Hebrew validation passes (no "gibberish detected" errors)
4. ✅ Area and location columns are populated with proper Hebrew

### Step 4: Verify Downstream Impact

After fixing the encoding, verify that Step 2.6 (demand matching) works correctly:

```python
# Check that area values match AREA_TO_REGION keys
print("Area values in data:")
print(gdf_demand['area'].value_counts())

print("\nArea keys in AREA_TO_REGION:")
print(list(AREA_TO_REGION.keys()))

# Check for mismatches
areas_in_data = set(gdf_demand['area'].dropna().unique())
areas_in_dict = set(AREA_TO_REGION.keys())

missing_in_dict = areas_in_data - areas_in_dict
if missing_in_dict:
    print(f"\n⚠️  Areas in data but not in AREA_TO_REGION:")
    for area in missing_in_dict:
        print(f"  - '{area}'")
else:
    print("\n✓ All areas in data are found in AREA_TO_REGION")
```

## Alternative: Post-Processing Fix

If the encoding cannot be fixed at load time, you can normalize the area values after the spatial join:

```python
# After the spatial join in Step 2.3
print("\nNormalizing area values...")

# Create a mapping from garbled to correct Hebrew
# (You'll need to manually create this based on your data)
AREA_NORMALIZATION = {
    "'¬–¥–ª–™–__'": "תל אביב",
    # Add more mappings as needed
}

# Apply normalization
gdf_demand['area'] = gdf_demand['area'].replace(AREA_NORMALIZATION)

print(f"✓ Normalized {len(AREA_NORMALIZATION)} area values")
print(f"Area values after normalization: {gdf_demand['area'].value_counts()}")
```

## Files Modified

1. **Created:** `src/utils/encoding_fix.py` - Improved encoding detection utilities
2. **Created:** `scripts/diagnose_encoding.py` - Diagnostic script for encoding issues
3. **Modified:** `COMPLETE_TRANSIT_PIPELINE.ipynb` - Apply one of the solutions above

## Testing

After applying the fix:

1. ✅ Run the diagnostic script to verify correct encoding detection
2. ✅ Re-run Step 2.3 and verify Hebrew text is readable
3. ✅ Check that area/location columns are properly populated
4. ✅ Verify Step 2.6 demand matching works correctly
5. ✅ Check final hub data has TotalDemand > 0 for hubs that should have demand

## Additional Resources

- **Hebrew Unicode Range:** U+0590 to U+05FF
- **Common Hebrew Encodings:**
  - `windows-1255` (Windows Hebrew)
  - `cp1255` (Code Page 1255, similar to windows-1255)
  - `ISO-8859-8` (Latin/Hebrew)
  - `utf-8` (Universal, but shapefiles often don't use it)

- **Geopandas Encoding:** https://geopandas.org/en/stable/docs/user_guide/io.html#encoding

## Contact

If you continue to experience encoding issues after applying these fixes, please:
1. Save the output of `scripts/diagnose_encoding.py`
2. Share a sample of the garbled text you're seeing
3. Share the shapefile metadata (if possible)
