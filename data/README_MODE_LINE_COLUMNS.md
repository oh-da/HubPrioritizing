# Mode-Specific Line Count Columns

## Overview

The pipeline tracks the number of unique transit lines per mode at each hub using dedicated columns. These columns are **critical for scoring** as they determine the service level and modal diversity of each hub.

## Column Names

Each transit mode has its own line count column:

- **`BRT Lines`**: Number of unique BRT (Bus Rapid Transit) lines
- **`LRT Lines`**: Number of unique Light Rail Transit lines
- **`Metro Lines`**: Number of unique metro lines
- **`Suburban Rail Lines`**: Number of unique suburban rail lines
- **`Interurban Rail Lines`**: Number of unique interurban rail lines
- **`HighSpeed Rail Lines`**: Number of unique high-speed rail lines
- **`Cable Line Lines`**: Number of unique cable car lines
- **`Funicular Lines`**: Number of unique funicular lines

## How They're Used in Scoring

### Step 4.3: Mode Service Score

The mode-specific line counts are the **foundation of the service score** calculation:

```python
def get_mode_score(row):
    """Calculate mode service score with diversity bonus."""
    score = 0.0
    alpha = 0.1  # Diversity bonus factor

    # For each mode, multiply line count by mode weight
    for mode, weight in MODE_WEIGHTS.items():
        column_name = f'{mode} Lines'
        if column_name in row.index and row[column_name] > 0:
            score += row[column_name] * weight  # <-- Uses line count!

    # Apply diversity bonus (more modes = higher multiplier)
    n_modes = row.get('Num_Modes', 1)
    score = score * (1 + alpha * (n_modes - 1))

    return score
```

### Mode Weights

Each mode has a different weight reflecting its capacity and importance:

```python
MODE_WEIGHTS = {
    'Funicular': 1.0,
    'Cable Line': 2.0,
    'BRT': 3.0,
    'LRT': 4.0,
    'Metro': 5.0,
    'Suburban Rail': 6.0,
    'Interurban Rail': 7.0,
    'HighSpeed Rail': 8.0,
}
```

### Example Calculation

**Hub A**: 2 BRT lines, 1 LRT line
- BRT contribution: 2 × 3 = 6
- LRT contribution: 1 × 4 = 4
- Raw score: 6 + 4 = 10
- Num_Modes: 2
- Diversity bonus: 1 + 0.1 × (2 - 1) = 1.1
- **Final score**: 10 × 1.1 = **11.0**

**Hub B**: 4 Metro lines
- Metro contribution: 4 × 5 = 20
- Num_Modes: 1
- Diversity bonus: 1 + 0.1 × (1 - 1) = 1.0
- **Final score**: 20 × 1.0 = **20.0**

**Hub C**: 2 LRT lines, 2 Metro lines, 1 Suburban Rail line
- LRT: 2 × 4 = 8
- Metro: 2 × 5 = 10
- Suburban Rail: 1 × 6 = 6
- Raw score: 8 + 10 + 6 = 24
- Num_Modes: 3
- Diversity bonus: 1 + 0.1 × (3 - 1) = 1.2
- **Final score**: 24 × 1.2 = **28.8**

**Key insight**: Hub C scores highest despite having fewer total lines than Hub B, because it has **modal diversity** (3 different modes vs 1).

## Where They Come From

### Input Data

The mode line count columns come from the **input transit network data**:

1. **Original node data** (`All_nodes+lines.csv`): Contains node IDs, geometries, and associated transit lines
2. **Mode definitions** (`Lines_and_Planned_Mode.csv`): Maps each line ID to its mode type

### Processing Steps

1. **Step 1.3-1.4**: Load nodes and mode data, assign H3 hexagons
2. **Step 1.5**: Aggregate nodes to hexagons, counting lines per mode
3. **Step 2.7**: Group hexagons into hubs, summing/preserving line counts

The aggregation ensures that when multiple hexagons are grouped into a hub, the mode line counts are properly aggregated (usually by summing or taking the maximum).

## Verification

To verify these columns exist and are used:

1. **Check input data**:
   ```python
   df = pd.read_csv('output/grouped_hubs.csv')
   mode_cols = [c for c in df.columns if 'Lines' in c]
   print(mode_cols)
   # Should show: ['BRT Lines', 'LRT Lines', 'Metro Lines', etc.]
   ```

2. **Check they're non-zero**:
   ```python
   for col in mode_cols:
       print(f"{col}: {(df[col] > 0).sum()} hubs with this mode")
   ```

3. **Check scoring uses them**:
   - See Step 4.3 in `COMPLETE_TRANSIT_PIPELINE.ipynb`
   - The `get_mode_score()` function explicitly references these columns

## Final Output

The mode line count columns are included in the final scored hubs CSV/Excel:

```
group,h3_index,node,centroid,x,y,Mode_Planned,BRT Lines,LRT Lines,Metro Lines,
Suburban Rail Lines,Interurban Rail Lines,HighSpeed Rail Lines,...,score,...
```

This allows you to:
- See exactly which modes serve each hub
- Understand why a hub received a particular service score
- Identify hubs that could benefit from additional modes
- Plan service improvements based on modal gaps

## Troubleshooting

### Issue: All mode line columns are 0

**Cause**: Input data doesn't have these columns, or they weren't aggregated properly

**Solution**:
1. Check if input file has columns like "BRT Lines", "LRT Lines", etc.
2. If not, check that Step 1.5 or 2.7 creates them during aggregation
3. Verify the aggregation function preserves numeric columns

### Issue: Mode scores are all very low

**Cause**: Line counts might be missing or not properly aggregated

**Solution**:
1. Check `df['BRT Lines'].sum(), df['LRT Lines'].sum()`, etc.
2. Verify that Step 4.3 runs without errors
3. Check that MODE_WEIGHTS are defined correctly

### Issue: Some modes have counts, others don't

**Cause**: Normal - not all hubs have all modes

**Solution**: This is expected behavior. Each hub will only have line counts for the modes that actually serve it.

## Summary

✅ **Mode line count columns** (`BRT Lines`, `LRT Lines`, etc.) are essential data columns
✅ **Created from input data** during H3 aggregation and hub grouping
✅ **Used in scoring** to calculate the mode service score (Step 4.3)
✅ **Multiplied by mode weights** with higher weights for higher-capacity modes
✅ **Included in final output** for transparency and analysis
✅ **Combined with diversity bonus** to reward multimodal hubs

These columns are a core part of the hub prioritization methodology and must be present for accurate scoring.
