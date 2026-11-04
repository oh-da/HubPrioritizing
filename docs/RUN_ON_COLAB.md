# Run the pipeline on Google Colab

No installation on your computer. You need a Google account, the model exports in Google
Drive, and access to this GitHub repository. Total time: about five minutes, of which the
pipeline itself takes one.

## 1. Put the run's files in one Drive folder

In Google Drive create a folder, for example `HubRuns/2026_06`, and put the exports of this
run in it. Nothing else needs to be there.

| File | Required |
|---|---|
| `All_nodeslines_<date>.csv` | yes |
| `Lines_and_Planned_Mode_<date>.csv` | yes |
| `Nodes_w_results_<date>.xlsx` | yes |
| `linesNames_noDuplicates.csv` | no (Hebrew line names) |
| `lines_exploded.csv` | no (line planning status) |
| `BS_lines.csv` | no (line name corrections) |

Keep the file names as the model exports them; the date in the name is how the pipeline
picks the newest file when several are present. The reference data (H3 base layer, hub
names, manual corrections) comes with the repository; you do not copy it.

## 2. Open the notebook in Colab

1. Go to https://colab.research.google.com.
2. **File → Open notebook → GitHub** tab.
3. If the repository is private, tick **Include private repos** and allow Colab to access
   your GitHub account when asked.
4. Enter `oh-da/HubPrioritizing`, pick the branch, and open `colab/hubs_run.ipynb`.

## 3. Fill in step 1 of the notebook

The first cell is a form:

| Box | What to type |
|---|---|
| `INPUT_FOLDER` | the Drive folder from section 1, either relative to My Drive (`HubRuns/2026_06`) or as a full path (`/content/drive/MyDrive/HubRuns/2026_06`) |
| `OUTPUT_FOLDER` | leave blank; results go to a folder named `out` inside the input folder (same two path forms) |
| `REFERENCE_FOLDER` | leave blank to use `data/reference` from the repository (H3 base layer and curated tables). See *Using your own reference data* below |
| `VERSION` | a name for this run, e.g. `2026-06`; blank = the newest date in the export file names |
| `REPO`, `BRANCH` | leave as they are unless you were told otherwise |
| `EXTRA_ARGS` | leave blank |
| `AGENCY_FOLDER`, `AGENCY_GPKG`, `AGENCY_META` | optional: the Drive folder that holds the planning agency's `MT_Network.gpkg` (and `MT_Network_MetaData.xlsx`) and the two file names. Blank `AGENCY_FOLDER` = no comparison. See *Comparing with the agency's network* below |
| `COMPARE_FOLDER`, `COMPARE_ARGS` | optional: where the comparison goes (blank = a folder `compare` inside `out`) and extra settings for `hubs compare-network`, e.g. `--set containment=false` |

### Using your own reference data

There are two ways, and the first is usually enough:

- **Replace one file:** put a file with the same name pattern in the *input* folder
  (e.g. `hub_names.csv` or `h3_base.parquet` with its `h3_base.manifest.json`). A file in
  the input folder always wins over the reference copy; `hubs validate` shows `input` in
  the *source* column for it.
- **Replace the whole folder:** set `REFERENCE_FOLDER`. This folder is used *instead of*
  `data/reference`, not on top of it, so copy the whole `data/reference` folder to Drive
  first and change files there. A file missing from it (for example `hub_names.csv`,
  `is_same_group.csv` or `manual_demand_updates.csv`) is simply not used, and the run
  loses those names, merges or corrections.

## 4. Runtime → Run all

Then answer what Colab asks:

- **Connect to Google Drive**: a Google window opens; choose your account and allow access.
  The cell prints the files it sees in your folder. If it stops with *Input folder not
  found*, fix `INPUT_FOLDER` and run again.
- **GitHub token** (private repository only): step 3 asks you to paste a personal access
  token. To make one: GitHub → your photo → **Settings → Developer settings → Personal
  access tokens → Fine-grained tokens → Generate new token**, choose this repository, set
  *Repository permissions → Contents → Read-only*, generate, copy. Paste it into the box in
  the notebook and press Enter. The token is never printed.

Step 4 checks the inputs. If it prints `STOP`, read the list above it: it names every
missing file or column. Fix the Drive folder and run the cell again; nothing else is
affected.

Step 5 runs the pipeline. Step 6 lists the files it wrote and the top ten hubs. Step 7 compares the
results with the planning agency's network when `AGENCY_FOLDER` is filled in (it prints a one-line
skip message otherwise).

## 5. Collect the results

In Drive, open the `out` folder inside your input folder:

| File | Use |
|---|---|
| `hub_prioritization_results.xlsx` | the workbook the display page reads |
| `hub_prioritization_results.csv` | the same table as CSV |
| `hub_scoring_calculation.xlsx` | the calculation workbook for stakeholders: every criterion, weight and rank as Excel formulas (start at `Hub_Explorer`) |
| `h3_layer.gpkg` | the H3 cell layer for QGIS / ArcGIS / SQL |
| `run_report.md` | every data-quality finding; read the warnings before publishing |
| `run_manifest.json` | the version record: which files, which settings, which code (`docs/VERSIONS.md`) |
| `hub_identity.csv`, `run_config.json`, `run.log` | traceability |

To see what changed since an earlier run, keep each run in its own folder and, in a Colab
cell after step 5, run `!hubs compare "/content/drive/MyDrive/HubRuns/2026_03/out" "$OUTPUT_DIR"`;
the report lands next to the new results.

Step 8 downloads the workbook to your computer straight away if you prefer.

### Comparing with the agency's network

With `AGENCY_FOLDER` filled in, step 7 runs `hubs compare-network` on the run that step 5 just wrote
and puts the comparison in `out/compare` (or `COMPARE_FOLDER`): `network_comparison.xlsx` (routes and
hubs of both networks side by side), `network_comparison.gpkg`, two Leaflet pages and a report. How to
read them is in `docs/NETWORK_COMPARISON.md`. If the agency files are missing the step stops with the
list of the paths it looked for; the pipeline results are already written by then. For a map of the lines
and hubs missing from either network, run `colab/hubs_missing_map.ipynb` (section 7).

## 6. Optional second step: line-status columns

`colab/hubs_line_status.ipynb` runs **after** the first notebook, in its own Colab session.
It reads the run's `hub_prioritization_results.csv`, looks up the planning status (0-7) of every
line of every hub in a line-status table, and recomputes `NumLinesStatus_0` ... `NumLinesStatus_7`
and `TotalLinesAllStatuses`. The first notebook already fills these columns from
`lines_exploded.csv`; use the second step when you have a richer status table (with the status
text and year) or want to see which line carries which status. It does not change eligibility,
tiers, scores or ranks.

Put the status table in the same Drive folder as the exports: `line_status*.csv` (or
`lines_exploded*.csv`) with `LineName` and `StatusID` / `Status Id`, and optionally `Status`
(text) and `Year`. `BS_lines*.csv` is applied first if present. Then open the notebook the same
way as in section 2, type the same `INPUT_FOLDER` / `OUTPUT_FOLDER` in step 1, and
**Runtime → Run all**. It writes into the same `out` folder:

| File | Use |
|---|---|
| `hub_prioritization_results_line_status.xlsx` / `.csv` | the results with the recomputed status columns; every other column is identical to the first run |
| `hub_line_status_detail.csv` | one row per hub and line: line ID, corrected ID, status code, text, year |
| `line_status_summary.csv` | per status code: lines, hubs, largest and mean count per hub |

Lines without a status are listed in step 6 of the notebook; add them to the status table or to
the corrections file and run again. Step 7 reports how many hubs differ from the status columns
written by `hubs run`.

## 7. Optional third step: map of the missing lines and hubs

`colab/hubs_missing_map.ipynb` runs **after** the first notebook, in its own Colab session. It
draws one map page of the lines and hubs that are in only one of the two networks (ours and the
planning agency's `MT_Network.gpkg`), with a verdict for each; see "Map of the missing lines and
hubs" in `docs/NETWORK_COMPARISON.md` for what the page shows and how the verdicts are decided.

Before you start:

- the output folder (`out`) of the first notebook must hold `hub_groups_all.csv` and
  `network_nodes.csv`; a run made before 2026-11-04 does not, so run the first notebook again;
- put the agency's `MT_Network.gpkg` (and optionally `MT_Network_MetaData.xlsx`) in one Drive
  folder, for example `HubRuns/agency`.

Open the notebook the same way as in section 2 and fill step 1:

| Box | What to type |
|---|---|
| `RUN_FOLDER` | the `out` folder of the first notebook (`HubRuns/2026_06/out`, or a full path) |
| `AGENCY_FOLDER`, `AGENCY_GPKG`, `AGENCY_META` | the agency folder and the two file names in it; leave the metadata name blank if there is none |
| `COMPARE_FOLDER` | blank = a folder `compare` inside the run folder; the comparison is written there (an existing one is overwritten unless `REDO_COMPARISON` is unticked) |
| `REDO_COMPARISON`, `COMPARE_ARGS` | on by default: `hubs compare-network` runs every time, so the map matches the run folder. Untick it to reuse a comparison that is already in the compare folder (it still runs if the files are missing). `COMPARE_ARGS` passes settings to it, e.g. `--set containment=false` or `--set full_cov=0.75` |
| `OUTPUT_FOLDER` | blank = the comparison folder |
| `RUN_NOTE` | the note about the data shown on the page; blank = built from the run's manifest |
| `INLINE_LEAFLET` | on = Leaflet is stored inside the page, so the page does not depend on a CDN (map tiles still need internet) |

Then **Runtime → Run all**. The notebook runs `hubs compare-network` (every time, unless you untick
`REDO_COMPARISON`), builds the page and writes, next to it, `missing_map_summary.md` (the counts per set
and verdict and the most important findings), which it also shows. Drive only shows the HTML
source of the page: run step 9 to download it, or download it from the Drive folder, and open it
in your browser.

## When something goes wrong

- **`STOP: the inputs are not complete`** — the message lists the exact file or column.
  Usually a missing file or a renamed column in the export.
- **`git clone failed`** — wrong repository name, wrong branch, or a token without read
  access to the repository.
- **Runtime disconnected / session expired** — Colab discards the virtual machine after
  idle time. Nothing in Drive is lost; **Runtime → Run all** again.
- **A run finished but you want different settings** — put them in `EXTRA_ARGS` in step 1,
  e.g. `--set mc_iterations=20000` or `--set spatial_source=shapefiles`, and run steps 5
  and 6 again. `docs/DEVIATIONS.md` lists the settings.
- **Node position conflicts** in step 4 are warnings, not errors: the run continues.
  `docs/full_documentation/06_manual_corrections.md` explains how to resolve them.
- **`h3_base is stale for 'taz' …`** — somebody replaced a reference shapefile (demographics,
  terminals, rings, districts) without rebuilding the H3 base layer. This needs a developer:
  in the repository run `hubs prepare-base` and commit the new `h3_base.parquet` and its
  manifest. Do not work around it with `on_stale_base_layer=warn` unless you accept results
  computed on the old data.

The notebooks are generated from `colab/build_notebook.py`; edit that file, run it, and commit
the `.ipynb` files with it if the cells need to change.
