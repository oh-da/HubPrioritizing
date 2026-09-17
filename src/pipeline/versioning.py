"""
Run versions: what went into a run, and what changed between two runs.

Every ``hubs run`` writes ``run_manifest.json`` next to the workbook: the version name
(by default the newest date among the model exports), the input files with their SHA-256,
the base-layer vintage, the effective configuration, the code version and a result summary.
``hubs compare A B`` reads two output directories and writes a comparison: which inputs and
settings differ, which hubs appeared, disappeared or changed tier, and how every score and
rank moved. Hubs are matched by ``hub_id`` (a hash of the node set) and, when the node set
changed, by shared nodes. ``hubs runs DIR`` lists the versions found under a directory.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from .base_layer import _sha256, manifest_path
from .inputs import InputSet
from .settings import PipelineConfig

RUN_MANIFEST = "run_manifest.json"
RESULTS_CSV = "hub_prioritization_results.csv"
IDENTITY_CSV = "hub_identity.csv"

CATEGORICAL = ("HubType", "Metro", "HubNameHE", "Modes_ForPlot", "location")
NUMERIC = (
    "TotalDemand",
    "TotalTransfers",
    "Line_Nunique",
    "Num_Modes",
    "bus_terminal",
    "TotalPop_2050",
    "TotalEmp_2050",
    "RegionLocation",
    "score",
    "RegionLocation_Norm",
    "score_Norm",
    "bus_terminal_Norm",
    "TotalDemand_Norm",
    "PopEmp_Score_Norm",
    "TotalScore_MC",
    "Rank_TS_MC",
    "RankByHubTypeMetro",
)


# ----------------------------------------------------------------------------------------
# run manifest
# ----------------------------------------------------------------------------------------


def default_version(inputs: InputSet) -> str:
    """Newest date carried by a required model export (``2026-06-18``), else today."""
    dates = [inputs.files[k].date for k in ("nodeslines", "lines_mode", "demand") if inputs.has(k) and inputs.files[k].date]
    if dates:
        return max(dates)
    return dt.date.today().isoformat()


def _git_commit(start: Path) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(start), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() or None if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _package_version() -> str | None:
    try:
        from importlib.metadata import version

        return version("hub-prioritization")
    except Exception:  # noqa: BLE001 - not installed as a package
        return None


def build_run_manifest(
    inputs: InputSet,
    cfg: PipelineConfig,
    results: pd.DataFrame,
    version: str | None = None,
    outputs: dict[str, Path] | None = None,
) -> dict[str, Any]:
    """The provenance record of one run (see module docstring)."""
    files: dict[str, dict[str, Any]] = {}
    for key, chosen in inputs.files.items():
        p = Path(chosen.path)
        entry: dict[str, Any] = {"file": p.name, "source": chosen.source, "date": chosen.date}
        if p.exists() and p.is_file():
            entry["sha256"] = _sha256(p)
            entry["bytes"] = p.stat().st_size
        files[key] = entry

    base: dict[str, Any] = {}
    layer = inputs.path("h3_base")
    if layer is not None:
        mp = manifest_path(layer)
        if mp.exists():
            m = json.loads(mp.read_text(encoding="utf-8"))
            base = {
                "file": Path(layer).name,
                "built": m.get("built"),
                "resolution": m.get("resolution"),
                "sources": {k: v.get("sha256", "")[:12] for k, v in m.get("sources", {}).items()},
            }

    counts = results["HubType"].value_counts().to_dict() if "HubType" in results.columns else {}
    top = []
    if {"Rank_TS_MC", "HubNameHE", "TotalScore_MC"} <= set(results.columns):
        top = results.nsmallest(10, "Rank_TS_MC")[["group", "HubNameHE", "HubType", "TotalScore_MC"]].to_dict("records")

    return {
        "version": version or default_version(inputs),
        "created": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "code": {"package": _package_version(), "git_commit": _git_commit(Path(__file__).resolve().parent)},
        "input_dir": str(inputs.input_dir),
        "reference_dir": str(inputs.reference_dir),
        "inputs": files,
        "base_layer": base,
        "config": cfg.to_dict(),
        "summary": {"hubs": int(len(results)), "hub_types": {str(k): int(v) for k, v in counts.items()}, "top10": _jsonable(top)},
        "outputs": {k: Path(v).name for k, v in (outputs or {}).items()},
    }


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if hasattr(obj, "item"):
        try:
            return obj.item()
        except Exception:  # noqa: BLE001
            return str(obj)
    if isinstance(obj, float) and obj != obj:
        return None
    return obj


def write_run_manifest(manifest: dict[str, Any], output_dir: Path | str) -> Path:
    path = Path(output_dir) / RUN_MANIFEST
    path.write_text(json.dumps(_jsonable(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_run_manifest(output_dir: Path | str) -> dict[str, Any] | None:
    path = Path(output_dir) / RUN_MANIFEST
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def list_runs(root: Path | str) -> pd.DataFrame:
    """Every output directory under ``root`` (recursively) that holds a run manifest."""
    rows = []
    for mp in sorted(Path(root).rglob(RUN_MANIFEST)):
        m = json.loads(mp.read_text(encoding="utf-8"))
        rows.append(
            {
                "version": m.get("version"),
                "created": m.get("created"),
                "hubs": m.get("summary", {}).get("hubs"),
                "nodeslines": m.get("inputs", {}).get("nodeslines", {}).get("file"),
                "demand": m.get("inputs", {}).get("demand", {}).get("file"),
                "base_layer_built": m.get("base_layer", {}).get("built"),
                "git_commit": m.get("code", {}).get("git_commit"),
                "dir": str(mp.parent),
            }
        )
    return pd.DataFrame(rows, columns=["version", "created", "hubs", "nodeslines", "demand", "base_layer_built", "git_commit", "dir"])


# ----------------------------------------------------------------------------------------
# comparison
# ----------------------------------------------------------------------------------------


class RunDir:
    """One output directory: results, identity table and manifest."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        results = self.path / RESULTS_CSV
        identity = self.path / IDENTITY_CSV
        if not results.exists() or not identity.exists():
            raise FileNotFoundError(f"{self.path} is not a run output directory ({RESULTS_CSV} and {IDENTITY_CSV} needed)")
        self.results = pd.read_csv(results, encoding="utf-8-sig")
        self.identity = pd.read_csv(identity, encoding="utf-8-sig")
        self.manifest = read_run_manifest(self.path) or {}
        self.version = self.manifest.get("version") or self.path.name
        ident = self.identity.set_index("group")
        self.hub_id = ident["hub_id"].to_dict()
        self.nodes = {g: set(int(n) for n in str(v).split(",") if n.strip()) for g, v in ident["nodes"].items()}


def match_hubs(a: RunDir, b: RunDir) -> pd.DataFrame:
    """Pair the hubs of two runs: by ``hub_id``, then by the most shared nodes.

    Returns ``group_a, group_b, match`` with ``match`` in ``hub_id`` / ``nodes`` /
    ``removed`` (only in A) / ``added`` (only in B).
    """
    groups_a = list(a.results["group"])
    groups_b = list(b.results["group"])
    id_to_b: dict = {}
    for g in groups_b:
        id_to_b.setdefault(b.hub_id.get(g), g)
    pairs: list[tuple[Any, Any, str]] = []
    used_b: set = set()
    left_a = []
    for g in groups_a:
        gb = id_to_b.get(a.hub_id.get(g))
        if gb is not None and gb not in used_b:
            pairs.append((g, gb, "hub_id"))
            used_b.add(gb)
        else:
            left_a.append(g)
    left_b = [g for g in groups_b if g not in used_b]
    # greedy on shared node count
    candidates = []
    for ga in left_a:
        for gb in left_b:
            shared = len(a.nodes.get(ga, set()) & b.nodes.get(gb, set()))
            if shared:
                candidates.append((shared, ga, gb))
    candidates.sort(reverse=True)
    used_a: set = set()
    for _, ga, gb in candidates:
        if ga in used_a or gb in used_b:
            continue
        pairs.append((ga, gb, "nodes"))
        used_a.add(ga)
        used_b.add(gb)
    for ga in left_a:
        if ga not in used_a:
            pairs.append((ga, None, "removed"))
    for gb in left_b:
        if gb not in used_b:
            pairs.append((None, gb, "added"))
    return pd.DataFrame(pairs, columns=["group_a", "group_b", "match"])


def compare_runs(dir_a: Path | str, dir_b: Path | str) -> dict[str, Any]:
    """Compare two output directories (A = before, B = after)."""
    a, b = RunDir(dir_a), RunDir(dir_b)
    pairs = match_hubs(a, b)
    ra = a.results.set_index("group")
    rb = b.results.set_index("group")

    rows = []
    for p in pairs.itertuples():
        row: dict[str, Any] = {"match": p.match, "group_a": p.group_a, "group_b": p.group_b}
        row["hub_id_a"] = a.hub_id.get(p.group_a) if p.group_a is not None and not pd.isna(p.group_a) else None
        row["hub_id_b"] = b.hub_id.get(p.group_b) if p.group_b is not None and not pd.isna(p.group_b) else None
        src_a = ra.loc[p.group_a] if row["hub_id_a"] is not None else None
        src_b = rb.loc[p.group_b] if row["hub_id_b"] is not None else None
        name = None
        for src in (src_b, src_a):
            if src is not None and "HubNameHE" in src and pd.notna(src["HubNameHE"]):
                name = src["HubNameHE"]
                break
        row["name"] = name
        changed = []
        for c in CATEGORICAL:
            va = src_a[c] if src_a is not None and c in src_a else None
            vb = src_b[c] if src_b is not None and c in src_b else None
            row[f"{c}_a"], row[f"{c}_b"] = va, vb
            if src_a is not None and src_b is not None and str(va) != str(vb):
                changed.append(c)
        for c in NUMERIC:
            va = float(src_a[c]) if src_a is not None and c in src_a and pd.notna(src_a[c]) else None
            vb = float(src_b[c]) if src_b is not None and c in src_b and pd.notna(src_b[c]) else None
            row[f"{c}_a"], row[f"{c}_b"] = va, vb
            row[f"{c}_delta"] = (vb - va) if va is not None and vb is not None else None
        row["changed_fields"] = ";".join(changed)
        rows.append(row)
    table = pd.DataFrame(rows)

    matched = table[table["match"].isin(["hub_id", "nodes"])]
    tier_changes = matched[matched["HubType_a"].astype(str) != matched["HubType_b"].astype(str)]
    score_moves = matched.dropna(subset=["TotalScore_MC_delta"]).sort_values("TotalScore_MC_delta")
    rank_moves = matched.dropna(subset=["RankByHubTypeMetro_delta"])
    rank_moves = rank_moves[rank_moves["RankByHubTypeMetro_delta"] != 0]

    ma, mb = a.manifest, b.manifest
    inputs_diff = _diff_inputs(ma.get("inputs", {}), mb.get("inputs", {}))
    config_diff = {k: (ma.get("config", {}).get(k), mb.get("config", {}).get(k)) for k in sorted(set(ma.get("config", {})) | set(mb.get("config", {}))) if ma.get("config", {}).get(k) != mb.get("config", {}).get(k)}
    base_diff = None
    if ma.get("base_layer") != mb.get("base_layer"):
        base_diff = (ma.get("base_layer", {}).get("built"), mb.get("base_layer", {}).get("built"))

    summary = {
        "a": {"version": a.version, "dir": str(a.path), "created": ma.get("created"), "hubs": int(len(a.results))},
        "b": {"version": b.version, "dir": str(b.path), "created": mb.get("created"), "hubs": int(len(b.results))},
        "matched_by_hub_id": int((table["match"] == "hub_id").sum()),
        "matched_by_nodes": int((table["match"] == "nodes").sum()),
        "added": int((table["match"] == "added").sum()),
        "removed": int((table["match"] == "removed").sum()),
        "tier_changes": int(len(tier_changes)),
        "score_changed": int((matched["TotalScore_MC_delta"].abs() > 1e-9).sum()),
        "rank_changed": int(len(rank_moves)),
        "inputs_changed": inputs_diff,
        "config_changed": config_diff,
        "base_layer_changed": base_diff,
        "code": {"a": ma.get("code"), "b": mb.get("code")},
    }
    return {"summary": summary, "table": table, "tier_changes": tier_changes, "score_moves": score_moves, "rank_moves": rank_moves}


def _diff_inputs(ia: dict, ib: dict) -> dict[str, dict[str, Any]]:
    out = {}
    for key in sorted(set(ia) | set(ib)):
        ea, eb = ia.get(key), ib.get(key)
        if ea is None or eb is None:
            out[key] = {"a": ea and ea.get("file"), "b": eb and eb.get("file"), "status": "only in " + ("A" if eb is None else "B")}
        elif ea.get("sha256") != eb.get("sha256"):
            out[key] = {"a": ea.get("file"), "b": eb.get("file"), "status": "different content" if ea.get("file") == eb.get("file") else "different file"}
    return out


def comparison_markdown(comp: dict[str, Any]) -> str:
    s = comp["summary"]
    t = comp["table"]
    lines = [f"# Run comparison: {s['a']['version']} → {s['b']['version']}", ""]
    lines += [
        "| | A (before) | B (after) |",
        "|---|---|---|",
        f"| version | {s['a']['version']} | {s['b']['version']} |",
        f"| created | {s['a']['created']} | {s['b']['created']} |",
        f"| directory | `{s['a']['dir']}` | `{s['b']['dir']}` |",
        f"| hubs in workbook | {s['a']['hubs']} | {s['b']['hubs']} |",
        f"| code | {(s['code']['a'] or {}).get('git_commit')} | {(s['code']['b'] or {}).get('git_commit')} |",
        "",
        "## What changed in the inputs",
        "",
    ]
    if s["inputs_changed"]:
        lines += ["| input | A | B | |", "|---|---|---|---|"]
        lines += [f"| {k} | {v['a']} | {v['b']} | {v['status']} |" for k, v in s["inputs_changed"].items()]
    else:
        lines.append("Identical input files (same names and hashes).")
    if s["base_layer_changed"]:
        lines += ["", f"H3 base layer rebuilt: built {s['base_layer_changed'][0]} → {s['base_layer_changed'][1]}."]
    if s["config_changed"]:
        lines += ["", "Settings that differ:", ""]
        lines += [f"- `{k}`: {va} → {vb}" for k, (va, vb) in s["config_changed"].items()]
    lines += [
        "",
        "## What changed in the results",
        "",
        f"- hubs matched by unchanged node set: {s['matched_by_hub_id']}; matched by shared nodes (membership changed): {s['matched_by_nodes']}",
        f"- hubs only in B (added): {s['added']}; only in A (removed): {s['removed']}",
        f"- tier changes: {s['tier_changes']}; score changed: {s['score_changed']}; RankByHubTypeMetro changed: {s['rank_changed']}",
        "",
    ]

    def hub_table(df: pd.DataFrame, cols: Sequence[tuple[str, str]], title: str, limit: int = 15) -> None:
        if df.empty:
            return
        lines.append(f"### {title}")
        lines.append("")
        lines.append("| " + " | ".join(h for _, h in cols) + " |")
        lines.append("|" + "---|" * len(cols))
        for _, r in df.head(limit).iterrows():
            cells = []
            for c, _ in cols:
                v = r.get(c)
                cells.append("" if v is None or (isinstance(v, float) and pd.isna(v)) else (f"{v:.3f}" if isinstance(v, float) and abs(v) < 1e6 and c.endswith(("_a", "_b", "_delta")) and "Rank" not in c and "group" not in c else str(v)))
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")

    added = t[t["match"] == "added"]
    removed = t[t["match"] == "removed"]
    hub_table(added, [("group_b", "group (B)"), ("name", "hub"), ("HubType_b", "tier"), ("Metro_b", "metro"), ("TotalScore_MC_b", "score"), ("RankByHubTypeMetro_b", "rank")], "Hubs only in B (added)")
    hub_table(removed, [("group_a", "group (A)"), ("name", "hub"), ("HubType_a", "tier"), ("Metro_a", "metro"), ("TotalScore_MC_a", "score"), ("RankByHubTypeMetro_a", "rank")], "Hubs only in A (removed)")
    hub_table(comp["tier_changes"], [("name", "hub"), ("HubType_a", "tier A"), ("HubType_b", "tier B"), ("TotalDemand_a", "demand A"), ("TotalDemand_b", "demand B"), ("Line_Nunique_a", "lines A"), ("Line_Nunique_b", "lines B")], "Tier changes")
    sm = comp["score_moves"]
    hub_table(sm.tail(15).iloc[::-1], [("name", "hub"), ("HubType_b", "tier"), ("TotalScore_MC_a", "score A"), ("TotalScore_MC_b", "score B"), ("TotalScore_MC_delta", "Δ"), ("RankByHubTypeMetro_a", "rank A"), ("RankByHubTypeMetro_b", "rank B"), ("changed_fields", "changed")], "Largest score increases")
    hub_table(sm.head(15), [("name", "hub"), ("HubType_b", "tier"), ("TotalScore_MC_a", "score A"), ("TotalScore_MC_b", "score B"), ("TotalScore_MC_delta", "Δ"), ("RankByHubTypeMetro_a", "rank A"), ("RankByHubTypeMetro_b", "rank B"), ("changed_fields", "changed")], "Largest score decreases")
    rm = comp["rank_moves"].reindex(comp["rank_moves"]["RankByHubTypeMetro_delta"].abs().sort_values(ascending=False).index)
    hub_table(rm, [("name", "hub"), ("HubType_b", "tier"), ("Metro_b", "metro"), ("RankByHubTypeMetro_a", "rank A"), ("RankByHubTypeMetro_b", "rank B"), ("RankByHubTypeMetro_delta", "Δ rank")], "Largest rank moves (RankByHubTypeMetro)")
    lines.append("The full per-hub table (every score, rank and delta) is in the CSV next to this file.")
    return "\n".join(lines) + "\n"


def write_comparison(comp: dict[str, Any], out_dir: Path | str, stem: str | None = None) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    s = comp["summary"]
    stem = stem or f"compare_{_slug(s['a']['version'])}_vs_{_slug(s['b']['version'])}"
    paths = {
        "md": out / f"{stem}.md",
        "csv": out / f"{stem}.csv",
        "json": out / f"{stem}.json",
    }
    paths["md"].write_text(comparison_markdown(comp), encoding="utf-8")
    comp["table"].to_csv(paths["csv"], index=False, encoding="utf-8-sig")
    paths["json"].write_text(json.dumps(_jsonable(s), ensure_ascii=False, indent=2), encoding="utf-8")
    return paths


def _slug(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(text))
