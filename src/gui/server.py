"""
Local web GUI: ``hubs serve`` starts a small HTTP server (standard library only) on
127.0.0.1 and opens ``src/gui/index.html``. The page lets a user pick the input folder,
validate it, run the pipeline, browse the run versions and compare two of them; every
action calls the same functions the command line uses.

API (JSON):

    GET  /api/state                     server root, reference dir, base-layer status
    GET  /api/browse?path=DIR           sub-folders, files and the inputs detected in DIR
    POST /api/validate                  {input_dir, sets} -> problems, input table, node positions
    POST /api/run                       {input_dir, output_dir, version, sets} -> {job}
    POST /api/prepare-base              {} -> {job}
    GET  /api/jobs/<id>                 status, log, result
    GET  /api/runs?root=DIR             run versions under DIR
    POST /api/compare                   {a, b} -> summary, tables, files
    GET  /api/report?dir=DIR            run_report.md of a run
    GET  /api/file?path=FILE            download a result file

Only files under the served root or under an output directory this server wrote can be
read. POST requests must carry ``X-Hubs: 1`` so a page on another origin cannot trigger a
run.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import threading
import time
import traceback
import uuid
import webbrowser
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..config import REFERENCE_DATA_DIR
from ..pipeline.inputs import InputError, base_layer_staleness, discover_inputs, read_csv_auto, validate_inputs
from ..pipeline.report import RunReport
from ..pipeline.settings import ConfigError, load_config, parse_set_overrides

INDEX_HTML = Path(__file__).with_name("index.html")


# ----------------------------------------------------------------------------------------
# jobs
# ----------------------------------------------------------------------------------------


@dataclass
class Job:
    id: str
    kind: str
    params: dict[str, Any]
    status: str = "queued"  # queued | running | done | error
    started: float | None = None
    finished: float | None = None
    log: list[str] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "started": self.started,
            "finished": self.finished,
            "elapsed": round((self.finished or time.time()) - self.started, 1) if self.started else None,
            "log": self.log[-400:],
            "result": self.result,
            "error": self.error,
        }


class _JobLogHandler(logging.Handler):
    def __init__(self, job: Job):
        super().__init__()
        self.job = job
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        self.job.log.append(self.format(record))


class ServerState:
    """Shared state: served root, reference dir, jobs, and the output dirs written here."""

    def __init__(self, root: Path, reference_dir: Path):
        self.root = Path(root).resolve()
        self.reference_dir = Path(reference_dir).resolve()
        self.jobs: dict[str, Job] = {}
        self.written_dirs: set[Path] = set()  # output dirs this server wrote
        self.extra_roots: set[Path] = set()  # run roots the page listed
        self._lock = threading.Lock()
        self._busy = False

    # --- jobs ---------------------------------------------------------------------------
    def start_job(self, kind: str, params: dict[str, Any]) -> Job:
        with self._lock:
            if self._busy:
                raise RuntimeError("another job is still running; wait for it to finish")
            self._busy = True
        job = Job(id=uuid.uuid4().hex[:8], kind=kind, params=params)
        self.jobs[job.id] = job
        threading.Thread(target=self._run_job, args=(job,), daemon=True).start()
        return job

    def _run_job(self, job: Job) -> None:
        job.status = "running"
        job.started = time.time()
        handler = _JobLogHandler(job)
        loggers = [logging.getLogger("hubs"), logging.getLogger("src")]
        for lg in loggers:
            lg.addHandler(handler)
            if lg.level == logging.NOTSET or lg.level > logging.INFO:
                lg.setLevel(logging.INFO)
        try:
            if job.kind == "run":
                job.result = self._do_run(job)
            elif job.kind == "prepare-base":
                job.result = self._do_prepare_base(job)
            else:
                raise ValueError(f"unknown job kind {job.kind}")
            job.status = "done"
        except InputError as exc:
            job.status = "error"
            job.error = str(exc)
        except Exception as exc:  # noqa: BLE001 - surfaced to the page
            job.status = "error"
            job.error = f"{type(exc).__name__}: {exc}"
            job.log.append(traceback.format_exc())
        finally:
            job.finished = time.time()
            for lg in loggers:
                lg.removeHandler(handler)
            with self._lock:
                self._busy = False

    def _do_run(self, job: Job) -> dict[str, Any]:
        from ..pipeline.run import run_pipeline, write_outputs

        p = job.params
        cfg = load_config(p.get("config") or None, parse_set_overrides(p.get("sets") or []))
        input_dir = Path(p["input_dir"])
        output_dir = Path(p["output_dir"])
        inputs = discover_inputs(input_dir, self.reference_dir)
        report = RunReport()
        job.log.append(f"run: {input_dir} -> {output_dir}")
        result = run_pipeline(cfg, inputs, report)
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = write_outputs(result, output_dir, p.get("version") or None)
        self.written_dirs.add(output_dir.resolve())
        res = result.results
        top = res.nsmallest(10, "Rank_TS_MC")[["group", "HubNameHE", "HubType", "Metro", "TotalScore_MC", "RankByHubTypeMetro"]]
        return {
            "output_dir": str(output_dir.resolve()),
            "version": report.metrics.get("version"),
            "hubs": int(len(res)),
            "hub_types": {str(k): int(v) for k, v in res["HubType"].value_counts().items()},
            "warnings": len(report.warnings),
            "files": [{"name": Path(v).name, "path": str(Path(v).resolve()), "bytes": Path(v).stat().st_size} for v in paths.values() if Path(v).is_file()],
            "top10": json.loads(top.to_json(orient="records", force_ascii=False)),
        }

    def _do_prepare_base(self, job: Job) -> dict[str, Any]:
        from ..pipeline.run import prepare_base_layer

        inputs = discover_inputs(self.reference_dir, self.reference_dir)
        out = self.reference_dir / "h3_base.parquet"
        job.log.append(f"prepare-base -> {out}")
        report = RunReport()
        layer, manifest = prepare_base_layer(inputs, out, 10, None, report)
        for w in report.warnings:
            job.log.append(f"WARNING {w.section}: {w.message}")
        return {"path": str(out), "cells": int(len(layer)), "built": manifest.get("built")}

    # --- access rules -------------------------------------------------------------------
    def readable(self, path: Path) -> bool:
        """Files under the served root, the reference dir, a listed runs root or an
        output directory written by this server."""
        p = Path(path).resolve()
        if not p.is_file():
            return False
        return any(_is_under(p, r) for r in (self.root, self.reference_dir, *self.written_dirs, *self.extra_roots))

    def allow_root(self, path: Path) -> None:
        self.extra_roots.add(Path(path).resolve())


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


# ----------------------------------------------------------------------------------------
# API implementation (plain functions, testable without HTTP)
# ----------------------------------------------------------------------------------------


def api_state(state: ServerState) -> dict[str, Any]:
    from ..pipeline.base_layer import manifest_path

    layer = state.reference_dir / "h3_base.parquet"
    base: dict[str, Any] = {"present": layer.exists()}
    if layer.exists():
        mp = manifest_path(layer)
        if mp.exists():
            m = json.loads(mp.read_text(encoding="utf-8"))
            base.update({"built": m.get("built"), "resolution": m.get("resolution"), "rows": m.get("rows"), "sources": {k: v.get("file") for k, v in m.get("sources", {}).items()}})
        inputs = discover_inputs(state.reference_dir, state.reference_dir)
        base["stale"] = base_layer_staleness(inputs)
    return {"root": str(state.root), "reference_dir": str(state.reference_dir), "base_layer": base, "busy": state._busy}


def api_browse(state: ServerState, path: str | None) -> dict[str, Any]:
    p = Path(path).expanduser().resolve() if path else state.root
    if not p.is_dir():
        raise FileNotFoundError(f"not a directory: {p}")
    dirs, files = [], []
    for child in sorted(p.iterdir(), key=lambda c: c.name.lower()):
        if child.name.startswith("."):
            continue
        try:
            if child.is_dir():
                dirs.append(child.name)
            else:
                st = child.stat()
                files.append({"name": child.name, "bytes": st.st_size, "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))})
        except OSError:
            continue
    detected = {}
    try:
        inputs = discover_inputs(p, state.reference_dir)
        for key, chosen in inputs.files.items():
            if chosen.source == "input":
                detected[key] = chosen.path.name
    except Exception:  # noqa: BLE001 - browsing must never fail on odd folders
        pass
    required_present = all(k in detected for k in ("nodeslines", "lines_mode", "demand"))
    has_manifest = (p / "run_manifest.json").exists()
    return {"path": str(p), "parent": str(p.parent) if p.parent != p else None, "dirs": dirs, "files": files, "detected": detected, "looks_like_input_dir": required_present, "is_run_dir": has_manifest}


def api_validate(state: ServerState, params: dict[str, Any]) -> dict[str, Any]:
    from ..pipeline.network import apply_node_position_overrides, load_nodeslines, node_position_table

    input_dir = Path(params["input_dir"]).expanduser()
    try:
        cfg = load_config(params.get("config") or None, parse_set_overrides(params.get("sets") or []))
    except (ConfigError, ValueError) as exc:
        return {"ok": False, "problems": [f"configuration error: {exc}"], "rows": [], "node_positions": []}
    report = RunReport()
    inputs = discover_inputs(input_dir, state.reference_dir)
    problems = validate_inputs(inputs, report, cfg.spatial_source, cfg.on_stale_base_layer)
    rows = inputs.summary_rows(cfg.spatial_source)
    for r in rows:
        r["encoding"] = report.inputs.get(r["key"], {}).get("encoding")
    positions: list[dict[str, Any]] = []
    if not problems:
        try:
            nodes = load_nodeslines(read_csv_auto(inputs.path("nodeslines"))[0])
            overrides = read_csv_auto(inputs.path("node_positions"))[0] if inputs.has("node_positions") else None
            nodes = apply_node_position_overrides(nodes, overrides)
            for row in node_position_table(nodes).itertuples():
                positions.append({"node": int(row.node), "n_positions": int(row.n_positions), "spread_m": float(row.spread_m), "conflict": row.spread_m > cfg.node_position_tolerance_m, "positions": row.positions})
        except Exception as exc:  # noqa: BLE001
            positions = [{"error": str(exc)}]
    return {
        "ok": not problems,
        "problems": problems,
        "rows": rows,
        "node_positions": positions,
        "default_version": _default_version(inputs),
        "config": {"mc_iterations": cfg.mc_iterations, "spatial_source": cfg.spatial_source, "influence_rings": list(cfg.influence_rings)},
    }


def _default_version(inputs) -> str:
    from ..pipeline.versioning import default_version

    return default_version(inputs)


def api_runs(state: ServerState, root: str | None) -> dict[str, Any]:
    from ..pipeline.versioning import list_runs

    r = Path(root).expanduser().resolve() if root else state.root
    state.allow_root(r)
    table = list_runs(r)
    return {"root": str(r), "runs": json.loads(table.to_json(orient="records", force_ascii=False))}


def api_compare(state: ServerState, params: dict[str, Any]) -> dict[str, Any]:
    from ..pipeline.versioning import compare_runs, write_comparison

    a, b = Path(params["a"]).expanduser(), Path(params["b"]).expanduser()
    comp = compare_runs(a, b)
    out_dir = Path(params["out"]).expanduser() if params.get("out") else b
    paths = write_comparison(comp, out_dir)
    state.written_dirs.add(out_dir.resolve())
    t = comp["table"]

    def records(df, cols, limit=20):
        cols = [c for c in cols if c in df.columns]
        return json.loads(df[cols].head(limit).to_json(orient="records", force_ascii=False))

    base = ["name", "match", "group_a", "group_b", "HubType_a", "HubType_b", "Metro_b", "TotalDemand_a", "TotalDemand_b", "Line_Nunique_a", "Line_Nunique_b", "TotalScore_MC_a", "TotalScore_MC_b", "TotalScore_MC_delta", "RankByHubTypeMetro_a", "RankByHubTypeMetro_b", "RankByHubTypeMetro_delta", "changed_fields"]
    sm = comp["score_moves"]
    rm = comp["rank_moves"]
    rm = rm.reindex(rm["RankByHubTypeMetro_delta"].abs().sort_values(ascending=False).index) if len(rm) else rm
    return {
        "summary": comp["summary"],
        "added": records(t[t["match"] == "added"], base),
        "removed": records(t[t["match"] == "removed"], base),
        "tier_changes": records(comp["tier_changes"], base),
        "score_up": records(sm.tail(15).iloc[::-1], base, 15),
        "score_down": records(sm.head(15), base, 15),
        "rank_moves": records(rm, base, 20),
        "files": {k: str(v) for k, v in paths.items()},
    }


def api_report(state: ServerState, run_dir: str) -> str:
    p = Path(run_dir).expanduser() / "run_report.md"
    if not state.readable(p):
        raise PermissionError(f"not readable: {p}")
    return p.read_text(encoding="utf-8")


# ----------------------------------------------------------------------------------------
# HTTP
# ----------------------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    state: ServerState  # set by make_server

    def log_message(self, fmt, *args):  # quieter console
        logging.getLogger("hubs.gui").debug(fmt, *args)

    # --- helpers ------------------------------------------------------------------------
    def _json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, exc: Exception, status: int = 400) -> None:
        self._json({"error": f"{type(exc).__name__}: {exc}"}, status)

    def _read_json(self) -> dict[str, Any]:
        if self.headers.get("X-Hubs") != "1":
            raise PermissionError("missing X-Hubs header")
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    # --- routes -------------------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            if url.path in ("/", "/index.html"):
                body = INDEX_HTML.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif url.path == "/api/state":
                self._json(api_state(self.state))
            elif url.path == "/api/browse":
                self._json(api_browse(self.state, q.get("path")))
            elif url.path.startswith("/api/jobs/"):
                job = self.state.jobs.get(url.path.rsplit("/", 1)[-1])
                self._json(job.to_dict() if job else {"error": "no such job"}, 200 if job else 404)
            elif url.path == "/api/runs":
                self._json(api_runs(self.state, q.get("root")))
            elif url.path == "/api/report":
                text = api_report(self.state, q["dir"])
                self._json({"markdown": text})
            elif url.path == "/api/file":
                self._send_file(Path(q["path"]).expanduser())
            else:
                self._json({"error": "not found"}, 404)
        except (FileNotFoundError, KeyError) as exc:
            self._error(exc, 404)
        except PermissionError as exc:
            self._error(exc, 403)
        except Exception as exc:  # noqa: BLE001
            self._error(exc, 500)

    def do_POST(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        try:
            params = self._read_json()
            if url.path == "/api/validate":
                self._json(api_validate(self.state, params))
            elif url.path == "/api/run":
                for key in ("input_dir", "output_dir"):
                    if not params.get(key):
                        raise ValueError(f"{key} is required")
                job = self.state.start_job("run", params)
                self._json({"job": job.to_dict()})
            elif url.path == "/api/prepare-base":
                job = self.state.start_job("prepare-base", params)
                self._json({"job": job.to_dict()})
            elif url.path == "/api/compare":
                self._json(api_compare(self.state, params))
            else:
                self._json({"error": "not found"}, 404)
        except PermissionError as exc:
            self._error(exc, 403)
        except FileNotFoundError as exc:
            self._error(exc, 404)
        except RuntimeError as exc:
            self._error(exc, 409)
        except Exception as exc:  # noqa: BLE001
            self._error(exc, 400)

    def _send_file(self, path: Path) -> None:
        if not self.state.readable(path):
            raise PermissionError(f"not readable: {path}")
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self.end_headers()
        self.wfile.write(data)


def make_server(root: Path | str = ".", reference_dir: Path | str = REFERENCE_DATA_DIR, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    state = ServerState(Path(root), Path(reference_dir))
    handler = type("BoundHandler", (Handler,), {"state": state})
    server = ThreadingHTTPServer((host, port), handler)
    server.state = state  # type: ignore[attr-defined]
    return server


def serve_from_cli(args: Any) -> int:
    """Entry point used by ``hubs serve``."""
    from ..utils.logging import setup_logger

    setup_logger("hubs")
    server = make_server(args.root, args.reference_dir, args.host, args.port)
    url = f"http://{args.host}:{server.server_address[1]}/"
    print(f"Hub prioritization GUI: {url}   (Ctrl+C to stop)")
    print(f"  root:      {server.state.root}")
    print(f"  reference: {server.state.reference_dir}")
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
    return 0
