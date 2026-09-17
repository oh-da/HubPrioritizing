s # CLAUDE.md
**Centralized Logic for Assessing, Understanding & Determining Evaluation**
**Hub Prioritization Framework for Integrated Transport Hubs (מתח"מים) in Israel**

---

## Table of Contents

1. [Purpose & Overview](#1-purpose--overview)
2. [Domain Context: What is a מתח״מ?](#2-domain-context-what-is-a-מתחמ)
3. [Problem Statement](#3-problem-statement)
4. [Framework Deliverables](#4-framework-deliverables)
5. [Hub Hierarchy](#5-hub-hierarchy)
6. [Workflow & Methodology](#6-workflow--methodology)
7. [Scoring Criteria](#7-scoring-criteria)
8. [Technical Implementation](#8-technical-implementation)
9. [Codebase Structure](#9-codebase-structure)
10. [Data Requirements](#10-data-requirements)
11. [Development Workflows](#11-development-workflows)
12. [Key Conventions](#12-key-conventions)
13. [Design Principles](#13-design-principles)
14. [AI Assistant Guidelines](#14-ai-assistant-guidelines)
15. [Results Overview](#15-results-overview-current-state)
16. [Future Directions](#16-future-directions)
17. [References & Sources](#17-references--sources)
18. [Code Quality](#18-code-quality)
19. [Document Maintenance](#19-document-maintenance)
20. [Quick Reference](#20-quick-reference)
21. [Contact & Support](#21-contact--support)

---

## 1. Purpose & Overview

This repository implements a unified framework for identifying, classifying, prioritizing, and evaluating integrated transport hubs (מתח"מים) in Israel. It standardizes terminology, hierarchy, criteria, data inputs, scoring, and process flow to support consistent system-level planning and resource allocation.

### Core Objectives

- **Systematic Identification**: Discover all potential hubs across mass-transit plans
- **Standardized Classification**: Apply consistent hierarchy (ארצי, מטרופוליני, עירוני)
- **Data-Driven Scoring**: Use transparent, reproducible methodology
- **Prioritization Support**: Enable evidence-based investment decisions
- **Spatial Visualization**: Provide interactive interface for results

---

## 2. Domain Context: What is a מתח״מ?

**מרכז תחבורה משולב (Integrated Transport Hub)** is a multimodal passenger interchange that includes:

- **At least one mass-transit mode**: רכבת (rail), מטרו (metro), רק״ל (light rail), or BRT
- **Seamless transfers**: Between multiple transport modes
- **Network centrality**: Functions as operational "heart" of the public transport network
- **Development catalyst**: Often drives transit-oriented development (TOD)

### Why It Matters

Hubs are not just infrastructure—they are:
- **Demand concentrators**: Aggregating passengers for efficient mass transit
- **Network integrators**: Connecting different modes and scales
- **Urban catalysts**: Driving development, accessibility, and economic activity
- **User experience touchpoints**: Critical for system-wide service quality

---

## 3. Problem Statement

### Current Challenges

Current planning of multi-modal hubs suffers from:

1. **Fragmentation**: No unified methodology across agencies
2. **Inconsistency**: Different criteria and standards per project
3. **Sub-optimal Investment**: Resource allocation without systematic prioritization
4. **Weak Connectivity**: Poor inter-modal integration
5. **Missed TOD Opportunities**: Development potential not realized

### The Solution

A **systemic, unified framework** that includes:
- Hub identification methodology
- Standardized classification system
- Objective scoring criteria
- Transparent prioritization process
- Reproducible, auditable results

---

## 4. Framework Deliverables

This system produces:

1. **Systematic Identification**: All potential hubs across mass-transit plans
2. **Standardized Hierarchy**: Classification into ארצי/מטרופוליני/עירוני
3. **Scoring & Prioritization**: Data-driven ranking methodology
4. **Planning Guidance**: Hub design and user-experience principles
5. **Spatial Interface**: Interactive visualization of results
6. **Reproducible Process**: Transparent, auditable, updatable methodology

---

## 5. Hub Hierarchy

### 5.1 ארצי (National)

**Definition**: Top-tier hubs connecting metropolitan regions and major cities

- **Ridership**: >50,000/day (commonly >100,000)
- **Role**: Links national networks (especially rail) to regional/urban systems
- **Characteristics**:
  - Very high frequencies across multiple modes
  - Major demand concentration
  - Economic significance
  - Major development catalyst
- **Examples**: Tel Aviv Savidor, Jerusalem Central, Haifa Merkaz

### 5.2 מטרופוליני (Metropolitan)

**Definition**: Mid-level nodes linking mass-transit lines to local feeders

- **Ridership**: ~5,000–50,000/day
- **Role**: Aggregates demand to trunk lines
- **Characteristics**:
  - Supports TOD
  - Smooth transfers between modes
  - High-frequency services
  - Regional connectivity
- **Sub-categories**:
  - Tel Aviv + Center: 29 hubs
  - Haifa + North: 14 hubs
  - South: 3 hubs

### 5.3 עירוני (Local)

**Definition**: Neighborhood/settlement gateways to PT network

- **Ridership**: <5,000/day
- **Role**: First/last-mile connections
- **Characteristics**:
  - Connects walking/cycling/feeder buses to higher tiers
  - Accessibility focus
  - Neighborhood integration

### Important Notes

- **No inherent preference**: All tiers are necessary and complementary
- **Hierarchy is descriptive**, not prescriptive of quality
- **Context matters**: A local hub in a small city may be as important locally as a national hub nationally

---

## 6. Workflow & Methodology

### Overall Process (Iterative)

```
1. Data Collection
   ↓
2. System Reconciliation
   ↓
3. Area Identification (H3 hexes)
   ↓
4. Eligibility Filtering
   ↓
5. Classification
   ↓
6. Scoring by Criteria
   ↓
7. Aggregation & Prioritization
   ↓
8. Validation & Iteration
```

### Step-by-Step Details

#### Step 1: Data Collection
- Transit lines (planned and existing)
- Station locations and forecasts
- 2050 demand projections
- Strategic transport plans
- Land use and demographic data
- Bus terminal strategies

#### Step 2: System Reconciliation
- Align forecasts across different sources
- Verify planned modes and timelines
- Resolve conflicts in planning documents
- Standardize station names and IDs

#### Step 3: Area Identification
- Use **H3 hexagons at 150m resolution**
- Aggregate passengers by hex
- Merge adjacent hexes into hub areas
- Define hub center points

#### Step 4: Eligibility Filtering

Exclude if:
- **< 1,000 passengers/day** → Not a hub
- **Only one mass-transit mode** → Not a hub
- No planned mass-transit service

#### Step 5: Classification
Classify remaining hubs into hierarchy based on:
- Ridership thresholds
- Modal diversity
- Network role
- Geographic context

#### Step 6: Scoring
Apply all scoring criteria (see Section 7)

#### Step 7: Aggregation

**Monte Carlo Simulation**
- 10,000 iterations with random weight sets
- Each criterion 0–50% per iteration (raw draws are capped at 0.5, then normalised to sum to 1)
- **Runs per hub type** with one seeded random stream consumed type by type (`mc_scope = per_hubtype`, the notebook's behaviour); `mc_scope = all_hubs` runs a single simulation across the entire dataset
- Final score = weighted mean across simulations (`Average_Simulated_Score` = `TotalScore_MC`)
- Prevents single-criterion dominance
- Robust to weighting uncertainty

#### Step 8: Ranking

After Monte Carlo scoring, hubs are ranked based on their tier and geographic area:

- **National (ארצי)**: All national hubs ranked **globally** together
- **Metropolitan (מטרופוליני)**: Ranked **within their geographic area** (e.g., Tel Aviv area, Haifa area, South area)
- **Local (עירוני)**: Ranked **within their geographic area**

This ensures hubs compete within comparable geographic contexts while national hubs are ranked nationwide.

#### Step 9: Validation
- Expert review
- Sensitivity analysis
- Update with new data/plans

---

## 7. Scoring Criteria

Each hub receives a **normalized score (1–10)** for each criterion.

### Normalization Approach

**Important**: Normalization is performed **per hub tier** (ארצי/מטרופוליני/עירוני), NOT per metro area within each tier:

| Criterion | Column | Normalization Method |
|-----------|--------|---------------------|
| Passenger Activity | `TotalDemand_Norm` | Per tier (log₁₀ + min-max to 1-10) |
| Service & Modes | `score_Norm` | Per tier (min-max to 1-10) |
| Location | `RegionLocation_Norm` | Per tier (min-max to 1-10) |
| Population & Jobs | `PopEmp_Score_Norm` | Per tier (min-max to 1-10) |
| Bus Terminal | `bus_terminal_Norm` | Per tier (min-max to 1-10) |

This means:
- All Metropolitan hubs (regardless of geographic area) are normalized together
- All Local hubs are normalized together
- National hubs are normalized together
- A tier whose values are all equal receives 5.5 for that criterion
- `renormalize_globally=true` reproduces the older results workbook's globally re-normalised display columns (see `docs/DEVIATIONS.md`)

### Aggregation

Final weights come from **Monte Carlo weighted scoring**: random weight simulation that prevents single-criterion dominance (Step 7).

### 7.1 Passenger Activity Score

**What it measures**: 2050 forecast demand

**Methodology**:
- Based on 2050 passenger forecasts
- **Log₁₀ transformation** to avoid extreme skew from mega-stations
- **Per-tier normalization**: All hubs within the same tier (ארצי/מטרופוליני/עירוני) are normalized together, regardless of geographic area

**Formula**:
```
activity_score = normalize_by_tier(log10(passengers_2050))
```

**Rationale**:
- A station with 100,000 passengers should not score 10× higher than 10,000
- Logarithmic scale reflects diminishing marginal impact
- Per-tier normalization ensures fair comparison within tier (NOT per metro area)

### 7.2 Service & Hierarchy of Modes Score

**What it measures**: Strength and diversity of transit service

**Components**:

1. **Line Count per Mode**
   - Each direction = separate line
   - Diminishing returns for high counts (2nd/3rd lines matter more than 9th)

2. **Modal Weights**
   - Each mode weighted by service quality
   - Higher capacity modes receive higher weights
   - Weights: Rail > Metro > Light Rail > BRT > Local Bus

3. **Diversity Bonus**
   - 2nd mode: +10%
   - 3rd mode: +20%
   - 4th mode: +30%
   - And so on...

**Formula**:
```
service_score = normalize_by_tier(Σ(mode_weight × line_count_with_diminishing_returns) × diversity_bonus)
```

**Normalization**: Per tier (all hubs of the same tier normalized together, regardless of metro area)

**Rationale**:
- More modes = better connectivity and resilience
- First few lines have bigger impact than many lines of same mode
- Diversity bonus reflects network effects of multimodality

### 7.3 Location Score (Geographic & Metropolitan)

**What it measures**: Strategic importance of location

**Two-dimensional scoring**:

1. **National Region**:
   - Center/Tel Aviv region = weight 0
   - All other regions = weight 1
   - (Inverted to prioritize peripheral areas)

2. **Metropolitan Position**:
   - Core = 3
   - First ring = 2
   - Outer = 1

**Formula**:
```
location_score = normalize_global(region_weight × ring_score)
```

**Normalization**: Per tier (`RegionLocation_Norm`)

**Rationale**:
- Balances national equity (periphery boost) with metropolitan efficiency (core importance)
- Recognizes different strategic value of locations
- Prevents over-concentration in center

### 7.4 Population & Jobs Score (2050)

**What it measures**: Development potential and catchment area

**Methodology**:

1. **Concentric Rings** (up to 1.5 km):
   - Multiple rings with distance decay
   - Closer rings weighted more heavily

2. **Different Mixes by Hub Type**:
   - **National/Metropolitan**: 80% jobs / 20% population
   - **Local**: 20% jobs / 80% population

3. **2050 Forecasts**:
   - Uses future land use projections
   - Reflects TOD potential

**Formula**:
```
pop_jobs_score = normalize_by_tier(Σ(ring_weight × (job_mix × jobs + pop_mix × population)))
```

**Normalization**: Per tier (all hubs of the same tier normalized together, regardless of metro area)

**Implementation**: the 2050 TAZ population and jobs are pre-allocated to H3 cells (`hubs prepare-base`); at run time the rings are filled from the cells around the hub centroid, each cell weighted by the share of its polygon inside the ring (`influence_cell_rule=fraction`). This is within about 1 % of the polygon overlay; `spatial_source=shapefiles` runs the overlay itself.

**Rationale**:
- Higher-tier hubs serve employment centers
- Local hubs serve residential areas
- Distance decay reflects walk/bike accessibility
- 2050 data captures development potential

### 7.5 Bus Terminal Proximity Score

**What it measures**: Integration with bus network

**Methodology**:

1. **200m radius** around hub center
2. **Terminal Classification**:
   - Weighted by size and function
   - National/Regional terminals weighted highest
   - Local terminals weighted lower
3. **2050 Terminal Strategy**:
   - Based on planned terminal locations

**Formula**:
```
terminal_score = normalize_global(Σ(terminal_weight × proximity_factor))
```

**Normalization**: Per tier (`bus_terminal_Norm`); the raw score is 0–3 by terminal class (חניון לילה 1, מסוף קטן/בינוני 2, מסוף גדול/מתקן משולב 3)

**Implementation**: each H3 cell of the base layer carries the class of the terminal whose 200 m buffer touches it; a hub takes the highest class over its cells, which is identical to buffering the terminals against the hub polygon.

**Rationale**:
- Bus integration critical for first/last mile
- Terminal proximity indicates planned integration
- Larger terminals indicate higher importance

---

## 8. Technical Implementation

### 8.1 Expected Technologies

This framework should be implemented using:

#### Spatial Analysis
- **H3**: Uber's Hexagonal Hierarchical Spatial Index
  - Resolution: 150m hexes for hub identification
  - Aggregation and merging logic

- **Geospatial Libraries**:
  - Python: `geopandas`, `shapely`, `h3-py`
  - R: `sf`, `h3r`
  - PostGIS for database operations

#### Data Processing
- **Pandas** or **Polars**: Tabular data manipulation
- **NumPy**: Numerical operations
- **SciPy**: Statistical functions

#### Scoring & Simulation

**Monte Carlo Method (Default)**:
- 10,000 iterations
- Random weight generation (0–50% per criterion)
- Aggregation across simulations
- Prevents single-criterion dominance

**Normalization**:
- Min-max scaling to 1–10
- Per-category normalization
- Log transformation for skewed distributions

#### Visualization
- **Interactive Maps**:
  - Folium, Leaflet, or Mapbox
  - Layered hub display by hierarchy

- **Dashboards**:
  - Streamlit, Dash, or Shiny
  - Interactive filtering and exploration

#### Version Control & Reproducibility
- **Git**: All code versioned
- **DVC** or similar: Large data file versioning
- **Jupyter/Quarto**: Reproducible analysis notebooks
- **Docker**: Environment containerization

### 8.2 Expected Performance

- **Processing Time**: < 5 minutes for full national analysis
- **Memory**: < 8GB RAM for complete dataset
- **Scalability**: Should handle 500+ potential hubs
- **Reproducibility**: 100% deterministic (with fixed random seed)

---

## 9. Codebase Structure

The production pipeline is the `hubs` command (`src/cli.py` → `src/pipeline/run.py`).
Key files for reference:
- `src/pipeline/run.py` — orchestrator; read this first to see the stage order
- `src/pipeline/scoring.py` — eligibility, tiers, normalisation, Monte Carlo
- `src/pipeline/export.py` — `FINAL_COLUMNS`, the 70-column schema the display page reads
- `docs/DEVIATIONS.md` — every notebook quirk kept behind a flag and every intentional fix
- Branch `legacy/v1-notebooks` holds the Colab notebooks and the earlier code this pipeline replaced (provenance only; not in the working tree)

### Organization

```
HubPrioritizing/
├── README.md, INSTALL.md, CLAUDE.md, LICENSE
├── pyproject.toml               # package metadata, `hubs` console script, pytest config
├── requirements.txt             # runtime deps (mirror of pyproject)
│
├── src/
│   ├── cli.py                   # hubs validate | run | show-config | prepare-base
│   ├── config.py                # thresholds, weights, CRS, column constants, tier labels
│   ├── pipeline/                # the one-command pipeline (pure DataFrame stages)
│   │   ├── settings.py          #   PipelineConfig, YAML / --set overrides
│   │   ├── inputs.py            #   input directory contract, discovery, validation, readers
│   │   ├── report.py            #   RunReport (findings, metrics, inputs)
│   │   ├── network.py           #   nodes x lines -> H3 hexagons -> per-mode line counts
│   │   ├── grouping.py          #   120 m union-find groups, manual merges, stable hub_id
│   │   ├── spatial_tags.py      #   metro ring / district -> area, location (shapefile path)
│   │   ├── demand.py            #   demand workbook -> TotalDemand, TotalTransfers, overrides
│   │   ├── aggregate.py         #   hexagons -> hubs; terminals, pop/jobs rings (shapefile path)
│   │   ├── base_layer.py        #   H3 base layer: prepare-base builder + the run-time lookups
│   │   ├── h3_export.py         #   shareable H3 cell layer (h3_layer.gpkg, hubs export-h3)
│   │   ├── scoring.py           #   categories, mode score, tiers, normalisation, Monte Carlo
│   │   ├── postprocess.py       #   display columns incl. the former Excel formulas
│   │   ├── export.py            #   xlsx (Excel Table) + CSV writers
│   │   └── run.py               #   orchestrator, write_outputs, run_from_cli
│   ├── spatial/                 # h3_operations.py, merging.py (UnionFind)
│   ├── classification/          # hierarchy.py (classify_hub_tier)
│   └── utils/                   # encoding_fix.py, logging.py
│
├── data/reference/              # stable layers + curated tables shipped with the repo
│
├── tests/
│   ├── unit/                    # synthetic tests per stage
│   ├── golden/                  # regression vs the real June 2026 results (fixtures gitignored)
│   ├── synthetic.py, test_smoke.py
│   └── fixtures/real/           # place the real exports + golden workbook here (not committed)
│
├── scripts/                     # compare_base_layer.py (H3 layer vs shapefile overlay)
└── docs/                        # full_documentation/, DEVIATIONS.md, H3_BASE_LAYER.md, DATA_CONFIGURATION.md
```

### Module Responsibilities

#### `src/config.py`
- Constants: thresholds, mode weights, CRS, `MODE_LINE_COLS`, tier labels
- No file paths except `REFERENCE_DATA_DIR`; no side effects on import

#### `src/pipeline/`
- One module per stage, each a pure function (DataFrame in, DataFrame out) recording findings on a `RunReport`
- `settings.py` holds every run-time parameter; `inputs.py` is the only place that resolves files
- Column names follow the canonical notebook so the workbook schema is unchanged
- `base_layer.py` is the default spatial source: `hubs prepare-base` allocates the four polygon layers to H3 cells once (`data/reference/h3_base.parquet`, manifest with source hashes) and the run looks area/ring, terminal class and 2050 population/jobs up by `h3_index`. `spatial_tags.py` and the terminal/TAZ functions of `aggregate.py` are the run-time overlay kept behind `spatial_source=shapefiles`
- `h3_export.py` writes the shareable cell layer (`h3_layer.gpkg`) with base attributes, hub identity, network and scores per cell

#### `src/spatial/`, `src/classification/`
- H3 helpers and union-find proximity grouping; tier rules

#### `src/utils/`
- Hebrew text validation for encoding detection; logger setup (file logging opt-in)

---

## 10. Data Requirements

### 10.1 Required Inputs

#### Transit Network Data
- **Lines**: Route definitions, modes, frequencies
- **Stations**: Locations (lat/lon), names, IDs
- **Forecasts**: 2050 passenger demand by station
- **Plans**: Strategic transport plans, phasing

**Format**: GeoJSON, Shapefile, or CSV with coordinates

#### Demographic Data
- **Population**: 2050 forecasts by small area
- **Employment**: 2050 jobs by small area
- **Land Use**: Zoning, development plans

**Format**: CSV or spatial (polygon/grid)

#### Bus Terminals
- **Locations**: Terminal coordinates
- **Classification**: Type, size, function
- **Strategy**: 2050 terminal network plan

**Format**: GeoJSON or CSV with coordinates

#### Geographic Boundaries
- **Regions**: National regions for scoring
- **Metropolitan Areas**: Core/ring definitions
- **Municipal Boundaries**: For context

**Format**: GeoJSON or Shapefile

#### H3 Base Layer (what a run actually reads)
- The demographic, bus terminal and boundary layers above are pre-allocated once to H3 resolution-10 cells by `hubs prepare-base` → `data/reference/h3_base.parquet` (1.57 M cells, 11 MB) plus a manifest with the source files' SHA-256
- Per cell: `area`, `location` (polygon containing the cell centre), `term_type` / `bus_terminal` (terminal buffered 200 m intersects the cell), `pop_2050` / `emp_2050` (intersection-area share of the TAZ, totals conserved)
- Rebuild only when one of the four source layers changes; the shapefiles are not needed at run time (`spatial_source=shapefiles` restores the run-time overlay)

**Format**: Parquet (zstd, pop/emp float32); see `docs/H3_BASE_LAYER.md`

### 10.2 Data Standards

#### Coordinate System
- **Primary**: WGS84 (EPSG:4326) for storage
- **Processing**: ITM (EPSG:2039) for distances
- Always specify CRS explicitly

#### Naming Conventions
- **Hebrew Names**: Use UTF-8 encoding
- **IDs**: Unique, stable identifiers
- **Stations**: Standardized naming (avoid duplicates)

#### Data Quality
- **Completeness**: No missing critical fields
- **Accuracy**: Coordinates validated
- **Consistency**: Cross-dataset alignment
- **Timeliness**: Data version and date documented

### 10.3 Output Data

#### Hub Database
- Hub ID, name, location (hex center)
- Hierarchy tier
- All criterion scores
- Final aggregated score
- Metadata (modes, lines, ridership)

**Format**: GeoJSON + CSV

#### Spatial Layers
- `h3_layer.gpkg`, written by every run: the hub hexagons and every cell within the outer catchment ring of a scored hub, each with area, ring, terminal class, 2050 population/jobs, hub identity, network, scores and nearest hub (`h3_layer_format`: gpkg / geojson / parquet / csv; `h3_layer_extent`: hubs / influence / all)
- `hubs export-h3`: the whole base layer (every cell of Israel) for GIS or SQL use
- Hub points and dissolved hub polygons (`intermediate/` with `keep_intermediates=true`)

**Format**: GeoPackage (EPSG:2039) by default; GeoJSON for web, GeoParquet or CSV+WKT for SQL

#### Reports
- Summary statistics
- Ranking tables
- Sensitivity analysis results

**Format**: CSV, Excel, PDF

---

## 11. Development Workflows

### 11.1 Standard Development Cycle

```
1. Branch Creation
   └─ `git checkout -b feature/your-feature-name`

2. Development
   ├─ Write code following conventions
   ├─ Add docstrings
   ├─ Write unit tests
   └─ Test locally

3. Testing
   ├─ `pytest tests/`
   ├─ Check coverage
   └─ Validate outputs

4. Documentation
   ├─ Update docstrings
   ├─ Update CLAUDE.md if needed
   └─ Add/update notebooks

5. Commit & Push
   ├─ `git add .`
   ├─ `git commit -m "Clear, descriptive message"`
   └─ `git push -u origin feature/your-feature-name`

6. Pull Request
   └─ Request review, address feedback
```

### 11.2 Testing Standards

#### Unit Tests
- **Coverage**: Aim for >80%
- **Focus**: Each scoring function, data loader, spatial operation
- **Fixtures**: Use pytest fixtures for sample data
- **Assertions**: Test both happy path and edge cases

#### Integration Tests
- **End-to-end**: Run full pipeline on sample data
- **Outputs**: Validate result structure and ranges
- **Reproducibility**: Same input = same output

#### Data Validation
- **Schema Checks**: Required fields present
- **Range Checks**: Values within expected bounds
- **Consistency**: Cross-dataset alignment

### 11.3 Code Review Checklist

- [ ] Code follows style guide (PEP 8 for Python)
- [ ] Docstrings complete and clear
- [ ] Tests added/updated
- [ ] No hardcoded paths or magic numbers
- [ ] Error handling appropriate
- [ ] Logging informative
- [ ] Performance acceptable
- [ ] Documentation updated

### 11.4 Branching Strategy

- **`main`**: Stable, production-ready code
- **`develop`**: Integration branch for features
- **`feature/*`**: New features
- **`bugfix/*`**: Bug fixes
- **`hotfix/*`**: Urgent production fixes
- **`claude/*`**: AI assistant work branches

---

## 12. Key Conventions

### 12.1 Naming Conventions

#### Python Code
- **Modules**: `lowercase_with_underscores.py`
- **Classes**: `CapitalizedWords`
- **Functions**: `lowercase_with_underscores()`
- **Constants**: `UPPER_CASE_WITH_UNDERSCORES`
- **Private**: `_leading_underscore`

#### Variables
- **Hub IDs**: `hub_id` (string, unique)
- **Scores**: `*_score` suffix (e.g., `activity_score`)
- **Normalized**: `*_norm` suffix (e.g., `passengers_norm`)
- **Geometry**: `geom`, `geometry`, `point`, `polygon`

#### Files
- **Data**: `lowercase_descriptive_2024_12_31.csv`
- **Results**: `hubs_scored_YYYY_MM_DD.geojson`
- **Notebooks**: `NN_descriptive_title.ipynb` (NN = order)

### 12.2 Documentation Standards

#### Docstrings (Google Style)
```python
def calculate_activity_score(passengers, hub_type):
    """Calculate normalized activity score for a hub.

    Uses log10 transformation to prevent extreme skew and normalizes
    within hub category to ensure fair comparison.

    Args:
        passengers (int): Daily passenger count (2050 forecast)
        hub_type (str): Hub category ('ארצי', 'מטרופוליני', 'עירוני')

    Returns:
        float: Normalized score between 1 and 10

    Raises:
        ValueError: If passengers < 0 or hub_type invalid

    Example:
        >>> calculate_activity_score(50000, 'ארצי')
        7.8
    """
```

#### Comments
- **Why, not what**: Explain reasoning, not mechanics
- **Hebrew terms**: Include English translation first time
- **Complex logic**: Comment non-obvious algorithms
- **TODOs**: Format as `# TODO(name): description`

### 12.3 Error Handling

```python
# Good: Specific exceptions, informative messages
try:
    hub_data = load_hub_data(hub_id)
except FileNotFoundError:
    logger.error(f"Hub data file not found for {hub_id}")
    raise
except ValueError as e:
    logger.warning(f"Invalid data for hub {hub_id}: {e}")
    return None
```

### 12.4 Logging

```python
import logging

logger = logging.getLogger(__name__)

# Levels
logger.debug("Detailed diagnostic information")
logger.info("General informational messages")
logger.warning("Warning messages for recoverable issues")
logger.error("Error messages for failures")
logger.critical("Critical issues requiring immediate attention")
```

### 12.5 Configuration Management

```python
# config.py
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Thresholds
ELIGIBILITY_MIN_PASSENGERS = 1000
NATIONAL_HUB_MIN_PASSENGERS = 50000
METRO_HUB_MIN_PASSENGERS = 5000

# Scoring
MONTE_CARLO_ITERATIONS = 10000
MAX_CRITERION_WEIGHT = 0.5
SCORE_RANGE = (1, 10)

# Spatial
H3_RESOLUTION = 10  # ~15 m edge hexes
HUB_MERGE_THRESHOLD_M = 120
CATCHMENT_RINGS = [(0, 500), (500, 1000), (1000, 1500)]  # meters
```

Run-time parameters (rings, filter flags, Monte Carlo scope, output names) live in
`src/pipeline/settings.py::PipelineConfig` and are set with `--config pipeline.yaml` or
`--set key=value`; the effective values are written to `run_config.json` with every run.

---

## 13. Design Principles

### 13.1 Hub Planning & Design Guidance

Hubs must support:

1. **Seamless Transfers**
   - Minimize walking distances
   - Clear wayfinding
   - Protected, climate-controlled paths
   - Level changes minimized

2. **Universal Accessibility**
   - Full wheelchair access
   - Visual/audio aids
   - Tactile paving
   - Elevators and ramps

3. **TOD-Ready Integration**
   - Mixed-use development
   - Pedestrian-friendly streetscape
   - Cycling infrastructure
   - Reduced parking requirements

4. **Scalable Capacity**
   - Future expansion planned
   - Modular design
   - Platform/access sizing

5. **High Passenger Experience**
   - Real-time information
   - Amenities (seating, shelter, retail)
   - Safety and security
   - Cleanliness and maintenance

6. **Multimodal Connectivity**
   - Walking and cycling facilities
   - Bus integration (bays, shelters)
   - Micro-mobility (bikes, scooters)
   - Kiss & ride, park & ride (where appropriate)

### 13.2 Code Design Principles

1. **Modularity**: Each function does one thing well
2. **Reusability**: Avoid code duplication
3. **Testability**: Easy to write tests for
4. **Readability**: Clear > clever
5. **Maintainability**: Well-documented, consistent style
6. **Performance**: Efficient algorithms, avoid premature optimization
7. **Robustness**: Handle errors gracefully

---

## 14. AI Assistant Guidelines

### 14.1 Understanding the Domain

As an AI assistant working on this project, you should:

1. **Learn the Terminology**
   - **מתח״מ**: Integrated transport hub (plural: מתח"מים)
   - **ארצי**: National tier
   - **מטרופוליני**: Metropolitan tier
   - **עירוני**: Local/urban tier
   - **TOD**: Transit-Oriented Development
   - **רכבת**: Railway/train
   - **מטרו**: Metro
   - **רק״ל**: Light rail
   - **BRT**: Bus Rapid Transit

2. **Understand the Context**
   - This is Israeli national transport planning
   - Bilingual environment (Hebrew and English)
   - Data from multiple government agencies
   - Long-term planning horizon (2050)
   - High stakes: billions in infrastructure investment

3. **Recognize the Constraints**
   - Political sensitivity (regional equity)
   - Data limitations (forecasts are uncertain)
   - Multiple stakeholders (national, regional, municipal)
   - Iterative process (plans change)

### 14.2 When Reading Code

1. **Check the scoring logic carefully**
   - Normalization ranges (1–10)
   - Per-category normalization
   - Log transformations
   - Weight constraints (0–50%)

2. **Validate spatial operations**
   - Coordinate reference systems
   - Distance calculations (meters, not degrees)
   - Buffer operations
   - H3 hex resolution

3. **Understand the data flow**
   - Raw → Processed → Scored → Aggregated
   - Intermediate outputs saved
   - Reproducibility critical

### 14.3 When Writing Code

1. **Follow the methodology strictly**
   - Don't deviate from scoring formulas
   - Don't change thresholds without justification
   - Document any assumptions

2. **Maintain reproducibility**
   - Set random seeds for Monte Carlo
   - Version data inputs
   - Log all parameters

3. **Handle Hebrew text properly**
   - UTF-8 encoding always
   - Test with actual Hebrew data
   - Don't break RTL display

4. **Validate outputs**
   - Scores in 1–10 range
   - No negative values where inappropriate
   - Totals add up correctly

### 14.4 When Analyzing Results

1. **Sanity checks**
   - Do top-ranked hubs make sense?
   - Are scores distributed reasonably?
   - Do hierarchy assignments match expectations?

2. **Sensitivity analysis**
   - How do results change with different weights?
   - Which criteria drive the ranking?
   - Are there data quality issues?

3. **Documentation**
   - Explain findings clearly
   - Visualize results
   - Highlight uncertainties

### 14.5 Common Pitfalls to Avoid

1. **Don't hardcode values** → Use config.py
2. **Don't ignore edge cases** → Test with extreme values
3. **Don't skip validation** → Always check data quality
4. **Don't forget normalization** → Scores must be comparable
5. **Don't use absolute paths** → Use Path objects, relative paths
6. **Don't commit large data files** → Use .gitignore, DVC
7. **Don't skip tests** → Every function needs tests
8. **Don't leave TODO comments** → Either do it or create an issue

### 14.6 Questions to Ask

Before implementing anything, ask:

1. **Does this match the methodology?**
2. **Is this reproducible?**
3. **How will I test this?**
4. **What edge cases exist?**
5. **Is this the simplest solution?**
6. **Will this scale to 500+ hubs?**
7. **Is this documented clearly?**

### 14.7 Communication Guidelines

When explaining your work:

1. **Be precise**: Use exact terminology
2. **Be bilingual**: Include Hebrew terms with English translations
3. **Be visual**: Show maps, charts, examples
4. **Be transparent**: Explain assumptions and limitations
5. **Be concise**: Prioritize clarity over completeness
6. **Cite sources**: Reference methodology sections

---

## 15. Results Overview (Current State)

June 2026 exports (`All_nodeslines_18062026`, `Lines_and_Planned_Mode_18-06-2026`, `Nodes_w_results_04022026`), reproduced by `hubs run`:

- **1,033 hub groups** formed from 1,244 hexagons (1,319 nodes)
- **142 groups pass eligibility** (≥ 1,000 passengers/day, ≥ 2 modes, a non-rail mode) and are exported:
  - 15 ארצי (National)
  - 67 מטרופוליני (Metropolitan)
  - 33 עירוני (Local)
  - 27 "Not Hub" (eligible but fewer than 3 lines)

The results workbook feeds the display page; `RankByHubTypeMetro` gives the tier-aware rank.

---

## 16. Future Directions

### 16.1 Methodology Enhancements

- Incorporate accessibility indices (transit access for disadvantaged populations)
- Add resilience/redundancy scoring (network robustness)
- Include environmental impact (emissions reduction potential)
- Add cost-benefit analysis integration

### 16.2 Data Improvements

- Real-time ridership data (when available)
- Detailed transfer time matrices
- User experience surveys
- Development pipeline data (planned projects)

### 16.3 Tool Enhancements

- Web-based dashboard for stakeholder access
- Scenario comparison tools
- Automated report generation
- API for external integration

---

## 17. References & Sources

### Academic & Technical
- National transport guidelines (Israel)
- OECD/EU interchange studies
- European station typologies
- Academic research on hub classification and TOD

### Planning Documents
- Israeli strategic transport plans
- Metropolitan transport authority plans
- Municipal master plans
- 2050 demand forecasts

### Technical Standards
- H3 spatial indexing documentation
- GIS standards and best practices
- Transport modeling guidelines

---

## 18. Code Quality

The pipeline is a chain of pure DataFrame stages under `src/pipeline/`, each recording its findings on a `RunReport`; every human correction is a data file under `data/reference/`; no stage reads or writes files itself; the golden tests in `tests/golden/` guard the June 2026 results. Keep it that way: a new criterion or data source is a new stage plus its unit test, not a change to the orchestrator's contract.

---

## 19. Document Maintenance

### Version History
- **v2.1** (2026-09-17): H3 base layer
  - The four reference shapefiles are pre-allocated once to H3 cells (`hubs prepare-base` → `data/reference/h3_base.parquet`); `hubs run` reads that table by default (`spatial_source=h3_base`) and never opens a shapefile
  - Population/jobs rings filled from cells with the `fraction` rule (within ~1 % of the overlay); terminals and tiers identical; ring tags of boundary hexagons follow the cell centre instead of shapefile order (4 hubs)
  - Every run writes `h3_layer.gpkg`; `hubs export-h3` shares the whole base layer
  - `hubs validate` requires the shapefiles only to rebuild the layer or with `spatial_source=shapefiles`
  - Node identity made explicit: one position per node (`check_node_positions`, `node_position_overrides.csv`), the demand model recorded per node, possible node-id collisions between models reported, optional `model` column on the manual tables
- **v2.0** (2026-09-16): One-command pipeline
  - `hubs run --input-dir … --output-dir …` replaces the Colab notebooks and the two Excel formulas
  - Notebook logic ported into `src/pipeline/` with golden tests against the June 2026 workbook
  - Documented that all five criteria are normalised per tier and Monte Carlo runs per hub type
  - Reference data moved to `data/reference/`; hardcoded demand overrides became data
  - Corrected quick-reference values (H3 resolution 10, 120 m merge, 500/1000/1500 m rings)
- **v1.3** (2025-12-29): Clarified scoring methodology documentation
  - Documented that normalization is per TIER only (not per metro+tier)
  - Documented that Monte Carlo runs on ALL hubs together
  - Added ranking step clarification (National: global, Metropolitan/Local: per area)
  - Updated scoring criteria formulas to show normalization method
- **v1.2** (2025-12-17): Updated SOLID review status and progress tracking
- **v1.1** (2025-12-13): Added SOLID principles review section
- **v1.0** (2024-12-30): Initial creation based on framework documentation

### Update Process
This document should be updated when:
- Methodology changes
- New data sources added
- Code structure evolves
- New findings emerge
- Thresholds or parameters adjusted
- Architecture patterns change

### Maintainers
- Project leads responsible for methodology
- Technical team responsible for implementation
- AI assistants should suggest updates via PR

---

## 20. Quick Reference

### Key Thresholds
- **Hub eligibility**: ≥1,000 passengers/day + ≥2 mass-transit modes
- **National tier**: ≥50,000 passengers/day
- **Metropolitan tier**: 5,000–50,000 passengers/day
- **Local tier**: <5,000 passengers/day

### Key Parameters
- **H3 resolution**: 10 (~15 m edge hexagons)
- **Hub merge distance**: 120 m edge-to-edge
- **Monte Carlo iterations**: 10,000, seed 42, per hub type
- **Max criterion weight**: 50% (on the raw draw)
- **Score range**: 1–10 (normalized per tier)
- **Catchment rings**: 0–500, 500–1000, 1000–1500 meters (configurable: `influence_rings`)
- **Bus terminal buffer**: 200 m (baked into the base layer)
- **Spatial source**: `h3_base` (pre-allocated cells, `influence_cell_rule=fraction`); `shapefiles` = legacy overlay. A source shapefile whose hash differs from the layer's manifest stops the run (`on_stale_base_layer=error`): rerun `hubs prepare-base`
- **Node identity**: node ID + location (the hexagon's area selects the demand model; recorded per node as `demand_models`); one position per node, spreads ≤ `node_position_tolerance_m` (150 m) snapped, larger ones reported and fixed in `node_position_overrides.csv`
- **Cell layer output**: `h3_layer.gpkg`, hub + catchment cells (`h3_layer_format`, `h3_layer_extent`)

### Key Commands
```bash
hubs validate --input-dir DIR            # check inputs
hubs run --input-dir DIR --output-dir OUT
hubs show-config --defaults              # every parameter as YAML
hubs prepare-base                        # rebuild data/reference/h3_base.parquet after a reference shapefile changes
hubs export-h3 --out cells.gpkg          # the H3 base layer (every cell, all attributes) for GIS / SQL; see docs/H3_BASE_LAYER.md
pytest                                    # unit + smoke tests
```

### Key Files
- `src/pipeline/run.py`: stage order
- `src/pipeline/base_layer.py`: the H3 base layer (builder + run-time lookups)
- `src/pipeline/scoring.py`: tiers, normalisation, Monte Carlo
- `src/pipeline/export.py`: the 70-column workbook schema
- `src/pipeline/h3_export.py`: the shareable cell layer
- `src/config.py`: thresholds and weights
- `data/reference/README.md`: reference layers and curated tables
- `docs/H3_BASE_LAYER.md`: how the base layer is built, validated against the overlay, and shared
- `docs/DEVIATIONS.md`: flags and fixes

---

## 21. Contact & Support

For questions about:
- **Methodology**: Refer to original planning documents
- **Code**: Check inline documentation and tests
- **Data**: See data dictionary in `docs/`
- **Issues**: Use GitHub issue tracker

---

**Last Updated**: 2026-09-17
**Document Version**: 2.1
**Status**: One-command pipeline on the H3 base layer
