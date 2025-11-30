# Input Data Configuration Guide
# ==============================

This document explains where to place your data files and how to configure paths.

## Quick Setup

### Step 1: Place your data files in `data/raw/`

```
data/raw/
├── All_nodes+lines.csv              # Transit nodes (REQUIRED)
├── Lines_and_Planned_Mode.csv       # Line-to-mode mapping (REQUIRED)
├── demand_2050.xlsx                 # Demand forecasts (OPTIONAL)
└── spatial/                         # Spatial layers (OPTIONAL)
    ├── metro.shp                    # Metro areas
    ├── districts.shp                # Administrative districts
    ├── TAZ_2050.shp                 # Traffic Analysis Zones with POP_2050, EMPL_2050
    └── bus_terminals.shp            # Bus terminals
```

### Step 2: Configure paths in the script

Open **`scripts/run_complete_pipeline.py`** and edit the paths at the top:

```python
# Line 20-35 - EDIT THESE PATHS
INPUT_TRANSIT_NODES = RAW_DATA_DIR / "All_nodes+lines.csv"
INPUT_LINES_MODES = RAW_DATA_DIR / "Lines_and_Planned_Mode.csv"
INPUT_DEMAND_EXCEL = RAW_DATA_DIR / "demand_2050.xlsx"
INPUT_METRO_AREAS = RAW_DATA_DIR / "spatial/metro.shp"
INPUT_DISTRICTS = RAW_DATA_DIR / "spatial/districts.shp"
INPUT_TAZ_ZONES = RAW_DATA_DIR / "spatial/TAZ_2050.shp"
INPUT_BUS_TERMINALS = RAW_DATA_DIR / "spatial/bus_terminals.shp"
```

### Step 3: Enable/disable optional data

If you don't have certain data yet, set these flags (lines 37-40):

```python
SKIP_DEMAND_DATA = False      # Set True if no demand Excel
SKIP_SPATIAL_LAYERS = False   # Set True if no shapefiles
SKIP_DEMOGRAPHICS = False     # Set True if no TAZ data
```

## Required vs Optional Files

### ✅ **REQUIRED** (Pipeline will fail without these)

1. **`All_nodes+lines.csv`**
   - Transit network nodes with coordinates
   - Columns: `node`, `LINE_ID`, `X`, `Y` (or `geometry`)
   - CRS: Israel TM Grid (EPSG:2039)

2. **`Lines_and_Planned_Mode.csv`**
   - Maps LINE_ID to transport mode
   - Columns: `Line_ModelName`, `Mode_Planned`, `Area`

### ⚠️ **RECOMMENDED** (Needed for full scoring)

3. **`demand_2050.xlsx`**
   - 2050 passenger forecasts
   - Sheets: Haifa, TelAviv, Jerusalem, BeerSheva, Ashdod, etc.
   - Columns per sheet: `node`, `Boardings`, `Alightings`
   - **Without this**: Activity score will use placeholders

4. **`metro.shp` + `districts.shp`**
   - Metro areas and administrative districts
   - Used for spatial tagging
   - **Without these**: Location score will use defaults

5. **`TAZ_2050.shp`**
   - Traffic Analysis Zones
   - Required columns: `POP_2050`, `EMPL_2050`
   - **Without this**: Demographics score will use placeholders

### 📋 **OPTIONAL** (Nice to have)

6. **`bus_terminals.shp`**
   - Bus terminal locations
   - **Without this**: Terminal score will default to 1.0 for all hubs

## File Format Requirements

### Transit Nodes CSV
```csv
node,LINE_ID,X,Y
1001,Rail_TA_Line1,180000,660000
1002,Rail_TA_Line1,180500,660500
...
```

OR with WKT geometry:
```csv
node,LINE_ID,geometry
1001,Rail_TA_Line1,"POINT(180000 660000)"
...
```

### Lines and Modes CSV
```csv
Line_ModelName,Mode_Planned,Area
Rail_TA_Line1,Rail,TelAviv
LRT_JLM_Red,LRT,Jerusalem
BRT_Haifa_1,BRT,Haifa
...
```

### Demand Excel Structure
```
Sheet: TelAviv
| node | Boardings | Alightings | Transfers |
|------|-----------|------------|-----------|
| 1001 | 15000     | 14500      | 2000      |
| 1002 | 8000      | 8200       | 1500      |
...

Sheet: Jerusalem
| node | Boardings | Alightings |
|------|-----------|------------|
| 2001 | 12000     | 11800      |
...
```

### Spatial Shapefiles

Must have standard shapefile components:
- `.shp` (geometry)
- `.shx` (index)
- `.dbf` (attributes)
- `.prj` (projection)

**TAZ shapefile** must have:
- `POP_2050` column (numeric)
- `EMPL_2050` column (numeric)

## Running with Different Data Configurations

### Scenario 1: I only have transit nodes and lines
```python
# In run_complete_pipeline.py
SKIP_DEMAND_DATA = True
SKIP_SPATIAL_LAYERS = True
SKIP_DEMOGRAPHICS = True

# Pipeline will run Steps 1-3, 8-11 with placeholder scores
```

### Scenario 2: I have everything except bus terminals
```python
# In run_complete_pipeline.py
SKIP_DEMAND_DATA = False
SKIP_SPATIAL_LAYERS = False
SKIP_DEMOGRAPHICS = False

# Leave INPUT_BUS_TERMINALS as is - pipeline will detect it's missing
# Terminal score will default to 1.0 for all hubs
```

### Scenario 3: Full dataset
```python
# All SKIP_* = False
# All input files exist
# Pipeline runs all 11 steps
```

## Troubleshooting

### "File not found" error
- Check the file path is correct
- Ensure file is in `data/raw/` directory
- Check file extension (.csv vs .xlsx vs .shp)

### "Column not found" error
- Check your CSV/Excel has the expected column names
- Column names are case-sensitive
- Remove any extra spaces in column names

### "CRS error" for shapefiles
- Shapefiles should be in EPSG:2039 (Israel TM Grid)
- Or EPSG:4326 (WGS84) - will be reprojected automatically

### "Encoding error" reading Hebrew text
- Ensure CSVs with Hebrew are saved as windows-1255 or UTF-8
- The code tries multiple encodings automatically

## Next Steps

After configuring paths:

```bash
# Run the pipeline
python scripts/run_complete_pipeline.py

# Check outputs in
ls data/results/
```

Results will include:
- `hub_prioritization_results_YYYYMMDD_HHMMSS.csv` - Full results
- `hub_results_YYYYMMDD_HHMMSS.geojson` - Spatial data
- `hub_map_YYYYMMDD_HHMMSS.html` - Interactive map
