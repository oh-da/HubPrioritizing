# 5. Scoring Methodology

Every eligible hub is scored on **five criteria**, each normalised to a
1–10 scale. The five criterion scores are then aggregated into a single
**final score** using **Monte Carlo simulation** (default) or
**AHP** (optional alternative). Ranking is finally applied **per tier**
and, for Metropolitan / Local hubs, **per geographic area**.

| # | Criterion | Source code | Normalization |
|---|-----------|------------|---------------|
| 1 | Passenger Activity | `src/scoring/activity.py` | per **tier** (log₁₀ + min-max) |
| 2 | Service & Hierarchy of Modes | `src/scoring/service.py` | per **tier** (min-max) |
| 3 | Location (Geographic + Metropolitan) | `src/scoring/location.py` | **global** (min-max) |
| 4 | Population & Jobs (2050) | `src/scoring/demographics.py` | per **tier** (min-max) |
| 5 | Bus Terminal Proximity | `src/scoring/terminals.py` | **global** (min-max) |

> "Per tier" means: every Metropolitan hub is normalised against every
> other Metropolitan hub *regardless of metropolitan area*; National
> hubs against other National hubs; Local hubs against other Local
> hubs. "Global" means: all hubs of all tiers normalised together.

---

## 5.1 Passenger Activity

**What it measures:** 2050 forecast demand.

```text
raw_value      = log10(TotalDemand + 1)
activity_score = minmax_per_tier(raw_value, [1, 10])
```

- `log10` (`config.ACTIVITY_SCORE_USE_LOG = True`) compresses the range so
  a 100 k station does not score 10× a 10 k station, only ~1.25× —
  reflecting diminishing marginal value of additional pax.
- Normalised within tier so the National outliers don't crush the
  spread for Metropolitan and Local hubs.

---

## 5.2 Service and Hierarchy of Modes

**What it measures:** the strength and diversity of transit service at
the hub.

### 5.2.1 Mode weights

Configured in `config.MODE_WEIGHTS`:

| Mode | Weight |
|------|-------:|
| HighSpeed Rail | 8.0 |
| Interurban Rail | 7.0 |
| Rail *(generic, treated as Interurban)* | 7.0 |
| Metro | 6.0 |
| Suburban Rail | 6.0 |
| LRT | 5.0 |
| BRT | 4.0 |
| Cable Line | 3.0 |
| Express Bus | 3.0 |
| Funicular | 2.0 |
| Bus | 1.0 |

### 5.2.2 Diminishing returns per mode

For each mode the effective line contribution is

```text
mode_contribution = mode_weight × sqrt(line_count)
```

so that the 9th line of a mode counts less than the 2nd.

### 5.2.3 Modal-diversity bonus

```text
diversity_bonus = 1 + 0.10 × (num_modes − 1)
```

i.e. +10 % per *additional* mode beyond the first.

### 5.2.4 Combined formula

```text
raw       = diversity_bonus × Σ_modes ( mode_weight × sqrt(line_count) )
service_score = minmax_per_tier(raw, [1, 10])
```

Worked example (from `data/README_MODE_LINE_COLUMNS.md`):

| Hub | Composition | Calculation | Raw |
|-----|-------------|-------------|----:|
| A | 2 BRT + 1 LRT | (2·4 + 1·5) · 1.1 | 14.3 |
| B | 4 Metro only | (4·6) · 1.0 | 24.0 |
| C | 2 LRT + 2 Metro + 1 Suburban Rail | (2·5 + 2·6 + 1·6) · 1.2 | 33.6 |

Hub **C** scores highest despite having fewer total lines than B,
because of modal diversity — exactly the intended behaviour.

---

## 5.3 Location (Geographic + Metropolitan)

**What it measures:** strategic positioning, balancing national equity
against metropolitan efficiency.

Two factors are combined multiplicatively:

| Dimension | Field | Mapping (`config.REGION_WEIGHTS`, `METRO_POSITION_WEIGHTS`) |
|-----------|------|------------------------------------------------------------|
| **Region** | `area` | תל אביב / מרכז → **0** ; חיפה / צפון / דרום / ירושלים → **1** (boost the periphery) |
| **Metropolitan position** | `location` | גלעין (core) → **3** ; טבעת (any ring) → **2** ; periphery → **1** |

```text
raw            = region_weight × metro_position_weight
location_score = minmax_global(raw, [1, 10])
```

Global normalisation here is intentional — geography signals (core vs.
periphery, centre vs. North/South) should be comparable across tiers,
not reset within each tier.

Hebrew labels are repaired by
`src/scoring/location.py::fix_truncated_hebrew` (e.g. `גלעי` → `גלעין`,
`תל אבי` → `תל אביב`) before the lookups.

---

## 5.4 Population and Jobs (2050)

**What it measures:** the catchment value of the hub — how much
population and employment it captures within walking/cycling distance,
projected to 2050.

### 5.4.1 Ring weights

Three concentric rings around each hub centroid (in EPSG:2039):

| Ring | Range (m) | Midpoint | Raw weight `1 / midpoint^1.5` | Normalised weight |
|-----:|-----------|---------:|------------------------------:|------------------:|
| 0 | 0 – 500 | 250 | 2.53e−4 | **0.78** |
| 1 | 500 – 1 000 | 750 | 4.87e−5 | **0.15** |
| 2 | 1 000 – 1 500 | 1 250 | 2.26e−5 | **0.07** |

The ring weights are computed in `src/config.py` from
`DISTANCE_DECAY_BETA = 1.5` and `RING_MIDPOINTS = [250, 750, 1250]`.

### 5.4.2 Pop vs Jobs mix per tier

| Tier | Jobs | Population |
|------|-----:|-----------:|
| ארצי (National) | 80 % | 20 % |
| מטרופוליני (Metro) | 80 % | 20 % |
| עירוני (Local) | 20 % | 80 % |

### 5.4.3 Formula

```text
ring_value     = ring_weight × ( jobs_mix · jobs_ring + pop_mix · pop_ring )
raw            = Σ over rings
pop_jobs_score = minmax_per_tier(raw, [1, 10])
```

Higher-tier hubs (Metro/National) reward employment density — they
support office centres. Local hubs reward residential density — they
serve the people who live nearby.

---

## 5.5 Bus Terminal Proximity

**What it measures:** integration with the bus network, which is the
dominant first / last mile feeder.

For each hub, the closest bus terminal within **200 m**
(`config.TERMINAL_PROXIMITY_DISTANCE_M`) contributes a weight from
`config.TERMINAL_WEIGHTS`:

| `term_type` (Hebrew) | English | Weight |
|----------------------|---------|------:|
| מתקן משולב | Integrated facility | 3.0 |
| מסוף גדול | Large terminal | 3.0 |
| מסוף בינוני | Medium terminal | 2.0 |
| מסוף קטן | Small terminal | 2.0 |
| חניון לילה | Night parking | 1.0 |
| — *(no terminal in 200 m)* | — | 0 |

```text
raw            = terminal_weight × proximity_factor
terminal_score = minmax_global(raw, [1, 10])
```

Global normalisation: terminal capability is treated as a system-wide
attribute and is compared across tiers.

---

## 5.6 Aggregation — Monte Carlo (default)

Aggregating five scores by hand-picking weights is fragile: small
changes in one weight can flip the ranking. The pipeline instead runs a
**weight-space simulation**.

For `MONTE_CARLO_ITERATIONS = 10_000` runs:

1. Draw five weights `w₁ … w₅` each uniformly in
   `[MIN_CRITERION_WEIGHT, MAX_CRITERION_WEIGHT]` = `[0, 0.5]`.
2. Re-normalise so `Σ wᵢ = 1`.
3. For every hub compute `iteration_score = Σ wᵢ · scoreᵢ`.

The hub's `final_score` is the mean of its 10,000 iteration scores.
Random seed is fixed (`MONTE_CARLO_RANDOM_SEED = 42`) so results are
deterministic.

**Implementation:**
`src/scoring/monte_carlo.py::monte_carlo_scoring`,
`run_complete_scoring_pipeline`.

### Distribution analysis (optional)

When `RUN_MC_DISTRIBUTION` is set, the raw iteration scores are kept
and the pipeline reports:

- per-hub mean / median / std / p5 / p25 / p75 / p95,
- per-hub rank robustness — probability of ending in Top 1 / Top 3 /
  Top 5 across iterations,
- box-plots, top-K probability charts, and per-hub histograms
  (`MC_DIST_TOP_N_HUBS = 30` by default).

This is the recommended way to characterise *which* rankings are
weight-sensitive and which are stable.

| Implementation | `src/scoring/mc_distribution.py` |

---

## 5.7 Aggregation — AHP (optional alternative)

When `config.AHP_ENABLED = True`, the Analytic Hierarchy Process runs
alongside Monte Carlo and produces an `ahp_score` and `ahp_rank` for
each hub.

**Inputs**: `data/ahp_expert_comparisons.csv` — a long or matrix-form
table of expert pairwise comparisons on the Saaty scale
(1 = equal, 3 = moderate, 5 = strong, 7 = very strong, 9 = extreme).

**Pipeline:**
1. Validate each expert's pairwise matrix (square, positive,
   reciprocal, diagonal = 1).
2. Compute priority weights via the principal eigenvector method.
3. Compute the Consistency Ratio. CR ≥ 0.10 flags a logically
   inconsistent expert (`AHP_CONSISTENCY_RATIO_THRESHOLD = 0.10`).
4. Aggregate experts using the geometric mean
   (`AHP_AGGREGATION_METHOD = 'geometric_mean'`).
5. Apply the aggregated weights to the normalised criterion scores.

Running both methods and comparing their rankings is the best practice:
agreement is evidence of robustness; disagreement isolates the hubs
whose rank is most sensitive to weight choice.

| Implementation | `src/scoring/ahp.py` |

---

## 5.8 Ranking

After scoring, hubs are ranked **per tier**:

- **ארצי (National)** — ranked **globally** (one ranking covers the
  whole country).
- **מטרופוליני (Metropolitan)** — ranked **within geographic area**
  (e.g. Tel Aviv + Center, Haifa + North, South).
- **עירוני (Local)** — ranked **within geographic area**.

This ensures Metropolitan hubs compete with peers serving comparable
catchments rather than against National hubs in the centre.

| Implementation | `src/scoring/monte_carlo.py::_calculate_tier_based_ranking` |
