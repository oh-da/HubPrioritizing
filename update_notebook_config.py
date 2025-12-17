#!/usr/bin/env python3
"""
Update COMPLETE_TRANSIT_PIPELINE.ipynb to use config.py and add latest features.

This script:
1. Adds imports from src.config
2. Replaces hardcoded values with config references
3. Adds Monte Carlo distribution analysis capability
4. Adds AHP scoring capability
5. Adds non-rail transit mode filtering
"""

import json
import sys
from pathlib import Path

# Notebook path
NOTEBOOK_PATH = Path(__file__).parent / "COMPLETE_TRANSIT_PIPELINE.ipynb"
BACKUP_PATH = Path(__file__).parent / "COMPLETE_TRANSIT_PIPELINE.ipynb.backup"

def load_notebook(path):
    """Load Jupyter notebook JSON."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_notebook(nb, path):
    """Save Jupyter notebook JSON."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)

def create_code_cell(source_lines):
    """Create a code cell from list of source lines."""
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source_lines
    }

def create_markdown_cell(source_lines):
    """Create a markdown cell from list of source lines."""
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source_lines
    }

def update_imports_cell(nb):
    """Update the imports cell to include src.config imports."""
    # Find the first code cell (imports)
    for i, cell in enumerate(nb['cells']):
        if cell['cell_type'] == 'code' and any('import h3' in line for line in cell['source']):
            print(f"✓ Found imports cell at index {i}")

            # Updated imports with src.config
            new_imports = [
                "import h3\n",
                "import numpy as np\n",
                "import pandas as pd\n",
                "import geopandas as gpd\n",
                "from shapely.geometry import Point, Polygon\n",
                "from shapely import wkt\n",
                "from geopy.geocoders import Nominatim\n",
                "from geopy.extra.rate_limiter import RateLimiter\n",
                "import warnings\n",
                "import os\n",
                "import sys\n",
                "warnings.filterwarnings('ignore')\n",
                "\n",
                "# Add src directory to path for config imports\n",
                "project_root = os.path.abspath('.')\n",
                "if project_root not in sys.path:\n",
                "    sys.path.insert(0, project_root)\n",
                "\n",
                "# Import configuration from src.config\n",
                "from src.config import (\n",
                "    H3_RESOLUTION,\n",
                "    HUB_MERGE_THRESHOLD_M,\n",
                "    MONTE_CARLO_ITERATIONS,\n",
                "    MONTE_CARLO_RANDOM_SEED,\n",
                "    MODE_WEIGHTS,\n",
                "    TIER_NATIONAL,\n",
                "    TIER_METRO,\n",
                "    TIER_LOCAL,\n",
                "    DISTANCE_DECAY_BETA,\n",
                "    CRS_WGS84,\n",
                "    CRS_ISRAEL_TM,\n",
                "    ELIGIBILITY_MIN_PASSENGERS,\n",
                "    ELIGIBILITY_MIN_MODES,\n",
                "    REQUIRE_NON_RAIL_MODE,\n",
                "    RAIL_ONLY_MODES,\n",
                "    NON_RAIL_TRANSIT_MODES,\n",
                "    AHP_ENABLED,\n",
                "    AHP_EXPERT_CSV_PATH,\n",
                "    MC_DIST_EXPORT_RAW_SCORES,\n",
                "    MC_DIST_TOP_N_HUBS,\n",
                ")\n",
                "\n",
                "print(\"✓ All libraries and configuration loaded successfully!\")\n",
                "print(f\"\\nConfiguration from src/config.py:\")\n",
                "print(f\"  H3_RESOLUTION: {H3_RESOLUTION}\")\n",
                "print(f\"  HUB_MERGE_THRESHOLD_M: {HUB_MERGE_THRESHOLD_M}m\")\n",
                "print(f\"  MONTE_CARLO_ITERATIONS: {MONTE_CARLO_ITERATIONS:,}\")\n",
                "print(f\"  REQUIRE_NON_RAIL_MODE: {REQUIRE_NON_RAIL_MODE}\")\n",
                "print(f\"  AHP_ENABLED: {AHP_ENABLED}\")\n"
            ]

            cell['source'] = new_imports
            return True

    return False

def update_config_cells(nb):
    """Update configuration cells to use imported config values."""
    updates_made = 0

    for i, cell in enumerate(nb['cells']):
        if cell['cell_type'] != 'code':
            continue

        source = ''.join(cell['source'])

        # Update H3_RESOLUTION references
        if 'H3_RESOLUTION = 10' in source:
            print(f"✓ Updating H3_RESOLUTION at cell {i}")
            cell['source'] = [line.replace('H3_RESOLUTION = 10', '# H3_RESOLUTION imported from config')
                             for line in cell['source']]
            updates_made += 1

        # Update BUFFER_DISTANCE references
        if 'BUFFER_DISTANCE = 120' in source:
            print(f"✓ Replacing BUFFER_DISTANCE with HUB_MERGE_THRESHOLD_M at cell {i}")
            cell['source'] = [line.replace('BUFFER_DISTANCE = 120', 'BUFFER_DISTANCE = HUB_MERGE_THRESHOLD_M  # From config')
                             for line in cell['source']]
            updates_made += 1

        # Update MONTE_CARLO_ITERATIONS references
        if 'MONTE_CARLO_ITERATIONS = 10000' in source:
            print(f"✓ Updating MONTE_CARLO_ITERATIONS at cell {i}")
            cell['source'] = [line.replace('MONTE_CARLO_ITERATIONS = 10000', '# MONTE_CARLO_ITERATIONS imported from config')
                             for line in cell['source']]
            updates_made += 1

        # Update RANDOM_SEED references
        if 'RANDOM_SEED = 42' in source:
            print(f"✓ Replacing RANDOM_SEED with MONTE_CARLO_RANDOM_SEED at cell {i}")
            cell['source'] = [line.replace('RANDOM_SEED = 42', 'RANDOM_SEED = MONTE_CARLO_RANDOM_SEED  # From config')
                             for line in cell['source']]
            updates_made += 1

        # Update MODE_WEIGHTS references
        if 'MODE_WEIGHTS = {' in source and 'Funicular' in source:
            print(f"✓ Updating MODE_WEIGHTS at cell {i}")
            # Find the MODE_WEIGHTS dict and comment it out
            new_source = []
            in_mode_weights = False
            for line in cell['source']:
                if 'MODE_WEIGHTS = {' in line:
                    new_source.append('# MODE_WEIGHTS imported from config\n')
                    new_source.append('# Original definition (now in src/config.py):\n')
                    new_source.append('# ' + line)
                    in_mode_weights = True
                elif in_mode_weights:
                    if '}' in line:
                        new_source.append('# ' + line)
                        in_mode_weights = False
                    else:
                        new_source.append('# ' + line)
                else:
                    new_source.append(line)
            cell['source'] = new_source
            updates_made += 1

        # Update CRS references
        if 'CRS_PROJECTED = "EPSG:2039"' in source:
            print(f"✓ Updating CRS references at cell {i}")
            cell['source'] = [line.replace('CRS_PROJECTED = "EPSG:2039"', 'CRS_PROJECTED = CRS_ISRAEL_TM  # From config')
                             for line in cell['source']]
            cell['source'] = [line.replace('CRS_WGS84 = "EPSG:4326"', '# CRS_WGS84 imported from config')
                             for line in cell['source']]
            updates_made += 1

    return updates_made

def add_nonrail_filtering_cell(nb):
    """Add a cell for non-rail transit mode filtering."""
    # Find the filtering section (look for eligibility filtering cells)
    insert_index = None
    for i, cell in enumerate(nb['cells']):
        if cell['cell_type'] == 'code':
            source = ''.join(cell['source'])
            if 'TotalDemand' in source and '>= 1000' in source:
                insert_index = i + 1
                break

    if insert_index is None:
        print("⚠ Could not find filtering section to add non-rail filtering")
        return False

    print(f"✓ Adding non-rail filtering cell at index {insert_index}")

    # Add markdown explanation
    nb['cells'].insert(insert_index, create_markdown_cell([
        "### Optional: Non-Rail Transit Mode Filtering\n",
        "\n",
        "**Configuration**: Set `REQUIRE_NON_RAIL_MODE = True` in `src/config.py` to enable this filter.\n",
        "\n",
        "When enabled, hubs must have at least one non-rail transit mode (Metro, LRT, or BRT) to be eligible. This excludes \"rail-only\" hubs that have combinations of:\n",
        "- Suburban Rail\n",
        "- Interurban Rail  \n",
        "- HighSpeed Rail\n",
        "- Generic Rail\n",
        "\n",
        "**Rationale**: True multimodal hubs should integrate urban transit (Metro/LRT/BRT) with rail, not just rail-to-rail transfers.\n"
    ]))

    # Add code cell
    nb['cells'].insert(insert_index + 1, create_code_cell([
        "# Non-rail transit mode filtering\n",
        "# This runs automatically if REQUIRE_NON_RAIL_MODE = True in config\n",
        "\n",
        "if REQUIRE_NON_RAIL_MODE:\n",
        "    print(f\"Non-rail mode filtering: ENABLED\")\n",
        "    print(f\"  Rail-only modes: {RAIL_ONLY_MODES}\")\n",
        "    print(f\"  Non-rail transit modes: {NON_RAIL_TRANSIT_MODES}\")\n",
        "    \n",
        "    # Check each hub for rail-only status\n",
        "    def is_rail_only(modes_list):\n",
        "        \"\"\"Check if hub has only rail modes (no Metro, LRT, BRT).\"\"\"\n",
        "        if not modes_list:\n",
        "            return False\n",
        "        return all(mode in RAIL_ONLY_MODES for mode in modes_list if mode is not None)\n",
        "    \n",
        "    # Assuming the filtered hubs are in df_filtered variable\n",
        "    if 'df_filtered' in globals():\n",
        "        initial_count = len(df_filtered)\n",
        "        \n",
        "        # Apply non-rail filter\n",
        "        df_filtered['is_rail_only'] = df_filtered['modes'].apply(is_rail_only)\n",
        "        rail_only_count = df_filtered['is_rail_only'].sum()\n",
        "        \n",
        "        df_filtered = df_filtered[~df_filtered['is_rail_only']].copy()\n",
        "        df_filtered = df_filtered.drop(columns=['is_rail_only'])\n",
        "        \n",
        "        print(f\"  ✓ Filtered out {rail_only_count} rail-only hubs\")\n",
        "        print(f\"  ✓ Remaining: {len(df_filtered)}/{initial_count} hubs\")\n",
        "    else:\n",
        "        print(\"  ⚠ df_filtered not found - run filtering steps first\")\n",
        "else:\n",
        "    print(f\"Non-rail mode filtering: DISABLED (REQUIRE_NON_RAIL_MODE = {REQUIRE_NON_RAIL_MODE})\")\n",
        "    print(f\"  All hubs with 2+ mass-transit modes are eligible, regardless of mode mix\")\n"
    ]))

    return True

def add_mc_distribution_cell(nb):
    """Add a cell for Monte Carlo distribution analysis."""
    # Find the scoring section (look for Monte Carlo section)
    insert_index = None
    for i, cell in enumerate(nb['cells']):
        if cell['cell_type'] == 'markdown':
            source = ''.join(cell['source'])
            if 'Monte Carlo' in source and 'Simulation' in source:
                # Insert after the Monte Carlo simulation cell
                insert_index = i + 2
                break

    if insert_index is None:
        print("⚠ Could not find Monte Carlo section to add distribution analysis")
        return False

    print(f"✓ Adding MC distribution analysis cell at index {insert_index}")

    # Add markdown explanation
    nb['cells'].insert(insert_index, create_markdown_cell([
        "### Optional: Monte Carlo Distribution Analysis\n",
        "\n",
        "**Extended Monte Carlo Analysis** with full distribution reporting:\n",
        "- Distribution statistics per hub (mean, median, percentiles, std)\n",
        "- Rank robustness metrics (mean_rank, p_top1, p_top3, p_top5)\n",
        "- Visualizations: boxplots, probability charts, per-hub histograms\n",
        "- CSV export for detailed analysis\n",
        "\n",
        "This provides deeper insight into score uncertainty and ranking robustness.\n"
    ]))

    # Add code cell
    nb['cells'].insert(insert_index + 1, create_code_cell([
        "# Optional: Run Monte Carlo Distribution Analysis\n",
        "# Provides full distribution statistics and visualizations\n",
        "\n",
        "RUN_MC_DISTRIBUTION = True  # Set to False to skip\n",
        "\n",
        "if RUN_MC_DISTRIBUTION:\n",
        "    print(\"Running Monte Carlo Distribution Analysis...\")\n",
        "    print(\"This may take a few minutes...\\n\")\n",
        "    \n",
        "    try:\n",
        "        from src.scoring.mc_distribution import run_mc_distribution_analysis\n",
        "        \n",
        "        # Prepare score matrix (assuming scored hubs are in df_scored)\n",
        "        if 'df_scored' in globals():\n",
        "            score_columns = [\n",
        "                'activity_score', 'service_score', 'location_score',\n",
        "                'pop_jobs_score', 'terminal_score'\n",
        "            ]\n",
        "            \n",
        "            # Check all columns exist\n",
        "            missing_cols = [c for c in score_columns if c not in df_scored.columns]\n",
        "            if missing_cols:\n",
        "                print(f\"⚠ Missing score columns: {missing_cols}\")\n",
        "                print(\"  Run scoring steps first\")\n",
        "            else:\n",
        "                # Extract score matrix\n",
        "                score_matrix = df_scored[score_columns].copy()\n",
        "                score_matrix.index = df_scored.index\n",
        "                \n",
        "                # Run distribution analysis\n",
        "                mc_results = run_mc_distribution_analysis(\n",
        "                    score_matrix=score_matrix,\n",
        "                    output_dir=OUTPUT_DIR + '/mc_distribution',\n",
        "                    n_iterations=MONTE_CARLO_ITERATIONS,\n",
        "                    random_seed=MONTE_CARLO_RANDOM_SEED,\n",
        "                    export_raw_scores=MC_DIST_EXPORT_RAW_SCORES,\n",
        "                    create_visualizations=True,\n",
        "                    top_n_for_plots=MC_DIST_TOP_N_HUBS,\n",
        "                )\n",
        "                \n",
        "                print(\"\\n✓ MC Distribution Analysis complete!\")\n",
        "                print(f\"  Results saved to: {OUTPUT_DIR}/mc_distribution/\")\n",
        "                print(f\"  Files: mc_hub_stats.csv, visualizations (PNG)\")\n",
        "                \n",
        "                # Display top hubs by robustness\n",
        "                print(\"\\nTop 10 Most Robust Hubs (by p_top3):\")\n",
        "                top_robust = mc_results.combined_stats.nlargest(10, 'p_top3')\n",
        "                for rank, (hub_id, row) in enumerate(top_robust.iterrows(), 1):\n",
        "                    print(f\"  {rank}. Hub {hub_id}: p_top3={row['p_top3']:.1%}, mean_score={row['mean_score']:.2f}\")\n",
        "        else:\n",
        "            print(\"⚠ df_scored not found - run scoring steps first\")\n",
        "    \n",
        "    except ImportError as e:\n",
        "        print(f\"⚠ Could not import mc_distribution module: {e}\")\n",
        "        print(\"  Ensure src/scoring/mc_distribution.py is available\")\n",
        "    except Exception as e:\n",
        "        print(f\"⚠ MC Distribution Analysis failed: {e}\")\n",
        "        import traceback\n",
        "        traceback.print_exc()\n",
        "else:\n",
        "    print(\"MC Distribution Analysis: SKIPPED (RUN_MC_DISTRIBUTION = False)\")\n"
    ]))

    return True

def add_ahp_scoring_cell(nb):
    """Add a cell for AHP scoring."""
    # Find after MC distribution cell
    insert_index = None
    for i, cell in enumerate(nb['cells']):
        if cell['cell_type'] == 'code':
            source = ''.join(cell['source'])
            if 'MC Distribution Analysis' in source or 'mc_distribution' in source:
                insert_index = i + 1
                break

    if insert_index is None:
        # Fall back to after Monte Carlo section
        for i, cell in enumerate(nb['cells']):
            if cell['cell_type'] == 'markdown':
                source = ''.join(cell['source'])
                if 'Monte Carlo' in source:
                    insert_index = i + 3
                    break

    if insert_index is None:
        print("⚠ Could not find location to add AHP scoring cell")
        return False

    print(f"✓ Adding AHP scoring cell at index {insert_index}")

    # Add markdown explanation
    nb['cells'].insert(insert_index, create_markdown_cell([
        "### Optional: AHP (Analytic Hierarchy Process) Scoring\n",
        "\n",
        "**Expert-Driven Weighting Alternative** to Monte Carlo:\n",
        "- Uses expert pairwise comparisons (Saaty scale 1-9)\n",
        "- Systematic weight derivation via eigenvector method\n",
        "- Consistency checking (CR < 0.10)\n",
        "- Compare AHP results with Monte Carlo for validation\n",
        "\n",
        "**Configuration**: Set `AHP_ENABLED = True` in `src/config.py` and provide expert comparisons CSV.\n",
        "\n",
        "See `docs/AHP_SCORING_GUIDE.md` for details.\n"
    ]))

    # Add code cell
    nb['cells'].insert(insert_index + 1, create_code_cell([
        "# Optional: Run AHP Scoring\n",
        "# Expert-driven alternative to Monte Carlo weighting\n",
        "\n",
        "if AHP_ENABLED:\n",
        "    print(\"AHP Scoring: ENABLED\")\n",
        "    print(f\"  Expert CSV path: {AHP_EXPERT_CSV_PATH}\\n\")\n",
        "    \n",
        "    try:\n",
        "        from pathlib import Path\n",
        "        from src.scoring.ahp import run_ahp_scoring_pipeline, compare_monte_carlo_vs_ahp\n",
        "        \n",
        "        # Check if expert CSV exists\n",
        "        if not Path(AHP_EXPERT_CSV_PATH).exists():\n",
        "            print(f\"⚠ AHP expert CSV not found: {AHP_EXPERT_CSV_PATH}\")\n",
        "            print(\"  To use AHP scoring:\")\n",
        "            print(\"  1. Create expert comparisons CSV (see data/ahp_expert_comparisons_TEMPLATE.csv)\")\n",
        "            print(\"  2. Update AHP_EXPERT_CSV_PATH in src/config.py\")\n",
        "            print(\"  3. Set AHP_ENABLED = True\")\n",
        "        else:\n",
        "            # Run AHP scoring (assuming df_scored exists with Monte Carlo results)\n",
        "            if 'df_scored' in globals() and 'final_score' in df_scored.columns:\n",
        "                print(\"Running AHP scoring pipeline...\\n\")\n",
        "                \n",
        "                df_scored_ahp, ahp_diagnostics = run_ahp_scoring_pipeline(\n",
        "                    df_scored,\n",
        "                    expert_csv_path=str(AHP_EXPERT_CSV_PATH),\n",
        "                )\n",
        "                \n",
        "                # Update df_scored with AHP results\n",
        "                df_scored = df_scored_ahp\n",
        "                \n",
        "                print(\"\\n✓ AHP Scoring complete!\")\n",
        "                print(f\"  New columns added: ahp_score, ahp_rank\")\n",
        "                \n",
        "                # Compare methods\n",
        "                print(\"\\nComparing Monte Carlo vs AHP:\")\n",
        "                comparison = compare_monte_carlo_vs_ahp(df_scored)\n",
        "                print(f\"  Correlation (scores): {comparison['score_correlation']:.3f}\")\n",
        "                print(f\"  Rank agreement (top 10): {comparison['top10_overlap']}/10\")\n",
        "                \n",
        "                # Display top hubs by AHP\n",
        "                print(\"\\nTop 10 Hubs by AHP Score:\")\n",
        "                top_ahp = df_scored.nlargest(10, 'ahp_score')\n",
        "                for rank, (idx, row) in enumerate(top_ahp.iterrows(), 1):\n",
        "                    hub_id = row.get('group', idx)\n",
        "                    ahp = row['ahp_score']\n",
        "                    mc = row['final_score']\n",
        "                    print(f\"  {rank}. Hub {hub_id}: AHP={ahp:.2f}, MC={mc:.2f}\")\n",
        "            else:\n",
        "                print(\"⚠ df_scored not found or missing final_score column\")\n",
        "                print(\"  Run Monte Carlo scoring first\")\n",
        "    \n",
        "    except ImportError as e:\n",
        "        print(f\"⚠ Could not import AHP module: {e}\")\n",
        "        print(\"  Ensure src/scoring/ahp.py is available\")\n",
        "    except Exception as e:\n",
        "        print(f\"⚠ AHP Scoring failed: {e}\")\n",
        "        import traceback\n",
        "        traceback.print_exc()\n",
        "else:\n",
        "    print(f\"AHP Scoring: DISABLED (AHP_ENABLED = {AHP_ENABLED})\")\n",
        "    print(\"  Using Monte Carlo scoring only\")\n",
        "    print(\"  To enable: Set AHP_ENABLED = True in src/config.py\")\n"
    ]))

    return True

def main():
    """Main update function."""
    print("=" * 80)
    print("UPDATING COMPLETE_TRANSIT_PIPELINE.ipynb")
    print("=" * 80)
    print()

    # Load notebook
    print("Loading notebook...")
    nb = load_notebook(NOTEBOOK_PATH)
    print(f"✓ Loaded {len(nb['cells'])} cells\n")

    # Create backup
    print("Creating backup...")
    save_notebook(nb, BACKUP_PATH)
    print(f"✓ Backup saved to {BACKUP_PATH}\n")

    # Apply updates
    print("Applying updates...\n")

    # 1. Update imports
    if update_imports_cell(nb):
        print("✓ Imports updated\n")
    else:
        print("⚠ Could not update imports\n")

    # 2. Update config references
    updates = update_config_cells(nb)
    print(f"✓ Updated {updates} configuration references\n")

    # 3. Add non-rail filtering
    if add_nonrail_filtering_cell(nb):
        print("✓ Non-rail filtering cell added\n")

    # 4. Add MC distribution
    if add_mc_distribution_cell(nb):
        print("✓ MC distribution analysis cell added\n")

    # 5. Add AHP scoring
    if add_ahp_scoring_cell(nb):
        print("✓ AHP scoring cell added\n")

    # Save updated notebook
    print("Saving updated notebook...")
    save_notebook(nb, NOTEBOOK_PATH)
    print(f"✓ Saved to {NOTEBOOK_PATH}\n")

    print("=" * 80)
    print("UPDATE COMPLETE")
    print("=" * 80)
    print()
    print("Summary of changes:")
    print("  1. ✓ Added imports from src.config")
    print("  2. ✓ Replaced hardcoded values with config references")
    print("  3. ✓ Added non-rail transit mode filtering capability")
    print("  4. ✓ Added Monte Carlo distribution analysis section")
    print("  5. ✓ Added AHP scoring section")
    print()
    print(f"Backup available at: {BACKUP_PATH}")
    print()
    print("Next steps:")
    print("  1. Open the updated notebook")
    print("  2. Review the changes")
    print("  3. Configure settings in src/config.py:")
    print("     - REQUIRE_NON_RAIL_MODE (True/False)")
    print("     - AHP_ENABLED (True/False)")
    print("     - MC_DIST_EXPORT_RAW_SCORES (True/False)")
    print("  4. Run the notebook")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
