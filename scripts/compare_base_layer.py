"""
Compare the shapefile spatial stages with the pre-allocated H3 base layer.

Runs the pipeline on one input directory twice (``spatial_source=shapefiles`` and
``spatial_source=h3_base``) and reports, per hub, the differences in area/location,
bus terminal class, population/jobs per ring, the Monte Carlo score and the display
rank. Used to decide whether the H3 layer can replace the shapefiles.

    python scripts/compare_base_layer.py --input-dir tests/fixtures/real [--cell-rule center|fraction]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import REFERENCE_DATA_DIR  # noqa: E402
from src.pipeline.aggregate import ring_column_names  # noqa: E402
from src.pipeline.inputs import discover_inputs  # noqa: E402
from src.pipeline.report import RunReport  # noqa: E402
from src.pipeline.run import run_pipeline  # noqa: E402
from src.pipeline.settings import load_config  # noqa: E402


def run(input_dir: Path, reference_dir: Path, overrides: dict) -> tuple[object, float]:
    cfg = load_config(None, overrides)
    inputs = discover_inputs(input_dir, reference_dir)
    t = time.perf_counter()
    result = run_pipeline(cfg, inputs, RunReport())
    return result, time.perf_counter() - t


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", type=Path, default=Path("tests/fixtures/real"))
    ap.add_argument("--reference-dir", type=Path, default=REFERENCE_DATA_DIR)
    ap.add_argument("--cell-rule", default="fraction", choices=["center", "fraction"])
    ap.add_argument("--set", action="append", default=[], help="extra config overrides applied to both runs (key=value)")
    ap.add_argument("--out", type=Path, default=None, help="write the per-hub comparison table as CSV")
    args = ap.parse_args(argv)

    common = dict(kv.split("=", 1) for kv in args.set)
    ref, t_ref = run(args.input_dir, args.reference_dir, {**common, "spatial_source": "shapefiles"})
    new, t_new = run(args.input_dir, args.reference_dir, {**common, "spatial_source": "h3_base", "influence_cell_rule": args.cell_rule})
    print(f"shapefiles: {t_ref:.1f} s   h3_base ({args.cell_rule}): {t_new:.1f} s\n")

    # --- hexagon tags ---------------------------------------------------------------------
    hx = ref.hexes[["h3_index", "area", "location"]].merge(new.hexes[["h3_index", "area", "location"]], on="h3_index", suffixes=("_shp", "_h3"))
    area_diff = hx[hx["area_shp"] != hx["area_h3"]]
    loc_diff = hx[hx["location_shp"].map(str) != hx["location_h3"].map(str)]
    print(f"hexagons: {len(hx)}   area differs: {len(area_diff)}   location differs: {len(loc_diff)}")
    if len(area_diff):
        print(area_diff.head(20).to_string(index=False))

    # --- groups ------------------------------------------------------------------------
    rings = ref.config.influence_rings
    ring_cols = ring_column_names(rings)
    pop_cols = [c[0] for c in ring_cols] + [c[1] for c in ring_cols]
    g = ref.groups[["group", "bus_terminal", "term_type", *pop_cols]].merge(
        new.groups[["group", "bus_terminal", "term_type", *pop_cols]], on="group", suffixes=("_shp", "_h3")
    )
    term_diff = g[g["bus_terminal_shp"] != g["bus_terminal_h3"]]
    print(f"\ngroups: {len(g)}   bus_terminal differs: {len(term_diff)}")
    if len(term_diff):
        print(term_diff[["group", "bus_terminal_shp", "bus_terminal_h3", "term_type_shp", "term_type_h3"]].to_string(index=False))

    # --- population / jobs on the scored (eligible) hubs ----------------------------------
    scored_ids = set(ref.scored["group"])
    gs = g[g["group"].isin(scored_ids)].copy()
    rows = []
    for col in pop_cols:
        a, b = gs[f"{col}_shp"].to_numpy(), gs[f"{col}_h3"].to_numpy()
        rel = np.abs(b - a) / np.where(a > 0, a, np.nan)
        rows.append(
            {
                "column": col,
                "mean_shp": a.mean(),
                "mean_h3": b.mean(),
                "mean_abs_diff": np.abs(b - a).mean(),
                "median_rel_diff": np.nanmedian(rel),
                "p90_rel_diff": np.nanpercentile(rel, 90),
                "max_rel_diff": np.nanmax(rel),
            }
        )
    print(f"\npopulation / jobs on the {len(gs)} scored hubs (relative differences vs the polygon overlay):")
    print(pd.DataFrame(rows).to_string(index=False, float_format=lambda v: f"{v:,.3f}"))
    tot_a = gs[[f"{c}_shp" for c in pop_cols]].sum().sum()
    tot_b = gs[[f"{c}_h3" for c in pop_cols]].sum().sum()
    print(f"total pop+emp within {rings[-1]} m over all scored hubs: {tot_a:,.0f} (shp) vs {tot_b:,.0f} (h3), {100 * (tot_b / tot_a - 1):+.2f} %")

    # --- scores and ranks --------------------------------------------------------------------
    keep = ["group", "HubNameHE", "HubType", "Metro", "PopEmp_Score_Norm", "TotalScore_MC", "Rank_TS_MC", "RankByHubTypeMetro"]
    r = ref.results[keep].merge(new.results[keep], on="group", suffixes=("_shp", "_h3"), how="outer", indicator=True)
    print(f"\nscored hubs: {len(ref.results)} (shp) vs {len(new.results)} (h3); only in one: {(r['_merge'] != 'both').sum()}")
    both = r[r["_merge"] == "both"].copy()
    print(f"HubType differs: {(both['HubType_shp'] != both['HubType_h3']).sum()}")
    both["score_diff"] = both["TotalScore_MC_h3"] - both["TotalScore_MC_shp"]
    both["popemp_norm_diff"] = both["PopEmp_Score_Norm_h3"] - both["PopEmp_Score_Norm_shp"]
    both["rank_diff"] = both["RankByHubTypeMetro_h3"] - both["RankByHubTypeMetro_shp"]
    both["overall_rank_diff"] = both["Rank_TS_MC_h3"] - both["Rank_TS_MC_shp"]
    print(
        f"TotalScore_MC: mean |diff| {both['score_diff'].abs().mean():.4f}, max |diff| {both['score_diff'].abs().max():.4f}"
        f" (scores range {both['TotalScore_MC_shp'].min():.2f}-{both['TotalScore_MC_shp'].max():.2f})"
    )
    print(f"PopEmp_Score_Norm: mean |diff| {both['popemp_norm_diff'].abs().mean():.3f}, max |diff| {both['popemp_norm_diff'].abs().max():.3f}")
    moved = both[both["rank_diff"] != 0]
    print(f"RankByHubTypeMetro changed for {len(moved)} of {len(both)} hubs; |change| max {both['rank_diff'].abs().max():.0f}, mean {both['rank_diff'].abs().mean():.2f}")
    print(f"Rank_TS_MC (nationwide) changed for {(both['overall_rank_diff'] != 0).sum()} hubs; |change| max {both['overall_rank_diff'].abs().max():.0f}")
    if len(moved):
        cols = ["group", "HubNameHE_shp", "HubType_shp", "Metro_shp", "TotalScore_MC_shp", "TotalScore_MC_h3", "RankByHubTypeMetro_shp", "RankByHubTypeMetro_h3"]
        print(moved.sort_values("rank_diff", key=np.abs, ascending=False)[cols].head(15).to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    if args.out:
        both.drop(columns=["_merge"]).merge(gs, on="group", how="left").to_csv(args.out, index=False, encoding="utf-8-sig")
        print(f"\nper-hub table written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
