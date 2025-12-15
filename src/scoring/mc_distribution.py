"""
Monte Carlo Distribution Reporting
===================================
Extends Monte Carlo scoring to report full distributions and rank robustness metrics.

This module provides:
- Full distribution statistics per hub (mean, median, percentiles, std, etc.)
- Rank robustness metrics (mean_rank, p_top1, p_top3, p_top5)
- CSV export for per-hub statistics
- Optional raw scores export in long format
- Visualizations: boxplots, probability bar charts, per-hub histograms

Usage:
    from src.scoring.mc_distribution import run_mc_distribution_analysis

    # Run analysis and get results
    results = run_mc_distribution_analysis(
        score_matrix,
        output_dir="outputs/mc_run_001",
        n_iterations=10000,
        random_seed=42
    )
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Tuple, List, Union
from datetime import datetime
import warnings

from ..config import (
    MONTE_CARLO_ITERATIONS,
    MONTE_CARLO_RANDOM_SEED,
    MAX_CRITERION_WEIGHT,
    MIN_CRITERION_WEIGHT,
    RESULTS_DIR,
    MC_DIST_TOP_N_HUBS,
    MC_DIST_HISTOGRAM_BINS,
    MC_DIST_EXPORT_RAW_SCORES,
    MC_DIST_PRECISION,
    MC_DIST_MAX_HUB_HISTOGRAMS,
)
from ..utils.logging import get_logger
from .monte_carlo import generate_random_weights

logger = get_logger(__name__)


# ============================================================================
# CORE MONTE CARLO WITH DISTRIBUTION TRACKING
# ============================================================================

def monte_carlo_with_distributions(
    score_matrix: pd.DataFrame,
    n_iterations: int = MONTE_CARLO_ITERATIONS,
    min_weight: float = MIN_CRITERION_WEIGHT,
    max_weight: float = MAX_CRITERION_WEIGHT,
    random_seed: Optional[int] = MONTE_CARLO_RANDOM_SEED,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Run Monte Carlo simulation and return all iteration scores and ranks.

    This is the core simulation function that stores all intermediate results
    for distribution analysis.

    Args:
        score_matrix: DataFrame with hubs as rows, criteria as columns.
                      Values should be normalized scores (typically 1-10).
        n_iterations: Number of Monte Carlo iterations (default: 10,000)
        min_weight: Minimum weight per criterion (default: 0.0)
        max_weight: Maximum weight per criterion (default: 0.5)
        random_seed: Random seed for reproducibility (None for non-deterministic)

    Returns:
        Tuple of:
        - iteration_scores: np.ndarray of shape (n_hubs, n_iterations)
        - iteration_ranks: np.ndarray of shape (n_hubs, n_iterations)
          where rank 1 = best (highest score)
    """
    logger.info(f"Running Monte Carlo simulation with full distribution tracking...")
    logger.info(f"  Iterations: {n_iterations:,}")
    logger.info(f"  Weight range: [{min_weight}, {max_weight}]")
    if random_seed is not None:
        logger.info(f"  Random seed: {random_seed}")

    n_hubs = len(score_matrix)
    n_criteria = len(score_matrix.columns)

    logger.info(f"  {n_hubs} hubs × {n_criteria} criteria")
    logger.info(f"  Criteria: {list(score_matrix.columns)}")

    # Initialize random state
    rng = np.random.RandomState(random_seed) if random_seed is not None else np.random.RandomState()

    # Allocate storage arrays
    iteration_scores = np.zeros((n_hubs, n_iterations), dtype=np.float64)
    iteration_ranks = np.zeros((n_hubs, n_iterations), dtype=np.int32)

    # Convert score matrix to numpy array for faster computation
    scores_array = score_matrix.values.astype(np.float64)

    # Run Monte Carlo iterations
    for i in range(n_iterations):
        # Generate random weights with constraint
        weights = generate_random_weights(
            n_criteria,
            max_weight=max_weight,
            min_weight=min_weight,
            random_state=rng
        )

        # Calculate weighted scores for all hubs (matrix multiplication)
        weighted_scores = scores_array @ weights

        # Store scores
        iteration_scores[:, i] = weighted_scores

        # Calculate ranks (rank 1 = highest score, using argsort twice)
        # argsort gives indices that would sort in ascending order
        # We want descending order, so we negate
        order = np.argsort(-weighted_scores)
        ranks = np.empty_like(order)
        ranks[order] = np.arange(1, n_hubs + 1)
        iteration_ranks[:, i] = ranks

        # Progress reporting
        if (i + 1) % 2000 == 0:
            logger.debug(f"  Completed {i + 1:,}/{n_iterations:,} iterations")

    logger.info(f"✓ Monte Carlo simulation complete")

    return iteration_scores, iteration_ranks


# ============================================================================
# DISTRIBUTION STATISTICS CALCULATION
# ============================================================================

def calculate_distribution_statistics(
    iteration_scores: np.ndarray,
    hub_ids: pd.Index,
) -> pd.DataFrame:
    """
    Calculate distribution statistics for each hub.

    Computes from the vector of simulated scores across all iterations:
    - Core stats: mean, median, std, min, max
    - Percentiles: p05, p10, p25, p75, p90, p95
    - Spread: IQR (interquartile range)

    Args:
        iteration_scores: Array of shape (n_hubs, n_iterations)
        hub_ids: Index of hub identifiers

    Returns:
        DataFrame with one row per hub and statistics as columns
    """
    logger.info("Calculating distribution statistics...")

    n_hubs, n_iterations = iteration_scores.shape

    # Calculate all statistics using vectorized operations
    stats = {
        'hub_id': hub_ids,
        'mean_score': np.mean(iteration_scores, axis=1),
        'median_score': np.median(iteration_scores, axis=1),
        'std_score': np.std(iteration_scores, axis=1, ddof=1),  # Sample std
        'min_score': np.min(iteration_scores, axis=1),
        'max_score': np.max(iteration_scores, axis=1),
        'p05_score': np.percentile(iteration_scores, 5, axis=1),
        'p10_score': np.percentile(iteration_scores, 10, axis=1),
        'p25_score': np.percentile(iteration_scores, 25, axis=1),
        'p75_score': np.percentile(iteration_scores, 75, axis=1),
        'p90_score': np.percentile(iteration_scores, 90, axis=1),
        'p95_score': np.percentile(iteration_scores, 95, axis=1),
    }

    # Calculate IQR
    stats['iqr_score'] = stats['p75_score'] - stats['p25_score']

    df = pd.DataFrame(stats)
    df.set_index('hub_id', inplace=True)

    logger.info(f"✓ Distribution statistics calculated for {n_hubs} hubs")

    return df


def calculate_rank_robustness(
    iteration_ranks: np.ndarray,
    hub_ids: pd.Index,
) -> pd.DataFrame:
    """
    Calculate rank robustness metrics for each hub.

    For each iteration, hubs are ranked by simulated score (rank 1 = best).
    Computes:
    - mean_rank: Average rank across all iterations
    - p_top1: Proportion of iterations where hub ranks #1
    - p_top3: Proportion where hub ranks in top 3
    - p_top5: Proportion where hub ranks in top 5

    Args:
        iteration_ranks: Array of shape (n_hubs, n_iterations)
                         with rank values (1 = best)
        hub_ids: Index of hub identifiers

    Returns:
        DataFrame with one row per hub and rank metrics as columns
    """
    logger.info("Calculating rank robustness metrics...")

    n_hubs, n_iterations = iteration_ranks.shape

    # Calculate rank statistics
    stats = {
        'hub_id': hub_ids,
        'mean_rank': np.mean(iteration_ranks, axis=1),
        'p_top1': np.mean(iteration_ranks == 1, axis=1),
        'p_top3': np.mean(iteration_ranks <= 3, axis=1),
        'p_top5': np.mean(iteration_ranks <= 5, axis=1),
    }

    df = pd.DataFrame(stats)
    df.set_index('hub_id', inplace=True)

    logger.info(f"✓ Rank robustness metrics calculated for {n_hubs} hubs")

    # Log some insights
    top_by_mean_rank = df.nsmallest(5, 'mean_rank')
    logger.info("  Top 5 by mean_rank:")
    for hub_id, row in top_by_mean_rank.iterrows():
        logger.info(f"    {hub_id}: mean_rank={row['mean_rank']:.2f}, p_top3={row['p_top3']:.1%}")

    return df


# ============================================================================
# EXPORT FUNCTIONS
# ============================================================================

def export_hub_stats_csv(
    dist_stats: pd.DataFrame,
    rank_stats: pd.DataFrame,
    output_path: Path,
    n_iterations: int,
    min_weight: float,
    max_weight: float,
    random_seed: Optional[int],
    precision: int = MC_DIST_PRECISION,
) -> None:
    """
    Export per-hub statistics to CSV (one row per hub).

    Combines distribution statistics and rank robustness metrics.
    Includes metadata columns for reproducibility.

    Args:
        dist_stats: DataFrame with distribution statistics
        rank_stats: DataFrame with rank robustness metrics
        output_path: Path for output CSV file
        n_iterations: Number of iterations (for metadata)
        min_weight: Minimum weight used (for metadata)
        max_weight: Maximum weight used (for metadata)
        random_seed: Random seed used (for metadata)
        precision: Decimal precision for numeric columns
    """
    logger.info(f"Exporting hub statistics to {output_path}...")

    # Combine statistics
    combined = dist_stats.join(rank_stats, how='outer')

    # Add metadata columns
    combined['n_iterations'] = n_iterations
    combined['min_weight'] = min_weight
    combined['max_weight'] = max_weight
    combined['random_seed'] = random_seed if random_seed is not None else 'None'
    combined['timestamp'] = datetime.now().isoformat()

    # Reset index to make hub_id a column
    combined = combined.reset_index()

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Export to CSV with specified precision
    combined.to_csv(
        output_path,
        index=False,
        encoding='utf-8',
        float_format=f'%.{precision}f'
    )

    logger.info(f"✓ Exported {len(combined)} hubs to {output_path}")


def export_raw_scores_long(
    iteration_scores: np.ndarray,
    hub_ids: pd.Index,
    output_path: Path,
) -> None:
    """
    Export raw simulated scores in long format for downstream analysis.

    Format: hub_id, iteration, score

    Args:
        iteration_scores: Array of shape (n_hubs, n_iterations)
        hub_ids: Index of hub identifiers
        output_path: Path for output CSV file
    """
    logger.info(f"Exporting raw scores in long format to {output_path}...")

    n_hubs, n_iterations = iteration_scores.shape

    # Create long format DataFrame efficiently
    hub_id_repeated = np.repeat(hub_ids.values, n_iterations)
    iteration_repeated = np.tile(np.arange(n_iterations), n_hubs)
    scores_flat = iteration_scores.flatten()

    df = pd.DataFrame({
        'hub_id': hub_id_repeated,
        'iteration': iteration_repeated,
        'score': scores_flat
    })

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Export to CSV
    df.to_csv(output_path, index=False, encoding='utf-8', float_format='%.6f')

    logger.info(f"✓ Exported {len(df):,} rows ({n_hubs} hubs × {n_iterations} iterations)")


# ============================================================================
# VISUALIZATION FUNCTIONS
# ============================================================================

def create_score_boxplot(
    iteration_scores: np.ndarray,
    hub_ids: pd.Index,
    dist_stats: pd.DataFrame,
    output_path: Path,
    top_n: int = MC_DIST_TOP_N_HUBS,
    figsize: Tuple[int, int] = (14, 8),
) -> None:
    """
    Create boxplot of score distributions for top N hubs by mean_score.

    Args:
        iteration_scores: Array of shape (n_hubs, n_iterations)
        hub_ids: Index of hub identifiers
        dist_stats: DataFrame with distribution statistics (needs mean_score)
        output_path: Path for output PNG file
        top_n: Number of top hubs to display
        figsize: Figure size tuple
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
    except ImportError:
        logger.warning("matplotlib not available. Skipping boxplot generation.")
        return

    logger.info(f"Creating score distribution boxplot for top {top_n} hubs...")

    # Get top N hubs by mean_score
    top_hubs = dist_stats.nlargest(top_n, 'mean_score').index

    # Get position mapping for top hubs
    hub_id_list = list(hub_ids)
    positions = [hub_id_list.index(h) for h in top_hubs if h in hub_id_list]

    if len(positions) == 0:
        logger.warning("No matching hubs found for boxplot")
        return

    # Extract scores for top hubs
    scores_subset = [iteration_scores[pos, :] for pos in positions]
    labels = [str(top_hubs[i]) for i in range(len(positions))]

    # Create figure
    fig, ax = plt.subplots(figsize=figsize)

    bp = ax.boxplot(
        scores_subset,
        labels=labels,
        patch_artist=True,
        showfliers=False,  # Hide outliers for clarity
    )

    # Style the boxplot
    for patch in bp['boxes']:
        patch.set_facecolor('#3498db')
        patch.set_alpha(0.7)

    for median in bp['medians']:
        median.set_color('#e74c3c')
        median.set_linewidth(2)

    ax.set_xlabel('Hub ID', fontsize=12)
    ax.set_ylabel('Simulated Score', fontsize=12)
    ax.set_title(f'Score Distributions - Top {len(positions)} Hubs by Mean Score', fontsize=14)
    ax.tick_params(axis='x', rotation=45)

    # Add grid for readability
    ax.yaxis.grid(True, linestyle='--', alpha=0.7)

    plt.tight_layout()

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    logger.info(f"✓ Boxplot saved to {output_path}")


def create_top_k_probability_chart(
    rank_stats: pd.DataFrame,
    output_path: Path,
    k: int = 3,
    top_n: int = MC_DIST_TOP_N_HUBS,
    figsize: Tuple[int, int] = (14, 8),
) -> None:
    """
    Create bar chart showing probability of ranking in top K.

    Args:
        rank_stats: DataFrame with rank robustness metrics
        output_path: Path for output PNG file
        k: Top K threshold (default: 3)
        top_n: Number of hubs to display
        figsize: Figure size tuple
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.use('Agg')
    except ImportError:
        logger.warning("matplotlib not available. Skipping probability chart generation.")
        return

    logger.info(f"Creating top-{k} probability bar chart for top {top_n} hubs...")

    # Select probability column based on k
    if k == 1:
        prob_col = 'p_top1'
    elif k == 3:
        prob_col = 'p_top3'
    elif k == 5:
        prob_col = 'p_top5'
    else:
        logger.warning(f"k={k} not supported. Using p_top3.")
        prob_col = 'p_top3'
        k = 3

    # Get top N hubs by the probability metric
    top_hubs = rank_stats.nlargest(top_n, prob_col)

    # Create figure
    fig, ax = plt.subplots(figsize=figsize)

    bars = ax.bar(
        range(len(top_hubs)),
        top_hubs[prob_col].values,
        color='#2ecc71',
        edgecolor='#27ae60',
        alpha=0.8
    )

    # Add value labels on bars
    for bar, val in zip(bars, top_hubs[prob_col].values):
        if val >= 0.01:  # Only label if visible
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.01,
                f'{val:.1%}',
                ha='center',
                va='bottom',
                fontsize=8
            )

    ax.set_xticks(range(len(top_hubs)))
    ax.set_xticklabels([str(h) for h in top_hubs.index], rotation=45, ha='right')
    ax.set_xlabel('Hub ID', fontsize=12)
    ax.set_ylabel(f'Probability of Ranking in Top {k}', fontsize=12)
    ax.set_title(f'Top-{k} Ranking Probability - Top {len(top_hubs)} Hubs', fontsize=14)
    ax.set_ylim(0, min(1.0, top_hubs[prob_col].max() * 1.2))

    # Add grid
    ax.yaxis.grid(True, linestyle='--', alpha=0.7)

    plt.tight_layout()

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    logger.info(f"✓ Top-{k} probability chart saved to {output_path}")


def create_hub_distribution_histogram(
    scores: np.ndarray,
    hub_id: str,
    output_path: Path,
    dist_stats: pd.DataFrame,
    n_bins: int = MC_DIST_HISTOGRAM_BINS,
    figsize: Tuple[int, int] = (10, 6),
) -> None:
    """
    Create histogram of score distribution for a single hub.

    Shows distribution with reference lines at P10, P50 (median), and P90.

    Args:
        scores: 1D array of simulated scores for this hub
        hub_id: Hub identifier (for title and filename)
        output_path: Path for output PNG file
        dist_stats: DataFrame with percentile values for this hub
        n_bins: Number of histogram bins
        figsize: Figure size tuple
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.use('Agg')
    except ImportError:
        logger.warning("matplotlib not available. Skipping histogram generation.")
        return

    # Get percentiles for this hub
    if hub_id in dist_stats.index:
        p10 = dist_stats.loc[hub_id, 'p10_score']
        p50 = dist_stats.loc[hub_id, 'median_score']
        p90 = dist_stats.loc[hub_id, 'p90_score']
    else:
        # Calculate directly if not available
        p10 = np.percentile(scores, 10)
        p50 = np.percentile(scores, 50)
        p90 = np.percentile(scores, 90)

    # Create figure
    fig, ax = plt.subplots(figsize=figsize)

    # Histogram
    ax.hist(
        scores,
        bins=n_bins,
        color='#3498db',
        edgecolor='#2980b9',
        alpha=0.7,
        density=False
    )

    # Add percentile reference lines
    ax.axvline(p10, color='#e74c3c', linestyle='--', linewidth=2, label=f'P10: {p10:.3f}')
    ax.axvline(p50, color='#f39c12', linestyle='-', linewidth=2, label=f'P50: {p50:.3f}')
    ax.axvline(p90, color='#27ae60', linestyle='--', linewidth=2, label=f'P90: {p90:.3f}')

    ax.set_xlabel('Simulated Score', fontsize=12)
    ax.set_ylabel('Frequency', fontsize=12)
    ax.set_title(f'Score Distribution - Hub {hub_id}', fontsize=14)
    ax.legend(loc='upper right')

    # Add grid
    ax.yaxis.grid(True, linestyle='--', alpha=0.7)

    plt.tight_layout()

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)


def create_all_hub_histograms(
    iteration_scores: np.ndarray,
    hub_ids: pd.Index,
    dist_stats: pd.DataFrame,
    output_dir: Path,
    max_hubs: Optional[int] = None,
    n_bins: int = MC_DIST_HISTOGRAM_BINS,
) -> None:
    """
    Create distribution histograms for all hubs (or top N).

    Args:
        iteration_scores: Array of shape (n_hubs, n_iterations)
        hub_ids: Index of hub identifiers
        dist_stats: DataFrame with distribution statistics
        output_dir: Directory for output PNG files (will create 'hubs' subdirectory)
        max_hubs: Maximum number of hub histograms to create (None for all)
        n_bins: Number of histogram bins
    """
    logger.info(f"Creating per-hub distribution histograms...")

    hubs_dir = output_dir / 'hubs'
    hubs_dir.mkdir(parents=True, exist_ok=True)

    # Determine which hubs to process
    if max_hubs is not None and max_hubs < len(hub_ids):
        # Process top N hubs by mean_score
        top_hubs = dist_stats.nlargest(max_hubs, 'mean_score').index
        hub_list = list(top_hubs)
        logger.info(f"  Creating histograms for top {max_hubs} hubs by mean_score")
    else:
        hub_list = list(hub_ids)
        logger.info(f"  Creating histograms for all {len(hub_list)} hubs")

    # Create histograms
    hub_id_to_idx = {h: i for i, h in enumerate(hub_ids)}

    for hub_id in hub_list:
        idx = hub_id_to_idx.get(hub_id)
        if idx is None:
            continue

        scores = iteration_scores[idx, :]

        # Clean hub_id for filename
        safe_hub_id = str(hub_id).replace('/', '_').replace('\\', '_').replace(' ', '_')
        output_path = hubs_dir / f'{safe_hub_id}_distribution.png'

        create_hub_distribution_histogram(
            scores=scores,
            hub_id=str(hub_id),
            output_path=output_path,
            dist_stats=dist_stats,
            n_bins=n_bins
        )

    logger.info(f"✓ Created {len(hub_list)} hub histograms in {hubs_dir}")


# ============================================================================
# MAIN ORCHESTRATION FUNCTION
# ============================================================================

class MCDistributionResults:
    """Container for Monte Carlo distribution analysis results."""

    def __init__(
        self,
        iteration_scores: np.ndarray,
        iteration_ranks: np.ndarray,
        hub_ids: pd.Index,
        dist_stats: pd.DataFrame,
        rank_stats: pd.DataFrame,
        n_iterations: int,
        min_weight: float,
        max_weight: float,
        random_seed: Optional[int],
        output_dir: Optional[Path] = None,
    ):
        self.iteration_scores = iteration_scores
        self.iteration_ranks = iteration_ranks
        self.hub_ids = hub_ids
        self.dist_stats = dist_stats
        self.rank_stats = rank_stats
        self.n_iterations = n_iterations
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.random_seed = random_seed
        self.output_dir = output_dir

    @property
    def combined_stats(self) -> pd.DataFrame:
        """Get combined distribution and rank statistics."""
        return self.dist_stats.join(self.rank_stats, how='outer')

    def get_hub_scores(self, hub_id) -> np.ndarray:
        """Get all iteration scores for a specific hub."""
        hub_list = list(self.hub_ids)
        if hub_id in hub_list:
            idx = hub_list.index(hub_id)
            return self.iteration_scores[idx, :]
        raise ValueError(f"Hub {hub_id} not found")

    def get_hub_ranks(self, hub_id) -> np.ndarray:
        """Get all iteration ranks for a specific hub."""
        hub_list = list(self.hub_ids)
        if hub_id in hub_list:
            idx = hub_list.index(hub_id)
            return self.iteration_ranks[idx, :]
        raise ValueError(f"Hub {hub_id} not found")


def run_mc_distribution_analysis(
    score_matrix: pd.DataFrame,
    output_dir: Optional[Union[str, Path]] = None,
    n_iterations: int = MONTE_CARLO_ITERATIONS,
    min_weight: float = MIN_CRITERION_WEIGHT,
    max_weight: float = MAX_CRITERION_WEIGHT,
    random_seed: Optional[int] = MONTE_CARLO_RANDOM_SEED,
    export_raw_scores: bool = MC_DIST_EXPORT_RAW_SCORES,
    create_visualizations: bool = True,
    top_n_for_plots: int = MC_DIST_TOP_N_HUBS,
    max_hub_histograms: Optional[int] = None,
    run_id: Optional[str] = None,
) -> MCDistributionResults:
    """
    Run complete Monte Carlo distribution analysis.

    This is the main entry point for MC distribution reporting. It:
    1. Runs Monte Carlo simulation with full score/rank tracking
    2. Calculates distribution statistics (mean, percentiles, std, etc.)
    3. Calculates rank robustness metrics (mean_rank, p_top1, p_top3, p_top5)
    4. Exports results to CSV
    5. Creates visualizations (boxplots, bar charts, histograms)

    Args:
        score_matrix: DataFrame with hubs as rows, criteria as columns.
                      Values should be normalized scores (typically 1-10).
        output_dir: Directory for outputs. If None, uses RESULTS_DIR/mc_run_<timestamp>.
                    If provided, outputs go to this directory.
        n_iterations: Number of Monte Carlo iterations (default: 10,000)
        min_weight: Minimum weight per criterion (default: 0.0)
        max_weight: Maximum weight per criterion (default: 0.5)
        random_seed: Random seed for reproducibility (None for non-deterministic)
        export_raw_scores: Whether to export raw scores in long format (default: True)
        create_visualizations: Whether to create PNG visualizations (default: True)
        top_n_for_plots: Number of top hubs for portfolio-level plots (default: 30)
        max_hub_histograms: Max number of per-hub histograms to create (None for all,
                           set to a number to limit when you have many hubs)
        run_id: Optional run identifier (used in output directory if output_dir not specified)

    Returns:
        MCDistributionResults object containing all results and statistics

    Example:
        >>> from src.scoring.mc_distribution import run_mc_distribution_analysis
        >>> results = run_mc_distribution_analysis(
        ...     score_matrix,
        ...     output_dir="outputs/my_analysis",
        ...     n_iterations=10000,
        ...     random_seed=42
        ... )
        >>> print(results.combined_stats.head())
        >>> # Access specific hub scores
        >>> hub_scores = results.get_hub_scores('hub_001')
    """
    logger.info("=" * 80)
    logger.info("MONTE CARLO DISTRIBUTION ANALYSIS")
    logger.info("=" * 80)

    # Setup output directory
    if output_dir is None:
        if run_id is None:
            run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = RESULTS_DIR / f'mc_run_{run_id}'
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")

    # Step 1: Run Monte Carlo simulation
    logger.info("\n" + "-" * 40)
    logger.info("Step 1: Monte Carlo Simulation")
    logger.info("-" * 40)

    iteration_scores, iteration_ranks = monte_carlo_with_distributions(
        score_matrix=score_matrix,
        n_iterations=n_iterations,
        min_weight=min_weight,
        max_weight=max_weight,
        random_seed=random_seed,
    )

    hub_ids = score_matrix.index

    # Step 2: Calculate distribution statistics
    logger.info("\n" + "-" * 40)
    logger.info("Step 2: Distribution Statistics")
    logger.info("-" * 40)

    dist_stats = calculate_distribution_statistics(iteration_scores, hub_ids)

    # Step 3: Calculate rank robustness metrics
    logger.info("\n" + "-" * 40)
    logger.info("Step 3: Rank Robustness Metrics")
    logger.info("-" * 40)

    rank_stats = calculate_rank_robustness(iteration_ranks, hub_ids)

    # Step 4: Export CSV files
    logger.info("\n" + "-" * 40)
    logger.info("Step 4: Export CSV Files")
    logger.info("-" * 40)

    # Main hub stats file
    hub_stats_path = output_dir / 'mc_hub_stats.csv'
    export_hub_stats_csv(
        dist_stats=dist_stats,
        rank_stats=rank_stats,
        output_path=hub_stats_path,
        n_iterations=n_iterations,
        min_weight=min_weight,
        max_weight=max_weight,
        random_seed=random_seed,
    )

    # Optional raw scores export
    if export_raw_scores:
        raw_scores_path = output_dir / 'mc_scores_long.csv'
        export_raw_scores_long(iteration_scores, hub_ids, raw_scores_path)

    # Step 5: Create visualizations
    if create_visualizations:
        logger.info("\n" + "-" * 40)
        logger.info("Step 5: Create Visualizations")
        logger.info("-" * 40)

        # Portfolio-level plots
        boxplot_path = output_dir / f'boxplot_scores_top{top_n_for_plots}.png'
        create_score_boxplot(
            iteration_scores=iteration_scores,
            hub_ids=hub_ids,
            dist_stats=dist_stats,
            output_path=boxplot_path,
            top_n=top_n_for_plots,
        )

        prob_chart_path = output_dir / f'prob_top3_top{top_n_for_plots}.png'
        create_top_k_probability_chart(
            rank_stats=rank_stats,
            output_path=prob_chart_path,
            k=3,
            top_n=top_n_for_plots,
        )

        # Per-hub histograms
        create_all_hub_histograms(
            iteration_scores=iteration_scores,
            hub_ids=hub_ids,
            dist_stats=dist_stats,
            output_dir=output_dir,
            max_hubs=max_hub_histograms,
        )

    # Create results object
    results = MCDistributionResults(
        iteration_scores=iteration_scores,
        iteration_ranks=iteration_ranks,
        hub_ids=hub_ids,
        dist_stats=dist_stats,
        rank_stats=rank_stats,
        n_iterations=n_iterations,
        min_weight=min_weight,
        max_weight=max_weight,
        random_seed=random_seed,
        output_dir=output_dir,
    )

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("ANALYSIS COMPLETE")
    logger.info("=" * 80)
    logger.info(f"\nResults Summary:")
    logger.info(f"  Hubs analyzed: {len(hub_ids)}")
    logger.info(f"  Iterations: {n_iterations:,}")
    logger.info(f"  Output directory: {output_dir}")
    logger.info(f"\nFiles created:")
    logger.info(f"  - mc_hub_stats.csv")
    if export_raw_scores:
        logger.info(f"  - mc_scores_long.csv")
    if create_visualizations:
        logger.info(f"  - boxplot_scores_top{top_n_for_plots}.png")
        logger.info(f"  - prob_top3_top{top_n_for_plots}.png")
        logger.info(f"  - hubs/<hub_id>_distribution.png")

    logger.info(f"\nTop 5 hubs by mean_score:")
    top5_mean = results.combined_stats.nlargest(5, 'mean_score')
    for hub_id, row in top5_mean.iterrows():
        logger.info(f"  {hub_id}: mean={row['mean_score']:.3f}, p_top3={row['p_top3']:.1%}")

    logger.info(f"\nTop 5 hubs by p_top3:")
    top5_p_top3 = results.combined_stats.nlargest(5, 'p_top3')
    for hub_id, row in top5_p_top3.iterrows():
        logger.info(f"  {hub_id}: mean={row['mean_score']:.3f}, p_top3={row['p_top3']:.1%}")

    return results


# ============================================================================
# DECISION SUPPORT UTILITIES
# ============================================================================

def get_conservative_ranking(
    results: MCDistributionResults,
    percentile: int = 10,
) -> pd.DataFrame:
    """
    Get hub ranking using conservative (low percentile) scores.

    Use p10_score or p25_score for risk-averse planning under uncertainty.

    Args:
        results: MCDistributionResults from run_mc_distribution_analysis
        percentile: Percentile to use (10 or 25)

    Returns:
        DataFrame sorted by conservative score, with columns for comparison
    """
    if percentile == 10:
        score_col = 'p10_score'
    elif percentile == 25:
        score_col = 'p25_score'
    else:
        raise ValueError("percentile must be 10 or 25")

    df = results.combined_stats[['mean_score', score_col, 'p_top3', 'mean_rank']].copy()
    df['conservative_rank'] = df[score_col].rank(ascending=False, method='min')
    df = df.sort_values(score_col, ascending=False)

    return df


def identify_robust_winners(
    results: MCDistributionResults,
    p_top_threshold: float = 0.5,
    k: int = 3,
) -> pd.DataFrame:
    """
    Identify hubs that are robust winners across weight variations.

    A "robust winner" has p_top_k >= threshold, meaning it ranks in top K
    in at least (threshold * 100)% of iterations.

    Args:
        results: MCDistributionResults from run_mc_distribution_analysis
        p_top_threshold: Minimum probability threshold (default: 0.5 = 50%)
        k: Top K ranking threshold (1, 3, or 5)

    Returns:
        DataFrame of robust winners sorted by p_top_k
    """
    if k == 1:
        prob_col = 'p_top1'
    elif k == 3:
        prob_col = 'p_top3'
    elif k == 5:
        prob_col = 'p_top5'
    else:
        raise ValueError("k must be 1, 3, or 5")

    df = results.combined_stats.copy()
    robust = df[df[prob_col] >= p_top_threshold].copy()
    robust = robust.sort_values(prob_col, ascending=False)

    logger.info(f"Identified {len(robust)} robust winners (p_top{k} >= {p_top_threshold:.0%})")

    return robust


def compare_hubs(
    results: MCDistributionResults,
    hub_ids: List,
) -> pd.DataFrame:
    """
    Compare distribution statistics for specific hubs.

    Useful for detailed comparison of candidate hubs.

    Args:
        results: MCDistributionResults from run_mc_distribution_analysis
        hub_ids: List of hub identifiers to compare

    Returns:
        DataFrame with comparison data for specified hubs
    """
    df = results.combined_stats.loc[hub_ids].copy()
    df['overall_rank_by_mean'] = results.combined_stats['mean_score'].rank(ascending=False, method='min')
    return df
