"""Writes colab/hubs_run.ipynb, colab/hubs_line_status.ipynb and colab/hubs_missing_map.ipynb. Run `python colab/build_notebook.py` after editing the cells."""

import json
from pathlib import Path

CELLS = [
    (
        'markdown',
        """# Hub prioritization — run on Google Colab

Runs the `hubs` pipeline on one folder of model exports in your Google Drive and writes
`hub_prioritization_results.xlsx` (the display workbook) and `h3_layer.gpkg` next to it.

**Before you start** (see `docs/RUN_ON_COLAB.md` in the repository):
1. A Google Drive folder with the run's exports: `All_nodeslines_*.csv`,
   `Lines_and_Planned_Mode_*.csv`, `Nodes_w_results_*.xlsx`, and optionally
   `linesNames*.csv`, `lines_exploded*.csv`, `BS_lines*.csv`.
2. Access to the GitHub repository (a personal access token if it is private).
3. Optional: the network of מנהל התכנון (`MT_Network.gpkg`, and `MT_Network_MetaData.xlsx`) in a Drive folder.
   Then step 7 also compares the results with it (`hubs compare-network`).

Then **Runtime → Run all** and answer the prompts. Every cell prints what it did.""",
    ),
    (
        'code',
        """#@title 1. Settings { display-mode: "form" }
#@markdown Drive folder that holds this run's model exports: either relative to My Drive (`HubRuns/2026_06`) or a full path (`/content/drive/MyDrive/HubRuns/2026_06`):
INPUT_FOLDER = "HubRuns/2026_06"  #@param {type:"string"}
#@markdown Where to write the results (blank = a folder named `out` inside the input folder):
OUTPUT_FOLDER = ""  #@param {type:"string"}
#@markdown Reference folder (H3 base layer `h3_base.parquet` + its manifest, curated tables). Blank = the `data/reference` folder shipped with the code:
REFERENCE_FOLDER = ""  #@param {type:"string"}
#@markdown Repository and branch to run:
REPO = "oh-da/HubPrioritizing"  #@param {type:"string"}
BRANCH = "main"  #@param {type:"string"}
#@markdown Name of this run version (blank = the newest date among the exports, e.g. `2026-06-18`):
VERSION = ""  #@param {type:"string"}
#@markdown Extra settings for `hubs run`, e.g. `--set mc_iterations=20000` (normally blank):
EXTRA_ARGS = ""  #@param {type:"string"}
#@markdown Optional: compare the results with the network of מנהל התכנון. Drive folder that holds its `MT_Network.gpkg` (blank = skip the comparison), and the two file names in it (leave the metadata name blank if there is none):
AGENCY_FOLDER = ""  #@param {type:"string"}
AGENCY_GPKG = "MT_Network.gpkg"  #@param {type:"string"}
AGENCY_META = "MT_Network_MetaData.xlsx"  #@param {type:"string"}
#@markdown Where to write the comparison (blank = a folder named `compare` inside the output folder):
COMPARE_FOLDER = ""  #@param {type:"string"}
#@markdown Extra settings for `hubs compare-network`, e.g. `--set containment=false` or `--set full_cov=0.75` (normally blank):
COMPARE_ARGS = ""  #@param {type:"string"}

import os
DRIVE_ROOT = "/content/drive/MyDrive"

def drive_path(folder: str) -> str:
    \"\"\"Accept a path relative to My Drive or a full /content/... path.\"\"\"
    f = folder.strip().rstrip("/")
    if f.startswith("/content/"):
        return f
    return f"{DRIVE_ROOT}/{f.lstrip('/')}"

INPUT_DIR = drive_path(INPUT_FOLDER)
OUTPUT_DIR = drive_path(OUTPUT_FOLDER) if OUTPUT_FOLDER.strip() else f"{INPUT_DIR}/out"
REFERENCE_DIR = drive_path(REFERENCE_FOLDER) if REFERENCE_FOLDER.strip() else ""
REF_ARGS = ["--reference-dir", REFERENCE_DIR] if REFERENCE_DIR else []
AGENCY_DIR = drive_path(AGENCY_FOLDER) if AGENCY_FOLDER.strip() else ""
COMPARE_DIR = drive_path(COMPARE_FOLDER) if COMPARE_FOLDER.strip() else f"{OUTPUT_DIR}/compare"
print("input    :", INPUT_DIR)
print("output   :", OUTPUT_DIR)
print("reference:", REFERENCE_DIR or "(default: data/reference in the repository)")
print("מנהל התכנון:", AGENCY_DIR or "(none: the comparison with the network of מנהל התכנון is skipped)")""",
    ),
    (
        'code',
        """#@title 2. Connect Google Drive
from google.colab import drive
drive.mount("/content/drive")
import os
assert os.path.isdir(INPUT_DIR), f"Input folder not found: {INPUT_DIR}\\nCheck INPUT_FOLDER in step 1 (relative to My Drive, or a full /content/drive/MyDrive/... path)."
if REFERENCE_DIR:
    assert os.path.isdir(REFERENCE_DIR), f"Reference folder not found: {REFERENCE_DIR}\\nCheck REFERENCE_FOLDER in step 1, or leave it blank for the default."
    print("Files in the reference folder:")
    for name in sorted(os.listdir(REFERENCE_DIR)):
        print("  ", name)
print("Files in the input folder:")
for name in sorted(os.listdir(INPUT_DIR)):
    print("  ", name)""",
    ),
    (
        'code',
        """#@title 3. Get the code and install it (about 2 minutes)
import os, subprocess, sys, shutil
from getpass import getpass

token = ""
probe = subprocess.run(["git", "ls-remote", f"https://github.com/{REPO}.git"], capture_output=True, text=True)
if probe.returncode != 0:
    print("The repository is private (or the name is wrong). Paste a GitHub personal access token with read access to it:")
    token = getpass("token: ").strip()
url = f"https://{token}@github.com/{REPO}.git" if token else f"https://github.com/{REPO}.git"

if os.path.isdir("/content/HubPrioritizing"):
    shutil.rmtree("/content/HubPrioritizing")
r = subprocess.run(["git", "clone", "--depth", "1", "--branch", BRANCH, url, "/content/HubPrioritizing"], capture_output=True, text=True)
if r.returncode != 0:
    raise SystemExit("git clone failed:\\n" + r.stderr.replace(token, "***") + "\\nCheck REPO, BRANCH and the token.")
os.chdir("/content/HubPrioritizing")
print("cloned", REPO, "branch", BRANCH, "-", subprocess.run(["git", "log", "-1", "--format=%h %s"], capture_output=True, text=True).stdout.strip())

r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", "."], capture_output=True, text=True)
if r.returncode != 0:
    raise SystemExit("pip install failed:\\n" + r.stderr[-3000:])
print("installed. hubs version check:")
print(subprocess.run(["hubs", "--help"], capture_output=True, text=True).stdout.splitlines()[0])""",
    ),
    (
        'code',
        """#@title 4. Check the inputs (hubs validate)
import subprocess
r = subprocess.run(["hubs", "validate", "--input-dir", INPUT_DIR] + REF_ARGS, capture_output=True, text=True)
print(r.stdout)
if r.returncode != 0:
    print(r.stderr)
    raise SystemExit("\\nSTOP: the inputs are not complete. Fix the problems listed above in the Drive folder, then run this cell again.")
print("OK - inputs are valid. Continue with step 5.")""",
    ),
    (
        'code',
        """#@title 5. Run the pipeline (about 1 minute)
import subprocess, shlex, os
os.makedirs(OUTPUT_DIR, exist_ok=True)
cmd = ["hubs", "run", "--input-dir", INPUT_DIR, "--output-dir", OUTPUT_DIR] + REF_ARGS + (["--version", VERSION.strip()] if VERSION.strip() else []) + shlex.split(EXTRA_ARGS)
print(" ".join(shlex.quote(c) for c in cmd))
r = subprocess.run(cmd, capture_output=True, text=True)
print(r.stdout)
if r.returncode != 0:
    print(r.stderr[-4000:])
    raise SystemExit("STOP: the run failed. Read the message above; the log is in " + OUTPUT_DIR + "/run.log")""",
    ),
    (
        'code',
        """#@title 6. Results
import os, pandas as pd
from IPython.display import display
print("Files written to", OUTPUT_DIR)
for name in sorted(os.listdir(OUTPUT_DIR)):
    size = os.path.getsize(os.path.join(OUTPUT_DIR, name)) / 1e6
    print(f"  {name:40s} {size:6.1f} MB")

res = pd.read_csv(os.path.join(OUTPUT_DIR, "hub_prioritization_results.csv"))
print(f"\\n{len(res)} hubs. Hub types:", res["HubType"].value_counts().to_dict())
print("\\nTop 10 by TotalScore_MC:")
display(res.nsmallest(10, "Rank_TS_MC")[["group", "HubNameHE", "HubType", "Metro", "TotalScore_MC", "RankByHubTypeMetro"]])

report = open(os.path.join(OUTPUT_DIR, "run_report.md"), encoding="utf-8").read()
n_warn = report.count("⚠")
print(f"\\nThe run report has {n_warn} warning line(s): open run_report.md in the output folder and read them before publishing.")
print("\\nThe display workbook is hub_prioritization_results.xlsx in that folder. To download it now, run step 8.\\nNext (optional): step 7 compares with the network of מנהל התכנון; hubs_line_status.ipynb adds the line-status counts from a status table; hubs_missing_map.ipynb draws the map of the lines and hubs missing from either network.")""",
    ),
    (
        'code',
        """#@title 7. (Optional) Compare with the network of מנהל התכנון (hubs compare-network, about 10 seconds)
import os, shlex, subprocess

if not AGENCY_DIR:
    print("AGENCY_FOLDER is blank in step 1: no comparison with the network of מנהל התכנון.\\nFill it in (and AGENCY_GPKG / AGENCY_META) and run this cell to add it.")
else:
    gpkg = f"{AGENCY_DIR}/{AGENCY_GPKG.strip()}"
    meta = f"{AGENCY_DIR}/{AGENCY_META.strip()}" if AGENCY_META.strip() else ""
    missing = [p for p in (gpkg, meta) if p and not os.path.isfile(p)]
    if missing:
        raise SystemExit("STOP: not found in Drive:\\n  " + "\\n  ".join(missing) + "\\nCheck AGENCY_FOLDER, AGENCY_GPKG and AGENCY_META in step 1.")
    os.makedirs(COMPARE_DIR, exist_ok=True)
    cmd = ["hubs", "compare-network", "--run", OUTPUT_DIR, "--agency-gpkg", gpkg] + (["--agency-meta", meta] if meta else []) + ["--out", COMPARE_DIR] + shlex.split(COMPARE_ARGS)
    print(" ".join(shlex.quote(c) for c in cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr[-4000:])
        raise SystemExit("STOP: the comparison failed. Read the message above.")
    print("The comparison is in", COMPARE_DIR, "- open network_comparison.xlsx there.\\nFor a map of the lines and hubs missing from either network, run hubs_missing_map.ipynb.")""",
    ),
    (
        'code',
        """#@title 8. (Optional) Download the workbook to this computer
from google.colab import files
import os
files.download(os.path.join(OUTPUT_DIR, "hub_prioritization_results.xlsx"))""",
    ),
]


# ----------------------------------------------------------------------------------------
# Second notebook: line-status columns, run after hubs_run.ipynb
# ----------------------------------------------------------------------------------------

# Steps 2 (Drive) and 3 (clone + install) are the same as in the first notebook.
assert CELLS[3][1].startswith("#@title 3. Get the code")
INSTALL_CELL = CELLS[3]
# hubs_line_status.ipynb keeps its own (older, relative-path) connect cell: its settings take no full paths.
CONNECT_CELL = (
    "code",
    """#@title 2. Connect Google Drive
from google.colab import drive
drive.mount("/content/drive")
import os
assert os.path.isdir(INPUT_DIR), f"Input folder not found: {INPUT_DIR}\\nCheck INPUT_FOLDER in step 1 (it is relative to MyDrive)."
print("Files in the input folder:")
for name in sorted(os.listdir(INPUT_DIR)):
    print("  ", name)""",
)

STATUS_CELLS = [
    (
        "markdown",
        """# Hub prioritization — line-status columns (second step)

Run this **after** `hubs_run.ipynb`. It reads that run's `hub_prioritization_results.csv`, looks up the
planning status (0-7) of every line that serves each hub in a line-status table, and writes:

| File (in the output folder) | What it is |
|---|---|
| `hub_prioritization_results_line_status.csv` / `.xlsx` | the results with `NumLinesStatus_0` ... `NumLinesStatus_7` and `TotalLinesAllStatuses` recomputed from this status table |
| `hub_line_status_detail.csv` | one row per hub and line: line ID, corrected ID, status code, status text, year |
| `line_status_summary.csv` | per status code: lines, hubs, largest count in one hub |

The status table only fills these display columns. It does not change eligibility, tiers, scores or ranks.

**Before you start:** run `hubs_run.ipynb` on the same folders, and put the line-status table in the input
folder: `line_status*.csv` (or `lines_exploded*.csv`) with columns `LineName` and `StatusID` / `Status Id`;
optional `Status` (text) and `Year`. A `BS_lines*.csv` with `LineName, LineName_Correct` fixes misspelled line IDs first.

Then **Runtime → Run all**.""",
    ),
    (
        "code",
        """#@title 1. Settings { display-mode: "form" }
#@markdown The same Drive folders as in step 1 of `hubs_run.ipynb`:
INPUT_FOLDER = "HubRuns/2026_06"  #@param {type:"string"}
OUTPUT_FOLDER = ""  #@param {type:"string"}
#@markdown File name of the line-status table inside the input folder (blank = the newest `line_status*.csv`, else `lines_exploded*.csv`):
STATUS_FILE = ""  #@param {type:"string"}
#@markdown File name of the line-name corrections inside the input folder (blank = `BS_lines*.csv` / `line_name_corrections*.csv` if present):
CORRECTIONS_FILE = ""  #@param {type:"string"}
#@markdown Also write the workbook (.xlsx), not only the CSV:
WRITE_XLSX = True  #@param {type:"boolean"}
#@markdown Repository and branch to take the code from (use the same as in the first notebook):
REPO = "oh-da/HubPrioritizing"  #@param {type:"string"}
BRANCH = "main"  #@param {type:"string"}

import os
INPUT_DIR = f"/content/drive/MyDrive/{INPUT_FOLDER.strip('/')}"
OUTPUT_DIR = f"/content/drive/MyDrive/{OUTPUT_FOLDER.strip('/')}" if OUTPUT_FOLDER.strip() else f"{INPUT_DIR}/out"
print("input :", INPUT_DIR)
print("output:", OUTPUT_DIR)""",
    ),
    CONNECT_CELL,
    INSTALL_CELL,
    (
        "code",
        """#@title 4. Find the results and the status table
import os, glob

RESULTS_CSV = os.path.join(OUTPUT_DIR, "hub_prioritization_results.csv")
if not os.path.isfile(RESULTS_CSV):
    raise SystemExit(f"STOP: {RESULTS_CSV} not found.\\nRun hubs_run.ipynb first, with the same INPUT_FOLDER / OUTPUT_FOLDER: this notebook adds to its results.")

def find(explicit, patterns, what):
    if explicit.strip():
        path = os.path.join(INPUT_DIR, explicit.strip())
        if not os.path.isfile(path):
            raise SystemExit(f"STOP: {what} file not found: {path}")
        return path
    for pattern in patterns:
        hits = sorted(glob.glob(os.path.join(INPUT_DIR, pattern)))
        if hits:
            return hits[-1]
    return None

STATUS_PATH = find(STATUS_FILE, ("line_status*.csv", "lines_exploded*.csv"), "line status")
if STATUS_PATH is None:
    raise SystemExit(f"STOP: no line-status table in {INPUT_DIR}.\\nPut line_status.csv (or lines_exploded.csv) there: columns LineName and StatusID / Status Id, optional Status and Year.")
CORRECTIONS_PATH = find(CORRECTIONS_FILE, ("BS_lines*.csv", "line_name_corrections*.csv"), "line corrections")

print("results    :", RESULTS_CSV)
print("line status:", STATUS_PATH)
print("corrections:", CORRECTIONS_PATH or "(none)")""",
    ),
    (
        "code",
        """#@title 5. Read the status table, the corrections and the results
import sys
import pandas as pd
from IPython.display import display

sys.path.insert(0, "/content/HubPrioritizing")
from src.pipeline.inputs import read_csv_auto
from src.pipeline.postprocess import STATUS_IDS, load_line_corrections, load_line_status, parse_line_unique
from src.pipeline.report import RunReport

report = RunReport()

raw, encoding = read_csv_auto(STATUS_PATH)
try:
    status = load_line_status(raw, report)  # LineName -> StatusID; the last row wins when a line repeats
except ValueError as exc:
    raise SystemExit(f"STOP: {exc}")
print(f"{os.path.basename(STATUS_PATH)} ({encoding}): {len(status)} lines with a status")

# Optional text and year columns of the status table.
def clean(value):
    return str(value).replace("\\r", "").replace("\\n", "").strip().strip("\\\\").strip()

columns = {str(c).strip().lower().replace(" ", "").replace("_", ""): c for c in raw.columns}
text_col, year_col, id_col, name_col = columns.get("status"), columns.get("year"), columns["statusid"], columns["linename"]
status_text, line_year = {}, {}
for _, row in raw.iterrows():
    sid = pd.to_numeric(row[id_col], errors="coerce")
    if pd.isna(sid):
        continue
    if text_col is not None and pd.notna(row[text_col]):
        status_text.setdefault(int(sid), str(row[text_col]).strip())
    if year_col is not None and pd.notna(row[year_col]):
        line_year[clean(row[name_col])] = row[year_col]

used = pd.Series(list(status.values())).value_counts().sort_index()
print("lines per status code:", used.to_dict())
outside = sorted(set(used.index) - set(STATUS_IDS))
if outside:
    print(f"WARNING: status codes {outside} are outside 0-7; their lines are listed in the detail table but not counted in NumLinesStatus_*.")
if status_text:
    display(pd.DataFrame({"StatusID": list(status_text), "Status": list(status_text.values())}).sort_values("StatusID"))

corrections = {}
if CORRECTIONS_PATH:
    corrections_df, _ = read_csv_auto(CORRECTIONS_PATH)
    corrections = load_line_corrections(corrections_df)
    print(f"{os.path.basename(CORRECTIONS_PATH)}: {len(corrections)} corrections")

res = pd.read_csv(RESULTS_CSV, float_precision="round_trip")  # scores come back bit-for-bit
for needed in ("group", "Line_Unique"):
    if needed not in res.columns:
        raise SystemExit(f"STOP: the results file has no {needed} column; is it hub_prioritization_results.csv from hubs run?")
print(f"results: {len(res)} hubs")

for entry in report.warnings:
    print("WARNING:", entry.message)
    if entry.data.get("lines"):
        print("   ", ", ".join(entry.data["lines"][:10]))""",
    ),
    (
        "code",
        """#@title 6. Match every line of every hub to its status
rows = []
for _, hub in res.iterrows():
    for line_id in parse_line_unique(hub["Line_Unique"]):
        fixed = corrections.get(line_id, line_id)  # spelling fix first, as in hubs run
        sid = status.get(fixed, status.get(line_id))
        rows.append({
            "group": hub["group"],
            "HubNameHE": hub.get("HubNameHE"),
            "HubType": hub.get("HubType"),
            "LineID": line_id,
            "LineID_Corrected": fixed,
            "StatusID": sid,
            "Status": status_text.get(sid) if sid is not None else None,
            "Year": line_year.get(fixed, line_year.get(line_id)),
        })
detail = pd.DataFrame(rows)
detail["StatusID"] = detail["StatusID"].astype("Int64")

def year_text(y):  # 2040.0 -> "2040"; text years stay as they are
    if pd.isna(y):
        return ""
    return str(int(y)) if isinstance(y, (int, float)) and float(y).is_integer() else str(y)

detail["Year"] = detail["Year"].map(year_text)

unmatched = detail[detail["StatusID"].isna()]
print(f"{len(detail)} hub-line pairs, {detail['LineID'].nunique()} distinct lines")
if len(unmatched):
    print(f"WARNING: {len(unmatched)} pairs ({len(unmatched) / len(detail):.1%}) have no status; {unmatched['LineID'].nunique()} distinct lines. Add them to the status table or to the corrections file:")
    print("  ", ", ".join(sorted(unmatched["LineID"].unique())[:40]))
else:
    print("every line has a status")""",
    ),
    (
        "code",
        """#@title 7. Count lines per status and compare with the run
counted = detail.dropna(subset=["StatusID"])
per_hub = counted.groupby(["group", "StatusID"]).size().unstack(fill_value=0)
status_cols = [f"NumLinesStatus_{sid}" for sid in STATUS_IDS]

previous = res[status_cols + ["TotalLinesAllStatuses"]].copy() if set(status_cols) <= set(res.columns) else None
for sid, col in zip(STATUS_IDS, status_cols):
    res[col] = res["group"].map(per_hub[sid] if sid in per_hub.columns else pd.Series(dtype=int)).fillna(0).astype(int)
res["TotalLinesAllStatuses"] = res[status_cols].sum(axis=1)

if previous is not None:
    changed = (previous.fillna(0).astype(int).values != res[status_cols + ["TotalLinesAllStatuses"]].values).any(axis=1)
    print(f"{int(changed.sum())} of {len(res)} hubs differ from the status columns written by hubs run")
    if changed.any():
        display(res.loc[changed, ["group", "HubNameHE"] + status_cols + ["TotalLinesAllStatuses"]].head(20))

summary = []
for sid, col in zip(STATUS_IDS, status_cols):
    n = res[col]
    summary.append({
        "StatusID": sid,
        "Status": status_text.get(sid, ""),
        "Lines": int(counted.loc[counted["StatusID"] == sid, "LineID"].nunique()),
        "LinesInHubs": int(n.sum()),
        "Hubs": int((n > 0).sum()),
        "MaxPerHub": int(n.max()),
        "MeanPerHub": round(float(n[n > 0].mean()), 2) if (n > 0).any() else 0.0,
    })
summary = pd.DataFrame(summary)
display(summary)""",
    ),
    (
        "code",
        """#@title 8. Write the results
from src.pipeline.export import FINAL_COLUMNS, LIST_COLUMNS, write_results_xlsx

base = os.path.join(OUTPUT_DIR, "hub_prioritization_results_line_status")
res.to_csv(base + ".csv", index=False, encoding="utf-8-sig")
written = [base + ".csv"]
if WRITE_XLSX:
    res[list(LIST_COLUMNS)] = res[list(LIST_COLUMNS)].fillna("")  # empty lists come back from the CSV as NaN
    extras = [c for c in res.columns if c not in FINAL_COLUMNS]
    write_results_xlsx(res, base + ".xlsx", extra_columns=extras)
    written.append(base + ".xlsx")
detail.to_csv(os.path.join(OUTPUT_DIR, "hub_line_status_detail.csv"), index=False, encoding="utf-8-sig")
summary.to_csv(os.path.join(OUTPUT_DIR, "line_status_summary.csv"), index=False, encoding="utf-8-sig")
written += [os.path.join(OUTPUT_DIR, "hub_line_status_detail.csv"), os.path.join(OUTPUT_DIR, "line_status_summary.csv")]

print("Written to", OUTPUT_DIR)
for path in written:
    print(f"  {os.path.basename(path):50s} {os.path.getsize(path) / 1e6:6.2f} MB")""",
    ),
    (
        "code",
        """#@title 9. (Optional) Download the workbook to this computer
from google.colab import files
files.download(base + (".xlsx" if WRITE_XLSX else ".csv"))""",
    ),
]


# ----------------------------------------------------------------------------------------
# Third notebook: map of the missing lines and hubs, run after hubs_run.ipynb
# ----------------------------------------------------------------------------------------

MAP_CELLS = [
    (
        "markdown",
        """# Hub prioritization — map of the missing lines and hubs

Draws **one map page** (`missing_lines_hubs_map.html`) of the lines and hubs that exist in only one of two
networks: the one of the hub prioritization pipeline and the one of מנהל התכנון (`MT_Network.gpkg`). Every item has a
verdict (likely real gap, covered elsewhere, definition difference, check). It also writes
`missing_map_summary.md` with the counts and the most important findings.

**Before you start** (see `docs/NETWORK_COMPARISON.md`, "Map of the missing lines and hubs"):
1. Run `hubs_run.ipynb` first. Its output folder (the one that holds `hub_groups_all.csv` and
   `network_nodes.csv`) is `RUN_FOLDER` below. A run made before 2026-11-04 does not have those two files:
   run it again.
2. Put the `MT_Network.gpkg` of מנהל התכנון (and, optionally, `MT_Network_MetaData.xlsx`) in one Drive folder.
3. The comparison itself (`hubs compare-network`) is run by this notebook, every time unless you untick `REDO_COMPARISON`.

Then **Runtime → Run all**. Every cell prints what it did.""",
    ),
    (
        "code",
        """#@title 1. Settings { display-mode: "form" }
#@markdown Drive folder with the output of `hubs_run.ipynb` (the `out` folder): either relative to My Drive (`HubRuns/2026_06/out`) or a full path (`/content/drive/MyDrive/HubRuns/2026_06/out`):
RUN_FOLDER = "HubRuns/2026_06/out"  #@param {type:"string"}
#@markdown Drive folder with the network of מנהל התכנון (same two path forms), and the two file names in it (leave the metadata name blank if there is none):
AGENCY_FOLDER = "HubRuns/agency"  #@param {type:"string"}
AGENCY_GPKG = "MT_Network.gpkg"  #@param {type:"string"}
AGENCY_META = "MT_Network_MetaData.xlsx"  #@param {type:"string"}
#@markdown Where the comparison (the output of `hubs compare-network`) is, or will be written (blank = a folder named `compare` inside the run folder):
COMPARE_FOLDER = ""  #@param {type:"string"}
#@markdown Run `hubs compare-network` every time, so the map always matches the run folder (untick it to reuse a comparison that is already in the compare folder):
REDO_COMPARISON = True  #@param {type:"boolean"}
#@markdown Extra settings for `hubs compare-network`, e.g. `--set containment=false` or `--set full_cov=0.75` (normally blank):
COMPARE_ARGS = ""  #@param {type:"string"}
#@markdown Where to write the map and its summary (blank = the comparison folder):
OUTPUT_FOLDER = ""  #@param {type:"string"}
#@markdown The note about the data shown on the map page (blank = built from the run's manifest):
RUN_NOTE = ""  #@param {type:"string"}
#@markdown Store Leaflet inside the page, so the page does not depend on a CDN (the map tiles still need internet):
INLINE_LEAFLET = True  #@param {type:"boolean"}
#@markdown Repository and branch to take the code from (use the same as in `hubs_run.ipynb`):
REPO = "oh-da/HubPrioritizing"  #@param {type:"string"}
BRANCH = "main"  #@param {type:"string"}

import os
DRIVE_ROOT = "/content/drive/MyDrive"

def drive_path(folder: str) -> str:
    # accept a path relative to My Drive or a full /content/... path
    f = folder.strip().rstrip("/")
    if f.startswith("/content/"):
        return f
    return f"{DRIVE_ROOT}/{f.lstrip('/')}"

RUN_DIR = drive_path(RUN_FOLDER)
AGENCY_GPKG_PATH = f"{drive_path(AGENCY_FOLDER)}/{AGENCY_GPKG.strip()}"
AGENCY_META_PATH = f"{drive_path(AGENCY_FOLDER)}/{AGENCY_META.strip()}" if AGENCY_META.strip() else ""
COMPARE_DIR = drive_path(COMPARE_FOLDER) if COMPARE_FOLDER.strip() else f"{RUN_DIR}/compare"
OUTPUT_DIR = drive_path(OUTPUT_FOLDER) if OUTPUT_FOLDER.strip() else COMPARE_DIR
print("hubs run output :", RUN_DIR)
print("מנהל התכנון network :", AGENCY_GPKG_PATH)
print("מנהל התכנון metadata:", AGENCY_META_PATH or "(none)")
print("comparison      :", COMPARE_DIR)
print("map written to  :", OUTPUT_DIR)""",
    ),
    (
        "code",
        """#@title 2. Connect Google Drive
from google.colab import drive
drive.mount("/content/drive")
import os
assert os.path.isdir(RUN_DIR), f"Run folder not found: {RUN_DIR}\\nCheck RUN_FOLDER in step 1 (relative to My Drive, or a full path)."
print("Files in the run folder:")
for name in sorted(os.listdir(RUN_DIR)):
    print("  ", name)""",
    ),
    INSTALL_CELL,
    (
        "code",
        """#@title 4. Check the inputs
import os, json

problems = []
for name in ("hub_groups_all.csv", "network_nodes.csv"):
    if not os.path.isfile(f"{RUN_DIR}/{name}"):
        problems.append(f"{RUN_DIR}/{name} is missing: run hubs_run.ipynb (again) on the same exports; this version of the code writes it.")
if not os.path.isfile(AGENCY_GPKG_PATH):
    problems.append(f"{AGENCY_GPKG_PATH} is missing: check AGENCY_FOLDER and AGENCY_GPKG in step 1.")
if AGENCY_META_PATH and not os.path.isfile(AGENCY_META_PATH):
    problems.append(f"{AGENCY_META_PATH} is missing: fix AGENCY_META in step 1, or leave it blank.")
if problems:
    raise SystemExit("STOP:\\n  " + "\\n  ".join(problems))

manifest = f"{RUN_DIR}/run_manifest.json"
if os.path.isfile(manifest):
    info = json.load(open(manifest, encoding="utf-8"))
    print("run version:", info.get("version"), "| created:", info.get("created"))
print("OK - the inputs are there. Continue with step 5.")""",
    ),
    (
        "code",
        """#@title 5. Compare the two networks (hubs compare-network, about 10 seconds)
import os, shlex, subprocess

xlsx, gpkg = f"{COMPARE_DIR}/network_comparison.xlsx", f"{COMPARE_DIR}/network_comparison.gpkg"
if REDO_COMPARISON or not (os.path.isfile(xlsx) and os.path.isfile(gpkg)):
    os.makedirs(COMPARE_DIR, exist_ok=True)
    cmd = ["hubs", "compare-network", "--run", RUN_DIR, "--agency-gpkg", AGENCY_GPKG_PATH]
    if AGENCY_META_PATH:
        cmd += ["--agency-meta", AGENCY_META_PATH]
    cmd += ["--out", COMPARE_DIR] + shlex.split(COMPARE_ARGS)
    print(" ".join(shlex.quote(c) for c in cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr[-4000:])
        raise SystemExit("STOP: the comparison failed. Read the message above.")
else:
    print("REDO_COMPARISON is off: using the comparison that is already in", COMPARE_DIR, "(tick it in step 1 to run the comparison again).")""",
    ),
    (
        "code",
        """#@title 6. Leaflet for the page
import os, urllib.request

LEAFLET_DIR = ""
if INLINE_LEAFLET:
    target = "/content/leaflet"
    os.makedirs(target, exist_ok=True)
    sources = [
        "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/",
        "https://unpkg.com/leaflet@1.9.4/dist/",
        "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/",
    ]
    for base in sources:
        try:
            for name in ("leaflet.js", "leaflet.css"):
                urllib.request.urlretrieve(base + name, f"{target}/{name}")
            assert os.path.getsize(f"{target}/leaflet.js") > 100_000 and os.path.getsize(f"{target}/leaflet.css") > 10_000
            LEAFLET_DIR = target
            print("Leaflet 1.9.4 downloaded from", base, "- it will be stored inside the page.")
            break
        except Exception as exc:
            print("could not use", base, "-", exc)
    if not LEAFLET_DIR:
        print("Leaflet could not be downloaded; the page will load it from the CDN instead (that needs internet when you open it).")
else:
    print("The page will load Leaflet from the CDN (cdnjs) when you open it.")""",
    ),
    (
        "code",
        """#@title 7. Build the map (about 20 seconds)
import os, shlex, subprocess, sys

os.makedirs(OUTPUT_DIR, exist_ok=True)
cmd = [sys.executable, "scripts/build_missing_map.py", "--compare-dir", COMPARE_DIR, "--run-dir", RUN_DIR,
       "--agency-gpkg", AGENCY_GPKG_PATH, "--out-dir", OUTPUT_DIR]
if AGENCY_META_PATH:
    cmd += ["--agency-meta", AGENCY_META_PATH]
if LEAFLET_DIR:
    cmd += ["--leaflet-dir", LEAFLET_DIR]
if RUN_NOTE.strip():
    cmd += ["--run-note", RUN_NOTE.strip()]
print(" ".join(shlex.quote(c) for c in cmd))
r = subprocess.run(cmd, capture_output=True, text=True)
print(r.stdout)
if r.returncode != 0:
    print(r.stderr[-4000:])
    raise SystemExit("STOP: the map could not be built. Read the message above.")""",
    ),
    (
        "code",
        """#@title 8. Results
import os
from IPython.display import Markdown, display

html_path = f"{OUTPUT_DIR}/missing_lines_hubs_map.html"
summary_path = f"{OUTPUT_DIR}/missing_map_summary.md"
for path in (html_path, summary_path):
    print(f"{os.path.basename(path):34s} {os.path.getsize(path) / 1e6:6.2f} MB   {path}")
print("\\nTo look at the map: run step 9 to download the page and open it in your browser (Drive only shows the HTML source).")
display(Markdown(open(summary_path, encoding="utf-8").read()))""",
    ),
    (
        "code",
        """#@title 9. (Optional) Download the map page and the summary to this computer
from google.colab import files
files.download(html_path)
files.download(summary_path)""",
    ),
]


def build(cells=CELLS, name="hubs_run.ipynb") -> dict:
    out = []
    for kind, source in cells:
        cell = {"cell_type": kind, "metadata": {}, "source": source}
        if kind == "code":
            cell.update({"execution_count": None, "outputs": []})
        out.append(cell)
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "colab": {"name": name, "provenance": []},
            "kernelspec": {"name": "python3", "display_name": "Python 3"},
            "language_info": {"name": "python"},
        },
        "cells": out,
    }


if __name__ == "__main__":
    for cells, name in ((CELLS, "hubs_run.ipynb"), (STATUS_CELLS, "hubs_line_status.ipynb"), (MAP_CELLS, "hubs_missing_map.ipynb")):
        out = Path(__file__).with_name(name)
        out.write_text(json.dumps(build(cells, name), ensure_ascii=False, indent=1), encoding="utf-8")
        print("wrote", out)
