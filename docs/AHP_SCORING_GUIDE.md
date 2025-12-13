# AHP Scoring Guide

**Analytic Hierarchy Process (AHP) for Hub Prioritization**

---

## Overview

The AHP (Analytic Hierarchy Process) scoring methodology provides a structured, expert-driven approach to deriving criterion weights for hub prioritization. Unlike the Monte Carlo method (which uses random weights), AHP derives weights from systematic pairwise comparisons made by domain experts.

### Key Benefits

✅ **Transparent**: Expert judgments are explicit and traceable
✅ **Consistent**: Built-in consistency checking ensures logical comparisons
✅ **Structured**: Systematic methodology prevents ad hoc weighting
✅ **Complementary**: Works alongside Monte Carlo for comparative analysis
✅ **Expert-Driven**: Incorporates domain knowledge and strategic priorities

---

## How AHP Works

### 1. Pairwise Comparisons

Experts compare criteria two at a time, answering: *"How much more important is Criterion A compared to Criterion B?"*

Example:
- **Question**: Is passenger activity more important than bus terminal proximity?
- **Answer**: Passenger activity is "strongly more important" → Value: **5**

### 2. Saaty Scale

AHP uses the Saaty scale (1-9) for comparisons:

| Value | Meaning | Description |
|-------|---------|-------------|
| 1 | Equal importance | Two criteria contribute equally |
| 2 | Weak or slight | Experience slightly favors one |
| 3 | Moderate importance | Experience strongly favors one |
| 4 | Moderate plus | Intermediate value |
| 5 | Strong importance | Experience very strongly favors one |
| 6 | Strong plus | Intermediate value |
| 7 | Very strong importance | Demonstrated in practice |
| 8 | Very, very strong | Intermediate value |
| 9 | Extreme importance | Highest order of importance |

**Reciprocals**: If A is 5× more important than B, then B is 1/5 = 0.2× as important as A.

### 3. Priority Calculation

From the pairwise comparison matrix, AHP calculates criterion weights using the **eigenvector method** (Saaty's principal eigenvector approach).

### 4. Consistency Checking

AHP computes a **Consistency Ratio (CR)** to validate expert judgments:

- **CR < 0.10**: Acceptable consistency ✓
- **CR ≥ 0.10**: Inconsistent judgments, expert should revise ✗

Example of inconsistency:
- A is 3× more important than B
- B is 3× more important than C
- C is 3× more important than A
→ **Logical contradiction!** (CR would be high)

### 5. Multi-Expert Aggregation

When multiple experts provide comparisons, their weights are combined using:
- **Geometric mean** (recommended)
- Arithmetic mean
- Median (robust to outliers)

---

## Using AHP Scoring

### Step 1: Enable AHP in Configuration

Edit `src/config.py`:

```python
# Enable AHP scoring
AHP_ENABLED = True

# Expert comparison CSV path
AHP_EXPERT_CSV_PATH = DATA_DIR / "ahp_expert_comparisons.csv"

# Consistency threshold (Saaty recommends 0.10)
AHP_CONSISTENCY_RATIO_THRESHOLD = 0.10

# How to aggregate multiple experts
AHP_AGGREGATION_METHOD = 'geometric_mean'  # or 'arithmetic_mean', 'median'
```

### Step 2: Create Expert Comparison Template

Use Python to generate a template:

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

This creates a CSV with all pairwise combinations pre-filled with neutral values (1).

### Step 3: Expert Input

Distribute the CSV to domain experts (transport planners, economists, accessibility experts, etc.) and ask them to fill in their pairwise comparisons.

**Example CSV format:**

```csv
expert,criterion_a,criterion_b,value
expert1,activity_score,service_score,3
expert1,activity_score,location_score,5
expert1,activity_score,pop_jobs_score,2
...
```

**Instructions for experts:**
1. Compare each pair of criteria
2. Use Saaty scale (1-9)
3. Value > 1 means criterion_a is MORE important
4. Value < 1 means criterion_b is MORE important
5. Value = 1 means EQUAL importance

### Step 4: Run AHP Scoring

```python
from src.scoring import run_complete_scoring_pipeline
import geopandas as gpd

# Load your scored hubs
gdf = gpd.read_file('data/hubs_with_scores.geojson')

# Run pipeline with AHP enabled
gdf_final = run_complete_scoring_pipeline(
    gdf,
    tier_column='tier',
    enable_ahp=True,
    ahp_expert_csv='data/ahp_expert_comparisons.csv'
)

# Results now include:
# - final_score (Monte Carlo)
# - ahp_score (AHP)
# - rank
# - ahp_rank
```

### Step 5: Analyze Results

```python
from src.scoring import compare_monte_carlo_vs_ahp

# Compare both methods
comparison_df = compare_monte_carlo_vs_ahp(
    gdf_final,
    monte_carlo_col='final_score',
    ahp_col='ahp_score',
    top_n=20
)

# Correlation between methods
print(f"Score correlation: {gdf_final['final_score'].corr(gdf_final['ahp_score']):.3f}")

# Top disagreements
disagreements = comparison_df.nlargest(10, 'rank_diff')
print(disagreements[['hub_id', 'mc_rank', 'ahp_rank', 'rank_diff']])
```

---

## Example Expert Scenario

### Expert 1: Transport Planner
*Prioritizes operational efficiency and ridership*

```csv
transport_planner,activity_score,service_score,3      # Activity is moderately more important than service
transport_planner,activity_score,location_score,5     # Activity is strongly more important than location
transport_planner,service_score,terminal_score,2      # Service is weakly more important than terminals
```

**Resulting weights:**
- Activity: 42%
- Service: 28%
- Location: 12%
- Pop/Jobs: 11%
- Terminals: 7%

### Expert 2: Urban Economist
*Prioritizes development potential and TOD*

```csv
urban_economist,pop_jobs_score,activity_score,2      # Pop/Jobs is weakly more important than activity
urban_economist,pop_jobs_score,service_score,2       # Pop/Jobs is weakly more important than service
urban_economist,pop_jobs_score,terminal_score,5      # Pop/Jobs is strongly more important than terminals
```

**Resulting weights:**
- Pop/Jobs: 38%
- Activity: 25%
- Service: 20%
- Location: 10%
- Terminals: 7%

### Expert 3: Accessibility Specialist
*Prioritizes network connectivity and integration*

```csv
accessibility_expert,service_score,activity_score,2   # Service is weakly more important than activity
accessibility_expert,terminal_score,pop_jobs_score,3  # Terminals are moderately more important than pop/jobs
accessibility_expert,location_score,terminal_score,0.5 # Location is less important than terminals (reciprocal)
```

**Resulting weights:**
- Service: 32%
- Terminals: 28%
- Activity: 18%
- Location: 12%
- Pop/Jobs: 10%

### Aggregated (Geometric Mean)

After combining all three experts:

- **Activity**: 28%
- **Service**: 27%
- **Pop/Jobs**: 18%
- **Terminals**: 15%
- **Location**: 12%

---

## Consistency Diagnostics

### What Gets Checked

For each expert, AHP calculates:

1. **Consistency Index (CI)**:
   ```
   CI = (λ_max - n) / (n - 1)
   ```
   Where λ_max is the principal eigenvalue and n is the number of criteria.

2. **Consistency Ratio (CR)**:
   ```
   CR = CI / RI
   ```
   Where RI is the Random Index (from Saaty's tables).

### Interpreting Results

| CR Range | Interpretation | Action |
|----------|----------------|--------|
| < 0.10 | Acceptable consistency ✓ | Use weights as-is |
| 0.10 - 0.15 | Marginal consistency ⚠️ | Review comparisons |
| > 0.15 | Unacceptable inconsistency ✗ | Revise comparisons |

### Example Output

```
Expert 'transport_planner': CR = 0.067 ✓
Expert 'urban_economist': CR = 0.045 ✓
Expert 'accessibility_expert': CR = 0.112 ✗

Warning: Expert 'accessibility_expert' has high inconsistency: CR = 0.112 (threshold: 0.10)
```

---

## AHP vs Monte Carlo

### When to Use AHP

✅ You have access to domain experts
✅ Strategic priorities are clear
✅ Stakeholder buy-in is important
✅ Transparent weighting is needed
✅ Consistency checking is valuable

### When to Use Monte Carlo

✅ You want to avoid single-weight bias
✅ Expert consensus is difficult
✅ Robustness to weighting is desired
✅ Exploratory analysis is needed
✅ Sensitivity testing is priority

### Using Both (Recommended!)

Running both methods provides:
- **Validation**: If methods agree, results are robust
- **Insights**: Disagreements highlight weight-sensitive hubs
- **Flexibility**: Different stakeholders may prefer different methods
- **Transparency**: Monte Carlo shows range, AHP shows expert consensus

---

## API Reference

### Core Functions

#### `run_ahp_scoring_pipeline()`
Run complete AHP scoring from expert CSV to final scores.

```python
gdf_ahp, diagnostics = run_ahp_scoring_pipeline(
    gdf,
    expert_csv_path='data/ahp_expert_comparisons.csv',
    score_columns=['activity_score', 'service_score', ...],
    consistency_threshold=0.10,
    aggregation_method='geometric_mean'
)
```

**Returns:**
- `gdf_ahp`: GeoDataFrame with `ahp_score` and `ahp_rank` columns
- `diagnostics`: Dictionary with expert weights, consistency ratios, etc.

#### `load_expert_comparisons_from_csv()`
Load expert pairwise comparisons from CSV.

```python
expert_matrices = load_expert_comparisons_from_csv(
    csv_path='data/ahp_expert_comparisons.csv',
    criteria_names=['activity_score', 'service_score', ...]
)
```

**Returns:** Dictionary mapping expert names to pairwise comparison matrices

#### `aggregate_expert_weights()`
Combine multiple expert opinions into aggregated weights.

```python
weights, diagnostics = aggregate_expert_weights(
    expert_matrices,
    method='geometric_mean',
    consistency_threshold=0.10
)
```

**Returns:**
- `weights`: Array of aggregated criterion weights (sum to 1)
- `diagnostics`: Dictionary with per-expert consistency ratios

#### `create_expert_template_csv()`
Generate template CSV for expert input.

```python
create_expert_template_csv(
    output_path='data/ahp_template.csv',
    criteria_names=['activity_score', 'service_score', ...],
    n_experts=3,
    format='long'
)
```

#### `compare_monte_carlo_vs_ahp()`
Compare rankings between Monte Carlo and AHP.

```python
comparison_df = compare_monte_carlo_vs_ahp(
    gdf,
    monte_carlo_col='final_score',
    ahp_col='ahp_score',
    top_n=20
)
```

**Returns:** DataFrame with score/rank comparisons and disagreements

### Utility Functions

#### `print_saaty_scale()`
Print the Saaty scale for reference.

```python
from src.scoring import print_saaty_scale
print_saaty_scale()
```

#### `saaty_scale_description()`
Get Saaty scale as DataFrame.

```python
scale_df = saaty_scale_description()
print(scale_df)
```

---

## Troubleshooting

### High Consistency Ratio

**Problem**: Expert's CR > 0.10

**Solutions**:
1. Review comparisons for logical contradictions
2. Focus on most inconsistent comparisons (use diagnostics)
3. Re-evaluate transitivity (if A>B and B>C, then A>C should hold approximately)
4. Use fewer extreme values (avoid excessive 9s)

### Missing Expert CSV

**Problem**: `AHP expert CSV not found`

**Solution**:
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
    n_experts=3
)
```

### Different Number of Experts

**Problem**: Want more or fewer than 3 experts

**Solution**: Simply add/remove rows in the CSV with different expert names. The code automatically detects unique experts.

### Matrix Format Instead of Long Format

**Problem**: Prefer matrix format for expert input

**Solution**:
```python
create_expert_template_csv(
    output_path='data/ahp_matrix.csv',
    criteria_names=[...],
    format='matrix'
)
```

---

## References

### Academic

- Saaty, T.L. (1980). *The Analytic Hierarchy Process*. McGraw-Hill.
- Saaty, T.L. (2008). "Decision making with the analytic hierarchy process." *International Journal of Services Sciences*, 1(1), 83-98.
- Brunelli, M. (2014). *Introduction to the Analytic Hierarchy Process*. Springer.

### Practical Applications

- Transport infrastructure prioritization
- Transit-oriented development assessment
- Multi-criteria urban planning
- Investment portfolio optimization

---

## Example Workflow

### Complete End-to-End Example

```python
import geopandas as gpd
from src.scoring import (
    create_expert_template_csv,
    run_complete_scoring_pipeline,
    compare_monte_carlo_vs_ahp,
    print_saaty_scale
)

# 1. Print Saaty scale for experts
print_saaty_scale()

# 2. Create template
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

# 3. [Experts fill in CSV with their comparisons]

# 4. Load hubs with individual criterion scores
gdf = gpd.read_file('data/hubs_with_criterion_scores.geojson')

# 5. Run complete pipeline (Monte Carlo + AHP)
gdf_final = run_complete_scoring_pipeline(
    gdf,
    tier_column='tier',
    enable_ahp=True,
    ahp_expert_csv='data/ahp_expert_comparisons.csv'
)

# 6. Compare methods
comparison = compare_monte_carlo_vs_ahp(gdf_final)

# 7. Export results
gdf_final.to_file('data/results/hubs_scored_both_methods.geojson', driver='GeoJSON')
comparison.to_csv('data/results/method_comparison.csv', index=False)

# 8. Analyze top hubs
top_mc = gdf_final.nlargest(10, 'final_score')[['group', 'tier', 'final_score', 'rank']]
top_ahp = gdf_final.nlargest(10, 'ahp_score')[['group', 'tier', 'ahp_score', 'ahp_rank']]

print("\nTop 10 by Monte Carlo:")
print(top_mc)

print("\nTop 10 by AHP:")
print(top_ahp)
```

---

## File Locations

```
HubPrioritizing/
├── data/
│   ├── ahp_expert_comparisons_TEMPLATE.csv    # Blank template
│   ├── ahp_expert_comparisons_example.csv     # Example with sample data
│   └── ahp_expert_comparisons.csv             # Your actual expert input
├── src/
│   └── scoring/
│       ├── ahp.py                             # AHP implementation
│       ├── monte_carlo.py                     # Integrated Monte Carlo + AHP
│       └── __init__.py                        # Exports both methods
├── docs/
│   └── AHP_SCORING_GUIDE.md                   # This document
└── notebooks/
    └── ahp_scoring_demo.ipynb                 # Interactive demo (to be created)
```

---

## Summary

AHP scoring provides a **transparent, expert-driven alternative to Monte Carlo** that:
- Systematically captures domain knowledge
- Enforces logical consistency
- Enables stakeholder participation
- Complements stochastic approaches

**Best Practice**: Use both methods and compare results. Agreement indicates robust findings; disagreement highlights weight-sensitive decisions requiring further discussion.

---

*For questions or issues, see the main CLAUDE.md documentation or create a GitHub issue.*
