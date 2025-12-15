# Executive Summary: Hub Scoring Criteria

**Hub Prioritization Framework for Integrated Transport Hubs (מתח"מים)**

---

## Overview

The Hub Prioritization Framework uses **5 scoring criteria** to evaluate and rank integrated transport hubs across Israel. Each criterion produces a normalized score from **1 to 10**, which are then aggregated using Monte Carlo simulation (10,000 iterations with random weights 0-50% per criterion) to produce final rankings.

---

## The 5 Scoring Criteria

### 1. Passenger Activity Score

**Purpose:** Measures hub importance based on 2050 forecasted passenger demand.

**Calculation Method:**
```
Activity Score = normalize(log₁₀(daily_passengers_2050))
```

**Key Features:**
- Uses **log₁₀ transformation** to prevent mega-stations from dominating
  - Example: 100,000 passengers scores ~1.25× higher than 10,000 (not 10×)
  - This reflects diminishing marginal impact at very high volumes
- **Per-tier normalization** ensures fair comparison within each hub category
- Based on 2050 passenger forecasts (boardings + alightings)

**Why It Matters:** Passenger volume directly indicates the strategic importance and utilization potential of a hub.

---

### 2. Service & Hierarchy of Modes Score

**Purpose:** Evaluates the strength and diversity of transit service at each hub.

**Calculation Method:**
```
Raw Score = Σ(mode_weight × √n_lines) × diversity_bonus

Where:
- diversity_bonus = 1 + (n_modes - 1) × 0.10
```

**Mode Weights:**
| Mode | Weight |
|------|--------|
| HighSpeed Rail | 8.0 |
| Interurban Rail | 7.0 |
| Rail (generic) | 7.0 |
| Suburban Rail | 6.0 |
| Metro | 5.0 |
| LRT (Light Rail) | 4.0 |
| BRT / Express Bus | 3.0 |
| Bus | 2.0 |
| Cable Line | 2.0 |
| Funicular | 1.0 |

**Key Features:**
- **Diminishing returns**: Uses √n for line counts (2nd/3rd lines matter more than 9th)
- **Diversity bonus**: +10% per additional mode (2 modes = +10%, 3 modes = +20%, etc.)
- Normalized to 1-10 scale per tier

**Why It Matters:** Multiple modes and high-capacity services indicate better connectivity, resilience, and network integration.

---

### 3. Location Score (Geographic & Metropolitan)

**Purpose:** Balances national equity (periphery prioritization) with metropolitan efficiency (core prioritization).

**Calculation Method:**
```
Location Score = normalize(region_weight × metro_position_weight)
```

**Regional Weights (National Equity):**
| Region | Weight |
|--------|--------|
| Tel Aviv / Center | 0 |
| North / Haifa | 1 |
| South / Beer Sheva | 1 |
| Jerusalem | 1 |

**Metropolitan Position Weights:**
| Position | Weight |
|----------|--------|
| Core (גלעין) | 3 |
| Ring (טבעת) | 2 |
| Outer / Periphery | 1 |

**Key Features:**
- **Inverted regional scoring**: Periphery receives higher weight to promote national equity
- **Core prioritization**: Within metropolitan areas, central locations score higher
- Combined score normalized to 1-10

**Why It Matters:** Ensures investment considers both regional equity and metropolitan efficiency.

---

### 4. Population & Jobs Score (2050)

**Purpose:** Measures development potential and catchment area characteristics.

**Calculation Method:**
```
Ring Score = (population × pop_weight + jobs × job_weight) × distance_weight

Total Score = Σ(Ring Scores for all rings)
```

**Catchment Rings:**
| Ring | Distance | Purpose |
|------|----------|---------|
| 1 | 0-500m | Primary walkable catchment |
| 2 | 500-1000m | Secondary catchment |
| 3 | 1000-1500m | Extended catchment |

**Population/Employment Mix by Tier:**
| Hub Tier | Jobs Weight | Population Weight |
|----------|-------------|-------------------|
| National (ארצי) | 80% | 20% |
| Metropolitan (מטרופוליני) | 80% | 20% |
| Local (עירוני) | 20% | 80% |

**Key Features:**
- **Distance decay**: Closer rings weighted more heavily
- **Tier-specific mix**: Higher-tier hubs weighted toward employment; local hubs toward population
- Uses **2050 forecasts** to capture Transit-Oriented Development (TOD) potential
- Normalized to 1-10 scale per tier

**Why It Matters:** Reflects actual demand potential and alignment with land use patterns.

---

### 5. Bus Terminal Proximity Score

**Purpose:** Measures integration with the bus network for first/last mile connectivity.

**Calculation Method:**
```
If hub within 200m of terminal:
    Raw Score = terminal_type_weight
Else:
    Raw Score = 0

Final Score = normalize(Raw Score)
```

**Terminal Weights:**
| Terminal Type | Weight |
|---------------|--------|
| Large Terminal (מסוף גדול) | 3.0 |
| Integrated Facility (מתקן משולב) | 3.0 |
| Regional | 2.5 |
| Medium Terminal (מסוף בינוני) | 2.0 |
| Metropolitan | 2.0 |
| Small Terminal (מסוף קטן) | 2.0 |
| Local | 1.5 |
| Night Parking (חניון לילה) | 1.0 |
| Neighborhood | 1.0 |

**Key Features:**
- **200m proximity threshold**: Binary check for terminal proximity
- **Terminal classification**: Larger/more important terminals score higher
- Based on 2050 terminal strategy plans
- Hubs not near terminals receive minimum score (1)

**Why It Matters:** Bus integration is critical for first/last mile access and overall network connectivity.

---

## Score Aggregation

### Monte Carlo Method (Default)

The final score is calculated using **Monte Carlo simulation**:

1. Run **10,000 iterations**
2. Each iteration assigns **random weights (0-50%)** to each criterion
3. Calculate weighted average score per iteration
4. Final score = mean across all simulations

**Benefits:**
- Prevents any single criterion from dominating
- Robust to weighting uncertainty
- Avoids arbitrary weight selection

### Alternative: AHP (Analytic Hierarchy Process)

An optional expert-driven weighting method is also available:
- Experts provide pairwise comparisons between criteria
- Weights derived using eigenvector method
- Consistency validation (CR < 0.10)
- Can run alongside Monte Carlo for comparison

---

## Summary Table

| # | Criterion | What It Measures | Key Method | Output |
|---|-----------|------------------|------------|--------|
| 1 | **Passenger Activity** | Demand importance | log₁₀ transform, per-tier normalization | 1-10 |
| 2 | **Service & Modes** | Transit service quality | Mode weights × √lines × diversity bonus | 1-10 |
| 3 | **Location** | Strategic position | Region × metro position weights | 1-10 |
| 4 | **Population & Jobs** | Catchment potential | Ring-weighted pop/job mix (tier-specific) | 1-10 |
| 5 | **Bus Terminal** | Network integration | 200m proximity × terminal weight | 1-10 |

---

## Key Design Principles

1. **Logarithmic scaling** prevents extreme values from dominating
2. **Per-tier normalization** ensures fair comparison within hub categories
3. **Diminishing returns** reflect real-world network effects
4. **Diversity bonuses** reward multimodal integration
5. **Regional equity** balanced with metropolitan efficiency
6. **2050 forecasts** capture future development potential
7. **Monte Carlo aggregation** provides robust, bias-resistant final scores

---

*Document generated: 2025-12-15*
*Source: Hub Prioritization Framework - src/scoring/*
