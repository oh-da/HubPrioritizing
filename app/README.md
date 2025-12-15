# AHP Expert Questionnaire - Streamlit App

A professional web-based questionnaire for collecting expert pairwise comparisons using the Analytic Hierarchy Process (AHP) methodology.

## Quick Start

```bash
# Install dependencies
pip install streamlit plotly pandas numpy

# Run the app
streamlit run app/ahp_questionnaire.py
```

## Features

- **Interactive Pairwise Comparisons**: Intuitive slider-based interface for comparing criteria
- **Real-time Consistency Check**: Immediate feedback on logical consistency (CR < 0.10)
- **Weight Visualization**: Bar charts and pie charts showing calculated priority weights
- **CSV Export**: Export comparisons in format compatible with the AHP scoring module
- **Professional Design**: Modern, responsive UI with Hebrew/English bilingual support

## How to Use

1. **Enter your name** in the sidebar
2. **Review the criteria** in the Overview tab
3. **Complete comparisons** by adjusting the sliders
4. **Check results** for consistency and weights
5. **Export to CSV** for use in the scoring pipeline

## Criteria

| Criterion | Description |
|-----------|-------------|
| Passenger Activity | 2050 passenger demand forecast |
| Service & Modes | Transit service quality and diversity |
| Location | Strategic geographic importance |
| Population & Jobs | Catchment area demographics |
| Bus Terminal | Integration with bus network |

## Output Format

The exported CSV follows this format:

```csv
expert,criterion_a,criterion_b,value
expert_name,activity_score,service_score,3
...
```

This file can be placed in `data/ahp_expert_comparisons.csv` for use with the scoring pipeline.
