"""Writes colab/hubs_run.ipynb and colab/hubs_line_status.ipynb. Run `python colab/build_notebook.py` after editing the cells."""

import json
from pathlib import Path

CELLS = [
    (
        "markdown",
        """# Hub prioritization — run on Google Colab

Runs the `hubs` pipeline on one folder of model exports in your Google Drive and writes
`hub_prioritization_results.xlsx` (the display workbook) and `h3_layer.gpkg` next to it.

**Before you start** (see `docs/RUN_ON_COLAB.md` in the repository):
1. A Google Drive folder with the run's exports: `All_nodeslines_*.csv`,
   `Lines_and_Planned_Mode_*.csv`, `Nodes_w_results_*.xlsx`, and optionally
   `linesNames*.csv`, `lines_exploded*.csv`, `BS_lines*.csv`.
2. Access to the GitHub repository (a personal access token if it is private).

Then **Runtime → Run all** and answer the prompts. Every cell prints what it did.""",
    ),
    (
        "code",
        """#@title 1. Settings { display-mode: "form" }
#@markdown Path of the Drive folder that holds this run's model exports (as shown in the Drive file browser, after `MyDrive/`):
INPUT_FOLDER = "HubRuns/2026_06"  #@param {type:"string"}
#@markdown Where to write the results (blank = a folder named `out` inside the input folder):
OUTPUT_FOLDER = ""  #@param {type:"string"}
#@markdown Repository and branch to run:
REPO = "oh-da/HubPrioritizing"  #@param {type:"string"}
BRANCH = "main"  #@param {type:"string"}
#@markdown Name of this run version (blank = the newest date among the exports, e.g. `2026-06-18`):
VERSION = ""  #@param {type:"string"}
#@markdown Extra settings for `hubs run`, e.g. `--set mc_iterations=20000` (normally blank):
EXTRA_ARGS = ""  #@param {type:"string"}

import os
INPUT_DIR = f"/content/drive/MyDrive/{INPUT_FOLDER.strip('/')}"
OUTPUT_DIR = f"/content/drive/MyDrive/{OUTPUT_FOLDER.strip('/')}" if OUTPUT_FOLDER.strip() else f"{INPUT_DIR}/out"
print("input :", INPUT_DIR)
print("output:", OUTPUT_DIR)""",
    ),
    (
        "code",
        """#@title 2. Connect Google Drive
from google.colab import drive
drive.mount("/content/drive")
import os
assert os.path.isdir(INPUT_DIR), f"Input folder not found: {INPUT_DIR}\\nCheck INPUT_FOLDER in step 1 (it is relative to MyDrive)."
print("Files in the input folder:")
for name in sorted(os.listdir(INPUT_DIR)):
    print("  ", name)""",
    ),
    (
        "code",
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
        "code",
        """#@title 4. Check the inputs (hubs validate)
import subprocess
r = subprocess.run(["hubs", "validate", "--input-dir", INPUT_DIR], capture_output=True, text=True)
print(r.stdout)
if r.returncode != 0:
    print(r.stderr)
    raise SystemExit("\\nSTOP: the inputs are not complete. Fix the problems listed above in the Drive folder, then run this cell again.")
print("OK - inputs are valid. Continue with step 5.")""",
    ),
    (
        "code",
        """#@title 5. Run the pipeline (about 1 minute)
import subprocess, shlex, os
os.makedirs(OUTPUT_DIR, exist_ok=True)
cmd = ["hubs", "run", "--input-dir", INPUT_DIR, "--output-dir", OUTPUT_DIR] + (["--version", VERSION.strip()] if VERSION.strip() else []) + shlex.split(EXTRA_ARGS)
print(" ".join(shlex.quote(c) for c in cmd))
r = subprocess.run(cmd, capture_output=True, text=True)
print(r.stdout)
if r.returncode != 0:
    print(r.stderr[-4000:])
    raise SystemExit("STOP: the run failed. Read the message above; the log is in " + OUTPUT_DIR + "/run.log")""",
    ),
    (
        "code",
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
print("\\nThe display workbook is hub_prioritization_results.xlsx in that folder. To download it now, run step 7.\\nNext (optional): hubs_line_status.ipynb adds the line-status counts from a status table.")""",
    ),
    (
        "code",
        """#@title 7. (Optional) Download the workbook to this computer
from google.colab import files
import os
files.download(os.path.join(OUTPUT_DIR, "hub_prioritization_results.xlsx"))""",
    ),
]


# ----------------------------------------------------------------------------------------
# Second notebook: line-status columns, run after hubs_run.ipynb
# ----------------------------------------------------------------------------------------

# Steps 2 (Drive) and 3 (clone + install) are the same as in the first notebook.
assert CELLS[2][1].startswith("#@title 2. Connect Google Drive") and CELLS[3][1].startswith("#@title 3. Get the code")
CONNECT_CELL, INSTALL_CELL = CELLS[2], CELLS[3]

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
    for cells, name in ((CELLS, "hubs_run.ipynb"), (STATUS_CELLS, "hubs_line_status.ipynb")):
        out = Path(__file__).with_name(name)
        out.write_text(json.dumps(build(cells, name), ensure_ascii=False, indent=1), encoding="utf-8")
        print("wrote", out)
