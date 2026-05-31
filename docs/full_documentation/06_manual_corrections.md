# 6. Manual Corrections (Human-in-the-Loop)

The model is data-driven, but transport planning has irreducible expert
judgement — anomalies in the input data, demand updates that arrive
through specialised models, hub groupings that the automatic algorithm
would never figure out from geometry alone. The framework exposes
**five formal override mechanisms** so this expert input is captured in
the data, not buried in code.

This document is the canonical inventory. Each correction below
includes: *what it does*, *when it is applied in the pipeline*, *the
file it lives in*, and *the exact CSV / data format*.

| Step | Correction | File | Optional? |
|------|-----------|------|-----------|
| 1.5.1 | Force nodes into the same hub group | `data/IsSameGroup.csv` | Yes |
| 2.6.1 | Override demand & transfers by node ID | `data/manual_demand_updates.csv` | Yes |
| 2.6.2 | Hardcoded National-Model node updates (4 nodes) | *in notebook* | No (built-in) |
| 2.6.3 | Shefaim LRT stop demand correction (node 511248) | *in notebook* | No (built-in) |
| 4.6 (AHP) | Expert pairwise comparisons | `data/ahp_expert_comparisons.csv` | Yes |
| Reporting | Human-curated hub display names | `data/hub_names.csv` | Yes |

Templates for every CSV are checked into `data/`:
`IsSameGroup_TEMPLATE.csv`, `manual_demand_updates_TEMPLATE.csv`,
`ahp_expert_comparisons_TEMPLATE.csv`, `hub_names_TEMPLATE.csv`.

---

## 6.1 🔧 `IsSameGroup.csv` — forcing nodes into the same hub group

**Where in the pipeline:** Step 1.5.1, immediately after the automatic
120 m buffer-based grouping.

**Why we need it:** the 120 m buffer is a good default, but it fails in
several recurring situations:

- two nodes that are operationally part of the same hub but happen to
  be > 120 m apart (e.g. opposite-direction platforms across a wide
  road, or two coordinated forecourts);
- nodes that *must* be planned together because of a board decision;
- data quirks where geometry is slightly off (truncated shapefile, etc.).

**File location (default):** `data/IsSameGroup.csv` (in the canonical
notebook configuration; the path is `MANUAL_GROUP_CSV` in
`COMPLETE_TRANSIT_PIPELINE.ipynb`).

**Format:** one column called exactly `Nodes in group`. Each row is a
comma-separated list of node IDs that must end up in the same group.

```csv
Nodes in group
"400018, 522101"
"123456, 789012, 345678"
"111111, 222222"
```

**Behaviour:**
- Pipeline parses each row, looks up the nodes in the current
  dataframe, and unions their groups (the smallest existing group ID
  becomes the merged group).
- Grouping is **transitive**: rows `A,B` and `B,C` together force
  `{A, B, C}` into one group.
- After all rows are applied, group IDs are **renormalised** to a
  sequential range so downstream code does not need to know about gaps.
- Missing nodes are skipped with a warning (`⚠️ Warning: Node 999999 not
  found in gdf_h3`).
- If the file does not exist or is empty, the pipeline simply continues
  with the automatic grouping (`ℹ️ No manual corrections file found at …`).

**See also:** `data/README_MANUAL_GROUP_CORRECTIONS.md` (the long-form
operator guide with troubleshooting and template instructions).

---

## 6.2 🔧 `manual_demand_updates.csv` — overriding 2050 demand by node

**Where in the pipeline:** Step 2.6.1, after the automatic
Excel-sheet-by-sheet demand match and **before** the hardcoded
overrides in Step 2.6.2 (so the hardcoded values win on conflict).

**Why we need it:** the demand Excel is one set of regional forecasts.
The Israel National Model, ad-hoc surveys, and revised plans regularly
produce more accurate numbers for specific nodes. This is the
preferred way to inject them.

**File location:** path is set by `MANUAL_DEMAND_UPDATES_CSV` in the
notebook MASTER CONFIGURATION; in `src/config.py` it would be e.g.
`DATA_DIR / "manual_demand_updates.csv"`.

**Format:**

| Column | Type | Required | Purpose |
|--------|------|----------|---------|
| `node` | integer | **yes** | Node ID to update |
| `total_demand` | numeric | **yes** | New `TotalDemand` |
| `total_transfers` | numeric | **yes** | New `TotalTransfers` |
| `area` | string | no | Region (for reference / readability) |
| `station_name` | string | no | Station name (for reference) |
| `notes` | string | no | Free-text rationale |

```csv
node,area,total_demand,total_transfers,station_name,notes
400020,Tel Aviv,108409,84490,Netanya,From National Model 2025
400470,Tel Aviv,40628,0,Modiin Merkaz,From National Model 2025
400460,Tel Aviv,41000,12133,Modiin West,From National Model 2025
```

**Why keyed by node ID and not by DataFrame index?** Index numbers
change every time H3 resolution or grouping parameters change, so
index-based overrides silently update *the wrong hub* after a regroup.
Node IDs are stable across runs.

**See also:** `data/README_MANUAL_DEMAND_UPDATES.md` (operator guide
incl. "converting old index-based updates" recipe).

---

## 6.3 🔧 Hardcoded National-Model node updates (Step 2.6.2)

**Where in the pipeline:** Step 2.6.2, after the optional CSV updates.

These are four overrides burned into the notebook source itself. They
exist because they were produced by a specific National-Model run and
the pipeline treats them as ground truth until something better comes
along.

| Node ID | Station | TotalDemand | TotalTransfers |
|---------|---------|------------:|----------------:|
| 400424  | Moshe Dayan (Rishon) | 64,985 | 43,032 |
| 400021  | Netanya Sapir        | 23,083 | 10,140 |
| 400030  | Beit Yehoshua Rail   | 14,518 | 6,101  |
| 511246  | Beit Yehoshua LRT    | 13,601 | 6,101  |

**Note:** three additional updates that the old code applied **by
DataFrame index** (Netanya `400020`, Modiin Merkaz `400470`, Modiin West
`400460`) are deliberately **skipped** in the current notebook because
index-based addressing is unsafe across regroupings. The notebook
prints the skipped values and instructions for re-adding them via the
node-ID-keyed CSV in Step 2.6.1.

---

## 6.4 🔧 Shefaim LRT stop correction (Step 2.6.3)

**Where in the pipeline:** Step 2.6.3, immediately after the hardcoded
updates.

Overrides node `511248` (Shefaim LRT stop) with `TotalDemand = 255.3`.
This is a planned LRT stop whose forecast was added later than the
original demand Excel and is small enough that not patching it would
have no practical effect — but it is left in for completeness.

---

## 6.5 🔧 AHP expert pairwise comparisons (Step 4.6, optional)

**Where in the pipeline:** Step 4.6, alongside Monte Carlo, **only if**
`config.AHP_ENABLED = True`.

**Why we need it:** Monte Carlo treats every weighting as equally
plausible. AHP lets domain experts impose a structured opinion about
*which* criterion should weigh more heavily.

**File location:** `data/ahp_expert_comparisons.csv`
(`config.AHP_EXPERT_CSV_PATH`).

**Format options:** the loader (`src/scoring/ahp.py::load_expert_comparisons_from_csv`)
accepts two formats:

1. **Long format** (one row per pairwise comparison, multi-expert
   supported):
   ```csv
   expert,criterion_a,criterion_b,value
   expert1,activity_score,service_score,3
   expert1,activity_score,location_score,5
   expert1,service_score,location_score,3
   …
   ```
2. **Matrix format** — one or more 5×5 reciprocal matrices, one per
   expert. See `data/ahp_expert_comparisons_example.csv` and
   `data/ahp_expert_comparisons_TEMPLATE.csv` for the exact layout.

**Validity rules** (enforced by
`src/scoring/ahp.py::validate_pairwise_matrix`):
- square 5 × 5 matrix,
- strictly positive entries,
- diagonal = 1,
- reciprocal: `M[i,j] = 1 / M[j,i]`,
- Consistency Ratio < 0.10
  (`config.AHP_CONSISTENCY_RATIO_THRESHOLD`).

Experts that fail validation are reported with a clear error and *not*
included in the aggregated weights.

**Aggregation** is the geometric mean by default
(`config.AHP_AGGREGATION_METHOD = 'geometric_mean'`); arithmetic mean
and median are supported.

See `docs/AHP_SCORING_GUIDE.md` and `AHP_QUICKSTART.md` for the
full operator guide.

---

## 6.6 🔧 Hub display names — `data/hub_names.csv`

**Where used:** map output and Excel exports.

**Why we need it:** automatic group IDs (`0`, `1`, `2`, …) are not
useful for stakeholders. Geocoding addresses are not always sensible
labels either. This file lets the team curate a clean Hebrew (or
English) display name for each hub.

**Format:**
```csv
group,HubName
0,קרית שמונה מרכז
1,כרמיאל מרכז מסחרי
16,נהריה מרכז
```

**Scope:** purely informational. Nothing in the scoring or ranking
depends on it — it only affects how each hub appears to a reader.

---

## 6.7 Where else "human knowledge" enters the model

For completeness, here is everything that is *configurable by humans*
but **not in a CSV**. These live in `src/config.py` and are intended to
be reviewed by domain experts during methodology updates, not edited
case-by-case per hub:

- the eligibility thresholds (`ELIGIBILITY_MIN_PASSENGERS`,
  `ELIGIBILITY_MIN_MODES`, `REQUIRE_NON_RAIL_MODE`);
- the tier thresholds (`NATIONAL_HUB_MIN_PASSENGERS`,
  `METRO_HUB_MIN_PASSENGERS`);
- the modal weights and the diversity bonus
  (`MODE_WEIGHTS`, `MODE_DIVERSITY_BONUS_PCT`);
- the regional and metropolitan position weights
  (`REGION_WEIGHTS`, `METRO_POSITION_WEIGHTS`);
- the ring definitions and the population-vs-jobs tier mix
  (`CATCHMENT_RINGS`, `DISTANCE_DECAY_BETA`, `POP_JOB_MIX`);
- the bus-terminal weights and proximity radius
  (`TERMINAL_WEIGHTS`, `TERMINAL_PROXIMITY_DISTANCE_M`);
- the Monte Carlo weighting envelope
  (`MAX_CRITERION_WEIGHT`, `MIN_CRITERION_WEIGHT`).

All of these have a change history — any modification should be
committed with a CLAUDE.md update.
