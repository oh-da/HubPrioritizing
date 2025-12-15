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

## Saaty Scale Reference

The application uses the Saaty scale (1-9) for pairwise comparisons:

| Value | Meaning |
|-------|---------|
| 1 | Equal importance |
| 3 | Moderate importance |
| 5 | Strong importance |
| 7 | Very strong importance |
| 9 | Extreme importance |

Values 2, 4, 6, 8 represent intermediate levels.

## Integration with Scoring Pipeline

After collecting expert comparisons:

1. Place the exported CSV in `data/ahp_expert_comparisons.csv`
2. Enable AHP in `src/config.py`: `AHP_ENABLED = True`
3. Run the scoring pipeline - both Monte Carlo and AHP scores will be calculated

## Screenshots

The app provides:
- **Criteria Overview Tab**: Descriptions of all 5 scoring criteria
- **Pairwise Comparisons Tab**: Interactive sliders for each comparison
- **Results & Export Tab**: Weight visualization and CSV download

## Requirements

- Python >= 3.9
- streamlit
- plotly
- pandas
- numpy

## Related Documentation

- [AHP_QUICKSTART.md](../AHP_QUICKSTART.md) - Quick start guide
- [docs/AHP_SCORING_GUIDE.md](../docs/AHP_SCORING_GUIDE.md) - Full methodology guide
- [CLAUDE.md](../CLAUDE.md) - Framework specification (Section 7.6)

---

*Part of the Hub Prioritization Framework*
