# Hub Prioritization Framework - Final Deliverables Summary

**Complete Multi-Criteria Decision Analysis System for Israeli Transit Hubs**

---

## Project Overview

This framework provides a comprehensive, production-ready system for identifying, classifying, scoring, and prioritizing integrated transport hubs (מתח"מים) across Israel. The system combines spatial analysis, multi-criteria decision making, and interactive visualization tools.

---

## Core Components

### 1. Scoring Pipeline

**Location:** `src/scoring/`

| Module | Description |
|--------|-------------|
| `activity.py` | Passenger activity scoring (log-transformed 2050 forecasts) |
| `service.py` | Service & modes scoring (mode weights + diversity bonus) |
| `location.py` | Location scoring (region + metro position weights) |
| `demographics.py` | Population & jobs scoring (ring-weighted catchment) |
| `terminals.py` | Bus terminal proximity scoring (200m threshold) |
| `monte_carlo.py` | Monte Carlo aggregation (10,000 iterations, 0-50% weights) |
| `ahp.py` | AHP expert-driven weighting (optional, runs alongside Monte Carlo) |
| `normalization.py` | Score normalization to 1-10 scale |

### 2. Spatial Processing

**Location:** `src/spatial/`

| Module | Description |
|--------|-------------|
| `h3_operations.py` | H3 hexagon creation and aggregation |
| `merging.py` | Hub area grouping (120m edge-to-edge) |
| `geometry.py` | Geometric calculations and buffer operations |

### 3. Classification

**Location:** `src/classification/`

| Module | Description |
|--------|-------------|
| `eligibility.py` | Hub eligibility filtering (>=1,000 passengers, >=2 modes) |
| `hierarchy.py` | Tier assignment (National/Metropolitan/Local) |

---

## Interactive Applications

### AHP Expert Questionnaire (Streamlit App)

**Location:** `app/ahp_questionnaire.py`

A professional web application for collecting expert pairwise comparisons:

- Interactive slider-based comparisons
- Real-time weight calculation and visualization
- Consistency ratio validation (CR < 0.10)
- CSV export for pipeline integration
- Bilingual support (English/Hebrew)

**Run with:**
```bash
streamlit run app/ahp_questionnaire.py
```

---

## Analysis Notebooks

### Primary Pipeline Notebooks

| Notebook | Description |
|----------|-------------|
| `notebooks/complete_hub_scoring_pipeline.ipynb` | End-to-end scoring pipeline |
| `notebooks/hub_data_postprocess.ipynb` | Post-processing with name mapping and ranking tables |
| `notebooks/map_hub_results.ipynb` | Interactive map visualization |

### AHP & Expert Analysis

| Notebook | Description |
|----------|-------------|
| `notebooks/ahp_expert_questionnaire.ipynb` | AHP questionnaire in notebook format |

### Legacy/Reference Notebooks

| Notebook | Description |
|----------|-------------|
| `src/COMPLETE_TRANSIT_PIPELINE.ipynb` | Combined H3 + demand processing |
| `notebooks/HubsScoring_vAugust2025.ipynb` | Hub scoring reference implementation |
| `notebooks/Group_n_Filter_Hubs.ipynb` | Hub grouping and filtering logic |

---

## Scoring Methodology

### Five Scoring Criteria

1. **Passenger Activity** - 2050 demand forecasts (log-transformed)
2. **Service & Modes** - Transit service quality with diversity bonus
3. **Location** - Strategic geographic importance
4. **Population & Jobs** - Catchment area potential (tier-specific mix)
5. **Bus Terminal Proximity** - Network integration

### Aggregation Methods

#### Monte Carlo Simulation (Default)
- 10,000 iterations with random weights (0-50% per criterion)
- Prevents single-criterion dominance
- Robust to weighting uncertainty

#### AHP (Analytic Hierarchy Process) - Optional
- Expert pairwise comparisons using Saaty scale (1-9)
- Eigenvector weight calculation
- Consistency ratio validation
- Multiple expert aggregation (geometric mean)

**Both methods produce:**
- `final_score` / `ahp_score` - Weighted aggregate score
- `rank` / `ahp_rank` - Hub ranking within tier
- Distribution metrics for robustness analysis

---

## Hub Hierarchy

| Tier | Hebrew | Daily Ridership | Description |
|------|--------|-----------------|-------------|
| National | ארצי | >= 50,000 | Top-tier metropolitan connectors |
| Metropolitan | מטרופוליני | 5,000 - 50,000 | Regional transit nodes |
| Local | עירוני | < 5,000 | Neighborhood gateways |

**Metropolitan Areas:**
- Tel Aviv + Center (29 hubs)
- Haifa + North (14 hubs)
- South (3 hubs)

---

## Output Files

### Scoring Results

| File | Description |
|------|-------------|
| `data/results/hub_prioritization_results_{timestamp}.csv` | Full results with all scores |
| `data/results/hub_prioritization_results_{timestamp}.geojson` | Spatial data for mapping |
| `data/results/hub_map_{timestamp}.html` | Interactive web map |

### AHP Outputs

| File | Description |
|------|-------------|
| `data/ahp_expert_comparisons.csv` | Expert pairwise comparison input |
| `data/ahp_weights_{expert}_{timestamp}.csv` | Calculated expert weights |

---

## Key Features

### Recent Additions (2024-2025)

- **AHP Streamlit App** - Professional UI for expert questionnaires
- **Monte Carlo Distribution Reporting** - Rank robustness metrics
- **Tier-Specific Ranking** - Rankings per hub type and area
- **Hub Data Post-Processing** - Name mapping and ranking tables
- **Transit Hub Classification** - Optional non-rail mode requirements
- **Executive Summary Documentation** - Comprehensive scoring criteria guide

### Core Capabilities

- **H3 Hexagon Grouping** - Edge-to-edge distance (120m default)
- **Per-Tier Normalization** - Fair comparison within categories
- **Diminishing Returns** - Logarithmic scaling for demand
- **Diversity Bonus** - Reward for multimodal integration
- **Consistency Validation** - AHP consistency ratio checking

---

## Quick Start

### Option 1: Run Scoring Pipeline

```python
from scripts.run_pipeline import HubPrioritizationPipeline

pipeline = HubPrioritizationPipeline()
results = pipeline.run_complete_pipeline(
    nodes_csv="data/raw/All_nodes+lines.csv",
    lines_modes_csv="data/raw/Lines_and_Planned_Mode.csv"
)
```

### Option 2: Use AHP Questionnaire

```bash
streamlit run app/ahp_questionnaire.py
```

### Option 3: Run Notebooks

Open and run:
- `notebooks/complete_hub_scoring_pipeline.ipynb`
- `notebooks/hub_data_postprocess.ipynb`

---

## Configuration

All parameters in `src/config.py`:

```python
# Eligibility thresholds
ELIGIBILITY_MIN_PASSENGERS = 1000
ELIGIBILITY_MIN_MODES = 2

# Hierarchy thresholds
NATIONAL_HUB_MIN_PASSENGERS = 50000
METRO_HUB_MIN_PASSENGERS = 5000

# Spatial parameters
H3_RESOLUTION = 10          # ~15m hexagons
HUB_MERGE_THRESHOLD_M = 120 # Edge-to-edge grouping

# Scoring
MONTE_CARLO_ITERATIONS = 10000
MAX_CRITERION_WEIGHT = 0.5

# AHP (optional)
AHP_ENABLED = False  # Set to True to enable
AHP_CONSISTENCY_RATIO_THRESHOLD = 0.10
```

---

## Documentation

| Document | Description |
|----------|-------------|
| `CLAUDE.md` | Complete framework specification |
| `README.md` | Project overview and quick start |
| `INSTALL.md` | Installation instructions |
| `QUICK_REFERENCE.md` | Quick reference card |
| `AHP_QUICKSTART.md` | AHP scoring quick start |
| `docs/AHP_SCORING_GUIDE.md` | Full AHP methodology guide |
| `docs/SCORING_CRITERIA_EXECUTIVE_SUMMARY.md` | Scoring criteria summary |
| `docs/SOLID_PRINCIPLES_REVIEW.md` | Code quality assessment |
| `docs/DATA_CONFIGURATION.md` | Data file configuration |

---

## Testing

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Test AHP scoring
python scripts/test_ahp_scoring.py
```

---

## Requirements

**Core Dependencies:**
- Python >= 3.9
- pandas >= 2.0.0
- geopandas >= 0.13.0
- h3 >= 3.7.0
- numpy >= 1.24.0
- shapely >= 2.0.0

**Optional (for AHP app):**
- streamlit
- plotly

Install with:
```bash
pip install -r requirements.txt
```

---

## Architecture

```
HubPrioritizing/
├── src/                    # Source code
│   ├── config.py           # Configuration
│   ├── scoring/            # Scoring modules
│   ├── spatial/            # Spatial operations
│   ├── classification/     # Hub classification
│   └── visualization/      # Maps and charts
├── app/                    # Streamlit applications
│   └── ahp_questionnaire.py
├── scripts/                # Pipeline scripts
├── notebooks/              # Analysis notebooks
├── data/                   # Data files
├── tests/                  # Unit tests
└── docs/                   # Documentation
```

---

## Summary

The Hub Prioritization Framework provides:

- **Complete scoring pipeline** with 5 criteria and dual aggregation methods
- **Interactive AHP application** for expert weight determination
- **Tier-specific ranking** for fair hub comparison
- **Comprehensive documentation** and test coverage
- **Production-ready architecture** following SOLID principles

**Code Quality: Grade B+** (See `docs/SOLID_PRINCIPLES_REVIEW.md`)

---

*Last Updated: 2025-12-15*
*Version: 2.0*
