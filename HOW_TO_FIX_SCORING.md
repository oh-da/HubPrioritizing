# How to Fix Scoring Calculation Issues

## Problem Summary

The file `score_hubs_final.xlsx` has incorrect values because the scoring calculations have bugs:
1. **Num_Modes** - all 0 (should count mode-specific line columns > 0)
2. **score** - all 0 (should be weighted mode service score)
3. **RegionLocation** - all 1 (should be Region_category × Location_category)
4. **RegionLocation_Norm** - all 5.5 (because all RegionLocation values are the same)
5. **score_Norm** - all 5.5 (because all score values are the same)

## Solution 1: Fix Existing File (QUICKEST)

If you already have `score_hubs_final.xlsx` and just want to fix it:

```bash
# Navigate to project directory
cd /home/user/HubPrioritizing

# Run the fix script on your file
python scripts/fix_existing_scores.py score_hubs_final.xlsx

# This creates: score_hubs_final_FIXED.xlsx
```

### What the Script Does

The script will:
1. Read your existing Excel/CSV file
2. Recalculate `Num_Modes` by counting mode-specific line columns > 0
3. Recalculate `score` using mode weights and diversity bonus
4. Recalculate `Region_category`, `Location_category`, and `RegionLocation`
5. Recalculate `RegionLocation_Norm` and `score_Norm` per hub type
6. Save the fixed file with `_FIXED` suffix

### Expected Output

```
================================================================================
FIXING SCORING CALCULATIONS
================================================================================

Input file: score_hubs_final.xlsx

1. Reading file...
   ✓ Loaded 86 rows, 45 columns

2. Checking for required columns...
   ✓ Mode line columns: Found
   ✓ area column: Found
   ✓ location column: Found
   ✓ HubType column: Found

3. Calculating Num_Modes...
   ✓ Calculated Num_Modes
      Range: 1 - 4
      Mean: 2.15
      Distribution: {1: 12, 2: 48, 3: 20, 4: 6}

4. Calculating mode service score...
   ✓ Calculated score
      Range: 3.00 - 52.80
      Mean: 18.45

5-8. [More calculations...]

================================================================================
✅ SCORING CALCULATIONS FIXED!
================================================================================

Fixed columns:
  • Num_Modes: 1-4 (was all 0)
  • score: 3.0-52.8 (was all 0)
  • RegionLocation: 0-3 (was all 1)
  • RegionLocation_Norm: 1.0-10.0 (was all 5.5)
  • score_Norm: 1.0-10.0 (was all 5.5)

Output file: score_hubs_final_FIXED.xlsx
================================================================================
```

---

## Solution 2: Fix the Pipeline (PERMANENT FIX)

To prevent this issue from happening again, you need to fix the notebook that generates the file.

### Fix COMPLETE_TRANSIT_PIPELINE.ipynb

The issues are in the notebook. You need to update **3 places**:

#### Issue 1: Num_Modes Calculation (Line ~1364)

**FIND THIS CODE** in Part 2 (creating grouped hubs):
```python
grouped['Num_Modes'] = grouped['Mode_Planned'].apply(
    lambda x: len(x) if isinstance(x, list) else 1
)
```

**REPLACE WITH:**
```python
# MODE LINE COLUMNS to check
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

#### Issue 2: Mode Score Calculation (Step 4.3)

**FIND THIS CODE** in Step 4.3:
```python
# Calculate mode score (if this cell exists with simplified calculation)
```

**ADD THIS CODE** in Step 4.3 (before normalization):
```python
# MODE WEIGHTS for scoring
MODE_WEIGHTS = {
    'Funicular': 1.0,
    'Cable Line': 2.0,
    'BRT': 3.0,
    'LRT': 4.0,
    'Metro': 5.0,
    'Suburban Rail': 6.0,
    'Interurban Rail': 7.0,
    'HighSpeed Rail': 8.0,
    'Rail': 7.0,
    'Express Bus': 3.0,
    'Bus': 2.0,
}

def calculate_mode_score(row):
    """Calculate mode service score with mode weights and diversity bonus."""
    score = 0.0
    alpha = 0.1  # Diversity bonus factor

    # Calculate score for each mode
    for mode, weight in MODE_WEIGHTS.items():
        column_name = f'{mode} Lines'
        if column_name in row.index and pd.notna(row[column_name]) and row[column_name] > 0:
            score += row[column_name] * weight

    # Apply diversity bonus
    n_modes = row.get('Num_Modes', 1)
    if pd.notna(n_modes) and n_modes > 0:
        score = score * (1 + alpha * (n_modes - 1))

    return score

df_scoring['score'] = df_scoring.apply(calculate_mode_score, axis=1)
```

#### Issue 3: RegionLocation Calculation (Step 4.2 or 4.3)

**ADD THIS CODE** before normalization:
```python
def get_region_category(area):
    """Map area to region category: 0=Tel Aviv/Center, 1=Periphery."""
    if pd.isna(area):
        return 1
    area_str = str(area).strip()
    if any(keyword in area_str for keyword in ['תל אביב', 'Tel Aviv', 'מרכז', 'Center']):
        return 0
    return 1

def get_location_category(location):
    """Map location to metro position: 3=Core, 2=Ring, 1=Other."""
    if pd.isna(location):
        return 1
    location_str = str(location).strip()
    if 'גלעין' in location_str or 'Core' in location_str:
        return 3
    elif 'טבעת' in location_str or 'Ring' in location_str:
        return 2
    else:
        return 1

# Calculate categories
if 'area' in df_scoring.columns:
    df_scoring['Region_category'] = df_scoring['area'].apply(get_region_category)
else:
    df_scoring['Region_category'] = 1

if 'location' in df_scoring.columns:
    df_scoring['Location_category'] = df_scoring['location'].apply(get_location_category)
else:
    df_scoring['Location_category'] = 1

# Calculate RegionLocation
df_scoring['RegionLocation'] = df_scoring['Region_category'] * df_scoring['Location_category']
```

---

## Solution 3: Use Fixed hub_demand_processor.py

If you're using the Python pipeline (not the notebook), my fixes are already in `hub_demand_processor.py`. Just run:

```bash
python scripts/run_complete_pipeline.py
```

The fixed code will:
- Calculate Num_Modes correctly (counting mode-specific columns > 0)
- Calculate score correctly (with mode weights and diversity bonus)
- Calculate RegionLocation correctly (Region_category × Location_category)

---

## Verification

After fixing (either method), verify the results:

### Check Num_Modes
```python
print(df['Num_Modes'].value_counts().sort_index())
```
**Expected:** Values ranging from 1-5, not all 0

### Check score
```python
print(f"score range: {df['score'].min():.1f} - {df['score'].max():.1f}")
```
**Expected:** Range like 3.0 - 60.0, not all 0

### Check RegionLocation
```python
print(df['RegionLocation'].value_counts().sort_index())
```
**Expected:** Values 0, 1, 2, or 3, not all 1

### Check Normalized Scores
```python
print(f"score_Norm range: {df['score_Norm'].min():.1f} - {df['score_Norm'].max():.1f}")
print(f"RegionLocation_Norm range: {df['RegionLocation_Norm'].min():.1f} - {df['RegionLocation_Norm'].max():.1f}")
```
**Expected:** Values from 1.0 to 10.0, not all 5.5

---

## Understanding the Fixes

### 1. Num_Modes (was wrong)
- **Before:** `len(Mode_Planned)` = counts modes in list
- **After:** Counts mode-specific columns with values > 0
- **Why:** Hub with ['BRT', 'Metro'] but only 'BRT Lines' = 2 should have Num_Modes = 1

### 2. score (was missing)
- **Before:** Not calculated, defaulted to 0
- **After:** `Σ(line_count × mode_weight) × (1 + 0.1 × (Num_Modes - 1))`
- **Example:** 2 BRT lines + 1 Metro line = (2×3 + 1×5) × 1.1 = 12.1

### 3. RegionLocation (was oversimplified)
- **Before:** All set to 1 or not calculated
- **After:** Region_category (0 or 1) × Location_category (1, 2, or 3)
- **Examples:**
  - Tel Aviv Core: 0 × 3 = 0
  - Haifa Ring: 1 × 2 = 2
  - Periphery Core: 1 × 3 = 3

---

## Quick Command Reference

```bash
# Fix existing file
python scripts/fix_existing_scores.py score_hubs_final.xlsx

# Fix with custom output
python scripts/fix_existing_scores.py input.xlsx -o output.xlsx

# Run the full pipeline (if using Python version)
python scripts/run_complete_pipeline.py

# Test the calculations
python scripts/test_scoring_fixes.py
```

---

## Need Help?

1. **Script fails:** Check that your file has the mode-specific line columns (e.g., 'BRT Lines', 'Metro Lines')
2. **Still getting 5.5:** The normalized scores will be 5.5 if all raw scores are identical - make sure raw scores were recalculated
3. **Different results:** Verify you have 'area' and 'location' columns in your data

All fixes are committed to branch: `claude/fix-scoring-calculations-fOnHv`
