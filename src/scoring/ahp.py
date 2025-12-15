"""
Analytic Hierarchy Process (AHP) Scoring
=========================================
Implements AHP methodology for multi-criteria decision making with expert panel input.

AHP provides a structured approach to deriving criterion weights through pairwise
comparisons, with built-in consistency checking to ensure logical expert judgments.

Key Features:
- Pairwise comparison matrix construction from expert input
- Consistency Ratio (CR) calculation and validation
- Multiple expert opinion aggregation
- Transparent, reproducible weight derivation
- Complementary to Monte Carlo approach

References:
    Saaty, T.L. (1980). The Analytic Hierarchy Process. McGraw-Hill.
    Saaty, T.L. (2008). Decision making with the analytic hierarchy process.
"""

import numpy as np
import pandas as pd
import geopandas as gpd
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import warnings

from ..config import (
    AHP_CONSISTENCY_RATIO_THRESHOLD,
    AHP_AGGREGATION_METHOD,
    AHP_SAATY_SCALE,
    SCORE_MIN,
    SCORE_MAX,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# RANDOM INDEX (RI) VALUES
# ============================================================================
# Used for consistency ratio calculation
# Source: Saaty (1980)
RANDOM_INDEX = {
    1: 0.00,
    2: 0.00,
    3: 0.58,
    4: 0.90,
    5: 1.12,
    6: 1.24,
    7: 1.32,
    8: 1.41,
    9: 1.45,
    10: 1.49,
    11: 1.51,
    12: 1.48,
    13: 1.56,
    14: 1.57,
    15: 1.59,
}


# ============================================================================
# CORE AHP FUNCTIONS
# ============================================================================


def validate_pairwise_matrix(matrix: np.ndarray) -> Tuple[bool, str]:
    """
    Validate that a pairwise comparison matrix meets AHP requirements.

    Args:
        matrix: Square pairwise comparison matrix

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check if square
    if matrix.shape[0] != matrix.shape[1]:
        return False, f"Matrix must be square, got shape {matrix.shape}"

    n = matrix.shape[0]

    # Check if all positive
    if np.any(matrix <= 0):
        return False, "All matrix values must be positive"

    # Check diagonal is all 1s
    if not np.allclose(np.diag(matrix), 1.0):
        return False, "Diagonal values must all be 1.0"

    # Check reciprocal property: A[i,j] * A[j,i] should equal 1
    for i in range(n):
        for j in range(i + 1, n):
            product = matrix[i, j] * matrix[j, i]
            if not np.isclose(product, 1.0, rtol=0.01):
                return False, f"Reciprocal property violated at ({i},{j}): {matrix[i,j]} * {matrix[j,i]} = {product}"

    return True, ""


def calculate_priority_vector(matrix: np.ndarray, method: str = 'eigenvector') -> np.ndarray:
    """
    Calculate priority weights from pairwise comparison matrix.

    Args:
        matrix: Square pairwise comparison matrix
        method: Calculation method ('eigenvector', 'geometric_mean', or 'normalized_column')

    Returns:
        Array of normalized priority weights

    Note:
        Eigenvector method is the most theoretically sound and is Saaty's recommended approach.
    """
    n = matrix.shape[0]

    if method == 'eigenvector':
        # Calculate principal eigenvector
        eigenvalues, eigenvectors = np.linalg.eig(matrix)

        # Get index of maximum eigenvalue
        max_idx = np.argmax(eigenvalues.real)
        max_eigenvector = eigenvectors[:, max_idx].real

        # Normalize to sum to 1
        weights = max_eigenvector / max_eigenvector.sum()

    elif method == 'geometric_mean':
        # Geometric mean of each row
        weights = np.array([np.prod(row) ** (1/n) for row in matrix])
        weights = weights / weights.sum()

    elif method == 'normalized_column':
        # Normalize each column, then average across rows
        normalized = matrix / matrix.sum(axis=0)
        weights = normalized.mean(axis=1)

    else:
        raise ValueError(f"Unknown method: {method}. Use 'eigenvector', 'geometric_mean', or 'normalized_column'")

    return weights


def calculate_consistency_ratio(matrix: np.ndarray, weights: np.ndarray) -> Tuple[float, float]:
    """
    Calculate Consistency Index (CI) and Consistency Ratio (CR).

    Args:
        matrix: Pairwise comparison matrix
        weights: Priority weights vector

    Returns:
        Tuple of (CI, CR)

    Note:
        CR < 0.10 indicates acceptable consistency
        CR < 0.08 for n=3, CR < 0.09 for n=4 are more stringent thresholds
    """
    n = matrix.shape[0]

    # Calculate maximum eigenvalue (λ_max)
    weighted_sum = matrix @ weights
    lambda_max = (weighted_sum / weights).mean()

    # Consistency Index (CI)
    ci = (lambda_max - n) / (n - 1) if n > 1 else 0

    # Consistency Ratio (CR)
    ri = RANDOM_INDEX.get(n, 1.49)  # Use max RI if n > 15
    cr = ci / ri if ri > 0 else 0

    return ci, cr


def load_expert_comparisons_from_csv(
    csv_path: Union[str, Path],
    criteria_names: Optional[List[str]] = None
) -> Dict[str, np.ndarray]:
    """
    Load expert pairwise comparisons from CSV file.

    Expected CSV format (Option 1 - Long format):
        expert,criterion_a,criterion_b,value
        expert1,activity,service,3
        expert1,activity,location,5
        ...

    Expected CSV format (Option 2 - Matrix format):
        Each expert has their own matrix with criteria as both rows and columns

    Args:
        csv_path: Path to CSV file
        criteria_names: List of criterion names (if None, auto-detect)

    Returns:
        Dictionary mapping expert names to pairwise comparison matrices
    """
    csv_path = Path(csv_path)

    if not csv_path.exists():
        raise FileNotFoundError(f"Expert comparison file not found: {csv_path}")

    logger.info(f"Loading expert comparisons from {csv_path}")

    # Try to read the CSV
    df = pd.read_csv(csv_path)

    # Detect format based on columns
    if 'expert' in df.columns and 'criterion_a' in df.columns and 'criterion_b' in df.columns:
        # Long format
        return _load_long_format(df, criteria_names)
    else:
        # Assume matrix format (multiple sheets or stacked matrices)
        return _load_matrix_format(csv_path, criteria_names)


def _load_long_format(df: pd.DataFrame, criteria_names: Optional[List[str]] = None) -> Dict[str, np.ndarray]:
    """Load expert comparisons from long format DataFrame."""
    expert_matrices = {}

    # Auto-detect criteria if not provided
    if criteria_names is None:
        criteria_names = sorted(set(df['criterion_a'].unique()) | set(df['criterion_b'].unique()))

    n = len(criteria_names)
    criteria_idx = {name: i for i, name in enumerate(criteria_names)}

    # Process each expert
    for expert in df['expert'].unique():
        expert_df = df[df['expert'] == expert]

        # Initialize matrix with 1s on diagonal
        matrix = np.eye(n)

        # Fill in pairwise comparisons
        for _, row in expert_df.iterrows():
            i = criteria_idx[row['criterion_a']]
            j = criteria_idx[row['criterion_b']]
            value = float(row['value'])

            matrix[i, j] = value
            matrix[j, i] = 1.0 / value  # Reciprocal

        expert_matrices[expert] = matrix

        # Validate
        is_valid, error_msg = validate_pairwise_matrix(matrix)
        if not is_valid:
            logger.warning(f"Expert '{expert}' matrix validation failed: {error_msg}")

    logger.info(f"Loaded {len(expert_matrices)} expert matrices for {n} criteria")
    logger.info(f"Criteria: {criteria_names}")

    return expert_matrices


def _load_matrix_format(csv_path: Path, criteria_names: Optional[List[str]] = None) -> Dict[str, np.ndarray]:
    """Load expert comparisons from matrix format (single or stacked)."""
    # For now, assume single expert matrix in CSV
    # Could be extended to handle Excel with multiple sheets

    df = pd.read_csv(csv_path, index_col=0)

    if criteria_names is None:
        criteria_names = list(df.columns)

    # Single expert named 'expert1' by default
    matrix = df.values.astype(float)

    expert_matrices = {'expert1': matrix}

    # Validate
    is_valid, error_msg = validate_pairwise_matrix(matrix)
    if not is_valid:
        logger.warning(f"Matrix validation failed: {error_msg}")

    logger.info(f"Loaded 1 expert matrix for {len(criteria_names)} criteria")
    logger.info(f"Criteria: {criteria_names}")

    return expert_matrices


def aggregate_expert_weights(
    expert_matrices: Dict[str, np.ndarray],
    method: str = 'geometric_mean',
    consistency_threshold: float = AHP_CONSISTENCY_RATIO_THRESHOLD
) -> Tuple[np.ndarray, Dict[str, Dict]]:
    """
    Aggregate weights from multiple experts.

    Args:
        expert_matrices: Dictionary mapping expert names to pairwise comparison matrices
        method: Aggregation method ('geometric_mean', 'arithmetic_mean', 'median')
        consistency_threshold: Maximum acceptable CR (experts exceeding this get flagged)

    Returns:
        Tuple of (aggregated_weights, expert_diagnostics)

    Note:
        Geometric mean is recommended for AHP weight aggregation (Saaty, 2008)
    """
    logger.info(f"Aggregating {len(expert_matrices)} expert opinions using {method}")

    expert_weights = []
    expert_diagnostics = {}

    # Calculate weights for each expert
    for expert_name, matrix in expert_matrices.items():
        # Calculate priority vector
        weights = calculate_priority_vector(matrix, method='eigenvector')

        # Calculate consistency
        ci, cr = calculate_consistency_ratio(matrix, weights)

        # Store diagnostics
        expert_diagnostics[expert_name] = {
            'weights': weights,
            'consistency_index': ci,
            'consistency_ratio': cr,
            'is_consistent': cr <= consistency_threshold,
        }

        # Warn if inconsistent
        if cr > consistency_threshold:
            logger.warning(
                f"Expert '{expert_name}' has high inconsistency: CR = {cr:.3f} "
                f"(threshold: {consistency_threshold:.2f})"
            )
        else:
            logger.info(f"Expert '{expert_name}': CR = {cr:.3f} ✓")

        expert_weights.append(weights)

    # Aggregate weights
    expert_weights_array = np.array(expert_weights)

    if method == 'geometric_mean':
        # Geometric mean (recommended)
        aggregated = np.exp(np.mean(np.log(expert_weights_array + 1e-10), axis=0))
        aggregated = aggregated / aggregated.sum()

    elif method == 'arithmetic_mean':
        # Arithmetic mean
        aggregated = expert_weights_array.mean(axis=0)
        aggregated = aggregated / aggregated.sum()

    elif method == 'median':
        # Median (robust to outliers)
        aggregated = np.median(expert_weights_array, axis=0)
        aggregated = aggregated / aggregated.sum()

    else:
        raise ValueError(f"Unknown aggregation method: {method}")

    logger.info("Aggregated weights:")
    for i, w in enumerate(aggregated):
        logger.info(f"  Criterion {i+1}: {w:.4f} ({w*100:.1f}%)")

    return aggregated, expert_diagnostics


# ============================================================================
# AHP SCORING FUNCTIONS
# ============================================================================


def calculate_ahp_scores(
    score_matrix: pd.DataFrame,
    ahp_weights: np.ndarray,
    score_columns: Optional[List[str]] = None,
) -> pd.Series:
    """
    Calculate AHP-weighted scores for hubs.

    Args:
        score_matrix: DataFrame with hubs as rows, criteria as columns
        ahp_weights: Array of criterion weights (must sum to 1)
        score_columns: List of score column names (if None, use all columns)

    Returns:
        Series of AHP scores
    """
    if score_columns is None:
        score_columns = list(score_matrix.columns)

    # Validate weights
    if len(ahp_weights) != len(score_columns):
        raise ValueError(
            f"Number of AHP weights ({len(ahp_weights)}) must match number of criteria ({len(score_columns)})"
        )

    if not np.isclose(ahp_weights.sum(), 1.0):
        logger.warning(f"AHP weights sum to {ahp_weights.sum():.4f}, normalizing to 1.0")
        ahp_weights = ahp_weights / ahp_weights.sum()

    logger.info("Calculating AHP scores...")
    logger.info(f"  Criteria weights:")
    for col, weight in zip(score_columns, ahp_weights):
        logger.info(f"    {col}: {weight:.4f} ({weight*100:.1f}%)")

    # Extract score matrix
    scores_array = score_matrix[score_columns].values

    # Calculate weighted scores
    ahp_scores = scores_array @ ahp_weights

    # Create Series with original index
    ahp_scores_series = pd.Series(ahp_scores, index=score_matrix.index)

    # Log statistics
    logger.info(f"✓ AHP scores calculated")
    logger.info(f"  Mean: {ahp_scores.mean():.2f}, Median: {np.median(ahp_scores):.2f}")
    logger.info(f"  Min: {ahp_scores.min():.2f}, Max: {ahp_scores.max():.2f}")
    logger.info(f"  Std Dev: {ahp_scores.std():.2f}")

    return ahp_scores_series


def run_ahp_scoring_pipeline(
    gdf: gpd.GeoDataFrame,
    expert_csv_path: Union[str, Path],
    score_columns: Optional[List[str]] = None,
    consistency_threshold: float = AHP_CONSISTENCY_RATIO_THRESHOLD,
    aggregation_method: str = AHP_AGGREGATION_METHOD,
    tier_column: str = 'tier',
    area_column: str = 'area',
) -> Tuple[gpd.GeoDataFrame, Dict]:
    """
    Run complete AHP scoring pipeline from expert comparisons to final scores.

    Ranking logic:
    - ארצי (National): All national hubs ranked together globally
    - מטרופוליני (Metropolitan): Ranked within their area
    - עירוני (Local): Ranked within their area

    Args:
        gdf: GeoDataFrame with individual criterion scores already calculated
        expert_csv_path: Path to CSV file with expert pairwise comparisons
        score_columns: List of score column names (if None, uses defaults)
        consistency_threshold: Maximum acceptable CR
        aggregation_method: How to aggregate multiple experts
        tier_column: Column name for hub tier classification
        area_column: Column name for geographic area

    Returns:
        Tuple of (GeoDataFrame with ahp_score column, diagnostics dictionary)
    """
    logger.info("="*80)
    logger.info("AHP SCORING PIPELINE")
    logger.info("="*80)

    # Default score columns
    if score_columns is None:
        score_columns = [
            'activity_score',
            'service_score',
            'location_score',
            'pop_jobs_score',
            'terminal_score'
        ]

    # Check that all score columns exist
    missing_cols = [col for col in score_columns if col not in gdf.columns]
    if missing_cols:
        raise ValueError(f"Missing score columns in GeoDataFrame: {missing_cols}")

    # 1. Load expert comparisons
    logger.info("\n1. Loading expert pairwise comparisons...")
    expert_matrices = load_expert_comparisons_from_csv(expert_csv_path, criteria_names=score_columns)

    # 2. Aggregate expert weights
    logger.info("\n2. Aggregating expert opinions...")
    ahp_weights, expert_diagnostics = aggregate_expert_weights(
        expert_matrices,
        method=aggregation_method,
        consistency_threshold=consistency_threshold
    )

    # 3. Calculate AHP scores
    logger.info("\n3. Calculating AHP scores...")
    score_matrix = gdf[score_columns]
    ahp_scores = calculate_ahp_scores(score_matrix, ahp_weights, score_columns)

    # 4. Add to GeoDataFrame
    gdf_ahp = gdf.copy()
    gdf_ahp['ahp_score'] = ahp_scores

    # 5. Add tier-based ranking (same logic as Monte Carlo)
    gdf_ahp['ahp_rank'] = _calculate_tier_based_ahp_ranking(
        gdf_ahp,
        tier_column=tier_column,
        area_column=area_column,
        score_column='ahp_score'
    )

    # 6. Create diagnostics summary
    diagnostics = {
        'expert_diagnostics': expert_diagnostics,
        'aggregated_weights': {col: w for col, w in zip(score_columns, ahp_weights)},
        'n_experts': len(expert_matrices),
        'n_criteria': len(score_columns),
        'aggregation_method': aggregation_method,
        'consistency_threshold': consistency_threshold,
        'n_inconsistent_experts': sum(
            1 for d in expert_diagnostics.values() if not d['is_consistent']
        ),
    }

    # Log summary
    logger.info("\n" + "="*80)
    logger.info("AHP SCORING COMPLETE")
    logger.info("="*80)
    logger.info(f"\n{len(gdf_ahp)} hubs scored using AHP methodology")
    logger.info(f"Experts consulted: {diagnostics['n_experts']}")
    logger.info(f"Inconsistent experts: {diagnostics['n_inconsistent_experts']}")

    # Top 10 hubs by AHP
    top_10 = gdf_ahp.nlargest(10, 'ahp_score')
    logger.info("\nTop 10 Hubs by AHP Score:")
    for i, (idx, row) in enumerate(top_10.iterrows(), 1):
        hub_id = row.get('group', idx)
        score = row['ahp_score']
        tier = row.get('tier', 'Unknown')
        logger.info(f"  {i}. Hub {hub_id} ({tier}): {score:.2f}")

    return gdf_ahp, diagnostics


def _calculate_tier_based_ahp_ranking(
    gdf: gpd.GeoDataFrame,
    tier_column: str = 'tier',
    area_column: str = 'area',
    score_column: str = 'ahp_score',
) -> pd.Series:
    """
    Calculate ranking based on hub type and area for AHP scores.

    Ranking logic:
    - ארצי (National): All national hubs ranked together globally
    - מטרופוליני (Metropolitan): Ranked within their area
    - עירוני (Local): Ranked within their area

    Args:
        gdf: GeoDataFrame with scores and tier/area columns
        tier_column: Column name for hub tier
        area_column: Column name for area
        score_column: Column name for score to rank by

    Returns:
        Series with ranking values
    """
    from ..config import TIER_NATIONAL, TIER_METRO, TIER_LOCAL

    # Initialize rank column with NaN
    ranks = pd.Series(index=gdf.index, dtype=float)

    # Check if required columns exist
    has_tier = tier_column in gdf.columns
    has_area = area_column in gdf.columns

    if not has_tier:
        logger.warning(f"Tier column '{tier_column}' not found. Using global ranking.")
        return gdf[score_column].rank(ascending=False, method='min')

    # ארצי (National): All ranked together globally
    national_mask = gdf[tier_column] == TIER_NATIONAL
    if national_mask.any():
        national_hubs = gdf[national_mask]
        ranks.loc[national_mask] = national_hubs[score_column].rank(ascending=False, method='min')
        logger.info(f"  AHP: Ranked {national_mask.sum()} ארצי (National) hubs globally")

    # מטרופוליני (Metropolitan) and עירוני (Local): Ranked within area
    for tier in [TIER_METRO, TIER_LOCAL]:
        tier_mask = gdf[tier_column] == tier

        if not tier_mask.any():
            continue

        if has_area:
            # Rank within each area
            tier_hubs = gdf[tier_mask]
            areas = tier_hubs[area_column].unique()

            for area in areas:
                area_mask = tier_mask & (gdf[area_column] == area)
                if area_mask.any():
                    area_hubs = gdf[area_mask]
                    ranks.loc[area_mask] = area_hubs[score_column].rank(ascending=False, method='min')

            logger.info(f"  AHP: Ranked {tier_mask.sum()} {tier} hubs within {len(areas)} areas")
        else:
            # No area column - rank all hubs of this tier together
            tier_hubs = gdf[tier_mask]
            ranks.loc[tier_mask] = tier_hubs[score_column].rank(ascending=False, method='min')
            logger.warning(f"  AHP: No area column - ranked {tier_mask.sum()} {tier} hubs globally")

    # Handle any remaining unranked hubs (e.g., "Not Hub", "Train Station")
    unranked_mask = ranks.isna()
    if unranked_mask.any():
        unranked_hubs = gdf[unranked_mask]
        ranks.loc[unranked_mask] = unranked_hubs[score_column].rank(ascending=False, method='min')
        logger.info(f"  AHP: Ranked {unranked_mask.sum()} other hubs globally")

    return ranks.astype(int)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def create_expert_template_csv(
    output_path: Union[str, Path],
    criteria_names: List[str],
    n_experts: int = 3,
    format: str = 'long'
) -> None:
    """
    Create a template CSV file for expert pairwise comparisons.

    Args:
        output_path: Path to save template CSV
        criteria_names: List of criterion names
        n_experts: Number of expert templates to create
        format: 'long' or 'matrix'
    """
    output_path = Path(output_path)

    if format == 'long':
        # Long format template
        rows = []
        for expert_num in range(1, n_experts + 1):
            expert_name = f"expert{expert_num}"

            # Generate all pairwise combinations
            for i, crit_a in enumerate(criteria_names):
                for j, crit_b in enumerate(criteria_names):
                    if i < j:  # Only upper triangle (avoid duplicates)
                        rows.append({
                            'expert': expert_name,
                            'criterion_a': crit_a,
                            'criterion_b': crit_b,
                            'value': 1,  # Neutral (equal importance)
                        })

        df = pd.DataFrame(rows)
        df.to_csv(output_path, index=False)

        logger.info(f"Created long-format template: {output_path}")
        logger.info(f"  {len(criteria_names)} criteria × {n_experts} experts")
        logger.info(f"  {len(df)} pairwise comparisons to fill")
        logger.info("\nInstructions:")
        logger.info("  - Use Saaty scale: 1=Equal, 3=Moderate, 5=Strong, 7=Very Strong, 9=Extreme")
        logger.info("  - For criterion_a vs criterion_b:")
        logger.info("    value > 1 means criterion_a is MORE important")
        logger.info("    value < 1 means criterion_b is MORE important")
        logger.info("    value = 1 means EQUAL importance")

    elif format == 'matrix':
        # Matrix format (one expert per file for simplicity, or stacked)
        # For single expert matrix
        matrix = pd.DataFrame(
            np.ones((len(criteria_names), len(criteria_names))),
            index=criteria_names,
            columns=criteria_names
        )
        matrix.to_csv(output_path)

        logger.info(f"Created matrix-format template: {output_path}")
        logger.info(f"  {len(criteria_names)} × {len(criteria_names)} matrix")
        logger.info("\nInstructions:")
        logger.info("  - Fill in pairwise comparisons (upper triangle)")
        logger.info("  - Diagonal should remain 1.0")
        logger.info("  - Lower triangle will be calculated automatically (reciprocals)")

    else:
        raise ValueError(f"Unknown format: {format}")


def compare_monte_carlo_vs_ahp(
    gdf: gpd.GeoDataFrame,
    monte_carlo_col: str = 'final_score',
    ahp_col: str = 'ahp_score',
    top_n: int = 20
) -> pd.DataFrame:
    """
    Compare rankings between Monte Carlo and AHP methods.

    Args:
        gdf: GeoDataFrame with both score types
        monte_carlo_col: Column name for Monte Carlo scores
        ahp_col: Column name for AHP scores
        top_n: Number of top hubs to compare

    Returns:
        DataFrame with comparison statistics
    """
    if monte_carlo_col not in gdf.columns or ahp_col not in gdf.columns:
        raise ValueError("Both scoring columns must exist in GeoDataFrame")

    # Calculate ranks
    mc_rank = gdf[monte_carlo_col].rank(ascending=False, method='min')
    ahp_rank = gdf[ahp_col].rank(ascending=False, method='min')

    # Correlation
    correlation = gdf[monte_carlo_col].corr(gdf[ahp_col])
    rank_correlation = mc_rank.corr(ahp_rank)

    logger.info("="*80)
    logger.info("MONTE CARLO vs AHP COMPARISON")
    logger.info("="*80)
    logger.info(f"\nScore correlation: {correlation:.3f}")
    logger.info(f"Rank correlation (Pearson): {rank_correlation:.3f}")

    # Top N comparison
    mc_top = set(gdf.nlargest(top_n, monte_carlo_col).index)
    ahp_top = set(gdf.nlargest(top_n, ahp_col).index)

    overlap = len(mc_top & ahp_top)
    overlap_pct = 100 * overlap / top_n

    logger.info(f"\nTop {top_n} hubs overlap: {overlap}/{top_n} ({overlap_pct:.1f}%)")

    # Disagreements (large rank differences)
    comparison_df = pd.DataFrame({
        'hub_id': gdf.index,
        'mc_score': gdf[monte_carlo_col],
        'ahp_score': gdf[ahp_col],
        'mc_rank': mc_rank,
        'ahp_rank': ahp_rank,
        'rank_diff': np.abs(mc_rank - ahp_rank),
    })

    # Largest disagreements
    disagreements = comparison_df.nlargest(10, 'rank_diff')

    logger.info("\nLargest ranking disagreements:")
    for _, row in disagreements.iterrows():
        logger.info(
            f"  Hub {row['hub_id']}: MC rank {int(row['mc_rank'])} vs AHP rank {int(row['ahp_rank'])} "
            f"(diff: {int(row['rank_diff'])})"
        )

    return comparison_df


# ============================================================================
# SAATY SCALE UTILITIES
# ============================================================================


def saaty_scale_description() -> pd.DataFrame:
    """Return the Saaty scale as a DataFrame for reference."""
    return pd.DataFrame({
        'Value': [1, 2, 3, 4, 5, 6, 7, 8, 9],
        'Importance': [
            'Equal',
            'Weak or slight',
            'Moderate',
            'Moderate plus',
            'Strong',
            'Strong plus',
            'Very strong',
            'Very, very strong',
            'Extreme',
        ],
        'Description': [
            'Two criteria contribute equally',
            'Experience slightly favors one over another',
            'Experience strongly favors one over another',
            'Intermediate value',
            'Experience very strongly favors one over another',
            'Intermediate value',
            'Importance of one over another is demonstrated in practice',
            'Intermediate value',
            'Importance of one over another is of the highest order',
        ]
    })


def print_saaty_scale():
    """Print the Saaty scale for expert reference."""
    scale_df = saaty_scale_description()
    print("\n" + "="*80)
    print("SAATY SCALE FOR PAIRWISE COMPARISONS")
    print("="*80)
    print(scale_df.to_string(index=False))
    print("\nNote: For reciprocals (when B is more important than A), use 1/value")
    print("="*80 + "\n")
