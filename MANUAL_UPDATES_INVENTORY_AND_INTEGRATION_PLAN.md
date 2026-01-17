# Manual Updates Inventory and Integration Plan

**Date**: 2025-01-17
**Purpose**: Comprehensive inventory of all manual updates in the codebase and plan to integrate them into the Transit Update System Design

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Manual Update Inventory](#manual-update-inventory)
3. [Current vs. Desired State](#current-vs-desired-state)
4. [Integration Plan](#integration-plan)
5. [Enhanced Input File Formats](#enhanced-input-file-formats)
6. [Notification System Design](#notification-system-design)
7. [Implementation Roadmap](#implementation-roadmap)
8. [Migration Guide](#migration-guide)

---

## Executive Summary

### Problem
The Hub Prioritization Framework currently has **manual overrides and corrections scattered throughout the code** in multiple locations. This creates:
- **Maintainability issues**: Changes require code edits
- **Reproducibility problems**: Manual edits not tracked in version control
- **Transparency gaps**: Users don't know what overrides were applied
- **Documentation drift**: Code comments don't capture the reasoning

### Solution
Move **all manual updates from code to standardized input files** and implement a **comprehensive notification system** that alerts users when overrides are applied.

### Scope
This document covers **4 types of manual updates** across **8 locations** in the codebase:

| Update Type | Current Locations | Input File(s) |
|-------------|-------------------|---------------|
| **Group Corrections** | 1 location (Step 1.5.1) | ✅ `IsSameGroup.csv` |
| **Demand Updates (CSV)** | 1 location (Step 2.6.1) | ✅ `manual_demand_updates.csv` |
| **Demand Updates (Hardcoded)** | 2 locations (Step 2.6.2, 2.6.3) | ❌ **To be migrated** |
| **Demand Overlays** | 1 location (Step 2.6 - Hadera) | ❌ **To be migrated** |
| **Old Notebook Updates** | 3 locations (legacy code) | ❌ **To be deprecated** |

**Status**:
- ✅ **2 types** already have CSV support (Group Corrections, Demand CSV)
- ⚠️ **2 types** need migration (Hardcoded Demand, Overlays)
- 🗑️ **Legacy code** to be deprecated

---

## Manual Update Inventory

### Category 1: Group Corrections (IsSameGroup.csv)
**Purpose**: Force specific nodes to be grouped together, overriding automatic 120m buffer grouping

**Status**: ✅ **Already implemented in CSV**

**Location**:
- `COMPLETE_TRANSIT_PIPELINE.ipynb` - Step 1.5.1

**File**: `data/IsSameGroup.csv`

**Example**:
```csv
Nodes in group
"400018, 521063, 523019"
"123456, 789012, 345678"
```

**Documentation**: `data/README_MANUAL_GROUP_CORRECTIONS.md`

**How it works**:
1. Load CSV after automatic grouping
2. Parse comma-separated node IDs per row
3. Merge all specified nodes into the same group (using minimum group ID)
4. Renormalize group IDs to be sequential

**Current notification**:
```
Step 1.5.1: Applying manual group corrections...
  ✓ Merged 3 hexagons for nodes [400018, 521063, 523019]
    From groups [635, 638] → 635
  Applied 1 manual corrections
  Merged 1 groups
```

✅ **Good**: Already CSV-based, documented, with notifications
⚠️ **Enhancement needed**: Notification could include reasoning/notes

---

### Category 2: Manual Demand Updates (CSV)
**Purpose**: Override demand forecasts for specific nodes using more accurate data sources

**Status**: ✅ **Already implemented in CSV**

**Location**:
- `COMPLETE_TRANSIT_PIPELINE.ipynb` - Step 2.6.1

**File**: `data/manual_demand_updates.csv`

**Format**:
```csv
node,area,total_demand,total_transfers,station_name,notes
400020,Tel Aviv,108409,84490,Netanya,From National Model 2025
400470,Tel Aviv,40628,0,Modiin Merkaz,From National Model 2025
400460,Tel Aviv,41000,12133,Modiin West,From National Model 2025
```

**Documentation**: `data/README_MANUAL_DEMAND_UPDATES.md`

**How it works**:
1. Load CSV if it exists (optional)
2. Validate required columns
3. For each row, find matching node(s) in `gdf_demand`
4. Update `TotalDemand` and `TotalTransfers`
5. Report updates applied

**Current notification**:
```
Step 2.6.1: Loading manual demand updates from CSV...
  ✓ Loaded 3 demand updates from CSV
  ✓ Updated node 400020 (Tel Aviv): 108,409 demand, 84,490 transfers
  ✓ Updated node 400470 (Tel Aviv): 40,628 demand, 0 transfers
  ✓ Updated node 400460 (Tel Aviv): 41,000 demand, 12,133 transfers
  Applied 3 manual demand updates
```

✅ **Good**: Already CSV-based, documented, with notifications
⚠️ **Enhancement needed**: Should include notes/reasoning in notification

---

### Category 3: Hardcoded Demand Updates (National Model)
**Purpose**: Apply specific node-level corrections from National Model that aren't in CSV yet

**Status**: ⚠️ **HARDCODED - Needs migration to CSV**

**Location**:
- `COMPLETE_TRANSIT_PIPELINE.ipynb` - Step 2.6.2

**Current code**:
```python
# Hardcoded in Step 2.6.2
NATIONAL_MODEL_UPDATES = {
    400424: (64985, 43032, 'Moshe Dayan (Rishon)'),
    400021: (23083, 10140, 'Netanya Sapir'),
    400030: (14518, 6101, 'Beit Yehoshua Rail'),
    511246: (13601, 6101, 'Beit Yehoshua LRT'),
}

for node_id, (demand, transfers, name) in NATIONAL_MODEL_UPDATES.items():
    mask = gdf_demand['node'].apply(lambda nodes: node_id in nodes)
    if mask.any():
        gdf_demand.loc[mask, 'TotalDemand'] = demand
        gdf_demand.loc[mask, 'TotalTransfers'] = transfers
        print(f"  ✓ Updated {name} (node {node_id}): {demand:,} demand, {transfers:,} transfers")
```

**Nodes affected**:
- **400424**: Moshe Dayan (Rishon) - 64,985 demand, 43,032 transfers
- **400021**: Netanya Sapir - 23,083 demand, 10,140 transfers
- **400030**: Beit Yehoshua Rail - 14,518 demand, 6,101 transfers
- **511246**: Beit Yehoshua LRT - 13,601 demand, 6,101 transfers

**Current notification**:
```
Step 2.6.2: Applying hardcoded demand updates from National Model...
  ✓ Updated Moshe Dayan (Rishon) (node 400424): 64,985 demand, 43,032 transfers
  ✓ Updated Netanya Sapir (node 400021): 23,083 demand, 10,140 transfers
  ✓ Updated Beit Yehoshua Rail (node 400030): 14,518 demand, 6,101 transfers
  ✓ Updated Beit Yehoshua LRT (node 511246): 13,601 demand, 6,101 transfers
```

❌ **Problem**: Hardcoded in Python dictionary
✅ **Solution**: Migrate to `manual_demand_updates.csv`

**Migration path**:
1. Add these 4 nodes to `manual_demand_updates.csv`
2. Remove hardcoded dictionary from code
3. Update Step 2.6.2 to use CSV loading (like Step 2.6.1)
4. Merge Step 2.6.1 and 2.6.2 into single CSV-based update step

---

### Category 4: Specific Node Corrections (Shefaim LRT)
**Purpose**: Apply correction for Shefaim LRT station with specific demand value

**Status**: ⚠️ **HARDCODED - Needs migration to CSV**

**Location**:
- `COMPLETE_TRANSIT_PIPELINE.ipynb` - Step 2.6.3
- `notebooks/OldCode_AddingDemand_Data.ipynb` (legacy)

**Current code**:
```python
# Hardcoded in Step 2.6.3
shefaim_node_id = 511248
shefaim_demand = 255.3

mask = gdf_demand['node'].apply(lambda node_list: shefaim_node_id in node_list)
if mask.any():
    gdf_demand.loc[mask, 'TotalDemand'] = shefaim_demand
    print(f"  ✓ Updated Shefaim LRT (node {shefaim_node_id}): {shefaim_demand} demand")
```

**Node affected**:
- **511248**: Shefaim LRT - 255.3 demand

**Current notification**:
```
Step 2.6.3: Updating Shefaim LRT stop demand...
  ✓ Updated Shefaim LRT (node 511248): 255.3 demand
```

❌ **Problem**: Hardcoded in code
✅ **Solution**: Migrate to `manual_demand_updates.csv`

**Migration**:
Add to CSV:
```csv
node,area,total_demand,total_transfers,station_name,notes
511248,Netanya,255.3,0,Shefaim LRT,Corrected forecast from local planning
```

---

### Category 5: Regional Demand Overlays (Hadera)
**Purpose**: Apply region-specific demand overlays to override base forecasts

**Status**: ⚠️ **HARDCODED - Needs design decision**

**Location**:
- `COMPLETE_TRANSIT_PIPELINE.ipynb` - Step 2.6 (embedded in main demand matching)
- `scripts/run_complete_pipeline.py` - Step 9 (line 852)

**Current code**:
```python
# Within Step 2.6 demand matching loop
if overlay_region in region_demand and node in region_demand[overlay_region]:
    overlay_demand = region_demand[overlay_region][node]
    total_demand = overlay_demand.get('TotalDemand', 0)
    total_transfers = overlay_demand.get('TotalTransfers', 0)
    overlay_matched += 1
    matched = True

# Later reporting
if overlay_region and overlay_matched > 0:
    print(f"  Applied {overlay_region} overlay: {overlay_matched} nodes updated")
```

**Regions with overlays**:
- **Hadera**: 4 nodes updated

**Current notification**:
```
Step 2.6: Matching demand to hubs by area...
  Applied Hadera overlay: 4 nodes updated
```

⚠️ **Design decision needed**:

**Option A**: Migrate to `manual_demand_updates.csv`
- Add all Hadera overlay nodes to CSV
- Include `data_source` = "Hadera Overlay"
- Simplest approach

**Option B**: Create separate `demand_overlays.csv`
- Regional overlay definitions
- Applied after base demand matching
- More complex but clearer separation

**Recommendation**: **Option A** - use existing `manual_demand_updates.csv` with `data_source` column

---

### Category 6: Legacy Index-Based Updates
**Purpose**: Old approach using DataFrame index rather than node ID

**Status**: 🗑️ **TO BE DEPRECATED**

**Locations**:
- `notebooks/OldCode_AddingDemand_Data.ipynb` (multiple cells)

**Current code examples**:
```python
# Index-based (OLD, fragile approach)
gdf.loc[gdf.index==1057, 'TotalDemand'] = 108409
gdf.loc[gdf.index==1058, 'TotalDemand'] = 108409
gdf.loc[gdf.index==421, 'TotalDemand'] = 40628
gdf.loc[gdf.index==422, 'TotalDemand'] = 40628
gdf.loc[gdf.index==419, 'TotalDemand'] = 41000
gdf.loc[gdf.index==420, 'TotalDemand'] = 41000
```

**Nodes affected** (based on comments in notebook):
- Indices 1057, 1058 → node 400020 (Netanya)
- Indices 421, 422 → node 400470 (Modiin Merkaz)
- Indices 419, 420 → node 400460 (Modiin West)

❌ **Problem**: Index-based updates are fragile (indices change with data updates)
✅ **Solution**: Already migrated to node-based CSV approach
🗑️ **Action**: Document as deprecated, do not port to new system

**Note**: The notebook `OldCode_AddingDemand_Data.ipynb` is legacy and should not be used for new work.

---

## Current vs. Desired State

### Current State: Manual Updates Scattered

```
┌─────────────────────────────────────────────────────────┐
│  CODEBASE (Multiple Locations)                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ✅ Step 1.5.1: IsSameGroup.csv (Group corrections)     │
│      → CSV-based, documented                            │
│                                                          │
│  ✅ Step 2.6.1: manual_demand_updates.csv               │
│      → CSV-based, documented                            │
│                                                          │
│  ❌ Step 2.6.2: Hardcoded National Model updates        │
│      → 4 nodes in Python dictionary                     │
│                                                          │
│  ❌ Step 2.6.3: Hardcoded Shefaim LRT update            │
│      → 1 node hardcoded                                 │
│                                                          │
│  ❌ Step 2.6: Hadera overlay (embedded in loop)         │
│      → 4 nodes in regional overlay logic                │
│                                                          │
│  🗑️ Legacy notebooks: Index-based updates              │
│      → Deprecated, do not use                           │
│                                                          │
└─────────────────────────────────────────────────────────┘

Problems:
- Inconsistent approaches (CSV vs hardcoded)
- Code edits required for updates
- Limited transparency and auditability
- Notes/reasoning scattered in comments
```

### Desired State: All Updates in Input Files

```
┌─────────────────────────────────────────────────────────┐
│  INPUT FILES (Centralized, Versioned)                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ✅ data/IsSameGroup.csv                                │
│      → Group merging corrections                        │
│      → With notes column for reasoning                  │
│                                                          │
│  ✅ data/manual_demand_updates.csv                      │
│      → ALL demand overrides (CSV + Hardcoded + Shefaim) │
│      → Includes: node, area, demand, transfers, notes   │
│      → Data source tracking                             │
│      → Confidence levels                                │
│      → Last updated timestamps                          │
│                                                          │
│  ✅ data/transit_lines_update.csv                       │
│      → Line and mode updates (future)                   │
│                                                          │
│  ✅ data/transit_stations_update.csv                    │
│      → Station metadata updates (future)                │
│                                                          │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  PIPELINE (Unified Update Processing)                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Step 1.5.1: Load group corrections                     │
│  Step 2.6.1: Load ALL demand updates (unified)          │
│                                                          │
│  → Validate input files                                 │
│  → Apply updates                                        │
│  → Log all changes with reasoning                       │
│  → Generate update summary report                       │
│                                                          │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  NOTIFICATION SYSTEM                                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ✅ Console output with detailed summary                │
│  ✅ Log file with full audit trail                      │
│  ✅ Update summary CSV for version control              │
│  ✅ Visual indicators for manual vs automatic data      │
│                                                          │
└─────────────────────────────────────────────────────────┘

Benefits:
+ All updates in version-controlled input files
+ Consistent format and validation
+ Complete audit trail with reasoning
+ Easy to update without code changes
+ Transparent and reproducible
```

---

## Integration Plan

### Phase 1: Migrate Hardcoded Updates to CSV ✅

**Goal**: Move all hardcoded demand updates to `manual_demand_updates.csv`

**Tasks**:

1. **Enhance `manual_demand_updates.csv` format**:
   - Add current hardcoded nodes (Step 2.6.2)
   - Add Shefaim LRT node (Step 2.6.3)
   - Add Hadera overlay nodes
   - Include comprehensive metadata

2. **Update CSV schema**:
   ```csv
   node,area,total_demand,total_transfers,station_name,data_source,confidence,is_override,last_updated,notes
   ```

3. **Consolidate pipeline steps**:
   - Merge Step 2.6.1, 2.6.2, 2.6.3 into **single unified Step 2.6.1**
   - Remove hardcoded dictionaries
   - Single CSV loading and validation

4. **Update documentation**:
   - Update `README_MANUAL_DEMAND_UPDATES.md`
   - Add migration notes for users

### Phase 2: Enhance Notification System ✅

**Goal**: Provide comprehensive, transparent reporting of all manual overrides

**Tasks**:

1. **Console output enhancements**:
   - Group updates by data source
   - Show reasoning/notes for each update
   - Highlight high-impact changes
   - Summary statistics (total updates, nodes affected, demand changed)

2. **Log file audit trail**:
   - Timestamp each update
   - Before/after values
   - Data source and confidence
   - User and version information

3. **Update summary CSV**:
   - Generated file: `data/results/run_YYYY-MM-DD_NN/update_summary.csv`
   - One row per manual update applied
   - Linked to run version for reproducibility

4. **Visual indicators**:
   - Flag manually-updated hubs in final output
   - Color-code by update type in map visualization
   - Include metadata in GeoJSON properties

### Phase 3: Integrate with Transit Update System ✅

**Goal**: Align with comprehensive transit update system design

**Tasks**:

1. **Standardize input file formats**:
   - Align `manual_demand_updates.csv` with `demand_2050_update.csv` schema
   - Ensure consistency across all input files
   - Add validation rules

2. **Implement update validation workflow**:
   - Pre-flight checks before pipeline execution
   - Validate node IDs against station database
   - Check for conflicts between update sources
   - Flag data quality issues

3. **Create unified update GUI** (future):
   - Streamlit interface for all update types
   - Group corrections editor
   - Demand overrides editor
   - Validation feedback
   - Update preview before committing

4. **Version control integration**:
   - Link manual updates to data versions
   - Track update history in version store
   - Enable rollback and comparison

---

## Enhanced Input File Formats

### 1. Enhanced `manual_demand_updates.csv`

**Purpose**: Centralized repository for ALL demand overrides

**Enhanced Schema**:

```csv
node,area,total_demand,total_transfers,station_name,data_source,confidence,is_override,last_updated,updated_by,notes
```

**Column Definitions**:

| Column | Type | Description | Example | Required |
|--------|------|-------------|---------|----------|
| `node` | Integer | Node ID to update | `400020` | ✅ Yes |
| `area` | String | Region name | `Tel Aviv` | ✅ Yes |
| `total_demand` | Float | Updated total demand | `108409.0` | ✅ Yes |
| `total_transfers` | Float | Updated total transfers | `84490.0` | ✅ Yes |
| `station_name` | String | Station name (human-readable) | `Netanya Central` | ✅ Yes |
| `data_source` | String | Source of update | `National Model 2025` | ⚠️ Recommended |
| `confidence` | String | Confidence level | `High`, `Medium`, `Low` | ⚠️ Recommended |
| `is_override` | Boolean | Is this overriding base forecast? | `TRUE`, `FALSE` | ⚠️ Recommended |
| `last_updated` | Date | When was this updated | `2025-01-17` | ⚠️ Recommended |
| `updated_by` | String | Who updated this | `planner@mot.gov.il` | Optional |
| `notes` | String | Explanation/reasoning | `Corrected based on local study` | ⚠️ Recommended |

**Enhanced Example**:

```csv
node,area,total_demand,total_transfers,station_name,data_source,confidence,is_override,last_updated,updated_by,notes
400020,Tel Aviv,108409,84490,Netanya Central,National Model 2025,High,TRUE,2025-01-15,transport.planner@example.com,Central station - verified against latest ridership projections
400470,Tel Aviv,40628,0,Modiin Merkaz,National Model 2025,High,TRUE,2025-01-15,transport.planner@example.com,New station - National Model has more accurate local forecast
400460,Tel Aviv,41000,12133,Modiin West,National Model 2025,Medium,TRUE,2025-01-10,transport.planner@example.com,Estimated based on similar stations in region
400424,Tel Aviv,64985,43032,Moshe Dayan (Rishon),National Model 2025,High,TRUE,2025-01-15,transport.planner@example.com,Major interchange - National Model forecast validated
400021,Tel Aviv,23083,10140,Netanya Sapir,National Model 2025,High,TRUE,2025-01-15,transport.planner@example.com,Secondary station in Netanya corridor
400030,Tel Aviv,14518,6101,Beit Yehoshua Rail,National Model 2025,Medium,TRUE,2025-01-15,transport.planner@example.com,Small station - forecast adjusted for TOD potential
511246,Netanya,13601,6101,Beit Yehoshua LRT,National Model 2025,Medium,TRUE,2025-01-15,transport.planner@example.com,LRT stop co-located with rail station
511248,Netanya,255.3,0,Shefaim LRT,Local Planning Study 2024,High,TRUE,2024-12-20,hadera.planner@example.com,Corrected forecast from Netanya LRT feasibility study
987294,Hadera,8234.5,2100,Hadera Central,Hadera Overlay Model,High,TRUE,2025-01-10,hadera.planner@example.com,Part of Hadera regional overlay - 4 nodes updated
```

**Benefits**:
- ✅ All demand overrides in ONE file
- ✅ Complete metadata for auditability
- ✅ Clear reasoning for each update
- ✅ Tracking of data sources and confidence
- ✅ Easy to update without code changes

---

### 2. Enhanced `IsSameGroup.csv`

**Purpose**: Group merging corrections with reasoning

**Current Schema**:
```csv
Nodes in group
"400018, 521063, 523019"
```

**Enhanced Schema**:
```csv
nodes_in_group,reason,applied_by,date_applied,notes
```

**Example**:
```csv
nodes_in_group,reason,applied_by,date_applied,notes
"400018, 521063, 523019",Planning decision - same interchange complex,planner@mot.gov.il,2025-01-15,Tel Aviv University interchange - rail and LRT should be same hub
"123456, 789012, 345678",Automatic grouping missed connection due to geography,analyst@mot.gov.il,2025-01-10,Stations connected by pedestrian bridge but >120m apart
```

**Benefits**:
- ✅ Clear reasoning for each manual merge
- ✅ Audit trail of who and when
- ✅ Better documentation for stakeholders

---

## Notification System Design

### Goal
**Transparent, comprehensive notification of all manual overrides applied during pipeline execution**

### Components

#### 1. Console Output (Real-time)

**Format**:
```
═══════════════════════════════════════════════════════════════════
  MANUAL UPDATES SUMMARY
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│  GROUP CORRECTIONS (Step 1.5.1)                                 │
├─────────────────────────────────────────────────────────────────┤
│  Source: data/IsSameGroup.csv                                   │
│  Corrections applied: 2                                         │
│  Groups merged: 4                                               │
│                                                                  │
│  ✅ Correction 1:                                               │
│     Nodes: [400018, 521063, 523019]                            │
│     Reason: Planning decision - same interchange complex       │
│     Applied by: planner@mot.gov.il (2025-01-15)                │
│     Action: Merged groups [635, 638] → 635                     │
│                                                                  │
│  ✅ Correction 2:                                               │
│     Nodes: [123456, 789012, 345678]                            │
│     Reason: Automatic grouping missed connection               │
│     Applied by: analyst@mot.gov.il (2025-01-10)                │
│     Action: Merged groups [5, 12, 15] → 5                      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  DEMAND OVERRIDES (Step 2.6.1)                                  │
├─────────────────────────────────────────────────────────────────┤
│  Source: data/manual_demand_updates.csv                         │
│  Updates applied: 9                                             │
│  Total demand adjusted: +245,123 passengers                     │
│                                                                  │
│  🔵 National Model Updates (4 nodes, HIGH confidence):          │
│     ✅ 400424 - Moshe Dayan (Rishon):                           │
│        Demand: 64,985 | Transfers: 43,032                       │
│        Source: National Model 2025                              │
│        Note: Major interchange - validated forecast             │
│                                                                  │
│     ✅ 400021 - Netanya Sapir:                                  │
│        Demand: 23,083 | Transfers: 10,140                       │
│        Source: National Model 2025                              │
│        Note: Secondary station in Netanya corridor              │
│                                                                  │
│     ✅ 400030 - Beit Yehoshua Rail:                             │
│        Demand: 14,518 | Transfers: 6,101                        │
│        Source: National Model 2025                              │
│        Note: Small station - forecast adjusted for TOD          │
│                                                                  │
│     ✅ 511246 - Beit Yehoshua LRT:                              │
│        Demand: 13,601 | Transfers: 6,101                        │
│        Source: National Model 2025                              │
│        Note: LRT stop co-located with rail station              │
│                                                                  │
│  🟢 Local Planning Updates (1 node, HIGH confidence):           │
│     ✅ 511248 - Shefaim LRT:                                    │
│        Demand: 255.3 | Transfers: 0                             │
│        Source: Local Planning Study 2024                        │
│        Note: Corrected from Netanya LRT feasibility study       │
│                                                                  │
│  🟡 Regional Overlay Updates (4 nodes, HIGH confidence):        │
│     ✅ Hadera Regional Overlay (4 nodes):                       │
│        987294, 987295, 987296, 987297                           │
│        Source: Hadera Overlay Model                             │
│        Note: Part of regional demand overlay                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  SUMMARY                                                         │
├─────────────────────────────────────────────────────────────────┤
│  Total manual updates: 11                                       │
│  Group corrections: 2                                           │
│  Demand overrides: 9                                            │
│                                                                  │
│  ⚠️  IMPORTANT: These updates override automatic processing     │
│      Review audit log for complete details                      │
│      See: data/results/run_2025-01-17_01/update_summary.csv    │
└─────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════
```

**Features**:
- ✅ Color coding by update type
- ✅ Grouped by data source
- ✅ Shows reasoning for each update
- ✅ Confidence levels indicated
- ✅ Summary statistics

---

#### 2. Log File (Detailed Audit Trail)

**File**: `data/results/run_YYYY-MM-DD_NN/manual_updates.log`

**Format**:
```
2025-01-17 14:32:15 | MANUAL_UPDATE | GROUP_CORRECTION | nodes=[400018,521063,523019] | groups_merged=[635,638]→635 | reason="Planning decision - same interchange complex" | applied_by="planner@mot.gov.il" | date="2025-01-15"

2025-01-17 14:32:45 | MANUAL_UPDATE | DEMAND_OVERRIDE | node=400424 | station="Moshe Dayan (Rishon)" | demand_before=52340 | demand_after=64985 | change=+12645 (+24.1%) | transfers_before=35200 | transfers_after=43032 | change=+7832 (+22.2%) | source="National Model 2025" | confidence="High" | notes="Major interchange - validated forecast" | applied_by="transport.planner@example.com" | date="2025-01-15"

2025-01-17 14:32:47 | MANUAL_UPDATE | DEMAND_OVERRIDE | node=511248 | station="Shefaim LRT" | demand_before=180.5 | demand_after=255.3 | change=+74.8 (+41.4%) | transfers_before=0 | transfers_after=0 | source="Local Planning Study 2024" | confidence="High" | notes="Corrected from Netanya LRT feasibility study" | applied_by="hadera.planner@example.com" | date="2024-12-20"
```

**Features**:
- ✅ Machine-readable format
- ✅ Before/after values
- ✅ Percent change calculations
- ✅ Complete metadata
- ✅ Timestamp and user tracking

---

#### 3. Update Summary CSV

**File**: `data/results/run_YYYY-MM-DD_NN/update_summary.csv`

**Purpose**: CSV summary of all manual updates for easy analysis and version tracking

**Schema**:
```csv
timestamp,run_id,update_type,update_category,node_id,station_name,field_updated,value_before,value_after,change_pct,data_source,confidence,applied_by,applied_date,notes
```

**Example**:
```csv
timestamp,run_id,update_type,update_category,node_id,station_name,field_updated,value_before,value_after,change_pct,data_source,confidence,applied_by,applied_date,notes
2025-01-17T14:32:15Z,run_2025-01-17_01,GROUP_CORRECTION,Manual,400018,Tel Aviv University,group_id,635,635,0.0,IsSameGroup.csv,Manual,planner@mot.gov.il,2025-01-15,Planning decision - same interchange complex
2025-01-17T14:32:45Z,run_2025-01-17_01,DEMAND_OVERRIDE,National Model,400424,Moshe Dayan (Rishon),TotalDemand,52340,64985,24.1,National Model 2025,High,transport.planner@example.com,2025-01-15,Major interchange - validated forecast
2025-01-17T14:32:45Z,run_2025-01-17_01,DEMAND_OVERRIDE,National Model,400424,Moshe Dayan (Rishon),TotalTransfers,35200,43032,22.2,National Model 2025,High,transport.planner@example.com,2025-01-15,Major interchange - validated forecast
2025-01-17T14:32:47Z,run_2025-01-17_01,DEMAND_OVERRIDE,Local Planning,511248,Shefaim LRT,TotalDemand,180.5,255.3,41.4,Local Planning Study 2024,High,hadera.planner@example.com,2024-12-20,Corrected from Netanya LRT feasibility study
```

**Features**:
- ✅ One row per field update
- ✅ Links to run version
- ✅ Easy to analyze in Excel/Python
- ✅ Can be tracked in version control
- ✅ Enables trend analysis over time

---

#### 4. Visual Indicators in Output Files

**GeoJSON Properties Enhancement**:

Add metadata to output GeoJSON to indicate manual updates:

```json
{
  "type": "Feature",
  "properties": {
    "hub_id": "hub_001",
    "station_name": "Moshe Dayan (Rishon)",
    "total_demand": 64985,
    "has_manual_updates": true,
    "manual_update_fields": ["TotalDemand", "TotalTransfers"],
    "manual_update_sources": ["National Model 2025"],
    "manual_update_confidence": "High",
    "manual_update_notes": "Major interchange - validated forecast"
  }
}
```

**Map Visualization**:
- Color-code hubs with manual updates (e.g., orange border)
- Add tooltip info showing update metadata
- Legend indicating manual vs automatic data

**CSV Output**:
Add columns:
```csv
hub_id,station_name,total_demand,...,has_manual_demand_update,demand_update_source,demand_update_confidence,demand_update_notes
hub_001,Moshe Dayan (Rishon),64985,...,TRUE,National Model 2025,High,Major interchange - validated forecast
```

---

### Notification System Implementation

**Code location**: `src/utils/manual_updates_notifier.py` (new module)

**Class**:
```python
class ManualUpdatesNotifier:
    """
    Comprehensive notification system for manual updates.

    Provides console output, log files, CSV summaries, and visual indicators.
    """

    def __init__(self, run_version_id: str, results_dir: Path):
        self.run_version_id = run_version_id
        self.results_dir = results_dir
        self.updates = []  # Track all updates

    def log_group_correction(self, nodes: List[int], groups_merged: List[int],
                             reason: str, applied_by: str, date: str):
        """Log a group correction update."""

    def log_demand_override(self, node_id: int, station_name: str,
                            demand_before: float, demand_after: float,
                            transfers_before: float, transfers_after: float,
                            data_source: str, confidence: str, notes: str,
                            applied_by: str, date: str):
        """Log a demand override update."""

    def print_summary(self):
        """Print formatted console summary."""

    def save_audit_log(self):
        """Save detailed log file."""

    def save_update_summary_csv(self):
        """Save CSV summary."""

    def add_visual_indicators(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Add manual update metadata to GeoDataFrame."""
```

**Integration**:
- Called in Step 1.5.1 for group corrections
- Called in Step 2.6.1 for demand overrides
- Summary printed before final results
- Files saved to versioned results directory

---

## Implementation Roadmap

### Week 1: Phase 1 - Migrate Hardcoded Updates ✅

**Tasks**:
1. ✅ Create enhanced `manual_demand_updates.csv` with all nodes
2. ✅ Update `README_MANUAL_DEMAND_UPDATES.md` with new schema
3. ✅ Modify Step 2.6.1 to load enhanced CSV
4. ✅ Remove Step 2.6.2 (hardcoded National Model updates)
5. ✅ Remove Step 2.6.3 (hardcoded Shefaim update)
6. ✅ Test unified demand update step
7. ✅ Document migration in CHANGELOG

**Deliverables**:
- Enhanced `manual_demand_updates.csv` with all 9+ nodes
- Updated `README_MANUAL_DEMAND_UPDATES.md`
- Modified `COMPLETE_TRANSIT_PIPELINE.ipynb` (Steps 2.6.1-2.6.3 → 2.6.1 unified)
- Migration notes for users

**Success Criteria**:
- Pipeline runs successfully with CSV-only updates
- All hardcoded demand updates removed from code
- Same results as before migration

---

### Week 2: Phase 2 - Notification System ✅

**Tasks**:
1. ✅ Create `src/utils/manual_updates_notifier.py`
2. ✅ Implement `ManualUpdatesNotifier` class
3. ✅ Add console output formatting
4. ✅ Add audit log generation
5. ✅ Add update summary CSV generation
6. ✅ Integrate with Step 1.5.1 (group corrections)
7. ✅ Integrate with Step 2.6.1 (demand updates)
8. ✅ Test notification output
9. ✅ Update documentation

**Deliverables**:
- `src/utils/manual_updates_notifier.py`
- Enhanced console output with formatted summaries
- Audit log: `data/results/run_YYYY-MM-DD_NN/manual_updates.log`
- Summary CSV: `data/results/run_YYYY-MM-DD_NN/update_summary.csv`
- Updated pipeline with integrated notifications

**Success Criteria**:
- Clear, comprehensive notifications during pipeline execution
- Complete audit trail in log files
- CSV summary generated for each run
- Users can easily see what manual updates were applied

---

### Week 3: Phase 3 - Visual Indicators & Integration ✅

**Tasks**:
1. ✅ Add `has_manual_updates` metadata to GeoDataFrame
2. ✅ Enhance GeoJSON export with update metadata
3. ✅ Add manual update columns to CSV export
4. ✅ Update map visualization to color-code manual updates
5. ✅ Add tooltips showing update metadata
6. ✅ Enhance `IsSameGroup.csv` with reason/notes columns
7. ✅ Update `README_MANUAL_GROUP_CORRECTIONS.md`
8. ✅ Align with Transit Update System Design document
9. ✅ Integration testing

**Deliverables**:
- Enhanced output files (GeoJSON, CSV) with manual update indicators
- Updated map visualization with color coding
- Enhanced `IsSameGroup.csv` schema
- Complete integration with Transit Update System Design
- End-to-end testing results

**Success Criteria**:
- Output files clearly indicate which hubs have manual updates
- Map visualization shows manual vs automatic data
- All manual updates tracked and documented
- System integrated with broader Transit Update System

---

### Week 4: Documentation & Rollout ✅

**Tasks**:
1. ✅ Update `TRANSIT_UPDATE_SYSTEM_DESIGN.md`
2. ✅ Create user migration guide
3. ✅ Update `CLAUDE.md` with manual updates section
4. ✅ Create training materials for users
5. ✅ Record demo video (optional)
6. ✅ Final testing and validation
7. ✅ Git commit and push
8. ✅ Release announcement

**Deliverables**:
- Updated `TRANSIT_UPDATE_SYSTEM_DESIGN.md` with manual updates integration
- User migration guide for transitioning from hardcoded to CSV
- Updated `CLAUDE.md`
- Training materials
- Final tested, documented system
- Git commit with comprehensive changelog

**Success Criteria**:
- Complete documentation
- Users can easily migrate existing manual updates
- System is production-ready
- All stakeholders informed

---

## Migration Guide

### For Users: Transitioning from Hardcoded to CSV

#### Step 1: Identify Current Manual Updates

**Review your current code** for any hardcoded updates:

```python
# Example: Find hardcoded demand updates
grep -n "\.loc.*TotalDemand.*=" COMPLETE_TRANSIT_PIPELINE.ipynb
grep -n "\.loc.*TotalTransfers.*=" COMPLETE_TRANSIT_PIPELINE.ipynb
```

**Document each update**:
- Node ID
- Station name
- Demand value
- Transfer value
- Data source
- Reasoning

#### Step 2: Create/Update `manual_demand_updates.csv`

**Location**: `data/manual_demand_updates.csv`

**Template**:
```csv
node,area,total_demand,total_transfers,station_name,data_source,confidence,is_override,last_updated,updated_by,notes
```

**Add your updates**:
```csv
node,area,total_demand,total_transfers,station_name,data_source,confidence,is_override,last_updated,updated_by,notes
400424,Tel Aviv,64985,43032,Moshe Dayan (Rishon),National Model 2025,High,TRUE,2025-01-15,your.email@example.com,Major interchange - validated forecast
```

#### Step 3: Remove Hardcoded Updates

**Delete or comment out** hardcoded update code:

```python
# OLD (DELETE THIS):
# gdf_demand.loc[mask, 'TotalDemand'] = 64985
# gdf_demand.loc[mask, 'TotalTransfers'] = 43032

# NEW: All updates now in data/manual_demand_updates.csv
```

#### Step 4: Update Configuration

**In notebook**, set CSV path:

```python
MANUAL_DEMAND_UPDATES_CSV = Path('data/manual_demand_updates.csv')
```

#### Step 5: Test

**Run pipeline and verify**:
1. Check console output for "Applied X manual demand updates"
2. Verify demand values are correct
3. Review `manual_updates.log` and `update_summary.csv`

#### Step 6: Version Control

**Commit your changes**:
```bash
git add data/manual_demand_updates.csv
git commit -m "Migrate manual demand updates from code to CSV"
```

---

### For Developers: Code Changes

#### Remove Hardcoded Updates

**Before** (Step 2.6.2):
```python
# Hardcoded National Model updates
NATIONAL_MODEL_UPDATES = {
    400424: (64985, 43032, 'Moshe Dayan (Rishon)'),
    400021: (23083, 10140, 'Netanya Sapir'),
    ...
}

for node_id, (demand, transfers, name) in NATIONAL_MODEL_UPDATES.items():
    ...
```

**After**: ❌ **Delete entire Step 2.6.2**

---

**Before** (Step 2.6.3):
```python
# Hardcoded Shefaim LRT update
shefaim_node_id = 511248
shefaim_demand = 255.3
mask = gdf_demand['node'].apply(lambda node_list: shefaim_node_id in node_list)
if mask.any():
    gdf_demand.loc[mask, 'TotalDemand'] = shefaim_demand
```

**After**: ❌ **Delete entire Step 2.6.3**

---

#### Enhance Step 2.6.1

**Add** comprehensive notification:

```python
if PART2_AVAILABLE:
    print("Step 2.6.1: Loading manual demand updates from CSV...")

    # Initialize notifier
    from src.utils.manual_updates_notifier import ManualUpdatesNotifier
    notifier = ManualUpdatesNotifier(run_version_id='run_2025-01-17_01',
                                      results_dir=RESULTS_DIR)

    if MANUAL_DEMAND_UPDATES_CSV and os.path.exists(MANUAL_DEMAND_UPDATES_CSV):
        updates_df = pd.read_csv(MANUAL_DEMAND_UPDATES_CSV)
        print(f"  ✓ Loaded {len(updates_df)} demand updates from CSV")

        for _, update_row in updates_df.iterrows():
            node_id = int(update_row['node'])
            demand = update_row['total_demand']
            transfers = update_row['total_transfers']

            # Get before values
            mask = gdf_demand['node'].apply(lambda nodes: node_id in nodes)
            demand_before = gdf_demand.loc[mask, 'TotalDemand'].iloc[0] if mask.any() else 0
            transfers_before = gdf_demand.loc[mask, 'TotalTransfers'].iloc[0] if mask.any() else 0

            # Apply update
            if mask.any():
                gdf_demand.loc[mask, 'TotalDemand'] = demand
                gdf_demand.loc[mask, 'TotalTransfers'] = transfers

                # Log to notifier
                notifier.log_demand_override(
                    node_id=node_id,
                    station_name=update_row.get('station_name', f'Node {node_id}'),
                    demand_before=demand_before,
                    demand_after=demand,
                    transfers_before=transfers_before,
                    transfers_after=transfers,
                    data_source=update_row.get('data_source', 'Unknown'),
                    confidence=update_row.get('confidence', 'Unknown'),
                    notes=update_row.get('notes', ''),
                    applied_by=update_row.get('updated_by', 'Unknown'),
                    date=update_row.get('last_updated', '')
                )

        # Print summary and save logs
        notifier.print_summary()
        notifier.save_audit_log()
        notifier.save_update_summary_csv()
```

---

## Summary

This document provides:

✅ **Complete inventory** of all manual updates in codebase
✅ **Migration plan** from hardcoded to CSV-based updates
✅ **Enhanced input file formats** with comprehensive metadata
✅ **Notification system design** for transparency and auditability
✅ **Implementation roadmap** with timeline and deliverables
✅ **Migration guide** for users and developers

**Next Steps**:
1. Review and approve this plan
2. Begin Week 1 implementation (migrate hardcoded updates)
3. Iterative development through Weeks 2-4
4. Final testing and documentation
5. Rollout to production

---

**Document Version**: 1.0
**Last Updated**: 2025-01-17
**Status**: Ready for Implementation
