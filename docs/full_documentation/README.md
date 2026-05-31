# Hub Prioritization Framework — Full Documentation

**Centralized Logic for Assessing, Understanding & Determining Evaluation**
*Hub Prioritization Framework for Integrated Transport Hubs (מתח״מים) in Israel*

---

This folder contains the end-to-end documentation of the Hub Prioritization
model: the goal of the project, the inputs it consumes, every step of the
pipeline, the scoring methodology, and a code-level appendix.

It is written to be read by a new team member, a reviewer, or a future
maintainer who needs to understand the model without reading the source
code first.

## Reading order

| # | Document | Purpose |
|---|---------|---------|
| 01 | [Project Overview](01_project_overview.md) | Goal, problem, deliverables, hub hierarchy |
| 02 | [Inputs](02_inputs.md) | Every input data file the pipeline expects |
| 03 | [Pipeline Overview](03_pipeline_overview.md) | The 4 parts / 12 steps of the workflow at a glance |
| 04 | [Step-by-Step Details](04_step_by_step.md) | What each step does, in detail |
| 05 | [Scoring Methodology](05_scoring_methodology.md) | The five criteria + Monte Carlo + AHP |
| 06 | [Manual Corrections](06_manual_corrections.md) | Every human-in-the-loop override (IsSameGroup, demand fixes, AHP, hub names) |
| 07 | [Outputs](07_outputs.md) | Files produced and their schemas |
| A  | [Appendix — Code Reference](appendix_code_reference.md) | Modules, functions, configuration constants |

## Conventions

- **Hebrew terms** appear with their English equivalent on first use.
  Tier names are kept in Hebrew throughout (`ארצי` / `מטרופוליני` / `עירוני`)
  because that is how they appear in the codebase.
- **File paths** are shown relative to the repository root.
- **Code references** use the format `src/module.py:line` so they can be
  clicked or navigated to directly.
- **Manual corrections** are flagged with a 🔧 icon wherever they appear in
  the pipeline description.

## Version

- **Document version:** 1.0
- **Last updated:** 2026-05-31
- **Pipeline implementation reviewed:** `COMPLETE_TRANSIT_PIPELINE.ipynb`
  and the `src/` package as of branch `claude/optimistic-goodall-qCF5U`.
