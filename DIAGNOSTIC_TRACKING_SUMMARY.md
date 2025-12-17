# Area/Location Data Diagnostic Tracking

## Overview
Added diagnostic checkpoints at 4 critical stages in the pipeline to track where `area` and `location` column data is being lost or corrupted.

## Diagnostic Locations

### 1. **After Step 2.3 (Spatial Tagging)** - Cell 30
**Location**: Line ~311, before the `else:` statement
**Purpose**: Verify that spatial tagging from shapefiles worked correctly
**Checks**:
- `gdf_demand` shape
- `area` column existence and non-null count
- `area` unique values (first 5)
- `location` column existence and non-null count
- `location` sample values (first 3)

**What to look for**:
- Are area/location columns populated after spatial join?
- Do the values look correct (not truncated Hebrew text)?
- How many rows have non-null values?

---

### 2. **After Step 2.7 (Hub Aggregation)** - Cell 44
**Location**: Line ~104, before "Step 2.7 complete!"
**Purpose**: Verify that grouping/aggregation preserved area/location data
**Checks**:
- `grouped_hubs` shape
- All columns in the dataframe
- `area` column existence, dtype, non-null count, unique values
- `location` column existence, dtype, non-null count, sample values

**What to look for**:
- Did the columns survive the aggregation operation?
- Are the data types correct (should be object/string)?
- Are values still present and not null?
- Did the aggregation logic (`.first()` or similar) work correctly?

---

### 3. **In Step 2.8 (CSV Export)** - Cell 50
**Location**: Line ~14, after `export_grouped = grouped_hubs.copy()`
**Purpose**: Verify what's being written to CSV before export
**Checks**:
- All columns in `export_grouped`
- `area` column presence and sample values
- `location` column presence and sample values

**What to look for**:
- Are area/location in the columns list?
- Do the sample values look correct?
- This is the LAST checkpoint before writing to disk

---

### 4. **In Step 4.2 (Scoring Data Load)** - Cell 69
**Location**: Line ~3, after `df_scoring = INPUT_FOR_SCORING.copy()`
**Purpose**: Verify what was loaded from CSV for scoring
**Checks**:
- `df_scoring` shape
- All columns loaded from CSV
- `area` column existence, dtype, non-null count, sample values
- `location` column existence, dtype, non-null count, sample values

**What to look for**:
- Are area/location columns present after loading?
- Did the CSV read operation preserve the data?
- Are the data types correct after loading?
- Are values present or all null?

---

## How to Use These Diagnostics

1. **Run the notebook** from the beginning through at least Step 4.2

2. **Look for "DIAGNOSTIC" sections** in the output - each will be clearly labeled:
   - `DIAGNOSTIC - After Step 2.3:`
   - `DIAGNOSTIC - After Step 2.7 Aggregation:`
   - `DIAGNOSTIC - Before Step 2.8 CSV Export:`
   - `DIAGNOSTIC - After Step 4.1 CSV Read:`

3. **Compare the outputs** to identify where data is lost:
   - If area/location are populated in Step 2.3 but missing in 2.7 → **Aggregation issue**
   - If present in 2.7 but missing in 2.8 → **Export preparation issue**
   - If present in 2.8 but missing in 4.2 → **CSV read/write issue**
   - If missing from 2.3 onwards → **Spatial tagging issue**

4. **Check specific issues**:
   - **All null values**: Spatial join likely failed
   - **Column missing entirely**: Dropped during aggregation or not saved to CSV
   - **Wrong data type**: Encoding or serialization issue
   - **Empty strings**: Data corruption during save/load

## Expected Output Format

Each diagnostic will print structured information like this:

```
  DIAGNOSTIC - After Step 2.3:
    gdf_demand shape: (155, 25)
    'area' column exists: True
    'area' non-null count: 140/155
    'area' unique values (first 5): ['תל אביב', 'חיפה', 'ירושלים', 'באר שבע', 'Unknown']
    'location' column exists: True
    'location' non-null count: 140/155
    'location' sample values: [['מרכז'], ['צפון'], ['דרום']]
```

## Next Steps After Running Diagnostics

1. **Capture all diagnostic output** from the notebook run
2. **Identify the last stage where data is present**
3. **Focus investigation on the next stage** where data disappears
4. **Check the specific code** between those two stages for:
   - Column dropping
   - Aggregation methods that lose data
   - DataFrame operations that exclude columns
   - CSV export/import settings

## File Modified

- `/home/user/HubPrioritizing/COMPLETE_TRANSIT_PIPELINE.ipynb`
  - Cell 30: Added 13 diagnostic lines
  - Cell 44: Added 16 diagnostic lines
  - Cell 50: Added 11 diagnostic lines
  - Cell 69: Added 16 diagnostic lines

## Notes

- All diagnostics use try-safe patterns (check if column exists before accessing)
- Diagnostics are clearly marked with `# DIAGNOSTIC:` comments
- Output is indented and formatted for easy visual scanning
- Sample values are limited (3-5) to avoid cluttering output

---

**Created**: 2025-12-17
**Purpose**: Track area/location column data loss in hub prioritization pipeline
