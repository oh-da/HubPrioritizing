# Hub Prioritization Framework — Full Documentation

**Centralized Logic for Assessing, Understanding & Determining Evaluation**
*Hub Prioritization Framework for Integrated Transport Hubs (מתח״מים) in Israel*

---

This folder contains the end-to-end documentation of the Hub Prioritization model: the goal
of the project, the inputs it consumes, every step of the pipeline, the scoring methodology,
and a code-level appendix.

It is written to be read by a new team member, a reviewer, or a future maintainer who needs
to understand the model without reading the source code first.

## Reading order

| # | Document | Purpose |
|---|---------|---------|
| 01 | [Project Overview](01_project_overview.md) | Goal, problem, deliverables, hub hierarchy |
| 02 | [Inputs](02_inputs.md) | The input directory contract and the reference layers |
| 03 | [Pipeline Overview](03_pipeline_overview.md) | The `hubs run` stages at a glance |
| 04 | [Step-by-Step Details](04_step_by_step.md) | What each step does, in detail |
| 05 | [Scoring Methodology](05_scoring_methodology.md) | The five criteria + Monte Carlo + AHP |
| 06 | [Manual Corrections](06_manual_corrections.md) | Every human-in-the-loop data file |
| 07 | [Outputs](07_outputs.md) | Files produced and the 70-column workbook schema |
| A  | [Appendix — Code Reference](appendix_code_reference.md) | Modules, functions, configuration constants |
| — | [Deviations](../DEVIATIONS.md) | Notebook quirks kept behind flags, and intentional fixes |

## Conventions

- **Hebrew terms** appear with their English equivalent on first use. Tier names are kept in
  Hebrew throughout (`ארצי` / `מטרופוליני` / `עירוני`) because that is how they appear in the data.
- **File paths** are shown relative to the repository root.
- **Manual corrections** are flagged with a 🔧 icon wherever they appear.
- Step numbers (1.3, 2.6.1 …) follow the archived notebook so older material stays readable.

## Version

- **Document version:** 2.0
- **Last updated:** 2026-09-16
- **Implementation documented:** `src/pipeline/` (the `hubs` command). The Colab notebooks it
  replaces are archived under `notebooks/archive/`; the pre-cleanup repository is tagged
  `v1-notebooks`.
