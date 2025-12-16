"""
Hub Scoring Module
==================
Provides scoring criteria and aggregation methods for hub prioritization.

Available Scoring Criteria:
- Activity Score: Based on passenger ridership (2050 forecast)
- Service Score: Multi-modal service hierarchy and diversity
- Location Score: Geographic and metropolitan position
- Demographics Score: Population and jobs in catchment area
- Terminal Score: Proximity to bus terminals

Aggregation Methods:
- Monte Carlo: Random weight simulation (default)
- AHP: Analytic Hierarchy Process with expert panel input
"""

# Individual scoring criteria
from .activity import calculate_activity_score
from .service import calculate_service_score
from .location import calculate_location_score
from .demographics import calculate_pop_jobs_score
from .terminals import calculate_terminal_score

# Monte Carlo scoring
from .monte_carlo import (
    monte_carlo_scoring,
    calculate_all_scores,
    calculate_final_scores,
    run_complete_scoring_pipeline,
    get_score_summary,
)

# Monte Carlo Distribution Reporting
from .mc_distribution import (
    run_mc_distribution_analysis,
    monte_carlo_with_distributions,
    calculate_distribution_statistics,
    calculate_rank_robustness,
    export_hub_stats_csv,
    export_raw_scores_long,
    create_score_boxplot,
    create_top_k_probability_chart,
    create_hub_distribution_histogram,
    create_all_hub_histograms,
    get_conservative_ranking,
    identify_robust_winners,
    compare_hubs,
    MCDistributionResults,
)

# AHP scoring
from .ahp import (
    run_ahp_scoring_pipeline,
    calculate_ahp_scores,
    load_expert_comparisons_from_csv,
    aggregate_expert_weights,
    create_expert_template_csv,
    compare_monte_carlo_vs_ahp,
    print_saaty_scale,
    saaty_scale_description,
)

__all__ = [
    # Individual criteria
    'calculate_activity_score',
    'calculate_service_score',
    'calculate_location_score',
    'calculate_pop_jobs_score',
    'calculate_terminal_score',

    # Monte Carlo
    'monte_carlo_scoring',
    'calculate_all_scores',
    'calculate_final_scores',
    'run_complete_scoring_pipeline',
    'get_score_summary',

    # Monte Carlo Distribution Reporting
    'run_mc_distribution_analysis',
    'monte_carlo_with_distributions',
    'calculate_distribution_statistics',
    'calculate_rank_robustness',
    'export_hub_stats_csv',
    'export_raw_scores_long',
    'create_score_boxplot',
    'create_top_k_probability_chart',
    'create_hub_distribution_histogram',
    'create_all_hub_histograms',
    'get_conservative_ranking',
    'identify_robust_winners',
    'compare_hubs',
    'MCDistributionResults',

    # AHP
    'run_ahp_scoring_pipeline',
    'calculate_ahp_scores',
    'load_expert_comparisons_from_csv',
    'aggregate_expert_weights',
    'create_expert_template_csv',
    'compare_monte_carlo_vs_ahp',
    'print_saaty_scale',
    'saaty_scale_description',
]
