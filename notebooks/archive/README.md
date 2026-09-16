# Archived notebooks

These Colab notebooks were the production pipeline until September 2026. They are
**superseded by the `hubs run` command** (`src/pipeline/`), which reproduces their
results on the June 2026 exports (see `tests/golden/`), and are kept only for
provenance. Cell outputs were stripped to keep the repository small.

| Notebook | Role it played | Ported to |
|---|---|---|
| `COMPLETE_TRANSIT_PIPELINE.ipynb` | Parts 1-4: network, grouping, demand, influence area, scoring | `src/pipeline/{network,grouping,spatial_tags,demand,aggregate,scoring}.py` |
| `create_results_csv.ipynb` | Display columns for the results workbook | `src/pipeline/postprocess.py`, `export.py` |
| `add_hebrew_line_names.ipynb`, `hub_postprocess_line_status.ipynb`, `hub_data_postprocess.ipynb` | Earlier post-processing variants | `src/pipeline/postprocess.py` |
| `Group_n_Filter_Hubs.ipynb`, `HubsScoring_vAugust2025.ipynb`, `OldCode_AddingDemand_Data.ipynb`, `complete_hub_scoring_pipeline.ipynb` | Older iterations of the same logic | — |
| `map_hub_results.ipynb`, `test_spatial_alignment.ipynb` | Ad-hoc QA maps | — |
| `ahp_expert_questionnaire.ipynb` | AHP expert input (still usable; see `app/ahp_questionnaire.py`) | `src/scoring/ahp.py` |
| `grouped_hubs_ready_for_scoring_21082025.csv` | Sample intermediate the notebooks defaulted to | `tests/fixtures/` |

The full pre-cleanup repository state is tagged `v1-notebooks`
(`git checkout v1-notebooks`).
