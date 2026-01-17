# Versioning System User Guide
**Hub Prioritization Framework - Version Management**

## Quick Start

### Check Current Versions

```bash
# List recent data versions
python scripts/version_management/list_versions.py --type data --limit 10

# List recent model runs
python scripts/version_management/list_versions.py --type runs --limit 10

# Check current model version
cat VERSION
```

### Compare Versions

```bash
# Compare two data versions
python scripts/version_management/compare_versions.py \
  --type data \
  --version1 data_transit_lines_2025-01-10_120000 \
  --version2 data_transit_lines_2025-01-17_143045

# Compare two model runs
python scripts/version_management/compare_versions.py \
  --type runs \
  --version1 run_2025-01-10_01 \
  --version2 run_2025-01-17_01
```

---

## Overview

The versioning system tracks three types of versions:

1. **Input Data Versions** - Every time you upload new data
2. **Model Run Versions** - Every time you run the pipeline
3. **Model Code Versions** - When code or methodology changes

---

## 1. Input Data Versioning

### What Gets Versioned

Every input data file is versioned when uploaded or updated:
- Transit lines (`transit_lines.csv`)
- Transit stations (`transit_stations.csv`)
- Demand forecasts (`demand_2050.csv`)
- Spatial layers (metro areas, TAZ zones, terminals)
- Manual overrides

### Version Naming

Format: `data_{data_type}_{YYYY-MM-DD}_{HHmmss}`

Example: `data_transit_lines_2025-01-17_143045`

### Creating Data Versions

**Automatic (via update system):**
```bash
# When you upload via GUI or CLI, version is created automatically
python scripts/update_transit_data/apply_transit_update.py
```

**Manual:**
```python
from src.versioning import create_data_version

version = create_data_version(
    data_type='transit_lines',
    source_file='path/to/transit_lines_update.csv',
    created_by='planner@example.com',
    notes='Added metro line 3',
    tags=['metro_expansion', '2030_scenario']
)

print(f"Created version: {version.version_id}")
```

### Listing Data Versions

```bash
# All data versions
python scripts/version_management/list_versions.py --type data

# Filter by data type
python scripts/version_management/list_versions.py --type data --data-type transit_lines

# Show verbose info
python scripts/version_management/list_versions.py --type data --verbose

# Export as JSON
python scripts/version_management/list_versions.py --type data --json > versions.json
```

### Comparing Data Versions

```bash
python scripts/version_management/compare_versions.py \
  --type data \
  --version1 data_transit_lines_2025-01-10_120000 \
  --version2 data_transit_lines_2025-01-17_143045
```

Output shows:
- Record count changes
- Added/removed/modified records
- Specific field changes

### Accessing Versioned Data

**Via Python API:**
```python
from src.versioning import DataVersion

# Load a specific version
version = DataVersion.load('data_transit_lines_2025-01-17_143045')

# Get the data as DataFrame
df = version.load_data()

# Get file path
file_path = version.get_file_path()
```

**Via filesystem:**
```
data/versions/transit_lines/data_2025-01-17_143045/
├── transit_lines.csv          # The actual data
├── metadata.json              # Version metadata
└── validation_report.json     # Validation results
```

---

## 2. Model Run Versioning

### What Gets Versioned

Every pipeline execution creates a run version that captures:
- Model code version used
- All input data versions used
- Configuration snapshot
- Execution time and status
- Results summary
- Output files

### Version Naming

Format: `run_{YYYY-MM-DD}_{NN}`

Example: `run_2025-01-17_01` (first run on Jan 17)

### Creating Run Versions

**Automatic (recommended):**

The pipeline automatically creates run versions when you execute it:

```bash
python scripts/run_complete_pipeline.py
```

**Programmatic:**

```python
from src.versioning import create_run_version, finalize_run_version
from src.config import *
import time

# Create run version at start
run_version = create_run_version(
    model_version='1.3.2',
    configuration={
        'h3_resolution': H3_RESOLUTION,
        'monte_carlo_iterations': MONTE_CARLO_ITERATIONS,
        # ... other config
    },
    run_purpose='Evaluate metro expansion scenario',
    created_by='planner@example.com',
    tags=['scenario_2030', 'metro']
)

# Update status as running
run_version.update_status('running')

# Run your pipeline...
start_time = time.time()
# ... execute pipeline steps ...
execution_time = time.time() - start_time

# Finalize when complete
finalize_run_version(
    run_version=run_version,
    results_summary={
        'total_nodes': 1245,
        'total_hubs': 86,
        'hubs_by_tier': {'ארצי': 15, 'מטרופוליני': 46, 'עירוני': 25}
    },
    output_files=[
        Path('data/results/run_2025-01-17_01/scored_hubs.csv'),
        Path('data/results/run_2025-01-17_01/hub_map.html')
    ],
    status='completed'
)
```

### Listing Run Versions

```bash
# All runs
python scripts/version_management/list_versions.py --type runs

# Recent runs
python scripts/version_management/list_versions.py --type runs --limit 20

# Filter by status
python scripts/version_management/list_versions.py --type runs --status completed

# Filter by tag
python scripts/version_management/list_versions.py --type runs --tag production
```

### Comparing Run Versions

```bash
python scripts/version_management/compare_versions.py \
  --type runs \
  --version1 run_2025-01-10_01 \
  --version2 run_2025-01-17_01
```

Shows:
- Model version differences
- Configuration changes
- Input data version changes
- Results differences (hub counts, tier changes, etc.)

### Accessing Run Results

**Via Python API:**
```python
from src.versioning import RunVersion

# Load a run
run = RunVersion.load('run_2025-01-17_01')

# Get results directory
results_dir = run.get_results_dir()

# Get output files
output_files = run.get_output_files()

# Get metadata
print(run.metadata['results_summary'])
print(run.metadata['execution_time_seconds'])
```

**Via filesystem:**
```
data/results/run_2025-01-17_01/
├── run_metadata.json          # Complete run metadata
├── config_snapshot.json       # Configuration used
├── scored_hubs.csv           # Main results
├── scored_hubs.geojson       # Spatial results
├── hub_map.html              # Interactive map
└── pipeline.log              # Execution log
```

---

## 3. Model Code Versioning

### What Gets Versioned

Model code versions track:
- Code changes (via git tags)
- Methodology changes
- Parameter/threshold updates
- Algorithm modifications
- Dependencies

### Version Naming

Format: `v{MAJOR}.{MINOR}.{PATCH}`

Example: `v1.3.2`

**Semantic versioning:**
- **MAJOR**: Breaking methodology changes (e.g., new scoring criteria)
- **MINOR**: New features, improvements (e.g., add AHP scoring)
- **PATCH**: Bug fixes, minor corrections

### Current Model Version

```bash
cat VERSION
# Output: 1.3.2
```

### Creating Model Versions

```python
from src.versioning import create_model_version

version = create_model_version(
    version='1.4.0',
    version_type='minor',
    changes=[
        {
            'type': 'feature',
            'description': 'Added accessibility scoring criterion',
            'files_modified': ['src/scoring/accessibility.py', 'src/config.py'],
            'breaking_change': False
        },
        {
            'type': 'improvement',
            'description': 'Enhanced mode weight calculation',
            'files_modified': ['src/scoring/service.py'],
            'breaking_change': False
        }
    ],
    methodology_changes={
        'scoring_criteria': {
            'added': ['accessibility_score'],
            'modified': ['service_score'],
            'removed': []
        },
        'thresholds': {}
    },
    git_commit='abc123def456',
    backward_compatible=True,
    notes='Improved scoring methodology for accessibility'
)
```

This automatically:
- Creates `docs/versions/v1.4.0.json` with metadata
- Updates `VERSION` file
- Updates `docs/CHANGELOG.md`
- Saves to version database

### Viewing Model Versions

**Current version:**
```bash
cat VERSION
```

**Version history:**
```bash
cat docs/CHANGELOG.md
```

**Version metadata:**
```bash
cat docs/versions/v1.3.2.json
```

**Via Python:**
```python
from src.versioning import ModelVersion, get_current_model_version

# Get current version
current_version = get_current_model_version()
print(f"Current model version: {current_version}")

# Load version metadata
version = ModelVersion.load('1.3.2')
print(version.metadata)
```

---

## 4. Common Workflows

### Workflow 1: Update Data and Run Pipeline

```bash
# 1. Upload new data (creates data version automatically)
python scripts/update_transit_data/apply_transit_update.py

# 2. List data versions to verify
python scripts/version_management/list_versions.py --type data --limit 5

# 3. Run pipeline (creates run version automatically)
python scripts/run_complete_pipeline.py

# 4. Check the run version
python scripts/version_management/list_versions.py --type runs --limit 1 --verbose
```

### Workflow 2: Compare Before/After

```bash
# Get IDs of last two runs
python scripts/version_management/list_versions.py --type runs --limit 2

# Compare them
python scripts/version_management/compare_versions.py \
  --type runs \
  --version1 run_2025-01-10_01 \
  --version2 run_2025-01-17_01 \
  --format json \
  --output comparison_report.json
```

### Workflow 3: Reproduce Historical Run

```python
from src.versioning import RunVersion, DataVersion, VersionStore

store = VersionStore()

# Load the historical run
old_run = RunVersion.load('run_2025-01-10_01', store)

# Get the exact data versions used
data_versions = old_run.metadata['input_data_versions']

# Load each data version
for data_type, version_id in data_versions.items():
    data_version = DataVersion.load(version_id, store)
    df = data_version.load_data()
    # Use this data for re-running...

# Get the exact configuration
config = old_run.metadata['configuration']

# Re-run with same inputs and config
# (Implementation depends on your pipeline structure)
```

---

## 5. Python API Reference

### VersionStore

Central storage and retrieval:

```python
from src.versioning import VersionStore

store = VersionStore()

# Data versions
latest_lines = store.get_latest_data_version('transit_lines')
all_lines_versions = store.list_data_versions(data_type='transit_lines')
specific_version = store.get_data_version('data_transit_lines_2025-01-17_143045')

# Model runs
latest_runs = store.list_run_versions(limit=10)
completed_runs = store.list_run_versions(status='completed')
tagged_runs = store.list_run_versions(tags=['production'])

# Find runs using specific data
runs_with_data = store.get_runs_using_data('data_transit_lines_2025-01-17_143045')
```

### DataVersion

```python
from src.versioning import DataVersion, create_data_version

# Create new version
version = create_data_version(
    data_type='transit_lines',
    source_file='path/to/file.csv',
    notes='Added new lines',
    tags=['update_2025']
)

# Load existing version
version = DataVersion.load('data_transit_lines_2025-01-17_143045')

# Access data
df = version.load_data()
file_path = version.get_file_path()

# Compare with another version
comparison = version.compare_with('data_transit_lines_2025-01-10_120000')
```

### RunVersion

```python
from src.versioning import RunVersion, create_run_version, finalize_run_version

# Create run version
run = create_run_version(
    model_version='1.3.2',
    configuration={...},
    run_purpose='Test scenario',
    tags=['test']
)

# Update status
run.update_status('running')

# Finalize
finalize_run_version(
    run_version=run,
    results_summary={...},
    output_files=[...],
    status='completed'
)

# Load and access
run = RunVersion.load('run_2025-01-17_01')
results_dir = run.get_results_dir()
output_files = run.get_output_files()
```

---

## 6. Best Practices

### Version Tagging

Use tags to categorize versions:

```python
# Production runs
tags=['production', '2025_Q1']

# Scenario testing
tags=['scenario_metro_2030', 'test']

# Data updates
tags=['annual_update', 'verified']
```

### Documentation

Always include notes:

```python
create_data_version(
    ...,
    notes='Updated demand from National Model Q1 2025 - verified by planning team'
)

create_run_version(
    ...,
    run_purpose='Production run for 2030 transport plan - final version for stakeholder presentation'
)
```

### Regular Cleanup

Periodically review and archive old versions:

```bash
# List old versions
python scripts/version_management/list_versions.py --type runs --limit 100

# Consider archiving runs older than 6 months
# (Archive functionality to be implemented)
```

---

## 7. Troubleshooting

### Issue: Version not found

**Symptom:**
```
ValueError: Data version not found: data_transit_lines_2025-01-17_143045
```

**Solution:**
```bash
# Check if version exists
python scripts/version_management/list_versions.py --type data --data-type transit_lines

# Check filesystem
ls -la data/versions/transit_lines/
```

### Issue: Run comparison shows no results

**Symptom:**
Comparison returns empty results.

**Solution:**
Ensure both runs have `results_summary` populated - this requires running `finalize_run_version()` after pipeline completes.

### Issue: Slow version queries

**Symptom:**
Listing versions takes a long time.

**Solution:**
The SQLite index should make queries fast. If slow, check:
```bash
# Check database size
ls -lh data/versions/index.db

# Rebuild index if needed
# (Rebuild functionality to be implemented)
```

---

## 8. Advanced Usage

### Custom Version Queries

```python
from src.versioning import VersionStore
import sqlite3

store = VersionStore()
conn = sqlite3.connect(store.db_path)
cursor = conn.cursor()

# Find all runs using a specific data version
cursor.execute('''
    SELECT r.run_id, r.created_at, r.status
    FROM model_runs r
    JOIN run_data_dependencies d ON r.run_id = d.run_id
    WHERE d.data_version_id = ?
    ORDER BY r.created_at DESC
''', ('data_transit_lines_2025-01-17_143045',))

for row in cursor.fetchall():
    print(f"Run: {row[0]}, Created: {row[1]}, Status: {row[2]}")

conn.close()
```

### Exporting Version History

```python
from src.versioning import VersionStore
import json

store = VersionStore()

# Export all runs to JSON
runs = store.list_run_versions()

with open('run_history.json', 'w', encoding='utf-8') as f:
    json.dump(runs, f, indent=2, ensure_ascii=False)
```

---

## 9. Integration with Pipeline

The pipeline should automatically version runs. Example integration:

```python
# In your pipeline script
from src.versioning import create_run_version, finalize_run_version
from src.config import *

def run_pipeline():
    # Create run version at start
    run_version = create_run_version(
        model_version=get_current_model_version(),
        configuration={
            'h3_resolution': H3_RESOLUTION,
            'monte_carlo_iterations': MONTE_CARLO_ITERATIONS,
            # ... all config values
        },
        run_purpose=args.purpose if args.purpose else 'Regular pipeline run',
        created_by=args.user if args.user else 'system',
        tags=args.tags.split(',') if args.tags else []
    )

    logger.info(f"Created run version: {run_version.run_id}")

    # Update to running
    run_version.update_status('running')

    try:
        # Execute pipeline steps
        results = execute_all_steps()

        # Finalize with results
        finalize_run_version(
            run_version=run_version,
            results_summary=results['summary'],
            output_files=results['output_files'],
            status='completed'
        )

        logger.info(f"Run {run_version.run_id} completed successfully")

    except Exception as e:
        # Mark as failed
        run_version.update_status('failed')
        logger.error(f"Run {run_version.run_id} failed: {e}")
        raise
```

---

**Version:** 1.0.0
**Last Updated:** 2025-01-17
**For Help:** See VERSIONING_SYSTEM_DESIGN.md for technical details
