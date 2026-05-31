# 1. Project Overview

## 1.1 What this project is

The Hub Prioritization Framework is a reproducible, data-driven methodology
for identifying, classifying, prioritizing, and evaluating **integrated
transport hubs** — *מרכזי תחבורה משולבים*, abbreviated **מתח״מים** — across
Israel's planned 2050 mass-transit network.

A *מתח״מ* is a multimodal passenger interchange that:

- combines **at least one mass-transit mode** (Rail, Metro, LRT, BRT) with
  one or more additional modes;
- supports **seamless transfers** between modes;
- functions as a **network node** within the larger PT system;
- often acts as a **catalyst for Transit-Oriented Development (TOD)**.

## 1.2 Goal of the project

Provide planners and decision-makers with a single, transparent system that
can answer three operational questions:

1. **Where are the hubs?** Systematically identify every location in the
   national plan that qualifies as a מתח״מ.
2. **What kind of hub is each one?** Classify hubs into a three-tier
   hierarchy (National / Metropolitan / Local).
3. **Which hubs should be prioritized?** Score and rank each hub using
   transparent, reproducible criteria so that investment can be allocated
   on evidence rather than intuition.

The framework also documents **planning principles** for hub design
(seamless transfer, universal accessibility, TOD-readiness, scalable
capacity, high passenger experience, multimodal connectivity), but those
are guidance — the runnable system focuses on identification, classification,
scoring and ranking.

## 1.3 Problem the framework solves

Multi-modal hub planning in Israel today suffers from:

- **Fragmentation** — no unified methodology across agencies.
- **Inconsistency** — each project uses different criteria.
- **Sub-optimal investment** — resources allocated without systematic
  prioritization.
- **Weak inter-modal connectivity** between projects.
- **Missed TOD opportunities** because development potential is not
  measured systematically.

This framework supplies a single objective process that all stakeholders
can run against the same data and reproduce the same result.

## 1.4 Hub hierarchy

The framework places every eligible hub into one of three tiers based on
2050 ridership forecasts:

| Tier | Hebrew | Daily ridership (2050) | Typical role |
|------|--------|------------------------|--------------|
| National | **ארצי** | ≥ 50,000 (commonly > 100,000) | Connects metropolitan regions and the rail backbone (e.g., Tel Aviv Savidor, Jerusalem Central, Haifa Merkaz) |
| Metropolitan | **מטרופוליני** | 5,000 – 50,000 | Aggregates demand from feeders onto trunk lines within a metro area |
| Local | **עירוני** | < 5,000 | First/last-mile gateway between a neighbourhood and the trunk network |

The three tiers are **descriptive, not prescriptive of quality**. A local
hub serving a small city can be locally critical even though its absolute
ridership is small. This is why scoring is normalised *within* each tier
(see `05_scoring_methodology.md`).

## 1.5 What the framework delivers

The runnable pipeline produces:

1. A **systematic inventory of candidate hubs** identified from the
   transit-network data.
2. A **filter** that removes anything that is not actually a hub
   (insufficient demand or only one mass-transit mode).
3. A **tier assignment** (ארצי / מטרופוליני / עירוני).
4. A **score** for each criterion (1–10) and an **aggregated final score**
   per hub, plus a **rank** per tier / per geographic area.
5. An **interactive map** and tabular exports (CSV / Excel / GeoJSON) for
   downstream use.
6. (Optional) **AHP** alternative scoring and **Monte Carlo distribution**
   analysis (uncertainty / rank robustness).

## 1.6 Headline configuration

These are the values currently configured in `src/config.py` and used
across the pipeline. They are the project's headline parameters; all
others are listed in the [Code Reference appendix](appendix_code_reference.md).

| Parameter | Value | Source |
|-----------|------|--------|
| H3 resolution | **10** (~15 m hexagons) | `config.H3_RESOLUTION` |
| Hub-merge edge-to-edge distance | **120 m** | `config.HUB_MERGE_THRESHOLD_M` |
| Minimum daily passengers for a hub | **1,000** | `config.ELIGIBILITY_MIN_PASSENGERS` |
| Minimum number of mass-transit modes | **2** | `config.ELIGIBILITY_MIN_MODES` |
| Require ≥ 1 non-rail mass-transit mode? | **True** | `config.REQUIRE_NON_RAIL_MODE` |
| National tier threshold | **≥ 50,000 pax/day** | `config.NATIONAL_HUB_MIN_PASSENGERS` |
| Metropolitan tier threshold | **5,000 – 50,000 pax/day** | `config.METRO_HUB_MIN_PASSENGERS` |
| Monte Carlo iterations | **10,000** | `config.MONTE_CARLO_ITERATIONS` |
| Max weight per criterion (MC) | **0.5 (50 %)** | `config.MAX_CRITERION_WEIGHT` |
| AHP enabled by default? | **False** | `config.AHP_ENABLED` |
| Score range | **1 – 10** | `config.SCORE_MIN/MAX` |
