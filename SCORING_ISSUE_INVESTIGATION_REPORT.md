# Scoring Issue Investigation Report
**Date:** 2025-12-14
**File:** COMPLETE_TRANSIT_PIPELINE.ipynb (Part 4 - Scoring)

---

## Executive Summary

Three critical scoring columns are producing incorrect values:
1. **RegionLocation**: All values = 1 (should vary by location)
2. **score** (Mode Score): All values = 0 (should reflect mode diversity)
3. **Num_Modes**: All values = 0 (should count transit modes)

**Root Cause:** The pipeline is missing data processing steps that create required input columns for scoring calculations.

---

## Detailed Analysis

### Issue 1: RegionLocation = 1 for All Rows

**Location in Code:** Step 4.2 (lines 7129-7139)

**Current Logic:**
```python
if 'area' in df_scoring.columns:
    df_scoring['Region_category'] = df_scoring['area'].apply(get_region_category)
else:
    df_scoring['Region_category'] = 1  # Default

if 'location' in df_scoring.columns:
    df_scoring['Location_category'] = df_scoring['location'].apply(get_location_category)
else:
    df_scoring['Location_category'] = 1  # Default

df_scoring['RegionLocation'] = df_scoring['Region_category'] * df_scoring['Location_category']
```

**Problem:**
- The **'location' column does NOT exist** in the data from Parts 1-3
- Therefore, `Location_category` defaults to 1 for all rows
- `RegionLocation = Region_category * 1 = Region_category`
- If all areas are the same or defaults apply, RegionLocation = 1 for all

**Evidence:**
- Part 2 Step 2.7 aggregation (line 6287-6288) includes 'location' IF it exists in gdf_demand
- But 'location' is never created in Part 2.3 (only 'area' is created via spatial join)
- The old workflow (Group_n_Filter_Hubs.ipynb) shows 'location' column exists in the source CSV with values like:
  - 'גלעין' (Core)
  - 'טבעת חיצונית' (Outer Ring)
  - 'טבעת תיכונה' (Middle Ring)
  - 'צפון' (North - for areas without metro classification)

**Impact:**
- Regional equity scoring fails completely
- Cannot differentiate between core/ring/periphery locations
- All hubs receive identical location-based scores

---

### Issue 2: score (Mode Score) = 0 for All Rows

**Location in Code:** Step 4.3 (lines 7179-7193)

**Current Logic:**
```python
MODE_LINE_COLS = [
    'BRT Lines', 'Cable Line Lines', 'Funicular Lines',
    'HighSpeed Rail Lines', 'Interurban Rail Lines', 'LRT Lines',
    'Metro Lines', 'Suburban Rail Lines'
]

def calculate_mode_score(row):
    """Calculate mode diversity and service score."""
    score = 0
    for col in MODE_LINE_COLS:
        if col in row.index and pd.notna(row[col]) and row[col] > 0:
            # Add weighted score based on mode type and line count
            score += calculate_mode_weight(col) * row[col]
    return score

df_scoring['score'] = df_scoring.apply(calculate_mode_score, axis=1)
```

**Problem:**
- **MODE_LINE_COLS do NOT exist** in the data from Parts 1-3
- Part 1 creates only: h3_index, node, Mode_Planned (list), Line_Nunique, Line_Unique (list)
- Part 2 aggregates these columns but never creates mode-specific line count columns
- Therefore, all mode score calculations return 0

**Evidence:**
- Part 2 Step 2.7 (lines 6295-6310) tries to count Num_Modes using MODE_LINE_COLS
- But these columns don't exist, so Num_Modes also = 0
- The old workflow (Group_n_Filter_Hubs.ipynb) shows these columns exist in source data:
  - 'BRT Lines': 0
  - 'LRT Lines': 2
  - 'Metro Lines': 0
  - etc.

**Impact:**
- Mode diversity scoring fails completely
- Cannot differentiate between single-mode and multi-modal hubs
- All hubs receive score = 0 regardless of service level

---

### Issue 3: Num_Modes = 0 for All Rows

**Location in Code:** Part 2 Step 2.7 (lines 6295-6310)

**Current Logic:**
```python
MODE_LINE_COLS = [
    'BRT Lines', 'Cable Line Lines', 'Funicular Lines',
    'HighSpeed Rail Lines', 'Interurban Rail Lines', 'LRT Lines',
    'Metro Lines', 'Suburban Rail Lines'
]

def count_positive_mode_lines(row):
    """Count how many mode-specific line columns have values > 0."""
    count = 0
    for col in MODE_LINE_COLS:
        if col in row.index and pd.notna(row[col]) and row[col] > 0:
            count += 1
    return count

grouped['Num_Modes'] = grouped.apply(count_positive_mode_lines, axis=1)
```

**Problem:**
- Same root cause as Issue 2: MODE_LINE_COLS don't exist
- All counts return 0

**Impact:**
- Cannot filter hubs by mode count
- Cannot identify multi-modal hubs
- Eligibility filtering (requires ≥2 modes) may fail

---

## Missing Data Processing Steps

The pipeline needs to create these columns that are currently missing:

### 1. Mode-Specific Line Count Columns

**Should be created from existing Mode_Planned and Line_Unique columns**

**Required Logic:**
```python
# After Part 1 grouping, before Part 2 grouping
# For each row, count lines per mode type

# Example for a hub with Mode_Planned = ['Metro', 'Bus'] and multiple lines:
# - Count Metro lines -> 'Metro Lines' = 2
# - Count Bus lines -> 'Bus Lines' = 5
# - All other mode columns = 0

MODE_MAPPING = {
    'BRT': 'BRT Lines',
    'Metro': 'Metro Lines',
    'LRT': 'LRT Lines',
    'Light Rail': 'LRT Lines',
    'Rail': 'Interurban Rail Lines',
    'Interurban Rail': 'Interurban Rail Lines',
    'HighSpeed Rail': 'HighSpeed Rail Lines',
    'Suburban Rail': 'Suburban Rail Lines',
    'Cable Line': 'Cable Line Lines',
    'Funicular': 'Funicular Lines',
}

# Initialize all mode columns to 0
for col in MODE_LINE_COLS:
    df[col] = 0

# For each row, parse Mode_Planned and Line_Unique to fill in mode-specific counts
# This requires understanding which lines belong to which modes
```

**Challenge:** The current data structure has:
- `Mode_Planned`: List of modes (e.g., ['Metro', 'Bus'])
- `Line_Unique`: List of ALL line names (e.g., ['M1_North', 'M1_South', 'Bus_101', 'Bus_102'])

**Missing:** Mapping between line names and modes. We need to either:
1. Parse line names to infer mode (e.g., 'M1' = Metro, 'L1' = LRT)
2. Join with the Lines_and_Planned_Mode data to get mode for each line
3. Or restructure to track lines per mode during initial aggregation

---

### 2. Location Column (Metropolitan Position)

**Should indicate Core / Ring / Periphery for each hub**

**Possible Sources:**
1. **Spatial join with metropolitan area shapefile** (similar to how 'area' is created)
   - Load shapefile with metropolitan zones
   - Each zone has attribute: Core (גלעין) / Ring (טבעת) / Outer (חיצונית)
   - Spatial join to assign location to each hub

2. **Derive from 'area' column**
   - Areas without metro systems: default to 'Periphery'
   - Areas with metro: need additional data for core/ring classification

3. **Manual mapping**
   - Create a dictionary mapping area names to locations
   - Example: {'תל אביב': 'גלעין', 'חיפה': 'טבעת', 'באר שבע': 'פריפריה'}

**Required Output:**
- Column name: 'location'
- Values: List (like 'area') containing location classifications
  - 'גלעין' or 'Core' (highest weight = 3)
  - 'טבעת' or 'Ring' (weight = 2)
  - Other / Periphery (weight = 1)

---

## Required Code Changes

### Change 1: Add Mode-Specific Line Column Creation

**Location:** After Part 1, before Part 2 Step 2.7

**New code cell to insert:**

```python
# ============================================================================
# NEW STEP: Create Mode-Specific Line Count Columns
# ============================================================================
print("\n" + "="*80)
print("Creating mode-specific line count columns...")
print("="*80)

# This step creates columns like 'BRT Lines', 'Metro Lines', etc.
# by analyzing the Mode_Planned and Line_Unique data

# First, we need to map each line to its mode
# Option 1: Re-join with Lines_and_Planned_Mode data
# Option 2: Parse line names (if they follow patterns like 'metro_1', 'brt_2', etc.)
# Option 3: Use the existing Mode_Planned list to infer

# For now, use a WORKAROUND: Count modes from Mode_Planned and distribute lines
# This is approximate but allows the pipeline to run

MODE_LINE_COLS = [
    'BRT Lines', 'Cable Line Lines', 'Funicular Lines',
    'HighSpeed Rail Lines', 'Interurban Rail Lines', 'LRT Lines',
    'Metro Lines', 'Suburban Rail Lines'
]

# Initialize all mode-specific line columns to 0
for col in MODE_LINE_COLS:
    gdf_h3[col] = 0

# WORKAROUND: For each hub, if a mode exists in Mode_Planned,
# assume at least 1 line for that mode
# Better solution: track lines per mode during initial aggregation

MODE_TO_COLUMN = {
    'BRT': 'BRT Lines',
    'Metro': 'Metro Lines',
    'LRT': 'LRT Lines',
    'Light Rail': 'LRT Lines',
    'Rail': 'Interurban Rail Lines',
    'Interurban Rail': 'Interurban Rail Lines',
    'HighSpeed Rail': 'HighSpeed Rail Lines',
    'Suburban Rail': 'Suburban Rail Lines',
    'Cable Line': 'Cable Line Lines',
    'Funicular': 'Funicular Lines',
    'Bus': None,  # Exclude bus from mode line counts
    'Express Bus': None,
}

def create_mode_line_columns(row):
    """Create mode-specific line count columns."""
    mode_counts = {}
    for col in MODE_LINE_COLS:
        mode_counts[col] = 0

    # Get modes for this row
    modes = row['Mode_Planned'] if isinstance(row['Mode_Planned'], list) else []
    total_lines = row['Line_Nunique'] if 'Line_Nunique' in row.index else 0

    # Distribute lines among modes (simple approximation)
    valid_modes = [m for m in modes if MODE_TO_COLUMN.get(m)]
    if valid_modes:
        lines_per_mode = max(1, total_lines // len(valid_modes))
        for mode in valid_modes:
            col = MODE_TO_COLUMN.get(mode)
            if col:
                mode_counts[col] = lines_per_mode

    return pd.Series(mode_counts)

# Apply to create columns
mode_line_df = gdf_h3.apply(create_mode_line_columns, axis=1)
for col in MODE_LINE_COLS:
    gdf_h3[col] = mode_line_df[col]

print(f"✓ Created {len(MODE_LINE_COLS)} mode-specific line count columns")
print(f"  Sample mode distribution:")
for col in MODE_LINE_COLS:
    nonzero = (gdf_h3[col] > 0).sum()
    if nonzero > 0:
        print(f"    {col}: {nonzero} hubs with lines")
```

---

### Change 2: Add Location Column Creation

**Location:** Part 2 Step 2.3 (after 'area' column is created)

**New code to add:**

```python
# ============================================================================
# Create 'location' column (metropolitan position: Core/Ring/Periphery)
# ============================================================================
print("\n  Creating 'location' column for metropolitan position...")

# Option 1: If you have a metropolitan zones shapefile
if os.path.exists('/path/to/metro_zones.shp'):
    metro_zones = gpd.read_file('/path/to/metro_zones.shp')
    # Spatial join to get location category
    gdf_demand = gpd.sjoin(gdf_demand, metro_zones[['location_type', 'geometry']],
                           how='left', predicate='intersects')
    gdf_demand = gdf_demand.rename(columns={'location_type': 'location'})
else:
    # Option 2: Simple mapping based on 'area'
    # This is a placeholder - replace with actual location data
    def assign_location(area):
        """Assign metropolitan location based on area."""
        if pd.isna(area):
            return ['Unknown']

        area_str = str(area).strip()

        # Tel Aviv metro area has core/ring structure
        if 'תל אביב' in area_str or 'Tel Aviv' in area_str:
            return ['גלעין']  # Default Tel Aviv to core for now

        # Haifa metro area
        elif 'חיפה' in area_str or 'Haifa' in area_str:
            return ['טבעת']  # Default Haifa to ring

        # Other areas (no metro structure)
        else:
            return [area_str]  # Use area name as location

    gdf_demand['location'] = gdf_demand['area'].apply(assign_location)
    print(f"    ✓ Assigned location based on area (placeholder logic)")
    print(f"    Note: This is simplified - should use actual metro zone data")

print(f"    Location values: {gdf_demand['location'].value_counts().to_dict()}")
```

---

### Change 3: Preserve Columns Through Aggregation

**Location:** Part 2 Step 2.7 aggregation dictionary

**Current code (line 6287-6288):**
```python
for col in ['address', 'area', 'district', 'metro_area', 'location']:
    if col in gdf_demand.columns:
        agg_dict[col] = 'first'
```

**Add mode-specific columns:**
```python
# Add mode-specific line columns to aggregation
for col in MODE_LINE_COLS:
    if col in gdf_demand.columns:
        agg_dict[col] = 'sum'  # Sum lines across grouped hexes
```

---

## Verification Steps

After implementing fixes, verify:

1. **Check column presence:**
   ```python
   print(f"Columns in grouped_hubs: {list(grouped_hubs.columns)}")
   print(f"\nMode columns present: {[c for c in MODE_LINE_COLS if c in grouped_hubs.columns]}")
   print(f"Location column present: {'location' in grouped_hubs.columns}")
   ```

2. **Check value distributions:**
   ```python
   print(f"\nRegionLocation distribution:")
   print(grouped_hubs['RegionLocation'].value_counts())

   print(f"\nNum_Modes distribution:")
   print(grouped_hubs['Num_Modes'].value_counts())

   print(f"\nMode score distribution:")
   print(grouped_hubs['score'].describe())

   # Show sample rows
   print(f"\nSample rows:")
   print(grouped_hubs[['group', 'area', 'location', 'Num_Modes', 'score', 'RegionLocation']].head(10))
   ```

3. **Validate calculations:**
   ```python
   # Check that RegionLocation varies
   assert grouped_hubs['RegionLocation'].nunique() > 1, "RegionLocation should have multiple values"

   # Check that scores are calculated
   assert grouped_hubs['score'].max() > 0, "Mode scores should be > 0 for multi-modal hubs"

   # Check that Num_Modes counts correctly
   assert grouped_hubs['Num_Modes'].max() >= 2, "Should have hubs with 2+ modes"
   ```

---

## Alternative Approach: Load Pre-Processed Data

If creating these columns from scratch is too complex, consider:

**Option:** Load the old grouped_hubs file that already has these columns:
```python
# Instead of running Parts 1-2, load the existing processed data
INPUT_FOR_SCORING = pd.read_csv('/path/to/grouped_hubs_for_filtering_29102025.csv')

# Then convert string columns to lists (as shown in Group_n_Filter_Hubs.ipynb)
# This file already has: mode-specific line columns, location, area, etc.
```

**Pros:**
- Immediate fix - scoring will work
- Preserves exact data from original workflow

**Cons:**
- Not reproducible - relies on external file
- Doesn't fix the pipeline for future runs
- Data may be outdated

---

## Recommended Action Plan

**SHORT TERM (Immediate Fix):**
1. Add placeholder logic for mode-specific columns (distribute lines evenly across modes)
2. Add simple area-based location mapping
3. Test that scoring calculations produce non-zero values

**LONG TERM (Proper Solution):**
1. Restructure Part 1 aggregation to track lines per mode separately
   - Group by h3_index, node, AND Mode_Planned (keep mode separate)
   - Aggregate to get line counts per mode
   - Then pivot to create mode-specific columns

2. Add spatial join with metropolitan zone shapefile for location data
   - Obtain/create shapefile with core/ring/periphery zones
   - Integrate into Part 2.3 spatial joins

3. Document data requirements and sources clearly

---

## Files Analyzed

1. `/home/user/HubPrioritizing/COMPLETE_TRANSIT_PIPELINE.ipynb` - Main pipeline
2. `/home/user/HubPrioritizing/Group_n_Filter_Hubs.ipynb` - Old workflow showing expected data structure
3. `/home/user/HubPrioritizing/HubsCode_to_1_file.ipynb` - Original implementation

---

## Summary

**Root Cause:** Missing data processing steps to create:
- Mode-specific line count columns ('BRT Lines', 'Metro Lines', etc.)
- Location column (metropolitan position: Core/Ring/Periphery)

**Impact:** Three critical scoring columns fail:
- RegionLocation = 1 (all rows)
- score = 0 (all rows)
- Num_Modes = 0 (all rows)

**Solution:** Add code to create these columns from existing Mode_Planned and spatial data

**Priority:** HIGH - Scoring system is completely non-functional without these fixes
