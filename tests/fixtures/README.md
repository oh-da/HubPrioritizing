# Test fixtures

## `real/` (not committed)

Golden-regression tests under `tests/golden/` and the real-sample checks in
`tests/unit/` use the planning team's actual exports. They are too large / too
sensitive to commit, so copy them here locally; every test that needs them skips
cleanly when the directory is empty.

Expected files (names are matched by the same patterns `hubs validate` uses):

| File | Role |
|---|---|
| `All_nodeslines_<ddmmyyyy>.csv` | node × line rows (cp1255, EPSG:2039) |
| `Lines_and_Planned_Mode_<dd-mm-yyyy>.csv` | line → mode/area (cp1255) |
| `Nodes_w_results_<ddmmyyyy>.xlsx` | demand workbook |
| `Routes_and_Nodes_<dd-mm-yyyy>.xlsx` | model routes (optional, stage 0) |
| `linesNames_noDuplicates.csv` | Hebrew line names (cp1255, headerless) |
| `lines_exploded.csv` | line status codes (legacy exploded format) |
| `BS_lines.csv` | line name corrections |
| `golden_hub_prioritization_results.xlsx` | the workbook the display page currently reads (oracle) |

The stable reference layers come from `data/reference/` and are committed.
