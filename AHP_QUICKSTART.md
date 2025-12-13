# AHP Scoring Quick Start

**Analytic Hierarchy Process (AHP) for Hub Prioritization**

---

## What is AHP?

AHP is an optional scoring methodology that complements the existing Monte Carlo approach by using **expert-driven pairwise comparisons** to determine criterion weights.

**Key Advantages:**
- ✅ Transparent and reproducible
- ✅ Expert knowledge incorporated
- ✅ Built-in consistency checking
- ✅ Runs alongside Monte Carlo for comparison
- ✅ No replacement of existing scoring

---

## Quick Usage

### 1. Enable AHP in Configuration

Edit `src/config.py`:

```python
# Enable AHP scoring alongside Monte Carlo
AHP_ENABLED = True  # Change from False to True
```

### 2. Create Expert Comparison CSV

Run in Python:

```python
from src.scoring import create_expert_template_csv

create_expert_template_csv(
    output_path='data/ahp_expert_comparisons.csv',
    criteria_names=[
        'activity_score',
        'service_score',
        'location_score',
        'pop_jobs_score',
        'terminal_score'
    ],
    n_experts=3,
    format='long'
)
```

Or use the existing template:
```bash
cp data/ahp_expert_comparisons_TEMPLATE.csv data/ahp_expert_comparisons.csv
```

### 3. Expert Input

Have experts fill in pairwise comparisons using the **Saaty scale (1-9)**:

| Value | Meaning |
|-------|---------|
| 1 | Equal importance |
| 3 | Moderate importance |
| 5 | Strong importance |
| 7 | Very strong importance |
| 9 | Extreme importance |

**Example CSV:**
```csv
expert,criterion_a,criterion_b,value
expert1,activity_score,service_score,3
expert1,activity_score,location_score,5
```

Where `value = 3` means criterion_a is **moderately more important** than criterion_b.

### 4. Run Scoring Pipeline

```python
from src.scoring import run_complete_scoring_pipeline
import geopandas as gpd

# Load your hubs
gdf = gpd.read_file('data/hubs.geojson')

# Run pipeline (now includes both Monte Carlo and AHP)
gdf_final = run_complete_scoring_pipeline(
    gdf,
    tier_column='tier',
    enable_ahp=True  # Optional: can override config
)

# Results include:
# - final_score (Monte Carlo)
# - ahp_score (AHP)
# - rank
# - ahp_rank
```

---

## Example Expert Input

See `data/ahp_expert_comparisons_example.csv` for a realistic example with 3 experts:
- **transport_planner**: Prioritizes ridership and service
- **urban_economist**: Prioritizes development potential
- **accessibility_expert**: Prioritizes network integration

---

## Interpreting Results

### Consistency Checking

Each expert's consistency is automatically validated:

```
Expert 'transport_planner': CR = 0.067 ✓
Expert 'urban_economist': CR = 0.045 ✓
Expert 'accessibility_expert': CR = 0.112 ✗ (inconsistent)
```

**CR < 0.10** = Acceptable consistency ✓

### Comparing Monte Carlo vs AHP

```python
from src.scoring import compare_monte_carlo_vs_ahp

comparison = compare_monte_carlo_vs_ahp(gdf_final)

# Shows:
# - Score correlation
# - Rank correlation
# - Top N overlap
# - Largest disagreements
```

---

## File Structure

```
data/
├── ahp_expert_comparisons_TEMPLATE.csv  # Blank template
├── ahp_expert_comparisons_example.csv   # Example with data
└── ahp_expert_comparisons.csv           # YOUR expert input here

src/scoring/
├── ahp.py                               # AHP implementation
├── monte_carlo.py                       # Integrated scoring pipeline
└── __init__.py                          # Exports both methods

docs/
└── AHP_SCORING_GUIDE.md                 # Full documentation

scripts/
└── test_ahp_scoring.py                  # Test suite
```

---

## Important Notes

1. **AHP is OPTIONAL**: Does not replace Monte Carlo, runs alongside it
2. **Requires expert input**: Must have CSV with pairwise comparisons
3. **Consistency matters**: High CR (>0.10) indicates illogical comparisons
4. **Multiple experts**: Automatically aggregated using geometric mean
5. **Both scores available**: Use whichever is more appropriate for your analysis

---

## Advanced Options

### Custom Aggregation Method

```python
from src.config import AHP_AGGREGATION_METHOD

# Options: 'geometric_mean', 'arithmetic_mean', 'median'
AHP_AGGREGATION_METHOD = 'geometric_mean'  # Recommended
```

### Custom Consistency Threshold

```python
from src.config import AHP_CONSISTENCY_RATIO_THRESHOLD

AHP_CONSISTENCY_RATIO_THRESHOLD = 0.10  # Saaty's recommendation
```

### Print Saaty Scale for Experts

```python
from src.scoring import print_saaty_scale

print_saaty_scale()  # Display full scale with descriptions
```

---

## Troubleshooting

**Q: AHP is skipped during pipeline run**
- A: Check that `AHP_ENABLED = True` in `src/config.py`
- A: Verify `data/ahp_expert_comparisons.csv` exists and has valid data

**Q: Expert has high CR (>0.10)**
- A: Review their comparisons for logical contradictions
- A: Check transitivity (if A>B and B>C, then A>C should hold)

**Q: Want different number of experts**
- A: Just add/remove rows with different expert names in CSV

**Q: Want matrix format instead of long format**
- A: Use `create_expert_template_csv(..., format='matrix')`

---

## Full Documentation

For complete details, see:
- **Full Guide**: `docs/AHP_SCORING_GUIDE.md`
- **Main Documentation**: `CLAUDE.md`
- **AHP Module Code**: `src/scoring/ahp.py`

---

## Testing

Run the test suite:

```bash
python scripts/test_ahp_scoring.py
```

Tests include:
- ✓ Saaty scale display
- ✓ Template creation
- ✓ Expert comparison loading
- ✓ Weight aggregation
- ✓ AHP scoring
- ✓ Full pipeline integration

---

## Summary

**To use AHP scoring:**

1. Set `AHP_ENABLED = True` in `src/config.py`
2. Create or copy expert comparison CSV to `data/ahp_expert_comparisons.csv`
3. Have experts fill in pairwise comparisons (Saaty scale 1-9)
4. Run `run_complete_scoring_pipeline()` as usual
5. Compare `final_score` (Monte Carlo) vs `ahp_score` (AHP)

**That's it!** AHP scoring will run automatically alongside Monte Carlo.

---

*Last updated: 2024-12-13*
