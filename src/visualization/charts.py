"""
Statistical Charts and Plots
=============================
Create statistical visualizations for hub analysis.
"""

import pandas as pd
import geopandas as gpd
from typing import Optional

try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from ..utils.logging import get_logger

logger = get_logger(__name__)


def plot_score_distribution(
    gdf: gpd.GeoDataFrame,
    score_column: str = 'final_score',
    tier_column: str = 'tier',
    output_file: Optional[str] = None,
) -> None:
    """
    Plot score distribution by tier.

    Args:
        gdf: GeoDataFrame with scores
        score_column: Column with scores to plot
        tier_column: Column with tier classification
        output_file: Path to save plot (if None, displays plot)
    """
    if not MATPLOTLIB_AVAILABLE:
        logger.error("Matplotlib not installed, cannot create plots")
        return

    logger.info(f"Plotting {score_column} distribution...")

    fig, ax = plt.subplots(figsize=(10, 6))

    if tier_column in gdf.columns:
        # Plot by tier
        tiers = gdf[tier_column].unique()
        for tier in tiers:
            tier_data = gdf[gdf[tier_column] == tier][score_column]
            ax.hist(tier_data, alpha=0.6, label=tier, bins=20)

        ax.legend()
    else:
        # Plot overall
        ax.hist(gdf[score_column], bins=20)

    ax.set_xlabel(score_column.replace('_', ' ').title())
    ax.set_ylabel('Frequency')
    ax.set_title(f'Distribution of {score_column.replace("_", " ").title()}')

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        logger.info(f"✓ Plot saved to {output_file}")
    else:
        plt.show()

    plt.close()


def plot_tier_comparison(
    gdf: gpd.GeoDataFrame,
    tier_column: str = 'tier',
    demand_column: str = 'TotalDemand',
    output_file: Optional[str] = None,
) -> None:
    """
    Create comparison plot across tiers.

    Args:
        gdf: GeoDataFrame with hubs
        tier_column: Column with tier classification
        demand_column: Column with demand data
        output_file: Path to save plot
    """
    if not MATPLOTLIB_AVAILABLE:
        logger.error("Matplotlib not installed")
        return

    logger.info("Creating tier comparison plot...")

    tier_stats = gdf.groupby(tier_column).agg({
        demand_column: ['count', 'sum', 'mean']
    })

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    # Count
    tier_stats[(demand_column, 'count')].plot(kind='bar', ax=axes[0])
    axes[0].set_title('Hub Count by Tier')
    axes[0].set_ylabel('Count')

    # Total demand
    tier_stats[(demand_column, 'sum')].plot(kind='bar', ax=axes[1])
    axes[1].set_title('Total Demand by Tier')
    axes[1].set_ylabel('Total Passengers/Day')

    # Average demand
    tier_stats[(demand_column, 'mean')].plot(kind='bar', ax=axes[2])
    axes[2].set_title('Average Demand by Tier')
    axes[2].set_ylabel('Avg Passengers/Day')

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        logger.info(f"✓ Plot saved to {output_file}")
    else:
        plt.show()

    plt.close()
