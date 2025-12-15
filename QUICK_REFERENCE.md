# Quick Reference Card - Hub Prioritization Framework

## Key Commands

### Run Scoring Pipeline
```bash
python scripts/run_complete_pipeline.py
```

### Run AHP Expert Questionnaire
```bash
streamlit run app/ahp_questionnaire.py
```

### Run Tests
```bash
pytest tests/
```

---

## Key Thresholds

| Parameter | Value | Description |
|-----------|-------|-------------|
| Min Passengers | 1,000/day | Hub eligibility threshold |
| Min Modes | 2 | Required mass-transit modes |
| National Tier | >= 50,000/day | ארצי classification |
| Metro Tier | 5,000-50,000/day | מטרופוליני classification |
| Local Tier | < 5,000/day | עירוני classification |

---

## Spatial Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| H3 Resolution | 10 | ~15m hexagon diameter |
| Buffer Distance | 120m | Hub grouping threshold (centroid-to-centroid) |
| Terminal Proximity | 200m | Bus terminal scoring radius |
| Catchment Rings | 0, 500, 1000, 1500m | Population/jobs distance decay |

---

## Scoring Criteria

| # | Criterion | Method |
|---|-----------|--------|
| 1 | **Passenger Activity** | log₁₀(passengers), per-tier normalization |
| 2 | **Service & Modes** | mode_weight × √lines × diversity_bonus |
| 3 | **Location** | region_weight × metro_position |
| 4 | **Population & Jobs** | Ring-weighted catchment (tier-specific mix) |
| 5 | **Bus Terminal** | 200m proximity × terminal_weight |

**Score Range**: 1-10 (normalized per tier)

---

## Aggregation Methods

### Monte Carlo (Default)
- 10,000 iterations
- Random weights: 0-50% per criterion
- Output: `final_score`, `rank`

### AHP (Optional)
- Expert pairwise comparisons (Saaty scale 1-9)
- Consistency ratio < 0.10 required
- Output: `ahp_score`, `ahp_rank`

---

## Key Files

| File | Purpose |
|------|---------|
| `src/config.py` | All configuration parameters |
| `scripts/run_complete_pipeline.py` | Main pipeline runner |
| `app/ahp_questionnaire.py` | AHP Streamlit app |
| `notebooks/complete_hub_scoring_pipeline.ipynb` | End-to-end scoring |
| `notebooks/hub_data_postprocess.ipynb` | Post-processing |

---

## Output Files

| File | Description |
|------|-------------|
| `hub_prioritization_results_{timestamp}.csv` | Full results |
| `hub_prioritization_results_{timestamp}.geojson` | Spatial data |
| `hub_map_{timestamp}.html` | Interactive map |

---

## H3 Hexagon Grouping

### What 120m Buffer Captures

```
        🟦
     🟦 🟦 🟦
  🟦 🟦 🟢 🟦 🟦
     🟦 🟦 🟦
        🟦

🟢 = Center hexagon
🟦 = Grouped (within 120m centroid distance)
```

### Distance Reference (Resolution 10)

| Hexagons Apart | Centroid Distance | Grouped? |
|----------------|-------------------|----------|
| Touching | ~26m | Yes |
| 1 gap | ~52m | Yes |
| 2 gaps | ~78m | Yes |
| 3 gaps | ~104m | Yes |
| 4 gaps | ~130m | No |

---

## Quick Configuration

```python
# src/config.py key settings

# Enable/disable AHP
AHP_ENABLED = False  # Set True to enable

# Monte Carlo
MONTE_CARLO_ITERATIONS = 10000
MAX_CRITERION_WEIGHT = 0.5

# Spatial
H3_RESOLUTION = 10
HUB_MERGE_THRESHOLD_M = 120

# AHP consistency
AHP_CONSISTENCY_RATIO_THRESHOLD = 0.10
```

---

## Common Adjustments

**Too many single groups?**
→ Increase `HUB_MERGE_THRESHOLD_M` to 150 or 200

**Groups too large?**
→ Decrease `HUB_MERGE_THRESHOLD_M` to 80 or 100

**Different hexagon size?**
→ Adjust `H3_RESOLUTION` (8=larger, 11=smaller)

**Enable expert weighting?**
→ Set `AHP_ENABLED = True` and provide `data/ahp_expert_comparisons.csv`

---

## Documentation

| Document | Description |
|----------|-------------|
| `CLAUDE.md` | Complete specification |
| `README.md` | Project overview |
| `AHP_QUICKSTART.md` | AHP quick start |
| `FINAL_DELIVERABLES_SUMMARY.md` | Deliverables summary |
| `docs/AHP_SCORING_GUIDE.md` | Full AHP guide |
| `docs/SCORING_CRITERIA_EXECUTIVE_SUMMARY.md` | Scoring criteria |

---

*Last Updated: 2025-12-15*
