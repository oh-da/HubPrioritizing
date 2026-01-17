# Transit Update System Design
**Easy Data Update for Transit Lines and Demand**

## Table of Contents
1. [Overview](#overview)
2. [Current System Analysis](#current-system-analysis)
3. [Standardized Input File Formats](#standardized-input-file-formats)
4. [Update Process Workflow](#update-process-workflow)
5. [GUI Design](#gui-design)
6. [Implementation Plan](#implementation-plan)
7. [Technical Architecture](#technical-architecture)

---

## 1. Overview

### Purpose
Create a user-friendly system for updating transit network data (lines, modes, stations) and demand forecasts without requiring direct code modification or deep technical knowledge.

### Key Goals
- ✅ **Standardized Input**: Clear, well-documented CSV/Excel formats
- ✅ **Non-Technical Friendly**: Planners can update data without coding
- ✅ **Validation**: Automatic checks for data quality and consistency
- ✅ **Traceable**: Version control and audit trail for all updates
- ✅ **GUI Interface**: Web-based tool for data upload and validation
- ✅ **Backward Compatible**: Works with existing pipeline

---

## 2. Current System Analysis

### Existing Data Inputs

**Transit Network Data:**
- `All_nodes+lines.csv`: Node IDs, coordinates, LINE_IDs (encoding: windows-1255)
  - Columns: `node`, `LINE_ID`, `X`, `Y`, `geometry`
- `Lines_and_Planned_Mode.csv`: Line-to-mode mapping
  - Columns: `Line_ModelName`, `Mode_Planned`, `Area`

**Demand Data:**
- `Demand_2050.xlsx`: Multi-sheet Excel with regional models
  - Sheets: Haifa, TelAviv, Jerusalem, BeerSheva, Ashdod, Hadera, HaifaMetronit, Ashkelon
  - Varying column formats per model (needs standardization)

**Manual Overrides:**
- `manual_demand_updates.csv`: Node-specific demand corrections
  - Columns: `node`, `area`, `total_demand`, `total_transfers`

### Current Pain Points
1. **Fragmented Data**: Multiple files with different formats
2. **Complex Excel**: Multi-sheet structure with inconsistent columns
3. **No Validation**: Errors only caught during pipeline execution
4. **Manual Process**: Requires file editing and technical knowledge
5. **No Preview**: Can't see impact before running full pipeline

---

## 3. Standardized Input File Formats

### 3.1 Transit Lines Master File

**File:** `transit_lines_update.csv`

**Purpose:** Define all transit lines with their properties in a single, comprehensive file

**Required Columns:**

| Column | Type | Description | Example | Notes |
|--------|------|-------------|---------|-------|
| `line_id` | String | Unique line identifier | `"TLV_M1"` | Must be unique |
| `line_name_he` | String | Hebrew line name | `"מטרו ת״א - קו 1"` | UTF-8 encoding |
| `line_name_en` | String | English line name | `"Tel Aviv Metro - Line 1"` | Optional |
| `mode` | String | Transit mode | `"Metro"` | See mode list below |
| `area` | String | Geographic area | `"Tel Aviv"` | See area list below |
| `status` | String | Planning status | `"Planned"` | `Planned`/`Under Construction`/`Operational` |
| `operational_year` | Integer | Expected operational year | `2030` | Future year for planned lines |
| `frequency_peak` | Float | Peak frequency (trains/hr) | `12.0` | Optional, for future use |
| `frequency_offpeak` | Float | Off-peak frequency (trains/hr) | `6.0` | Optional |
| `is_active` | Boolean | Include in analysis | `TRUE` | `TRUE`/`FALSE` |
| `notes` | String | Additional notes | `"Extension to airport"` | Optional |

**Valid Modes:**
- `Rail` (רכבת)
- `HighSpeed Rail` (רכבת מהירה)
- `Suburban Rail` (רכבת פרברית)
- `Interurban Rail` (רכבת בין-עירונית)
- `Metro` (מטרו)
- `LRT` (רק״ל - Light Rail)
- `BRT` (מטרונית - Bus Rapid Transit)
- `Bus` (אוטובוס)
- `Express Bus` (אוטובוס אקספרס)
- `Cable Line` (רכבל)
- `Funicular` (פוניקולר)

**Valid Areas:**
- `Tel Aviv` (תל אביב)
- `Center` (מרכז)
- `Haifa` (חיפה)
- `North` (צפון)
- `South` (דרום)
- `Jerusalem` (ירושלים)
- `Beer Sheva` (באר שבע)
- `National` (ארצי)

**Example CSV:**
```csv
line_id,line_name_he,line_name_en,mode,area,status,operational_year,frequency_peak,frequency_offpeak,is_active,notes
TLV_M1,קו 1 מטרו ת״א,Tel Aviv Metro Line 1,Metro,Tel Aviv,Planned,2030,12,6,TRUE,Core route
TLV_M2,קו 2 מטרו ת״א,Tel Aviv Metro Line 2,Metro,Tel Aviv,Planned,2032,10,5,TRUE,
HFA_LRT1,קו רק״ל חיפה,Haifa Light Rail,LRT,Haifa,Under Construction,2027,8,4,TRUE,Carmelit extension
NAT_HSR1,רכבת מהירה ת״א-אילת,Tel Aviv-Eilat HSR,HighSpeed Rail,National,Planned,2040,4,2,FALSE,Long-term plan
```

### 3.2 Transit Stations/Nodes File

**File:** `transit_stations_update.csv`

**Purpose:** Define all station locations and their line associations

**Required Columns:**

| Column | Type | Description | Example | Notes |
|--------|------|-------------|---------|-------|
| `node_id` | Integer | Unique node identifier | `400020` | Must be unique, stable across updates |
| `station_name_he` | String | Hebrew station name | `תל אביב סבידור מרכז` | UTF-8 encoding |
| `station_name_en` | String | English station name | `Tel Aviv Savidor Center` | Optional |
| `x_coord` | Float | X coordinate (Israel TM) | `180000.5` | EPSG:2039 projection |
| `y_coord` | Float | Y coordinate (Israel TM) | `665000.3` | EPSG:2039 projection |
| `lon` | Float | Longitude (WGS84) | `34.8516` | Optional, auto-calculated if missing |
| `lat` | Float | Latitude (WGS84) | `32.0853` | Optional, auto-calculated if missing |
| `lines_served` | String | Comma-separated line IDs | `"TLV_M1,TLV_M2,NAT_R1"` | Must match `transit_lines_update.csv` |
| `area` | String | Geographic area | `"Tel Aviv"` | Must match area list |
| `is_interchange` | Boolean | Is this a major interchange? | `TRUE` | `TRUE`/`FALSE` |
| `is_active` | Boolean | Include in analysis | `TRUE` | `TRUE`/`FALSE` |
| `notes` | String | Additional notes | `"Main railway station"` | Optional |

**Example CSV:**
```csv
node_id,station_name_he,station_name_en,x_coord,y_coord,lon,lat,lines_served,area,is_interchange,is_active,notes
400020,תל אביב סבידור מרכז,Tel Aviv Savidor Center,180500.0,665200.0,34.8516,32.0853,"NAT_R1,TLV_M1",Tel Aviv,TRUE,TRUE,Central Station
400470,מודיעין מרכז,Modiin Center,166200.0,650800.0,34.8892,31.8974,"NAT_R1",Center,FALSE,TRUE,
400460,מודיעין מערב,Modiin West,165800.0,650500.0,34.8850,31.8947,"NAT_R1",Center,FALSE,TRUE,
```

### 3.3 Demand Data File

**File:** `demand_2050_update.csv`

**Purpose:** Unified demand forecasts for all stations (replaces multi-sheet Excel)

**Required Columns:**

| Column | Type | Description | Example | Notes |
|--------|------|-------------|---------|-------|
| `node_id` | Integer | Node identifier | `400020` | Must match `transit_stations_update.csv` |
| `model_area` | String | Source model area | `"TelAviv"` | Which model produced this forecast |
| `total_boardings` | Float | Daily boardings (2050) | `54204.5` | Passengers getting on |
| `total_alightings` | Float | Daily alightings (2050) | `54204.5` | Passengers getting off |
| `total_transfers` | Float | Daily transfers (2050) | `42245.0` | Transfer passengers |
| `total_demand` | Float | Total activity | `108409.0` | Boardings + Alightings |
| `peak_hour_factor` | Float | Peak/average ratio | `1.3` | Optional, for capacity analysis |
| `data_source` | String | Source of data | `"National Model 2025"` | Documentation |
| `confidence` | String | Data confidence level | `"High"` | `High`/`Medium`/`Low` |
| `is_override` | Boolean | Overrides other sources | `FALSE` | `TRUE` for manual corrections |
| `last_updated` | Date | Date of last update | `2025-01-15` | YYYY-MM-DD format |
| `notes` | String | Additional notes | `"Updated from national model"` | Optional |

**Example CSV:**
```csv
node_id,model_area,total_boardings,total_alightings,total_transfers,total_demand,peak_hour_factor,data_source,confidence,is_override,last_updated,notes
400020,TelAviv,54204.5,54204.5,42245.0,108409.0,1.3,National Model 2025,High,TRUE,2025-01-15,Central station - verified data
400470,TelAviv,20314.0,20314.0,0,40628.0,1.2,National Model 2025,High,TRUE,2025-01-15,
400460,TelAviv,20500.0,20500.0,6066.5,41000.0,1.2,National Model 2025,Medium,FALSE,2025-01-10,
```

**Key Features:**
- **Single file** instead of multi-sheet Excel
- **Clear source tracking** (model_area, data_source)
- **Override capability** (is_override flag for manual corrections)
- **Version tracking** (last_updated field)
- **Confidence levels** for data quality assessment

### 3.4 Data Update Templates

Create template files in `data/templates/`:

1. **`transit_lines_TEMPLATE.csv`** - Empty template with headers + example rows
2. **`transit_stations_TEMPLATE.csv`** - Empty template with headers + example rows
3. **`demand_2050_TEMPLATE.csv`** - Empty template with headers + example rows

Each template includes:
- Header row with all column names
- 2-3 example rows showing correct format
- Comments (in separate README) explaining each field

---

## 4. Update Process Workflow

### 4.1 Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    TRANSIT UPDATE WORKFLOW                       │
└─────────────────────────────────────────────────────────────────┘

Step 1: Prepare Data
├─ Download templates from data/templates/
├─ Fill in transit_lines_update.csv
├─ Fill in transit_stations_update.csv
└─ Fill in demand_2050_update.csv

Step 2: Validate Data (Automatic)
├─ Check required columns exist
├─ Validate data types and ranges
├─ Check referential integrity (line_ids match, node_ids match)
├─ Verify coordinate systems
├─ Check for duplicates
└─ Generate validation report

Step 3: Preview Impact (Optional)
├─ Show summary statistics
├─ Compare with current data
├─ Highlight changes (new lines, modified demand)
└─ Generate diff report

Step 4: Upload & Process
├─ Backup current data (timestamped)
├─ Replace old files with new validated files
├─ Update data/processed/ directory
└─ Log all changes to audit trail

Step 5: Run Pipeline
├─ Execute complete_transit_pipeline.py
├─ Monitor progress
└─ Review results

Step 6: Verify Results
├─ Check hub counts and classifications
├─ Review scoring outputs
├─ Validate against expectations
└─ Generate comparison report
```

### 4.2 Validation Rules

**Transit Lines Validation:**
1. `line_id` must be unique
2. `mode` must be from valid mode list
3. `area` must be from valid area list
4. `status` must be: Planned, Under Construction, or Operational
5. `operational_year` must be ≥ current year
6. `is_active` must be TRUE or FALSE

**Transit Stations Validation:**
1. `node_id` must be unique integer
2. Coordinates must be within Israel bounds:
   - X: 50,000 - 300,000 (EPSG:2039)
   - Y: 400,000 - 800,000 (EPSG:2039)
   - Lon: 34.0 - 36.0 (WGS84)
   - Lat: 29.0 - 33.5 (WGS84)
3. `lines_served` must reference valid line_ids from transit_lines_update.csv
4. `area` must match area list
5. Station must serve at least 1 line

**Demand Data Validation:**
1. `node_id` must exist in transit_stations_update.csv
2. All demand values must be ≥ 0
3. `total_demand` should approximately equal boardings + alightings (±5% tolerance)
4. `peak_hour_factor` must be ≥ 1.0 if provided
5. `last_updated` must be valid date in YYYY-MM-DD format
6. No duplicate node_id entries (unless is_override=TRUE overrides lower priority)

**Cross-File Validation:**
1. All line_ids in stations file exist in lines file
2. All node_ids in demand file exist in stations file
3. Area assignments are consistent across files
4. No orphaned records (stations without lines, demand without stations)

### 4.3 Update Automation Scripts

Create Python scripts in `scripts/update_transit_data/`:

**`validate_input_files.py`**
- Validates all three input files
- Generates detailed validation report
- Exit code 0 = valid, 1 = errors found
- Usage: `python scripts/update_transit_data/validate_input_files.py`

**`preview_update_impact.py`**
- Compares new files with current processed data
- Shows summary of changes:
  - New lines added
  - Lines removed/deactivated
  - Stations added/modified
  - Demand changes (by hub)
- Generates HTML diff report
- Usage: `python scripts/update_transit_data/preview_update_impact.py`

**`apply_transit_update.py`**
- Validates input files (calls validate_input_files.py)
- Backs up current data to `data/backups/YYYY-MM-DD_HHMMSS/`
- Copies new files to data/raw/
- Converts and processes to data/processed/
- Updates audit log
- Usage: `python scripts/update_transit_data/apply_transit_update.py`

**`rollback_transit_update.py`**
- Lists available backups
- Restores selected backup
- Updates audit log
- Usage: `python scripts/update_transit_data/rollback_transit_update.py [backup_date]`

---

## 5. GUI Design

### 5.1 Technology Stack

**Framework:** Streamlit (Python-based, easy to deploy, interactive)

**Alternative:** Gradio (simpler) or Dash (more customizable)

**Advantages of Streamlit:**
- ✅ Pure Python (no HTML/CSS/JS required)
- ✅ Fast prototyping
- ✅ Built-in file upload widgets
- ✅ Easy data table display
- ✅ Can run locally or deploy to web
- ✅ Good for internal tools

### 5.2 GUI Interface Mockup

```
┌──────────────────────────────────────────────────────────────────────┐
│  🚇 Transit Data Update System                              [Help] [⚙]│
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  📊 Current Data Status                                              │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Last Updated: 2025-01-10 14:30                                 │ │
│  │ Transit Lines: 87 active lines                                 │ │
│  │ Stations: 423 nodes                                            │ │
│  │ Hubs Identified: 86 hubs (15 ארצי, 46 מטרופוליני, 25 עירוני)  │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ═══════════════════════════════════════════════════════════════     │
│                                                                       │
│  📁 Step 1: Upload New Data Files                                    │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Transit Lines:                                                 │ │
│  │ [Choose File: transit_lines_update.csv]   [Download Template] │ │
│  │ Status: ✅ File uploaded (87 lines)                            │ │
│  │                                                                │ │
│  │ Transit Stations:                                              │ │
│  │ [Choose File: transit_stations_update.csv] [Download Template]│ │
│  │ Status: ✅ File uploaded (425 stations)                        │ │
│  │                                                                │ │
│  │ Demand Data (2050):                                            │ │
│  │ [Choose File: demand_2050_update.csv]     [Download Template] │ │
│  │ Status: ✅ File uploaded (425 records)                         │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ═══════════════════════════════════════════════════════════════     │
│                                                                       │
│  ✔ Step 2: Validate Data                     [Run Validation]        │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Validation Results:                                            │ │
│  │                                                                │ │
│  │ ✅ Transit Lines: All checks passed                            │ │
│  │    - 87 unique line IDs                                        │ │
│  │    - All modes valid                                           │ │
│  │    - All areas valid                                           │ │
│  │                                                                │ │
│  │ ✅ Transit Stations: All checks passed                         │ │
│  │    - 425 unique node IDs                                       │ │
│  │    - All coordinates within bounds                             │ │
│  │    - All line references valid                                 │ │
│  │                                                                │ │
│  │ ⚠️  Demand Data: 2 warnings                                    │ │
│  │    - Node 400123: total_demand doesn't match sum (+3%)         │ │
│  │    - Node 400456: No demand data (new station?)                │ │
│  │    [View Details] [Download Report]                            │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ═══════════════════════════════════════════════════════════════     │
│                                                                       │
│  👁 Step 3: Preview Changes (Optional)        [Generate Preview]     │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Impact Summary:                                                │ │
│  │                                                                │ │
│  │ 📊 Changes Overview:                                           │ │
│  │   • New lines: 3 (TLV_M3, HFA_BRT2, NAT_HSR1)                  │ │
│  │   • Modified lines: 2 (updated status/year)                    │ │
│  │   • New stations: 12                                           │ │
│  │   • Demand updates: 8 nodes with changed forecasts             │ │
│  │                                                                │ │
│  │ 🔢 Expected Hub Changes:                                       │ │
│  │   • New hubs: ~3-5 (preliminary estimate)                      │ │
│  │   • Hubs with increased scores: ~12                            │ │
│  │   • Hubs with mode changes: ~2                                 │ │
│  │                                                                │ │
│  │ [View Detailed Comparison]  [Download Diff Report]             │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ═══════════════════════════════════════════════════════════════     │
│                                                                       │
│  💾 Step 4: Apply Update                                             │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ ⚠️  This will replace current data with uploaded files         │ │
│  │                                                                │ │
│  │ [✓] Create backup before applying                             │ │
│  │ [✓] Run full pipeline after update                            │ │
│  │ [✓] Generate comparison report                                │ │
│  │                                                                │ │
│  │             [Cancel]              [Apply Update]               │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ═══════════════════════════════════════════════════════════════     │
│                                                                       │
│  📊 Step 5: Run Pipeline & View Results                              │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Pipeline Status: ⏳ Running... (Step 3/8 - Grouping hexagons)  │ │
│  │                                                                │ │
│  │ Progress: ▓▓▓▓▓▓▓▓░░░░░░░░ 40%                                 │ │
│  │                                                                │ │
│  │ [View Live Log]  [Cancel]                                      │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘

  Sidebar:
  ┌──────────────────┐
  │ 📚 Resources     │
  ├──────────────────┤
  │ • User Guide     │
  │ • Data Templates │
  │ • Field Glossary │
  │ • Validation Ref │
  │                  │
  │ 🔧 Tools         │
  ├──────────────────┤
  │ • View Backups   │
  │ • Restore Backup │
  │ • Export Data    │
  │ • Audit Log      │
  │                  │
  │ ℹ️ System Info   │
  ├──────────────────┤
  │ Version: 1.0.0   │
  │ Last Backup:     │
  │  2025-01-15      │
  └──────────────────┘
```

### 5.3 GUI Features

**File Upload:**
- Drag-and-drop support
- CSV format validation
- Immediate file preview (first 10 rows)
- Download template buttons

**Validation:**
- Real-time validation as files are uploaded
- Color-coded results (✅ green, ⚠️ yellow, ❌ red)
- Expandable error details
- Downloadable validation report (HTML/PDF)

**Preview:**
- Side-by-side comparison (old vs new)
- Change summary statistics
- Visual diff highlighting
- Interactive data tables with sorting/filtering

**Apply Update:**
- Confirmation dialog with checklist
- Automatic backup creation
- Progress indicators
- Success/error notifications

**Pipeline Execution:**
- Live progress bar
- Step-by-step status updates
- Real-time log viewing
- Cancel button (graceful shutdown)

**Results:**
- Summary comparison (before/after)
- Interactive maps showing changes
- Downloadable reports
- Link to full hub scoring results

### 5.4 GUI Implementation Structure

**File:** `app/transit_updater.py`

```python
"""
Transit Data Update GUI
=======================
Streamlit-based web interface for uploading and validating transit data updates.
"""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.update_transit_data.validate_input_files import validate_all_files
from scripts.update_transit_data.preview_update_impact import generate_preview
from scripts.update_transit_data.apply_transit_update import apply_update
from src.config import DATA_DIR, RESULTS_DIR

def main():
    st.set_page_config(
        page_title="Transit Data Updater",
        page_icon="🚇",
        layout="wide"
    )

    st.title("🚇 Transit Data Update System")

    # Sidebar
    with st.sidebar:
        st.header("📚 Resources")
        # ... template downloads, help links

        st.header("🔧 Tools")
        # ... backup management, export tools

    # Main content
    # Step 1: File upload
    st.header("📁 Step 1: Upload New Data Files")
    # ... file uploaders

    # Step 2: Validation
    st.header("✔ Step 2: Validate Data")
    # ... validation logic

    # Step 3: Preview
    st.header("👁 Step 3: Preview Changes")
    # ... preview generation

    # Step 4: Apply
    st.header("💾 Step 4: Apply Update")
    # ... update application

    # Step 5: Pipeline
    st.header("📊 Step 5: Run Pipeline")
    # ... pipeline execution

if __name__ == "__main__":
    main()
```

**Running the GUI:**
```bash
# Local development
streamlit run app/transit_updater.py

# Production deployment
streamlit run app/transit_updater.py --server.port 8501 --server.address 0.0.0.0
```

---

## 6. Implementation Plan

### Phase 1: Foundation (Week 1-2)
**Goal:** Create standardized formats and validation

1. ✅ Create template files:
   - `data/templates/transit_lines_TEMPLATE.csv`
   - `data/templates/transit_stations_TEMPLATE.csv`
   - `data/templates/demand_2050_TEMPLATE.csv`
   - Documentation README for each template

2. ✅ Create validation module:
   - `src/data/validators.py` - Update with new validation functions
   - Unit tests for all validation rules

3. ✅ Create update scripts:
   - `scripts/update_transit_data/validate_input_files.py`
   - `scripts/update_transit_data/backup_data.py`
   - Unit tests

### Phase 2: Preview & Apply (Week 3)
**Goal:** Enable data comparison and safe updates

4. ✅ Create preview module:
   - `scripts/update_transit_data/preview_update_impact.py`
   - Diff report generation (HTML)
   - Summary statistics

5. ✅ Create apply module:
   - `scripts/update_transit_data/apply_transit_update.py`
   - Backup creation logic
   - Audit logging
   - Rollback functionality

6. ✅ Integration with existing pipeline:
   - Modify loaders to handle new formats
   - Ensure backward compatibility
   - Test with sample data

### Phase 3: GUI Development (Week 4-5)
**Goal:** Build user-friendly interface

7. ✅ Basic GUI framework:
   - `app/transit_updater.py`
   - File upload interface
   - Basic validation display

8. ✅ Advanced GUI features:
   - Preview generation
   - Interactive data tables
   - Progress indicators
   - Results visualization

9. ✅ Testing & refinement:
   - User testing with planners
   - UI/UX improvements
   - Error handling

### Phase 4: Documentation & Deployment (Week 6)
**Goal:** Prepare for production use

10. ✅ Documentation:
    - User guide (how to use GUI)
    - Data format specification
    - Troubleshooting guide
    - Video tutorial (optional)

11. ✅ Deployment:
    - Setup instructions
    - Docker container (optional)
    - Access control (if needed)

12. ✅ Training:
    - Walkthrough for planners
    - Q&A session
    - Feedback collection

---

## 7. Technical Architecture

### 7.1 Directory Structure

```
HubPrioritizing/
├── data/
│   ├── templates/              # NEW: Template files for users
│   │   ├── transit_lines_TEMPLATE.csv
│   │   ├── transit_stations_TEMPLATE.csv
│   │   ├── demand_2050_TEMPLATE.csv
│   │   └── README_TEMPLATES.md
│   │
│   ├── uploads/                # NEW: User uploaded files (temporary)
│   │   └── [timestamped folders]
│   │
│   ├── backups/                # NEW: Automatic backups
│   │   └── YYYY-MM-DD_HHMMSS/
│   │       ├── transit_lines.csv
│   │       ├── transit_stations.csv
│   │       └── demand_2050.csv
│   │
│   ├── raw/                    # MODIFIED: Now uses standardized formats
│   │   ├── transit_lines.csv
│   │   ├── transit_stations.csv
│   │   └── demand_2050.csv
│   │
│   ├── processed/              # Existing
│   └── results/                # Existing
│
├── scripts/
│   └── update_transit_data/    # NEW: Update automation scripts
│       ├── __init__.py
│       ├── validate_input_files.py
│       ├── preview_update_impact.py
│       ├── apply_transit_update.py
│       ├── rollback_transit_update.py
│       └── backup_data.py
│
├── app/
│   ├── transit_updater.py      # NEW: Main GUI application
│   ├── components/             # NEW: Reusable UI components
│   │   ├── file_uploader.py
│   │   ├── validator_display.py
│   │   ├── preview_generator.py
│   │   └── pipeline_runner.py
│   └── assets/                 # NEW: CSS, images, etc.
│
├── src/
│   ├── data/
│   │   ├── loaders.py          # MODIFIED: Support new formats
│   │   └── validators.py       # MODIFIED: New validation functions
│   └── ...                     # Existing modules
│
├── tests/
│   └── test_update_system/     # NEW: Tests for update system
│       ├── test_validators.py
│       ├── test_preview.py
│       └── test_apply.py
│
├── docs/
│   ├── TRANSIT_UPDATE_GUIDE.md # NEW: User guide
│   └── DATA_FORMAT_SPEC.md     # NEW: Format specification
│
└── TRANSIT_UPDATE_SYSTEM_DESIGN.md  # This document
```

### 7.2 Data Flow Diagram

```
┌─────────────────┐
│  User           │
│  (Planner)      │
└────────┬────────┘
         │
         │ 1. Fills templates
         │
         ▼
┌─────────────────────────────────────┐
│  CSV Files                          │
│  • transit_lines_update.csv         │
│  • transit_stations_update.csv      │
│  • demand_2050_update.csv           │
└────────┬────────────────────────────┘
         │
         │ 2. Upload via GUI
         │
         ▼
┌─────────────────────────────────────┐
│  Validation Engine                  │
│  • Format validation                │
│  • Data type validation             │
│  • Referential integrity            │
│  • Cross-file consistency           │
└────────┬────────────────────────────┘
         │
         │ 3a. If errors → Show report, reject
         │ 3b. If valid → Continue
         │
         ▼
┌─────────────────────────────────────┐
│  Preview Generator                  │
│  • Compare with current data        │
│  • Generate change summary          │
│  • Estimate impact on hubs          │
└────────┬────────────────────────────┘
         │
         │ 4. User reviews & approves
         │
         ▼
┌─────────────────────────────────────┐
│  Backup Manager                     │
│  • Timestamp current data           │
│  • Copy to data/backups/            │
│  • Log backup creation              │
└────────┬────────────────────────────┘
         │
         │ 5. Backup created
         │
         ▼
┌─────────────────────────────────────┐
│  Data Updater                       │
│  • Replace data/raw/ files          │
│  • Convert to processed format      │
│  • Update audit log                 │
└────────┬────────────────────────────┘
         │
         │ 6. Data updated
         │
         ▼
┌─────────────────────────────────────┐
│  Hub Prioritization Pipeline        │
│  • Load new transit data            │
│  • Assign H3 hexagons               │
│  • Group into hubs                  │
│  • Calculate scores                 │
│  • Generate outputs                 │
└────────┬────────────────────────────┘
         │
         │ 7. Pipeline complete
         │
         ▼
┌─────────────────────────────────────┐
│  Results Comparison                 │
│  • Compare before/after hubs        │
│  • Generate diff report             │
│  • Visualize changes on map         │
└────────┬────────────────────────────┘
         │
         │ 8. Review results
         │
         ▼
┌─────────────────┐
│  User Reviews   │
│  Final Results  │
└─────────────────┘
```

### 7.3 Key Technical Considerations

**File Encoding:**
- All input CSVs: UTF-8 (with BOM for Excel compatibility)
- Hebrew text: Properly encoded in UTF-8
- Output files: UTF-8 (with BOM)

**Data Validation:**
- Use Pydantic or Pandera for schema validation
- Comprehensive error messages
- Warnings vs. errors (strict vs. permissive)

**Version Control:**
- Timestamped backups
- Audit log (JSON or SQLite)
- Track who made changes (if multi-user)

**Performance:**
- Large files: Stream processing
- Preview generation: Sample data if >100k rows
- Pipeline execution: Background task with status updates

**Security:**
- File upload size limits
- CSV injection prevention
- Path traversal prevention
- Input sanitization

**Error Handling:**
- Graceful failures
- Clear error messages
- Rollback on critical errors
- Detailed logging

---

## 8. Success Criteria

### User Experience
- ✅ Non-technical planner can update data without assistance
- ✅ < 5 minutes to upload and validate files
- ✅ Clear, actionable error messages
- ✅ Ability to preview changes before applying

### Technical
- ✅ 100% validation coverage for input data
- ✅ Zero data loss (automatic backups)
- ✅ Backward compatible with existing pipeline
- ✅ Full audit trail of all changes

### Process
- ✅ Documented workflow
- ✅ Template files with examples
- ✅ One-click rollback capability
- ✅ Comparison reports (before/after)

---

## 9. Future Enhancements

### Phase 2 Features
1. **Web-based data editor**: Edit CSV data directly in browser
2. **Collaborative editing**: Multiple users can propose changes
3. **Approval workflow**: Changes require review before applying
4. **API integration**: Direct connection to external data sources
5. **Scheduled updates**: Automatic data refresh from source systems
6. **Version comparison**: Compare any two historical versions
7. **Bulk operations**: Update multiple lines/stations at once
8. **Import from Excel**: Support Excel uploads with conversion
9. **Export to GIS**: Direct export to shapefile/GeoJSON
10. **Mobile interface**: Responsive design for tablets

---

## 10. Appendices

### A. Sample Validation Report

```
═══════════════════════════════════════════════════════════
TRANSIT DATA VALIDATION REPORT
Generated: 2025-01-17 10:30:45
═══════════════════════════════════════════════════════════

FILE: transit_lines_update.csv
STATUS: ✅ PASSED (87 records, 0 errors, 1 warning)

Validation Results:
  ✅ All line_ids are unique
  ✅ All modes are valid
  ✅ All areas are valid
  ✅ All statuses are valid
  ✅ All operational_years are >= 2025
  ⚠️  WARNING: Line "NAT_HSR1" has is_active=FALSE (will be excluded)

═══════════════════════════════════════════════════════════

FILE: transit_stations_update.csv
STATUS: ✅ PASSED (425 records, 0 errors, 0 warnings)

Validation Results:
  ✅ All node_ids are unique
  ✅ All coordinates are within Israel bounds
  ✅ All line references are valid
  ✅ All areas are valid
  ✅ All stations serve at least 1 line

═══════════════════════════════════════════════════════════

FILE: demand_2050_update.csv
STATUS: ⚠️  WARNINGS (425 records, 0 errors, 3 warnings)

Validation Results:
  ✅ All node_ids exist in stations file
  ✅ All demand values are non-negative
  ⚠️  WARNING: Node 400123 - total_demand mismatch
      Expected: 50000 (boardings + alightings)
      Found: 51500
      Difference: +3.0%
  ⚠️  WARNING: Node 400456 - No demand data found
      (This may be a new station without forecasts yet)
  ⚠️  WARNING: Node 400789 - Very low demand (248 passengers/day)
      (Below eligibility threshold of 1000/day)

═══════════════════════════════════════════════════════════

CROSS-FILE VALIDATION:
STATUS: ✅ PASSED

  ✅ All line_ids in stations exist in lines file
  ✅ All node_ids in demand exist in stations file
  ✅ Area assignments are consistent
  ✅ No orphaned records

═══════════════════════════════════════════════════════════

OVERALL STATUS: ✅ READY TO APPLY
(0 errors, 4 warnings)

Warnings are informational and do not prevent update.
Review warnings above and apply update when ready.

═══════════════════════════════════════════════════════════
```

### B. Sample Change Preview

```
═══════════════════════════════════════════════════════════
TRANSIT DATA UPDATE PREVIEW
Current Data: 2025-01-10 14:30
New Data: 2025-01-17 10:30
═══════════════════════════════════════════════════════════

TRANSIT LINES CHANGES:

  NEW LINES (3):
  • TLV_M3 - קו 3 מטרו ת״א (Metro, Tel Aviv, Planned 2035)
  • HFA_BRT2 - מטרונית חיפה קו 2 (BRT, Haifa, Planned 2028)
  • NAT_HSR1 - רכבת מהירה ת״א-אילת (HSR, National, Planned 2040)

  MODIFIED LINES (2):
  • TLV_M1 - Status: Planned → Under Construction
  • TLV_M1 - Operational Year: 2030 → 2029

  REMOVED LINES (1):
  • OLD_BUS_1 - Deactivated (is_active=FALSE)

═══════════════════════════════════════════════════════════

TRANSIT STATIONS CHANGES:

  NEW STATIONS (12):
  • 500001 - תל אביב דרום (Tel Aviv South) - TLV_M3
  • 500002 - תל אביב מזרח (Tel Aviv East) - TLV_M3
  ... (10 more)

  MODIFIED STATIONS (3):
  • 400020 - Tel Aviv Savidor: Added line TLV_M3
  • 400150 - Haifa Central: Added line HFA_BRT2
  • 400200 - Beer Sheva North: Updated coordinates

═══════════════════════════════════════════════════════════

DEMAND CHANGES:

  DEMAND UPDATES (8 nodes):
  • 400020 - Tel Aviv Savidor: 108,409 → 115,234 (+6.3%)
  • 400150 - Haifa Central: 45,230 → 48,100 (+6.3%)
  • 400470 - Modiin Center: 40,628 → 42,000 (+3.4%)
  ... (5 more)

═══════════════════════════════════════════════════════════

ESTIMATED HUB IMPACT:

  PRELIMINARY ESTIMATES (run full pipeline for accurate results):

  • New hubs expected: 3-5
    (Based on new stations in clustered areas)

  • Hubs with increased scores: ~12
    (Due to new lines and demand increases)

  • Hubs with mode changes: ~2
    (TLV_Savidor gains Metro, Haifa_Central gains BRT)

  • Classification changes: Possible
    (Some מטרופוליני hubs may reach ארצי threshold)

  NOTE: These are estimates based on simple heuristics.
        Run full pipeline for definitive results.

═══════════════════════════════════════════════════════════

RECOMMENDATION:
✅ Data changes look reasonable
✅ No major anomalies detected
✅ Ready to apply and run pipeline

[View Detailed Diff] [Download Report] [Apply Update]

═══════════════════════════════════════════════════════════
```

---

**Document Version:** 1.0
**Last Updated:** 2025-01-17
**Author:** Transit Planning Team
**Status:** Design Proposal - Ready for Implementation
