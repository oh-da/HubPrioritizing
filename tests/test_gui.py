"""The local GUI server: its JSON API end to end on the synthetic inputs."""

import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from src.gui.server import api_browse, api_state, api_validate, make_server
from tests.synthetic import make_synthetic_dirs


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    root = tmp_path_factory.mktemp("gui")
    input_dir, ref_dir = make_synthetic_dirs(root)
    srv = make_server(root, ref_dir, port=0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv, root, input_dir, ref_dir
    srv.shutdown()


def _call(srv, path, body=None, headers=None):
    port = srv.server_address[1]
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method="POST" if data else "GET")
    if data:
        req.add_header("Content-Type", "application/json")
    for k, v in ({"X-Hubs": "1"} if headers is None else headers).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if r.headers.get("Content-Type", "").startswith("application/json") else raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, (json.loads(raw) if raw.startswith(b"{") else raw)


def _wait_job(srv, job_id, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, j = _call(srv, f"/api/jobs/{job_id}")
        if j["status"] in ("done", "error"):
            return j
        time.sleep(0.3)
    raise AssertionError("job did not finish")


def test_page_and_state(server):
    srv, root, input_dir, ref_dir = server
    status, page = _call(srv, "/")
    assert status == 200 and b"Hub prioritization" in page and b"/api/validate" in page
    status, st = _call(srv, "/api/state")
    assert status == 200 and st["root"] == str(root.resolve()) and st["base_layer"]["present"] and st["base_layer"]["stale"] == []
    assert api_state(srv.state)["base_layer"]["resolution"] == 10


def test_browse_detects_inputs(server):
    srv, root, input_dir, ref_dir = server
    status, b = _call(srv, "/api/browse?path=" + str(root))
    assert status == 200 and "input" in b["dirs"] and "reference" in b["dirs"] and not b["looks_like_input_dir"]
    status, b = _call(srv, "/api/browse?path=" + str(input_dir))
    assert b["looks_like_input_dir"] and b["detected"]["nodeslines"].startswith("All_nodeslines")
    assert any(f["name"].endswith(".xlsx") for f in b["files"])
    status, err = _call(srv, "/api/browse?path=" + str(root / "nope"))
    assert status == 404
    assert api_browse(srv.state, None)["path"] == str(root.resolve())


def test_validate_run_and_download(server):
    srv, root, input_dir, ref_dir = server
    status, v = _call(srv, "/api/validate", {"input_dir": str(input_dir), "sets": ["mc_iterations=50"]})
    assert status == 200 and v["ok"] and v["problems"] == [] and v["default_version"] == "2030-01-01"
    assert any(r["key"] == "nodeslines" and r["encoding"] == "cp1255" for r in v["rows"])
    # a bad setting is a problem, not a crash
    status, v2 = _call(srv, "/api/validate", {"input_dir": str(input_dir), "sets": ["mc_scope=weird"]})
    assert not v2["ok"] and "configuration error" in v2["problems"][0]
    assert not api_validate(srv.state, {"input_dir": str(root / "missing")})["ok"]

    out_dir = root / "out_gui"
    status, r = _call(srv, "/api/run", {"input_dir": str(input_dir), "output_dir": str(out_dir), "version": "gui-test", "sets": ["mc_iterations=50", "apply_eligibility_filter=false"]})
    assert status == 200
    job = _wait_job(srv, r["job"]["id"])
    assert job["status"] == "done", job.get("error")
    res = job["result"]
    assert res["version"] == "gui-test" and res["hubs"] == 3 and len(res["top10"]) == 3
    names = {f["name"] for f in res["files"]}
    assert {"hub_prioritization_results.xlsx", "h3_layer.gpkg", "run_manifest.json"} <= names
    assert any("Part 4" in line for line in job["log"])

    # files of a run this server wrote can be downloaded; others cannot
    xlsx = next(f["path"] for f in res["files"] if f["name"].endswith(".xlsx"))
    status, data = _call(srv, "/api/file?path=" + xlsx)
    assert status == 200 and data[:2] == b"PK"
    status, _ = _call(srv, "/api/file?path=" + str(ref_dir.parent.parent / "pyproject.toml"))
    assert status == 403
    status, rep = _call(srv, "/api/report?dir=" + str(out_dir))
    assert status == 200 and "Metrics" in rep["markdown"]

    # a second run with a different version, then the versions list and a comparison
    status, r = _call(srv, "/api/run", {"input_dir": str(input_dir), "output_dir": str(root / "out_gui2"), "version": "gui-test-2", "sets": ["mc_iterations=80", "apply_eligibility_filter=false"]})
    assert _wait_job(srv, r["job"]["id"])["status"] == "done"
    status, runs = _call(srv, "/api/runs?root=" + str(root))
    assert status == 200 and {x["version"] for x in runs["runs"]} >= {"gui-test", "gui-test-2"}
    status, c = _call(srv, "/api/compare", {"a": str(out_dir), "b": str(root / "out_gui2")})
    assert status == 200 and c["summary"]["matched_by_hub_id"] == 3 and c["summary"]["config_changed"]["mc_iterations"] == [50, 80]
    assert "md" in c["files"] and c["added"] == [] and c["removed"] == []


def test_post_requires_header_and_rejects_bad_requests(server):
    srv, root, input_dir, ref_dir = server
    status, err = _call(srv, "/api/validate", {"input_dir": str(input_dir)}, headers={})
    assert status == 403
    status, err = _call(srv, "/api/run", {"input_dir": str(input_dir)})
    assert status == 400 and "output_dir" in err["error"]
    status, err = _call(srv, "/api/compare", {"a": str(root / "x"), "b": str(root / "y")})
    assert status == 404
    status, err = _call(srv, "/api/jobs/nope")
    assert status == 404
    status, err = _call(srv, "/api/nothing")
    assert status == 404
