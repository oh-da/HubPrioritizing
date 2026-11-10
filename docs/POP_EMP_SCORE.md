# Population & Jobs 2050 score: how it is calculated

Criterion 4 (`PopEmp_Score_Norm`). Code: `src/pipeline/scoring.py::pop_emp_raw_score`
(rings filled in `src/pipeline/base_layer.py::add_influence_area_from_base`).

## Formula

For hub $h$ and ring $r$ (annulus, not cumulative):

$$
\text{raw}_h = \sum_{r} \frac{w_{pop}\cdot P_{h,r} + w_{emp}\cdot E_{h,r}}{m_r^{\beta}}
\qquad \beta = 1.5
$$

$$
\text{PopEmp\_Score\_Norm}_h = 1 + 9\cdot\frac{\text{raw}_h - \min_{T}\text{raw}}{\max_{T}\text{raw} - \min_{T}\text{raw}}
$$

- $P_{h,r}, E_{h,r}$: 2050 population / jobs inside ring $r$ (each H3 cell counted by the share of its area in the ring)
- $m_r$: ring midpoint, $(r_{in} + r_{out})/2$
- $T$: all hubs of the same `HubType` (min-max is per tier; a tier with a constant value gets 5.5)
- Mix by tier:

| Tier | $w_{emp}$ | $w_{pop}$ |
|---|---|---|
| ארצי (National), מטרופוליני (Metropolitan) | 0.8 | 0.2 |
| עירוני (Local), "Not Hub" | 0.2 | 0.8 |

## Decay divisors (defaults: rings 500 / 1000 / 1500 m)

| Ring (m) | $m_r$ | $m_r^{1.5}$ | $1/m_r^{1.5}$ | Relative to inner ring | Normalised (sum = 1) |
|---|---|---|---|---|---|
| 0–500 | 250 | 3,952.8 | 2.530e-4 | 1.000 | 0.780 |
| 500–1000 | 750 | 20,539.6 | 4.869e-5 | 0.192 | 0.150 |
| 1000–1500 | 1250 | 44,194.2 | 2.263e-5 | 0.089 | 0.070 |

The code divides by $m_r^{1.5}$ directly. The "normalised" column is the same thing scaled by
a constant ($\sum 1/m_r^{1.5} = 3.243\text{e-}4$), so it gives identical 1–10 scores after the
per-tier min-max (see Example 2). The constants `RING_WEIGHTS` / `RING_MIDPOINTS` in
`src/config.py` are not used by the pipeline.

## Example 1: three metropolitan hubs (80 % jobs / 20 % population)

**Hub A**

| Ring | $P$ | $E$ | $0.2P + 0.8E$ | $\div\, m_r^{1.5}$ | Contribution |
|---|---|---|---|---|---|
| 0–500 | 3,000 | 20,000 | 16,600 | ÷ 3,952.8 | 4.200 |
| 500–1000 | 9,000 | 30,000 | 25,800 | ÷ 20,539.6 | 1.256 |
| 1000–1500 | 15,000 | 40,000 | 35,000 | ÷ 44,194.2 | 0.792 |
| **raw** | | | | | **6.248** |

**Hub B**: $P = (2000, 6000, 10000)$, $E = (3000, 8000, 12000)$

$$
\text{raw}_B = \frac{2800}{3952.8} + \frac{7600}{20539.6} + \frac{11600}{44194.2} = 0.708 + 0.370 + 0.262 = 1.341
$$

**Hub C**: $P = (4000, 10000, 14000)$, $E = (10000, 15000, 20000)$

$$
\text{raw}_C = \frac{8800}{3952.8} + \frac{14000}{20539.6} + \frac{18800}{44194.2} = 2.226 + 0.682 + 0.425 = 3.333
$$

**Normalise within the metropolitan tier** (min = B, max = A):

$$
\text{Norm}_A = 10,\quad \text{Norm}_B = 1,\quad
\text{Norm}_C = 1 + 9\cdot\frac{3.333 - 1.341}{6.248 - 1.341} = 1 + 9\cdot 0.406 = 4.65
$$

Hub A's outer ring holds 2.1× the weighted activity of its inner ring
(35,000 vs 16,600), yet contributes 5.3× less (0.792 vs 4.200).

## Example 2: normalised weights give the same score

Using the weights 0.780 / 0.150 / 0.070 instead of the divisors divides every raw value by
the same constant $3.243\text{e-}4$:

$$
\text{raw}'_A = 19{,}265,\quad \text{raw}'_B = 4{,}135,\quad \text{raw}'_C = 10{,}278
$$

$$
\text{Norm}_C = 1 + 9\cdot\frac{10278 - 4135}{19265 - 4135} = 4.65 \quad\text{(unchanged)}
$$

## Example 3: a local hub (80 % population / 20 % jobs)

$P = (6000, 15000, 20000)$, $E = (1500, 4000, 5000)$

$$
\text{raw}_L = \frac{0.8\cdot6000 + 0.2\cdot1500}{3952.8} + \frac{0.8\cdot15000 + 0.2\cdot4000}{20539.6} + \frac{0.8\cdot20000 + 0.2\cdot5000}{44194.2}
$$

$$
= \frac{5100}{3952.8} + \frac{12800}{20539.6} + \frac{17000}{44194.2} = 1.290 + 0.623 + 0.385 = 2.298
$$

It is normalised only against other local hubs, never against A, B, C.

## Example 4: the decay acts on totals, not densities

The rings grow in area, $\pi(r_{out}^2 - r_{in}^2)$:

| Ring | Area (km²) | Area ÷ $m_r^{1.5}$ (relative) | Share of score at uniform density |
|---|---|---|---|
| 0–500 | 0.785 | 1.000 | 49 % |
| 500–1000 | 2.356 | 0.577 | 29 % |
| 1000–1500 | 3.927 | 0.447 | 22 % |

With an even spread of people and jobs, the two outer rings still carry about half the score.

## Example 5: arithmetic vs area-weighted midpoint

The mean distance of a point spread evenly over an annulus is

$$
\bar d = \frac{2}{3}\cdot\frac{r_{out}^3 - r_{in}^3}{r_{out}^2 - r_{in}^2}
$$

| Ring | Arithmetic $m_r$ | Area-weighted $\bar d$ |
|---|---|---|
| 0–500 | 250 | 333.3 |
| 500–1000 | 750 | 777.8 |
| 1000–1500 | 1250 | 1266.7 |

The inner ring's midpoint (250 m) understates its mean distance most. To use $\bar d$:
`--set pop_emp_decay_midpoints=333,778,1267` (this changes the scores).

## Parameters

| Key | Default | Note |
|---|---|---|
| `influence_rings` | `500,1000,1500` | outer radii of the annuli |
| `pop_emp_decay_midpoints` | empty = $(r_{in}+r_{out})/2$ | one per ring |
| `distance_decay_beta` | `1.5` | exponent $\beta$ |

June 2026 legacy results: `--set influence_rings=600,1000,1200 --set pop_emp_decay_midpoints=250,750,1250`
(the old code buffered 600/1000/1200 m but decayed at 250/750/1250 m; see `docs/DEVIATIONS.md`).
