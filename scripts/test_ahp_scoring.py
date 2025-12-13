#!/usr/bin/env python3
"""
Test AHP Scoring Functionality
================================
Simple script to test AHP scoring implementation with synthetic data.
"""

import numpy as np
import pandas as pd
import geopandas as gpd
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.scoring.ahp import (
    load_expert_comparisons_from_csv,
    aggregate_expert_weights,
    calculate_ahp_scores,
    run_ahp_scoring_pipeline,
    create_expert_template_csv,
    print_saaty_scale,
    saaty_scale_description,
)


def create_synthetic_hub_data(n_hubs=20):
    """Create synthetic hub data for testing."""
    print("Creating synthetic hub data...")

    np.random.seed(42)

    # Generate synthetic scores (1-10 scale)
    data = {
        'hub_id': [f'hub_{i:03d}' for i in range(1, n_hubs + 1)],
        'tier': np.random.choice(['ארצי', 'מטרופוליני', 'עירוני'], n_hubs, p=[0.2, 0.5, 0.3]),
        'activity_score': np.random.uniform(1, 10, n_hubs),
        'service_score': np.random.uniform(1, 10, n_hubs),
        'location_score': np.random.uniform(1, 10, n_hubs),
        'pop_jobs_score': np.random.uniform(1, 10, n_hubs),
        'terminal_score': np.random.uniform(1, 10, n_hubs),
    }

    # Create DataFrame
    df = pd.DataFrame(data)

    # Add dummy geometry
    df['geometry'] = [None] * n_hubs

    # Convert to GeoDataFrame
    gdf = gpd.GeoDataFrame(df, geometry='geometry')

    print(f"Created {n_hubs} synthetic hubs")
    print(f"  Tiers: {df['tier'].value_counts().to_dict()}")

    return gdf


def test_saaty_scale():
    """Test Saaty scale display."""
    print("\n" + "="*80)
    print("TEST 1: Saaty Scale Display")
    print("="*80)

    print_saaty_scale()

    scale_df = saaty_scale_description()
    print("\nSaaty Scale DataFrame shape:", scale_df.shape)

    print("✓ Saaty scale test passed")


def test_expert_template_creation():
    """Test expert template CSV creation."""
    print("\n" + "="*80)
    print("TEST 2: Expert Template Creation")
    print("="*80)

    output_path = project_root / 'data' / 'test_ahp_template.csv'

    criteria = [
        'activity_score',
        'service_score',
        'location_score',
        'pop_jobs_score',
        'terminal_score'
    ]

    create_expert_template_csv(
        output_path=output_path,
        criteria_names=criteria,
        n_experts=3,
        format='long'
    )

    # Verify file exists
    assert output_path.exists(), "Template file not created"

    # Read and check
    df = pd.read_csv(output_path)
    print(f"\nTemplate created with {len(df)} rows")
    print(f"Columns: {list(df.columns)}")
    print(f"Experts: {df['expert'].unique()}")

    # Clean up
    output_path.unlink()
    print("✓ Template creation test passed")


def test_expert_comparison_loading():
    """Test loading expert comparisons from CSV."""
    print("\n" + "="*80)
    print("TEST 3: Expert Comparison Loading")
    print("="*80)

    # Use the example file
    example_csv = project_root / 'data' / 'ahp_expert_comparisons_example.csv'

    if not example_csv.exists():
        print("⚠ Example CSV not found, skipping test")
        return

    criteria = [
        'activity_score',
        'service_score',
        'location_score',
        'pop_jobs_score',
        'terminal_score'
    ]

    expert_matrices = load_expert_comparisons_from_csv(
        csv_path=example_csv,
        criteria_names=criteria
    )

    print(f"\nLoaded {len(expert_matrices)} expert matrices")

    for expert, matrix in expert_matrices.items():
        print(f"\n{expert}:")
        print(f"  Matrix shape: {matrix.shape}")
        print(f"  Diagonal all 1s: {np.allclose(np.diag(matrix), 1.0)}")
        print(f"  All positive: {np.all(matrix > 0)}")

    print("✓ Expert comparison loading test passed")

    return expert_matrices


def test_weight_aggregation(expert_matrices):
    """Test weight aggregation from multiple experts."""
    print("\n" + "="*80)
    print("TEST 4: Weight Aggregation")
    print("="*80)

    if expert_matrices is None:
        print("⚠ No expert matrices available, skipping test")
        return None

    weights, diagnostics = aggregate_expert_weights(
        expert_matrices,
        method='geometric_mean',
        consistency_threshold=0.10
    )

    print(f"\nAggregated weights: {weights}")
    print(f"Sum: {weights.sum():.6f}")
    print(f"\nDiagnostics:")
    for expert, diag in diagnostics.items():
        print(f"  {expert}:")
        print(f"    CR: {diag['consistency_ratio']:.3f}")
        print(f"    Consistent: {diag['is_consistent']}")
        print(f"    Weights: {diag['weights']}")

    assert np.isclose(weights.sum(), 1.0), "Weights don't sum to 1"
    print("✓ Weight aggregation test passed")

    return weights


def test_ahp_scoring(weights):
    """Test AHP scoring on synthetic data."""
    print("\n" + "="*80)
    print("TEST 5: AHP Scoring")
    print("="*80)

    if weights is None:
        print("⚠ No weights available, skipping test")
        return

    # Create synthetic data
    gdf = create_synthetic_hub_data(n_hubs=20)

    score_columns = [
        'activity_score',
        'service_score',
        'location_score',
        'pop_jobs_score',
        'terminal_score'
    ]

    # Calculate AHP scores
    score_matrix = gdf[score_columns]
    ahp_scores = calculate_ahp_scores(score_matrix, weights, score_columns)

    print(f"\nAHP Scores calculated for {len(ahp_scores)} hubs")
    print(f"  Mean: {ahp_scores.mean():.2f}")
    print(f"  Median: {ahp_scores.median():.2f}")
    print(f"  Min: {ahp_scores.min():.2f}")
    print(f"  Max: {ahp_scores.max():.2f}")

    # Add to GeoDataFrame
    gdf['ahp_score'] = ahp_scores
    gdf['ahp_rank'] = ahp_scores.rank(ascending=False, method='min')

    # Top 5
    top_5 = gdf.nlargest(5, 'ahp_score')
    print("\nTop 5 Hubs by AHP Score:")
    for i, (idx, row) in enumerate(top_5.iterrows(), 1):
        print(f"  {i}. {row['hub_id']} ({row['tier']}): {row['ahp_score']:.2f}")

    print("✓ AHP scoring test passed")


def test_full_pipeline():
    """Test the complete AHP scoring pipeline."""
    print("\n" + "="*80)
    print("TEST 6: Full AHP Pipeline")
    print("="*80)

    # Create synthetic data
    gdf = create_synthetic_hub_data(n_hubs=20)

    # Use example CSV
    example_csv = project_root / 'data' / 'ahp_expert_comparisons_example.csv'

    if not example_csv.exists():
        print("⚠ Example CSV not found, skipping test")
        return

    try:
        # Run full pipeline
        gdf_ahp, diagnostics = run_ahp_scoring_pipeline(
            gdf,
            expert_csv_path=example_csv,
            consistency_threshold=0.10,
            aggregation_method='geometric_mean'
        )

        print(f"\nPipeline completed successfully")
        print(f"  {len(gdf_ahp)} hubs scored")
        print(f"  Columns: {list(gdf_ahp.columns)}")
        print(f"  AHP score range: {gdf_ahp['ahp_score'].min():.2f} - {gdf_ahp['ahp_score'].max():.2f}")

        print(f"\nDiagnostics:")
        print(f"  Experts consulted: {diagnostics['n_experts']}")
        print(f"  Criteria: {diagnostics['n_criteria']}")
        print(f"  Inconsistent experts: {diagnostics['n_inconsistent_experts']}")
        print(f"  Aggregation method: {diagnostics['aggregation_method']}")

        print(f"\nAggregated weights:")
        for criterion, weight in diagnostics['aggregated_weights'].items():
            print(f"  {criterion}: {weight:.4f} ({weight*100:.1f}%)")

        print("✓ Full pipeline test passed")

    except Exception as e:
        print(f"✗ Pipeline test failed: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run all tests."""
    print("="*80)
    print("AHP SCORING TESTS")
    print("="*80)

    try:
        # Test 1: Saaty scale
        test_saaty_scale()

        # Test 2: Template creation
        test_expert_template_creation()

        # Test 3: Load expert comparisons
        expert_matrices = test_expert_comparison_loading()

        # Test 4: Aggregate weights
        weights = test_weight_aggregation(expert_matrices)

        # Test 5: Calculate AHP scores
        test_ahp_scoring(weights)

        # Test 6: Full pipeline
        test_full_pipeline()

        print("\n" + "="*80)
        print("ALL TESTS COMPLETED SUCCESSFULLY ✓")
        print("="*80)

    except Exception as e:
        print(f"\n✗ Tests failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
