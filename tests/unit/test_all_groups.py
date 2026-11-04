"""hub_groups_all.csv (every group before the eligibility filter) and network_nodes.csv."""

import pandas as pd
import pytest

from src.pipeline.all_groups import build_all_groups_table, build_network_nodes_table
from src.pipeline.inputs import discover_inputs
from src.pipeline.run import run_pipeline, write_outputs
from src.pipeline.settings import PipelineConfig, load_config
from tests.synthetic import make_synthetic_dirs


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    root = tmp_path_factory.mktemp("allgroups")
    input_dir, ref_dir = make_synthetic_dirs(root)
    cfg = load_config(None, {"mc_iterations": 50})
    result = run_pipeline(cfg, discover_inputs(input_dir, ref_dir))
    paths = write_outputs(result, root / "out")
    return result, paths, root


def _all_groups(result):
    return build_all_groups_table(result.groups, result.results, result.hub_names, result.config.require_non_rail_mode)


def test_run_result_carries_nodes_and_names(run):
    result, _, _ = run
    assert result.nodes is not None and {"node", "LINE_ID", "Mode_Planned"} <= set(result.nodes.columns)
    assert result.line_names  # the synthetic fixture ships line names
    assert len(result.results) < len(result.groups)  # the default filter removed a group


def test_all_groups_has_every_group_including_ineligible(run):
    result, _, _ = run
    table = _all_groups(result)
    assert len(table) == len(result.groups) and table["group"].is_unique
    rail_group = int(result.groups[result.groups["node"].map(lambda ns: 9 in ns)]["group"].iloc[0])
    row = table[table["group"] == rail_group].iloc[0]
    assert not row["eligible"]
    assert "single mode" in row["exclusion_reason"] and "rail only" in row["exclusion_reason"]
    assert row["n_modes"] == 1 and pd.isna(row["TotalScore_MC"])
    for node in (1, 4):  # hubs A and B
        a = table[table["group"] == int(result.groups[result.groups["node"].map(lambda ns, n=node: n in ns)]["group"].iloc[0])].iloc[0]
        assert a["eligible"]


def test_eligible_rows_match_scored_hubs(run):
    result, _, _ = run
    table = _all_groups(result)
    assert set(table.loc[table["eligible"], "group"]) == set(result.results["group"])
    scored = table[table["eligible"]]
    assert scored["TotalScore_MC"].notna().all() and scored["HubType"].notna().all()
    assert set(table.columns) >= {
        "hub_id", "group", "HubNameHE", "x", "y", "x_itm", "y_itm", "area", "Mode_Planned", "n_modes",
        "Line_Unique", "n_lines", "TotalDemand", "TotalTransfers", "eligible", "exclusion_reason",
        "HubType", "TotalScore_MC", "Rank_TS_MC", "RankByHubTypeMetro",
    }


def test_exclusion_reason_empty_when_eligible(run):
    result, _, _ = run
    table = _all_groups(result)
    assert (table.loc[table["eligible"], "exclusion_reason"] == "").all()
    assert (table.loc[~table["eligible"], "exclusion_reason"] != "").all()


def test_demand_reason_and_rail_flag(run):
    result, _, _ = run
    groups = result.groups.copy()
    groups.loc[groups.index[0], "TotalDemand"] = 10
    table = build_all_groups_table(groups, result.results, None, True)
    first = table[table["group"] == int(groups.iloc[0]["group"])].iloc[0]
    assert "demand < min" in first["exclusion_reason"] and not first["eligible"]
    lenient = build_all_groups_table(result.groups, result.results, None, False)
    assert "rail only" not in " ".join(lenient["exclusion_reason"])  # flag off: no rail-only reason


def test_itm_and_wgs84_centroids(run):
    result, _, _ = run
    table = _all_groups(result)
    assert table["x_itm"].between(100000, 300000).all() and table["y_itm"].between(350000, 800000).all()
    assert table["x"].between(34, 36).all() and table["y"].between(29, 34).all()


def test_network_nodes_counts(run):
    result, _, _ = run
    all_groups = _all_groups(result)
    nn = build_network_nodes_table(result.nodes, result.hexes, result.line_names)
    assert list(nn.columns) == ["node", "LINE_ID", "line_name", "Mode_Planned", "x_itm", "y_itm", "group", "hub_id"]
    assert len(nn) == len(result.nodes.drop_duplicates(["node", "LINE_ID"]))
    assert nn["group"].notna().all() and nn["hub_id"].notna().all()
    assert set(nn["group"]) <= set(all_groups["group"]) and set(nn["hub_id"]) <= set(all_groups["hub_id"])
    me = nn[nn["LINE_ID"] == "Me1-N"].iloc[0]
    assert me["line_name"] == "מטרו צפון (מטרו)" and me["Mode_Planned"] == "Metro"
    assert nn["x_itm"].between(100000, 300000).all()


def test_files_written_and_roundtrip(run):
    result, paths, root = run
    assert paths["hub_groups_all"] == root / "out" / "hub_groups_all.csv" and paths["hub_groups_all"].exists()
    assert paths["network_nodes"] == root / "out" / "network_nodes.csv" and paths["network_nodes"].exists()
    csv = pd.read_csv(paths["hub_groups_all"], encoding="utf-8-sig", keep_default_na=False)
    memory = _all_groups(result)
    assert len(csv) == len(memory)
    for lines_text, lines in zip(csv["Line_Unique"], memory["Line_Unique"]):
        assert lines_text.split(";") == list(lines)
    assert paths["hub_groups_all"].read_bytes().startswith(b"\xef\xbb\xbf")
    nn = pd.read_csv(paths["network_nodes"], encoding="utf-8-sig")
    assert "line_name" in nn.columns and nn["line_name"].str.contains("מטרו").any()


def test_hub_groups_all_roundtrips_lists(run):
    result, paths, _ = run
    csv = pd.read_csv(paths["hub_groups_all"], encoding="utf-8-sig", keep_default_na=False)
    by_group = {int(g): lines for g, lines in zip(result.groups["group"], result.groups["Line_Unique"])}
    for g, text in zip(csv["group"], csv["Line_Unique"]):
        assert text.split(";") == list(by_group[int(g)])


def test_outputs_can_be_switched_off(tmp_path):
    input_dir, ref_dir = make_synthetic_dirs(tmp_path)
    cfg = load_config(None, {"mc_iterations": 50, "all_groups_basename": "", "network_nodes_basename": ""})
    paths = write_outputs(run_pipeline(cfg, discover_inputs(input_dir, ref_dir)), tmp_path / "out")
    assert "hub_groups_all" not in paths and "network_nodes" not in paths
    assert not (tmp_path / "out" / "hub_groups_all.csv").exists()
    assert not (tmp_path / "out" / "network_nodes.csv").exists()


def test_settings_defaults():
    cfg = PipelineConfig()
    assert cfg.all_groups_basename == "hub_groups_all" and cfg.network_nodes_basename == "network_nodes"
