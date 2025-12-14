# Scoring Calculations Fix Summary

## Issues Fixed

Three critical scoring calculation issues have been resolved in `hub_demand_processor.py`:

### 1. **Num_Modes** - All showing 0

**Problem:**
- Calculated as `len(Mode_Planned)` which counts modes in the list
- Did not account for whether those modes actually have lines

**Solution:**
- Now counts mode-specific line columns (e.g., 'BRT Lines', 'Metro Lines', etc.) that have values > 0
- Uses `count_positive_mode_lines()` function
- Example: If hub has 2 in 'BRT Lines' and 3 in 'LRT Lines', Num_Modes = 2

**Code Location:** `hub_demand_processor.py:536-542, 595`

### 2. **score** - All showing 0 (or not calculated)

**Problem:**
- Mode service score was not being calculated at all in the hub_demand_processor

**Solution:**
- Now calculates weighted score based on:
  - Line count for each mode
  - Mode weight (from CLAUDE.md specification)
  - Diversity bonus (10% per additional mode)
- Formula: `score = Σ(line_count × mode_weight) × (1 + 0.1 × (Num_Modes - 1))`
- Mode weights:
  - HighSpeed Rail: 8.0
  - Rail/Interurban Rail: 7.0
  - Suburban Rail: 6.0
  - Metro: 5.0
  - LRT: 4.0
  - BRT: 3.0
  - Cable Line/Bus: 2.0
  - Funicular: 1.0

**Code Location:** `hub_demand_processor.py:514-561, 598`

### 3. **RegionLocation** - All showing 1

**Problem:**
- RegionLocation was not being calculated, or was using incorrect logic
- Should be `Region_category × Location_category`

**Solution:**
- Now properly calculates:
  - **Region_category**: 0 for Tel Aviv/Center, 1 for periphery
  - **Location_category**: 3 for Core (גלעין), 2 for Ring (טבעת), 1 for other
  - **RegionLocation**: Product of the two
- Checks 'area' column for region determination
- Checks 'location' column for metropolitan position
- Example: Tel Aviv Core = 0 × 3 = 0, Haifa Ring = 1 × 2 = 2

**Code Location:** `hub_demand_processor.py:563-612`

## Files Modified

1. **hub_demand_processor.py**
   - Added MODE_WEIGHTS dictionary (lines 514-527)
   - Added MODE_LINE_COLS list (lines 529-534)
   - Added `count_positive_mode_lines()` function (lines 536-542)
   - Added `calculate_mode_score()` function (lines 544-561)
   - Added `get_region_category()` function (lines 563-575)
   - Added `get_location_category()` function (lines 577-592)
   - Added calculations for all three scoring columns (lines 595-612)
   - Added debug output (lines 614-619)
   - Added 'location' to spatial columns aggregation (line 501)

2. **scripts/test_scoring_fixes.py** (NEW)
   - Test script to validate calculations
   - Can be run to verify all three fixes work correctly

## How to Verify the Fixes

### Option 1: Run the Test Script

```bash
cd /home/user/HubPrioritizing
python scripts/test_scoring_fixes.py
```

Expected output: All tests should pass with ✓ marks

### Option 2: Re-process Your Data

1. Re-run the pipeline with your actual data
2. Check the debug output during processing:
   ```
   ✓ Calculated scoring columns:
      Num_Modes: min=1, max=4, mean=2.15
      score: min=3.00, max=45.50, mean=18.23
      RegionLocation: min=0, max=3, mean=1.35
      Hubs by Num_Modes: {1: 45, 2: 78, 3: 32, 4: 5}
   ```
3. Inspect the output CSV to verify:
   - `Num_Modes` has values > 0 for hubs with multiple modes
   - `score` has varied values reflecting mode diversity and line counts
   - `RegionLocation` has varied values (0, 1, 2, or 3) based on location

### Option 3: Manual Spot Check

Pick a few hubs from your data and manually verify:

**Example Hub:**
- BRT Lines: 2
- Metro Lines: 1
- All other modes: 0

**Expected Values:**
- Num_Modes: 2 (two mode-specific columns > 0)
- score: (2 × 3) + (1 × 5) = 11, then 11 × (1 + 0.1 × 1) = 12.1
- RegionLocation: Depends on 'area' and 'location' columns

## Expected Impact on Results

After applying these fixes, you should see:

1. **Num_Modes distribution:**
   - Most hubs: 1-3 modes
   - Large interchange hubs: 3-5 modes
   - No more "all zeros"

2. **score distribution:**
   - Range: approximately 3.0 to 60.0
   - Higher scores for hubs with:
     - More lines
     - Higher-weight modes (Rail, Metro)
     - Greater mode diversity
   - No more "all zeros"

3. **RegionLocation distribution:**
   - Tel Aviv Core: 0 (0 × 3)
   - Tel Aviv Ring: 0 (0 × 2)
   - Periphery Core: 3 (1 × 3)
   - Periphery Ring: 2 (1 × 2)
   - Periphery Other: 1 (1 × 1)
   - No more "all ones"

4. **score_norm (downstream impact):**
   - Will now vary properly (1-10 scale per hub type)
   - No more "all 5.5" due to all zeros in input

## Dependencies

The fix requires these columns to be present in the input data:

**Required:**
- Mode-specific line columns: 'BRT Lines', 'LRT Lines', 'Metro Lines', etc.

**Optional (but recommended):**
- 'area': For regional categorization (default: periphery if missing)
- 'location': For metro position categorization (default: periphery if missing)

If these columns are missing, the calculations will use defaults but won't be fully accurate.

## Next Steps

1. ✅ Fixes have been committed and pushed to branch `claude/fix-scoring-calculations-fOnHv`
2. 📋 Re-run your data processing pipeline to generate updated results
3. 🔍 Verify the output has varied values for Num_Modes, score, and RegionLocation
4. 📊 Compare before/after results to see the impact on final rankings

## Questions or Issues?

If you encounter any problems:
1. Check that your input data has the mode-specific line columns
2. Verify 'area' and 'location' columns exist and have proper values
3. Run the test script to validate the calculation logic
4. Check the debug output during processing for statistics

The fixes follow the methodology specified in CLAUDE.md and match the notebook logic from `complete_hub_scoring_pipeline.ipynb`.
