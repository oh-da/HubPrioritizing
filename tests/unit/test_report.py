import json
from pathlib import Path

import numpy as np

from src.pipeline.report import RunReport


def test_report_collects_and_renders(tmp_path):
    r = RunReport()
    r.record_input("nodeslines", Path("/x/All_nodeslines.csv"), encoding="cp1255")
    r.info("network", "loaded rows", rows=np.int64(5013))
    r.warn("network", "lines without a mode row", lines={"LRT9", "LRT10"})
    r.set_metric("hubs", 142)

    assert len(r.warnings) == 1 and not r.errors
    assert r.sections() == ["network"]

    md, js = r.write(tmp_path)
    text = md.read_text(encoding="utf-8")
    assert "lines without a mode row" in text and "LRT10" in text
    data = json.loads(js.read_text(encoding="utf-8"))
    assert data["metrics"]["hubs"] == 142
    assert data["entries"][1]["data"]["lines"] == ["LRT10", "LRT9"]  # sets become sorted lists
    assert data["inputs"]["nodeslines"]["encoding"] == "cp1255"
