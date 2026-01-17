# Notebook Versioning Guide
**How to Add Versioning to Jupyter Notebooks**

## Quick Start

### Method 1: Simple Wrapper (Recommended)

Add these cells to the **beginning** of your notebook:

```python
# Cell 1: Import versioning
from src.versioning.notebook_helper import NotebookVersioning

# Cell 2: Start versioned run
nb = NotebookVersioning(
    purpose="Testing metro expansion scenario",
    tags=["scenario", "metro_2030", "draft"]
)
nb.start()
```

Run your analysis as normal...

Add this cell at the **end** of your notebook:

```python
# Final cell: Finish and save version
nb.finish(results_summary={
    'total_hubs': len(scored_hubs),
    'hubs_by_tier': scored_hubs['tier'].value_counts().to_dict(),
    'avg_score': scored_hubs['final_score'].mean()
})
```

### Method 2: Quick Version (One-liner)

For simple notebooks:

```python
# At start
nb = quick_version("Quick analysis of new data")

# ... your analysis ...

# At end
nb.finish()
```

---

## Full Example

### Complete Notebook with Versioning

```python
# =============================================================================
# Cell 1: Setup and Versioning
# =============================================================================

import sys
from pathlib import Path

# Add project to path
PROJECT_ROOT = Path.cwd().parent if 'notebooks' in str(Path.cwd()) else Path.cwd()
sys.path.insert(0, str(PROJECT_ROOT))

# Import versioning
from src.versioning.notebook_helper import NotebookVersioning

# Start versioned run
nb = NotebookVersioning(
    purpose="Evaluate 2030 metro scenario with updated demand forecasts",
    created_by="planner@example.com",
    tags=["production", "2030_scenario", "validated"],
    notebook_name="hub_scoring_analysis.ipynb"
)

run_id = nb.start()
print(f"Run ID: {run_id}")

# =============================================================================
# Cell 2: Import Libraries
# =============================================================================

import pandas as pd
import geopandas as gpd
from src.config import *
from src.data import loaders
from src.scoring import monte_carlo

# =============================================================================
# Cell 3-N: Your Analysis
# =============================================================================

# Load data
transit_nodes = loaders.load_transit_nodes("data/raw/All_nodes+lines.csv")

# ... continue with your analysis ...

# Save intermediate results to versioned directory
nb.save_intermediate(
    transit_nodes,
    filename="transit_nodes_processed",
    description="Processed transit nodes"
)

# ... more analysis ...

# Calculate scores
scored_hubs = monte_carlo.run_complete_scoring_pipeline(classified_hubs)

# Save final results
nb.save_intermediate(
    scored_hubs,
    filename="scored_hubs_final",
    description="Final scored hubs"
)

# =============================================================================
# Final Cell: Finalize Versioning
# =============================================================================

# Prepare results summary
results_summary = {
    'total_nodes': len(transit_nodes),
    'total_hubs': len(scored_hubs),
    'hubs_by_tier': scored_hubs['tier'].value_counts().to_dict(),
    'avg_score': float(scored_hubs['final_score'].mean()),
    'max_score': float(scored_hubs['final_score'].max()),
    'top_hub': scored_hubs.nlargest(1, 'final_score')['group'].iloc[0]
}

# Finish versioned run
nb.finish(results_summary=results_summary)
```

---

## Updating Existing Notebooks

### Step-by-Step Guide

**1. Add imports at the beginning:**

```python
# Add after your existing imports
from src.versioning.notebook_helper import NotebookVersioning
```

**2. Initialize versioning (add new cell after imports):**

```python
# Initialize versioning
nb = NotebookVersioning(
    purpose="<Describe what this notebook does>",
    tags=["<tag1>", "<tag2>"],
    notebook_name="<your_notebook_name>.ipynb"
)
nb.start()
```

**3. Save intermediate results (optional, add where needed):**

```python
# When you want to save intermediate data
nb.save_intermediate(your_dataframe, "descriptive_filename", "Description")
```

**4. Add finalization at the end:**

```python
# Collect your results
results_summary = {
    # Add key metrics from your analysis
    'metric1': value1,
    'metric2': value2,
    # ...
}

# Finish versioning
nb.finish(results_summary=results_summary)
```

### Example: Updating `COMPLETE_TRANSIT_PIPELINE.ipynb`

**Before Cell 1:**
```python
import pandas as pd
import geopandas as gpd
# ... other imports ...
```

**After Cell 1:**
```python
import pandas as pd
import geopandas as gpd
# ... other imports ...

# ADD THIS:
from src.versioning.notebook_helper import NotebookVersioning

nb = NotebookVersioning(
    purpose="Complete transit hub pipeline execution",
    tags=["pipeline", "complete"],
    notebook_name="COMPLETE_TRANSIT_PIPELINE.ipynb"
)
nb.start()
```

**Before Last Cell:**
```python
# Display final results
print(f"Total hubs: {len(final_hubs)}")
# ...
```

**After Last Cell:**
```python
# Display final results
print(f"Total hubs: {len(final_hubs)}")
# ...

# ADD THIS:
results_summary = {
    'total_hexes': len(h3_hexagons),
    'total_hub_groups': len(grouped_hubs),
    'eligible_hubs': len(eligible_hubs),
    'final_hubs': len(final_hubs),
    'hubs_by_tier': final_hubs['tier'].value_counts().to_dict() if 'tier' in final_hubs.columns else {}
}

nb.finish(results_summary=results_summary)
```

---

## Features

### Automatic Tracking

Versioning automatically tracks:
- ✅ Model code version
- ✅ Input data versions
- ✅ Configuration snapshot
- ✅ Execution time
- ✅ Results summary
- ✅ All saved outputs

### Save Intermediate Results

```python
# Save DataFrames
nb.save_intermediate(df, "my_data", "Description of data")
# → Saves to: data/results/run_YYYY-MM-DD_NN/my_data.csv

# Save GeoDataFrames
nb.save_intermediate(gdf, "spatial_data", "Spatial analysis results")
# → Saves to: data/results/run_YYYY-MM-DD_NN/spatial_data.geojson

# Save dictionaries
nb.save_intermediate(config_dict, "configuration", "Run configuration")
# → Saves to: data/results/run_YYYY-MM-DD_NN/configuration.json
```

### Tags for Organization

Use tags to categorize runs:

```python
# Development/testing
tags=["dev", "test", "draft"]

# Production
tags=["production", "validated", "final"]

# Scenarios
tags=["scenario_2030", "metro_expansion", "high_growth"]

# Data updates
tags=["data_update", "q1_2025", "revised_demand"]
```

### Query Notebook Runs

```bash
# List all notebook runs
python scripts/version_management/list_versions.py --type runs --tag notebook

# List specific scenario runs
python scripts/version_management/list_versions.py --type runs --tag "scenario_2030"

# Compare two notebook runs
python scripts/version_management/compare_versions.py \
  --type runs \
  --version1 run_2025-01-10_01 \
  --version2 run_2025-01-17_02
```

---

## Best Practices

### 1. Always Version Production Analysis

```python
# ✅ Good
nb = NotebookVersioning(
    purpose="Production analysis for stakeholder presentation",
    tags=["production", "validated", "presentation"],
    notebook_name="stakeholder_analysis.ipynb"
)
nb.start()
```

```python
# ❌ Bad - no versioning
# Just run notebook without tracking
```

### 2. Use Descriptive Purposes

```python
# ✅ Good
purpose="Evaluate impact of metro line 3 on hub rankings"

# ❌ Bad
purpose="Test"
```

### 3. Tag Appropriately

```python
# ✅ Good - specific, searchable tags
tags=["production", "2025_Q1", "metro_scenario", "validated"]

# ❌ Bad - vague tags
tags=["run1", "test"]
```

### 4. Save Key Intermediate Results

```python
# ✅ Good - save important checkpoints
nb.save_intermediate(raw_data, "01_raw_data", "Original data before processing")
nb.save_intermediate(cleaned_data, "02_cleaned_data", "After cleaning and validation")
nb.save_intermediate(final_results, "03_final_results", "Final scored hubs")

# ❌ Bad - save nothing or save everything
```

### 5. Provide Results Summary

```python
# ✅ Good - comprehensive summary
results_summary = {
    'total_hubs': len(hubs),
    'new_hubs': len(new_hubs),
    'tier_distribution': tier_counts,
    'avg_score': avg_score,
    'data_quality_issues': n_issues,
    'notes': "3 hubs reclassified from מטרופוליני to ארצי"
}
nb.finish(results_summary=results_summary)

# ❌ Bad - no summary or minimal info
nb.finish()
```

---

## Handling Errors

If your notebook fails partway through:

```python
try:
    # Your analysis code
    results = run_analysis()

    # Finish successfully
    nb.finish(results_summary={'status': 'completed'})

except Exception as e:
    # Finish with error status
    nb.finish(
        results_summary={'error': str(e), 'status': 'failed'},
        status='failed'
    )
    raise  # Re-raise error for debugging
```

---

## Advanced Usage

### Custom Configuration Tracking

```python
# Track custom parameters
nb = NotebookVersioning(
    purpose="Sensitivity analysis - vary mode weights",
    tags=["sensitivity", "mode_weights"]
)
nb.start()

# Override or add to configuration
custom_config = {
    'analysis_type': 'sensitivity',
    'parameter_varied': 'mode_weights',
    'test_values': [0.1, 0.3, 0.5, 0.7, 0.9]
}

# Save custom config
nb.save_intermediate(custom_config, "custom_config", "Sensitivity parameters")
```

### Multiple Scenarios in One Notebook

```python
# Scenario 1
nb1 = NotebookVersioning(
    purpose="Scenario A: Conservative growth",
    tags=["scenario_A", "conservative"]
)
nb1.start()
# ... run scenario A ...
nb1.finish(results_summary=results_A)

# Scenario 2
nb2 = NotebookVersioning(
    purpose="Scenario B: High growth",
    tags=["scenario_B", "high_growth"]
)
nb2.start()
# ... run scenario B ...
nb2.finish(results_summary=results_B)
```

---

## Troubleshooting

### Issue: "No run version to finalize"

**Cause:** `nb.start()` was not called or failed.

**Solution:**
```python
# Make sure start() is called and succeeds
try:
    nb.start()
except Exception as e:
    print(f"Failed to start versioning: {e}")
    # Continue without versioning or fix the issue
```

### Issue: Cannot find versioning module

**Cause:** Project root not in Python path.

**Solution:**
```python
# Add at top of notebook
import sys
from pathlib import Path

PROJECT_ROOT = Path.cwd().parent  # Adjust based on notebook location
sys.path.insert(0, str(PROJECT_ROOT))

# Now import versioning
from src.versioning.notebook_helper import NotebookVersioning
```

### Issue: Results not saved to versioned directory

**Cause:** Results dir not properly set.

**Solution:**
```python
# Check results directory
print(f"Results will be saved to: {nb.results_dir}")

# Make sure to use nb.save_intermediate() or save manually:
import pandas as pd
df.to_csv(nb.results_dir / "my_results.csv")
```

---

## Complete Template

Copy and paste this into your notebooks:

```python
# ==============================================================================
# VERSIONING SETUP
# ==============================================================================

import sys
from pathlib import Path

# Add project to path (adjust if needed)
PROJECT_ROOT = Path.cwd().parent if 'notebooks' in str(Path.cwd()) else Path.cwd()
sys.path.insert(0, str(PROJECT_ROOT))

# Import versioning
from src.versioning.notebook_helper import NotebookVersioning

# Initialize versioned run
nb = NotebookVersioning(
    purpose="<Describe your analysis>",
    created_by="<your_email@example.com>",
    tags=["<tag1>", "<tag2>"],
    notebook_name="<notebook_filename>.ipynb"
)

# Start versioning
run_id = nb.start()
print(f"Run ID: {run_id}")
print(f"Results: {nb.results_dir}")

# ==============================================================================
# YOUR ANALYSIS HERE
# ==============================================================================

# ... your code ...

# Save intermediate results (optional)
# nb.save_intermediate(data, "filename", "description")

# ==============================================================================
# FINALIZE VERSIONING
# ==============================================================================

# Prepare results summary
results_summary = {
    # Add your key metrics here
}

# Finish versioned run
nb.finish(results_summary=results_summary)

print("\n" + "="*80)
print(f"Analysis complete! Results saved to: {nb.results_dir}")
print("="*80)
```

---

**Last Updated:** 2025-01-17
**Version:** 1.0.0
