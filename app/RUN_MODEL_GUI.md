# Run Model GUI

An interactive desktop application for running the full hub prioritization
pipeline without touching code. The interface is built with HTML/JS and rendered
in a **native window** via [pywebview](https://pywebview.flowrl.com/), so it can
open real OS folder/file pickers.

## What it does

1. **Select inputs** — either pick a single folder and let the app auto-detect
   every input file by name, or pick each file individually with a native
   "Browse…" dialog.
2. **Record who & why** — enter your name and free-text remarks describing the
   run.
3. **Run the pipeline** — outputs (CSV, GeoJSON, interactive map) are written to
   an output directory of your choice.
4. **Run log** — every run writes `run_log.json` and `run_log.txt` into the
   output folder, recording:
   - run id + start/finish timestamps + duration
   - who ran it and their remarks
   - every input file used, with size, last-modified time and SHA-256 checksum
   - the options used and the output files produced
   - a results summary (hub counts by tier) and success/error status

## Install

```bash
pip install -r requirements.txt
```

`pywebview` needs a rendering backend:

- **Windows** — uses the built-in Edge WebView2 (usually already present).
- **macOS** — uses the built-in WebKit (no extra install).
- **Linux** — install one backend, e.g.
  `pip install pyqt5 pyqtwebengine` **or** the system
  `python3-gi gir1.2-webkit2-4.1` packages.

## Run

```bash
python app/run_model_gui.py
```

## Input files

| Field | Required | Typical filename |
|-------|----------|------------------|
| Transit nodes (CSV) | ✅ | `All_nodes+lines.csv` |
| Lines & planned modes (CSV) | ✅ | `Lines_and_Planned_Mode.csv` |
| Demand forecast (Excel/CSV) | optional | `Demand_2050_all.xlsx` |
| Metro areas (SHP) | optional | `metro.shp` |
| Districts (SHP) | optional | `districts.shp` |
| TAZ zones / demographics (SHP) | optional | `TAZ_2050.shp` |
| Bus terminals (SHP) | optional | `bus_terminals.shp` |

Directory auto-detection matches files by extension and name keywords, so naming
your files close to the conventions above lets the app find them automatically.

## Output

Default output directory is `data/results/run_<timestamp>/`. Each run is
self-contained in its own folder, including the intermediate artefacts
(`processed/`), the final outputs, the streaming `run_<timestamp>.log`, and the
`run_log.json` / `run_log.txt` manifest.

## How it fits the code

The GUI is a thin front-end over `scripts/run_complete_pipeline.py`:

- `RunConfig` — describes one run (inputs, output dir, options, metadata).
- `run_pipeline(config)` — the shared entry point used by both the GUI and the
  command line (`python scripts/run_complete_pipeline.py`).
- `resolve_inputs_from_directory(dir)` — powers the folder auto-detect.

Running the script directly still works exactly as before, using the default
paths under `data/raw/`.
