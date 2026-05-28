# Hub Prioritization Framework — Executive Summary

**A Unified National Methodology for Identifying, Classifying, and Prioritizing Integrated Transport Hubs (מתח״מים) in Israel**

---

## The Headline

We did not build a ranking. We built **the missing decision infrastructure** for one of Israel's largest infrastructure investment areas.

Before this project, the country was planning tens of billions of shekels of multimodal hub investment **without a shared definition of what a hub is, a shared way to classify it, or a shared way to compare it to another**. Each agency, plan, and consultant used its own logic. The output of this project is the first end-to-end, reproducible, auditable system that closes that gap — from raw multi-agency data all the way to a defensible priority list.

**What looks on a slide like "a list of hubs with scores" is, under the surface, a five-layer methodology with explicit design decisions at every layer.** The rest of this document makes those layers visible.

---

## Why The Work Looks Simpler Than It Is

A two-column ranking table hides:

- **Six distinct analytical stages**, each with its own validation
- **Five scoring criteria**, each with its own normalization regime, mathematical transformation, and rationale
- **Two independent aggregation methods** (Monte Carlo + AHP) running in parallel for cross-validation
- **Three-tier classification** with different scoring logic per tier
- **Multi-agency data reconciliation** across conflicting forecasts and naming systems
- **A spatial indexing strategy** (H3 at 150m resolution) that itself encodes thousands of hex-level aggregation decisions
- **Per-tier normalization** vs **global normalization** chosen separately for each criterion based on planning logic

The final ranking is the *last* step. The depth lives in everything that had to be true before that step could exist.

---

## The Five Layers of Depth

### Layer 1 — Problem Definition That Did Not Exist Before

Israeli transport planning had **no agreed operational definition** of an integrated transport hub. We established one:

> A *מתח״מ* requires (a) at least one mass-transit mode (רכבת / מטרו / רק״ל / BRT), (b) seamless inter-modal transfer, (c) a network-centrality role, (d) ≥1,000 passengers/day forecast.

This single definition — and its eligibility filter — is itself a research contribution. It is what allowed **155 candidate sites** to be evaluated by the same yardstick for the first time.

### Layer 2 — A Hierarchy That Respects Both Equity and Function

A flat ranking would have collapsed national, metropolitan, and local hubs into one list, hiding the fact that they serve completely different planning functions. We built a **three-tier hierarchy** — ארצי / מטרופוליני / עירוני — with:

- Different ridership thresholds per tier
- Different scoring mixes (e.g., national/metro hubs scored 80% jobs / 20% population; local hubs scored 20% jobs / 80% population — because their planning purpose is different)
- Different ranking scopes: **national hubs ranked globally; metropolitan and local hubs ranked within their geographic area** (Tel Aviv, Haifa+North, South) so peripheral hubs are not crushed by Gush Dan demand mass

This is not a cosmetic taxonomy. It is the mechanism by which the framework remains **fair across geography** while still being **rigorous within tier**.

### Layer 3 — Five Criteria, Each Engineered Individually

| Criterion | Why It Matters | Engineering Decision | Normalization |
|---|---|---|---|
| **Passenger Activity (2050)** | Demand is the primary justification for investment | **log₁₀ transformation** — prevents a 100k-rider mega-station from scoring 10× a 10k-rider hub, which would erase all variation among non-mega hubs | Per tier |
| **Service & Modes Hierarchy** | A hub's value comes from *what connects there*, not just how many people use it | Mode-weighted line counts with **diminishing returns** (the 9th line matters less than the 2nd) + **diversity bonus** (+10% for the 2nd mode, +20% for the 3rd, etc.) — reflecting network effects | Per tier |
| **Location (Geographic + Metropolitan)** | National planning must balance metropolitan efficiency against regional equity | **Two-dimensional**: national region weight (periphery boost) × metropolitan position (core/ring/outer). Center receives weight 0 in the equity dimension — an explicit policy lever | **Global** |
| **Population & Jobs (2050)** | Hubs are demand catalysts; catchment matters | **Concentric rings up to 1.5 km** with distance decay; **tier-specific job/population mix** (national/metro = 80/20 jobs/pop; local = 20/80) | Per tier |
| **Bus Terminal Integration** | First/last mile is where multimodal promises succeed or fail | 200m radius, terminal-type-weighted, based on the **2050 strategic terminal plan** | **Global** |

Every one of these cells is a *defended* choice. The log transform, the diminishing returns curve, the diversity bonus, the ring-decay function, the choice of global vs per-tier normalization — each was made deliberately and each is reversible by anyone auditing the method.

### Layer 4 — Two Aggregation Methods, Not One

Most prioritization exercises pick a set of weights and call it done — which means the result is hostage to whichever expert was in the room that day. We refused that trap.

**Method A — Monte Carlo Simulation** (default)

- **10,000 iterations** with randomly sampled weight vectors
- Each criterion sampled in [0%, 50%] per iteration
- Final score = mean weighted score across all simulations
- **Result: no single criterion can dominate**, and the ranking is robust to weighting uncertainty by construction

**Method B — Analytic Hierarchy Process (AHP)** (optional, expert-driven)

- Pairwise expert comparisons on the Saaty 1–9 scale
- Principal eigenvector weight extraction
- **Consistency Ratio (CR) check** — experts whose judgments contradict themselves (CR ≥ 0.10) are flagged automatically
- Multi-expert aggregation via geometric mean

**Why both?** Running them in parallel produces a third deliverable nobody explicitly asks for but everyone needs:

> **Hubs where Monte Carlo and AHP agree are robust. Hubs where they disagree are weight-sensitive and require deliberate stakeholder decision.**

That second list is arguably more valuable than the first — it tells planners *where the political/judgment calls are*, not just where the math points.

### Layer 5 — Reproducibility as a First-Class Requirement

Every result in this project can be regenerated end-to-end. This is rare in transport planning and is itself an outcome:

- All thresholds, weights, and parameters are in `src/config.py` — no magic numbers in code
- Random seeds fix Monte Carlo output exactly
- H3 hexagonal indexing makes spatial aggregation deterministic
- Data versioning, logging, and validation at every stage
- Modular codebase reviewed against SOLID principles (Grade A−, see `docs/SOLID_PRINCIPLES_REVIEW.md`)

A future analyst, a future government, or a future critic can rerun this with new 2050 forecasts and get a defensible answer. **That is the deliverable.** The current ranking is a snapshot; the framework is the asset.

---

## What We Actually Built

| Component | Description |
|---|---|
| **End-to-end data pipeline** | Multi-agency reconciliation → H3 spatial aggregation → eligibility filtering → tier classification → five-criterion scoring → dual-method aggregation → ranking |
| **155 candidate hubs identified** | Across all mass-transit plans nationally |
| **69 filtered out** | By transparent eligibility rules (≥1,000 passengers/day, ≥2 mass-transit modes) |
| **86 hubs fully scored and prioritized** | 15 national / 29 Tel Aviv+Center metropolitan / 14 Haifa+North metropolitan / 3 South metropolitan / local hubs as defined |
| **Dual aggregation** | Monte Carlo (10,000 iterations) + optional AHP with consistency validation |
| **Interactive spatial visualization** | Hub points, areas, catchments, network connections |
| **Audit trail** | Every score traceable back to its inputs and parameters |
| **Documented methodology** | `CLAUDE.md`, `docs/SCORING_CRITERIA_EXECUTIVE_SUMMARY.md`, `docs/AHP_SCORING_GUIDE.md`, `docs/DEMO_SCORING_WALKTHROUGH.md` |

---

## How This Helps Transport Hub Planning

1. **A single common language.** Agencies, ministries, municipalities, and consultants can now use the same definition, the same hierarchy, the same criteria, and the same scores. Conversations move from "what *is* a hub" to "what should we do about *this* hub."

2. **Defensible investment sequencing.** Capital plans can cite a reproducible methodology rather than ad-hoc judgment. Treasury, regulators, and the public can see *why* one hub is prioritized over another.

3. **Equity as an explicit lever, not an afterthought.** The geographic location score makes periphery weighting a visible choice. If policy changes, the parameter changes — not the entire study.

4. **Sensitivity is built in, not bolted on.** Monte Carlo's design *is* a sensitivity analysis. Decision-makers see not just the ranking, but how stable it is.

5. **A live framework, not a final report.** When 2050 forecasts update, when a new mass-transit line is approved, when a terminal strategy shifts — the pipeline reruns and produces an updated, comparable answer.

6. **TOD and planning guidance.** The framework also encodes design principles (seamless transfers, accessibility, scalable capacity, multimodal connectivity) that translate prioritization into *design intent*.

---

## How To Convey The Depth In A Presentation

If the audience is leaving with "they made a list," the slides are showing the destination without the road. Some narrative anchors that surface the depth:

1. **Lead with the absence.** Before this work, there was no agreed definition of a hub, no agreed hierarchy, no agreed criteria. **Show the void first.** The framework becomes meaningful only against the prior fragmentation.

2. **Show one criterion in full.** Pick *one* of the five scoring criteria — Service & Modes, say — and walk through line counts → mode weights → diminishing returns → diversity bonus → per-tier normalization. The audience now understands that **each of the other four has the same depth behind it**. One example beats five summaries.

3. **Show the dual-method comparison.** Display Monte Carlo and AHP rankings side by side. Highlight a hub where they *agree* (robust) and a hub where they *disagree* (politically sensitive). This single visual proves the framework is doing analytical work the audience did not know was possible.

4. **Show the parameter file.** Pull up `src/config.py`. Every threshold is visible and changeable. This is what reproducibility *looks* like. Audiences trust what they can see.

5. **Show a sensitivity sweep.** "What if jobs matter twice as much?" Run it live or pre-rendered. The ranking shifts — or doesn't. That responsiveness *is* the product.

6. **Reframe the deliverable.** Say explicitly: **"The ranking is a snapshot of the framework's output on today's data. The framework itself is the deliverable."** This reframes the work from a one-off study to a permanent national capability.

7. **Quantify the decisions.** Roughly: 1 definition × 3 tiers × 5 criteria × 2 aggregation methods × 10,000 Monte Carlo iterations × 155 candidate hubs = the surface area of judgment the framework systematizes. Numbers like these make depth audible.

---

## One-Line Versions (Pick Per Audience)

- **For ministers**: "We built the first reproducible national system for deciding which transport hubs to invest in, and in what order."
- **For planners**: "Five criteria, two aggregation methods, three tiers, H3-indexed, fully parameterized — the methodology is the asset."
- **For the public**: "Hub investment decisions are now transparent, auditable, and defendable — anyone can see why a hub was prioritized."
- **For critics**: "Every threshold, weight, and transformation is in version control. Disagree? Change a parameter and rerun."

---

## Bottom Line

This is not a ranking exercise dressed up in math. It is a **decision-infrastructure project** that happens to produce a ranking as one of its outputs. The depth is in the layering — definition, hierarchy, criteria engineering, dual aggregation, reproducibility — and in the fact that **each layer was a deliberate choice with a documented rationale**.

If a presentation conveys only the top layer, the audience sees a list. If it conveys the five layers, the audience sees the **national planning capability** that produced it.
