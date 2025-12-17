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
18. [Code Quality & Architecture](#18-code-quality--architecture)
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

Two complementary methods are available:

**Option A: Monte Carlo Simulation (Default)**
- 10,000 iterations with random weight sets
- Each criterion 0–50% per iteration
- Final score = weighted mean across simulations
- Prevents single-criterion dominance
- Robust to weighting uncertainty

**Option B: AHP (Analytic Hierarchy Process)**
- Expert-driven pairwise comparisons
- Systematic weight derivation via eigenvector method
- Built-in consistency checking (CR < 0.10)
- Multiple expert aggregation (geometric mean)
- Transparent, reproducible weighting

**Usage**: Both methods can run simultaneously for comparative analysis. AHP is optional and disabled by default.

#### Step 8: Validation
- Expert review
- Sensitivity analysis
- Method comparison (Monte Carlo vs AHP)
- Update with new data/plans

---

## 7. Scoring Criteria

Each hub receives a **normalized score (1–10)** for each criterion. Final weights are derived through either:
- **Monte Carlo weighted scoring** (default): Random weight simulation to prevent single-criterion dominance
- **AHP (Analytic Hierarchy Process)**: Expert-driven pairwise comparisons for systematic weight derivation

Both methods can be used simultaneously for comparative analysis.

### 7.1 Passenger Activity Score

**What it measures**: 2050 forecast demand

**Methodology**:
- Based on 2050 passenger forecasts
- **Log₁₀ transformation** to avoid extreme skew from mega-stations
- Separate normalization per hub category (ארצי/מטרופוליני/עירוני)

**Formula**:
```
activity_score = normalize(log10(passengers_2050))
```

**Rationale**:
- A station with 100,000 passengers should not score 10× higher than 10,000
- Logarithmic scale reflects diminishing marginal impact
- Per-category normalization ensures fair comparison within tier

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
service_score = Σ(mode_weight × line_count_with_diminishing_returns) × diversity_bonus
normalized to 1–10 per hub type
```

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
location_score = region_weight × ring_score
normalized to 1–10
```

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
pop_jobs_score = Σ(ring_weight × (job_mix × jobs + pop_mix × population))
normalized to 1–10 per hub type
```

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
terminal_score = Σ(terminal_weight × proximity_factor)
normalized to 1–10
```

**Rationale**:
- Bus integration critical for first/last mile
- Terminal proximity indicates planned integration
- Larger terminals indicate higher importance

### 7.6 AHP Scoring Methodology (Optional)

**What it is**: Analytic Hierarchy Process - expert-driven alternative to Monte Carlo

**How it works**:

1. **Expert Pairwise Comparisons**
   - Domain experts compare criteria two at a time
   - Use Saaty scale (1-9): 1=Equal, 3=Moderate, 5=Strong, 7=Very Strong, 9=Extreme
   - Example: "Is passenger activity more important than location?" → Answer: 5 (Strong)

2. **Priority Weight Calculation**
   - Construct pairwise comparison matrix from expert input
   - Calculate weights using principal eigenvector method
   - Normalize weights to sum to 1.0

3. **Consistency Validation**
   - Calculate Consistency Ratio (CR) for each expert
   - CR < 0.10 indicates acceptable logical consistency
   - High CR (≥0.10) flags contradictory judgments

4. **Multi-Expert Aggregation**
   - Combine multiple expert opinions using geometric mean
   - Alternative methods: arithmetic mean, median
   - Produces single set of aggregated weights

5. **AHP Score Calculation**
   - Apply aggregated weights to normalized criterion scores
   - Calculate final AHP score per hub
   - Compare with Monte Carlo results for validation

**Saaty Scale Reference**:
```
1 = Equal importance
3 = Moderate importance
5 = Strong importance
7 = Very strong importance
9 = Extreme importance
(2, 4, 6, 8 are intermediate values)
```

**When to use AHP**:
- ✅ Expert knowledge should drive weighting
- ✅ Stakeholder transparency is critical
- ✅ Systematic, reproducible weights are needed
- ✅ Validation against Monte Carlo is desired

**When to use Monte Carlo**:
- ✅ Expert consensus is difficult
- ✅ Robustness to weighting is priority
- ✅ Sensitivity analysis is needed
- ✅ Avoiding single-weight bias is important

**Best Practice**: Run both methods and compare. Agreement indicates robust results; disagreement highlights weight-sensitive hubs.

**Configuration**:
```python
# In src/config.py
AHP_ENABLED = True  # Set to True to enable
AHP_CONSISTENCY_RATIO_THRESHOLD = 0.10  # Saaty's recommendation
AHP_AGGREGATION_METHOD = 'geometric_mean'  # Recommended
AHP_EXPERT_CSV_PATH = DATA_DIR / "ahp_expert_comparisons.csv"
```

**Output**: When AHP is enabled, hubs receive both:
- `final_score`: Monte Carlo aggregated score
- `ahp_score`: AHP weighted score
- `rank`: Monte Carlo ranking
- `ahp_rank`: AHP ranking

**Documentation**: See `docs/AHP_SCORING_GUIDE.md` and `AHP_QUICKSTART.md` for full details.

**References**:
- Saaty, T.L. (1980). The Analytic Hierarchy Process. McGraw-Hill.
- Saaty, T.L. (2008). Decision making with the analytic hierarchy process. IJSSCI 1(1), 83-98.

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

**AHP Method (Optional)**:
- Expert pairwise comparison matrix
- Eigenvector weight calculation
- Consistency ratio validation (CR < 0.10)
- Multi-expert aggregation (geometric mean)
- Transparent, systematic weighting

**Normalization**:
- Min-max scaling to 1–10
- Per-category normalization
- Log transformation for skewed distributions

**Comparison Tools**:
- Correlation analysis between methods
- Rank overlap assessment
- Disagreement identification

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
Key files for reference:
@src/COMPLETE_TRANSIT_PIPELINE.ipynb - complete the first 3 parts of the project in a pipeline, needs to be reviewed
@src/HubsCode_to_1_file.ipynb - older version of most of the steps in the project
@src/Create_h3_from_all_nodes.ipynb - the first step in the project
@src/Group_n_Filter_Hubs.ipynb - how the grouping and the filtering of the transit hubs was made before

### Recommended Organization

```
HubPrioritizing/
├── README.md                    # Project overview
├── CLAUDE.md                    # This file
├── .gitignore
├── requirements.txt             # Python dependencies
├── environment.yml              # Conda environment (optional)
├── Dockerfile                   # Container definition
│
├── data/                        # Data files (not in git)
│   ├── raw/                     # Original source data
│   │   ├── transit_lines/
│   │   ├── stations/
│   │   ├── forecasts_2050/
│   │   ├── demographics/
│   │   └── terminals/
│   ├── processed/               # Cleaned, standardized data
│   └── results/                 # Output files
│
├── src/                         # Source code
│   ├── __init__.py
│   ├── config.py                # Configuration and constants
│   ├── data/                    # Data loading and processing
│   │   ├── __init__.py
│   │   ├── loaders.py           # Data import functions
│   │   ├── validators.py        # Data quality checks
│   │   └── reconciliation.py   # Cross-dataset alignment
│   ├── spatial/                 # Spatial operations
│   │   ├── __init__.py
│   │   ├── h3_operations.py     # H3 hex aggregation
│   │   ├── merging.py           # Adjacent hex merging
│   │   └── geometry.py          # Geometric calculations
│   ├── classification/          # Hub classification
│   │   ├── __init__.py
│   │   ├── eligibility.py       # Filtering logic
│   │   └── hierarchy.py         # Tier assignment
│   ├── scoring/                 # Scoring algorithms
│   │   ├── __init__.py
│   │   ├── activity.py          # Passenger activity score
│   │   ├── service.py           # Service & modes score
│   │   ├── location.py          # Geographic score
│   │   ├── demographics.py      # Population & jobs score
│   │   ├── terminals.py         # Bus terminal score
│   │   ├── normalization.py     # Scoring normalization
│   │   ├── monte_carlo.py       # Weight simulation & aggregation
│   │   └── ahp.py               # AHP expert-driven weighting (optional)
│   ├── visualization/           # Visualization components
│   │   ├── __init__.py
│   │   ├── maps.py              # Interactive maps
│   │   └── charts.py            # Statistical plots
│   └── utils/                   # Utility functions
│       ├── __init__.py
│       ├── logging.py
│       └── constants.py
│
├── notebooks/                   # Analysis notebooks
│   ├── 01_data_exploration.ipynb
│   ├── 02_hub_identification.ipynb
│   ├── 03_scoring_analysis.ipynb
│   ├── 04_sensitivity_analysis.ipynb
│   └── 05_results_visualization.ipynb
│
├── tests/                       # Unit tests
│   ├── __init__.py
│   ├── test_data_loaders.py
│   ├── test_spatial.py
│   ├── test_scoring.py
│   └── test_classification.py
│
├── docs/                        # Documentation
│   ├── methodology.md
│   ├── data_dictionary.md
│   ├── api_reference.md
│   ├── user_guide.md
│   └── AHP_SCORING_GUIDE.md     # AHP methodology guide
│
├── AHP_QUICKSTART.md            # AHP quick-start guide
│
├── scripts/                     # Execution scripts
│   ├── run_pipeline.py          # Main workflow
│   ├── update_data.py           # Data refresh
│   ├── export_results.py        # Output generation
│   └── test_ahp_scoring.py      # AHP scoring test suite
│
├── data/                        # Data files
│   ├── ahp_expert_comparisons_TEMPLATE.csv  # Blank AHP template
│   ├── ahp_expert_comparisons_example.csv   # Example with 3 experts
│   └── ahp_expert_comparisons.csv           # Actual expert input (user-provided)
│
└── app/                         # Web application (optional)
    ├── app.py                   # Main app file
    ├── components/              # UI components
    └── assets/                  # Static assets
```

### Module Responsibilities

#### `src/config.py`
- Constants (thresholds, weights, parameters)
- File paths
- Configuration management

#### `src/data/`
- Load raw data from various sources
- Validate data quality and completeness
- Reconcile conflicts between datasets
- Standardize formats

#### `src/spatial/`
- H3 hex operations (creation, aggregation)
- Merge adjacent hexes into hub areas
- Calculate distances and buffers
- Geometric operations

#### `src/classification/`
- Apply eligibility filters
- Assign hierarchy tier
- Handle edge cases

#### `src/scoring/`
- Implement each scoring criterion (activity, service, location, demographics, terminals)
- Normalize scores to 1–10 scale
- **Monte Carlo**: Random weight simulation (10,000 iterations)
- **AHP**: Expert pairwise comparisons, eigenvector weights, consistency checking
- Aggregate final scores using selected method(s)
- Compare Monte Carlo vs AHP results

#### `src/visualization/`
- Generate interactive maps
- Create statistical charts
- Export visualizations

#### `src/utils/`
- Logging and debugging
- Common utilities
- Constants and enums

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
- Hub points (colored by tier)
- Hub areas (hexes)
- Service area buffers
- Network connections

**Format**: GeoJSON for web, Shapefile for GIS

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
H3_RESOLUTION = 9  # ~150m hexes
HUB_MERGE_THRESHOLD_M = 300
CATCHMENT_RINGS = [0, 400, 800, 1500]  # meters
```

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

Based on the initial methodology application:

- **155 potential hubs identified**
- **69 filtered out** (demand <1,000 or single-mode)
- **86 hubs fully evaluated**:
  - 15 ארצי (National)
  - 29 מטרופוליני - TA+Center
  - 14 מטרופוליני - Haifa+North
  - 3 מטרופוליני - South
  - עירוני (Local) as defined in dataset

Full spatial visualization should be available via interactive interface.

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

## 18. Code Quality & Architecture

### SOLID Principles Review

The codebase has been comprehensively reviewed for adherence to SOLID design principles. See [docs/SOLID_PRINCIPLES_REVIEW.md](docs/SOLID_PRINCIPLES_REVIEW.md) and [docs/EXECUTIVE_SUMMARY.md](docs/EXECUTIVE_SUMMARY.md) for detailed findings.

**Overall Assessment: VERY GOOD (Grade: A-)**
**Last Review: 2025-12-17**

#### Strengths
- ✅ **Single Responsibility Principle** - Excellent (Grade: A)
  - Clear module boundaries
  - Focused functions
  - Strong separation of concerns
  - New modules maintain excellent SRP (AHP, MC distribution)

- ✅ **Interface Segregation Principle** - Good (Grade: A-)
  - Minimal function parameters
  - No "god functions"
  - Separation of data and configuration

- ✅ **Recent Architectural Improvements** (2025-12-17)
  - AHP scoring module for expert-driven weighting
  - Monte Carlo distribution analysis for robustness metrics
  - Enhanced configuration integration

#### Improvement Opportunities
- ⚠️ **Open/Closed Principle** - Partial (Grade: B-)
  - Currently requires code changes to add new scoring criteria
  - Recommended: Implement Strategy Pattern with scorer registry

- ⚠️ **Dependency Inversion Principle** - Needs Work (Grade: C+)
  - Direct dependencies on concrete implementations
  - Recommended: Use Protocol classes and dependency injection

#### Implementation Recommendations

**COMPLETED (✅):**
- AHP Scoring Module - Alternative expert-driven methodology
- Monte Carlo Distribution Analysis - Robustness and uncertainty metrics
- Configuration Integration - Enhanced config.py usage

**HIGH PRIORITY (⚠️):**
1. **Strategy Pattern for Scoring** - Enable adding new scorers without modifying existing code
2. **Abstract Interfaces** - Use Protocol classes for loose coupling

**MEDIUM PRIORITY (🔲):**
3. **Configuration-Driven Pipeline** - Make pipeline behavior configurable (partial implementation)
4. **Dependency Injection** - Improve testability and flexibility

**Progress:** ~25% of recommendations implemented

See the full review documents for detailed code examples and implementation guidance.

---

## 19. Document Maintenance

### Version History
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
- **H3 resolution**: 9 (~150m hexes)
- **Monte Carlo iterations**: 10,000
- **Max criterion weight**: 50%
- **Score range**: 1–10 (normalized)
- **Catchment rings**: 0, 400, 800, 1500 meters

### Key Files (Expected)
- `src/scoring/monte_carlo.py`: Final scoring logic
- `src/spatial/h3_operations.py`: Hub identification
- `src/config.py`: All parameters and thresholds
- `notebooks/03_scoring_analysis.ipynb`: Scoring exploration

---

## 21. Contact & Support

For questions about:
- **Methodology**: Refer to original planning documents
- **Code**: Check inline documentation and tests
- **Data**: See data dictionary in `docs/`
- **Issues**: Use GitHub issue tracker
- **Code Quality**: See SOLID review in `docs/SOLID_PRINCIPLES_REVIEW.md`

---

**Last Updated**: 2025-12-17
**Document Version**: 1.2
**Status**: Framework with Updated Architecture Review
