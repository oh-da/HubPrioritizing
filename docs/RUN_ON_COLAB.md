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

The first cell is a form with four boxes:

| Box | What to type |
|---|---|
| `INPUT_FOLDER` | the Drive folder from section 1, relative to My Drive, e.g. `HubRuns/2026_06` |
| `OUTPUT_FOLDER` | leave blank; results go to a folder named `out` inside the input folder |
| `VERSION` | a name for this run, e.g. `2026-06`; blank = the newest date in the export file names |
| `REPO`, `BRANCH` | leave as they are unless you were told otherwise |
| `EXTRA_ARGS` | leave blank |

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

Step 5 runs the pipeline. Step 6 lists the files it wrote and the top ten hubs.

## 5. Collect the results

In Drive, open the `out` folder inside your input folder:

| File | Use |
|---|---|
| `hub_prioritization_results.xlsx` | the workbook the display page reads |
| `hub_prioritization_results.csv` | the same table as CSV |
| `h3_layer.gpkg` | the H3 cell layer for QGIS / ArcGIS / SQL |
| `run_report.md` | every data-quality finding; read the warnings before publishing |
| `run_manifest.json` | the version record: which files, which settings, which code (`docs/VERSIONS.md`) |
| `hub_identity.csv`, `run_config.json`, `run.log` | traceability |

To see what changed since an earlier run, keep each run in its own folder and, in a Colab
cell after step 5, run `!hubs compare "/content/drive/MyDrive/HubRuns/2026_03/out" "$OUTPUT_DIR"`;
the report lands next to the new results.

Step 7 downloads the workbook to your computer straight away if you prefer.

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
