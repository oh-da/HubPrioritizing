# Run versions and comparing runs

A *version* is one run of the pipeline on one set of model exports. The version lives in the
output directory, not in the code: every `hubs run` writes `run_manifest.json` next to the
workbook, and two output directories can be compared at any time.

## What a version records (`run_manifest.json`)

| field | content |
|---|---|
| `version` | the run's name: `--version NAME`, or by default the newest date carried by the model exports (`2026-06-18`) |
| `created` | when the run finished (UTC) |
| `inputs` | every input file the run used, with source (input dir / reference dir), the date in its name and its SHA-256 |
| `base_layer` | when `h3_base.parquet` was built and the hashes of its four source shapefiles |
| `config` | the effective configuration (same as `run_config.json`) |
| `code` | package version and git commit of the code that ran |
| `summary` | hub count, hubs per tier, top ten |
| `outputs` | the files written |

Because the hashes are recorded, two runs with the same version name but different data are
still distinguishable, and a run can always be traced back to the exact export it consumed.

```bash
hubs run --input-dir runs/2026_06/in --output-dir runs/2026_06/out --version 2026-06
hubs runs runs/                         # every version found under a directory
```

Keep one directory per run. A layout that works:

```
runs/
  2026_06/in/   the model exports          2026_06/out/   the results + run_manifest.json
  2026_09/in/                              2026_09/out/
```

## Comparing two versions

```bash
hubs compare runs/2026_06/out runs/2026_09/out            # writes into runs/2026_09/out
hubs compare runs/2026_06/out runs/2026_09/out --out cmp/  # or elsewhere
```

A is the earlier run, B the later. Three files are written, `compare_<A>_vs_<B>.md`, `.csv`
and `.json`:

- **The report (`.md`)** answers, in order: what changed in the inputs (files that differ by
  name or content, a rebuilt base layer, settings that differ); how many hubs were matched,
  added or removed; the hubs that changed tier; the largest score increases and decreases;
  the largest moves in `RankByHubTypeMetro`.
- **The table (`.csv`)** has one row per hub in either run with every compared field as
  `<field>_a`, `<field>_b` and, for numbers, `<field>_delta`: tier, metro, name, modes,
  demand, transfers, lines, the five normalised criteria, `TotalScore_MC`, `Rank_TS_MC` and
  `RankByHubTypeMetro`. Filter it in Excel or load it in SQL.
- **The summary (`.json`)** is the same numbers for a page or a script.

### How hubs are matched between runs

Group numbers are renumbered every run and cannot be used. Each hub carries `hub_id`, a
hash of its node set, which is identical as long as the same nodes form the hub. The
comparison matches on `hub_id` first (`match = hub_id`); hubs whose node set changed are
then paired by the most shared nodes (`match = nodes`, e.g. a hub that gained a platform).
What is left is `added` (only in B) or `removed` (only in A).

### Reading the differences

- A hub with `match = hub_id` and no changed inputs but a different score reflects a
  settings change or a rebuilt base layer; the report's first section says which.
- A score change with unchanged demand and lines usually comes through the normalisation:
  the criteria are min-max scaled per tier, so one hub's new demand moves every hub of its
  tier a little. `PopEmp_Score_Norm_delta` and the other `_Norm` deltas show where.
- `RankByHubTypeMetro` is a competition rank within tier and metro, so a hub can move rank
  without any change of its own when a neighbour moves.

## Where this goes next

The manifest and the comparison files are plain JSON, CSV and Markdown so that a browser page
can list versions (`hubs runs`), pick two, and show the comparison without recomputing
anything.
