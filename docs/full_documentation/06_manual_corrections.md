# 6. Manual Corrections (Human-in-the-Loop)

The model is data-driven, but transport planning has irreducible expert judgement:
anomalies in the input data, demand updates that arrive through specialised models, hub
groupings the geometry alone would never produce. Every such override is a **data file**
under `data/reference/` (or a same-named file in the run's input directory, which takes
precedence). Nothing is hardcoded in the pipeline any more; every applied or skipped row is
listed in `run_report.md`.

| Stage | Correction | File | Key |
|------|-----------|------|-----|
| Grouping | Force nodes into one hub | `is_same_group.csv` | node IDs |
| Demand | Override 2050 demand / transfers | `manual_demand_updates.csv` | node ID |
| Display | Hebrew hub names | `hub_names.csv` | H3 index |
| Display | Hebrew line names missing from the export | `line_names_extra.csv` | line ID |
| Display | Line-name spelling corrections | `BS_lines.csv` (per run) | line ID |
| Display | Line planning status | `line_status.csv` / `lines_exploded.csv` (per run) | line ID |
| Scoring (optional) | AHP expert pairwise comparisons | `data/ahp_expert_comparisons.csv` | — |

All keys are stable model identifiers. **Never key a table by `group`**: group IDs are
renumbered whenever the network or the manual merges change. (A legacy `group`-keyed hub
names file is still accepted with a deprecation warning.)

---

## 6.1 🔧 `is_same_group.csv` — forcing nodes into one hub

**Stage:** `grouping.apply_manual_groups`, right after the automatic 120 m grouping.

**Why:** two nodes that belong to one hub operationally but sit more than 120 m apart
(opposite platforms across a wide road, coordinated forecourts, a board decision).

**Format:** one column `Nodes in group`; each row a comma-separated list of node IDs.

```csv
Nodes in group
"400018, 521063, 523019"
"400020, 511128"
```

**Behaviour:** every group touched by a row is merged into the smallest group ID among them;
merges are transitive across rows; group IDs are then renumbered sequentially. Nodes that are
not in the network are reported (`manual group row N: nodes not found`).

## 6.2 🔧 `manual_demand_updates.csv` — overriding 2050 demand by node

**Stage:** `demand.apply_manual_demand`, after the workbook match. Rows are applied in file
order; later rows win. The override applies to every hexagon that contains the node.

| Column | Required | Purpose |
|--------|----------|---------|
| `node` | yes | node ID |
| `total_demand` | yes | new `TotalDemand` |
| `total_transfers` | no | new `TotalTransfers`; blank keeps the computed value |
| `station_name`, `notes` | no | shown in the report |

The file shipped in `data/reference/` holds the National-Model values that used to be
hardcoded in the notebook (Moshe Dayan, Netanya Sapir, Beit Yehoshua rail and LRT, Shefaim) and
the Netanya (node 400020) update the notebook listed for CSV entry. Candidates not included
because their hubs are not in the current set: Modiin Merkaz 400470 (40,628 / 0) and Modiin
West 400460 (41,000 / 12,133).

## 6.3 🔧 `hub_names.csv` — Hebrew display names

**Stage:** `postprocess.hub_name_lookup`.

**Format:** `name_id, h3_index, HubNameHE` — one row per H3 cell; a hub takes the name of the
first of its cells that appears in the file. A hub whose cells map to two different names, and
hubs without any name, are reported. To name a new hub, copy one of its `h3_index` values
from `hub_identity.csv` or the workbook's `h3_index` column.

## 6.4 🔧 Line names, corrections and statuses

- `linesNames*.csv` (per run) maps line IDs to `Hebrew name (mode)`; it may be headerless.
  `data/reference/line_names_extra.csv` fills gaps (currently the Metro M1 lines). Lines that
  remain unnamed keep their ID and are listed in the report.
- `BS_lines.csv` (per run) fixes misspelled line IDs before name and status lookups.
- `line_status.csv` (clean: `LineName, StatusID`) or the legacy `lines_exploded.csv` gives each
  line a planning-status code 0–7, counted into `NumLinesStatus_*`. In legacy files a line may
  appear with different statuses; the last value is used and the conflict reported.

## 6.5 🔧 AHP expert pairwise comparisons (optional)

Unchanged: `data/ahp_expert_comparisons.csv` (long or matrix format, see the templates),
validated for reciprocity and consistency (CR < 0.10), aggregated by geometric mean.
See `docs/AHP_SCORING_GUIDE.md` and `AHP_QUICKSTART.md`.

## 6.6 Where else human knowledge enters the model

Parameters reviewed by domain experts during methodology updates, not per hub:

- eligibility and tier thresholds (`src/config.py`: `ELIGIBILITY_MIN_PASSENGERS`,
  `NATIONAL_HUB_MIN_PASSENGERS`, `METRO_HUB_MIN_PASSENGERS`, `REQUIRE_NON_RAIL_MODE`);
- modal weights and the diversity bonus (`MODE_WEIGHTS`, `mode_diversity_alpha`);
- catchment rings and distance decay (`influence_rings`, `distance_decay_beta`);
- terminal buffer (`terminal_buffer_m`) and Monte Carlo settings (`mc_iterations`, `mc_seed`);
- line drop rules (`drop_line_rules`).

Run-time parameters are set with `--config pipeline.yaml` or `--set key=value` and recorded
in `run_config.json`; `docs/DEVIATIONS.md` explains each flag.
