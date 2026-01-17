# Versioning System Design
**Comprehensive Version Management for Hub Prioritization Framework**

## Table of Contents
1. [Overview](#overview)
2. [Versioning Schema](#versioning-schema)
3. [Version Types](#version-types)
4. [Implementation](#implementation)
5. [Usage Examples](#usage-examples)
6. [Integration](#integration)

---

## 1. Overview

### Purpose
Track and manage versions across three dimensions:
1. **Input Data Versions** - Each data type (lines, stations, demand, spatial layers)
2. **Model Run Versions** - Each execution of the complete pipeline
3. **Model Code Versions** - Code and methodology changes

### Key Goals
- ✅ **Reproducibility**: Re-run any historical model version with exact inputs
- ✅ **Traceability**: Know exactly what data and code produced each result
- ✅ **Comparison**: Compare results across versions
- ✅ **Auditing**: Complete history of all changes
- ✅ **Rollback**: Restore previous states if needed

### Versioning Strategy

**Semantic Versioning for Model Code:**
- Format: `MAJOR.MINOR.PATCH`
- Example: `1.3.2`
- MAJOR: Breaking changes to methodology
- MINOR: New features, criteria, or improvements
- PATCH: Bug fixes, minor corrections

**Date-based Versioning for Data:**
- Format: `YYYY-MM-DD` or `YYYY-MM-DD_HHmmss` for multiple updates per day
- Example: `2025-01-17` or `2025-01-17_143045`

**Sequential Versioning for Model Runs:**
- Format: `run_NNNN` or `YYYY-MM-DD_run_NN`
- Example: `run_0042` or `2025-01-17_run_01`

---

## 2. Versioning Schema

### 2.1 Input Data Version

**Metadata Structure:**
```json
{
  "data_version_id": "data_2025-01-17_143045",
  "created_at": "2025-01-17T14:30:45Z",
  "data_type": "transit_lines",
  "source_file": "transit_lines_update.csv",
  "source_file_hash": "sha256:abc123...",
  "record_count": 87,
  "changes_from_previous": {
    "previous_version": "data_2025-01-10_120000",
    "records_added": 3,
    "records_modified": 2,
    "records_removed": 1,
    "summary": "Added Metro Line 3, updated TLV M1 status"
  },
  "validation": {
    "status": "passed",
    "errors": 0,
    "warnings": 2
  },
  "created_by": "user@example.com",
  "notes": "Added planned metro extension lines",
  "tags": ["planned_2030", "metro_expansion"]
}
```

**Data Types Tracked:**
- `transit_lines` - Transit line definitions
- `transit_stations` - Station/node locations
- `demand_2050` - Demand forecasts
- `metro_areas` - Metropolitan area boundaries
- `taz_zones` - Traffic analysis zones with population/employment
- `bus_terminals` - Bus terminal locations
- `manual_overrides` - Manual demand/grouping corrections

### 2.2 Model Run Version

**Metadata Structure:**
```json
{
  "run_version_id": "run_2025-01-17_01",
  "run_number": 42,
  "created_at": "2025-01-17T15:00:00Z",
  "status": "completed",
  "execution_time_seconds": 287.5,

  "model_version": {
    "code_version": "1.3.2",
    "git_commit": "4e90c26a1b2c3d4e5f6g7h8i9j0k",
    "git_branch": "main"
  },

  "input_data_versions": {
    "transit_lines": "data_2025-01-17_143045",
    "transit_stations": "data_2025-01-17_143045",
    "demand_2050": "data_2025-01-17_143045",
    "metro_areas": "data_2024-12-01_000000",
    "taz_zones": "data_2024-12-01_000000",
    "bus_terminals": "data_2024-11-15_000000",
    "manual_overrides": "data_2025-01-10_120000"
  },

  "configuration": {
    "h3_resolution": 10,
    "hub_merge_threshold_m": 120,
    "eligibility_min_passengers": 1000,
    "monte_carlo_iterations": 10000,
    "ahp_enabled": false,
    "require_non_rail_mode": true
  },

  "results_summary": {
    "total_nodes": 1245,
    "total_hexes": 876,
    "total_hubs": 86,
    "hubs_by_tier": {
      "ארצי": 15,
      "מטרופוליני": 46,
      "עירוני": 25
    },
    "hubs_by_area": {
      "Tel Aviv": 35,
      "Haifa": 18,
      "South": 8,
      "Jerusalem": 12,
      "North": 13
    }
  },

  "output_files": [
    "data/results/run_2025-01-17_01/scored_hubs.csv",
    "data/results/run_2025-01-17_01/scored_hubs.geojson",
    "data/results/run_2025-01-17_01/hub_map.html"
  ],

  "comparison_to_previous": {
    "previous_run": "run_2025-01-10_01",
    "hub_count_change": 3,
    "new_hubs": ["group_123", "group_124", "group_125"],
    "removed_hubs": [],
    "tier_changes": [
      {"hub": "group_045", "from": "מטרופוליני", "to": "ארצי"}
    ]
  },

  "created_by": "user@example.com",
  "run_purpose": "Evaluate metro expansion scenarios",
  "notes": "First run with new metro lines included",
  "tags": ["scenario_metro_2030", "production"]
}
```

### 2.3 Model Code Version

**Metadata Structure:**
```json
{
  "model_version": "1.3.2",
  "version_date": "2025-01-15",
  "version_type": "minor",

  "changes": [
    {
      "type": "feature",
      "description": "Added AHP scoring as alternative to Monte Carlo",
      "files_modified": [
        "src/scoring/ahp.py",
        "src/config.py"
      ],
      "breaking_change": false
    },
    {
      "type": "improvement",
      "description": "Enhanced mode weight calculation for suburban rail",
      "files_modified": [
        "src/scoring/service.py",
        "src/config.py"
      ],
      "breaking_change": false
    }
  ],

  "methodology_changes": {
    "scoring_criteria": {
      "modified": ["service_score"],
      "added": ["ahp_score"],
      "removed": []
    },
    "thresholds": {
      "mode_weights": {
        "Suburban Rail": {"from": 5.0, "to": 6.0},
        "Metro": {"from": 5.0, "to": 6.0}
      }
    },
    "algorithms": {
      "added": ["AHP pairwise comparison"],
      "modified": [],
      "removed": []
    }
  },

  "backward_compatible": true,
  "migration_required": false,
  "migration_guide": null,

  "git_info": {
    "tag": "v1.3.2",
    "commit": "4e90c26a1b2c3d4e5f6g7h8i9j0k",
    "branch": "main",
    "release_notes_url": "https://github.com/org/repo/releases/tag/v1.3.2"
  },

  "dependencies": {
    "python": ">=3.9",
    "key_packages": {
      "pandas": ">=1.5.0",
      "geopandas": ">=0.12.0",
      "h3": ">=3.7.0",
      "numpy": ">=1.23.0"
    }
  },

  "validation": {
    "tests_passed": true,
    "test_coverage": 87.5,
    "benchmark_performance": "285s (baseline: 290s)"
  },

  "authors": ["team@example.com"],
  "reviewed_by": ["reviewer@example.com"],
  "approved_by": ["lead@example.com"],

  "notes": "AHP provides alternative weighting method for stakeholder engagement"
}
```

---

## 3. Version Types

### 3.1 Input Data Versions

**What's Versioned:**
- Each input file gets a version when updated
- Version created on successful validation
- Stored in `data/versions/{data_type}/`

**Naming Convention:**
```
data_{data_type}_{YYYY-MM-DD}_{HHmmss}
```

**Examples:**
- `data_transit_lines_2025-01-17_143045`
- `data_demand_2050_2025-01-17_143045`
- `data_metro_areas_2024-12-01_000000`

**Storage:**
- Original file: `data/versions/transit_lines/data_2025-01-17_143045/transit_lines.csv`
- Metadata: `data/versions/transit_lines/data_2025-01-17_143045/metadata.json`
- Validation report: `data/versions/transit_lines/data_2025-01-17_143045/validation_report.txt`

### 3.2 Model Run Versions

**What's Versioned:**
- Complete pipeline execution
- Links to input data versions used
- Configuration snapshot
- Results and outputs

**Naming Convention:**
```
run_{YYYY-MM-DD}_{NN}
```

**Examples:**
- `run_2025-01-17_01` (first run on Jan 17)
- `run_2025-01-17_02` (second run same day)

**Storage:**
- Results: `data/results/run_2025-01-17_01/`
- Metadata: `data/results/run_2025-01-17_01/run_metadata.json`
- Config snapshot: `data/results/run_2025-01-17_01/config_snapshot.json`
- Logs: `data/results/run_2025-01-17_01/pipeline.log`

### 3.3 Model Code Versions

**What's Versioned:**
- Code changes (tracked via git tags)
- Methodology changes
- Parameter/threshold updates
- Algorithm modifications

**Naming Convention:**
```
v{MAJOR}.{MINOR}.{PATCH}
```

**Examples:**
- `v1.0.0` - Initial release
- `v1.3.2` - Current version
- `v2.0.0` - Major methodology change

**Storage:**
- Git tags for code
- Metadata: `docs/versions/v1.3.2.json`
- Release notes: `docs/CHANGELOG.md`

---

## 4. Implementation

### 4.1 Directory Structure

```
HubPrioritizing/
├── data/
│   ├── versions/                      # NEW: Versioned input data
│   │   ├── transit_lines/
│   │   │   ├── data_2025-01-17_143045/
│   │   │   │   ├── transit_lines.csv
│   │   │   │   ├── metadata.json
│   │   │   │   └── validation_report.txt
│   │   │   └── data_2025-01-10_120000/
│   │   │       └── ...
│   │   ├── transit_stations/
│   │   ├── demand_2050/
│   │   ├── metro_areas/
│   │   └── ...
│   │
│   ├── results/                       # MODIFIED: Versioned model runs
│   │   ├── run_2025-01-17_01/
│   │   │   ├── run_metadata.json
│   │   │   ├── config_snapshot.json
│   │   │   ├── scored_hubs.csv
│   │   │   ├── scored_hubs.geojson
│   │   │   ├── hub_map.html
│   │   │   └── pipeline.log
│   │   └── run_2025-01-10_01/
│   │       └── ...
│   │
│   └── current/                       # NEW: Symlinks to latest versions
│       ├── transit_lines.csv -> ../versions/transit_lines/data_2025-01-17_143045/transit_lines.csv
│       ├── transit_stations.csv -> ...
│       └── ...
│
├── src/
│   └── versioning/                    # NEW: Versioning modules
│       ├── __init__.py
│       ├── data_version.py            # Input data versioning
│       ├── run_version.py             # Model run versioning
│       ├── model_version.py           # Code version management
│       ├── version_store.py           # Version metadata storage
│       └── version_compare.py         # Version comparison tools
│
├── scripts/
│   └── version_management/            # NEW: Version management CLI
│       ├── create_data_version.py
│       ├── create_run_version.py
│       ├── list_versions.py
│       ├── compare_versions.py
│       ├── restore_version.py
│       └── export_version_report.py
│
├── docs/
│   └── versions/                      # NEW: Model version metadata
│       ├── v1.0.0.json
│       ├── v1.3.2.json
│       └── CHANGELOG.md
│
└── VERSION                            # Current model version file
```

### 4.2 Core Modules

Will implement:
1. `src/versioning/data_version.py` - Create and manage data versions
2. `src/versioning/run_version.py` - Track model run versions
3. `src/versioning/model_version.py` - Manage code versions
4. `src/versioning/version_store.py` - Storage backend (JSON + SQLite index)
5. `src/versioning/version_compare.py` - Compare versions and generate diffs

### 4.3 CLI Tools

Will implement:
1. `scripts/version_management/create_data_version.py` - Version new input data
2. `scripts/version_management/list_versions.py` - List all versions
3. `scripts/version_management/compare_versions.py` - Compare two versions
4. `scripts/version_management/restore_version.py` - Restore old version
5. `scripts/version_management/export_version_report.py` - Generate reports

---

## 5. Usage Examples

### 5.1 Create Data Version

```bash
# Automatic versioning when uploading new data
python scripts/update_transit_data/apply_transit_update.py

# Manual versioning
python scripts/version_management/create_data_version.py \
  --data-type transit_lines \
  --source-file data/uploads/transit_lines_update.csv \
  --notes "Added metro line 3 and BRT extensions"
```

### 5.2 Run Pipeline with Versioning

```bash
# Pipeline automatically creates run version
python scripts/run_complete_pipeline.py \
  --run-purpose "Evaluate 2030 metro scenario" \
  --tags "scenario_2030,metro_expansion"

# Output:
# Created run version: run_2025-01-17_01
# Results saved to: data/results/run_2025-01-17_01/
```

### 5.3 List Versions

```bash
# List all data versions
python scripts/version_management/list_versions.py --type data

# List recent model runs
python scripts/version_management/list_versions.py --type runs --limit 10

# List by tag
python scripts/version_management/list_versions.py --tag "production"
```

### 5.4 Compare Versions

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
  --version2 run_2025-01-17_01 \
  --output comparison_report.html
```

### 5.5 Restore Previous Version

```bash
# Restore a previous data version as current
python scripts/version_management/restore_version.py \
  --type data \
  --data-type transit_lines \
  --version data_2025-01-10_120000 \
  --create-backup

# Re-run a previous model run configuration
python scripts/version_management/restore_version.py \
  --type run \
  --run run_2025-01-10_01 \
  --rerun
```

### 5.6 Export Version Report

```bash
# Generate comprehensive version history report
python scripts/version_management/export_version_report.py \
  --output version_history.html \
  --include-data \
  --include-runs \
  --date-from 2024-01-01
```

---

## 6. Integration

### 6.1 Pipeline Integration

**Automatic Versioning:**
- Pipeline automatically creates run version on each execution
- Links to current data versions
- Captures configuration snapshot
- Stores all outputs in versioned directory

**Modified Pipeline Flow:**
```python
# At start of pipeline
run_version = create_run_version(
    model_version=MODEL_VERSION,
    input_data_versions=get_current_data_versions(),
    configuration=config.to_dict(),
    run_purpose=args.purpose,
    tags=args.tags
)

# Run pipeline steps...
# ...

# At end of pipeline
finalize_run_version(
    run_version=run_version,
    results_summary=compute_results_summary(),
    output_files=output_file_list,
    status='completed'
)
```

### 6.2 Data Update Integration

**Automatic Data Versioning:**
- When uploading new data via GUI or CLI
- Validation must pass before version is created
- Old data automatically archived
- `data/current/` symlinks updated

**Modified Update Flow:**
```python
# After successful validation
data_version = create_data_version(
    data_type='transit_lines',
    source_file=uploaded_file,
    validation_report=validation_results,
    changes_summary=compute_changes(previous_version, new_data),
    created_by=user_email,
    notes=user_notes
)

# Update current symlink
update_current_data_link(data_type='transit_lines', version=data_version)
```

### 6.3 Git Integration

**Model Code Versions:**
- Semantic version tags in git: `v1.3.2`
- Changelog maintained in `docs/CHANGELOG.md`
- Version metadata in `docs/versions/v1.3.2.json`
- `VERSION` file at project root

**Tagging Workflow:**
```bash
# Create new model version
python scripts/version_management/create_model_version.py \
  --version 1.3.2 \
  --type minor \
  --changes "Added AHP scoring, enhanced mode weights" \
  --git-tag

# Automatically creates:
# - Git tag: v1.3.2
# - Metadata: docs/versions/v1.3.2.json
# - Updates: VERSION file
# - Updates: docs/CHANGELOG.md
```

---

## 7. Version Comparison Features

### 7.1 Data Version Comparison

Compare two data versions:
- Records added/modified/removed
- Field-level changes
- Spatial changes (for geographic data)
- Summary statistics

### 7.2 Run Version Comparison

Compare two model runs:
- Hub count changes
- Tier classification changes
- Score changes (by hub)
- New/removed hubs
- Configuration differences

### 7.3 Model Version Comparison

Compare two code versions:
- Code changes (via git diff)
- Methodology changes
- Parameter/threshold changes
- Performance changes

---

## 8. Query API

### 8.1 Python API

```python
from src.versioning import VersionStore

vs = VersionStore()

# Get latest data version
latest_lines = vs.get_latest_data_version('transit_lines')

# Get specific run
run = vs.get_run_version('run_2025-01-17_01')

# Query runs by tag
production_runs = vs.query_runs(tags=['production'])

# Get all runs using specific data version
runs = vs.get_runs_using_data('data_transit_lines_2025-01-17_143045')

# Compare two runs
diff = vs.compare_runs('run_2025-01-10_01', 'run_2025-01-17_01')
```

### 8.2 CLI API

```bash
# Query latest version
version-query --type data --data-type transit_lines --latest

# Query by date range
version-query --type runs --from 2025-01-01 --to 2025-01-31

# Query by tag
version-query --tag "production" --format json

# Get run details
version-query --run run_2025-01-17_01 --verbose
```

---

## 9. Metadata Storage

### 9.1 Storage Backend

**Primary: JSON Files**
- Human-readable
- Easy to version control
- Self-contained

**Index: SQLite Database**
- Fast querying
- Complex filters
- Relationship tracking

**Files:**
- `data/versions/index.db` - SQLite index
- `data/versions/{type}/{version}/metadata.json` - Individual metadata

### 9.2 Database Schema

```sql
-- Data versions
CREATE TABLE data_versions (
    version_id TEXT PRIMARY KEY,
    data_type TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    source_file TEXT,
    file_hash TEXT,
    record_count INTEGER,
    created_by TEXT,
    notes TEXT,
    tags TEXT  -- JSON array
);

-- Model runs
CREATE TABLE model_runs (
    run_id TEXT PRIMARY KEY,
    run_number INTEGER,
    created_at TIMESTAMP NOT NULL,
    model_version TEXT,
    git_commit TEXT,
    status TEXT,
    execution_time REAL,
    created_by TEXT,
    run_purpose TEXT,
    notes TEXT,
    tags TEXT  -- JSON array
);

-- Run data dependencies
CREATE TABLE run_data_dependencies (
    run_id TEXT,
    data_type TEXT,
    data_version_id TEXT,
    FOREIGN KEY (run_id) REFERENCES model_runs(run_id),
    FOREIGN KEY (data_version_id) REFERENCES data_versions(version_id)
);

-- Model versions
CREATE TABLE model_versions (
    version TEXT PRIMARY KEY,
    version_date DATE NOT NULL,
    version_type TEXT,
    git_tag TEXT,
    git_commit TEXT,
    backward_compatible BOOLEAN,
    notes TEXT
);
```

---

## 10. Benefits

### Reproducibility
- ✅ Re-run any historical analysis exactly
- ✅ Verify results from previous runs
- ✅ Test methodology changes against historical data

### Traceability
- ✅ Know exactly what data produced each result
- ✅ Track data lineage
- ✅ Audit trail for compliance

### Comparison
- ✅ Compare results over time
- ✅ Analyze impact of data updates
- ✅ Evaluate methodology improvements

### Collaboration
- ✅ Share specific versions with stakeholders
- ✅ Document decisions and changes
- ✅ Enable parallel scenario development

### Quality Control
- ✅ Rollback bad data or runs
- ✅ A/B test different approaches
- ✅ Benchmark performance over time

---

**Document Version:** 1.0
**Last Updated:** 2025-01-17
**Status:** Design Ready for Implementation
