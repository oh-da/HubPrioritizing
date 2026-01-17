# Versioning Integration README
**How Versioning is Integrated into the Hub Prioritization Framework**

## Overview

The Hub Prioritization Framework now includes **comprehensive automatic versioning** for all pipeline executions and notebook analyses. Every run is tracked, stored, and can be reproduced exactly.

---

## What's New

### 🎯 **Automatic Version Tracking**

**Every pipeline run now automatically creates a version that tracks:**
- ✅ Model code version used
- ✅ All input data versions
- ✅ Complete configuration snapshot
- ✅ Execution time and status
- ✅ Results summary (hub counts, tier distribution, etc.)
- ✅ All output files

**Every notebook analysis can be versioned to track:**
- ✅ Purpose and context of the analysis
- ✅ Data versions used
- ✅ Configuration at time of run
- ✅ Intermediate results
- ✅ Final results and metrics

### 🔧 **New Components**

1. **Versioned Pipeline Script**: `scripts/run_complete_pipeline_versioned.py`
2. **Notebook Helper**: `src/versioning/notebook_helper.py`
3. **CLI Tools**: `scripts/version_management/`
4. **Documentation**: `docs/VERSIONING_GUIDE.md`, `docs/NOTEBOOK_VERSIONING_GUIDE.md`

---

## Quick Start

### Running the Versioned Pipeline

**Option 1: Command Line (Recommended)**

```bash
# Basic run with automatic versioning
python scripts/run_complete_pipeline_versioned.py

# Run with metadata
python scripts/run_complete_pipeline_versioned.py \
  --purpose "Production run for Q1 2025 planning" \
  --user "planner@example.com" \
  --tags "production,q1_2025,validated"

# Run without versioning (legacy mode)
python scripts/run_complete_pipeline_versioned.py --no-version
```

**Option 2: Python API**

```python
from scripts.run_complete_pipeline_versioned import VersionedHubPipeline

pipeline = VersionedHubPipeline(
    run_purpose="Testing metro expansion scenario",
    created_by="analyst@example.com",
    tags=["scenario", "metro_2030"]
)

results = pipeline.run()
```

### Using Versioning in Notebooks

**Add to the start of your notebook:**

```python
from src.versioning.notebook_helper import NotebookVersioning

nb = NotebookVersioning(
    purpose="Analyze hub rankings with new demand data",
    tags=["analysis", "demand_update"]
)
nb.start()
```

**Add to the end of your notebook:**

```python
nb.finish(results_summary={
    'total_hubs': len(scored_hubs),
    'avg_score': scored_hubs['final_score'].mean()
})
```

---

## Architecture

### Directory Structure

```
HubPrioritizing/
├── VERSION                          # Current model version (1.3.2)
│
├── data/
│   ├── versions/                    # Versioned input data
│   │   ├── transit_lines/
│   │   │   └── data_2025-01-17_143045/
│   │   │       ├── transit_lines.csv
│   │   │       ├── metadata.json
│   │   │       └── validation_report.json
│   │   ├── transit_stations/
│   │   ├── demand_2050/
│   │   └── index.db                 # SQLite index for fast queries
│   │
│   ├── results/                     # Versioned pipeline runs
│   │   ├── run_2025-01-17_01/       # ← Versioned run directory
│   │   │   ├── run_metadata.json    # Complete run metadata
│   │   │   ├── config_snapshot.json # Configuration used
│   │   │   ├── scored_hubs.csv      # Results
│   │   │   ├── scored_hubs.geojson  # Spatial results
│   │   │   └── hub_map.html         # Interactive map
│   │   └── run_2025-01-10_01/
│   │
│   └── current/                     # Symlinks to latest data versions
│       ├── transit_lines.csv → ../versions/...
│       └── ...
│
├── src/versioning/                  # Versioning modules
│   ├── version_store.py             # Central storage (JSON + SQLite)
│   ├── data_version.py              # Input data versioning
│   ├── run_version.py               # Pipeline run versioning
│   ├── model_version.py             # Code version management
│   ├── version_compare.py           # Comparison tools
│   └── notebook_helper.py           # Notebook versioning helper
│
├── scripts/
│   ├── run_complete_pipeline_versioned.py  # Versioned pipeline
│   └── version_management/          # CLI tools
│       ├── list_versions.py         # List all versions
│       └── compare_versions.py      # Compare versions
│
└── docs/
    ├── VERSIONING_GUIDE.md          # User guide
    ├── NOTEBOOK_VERSIONING_GUIDE.md # Notebook guide
    └── versions/                    # Model version metadata
        └── v1.3.2.json
```

### Data Flow

```
┌────────────────────────────────────────────────────────────────┐
│  1. Start Pipeline Run                                          │
│     └─ Create run version (captures everything)                │
└────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│  2. Load Input Data                                             │
│     └─ Links to specific data versions                         │
└────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│  3. Execute Pipeline Steps                                      │
│     ├─ H3 hexagons                                             │
│     ├─ Grouping                                                │
│     ├─ Scoring                                                 │
│     └─ ... (all steps tracked)                                 │
└────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│  4. Save Results to Versioned Directory                         │
│     └─ data/results/run_YYYY-MM-DD_NN/                         │
└────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│  5. Finalize Run Version                                        │
│     ├─ Execution time                                          │
│     ├─ Results summary                                         │
│     ├─ Status (completed/failed)                               │
│     └─ Comparison with previous run                            │
└────────────────────────────────────────────────────────────────┘
```

---

## Key Features

### 1. Automatic Run Versioning

```python
# The versioned pipeline automatically:
# 1. Creates run version before execution
# 2. Captures all configuration
# 3. Links to input data versions
# 4. Tracks execution
# 5. Saves results to versioned directory
# 6. Finalizes with summary

# NO MANUAL WORK REQUIRED!
```

### 2. Reproducibility

```python
from src.versioning import RunVersion

# Load any historical run
run = RunVersion.load('run_2025-01-10_01')

# See exactly what was used
print(run.metadata['input_data_versions'])
print(run.metadata['configuration'])

# Re-run with exact same inputs
# (Implementation depends on your needs)
```

### 3. Comparison

```bash
# Compare any two runs
python scripts/version_management/compare_versions.py \
  --type runs \
  --version1 run_2025-01-10_01 \
  --version2 run_2025-01-17_01

# Shows:
# - Configuration differences
# - Data version differences
# - Results differences (hub counts, scores, etc.)
```

### 4. Query and Search

```bash
# List recent runs
python scripts/version_management/list_versions.py --type runs --limit 10

# Filter by tag
python scripts/version_management/list_versions.py --type runs --tag production

# Filter by status
python scripts/version_management/list_versions.py --type runs --status completed

# Get run details as JSON
python scripts/version_management/list_versions.py --type runs --limit 1 --json
```

---

## Migration Guide

### For Existing Pipelines

**Before:**
```bash
python scripts/run_complete_pipeline.py
```

**After:**
```bash
# Now use the versioned script
python scripts/run_complete_pipeline_versioned.py

# Or to keep old behavior:
python scripts/run_complete_pipeline_versioned.py --no-version
```

### For Existing Notebooks

**Before:**
```python
# Just run cells without versioning
import pandas as pd
# ... analysis ...
```

**After:**
```python
# Add versioning wrapper
from src.versioning.notebook_helper import NotebookVersioning

nb = NotebookVersioning(purpose="My analysis", tags=["test"])
nb.start()

# ... your existing analysis ...

nb.finish()
```

See `docs/NOTEBOOK_VERSIONING_GUIDE.md` for complete examples.

---

## Use Cases

### Use Case 1: Production Runs

```bash
# Monthly production run with full tracking
python scripts/run_complete_pipeline_versioned.py \
  --purpose "January 2025 production run for annual planning" \
  --user "planning.team@gov.il" \
  --tags "production,monthly,2025_01,validated"

# Results automatically saved to:
# data/results/run_2025-01-17_01/
```

### Use Case 2: Scenario Testing

```python
# Test multiple scenarios with versioning
for scenario in ['conservative', 'moderate', 'aggressive']:
    pipeline = VersionedHubPipeline(
        run_purpose=f"Growth scenario: {scenario}",
        tags=["scenario", f"growth_{scenario}", "test"]
    )
    # Modify data/config for scenario...
    results = pipeline.run()
```

### Use Case 3: Data Update Validation

```bash
# After updating input data, run pipeline to see impact
python scripts/run_complete_pipeline_versioned.py \
  --purpose "Validate Q1 2025 demand data update" \
  --tags "validation,data_update,q1_2025"

# Compare with previous run
python scripts/version_management/compare_versions.py \
  --type runs \
  --version1 run_2025-01-10_01 \  # Before update
  --version2 run_2025-01-17_01    # After update
```

### Use Case 4: Methodology Changes

```bash
# After changing scoring methodology
python scripts/run_complete_pipeline_versioned.py \
  --purpose "Test new accessibility scoring criterion" \
  --tags "methodology,accessibility,test"

# Compare results to validate improvement
```

---

## Best Practices

### 1. Always Use Versioning for Production

```bash
# ✅ Good
python scripts/run_complete_pipeline_versioned.py \
  --purpose "Production run for stakeholder presentation" \
  --tags "production,validated"

# ❌ Bad
python scripts/run_complete_pipeline.py  # No versioning
```

### 2. Use Descriptive Purposes

```bash
# ✅ Good
--purpose "Evaluate impact of metro line 3 on hub rankings with 2030 demand forecasts"

# ❌ Bad
--purpose "Test run"
```

### 3. Tag Systematically

```bash
# ✅ Good - consistent, searchable tagging
--tags "production,2025_Q1,validated,final"
--tags "scenario,metro_expansion,high_growth"
--tags "validation,data_update,demand_2050"

# ❌ Bad - vague or inconsistent
--tags "run1,test"
```

### 4. Review Before Important Decisions

```bash
# Before major planning decisions, compare recent runs
python scripts/version_management/list_versions.py --type runs --tag production

# Pick two and compare
python scripts/version_management/compare_versions.py ...
```

---

## FAQ

### Q: Does versioning slow down the pipeline?

**A:** Negligible impact (<1 second overhead). The versioning happens before/after the main pipeline execution.

### Q: How much storage does versioning use?

**A:** Each run stores:
- Results files (CSV, GeoJSON, HTML): ~5-50 MB
- Metadata (JSON): <1 MB
- Total: Similar to your current results storage

### Q: Can I delete old versions?

**A:** Yes, but keep important ones. Delete manually from `data/versions/` and `data/results/`. Consider archiving to external storage for long-term history.

### Q: What if I don't want versioning?

**A:** Use the `--no-version` flag:
```bash
python scripts/run_complete_pipeline_versioned.py --no-version
```

Or use the original script (though versioned is recommended).

### Q: Can I version runs retroactively?

**A:** No, versioning must be enabled when the run executes. However, you can manually create version metadata for old runs if needed.

### Q: How do I share a specific run with colleagues?

**A:**
1. Get the run ID: `run_2025-01-17_01`
2. Share the entire directory: `data/results/run_2025-01-17_01/`
3. They can copy it to their `data/results/` folder
4. It will appear in their version queries

---

## Troubleshooting

### Issue: "Could not get data versions"

**Symptom:** Warning when starting versioned run.

**Cause:** No data versions exist yet (first time using versioning).

**Solution:** This is normal for first run. Future runs will track data versions properly. You can manually create data versions:

```python
from src.versioning import create_data_version

create_data_version(
    data_type='transit_lines',
    source_file='data/raw/transit_lines.csv',
    notes='Initial data version'
)
```

### Issue: Pipeline fails with "No module named 'src.versioning'"

**Cause:** Python path not set correctly.

**Solution:** Run from project root:
```bash
cd /path/to/HubPrioritizing
python scripts/run_complete_pipeline_versioned.py
```

### Issue: Results not saved to versioned directory

**Cause:** Using old script or --no-version flag.

**Solution:** Use the versioned script without --no-version flag.

---

## Advanced Topics

### Custom Version Queries

```python
from src.versioning import VersionStore
import sqlite3

store = VersionStore()
conn = sqlite3.connect(store.db_path)

# Find all runs using specific data
cursor = conn.execute('''
    SELECT r.run_id, r.created_at, r.status
    FROM model_runs r
    JOIN run_data_dependencies d ON r.run_id = d.run_id
    WHERE d.data_version_id = ?
''', ('data_transit_lines_2025-01-17_143045',))

for row in cursor:
    print(f"{row[0]}: {row[1]} - {row[2]}")
```

### Automated Comparison Reports

```bash
# Script to compare latest production run with previous
#!/bin/bash

# Get last two production runs
RUNS=$(python scripts/version_management/list_versions.py \
  --type runs --tag production --limit 2 --json | \
  jq -r '.[].run_version_id')

RUN_ARRAY=($RUNS)
LATEST="${RUN_ARRAY[0]}"
PREVIOUS="${RUN_ARRAY[1]}"

# Compare
python scripts/version_management/compare_versions.py \
  --type runs \
  --version1 "$PREVIOUS" \
  --version2 "$LATEST" \
  --format json \
  --output comparison_report.json
```

### Integration with External Systems

```python
# Export run metadata to external tracking system
from src.versioning import RunVersion
import requests

run = RunVersion.load('run_2025-01-17_01')

# Send to external system
response = requests.post('https://your-system.com/api/runs', json={
    'run_id': run.run_id,
    'model_version': run.metadata['model_version']['code_version'],
    'total_hubs': run.metadata['results_summary']['total_hubs'],
    'execution_time': run.metadata['execution_time_seconds']
})
```

---

## Summary

### What You Get

✅ **Full Reproducibility** - Re-run any historical analysis exactly
✅ **Complete Audit Trail** - Know what produced each result
✅ **Easy Comparison** - Diff any two versions instantly
✅ **Quality Control** - Track methodology changes over time
✅ **Collaboration** - Share exact run configurations
✅ **Compliance** - Meet data governance requirements

### Minimal Effort

- **Pipelines**: Just use the versioned script - it's automatic!
- **Notebooks**: Add 3 cells (start, optional saves, finish)
- **Query**: Simple CLI commands to list and compare

### Next Steps

1. **Try it**: Run the versioned pipeline once
2. **Compare**: Compare with a previous run
3. **Integrate**: Add versioning to your notebooks
4. **Share**: Share run IDs with colleagues

---

**Version:** 1.0.0
**Last Updated:** 2025-01-17
**Questions?** See `docs/VERSIONING_GUIDE.md` for detailed documentation
