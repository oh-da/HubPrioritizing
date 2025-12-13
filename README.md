# Hub Prioritization Framework
**Centralized Logic for Assessing, Understanding & Determining Evaluation**

A systematic framework for identifying, classifying, and prioritizing integrated transport hubs (מתח"מים) in Israel.

---

## Overview

This framework implements a comprehensive methodology for evaluating multi-modal transit hubs based on:
- **Passenger activity** (2050 forecasts)
- **Service quality** (modes and frequencies)
- **Strategic location** (national and metropolitan importance)
- **Development potential** (population and employment catchment)
- **Bus network integration** (terminal proximity)

Results are aggregated using **Monte Carlo simulation** to ensure no single criterion dominates the final score.

---

## Quick Start

### Installation

**Option 1: Automatic (Recommended)**
```bash
# Just run the pipeline - it will check and install dependencies
python scripts/run_complete_pipeline.py
# When prompted, type 'y' to install missing packages
```

**Option 2: Install Script**
```bash
python scripts/install_dependencies.py
```

**Option 3: Manual**
```bash
pip install -r requirements.txt
```

See **INSTALL.md** for detailed installation instructions and troubleshooting.

### Basic Usage

```python
from scripts.run_pipeline import HubPrioritizationPipeline

# Initialize pipeline
pipeline = HubPrioritizationPipeline()

# Run complete analysis
results = pipeline.run_complete_pipeline(
    nodes_csv="data/raw/All_nodes+lines.csv",
    lines_modes_csv="data/raw/Lines_and_Planned_Mode.csv"
)

# View top hubs
print(results.nlargest(10, 'final_score'))
```

### Command Line

```bash
# Edit file paths in scripts/run_pipeline.py, then run:
python scripts/run_pipeline.py
```

---

## Project Structure

```
HubPrioritizing/
├── src/                          # Source code
│   ├── config.py                 # Configuration and constants
│   ├── utils/                    # Utilities (logging, constants)
│   ├── data/                     # Data loading and validation
│   ├── spatial/                  # H3 operations and merging
│   ├── classification/           # Eligibility and hierarchy
│   ├── scoring/                  # All 5 scoring criteria + Monte Carlo
│   └── visualization/            # Maps and charts
│
├── scripts/                      # Execution scripts
│   └── run_pipeline.py           # Main pipeline runner
│
├── data/                         # Data files (not in git)
│   ├── raw/                      # Input data
│   ├── processed/                # Intermediate results
│   └── results/                  # Final outputs
│
├── tests/                        # Unit tests
├── notebooks/                    # Analysis notebooks
├── docs/                         # Documentation
│
├── requirements.txt              # Python dependencies
├── CLAUDE.md                     # Full framework specification
└── README.md                     # This file
```

---

## Methodology

### Pipeline Steps

1. **Load Transit Data**: Import nodes, lines, and modes
2. **Create H3 Hexagons**: Assign hexagonal spatial indices (~15m resolution)
3. **Group Hexagons**: Merge nearby hexagons (120m threshold) into hub areas
4. **Filter Eligibility**: Keep hubs with ≥1,000 passengers/day and ≥2 mass-transit modes
5. **Classify Hierarchy**: Assign tiers (ארצי/מטרופוליני/עירוני) based on ridership
6. **Calculate Scores**: Compute 5 scoring criteria normalized to 1-10 scale
7. **Aggregate Scores**: Monte Carlo simulation (10,000 iterations) for final ranking

### Hub Hierarchy

| Tier | Hebrew | Ridership | Description |
|------|--------|-----------|-------------|
| **National** | ארצי | ≥50,000/day | Top-tier hubs connecting metropolitan regions |
| **Metropolitan** | מטרופוליני | 5,000-50,000/day | Mid-level nodes linking trunk lines to feeders |
| **Local** | עירוני | <5,000/day | Neighborhood gateways to the transit network |

### Scoring Criteria

1. **Passenger Activity** (log₁₀ normalized per tier)
2. **Service & Modes** (weighted by mode quality + diversity bonus)
3. **Location** (region weight × metro position)
4. **Population & Jobs** (2050 catchment with distance decay)
5. **Bus Terminal Proximity** (200m buffer, weighted by terminal type)

**Final Score**: Monte Carlo aggregation ensures balanced weighting (no criterion >50%)

---

## Configuration

All parameters are centralized in `src/config.py`:

```python
# Key thresholds
ELIGIBILITY_MIN_PASSENGERS = 1000  # Minimum daily passengers
ELIGIBILITY_MIN_MODES = 2          # Minimum mass-transit modes

# Hierarchy thresholds
NATIONAL_HUB_MIN_PASSENGERS = 50000
METRO_HUB_MIN_PASSENGERS = 5000

# Spatial parameters
H3_RESOLUTION = 10                  # ~15m hexagons
HUB_MERGE_THRESHOLD_M = 120        # Edge-to-edge grouping distance

# Scoring
MONTE_CARLO_ITERATIONS = 10000      # Simulation iterations
MAX_CRITERION_WEIGHT = 0.5          # Max weight per criterion (50%)
```

---

## Data Requirements

### Input Files

1. **Transit Nodes** (`All_nodes+lines.csv`)
   - Columns: `node`, `LINE_ID`, `X`, `Y` (or `geometry`)
   - Format: CSV with Israel TM Grid coordinates (EPSG:2039)

2. **Lines and Modes** (`Lines_and_Planned_Mode.csv`)
   - Columns: `Line_ModelName`, `Mode_Planned`, `Area`
   - Maps transit lines to their planned mode

3. **Demand Data** (optional, Excel file)
   - 2050 passenger forecasts by station
   - Sheets for each regional model (Haifa, TelAviv, Jerusalem, etc.)

4. **Spatial Layers** (optional shapefiles)
   - Metro areas
   - Administrative districts
   - TAZ zones with POP_2050 and EMPL_2050
   - Bus terminals

### Output Files

- `hub_prioritization_results_{timestamp}.csv` - Full results with all scores
- `hub_prioritization_results_{timestamp}.geojson` - Spatial data for mapping
- `hub_map_{timestamp}.html` - Interactive web map

---

## Examples

### Run Specific Steps

```python
from scripts.run_pipeline import HubPrioritizationPipeline

pipeline = HubPrioritizationPipeline()

# Run individual steps
pipeline.step_1_load_transit_data(nodes_csv, lines_csv)
pipeline.step_2_create_h3_hexagons()
pipeline.step_3_group_hexagons()
# ... continue as needed

# Access intermediate results
hubs = pipeline.grouped_hubs
```

### Custom Scoring

```python
from src.scoring import monte_carlo

# Calculate all scores
scored_hubs = monte_carlo.run_complete_scoring_pipeline(
    hubs_gdf,
    tier_column='tier'
)

# View top 20
top_20 = scored_hubs.nlargest(20, 'final_score')
print(top_20[['group', 'tier', 'final_score', 'rank']])
```

### Visualization

```python
from src.visualization import maps

# Create interactive map
maps.create_hub_map(
    scored_hubs,
    color_by='final_score',
    output_file='results/my_map.html'
)
```

---

## Testing

```bash
# Run all tests
pytest tests/

# With coverage
pytest tests/ --cov=src --cov-report=html
```

---

## Code Quality

This codebase has been reviewed for adherence to SOLID design principles and software engineering best practices. See [docs/EXECUTIVE_SUMMARY.md](docs/EXECUTIVE_SUMMARY.md) for the complete assessment.

### Key Strengths
- ✅ **Excellent module organization** - Clear separation of concerns
- ✅ **Well-documented methodology** - Comprehensive technical documentation
- ✅ **Centralized configuration** - All parameters in one place
- ✅ **Strong data validation** - Early error detection

### Architecture Highlights
- **Single Responsibility**: Each module has one clear purpose
- **Functional Design**: Composable, testable functions
- **Configuration-Driven**: Behavior controlled by `config.py`
- **Reproducible**: Fixed random seeds, version-controlled parameters

### Overall Assessment: **GOOD (Grade: B+)**

The framework demonstrates strong engineering practices and is production-ready. See the [SOLID review](docs/SOLID_PRINCIPLES_REVIEW.md) for detailed recommendations to enhance extensibility and testability

---

## Documentation

### Primary Documentation

- **[CLAUDE.md](CLAUDE.md)** - Complete framework specification and methodology
  - Domain context (What is a מתח"מ?)
  - Hub hierarchy definitions
  - Detailed scoring methodology
  - Data requirements
  - Development guidelines
  - AI assistant instructions

- **[INSTALL.md](INSTALL.md)** - Installation guide and troubleshooting
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Quick reference for common tasks

### Code Quality & Architecture

- **[docs/EXECUTIVE_SUMMARY.md](docs/EXECUTIVE_SUMMARY.md)** - Code quality review executive summary
  - Overall assessment and scorecard
  - Key findings and recommendations
  - Implementation roadmap
  - Business impact analysis

- **[docs/SOLID_PRINCIPLES_REVIEW.md](docs/SOLID_PRINCIPLES_REVIEW.md)** - Detailed SOLID principles review
  - Comprehensive analysis of each principle
  - Code examples and recommendations
  - Testing strategies
  - Implementation guidelines

### Additional Documentation

- **[docs/DATA_CONFIGURATION.md](docs/DATA_CONFIGURATION.md)** - Data file configuration guide
- **[data/README_MANUAL_DEMAND_UPDATES.md](data/README_MANUAL_DEMAND_UPDATES.md)** - Demand data update procedures
- **[data/README_MODE_LINE_COLUMNS.md](data/README_MODE_LINE_COLUMNS.md)** - Mode and line column descriptions

---

## Contributing

This is a planning framework for Israeli transport infrastructure. For questions or contributions, please refer to the project documentation.

---

## License

See project documentation for license information.

---

## Contact

For technical questions about the framework, see CLAUDE.md or project documentation.
