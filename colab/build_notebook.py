"""Writes colab/hubs_run.ipynb. Run `python colab/build_notebook.py` after editing the cells."""

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
print("\\nThe display workbook is hub_prioritization_results.xlsx in that folder. To download it now, run step 7.")""",
    ),
    (
        "code",
        """#@title 7. (Optional) Download the workbook to this computer
from google.colab import files
import os
files.download(os.path.join(OUTPUT_DIR, "hub_prioritization_results.xlsx"))""",
    ),
]


def build() -> dict:
    cells = []
    for kind, source in CELLS:
        cell = {"cell_type": kind, "metadata": {}, "source": source}
        if kind == "code":
            cell.update({"execution_count": None, "outputs": []})
        cells.append(cell)
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "colab": {"name": "hubs_run.ipynb", "provenance": []},
            "kernelspec": {"name": "python3", "display_name": "Python 3"},
            "language_info": {"name": "python"},
        },
        "cells": cells,
    }


if __name__ == "__main__":
    out = Path(__file__).with_name("hubs_run.ipynb")
    out.write_text(json.dumps(build(), ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", out)
