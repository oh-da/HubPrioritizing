# Input Data Configuration Guide

The pipeline no longer has paths to edit in code. Inputs are found by name in one directory,
and every parameter is a configuration value.

## Where files go

| Kind | Location | Examples |
|---|---|---|
| Per-run model exports | the directory you pass to `--input-dir` | `All_nodeslines_18062026.csv`, `Lines_and_Planned_Mode_18-06-2026.csv`, `Nodes_w_results_04022026.xlsx`, `linesNames_noDuplicates.csv`, `lines_exploded.csv`, `BS_lines.csv` |
| Stable layers and curated tables | `data/reference/` (committed) or `--reference-dir` | `h3_base.parquet` (+ manifest), `hub_names.csv`, `is_same_group.csv`, `manual_demand_updates.csv`, `node_position_overrides.csv`, `line_names_extra.csv` |
| Sources of the base layer | `data/reference/`; read only by `hubs prepare-base` (or with `spatial_source=shapefiles`) | `metro_2008.shp`, `Districts.shp`, `BUS_TERMINAL_STRAT.shp`, `TAZ_1270.shp` |

A file placed in the input directory with a reference file's name overrides the reference copy
for that run. The newest file per input (by the date in its name) is used when several match.
When one of the four shapefiles changes, run `hubs prepare-base` to rebuild `h3_base.parquet`
(about 2.5 minutes) and commit both the layer and its manifest; see `H3_BASE_LAYER.md`.
Forgetting is not possible: `hubs validate` and `hubs run` compare the shapefiles' hashes with
the manifest and stop on a mismatch (`on_stale_base_layer=error`).

## Check before you run

```bash
hubs validate --input-dir my_run
```

prints the chosen file for every input, the detected encodings and every problem. Fix the
directory until it exits 0; `hubs run` refuses to start on the same problems and never
substitutes placeholder data.

## Configuration values

```bash
hubs show-config --defaults            # all parameters with their defaults, as YAML
hubs run ... --config pipeline.yaml    # a YAML file with the values you want to change
hubs run ... --set mc_iterations=20000
hubs run ... --set influence_rings=600,1000,1200 --set pop_emp_decay_midpoints=250,750,1250   # June 2026 geometry
```

The effective configuration is saved as `run_config.json` next to the results. See
[`DEVIATIONS.md`](DEVIATIONS.md) for what each flag controls and
[`full_documentation/02_inputs.md`](full_documentation/02_inputs.md) for the exact column
requirements of every file.
