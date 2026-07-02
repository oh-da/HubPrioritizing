"""
Centrality Validation Against Hub Rankings
===========================================
Compares network centrality of hubs with the Monte Carlo prioritization
results: rank correlations, top-N overlap, and a divergence table listing
hubs whose network role and MC rank disagree most.

This is a validation/sanity-check deliverable — it does not change any
scores or rankings.
"""

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from scipy.stats import kendalltau, spearmanr

from ..config import RESULTS_DIR
from ..utils.logging import get_logger

logger = get_logger(__name__)

# Column-name candidates across notebook vs package exports
SCORE_COL_CANDIDATES = ['Average_Simulated_Score', 'final_score']
RANK_COL_CANDIDATES = ['Overall_Rank', 'rank']
NAME_COL_CANDIDATES = ['address', 'Hub_Name', 'name']
TIER_COL = 'HubType'
NON_HUB_TIERS = {'Not Hub'}


def _resolve_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _df_to_md(df: pd.DataFrame, index: bool = False) -> str:
    """Render a DataFrame as a markdown table, falling back to a fenced
    text block when the optional `tabulate` dependency is missing."""
    try:
        return df.to_markdown(index=index)
    except ImportError:
        return "```\n" + df.to_string(index=index) + "\n```"


def compare_with_rankings(
    centrality_df: pd.DataFrame,
    scored_hubs: pd.DataFrame,
) -> Dict:
    """Join hub centrality with the scored-hubs table and compute statistics.

    Args:
        centrality_df: Output of compute_centrality_metrics (indexed by
            node_id; hub rows have index 'hub_<group>')
        scored_hubs: Final scored hubs table (scored_hubs_final.csv)

    Returns:
        Dict with keys: merged (DataFrame), coverage, correlations,
        tier_correlations, criterion_correlations, top_n_overlap,
        score_col, rank_col
    """
    score_col = _resolve_column(scored_hubs, SCORE_COL_CANDIDATES)
    if score_col is None:
        raise ValueError(
            f"Scored hubs table has none of {SCORE_COL_CANDIDATES}")
    rank_col = _resolve_column(scored_hubs, RANK_COL_CANDIDATES)

    hubs_cent = centrality_df[centrality_df['is_hub']].copy()
    hubs_cent['group'] = (
        hubs_cent.index.astype(str).str.replace('hub_', '', n=1)
    )

    scored = scored_hubs.copy()
    scored['group'] = scored['group'].astype(str)
    # Float-formatted groups ("3.0") from CSV round-trips
    hubs_cent['group'] = hubs_cent['group'].str.replace(
        r'\.0$', '', regex=True)
    scored['group'] = scored['group'].str.replace(r'\.0$', '', regex=True)

    merged = scored.merge(
        hubs_cent.reset_index(drop=True), on='group', how='outer',
        indicator=True)

    coverage = {
        'n_scored_hubs': int((merged['_merge'] != 'right_only').sum()),
        'n_centrality_hubs': int((merged['_merge'] != 'left_only').sum()),
        'n_matched': int((merged['_merge'] == 'both').sum()),
        'scored_without_centrality': merged.loc[
            merged['_merge'] == 'left_only', 'group'].tolist(),
        'centrality_without_scored': merged.loc[
            merged['_merge'] == 'right_only', 'group'].tolist(),
    }
    logger.info(
        f"Coverage: {coverage['n_matched']} hubs matched "
        f"({len(coverage['scored_without_centrality'])} scored hubs lack "
        f"centrality, {len(coverage['centrality_without_scored'])} "
        f"centrality hubs missing from scored table)")

    both = merged[merged['_merge'] == 'both'].drop(columns='_merge').copy()

    # Headline stats exclude non-hubs (they were filtered out of the
    # prioritization, so their MC score is not meaningful)
    if TIER_COL in both.columns:
        eligible = both[~both[TIER_COL].isin(NON_HUB_TIERS)].copy()
    else:
        eligible = both.copy()

    if rank_col is None:
        rank_col = 'Overall_Rank'
        eligible[rank_col] = eligible[score_col].rank(
            ascending=False, method='min')

    eligible['centrality_rank'] = eligible['betweenness'].rank(
        ascending=False, method='min')

    def _corr(x, y):
        if len(x) < 3:
            return {'n': len(x), 'spearman_rho': None, 'spearman_p': None,
                    'kendall_tau': None, 'kendall_p': None}
        rho, p_s = spearmanr(x, y)
        tau, p_k = kendalltau(x, y)
        return {'n': len(x), 'spearman_rho': round(float(rho), 3),
                'spearman_p': round(float(p_s), 4),
                'kendall_tau': round(float(tau), 3),
                'kendall_p': round(float(p_k), 4)}

    correlations = {
        'betweenness_vs_score': _corr(
            eligible['betweenness'], eligible[score_col]),
        'closeness_vs_score': _corr(
            eligible['closeness'], eligible[score_col]),
        'degree_vs_score': _corr(
            eligible['degree'], eligible[score_col]),
    }

    tier_correlations = {}
    if TIER_COL in eligible.columns:
        for tier, tier_df in eligible.groupby(TIER_COL):
            tier_correlations[tier] = _corr(
                tier_df['betweenness'], tier_df[score_col])

    # Centrality vs each normalized criterion (degree<->service score is the
    # construction cross-check; closeness<->location should be negative)
    crit_rows = []
    norm_cols = [c for c in eligible.columns if c.endswith('_Norm')
                 and c not in ('betweenness_Norm', 'closeness_Norm',
                               'degree_Norm')]
    for crit in norm_cols:
        vals = eligible[[crit, 'betweenness', 'closeness', 'degree']].dropna()
        if len(vals) < 3:
            continue
        crit_rows.append({
            'criterion': crit,
            'spearman_vs_betweenness': round(float(
                spearmanr(vals[crit], vals['betweenness'])[0]), 3),
            'spearman_vs_closeness': round(float(
                spearmanr(vals[crit], vals['closeness'])[0]), 3),
            'spearman_vs_degree': round(float(
                spearmanr(vals[crit], vals['degree'])[0]), 3),
        })
    criterion_correlations = pd.DataFrame(crit_rows)

    top_n_overlap = {}
    for n in (10, 20):
        if len(eligible) < n:
            continue
        top_cent = set(eligible.nsmallest(n, 'centrality_rank')['group'])
        top_rank = set(eligible.nsmallest(n, rank_col)['group'])
        inter = top_cent & top_rank
        top_n_overlap[n] = {
            'recall': round(len(inter) / n, 2),
            'jaccard': round(len(inter) / len(top_cent | top_rank), 2),
            'shared_groups': sorted(inter),
        }

    return {
        'merged': both,
        'eligible': eligible,
        'coverage': coverage,
        'correlations': correlations,
        'tier_correlations': tier_correlations,
        'criterion_correlations': criterion_correlations,
        'top_n_overlap': top_n_overlap,
        'score_col': score_col,
        'rank_col': rank_col,
    }


def find_divergent_hubs(
    eligible: pd.DataFrame,
    rank_col: str,
    top_n: int = 10,
) -> pd.DataFrame:
    """Find hubs where centrality rank and MC rank disagree the most.

    Positive rank_diff = the network says this hub matters more than the
    MC ranking does ("network hearts the ranking misses"); negative = the
    MC ranking favours it beyond its structural role.

    Args:
        eligible: 'eligible' DataFrame from compare_with_rankings
        rank_col: Name of the MC rank column
        top_n: Rows per direction

    Returns:
        DataFrame sorted by rank_diff with both directions' top_n rows
    """
    df = eligible.copy()
    df['rank_diff'] = df[rank_col] - df['centrality_rank']

    name_col = _resolve_column(df, NAME_COL_CANDIDATES)
    keep = ['group', 'rank_diff', 'centrality_rank', rank_col,
            'betweenness', 'closeness']
    for extra in (name_col, TIER_COL, 'area', 'TotalDemand'):
        if extra and extra in df.columns:
            keep.append(extra)

    top_under = df.nlargest(top_n, 'rank_diff')   # network > MC
    top_over = df.nsmallest(top_n, 'rank_diff')   # MC > network
    combined = pd.concat([top_under, top_over])
    combined = combined[~combined.index.duplicated()]
    return combined[keep].sort_values('rank_diff', ascending=False)


def write_validation_report(
    results: Dict,
    divergent: pd.DataFrame,
    qa_df: pd.DataFrame,
    out_dir: Path = RESULTS_DIR,
    weight: str = 'time_min',
    top_stations: Optional[pd.DataFrame] = None,
) -> Path:
    """Write the markdown validation report.

    Args:
        results: Output of compare_with_rankings
        divergent: Output of find_divergent_hubs
        qa_df: Per-line QA DataFrame from build_station_graph
        out_dir: Output directory
        weight: Edge weight used (for documentation)
        top_stations: Optional top non-hub stations by betweenness

    Returns:
        Path to the written report
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / 'centrality_validation_report.md'

    corr = results['correlations']
    cov = results['coverage']

    def _fmt_corr(c):
        if c['spearman_rho'] is None:
            return f"n={c['n']} (too few for correlation)"
        return (f"Spearman ρ = {c['spearman_rho']} (p={c['spearman_p']}), "
                f"Kendall τ = {c['kendall_tau']} (p={c['kendall_p']}), "
                f"n = {c['n']}")

    lines = [
        "# Network Centrality Validation Report",
        "",
        "Standalone validation of the Monte Carlo hub rankings against "
        "weighted **betweenness centrality** computed on the planned "
        "mass-transit network (hub-contracted L-space graph, edge cost = "
        f"`{weight}`).",
        "",
        "## Coverage",
        "",
        f"- Hubs matched (scored ∩ centrality): **{cov['n_matched']}**",
        f"- Scored hubs without centrality: "
        f"{len(cov['scored_without_centrality'])}",
        f"- Centrality hubs missing from scored table: "
        f"{len(cov['centrality_without_scored'])}",
    ]

    if len(qa_df):
        n_ok = int(qa_df['status'].str.startswith(
            ('ok', 'heuristic')).sum())
        n_skipped = len(qa_df) - n_ok
        pct = 100.0 * n_ok / len(qa_df)
        lines += [
            f"- Lines built into the graph: **{n_ok}/{len(qa_df)} "
            f"({pct:.0f}%)**; skipped: {n_skipped}",
        ]
        if pct < 90:
            lines += [
                "",
                "> ⚠️ **Line coverage is below 90% — treat these results "
                "as indicative only.** A missing central line changes "
                "betweenness for the whole network, not just locally.",
            ]

    lines += [
        "",
        "## Headline correlations (eligible hubs only)",
        "",
        f"- **Betweenness vs MC score**: {_fmt_corr(corr['betweenness_vs_score'])}",
        f"- Closeness vs MC score: {_fmt_corr(corr['closeness_vs_score'])}",
        f"- Degree vs MC score: {_fmt_corr(corr['degree_vs_score'])}",
        "",
        "### Per tier",
        "",
    ]
    for tier, c in results['tier_correlations'].items():
        lines.append(f"- {tier}: {_fmt_corr(c)}")

    if len(results['criterion_correlations']):
        lines += [
            "",
            "### Centrality vs individual criteria (Spearman)",
            "",
            _df_to_md(results['criterion_correlations']),
            "",
            "Expected patterns: degree ↔ service score high (construction "
            "cross-check); closeness ↔ location score negative (the "
            "location criterion deliberately boosts the periphery).",
        ]

    lines += ["", "## Top-N overlap", ""]
    if results['top_n_overlap']:
        for n, ov in results['top_n_overlap'].items():
            lines.append(
                f"- Top-{n}: recall {ov['recall']}, Jaccard {ov['jaccard']}")
    else:
        lines.append("- (fewer than 10 matched hubs — overlap not computed)")

    lines += [
        "",
        "## Largest divergences",
        "",
        "Positive `rank_diff` = the network structure ranks this hub higher "
        "than the MC scoring does; negative = the opposite.",
        "",
        _df_to_md(divergent),
    ]

    if top_stations is not None and len(top_stations):
        lines += [
            "",
            "## Top non-hub stations by betweenness",
            "",
            "Structurally central stations that are not part of any "
            "identified hub:",
            "",
            _df_to_md(top_stations, index=True),
        ]

    lines += [
        "",
        "## Limitations",
        "",
        "- **Mode speeds are planning assumptions** (`MODE_SPEEDS_KMH` in "
        "`src/config.py`); edge costs are generalized time, not modeled "
        "travel times.",
        "- Centrality is computed on the **full planned 2050 network** — "
        "consistent with the 2050-demand-based rankings, but no phasing.",
        "- **Topological betweenness**, not passenger-flow betweenness: no "
        "OD matrix exists, so all node pairs count equally.",
        "- Hub contraction models intra-hub transfers as free and counts "
        "each traversing path once; it structurally favours large "
        "multi-station hubs (which is what the validation tests).",
        "- Isolated components (e.g. cable/funicular systems) are expected "
        "and retained; closeness uses the Wasserman-Faust per-component "
        "correction.",
    ]

    path.write_text("\n".join(lines), encoding='utf-8')
    logger.info(f"✓ Validation report written to {path}")
    return path


def plot_centrality_vs_score(
    results: Dict,
    out_path: Path,
    annotate_top: int = 8,
) -> Optional[Path]:
    """Scatter of betweenness vs MC score, colored by tier.

    Args:
        results: Output of compare_with_rankings
        out_path: PNG output path
        annotate_top: Annotate this many largest |rank_diff| hubs

    Returns:
        Path if written, None if matplotlib unavailable
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available — skipping scatter plot")
        return None

    df = results['eligible'].copy()
    score_col = results['score_col']
    rank_col = results['rank_col']

    fig, ax = plt.subplots(figsize=(10, 7))
    tiers = df[TIER_COL].unique() if TIER_COL in df.columns else ['all']
    colors = plt.cm.tab10.colors
    for i, tier in enumerate(tiers):
        sub = df[df[TIER_COL] == tier] if TIER_COL in df.columns else df
        ax.scatter(sub['betweenness'], sub[score_col],
                   label=str(tier), color=colors[i % len(colors)],
                   alpha=0.7, s=40)

    df['rank_diff_abs'] = (df[rank_col] - df['centrality_rank']).abs()
    name_col = _resolve_column(df, NAME_COL_CANDIDATES) or 'group'
    for _, row in df.nlargest(annotate_top, 'rank_diff_abs').iterrows():
        label = str(row[name_col])[:30]
        ax.annotate(label, (row['betweenness'], row[score_col]),
                    fontsize=7, alpha=0.8,
                    xytext=(4, 4), textcoords='offset points')

    ax.set_xlabel('Betweenness centrality (weighted, normalized)')
    ax.set_ylabel(f'Monte Carlo score ({score_col})')
    rho = results['correlations']['betweenness_vs_score']['spearman_rho']
    ax.set_title(f'Network centrality vs MC hub score (Spearman ρ = {rho})')
    ax.legend(title='Tier', fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    logger.info(f"✓ Scatter plot written to {out_path}")
    return Path(out_path)


def create_centrality_map(
    centrality_df: pd.DataFrame,
    out_path: Path,
    line_geometries: Optional[Dict] = None,
    merged: Optional[pd.DataFrame] = None,
) -> Optional[Path]:
    """Folium map of hubs sized/colored by betweenness.

    Args:
        centrality_df: Output of compute_centrality_metrics (x/y in
            EPSG:2039)
        out_path: HTML output path
        line_geometries: Optional {LINE_ID: geometry} to draw alignments
        merged: Optional merged table from compare_with_rankings (for
            tier/rank popups)

    Returns:
        Path if written, None if folium unavailable
    """
    try:
        import folium
        from pyproj import Transformer
    except ImportError:
        logger.warning("folium/pyproj not available — skipping map")
        return None

    transformer = Transformer.from_crs('EPSG:2039', 'EPSG:4326',
                                       always_xy=True)

    df = centrality_df.dropna(subset=['x', 'y']).copy()
    lons, lats = transformer.transform(df['x'].values, df['y'].values)
    df['lon'], df['lat'] = lons, lats

    m = folium.Map(location=[float(df['lat'].mean()),
                             float(df['lon'].mean())],
                   zoom_start=9, tiles='cartodbpositron')

    if line_geometries:
        for line_id, geom in line_geometries.items():
            try:
                geoms = getattr(geom, 'geoms', [geom])
                for part in geoms:
                    coords = [
                        transformer.transform(x, y)[::-1]
                        for x, y in part.coords
                    ]
                    folium.PolyLine(coords, color='#888888', weight=1,
                                    opacity=0.5, tooltip=line_id).add_to(m)
            except Exception:
                continue

    tier_by_group = {}
    if merged is not None and TIER_COL in merged.columns:
        tier_by_group = merged.set_index('group')[TIER_COL].to_dict()

    max_b = df['betweenness'].max() or 1.0
    hubs = df[df['is_hub']]
    stations = df[~df['is_hub']]

    for node_id, row in stations.iterrows():
        folium.CircleMarker(
            [row['lat'], row['lon']], radius=2, color='#bbbbbb',
            fill=True, fill_opacity=0.5, weight=0,
            tooltip=f"{node_id}: b={row['betweenness']:.4f}",
        ).add_to(m)

    for node_id, row in hubs.iterrows():
        group = str(node_id).replace('hub_', '', 1)
        frac = row['betweenness'] / max_b
        color = (
            '#d73027' if frac > 0.66 else
            '#fc8d59' if frac > 0.33 else '#4575b4'
        )
        tier = tier_by_group.get(group, '')
        folium.CircleMarker(
            [row['lat'], row['lon']],
            radius=4 + 16 * frac,
            color=color, fill=True, fill_opacity=0.7, weight=1,
            popup=(f"hub {group} {tier}<br>"
                   f"betweenness: {row['betweenness']:.4f}<br>"
                   f"closeness: {row['closeness']:.4f}<br>"
                   f"degree: {row['degree']}"),
        ).add_to(m)

    m.save(str(out_path))
    logger.info(f"✓ Centrality map written to {out_path}")
    return Path(out_path)
