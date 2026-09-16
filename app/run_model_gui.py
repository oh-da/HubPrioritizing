"""
Hub Prioritization - Run Model GUI
==================================

An interactive desktop GUI (HTML/JS rendered in a native window via pywebview)
for running the full hub prioritization pipeline.

Features
--------
* Native OS folder / file pickers for selecting inputs.
* Select a single directory and have the app auto-detect all input files,
  or pick each file individually.
* Enter who is running the model and free-text remarks.
* Choose an output directory; every run writes its outputs there together
  with a run log (run_log.json / run_log.txt) recording which files were used,
  timestamps, who ran it, the remarks, and the outputs produced.
* Live log streaming while the pipeline runs.

Run with:
    python app/run_model_gui.py
"""

import sys
import json
import logging
import threading
from pathlib import Path
from datetime import datetime

# --- Make the project importable ---------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import webview  # pywebview
except ImportError:
    print("ERROR: pywebview is not installed.\n"
          "Install it with:  pip install pywebview\n"
          "(On Linux you may also need a backend, e.g. PyGObject + WebKit2GTK,\n"
          " or pyqt5/pyqtwebengine.)")
    sys.exit(1)

# Import the pipeline. NOTE: importing this module runs a dependency check that
# may prompt on the console if core packages are missing - install
# requirements.txt first.
from scripts.run_complete_pipeline import (
    RunConfig,
    run_pipeline,
    resolve_inputs_from_directory,
    INPUT_FILE_HINTS,
    REQUIRED_INPUTS,
    logger as pipeline_logger,
)
from src.config import RESULTS_DIR

GUI_DIR = Path(__file__).resolve().parent / "gui"

# Ordered list of input fields shown in the GUI (field, label, required)
INPUT_FIELDS = [
    ("transit_nodes", "Transit nodes (CSV)", True),
    ("lines_modes", "Lines & planned modes (CSV)", True),
    ("demand", "Demand forecast (Excel/CSV)", False),
    ("metro_areas", "Metro areas (SHP)", False),
    ("districts", "Districts (SHP)", False),
    ("taz_zones", "TAZ zones / demographics (SHP)", False),
    ("bus_terminals", "Bus terminals (SHP)", False),
]

# File-type filters for the native open dialog, per field
FILE_TYPES = {
    "transit_nodes": ("CSV files (*.csv)", "All files (*.*)"),
    "lines_modes": ("CSV files (*.csv)", "All files (*.*)"),
    "demand": ("Spreadsheet (*.xlsx;*.xls;*.csv)", "All files (*.*)"),
    "metro_areas": ("Shapefile (*.shp)", "All files (*.*)"),
    "districts": ("Shapefile (*.shp)", "All files (*.*)"),
    "taz_zones": ("Shapefile (*.shp)", "All files (*.*)"),
    "bus_terminals": ("Shapefile (*.shp)", "All files (*.*)"),
}


class _LogCapture(logging.Handler):
    """Logging handler that buffers formatted records for the GUI to poll."""

    def __init__(self, sink):
        super().__init__(level=logging.INFO)
        self._sink = sink
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record):
        try:
            self._sink(self.format(record))
        except Exception:
            pass


class Api:
    """Methods exposed to the JavaScript front-end via pywebview."""

    def __init__(self):
        self.window = None
        self._lock = threading.Lock()
        self._log_lines = []
        self._running = False
        self._done = False
        self._error = None
        self._manifest = None
        self._handler = None

    # -- metadata for the UI ------------------------------------------------
    def get_input_fields(self):
        return [{"field": f, "label": l, "required": r} for f, l, r in INPUT_FIELDS]

    def default_output_dir(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return str(RESULTS_DIR / f"run_{ts}")

    # -- native dialogs -----------------------------------------------------
    def pick_folder(self):
        result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        if not result:
            return None
        return result[0] if isinstance(result, (list, tuple)) else result

    def pick_file(self, field=None):
        file_types = FILE_TYPES.get(field, ("All files (*.*)",))
        result = self.window.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=False, file_types=file_types
        )
        if not result:
            return None
        return result[0] if isinstance(result, (list, tuple)) else result

    # -- scan a directory for inputs ---------------------------------------
    def scan_directory(self, directory):
        """Auto-detect input files inside a directory."""
        try:
            return {"ok": True, "matches": resolve_inputs_from_directory(directory)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # -- run ----------------------------------------------------------------
    def _append_log(self, line):
        with self._lock:
            self._log_lines.append(line)

    def start_run(self, payload):
        """Validate the payload and start the pipeline in a background thread.

        payload keys: inputs (dict field->path), output_dir, run_by, remarks,
        skip_demand_data, skip_spatial_layers, skip_demographics,
        run_mc_distribution.
        """
        with self._lock:
            if self._running:
                return {"ok": False, "error": "A run is already in progress."}

        inputs = payload.get("inputs", {}) or {}

        # Build the config
        try:
            cfg = RunConfig(
                transit_nodes=inputs.get("transit_nodes") or None,
                lines_modes=inputs.get("lines_modes") or None,
                demand=inputs.get("demand") or None,
                metro_areas=inputs.get("metro_areas") or None,
                districts=inputs.get("districts") or None,
                taz_zones=inputs.get("taz_zones") or None,
                bus_terminals=inputs.get("bus_terminals") or None,
                output_dir=payload.get("output_dir") or None,
                skip_demand_data=bool(payload.get("skip_demand_data")),
                skip_spatial_layers=bool(payload.get("skip_spatial_layers")),
                skip_demographics=bool(payload.get("skip_demographics")),
                run_mc_distribution=bool(payload.get("run_mc_distribution")),
                run_by=payload.get("run_by", "").strip(),
                remarks=payload.get("remarks", "").strip(),
            )
        except Exception as e:
            return {"ok": False, "error": f"Invalid configuration: {e}"}

        problems = cfg.validate()
        if problems:
            return {"ok": False, "error": " ; ".join(problems)}

        # Reset state
        with self._lock:
            self._log_lines = []
            self._running = True
            self._done = False
            self._error = None
            self._manifest = None

        # Attach log capture
        self._handler = _LogCapture(self._append_log)
        pipeline_logger.addHandler(self._handler)

        thread = threading.Thread(target=self._worker, args=(cfg,), daemon=True)
        thread.start()
        return {"ok": True, "output_dir": str(cfg.output_dir)}

    def _worker(self, cfg):
        try:
            self._append_log(f"Starting run {cfg.run_id} (by {cfg.run_by or 'unknown'})...")
            run_pipeline(cfg)
            # Read the manifest the pipeline wrote
            manifest_path = Path(cfg.output_dir) / "run_log.json"
            if manifest_path.exists():
                with open(manifest_path, encoding="utf-8") as f:
                    self._manifest = json.load(f)
        except Exception as e:
            with self._lock:
                self._error = str(e)
            self._append_log(f"ERROR: {e}")
            # Try to still load a manifest (the pipeline writes one on failure)
            try:
                manifest_path = Path(cfg.output_dir) / "run_log.json"
                if manifest_path.exists():
                    with open(manifest_path, encoding="utf-8") as f:
                        self._manifest = json.load(f)
            except Exception:
                pass
        finally:
            with self._lock:
                self._running = False
                self._done = True
            if self._handler is not None:
                pipeline_logger.removeHandler(self._handler)
                self._handler = None

    def poll(self):
        """Return current run state for the UI to render."""
        with self._lock:
            return {
                "running": self._running,
                "done": self._done,
                "error": self._error,
                "log": "\n".join(self._log_lines),
                "manifest": self._manifest,
            }

    def open_path(self, path):
        """Open a file/folder in the OS default application."""
        import os
        import subprocess
        try:
            p = Path(path)
            target = str(p if p.exists() else p.parent)
            if sys.platform.startswith("darwin"):
                subprocess.Popen(["open", target])
            elif sys.platform.startswith("win"):
                os.startfile(target)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", target])
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}


def main():
    api = Api()
    window = webview.create_window(
        "Hub Prioritization - Run Model",
        url=str(GUI_DIR / "index.html"),
        js_api=api,
        width=1100,
        height=860,
        min_size=(900, 700),
    )
    api.window = window
    webview.start()


if __name__ == "__main__":
    main()
