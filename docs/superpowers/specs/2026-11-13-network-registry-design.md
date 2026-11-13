# Network registry: managing lines and nodes per source project

Status: **draft plan**, written 2026-11-13 after a first conversation. Nothing is implemented.
Section 12 lists what is still open; we continue from there.

## 1. Purpose

The mass-transit network (lines and their nodes) is collected line by line from many projects.
Today it is kept as two national flat files that are edited by hand. Updating one line is
risky, updating many is a mess, and two projects that use the same line ID (for example
`BRT-1`) corrupt each other.

This plan adds a sub-process **before** `hubs run`: every source project keeps its own small
package of lines and nodes, and a build step checks the packages and assembles them into the
two files the pipeline already reads. Scoring, tiers and every output of `hubs run` stay
unchanged.

Success:

- updating one line, or thirty, is one command per delivery, with a report of exactly what
  changed before anything is replaced;
- a line ID used by two projects is caught at build time and can never merge silently;
- every line of a run can be traced to the project and the delivery it came from;
- building the registry from today's data reproduces the V1.1 files exactly.

## 2. How the network enters the model today

- `All_nodeslines*.csv` / `All_nodes+lines*.csv`: one row per node x line with ITM coordinates
  (V1.1: 5,048 rows, 229 lines). Required columns `node`, `LINE_ID`, and `X`/`Y` or `geometry`.
- `Lines_and_Planned_Mode*.csv`: one row per line with `Line_ModelName`, `Mode_Planned`,
  `Line_Name`, `Line_Description`, `Area` (V1.1: 270 rows).
- `src/pipeline/inputs.py` picks the newest file of each by the date in its name;
  `src/pipeline/network.py::attach_modes` joins them on the bare line ID.
- The only key is the `LINE_ID` text, nationwide. Nothing records the source project, the
  delivery date or the previous state of a line.
- Side tables keyed by the same bare ID: `linesNames*.csv`, `line_status*.csv`, `BS_lines*.csv`
  (per run) and `line_names_extra.csv` (reference).
- Demand is matched by **node ID** per regional model (`Nodes_w_results*.xlsx`, one sheet per
  model; the hexagon's area selects the model). Node IDs therefore have to be the regional
  model's IDs.
- `inputs.py` already declares two optional inputs for a "stage 0" that was never built:
  `Routes_and_Nodes*.xlsx` (Line, Node, IsStop, Include, PlannedMode) and `Nodes_coords*`
  (node, X, Y). No code reads them. This plan is that stage 0.

### What the V1.1 files show (inspected, not assumed)

| Problem | Evidence |
|---|---|
| Same ID, different lines | `m0610a`, `m0620a`, `m0810a`, `m0820a` each appear twice in the lines file with different routes (מטרונית 8 עכו-הדר and טכניון-בת גלים). `clean_lines_mode` keeps the first and warns. Harmless today only because the Haifa `^m` drop rule removes these lines anyway. |
| Collisions in the nodes file are invisible | Two lines that share an ID become one line with the union of their nodes. No check exists. |
| Lookalike IDs | `BRT-1` and `BRT1-1` (Tel Aviv), `BRT11` (Jerusalem), `brt011` (Haifa); `Red-N` (Tel Aviv) and `RedN` (Ashdod-Ashkelon). |
| Spelling drift between the two files | `BluRT1`/`BluRT2` in the nodes file, `BlueRT1`/`BlueRT2` in the lines file: the lines were excluded and hub 320 lost its BRT mode until commit `d50cd41`. |
| Orphans | 37 lines have a mode row but no nodes (30 after the `BlueRT` pair and the dropped Metronit are set aside; the rest need a decision each). |

### How deliveries arrive (from the conversation)

1. **Shapefiles**: a nodes layer plus a lines / line-segments layer.
2. **An Emme project**: the node table per line has to be extracted from it.

In most deliveries the nodes carry the regional model's node IDs. Sometimes they do not.

## 3. Goals, non-goals, anti-goals

Goals

- One package per source project, holding only that project's lines and nodes.
- Line identity = project + line ID.
- Two import doors (shapefiles, Emme export) that end in the same package format.
- A change report for every import, shown before the package is replaced.
- A build step with checks that writes the two files of section 2 plus a manifest.
- History of every change (what, when, from which delivery).

Non-goals

- No change to scoring, grouping, tiers or the 70-column workbook.
- No change to how demand is read.
- No route alignments. The pipeline needs nodes per line; line geometry in a delivery is used
  only to order nodes and for checks.
- Reading an Emme databank directly. Emme needs a licence; the door starts from tables exported
  from Emme.

Anti-goals

- A line silently renamed, merged or dropped by the build.
- A build whose result depends on file dates or on the order files were copied.
- A second place where the same line can be edited (the assembled files become build outputs,
  never hand-edited again).

## 4. Approaches considered

**A. Per-project registry + build step (chosen).** Projects live as folders of small CSV files;
`hubs network build` assembles them into the two existing input files. The pipeline is not
touched, so the golden tests keep guarding the results, and the registry can be proven correct
by rebuilding V1.1 exactly.

**B. Patch files on top of the national files.** Keep the two big files and add a
`line_updates.csv` layer (replace these lines with these rows). Cheapest to build, but the
national file stays the source of truth, a line still has no owner, and ID collisions stay
undetectable. It fixes next week and nothing after it.

**C. The pipeline reads project folders and uses a composite key.** Cleanest in theory, but the
line ID runs through hexagon aggregation, the workbook columns, the cell layer, the calculation
workbook and `hubs compare-network`. A large change to guarded code for no gain over A.

**D. A database (SQLite / PostGIS) as the registry.** Natural for SQL work, but a binary file
has no readable diff or review in git, and it adds a dependency. With A the CSV packages can be
loaded into SQLite or DuckDB at any time for analysis, so this stays available as a view.

A is chosen because it isolates projects, keeps the scored pipeline untouched and gives history
for free through git.

## 5. The registry

Proposed location: `data/network/` in this repository (see open question 12.2).

```
data/network/
├── README.md
├── projects/
│   ├── <project_id>/
│   │   ├── project.yaml        # who, what, which model, deliveries
│   │   ├── lines.csv           # one row per line of this project
│   │   └── line_nodes.csv      # one row per node of a line, in order
│   └── ...
└── aliases.csv                 # optional: resolved ID collisions (section 7)
```

`project.yaml`

| Field | Meaning |
|---|---|
| `project_id` | short stable key, lowercase, no spaces (`ta_lrt`, `haifa_brt`, `national_rail`) |
| `name` | display name, Hebrew allowed |
| `area` | the `Area` value written to the lines file (Tel Aviv, Haifa, National, ...) |
| `demand_model` | the regional model whose node IDs the project uses |
| `deliveries` | list: `date`, `source_type` (`shp` / `emme` / `manual`), `sender`, source file names with SHA-256, `lines` touched, `notes` |

`lines.csv`: `line_id, mode_planned, line_name, line_description, status, updated`

- `line_id` is the project's own ID, unique **within the project**.
- `mode_planned` uses the existing vocabulary (BRT, LRT, Metro, Suburban Rail, Interurban Rail,
  HighSpeed Rail, Cable Line, Funicular).
- `status`: `active` or `retired`. A retired line stays in the registry and is left out of the
  build, so removing a line is a recorded decision.
- `updated`: date of the delivery that last changed the line.

`line_nodes.csv`: `line_id, seq, node, X, Y, is_stop`

- `seq` is the order along the line; `X`, `Y` in EPSG:2039; `node` is the regional model's ID.
- Each direction is its own line, as today.

All files UTF-8 with BOM (opens correctly in Excel with Hebrew).

## 6. The two import doors

Both write a **staged** package and a change report, and replace nothing until confirmed.

```
hubs network import-shp  --project ID --nodes nodes.shp --lines lines.shp [--only LINE ...] [--map cols.yaml]
hubs network import-emme --project ID --routes Routes_and_Nodes.xlsx --coords Nodes_coords.csv [--only LINE ...]
hubs network apply       --project ID          # replace the package with the staged one
```

- `--only` limits the import to the named lines: the "update one line" case. Without it the
  delivery replaces every line it contains; lines of the project that the delivery does not
  contain are left alone and listed as "not in this delivery".
- Shapefile column names differ between senders. `--map` (or a `columns:` block in
  `project.yaml`, remembered for next time) says which column is the node ID, the line ID, the
  sequence and the stop flag.
- If the nodes layer has no order column, the order comes from the line geometry (position of
  each node along the line).
- The Emme door reads the tables exported from Emme in the stage-0 format already declared in
  `inputs.py`; rows with `IsStop = 0` or `Include = 0` are dropped.

The change report (`import_report.md` + `.csv`) lists per line: added / changed / unchanged /
not in this delivery, nodes added and removed, nodes moved (metres), mode or name changed.

**Node IDs.** After reading a delivery the import checks its node IDs against the project's
demand model. IDs that are not in the model are listed. When most of a delivery fails this
check it is not using model IDs, and the import stops and writes `node_match.csv`: each
delivered station with the nearest model node, the distance, and an empty `use_node` column to
review and fill. A second import with `--node-match node_match.csv` applies it. Matching is
never automatic.

## 7. Checks and the build

```
hubs network check                      # every check, no output files
hubs network build --out DIR --version NAME
hubs network diff  DIR_A DIR_B          # two builds: lines and nodes that differ
```

Checks (errors stop the build; warnings are listed):

| Check | Level |
|---|---|
| Duplicate `line_id` inside a project | error |
| Same `line_id` in two projects, not resolved in `aliases.csv` | error |
| Lookalike IDs (equal after lowercasing and removing `-`, `_`, spaces, leading zeros) | warning |
| Line in `lines.csv` without nodes, or nodes for a line not in `lines.csv` | error |
| Unknown `mode_planned` | error |
| Line with fewer than 2 nodes; duplicated `seq` | error |
| Direction pair incomplete (`-1` without `-2`, `_N` without `_S`) | warning |
| A node ID at positions more than `node_position_tolerance_m` (150 m) apart, within or across projects | warning, listed for `node_position_overrides.csv` |
| Node ID not in the project's demand model (needs the demand workbook; optional) | warning |
| Hebrew text garbled | error |

**The line ID written to the build.** The pipeline and the side tables (`linesNames`,
`line_status`, `hub_names` through the hubs) know lines by the bare ID, so the build keeps the
bare `line_id` whenever it is unique nationwide. When two projects use the same ID the build
stops until `aliases.csv` (`project_id, line_id, export_id, notes`) says what each one is called
in the output. No automatic prefixing: a rename is a decision someone made and wrote down.

Build outputs in `DIR`:

- `All_nodeslines_<version>.csv` and `Lines_and_Planned_Mode_<version>.csv`, in the exact
  columns `hubs run` reads today. `DIR` is used as (or copied into) the run's `--input-dir`.
- `network_manifest.json`: per line the project, the delivery, the number of nodes and a hash
  of its rows; plus the registry's git commit. `hubs run` already hashes its inputs into
  `run_manifest.json`, so a run is tied to a build without any pipeline change.
- `network_check.md`: every warning of the build.

## 8. Bootstrap from V1.1

1. Split the two V1.1 files into project packages using a mapping table
   `line -> project_id` (to be supplied; the `Area` column and the ID patterns give a first
   draft: `m####a` / `brt0##` / `lrt0#` / `c00#` Haifa, `rail_*` national rail, `R3##-#` /
   `R100#-#`, `LRT##`, `MTR##`, colour lines Tel Aviv, and so on).
2. Decide each of the known problems of section 2 once (the duplicated Metronit IDs, the
   orphan lines, the `BluRT` spelling) and record the decision in the registry.
3. `hubs network build` must reproduce the V1.1 node x line rows and line rows exactly
   (same set of rows; a test asserts it), and `hubs run` on the build must give the V1.1
   results unchanged.

Only after step 3 passes are the national files retired as hand-edited sources.

## 9. The many-lines update, as it would run

```
for each delivery:
    hubs network import-shp|import-emme --project ID ...     # read, check, write the report
    read import_report.md                                    # is this what the sender meant?
    hubs network apply --project ID
    git commit                                               # one commit per delivery
hubs network build --out runs/<version>/in --version <version>
hubs network diff runs/<previous>/in runs/<version>/in
hubs run --input-dir runs/<version>/in --output-dir runs/<version>/out
hubs compare runs/<previous>/out runs/<version>/out          # effect on hubs, scores, ranks
```

A wrong delivery is undone by reverting its commit.

## 10. Code layout

New package `src/network_registry/` (name to confirm), following the pattern of `src/compare/`:
pure functions on DataFrames, one module per concern, findings on a `RunReport`.

| Module | Content |
|---|---|
| `package.py` | read / write / validate one project package |
| `import_shp.py` | shapefile door, column mapping, node order from geometry |
| `import_emme.py` | Emme-export door (the stage-0 tables) |
| `changes.py` | change report between two states of a package |
| `checks.py` | the checks of section 7 (reuses `network.node_position_table`) |
| `build.py` | assemble, aliases, manifest |
| `run.py` | orchestration behind the `hubs network ...` subcommands |

Unit tests on synthetic packages per module; one golden test for the V1.1 bootstrap.

## 11. Phases

| Phase | Content | Needed for the coming update? |
|---|---|---|
| 1 | Package format, bootstrap of V1.1, `check`, `build`, `diff`, golden test | yes |
| 2 | Shapefile door with `--only`, change report, `apply` | yes |
| 3 | Emme-export door | if any of the coming deliveries is Emme |
| 4 | Node matching for deliveries without model IDs | no, unless one arrives |
| 5 | Registry page in `hubs serve`; side tables (`linesNames`, `line_status`) folded into `lines.csv` | no |

If phases 1-2 are not ready when the deliveries arrive, a fallback for that week only: hand-made
packages for the updated projects plus `build`, which already gives the checks and the diff.

## 12. Open questions

1. **The project list.** Which projects exist, and which lines belong to each? A table
   `line -> project` for the 229 lines is the one input the bootstrap cannot guess.
2. **Where the registry lives.** In this repository (history and review through git, about
   5,000 small rows) or in the planning team's Drive with only builds entering the repository?
   The plan assumes the repository.
3. **Shapefile schemas.** One or two real deliveries (nodes and lines / segments layers) are
   needed to fix the column mapping and to see whether node order is given or has to come from
   the geometry.
4. **Emme export.** Is the table extracted today in the `Routes_and_Nodes` layout
   (Line, Node, IsStop, Include, PlannedMode), and by what steps? Worth recording as a short
   procedure so the export is the same every time.
5. **What a delivery means for lines it does not mention.** The plan leaves them untouched. Is
   a full project delivery sometimes meant as "these are now all the lines"?
6. **Collisions.** Is an explicit `aliases.csv` acceptable, or should a colliding line always
   be written as `<project>:<line_id>`?
7. **The orphan lines** (mode row, no nodes): planned lines still waiting for nodes, or
   leftovers to retire?
8. **Demand for new nodes.** When an updated line brings nodes that the demand workbook does
   not have yet, the hub gets no demand from them. Should the build warn only, or list them as
   a to-do for the next model run?
