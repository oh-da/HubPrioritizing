# Comparing our network with the planning agency's (`hubs compare-network`)

The planning agency delivered `MT_Network.gpkg` (+ `MT_Network_MetaData.xlsx`): every transit
route it has and every hub it identified. `hubs compare-network` compares that network with the
one a finished `hubs run` worked from, in two steps:

1. **Routes**: which routes each source has and where they differ. Route names differ between
   the sources, so routes are matched on geometry (node positions against route lines and stops).
2. **Hubs**: which hubs the agency identified, their routes and their mode mix, against **all**
   the hub groups the pipeline formed *before* the eligibility filter.

"All pre-filter groups" means every group built from the H3 hexagons, not only the 142 or so
scored hubs of the results workbook. `hub_groups_all.csv` therefore also contains the groups the
pipeline drops: "Not Hub" tiers, groups under 1,000 passengers/day, single-mode groups and
rail-only groups. Each row carries `eligible` and `exclusion_reason`, so an agency hub that falls
on a dropped group is reported with the reason it was dropped instead of as "missing".

One command produces an Excel workbook, a GeoPackage and two self-contained HTML maps. Every
difference in the workbook can be traced to a route or a hub on a map.

## Prerequisite: re-run `hubs run` with this version

The comparison reads a finished run; it does not re-run the pipeline. From this version `hubs run`
also writes two files next to the results workbook:

| file | content |
|---|---|
| `hub_groups_all.csv` | one row per hub group before any filter: `hub_id`, `group`, `HubNameHE`, `x`, `y` (WGS84), `x_itm`, `y_itm`, `area`, `Mode_Planned` and `Line_Unique` (`;`-joined), `n_modes`, `n_lines`, `TotalDemand`, `TotalTransfers`, `eligible`, `exclusion_reason`, `HubType`, and for scored hubs `TotalScore_MC`, `Rank_TS_MC`, `RankByHubTypeMetro` |
| `network_nodes.csv` | one row per node x line: `node`, `LINE_ID`, `line_name`, `Mode_Planned`, `x_itm`, `y_itm`, `group`, `hub_id` |

`exclusion_reason` is empty for an eligible group, otherwise one or more of `demand < min`,
`single mode`, `rail only`, joined by `;`. The thresholds are the constants of `src/config.py`
(`ELIGIBILITY_MIN_PASSENGERS`, `ELIGIBILITY_MIN_MODES`), and `rail only` applies only while
`require_non_rail_mode` is on, exactly as in the run.

Settings: `all_groups_basename` (default `hub_groups_all`) and `network_nodes_basename` (default
`network_nodes`); an empty string `""` turns the file off (same convention as
`calc_workbook_basename`). A run made with an older version, or with either file turned off, has
no such file: `hubs compare-network` then stops and asks for a re-run (see "Exit codes").

Nothing else in a run changed: scoring, tiers, normalisation and every existing output column are
as before.

## The command

```bash
hubs compare-network --run OUT_DIR --agency-gpkg MT_Network.gpkg \
    [--agency-meta MT_Network_MetaData.xlsx] [--tod-gpkg tod_israel.gpkg] \
    [--out DIR] [--config compare.yaml] [--set key=value ...]
```

| option | meaning |
|---|---|
| `--run DIR` | required. Output directory of `hubs run`, with `hub_groups_all.csv` and `network_nodes.csv` |
| `--agency-gpkg FILE` | required. The agency network, EPSG:2039, layers `lines` and `stations` (a layer in another CRS is reprojected) |
| `--agency-meta FILE` | optional. `MT_Network_MetaData.xlsx`, the code dictionary: Hebrew labels for the route `type` and `source_plan` codes, shown in the `source_plan` column |
| `--tod-gpkg FILE` | optional. The scraped TOD map (`tod_israel.gpkg`, layer `stations` with `hub_id`, `n_modes`, `type_sum`); used only as a cross-check of the agency hubs (see below) |
| `--out DIR` | where to write the files; default is the `--run` directory |
| `--config FILE` | `compare.yaml`, a flat mapping of the settings below |
| `--set KEY=VALUE` | override one setting, repeatable; wins over `--config` |

Precedence is built-in defaults, then `--config`, then `--set` (as for `hubs run`). The effective
values are written to `compare_config.json` and the workbook's `settings` sheet.

```bash
hubs compare-network --run runs/2026_10/out --agency-gpkg MT_Network.gpkg \
    --agency-meta MT_Network_MetaData.xlsx --out runs/2026_10/network_cmp \
    --set hub_match_tol_m=300 --set apply_offset=false
```

On success the command prints the run version, whether the offset was applied and its global
shift, the number of routes per status, the number of hub rows per relation, the number of
warnings in the report and the paths written.

### Exit codes and messages

| exit | when | message |
|---|---|---|
| 0 | the comparison was written | `✓ network comparison of run <version>` and a summary |
| 1 | `hub_groups_all.csv` and/or `network_nodes.csv` missing in `--run` | `✗ <dir> has no <file(s)>: re-run `hubs run` with this version (runs made before the network comparison do not write these files)` |
| 1 | the agency GeoPackage, the metadata workbook or the TOD map is unusable | `✗ N input problem(s):` followed by one `- ...` line per problem, all at once: a missing file, layer (`lines`, `stations`), required column or CRS, an unreadable workbook, an empty or non-numeric `line_id`, an empty `type` |
| 1 | an unknown `--set` key, a value that is not a number / boolean, a failed range check, a missing `--config` file | `configuration error: ...` |
| 2 | a required option is missing | the usage text (argparse) |

Required columns: `lines` needs `type`, `line_id`, `name` (optional: `line_name`, `year_operation`,
`year_cancel`, `source_plan`, `source_name`); `stations` needs `type`, `line_id`, `station_name`,
`stop_id`, `hub_id`, `rail_hub` (optional: `hub_stop_id`).

### Configuration (`CompareConfig`)

All thresholds live here; no stage hard-codes one. Distances are metres in ITM.

| key | default | meaning |
|---|---|---|
| `route_tol_m` | 100 | a node of ours counts as "on" an agency route when it is within this distance of the route line |
| `rail_tol_m` | 250 | the same for the rail types (`Rail`, `Rail fast`), whose geometry is coarser |
| `stop_tol_m` | 150 | an agency stop counts as covered when a node of ours is within this distance. Also the node-to-stop tolerance of the offset estimate |
| `rail_assign_tol_m` | 250 | the agency `stations` layer has no `name` column, so a station with `line_id = 0` is assigned to the nearest same-type `line_id = 0` feature within this distance; stations that fit none are dropped and reported |
| `match_min_score` | 0.5 | lowest score of a "real" match: `partial` and above; `agency_only` and the hub route evidence use it too |
| `full_cov` | 0.8 | both coverages at or above this make a full match |
| `only_max_score` | 0.2 | a pair with a lower score is not a candidate at all; must be `<= match_min_score` |
| `multi_cov` | 0.3 | both coverages at or above this make a candidate "part of" a split or merge |
| `apply_offset` | true | correct our node positions by the estimated offset before matching (`false` skips it) |
| `offset_radius_m` | 10000 | radius within which node-to-stop offsets are pooled into a local median |
| `offset_passes` | 2 | refinement passes of the offset estimate (`0` gives a zero shift) |
| `hub_match_tol_m` | 400 | an agency hub and one of our groups are a pair when their nearest points are this close |
| `tod_join_tol_m` | 200 | agency hub to nearest scraped TOD hub (`--tod-gpkg`) |

Validation: the tolerances and `offset_radius_m` must be above 0, the four scores / coverages in
[0, 1], `only_max_score <= match_min_score`, `offset_passes >= 0`. Coverage and score thresholds are
inclusive (`>=`). Scores are rounded to 9 digits before any threshold is applied, so a score that
is exactly on a threshold (7/8 and 7/20 give 0.5) counts as that value.

## How the matching works

**Our routes.** Lines of the same mode whose node sets are equal are one *route* (the two
directions). The route key is the sorted member `LINE_ID`s joined with `+`; a line with no partner
is a one-line route. Nodes with unparseable coordinates are dropped and counted in the report.
A route with fewer than 2 nodes is compared normally and flagged `short_route`.

**Agency routes.** Key `(type, line_id)`; the rail features all share `line_id = 0`, so for
`line_id = 0` the feature `name` completes the key (`Rail:0:<name>`, other keys look like
`LRT:3106`). Geometry is the union of the key's `lines` features and its stops are the key's
`stations` rows. A route with no stations (about 7 of 132 line ids) is matched on its geometry
alone, its "stops" being the line vertices sampled every 100 m.

**Mode mapping.** `data/reference/agency_mode_map.csv` maps our mode to the agency `type`: BRT,
LRT (also `Light Rail`), Metro, Suburban Rail / Interurban Rail (also `Rail`) to Rail,
HighSpeed Rail to Rail fast, Funicular to FUNI. Cable Line, Bus and Express Bus have no
counterpart: their routes are always `ours_only` with `reason = no agency mode`, and the report
warns about the unmapped modes.

**Offset.** Earlier work found a systematic shift of about 40-60 m between our nodes and the
agency stops. For every distinct node of ours the shift is the median `stop - node` offset of the
node-to-nearest-agency-stop pairs (closer than `stop_tol_m`, any mode) of the nodes within
`offset_radius_m`, falling back to the global median when fewer than 5 pairs are near; the
estimate is refined for `offset_passes` passes. The corrected position is used for all matching;
distances are reported both raw and corrected.

**Candidates and score.** For each route `R` of ours and each agency route `A`:

- `cov_ours` = share of `R`'s nodes within `route_tol_m` of `A`'s geometry (`rail_tol_m` for the
  rail types);
- `cov_agency` = share of `A`'s stops within `stop_tol_m` of a node of `R`;
- `score` = `2 * cov_ours * cov_agency / (cov_ours + cov_agency)`.

Pairs with `score >= only_max_score` are *candidates*, ranked by score (ties by agency route key).
A candidate whose agency type is not the mapped mode of our route is *cross-mode* and never counts
as a match. The result is deterministic: no randomness, ties broken by sorted key.

## Vocabularies

### Route `status` (one per route of ours, evaluated in this order; plus `agency_only`)

| status | rule |
|---|---|
| `ours_only` (first test) | our mode has no agency counterpart (`reason = no agency mode`) |
| `matched` | some same-mode candidate has `cov_ours >= full_cov` and `cov_agency >= full_cov`; the best-scoring such candidate is the match. A full match always wins, so routes that share a trunk (rail) are not mislabelled |
| `split_merge` | no full match, and either at least two same-mode candidates have both coverages `>= multi_cov` (one of ours runs over several agency routes), or the best candidate's agency route is used, with both coverages `>= multi_cov`, by at least two of our routes and none of those pairs is a full match (several of ours share one agency route). All candidates are listed in `candidates`; `reason` says which case |
| `partial` | not the above; the best same-mode candidate has `score >= match_min_score` |
| `weak` | the best same-mode candidate has `only_max_score <= score < match_min_score` |
| `mode_differs` | no same-mode candidate, but a cross-mode candidate with `score >= match_min_score` |
| `ours_only` | none of the above (no candidate, or only cross-mode candidates below `match_min_score`); `reason` says which |
| `agency_only` | an agency route that no route of ours has a same-mode candidate on with `score >= match_min_score`; one extra row per such route |

For every row except `agency_only` and the unmatched `ours_only`, the `agency_*`, `cov_*` and
`score` columns describe the chosen agency route (the full match, or the best-scoring same-mode
candidate; for `mode_differs` the best cross-mode one). `agency_n_our_routes` is how many of our
routes use that agency route (same mode, both coverages `>= multi_cov`).

### Hub `relation`

An agency hub `H` and one of our groups `G` are a *pair* when the minimum distance between a stop
of `H` and a node of `G` (offset-corrected, nearest points, not centroids) is `<= hub_match_tol_m`
(inclusive). Pairs are many-to-many; the relation is derived per connected component of the pair
graph:

| relation | meaning |
|---|---|
| `1:1` | one agency hub, one group |
| `agency_splits` | one agency hub overlaps several of our groups |
| `ours_merges` | several agency hubs overlap one of our groups |
| `many_to_many` | both of the above in one component |
| `agency_only` | no group within tolerance; the row gives the nearest group, its distance, its `eligible` and `exclusion_reason` for information |
| `ours_only` | no agency hub within tolerance; every group of `hub_groups_all.csv` appears, scored hubs and filtered-out groups alike, told apart by `eligible` |

The agency hubs are the `hub_id`s of the `stations` layer (426 in the delivered file). Their "type" is **derived**: the
number of distinct modes, the `rail_hub` flag and the mode mix, for example
`3 modes, rail hub: BRT+LRT+Rail`. It is not an agency classification, and the agency files carry
no demand (see "Known behaviours and limits").

## Reading the outputs

Everything is written to `--out`.

### `network_comparison.xlsx`

List cells are joined with `; `. Every sheet has a frozen bold header and an autofilter.

| sheet | content |
|---|---|
| `summary` | sections `about` (run version and directory, and the two statements that agency demand is empty and agency type is derived), `routes` (counts of ours, the agency and each status), `hubs` (agency hubs, groups of ours, rows per relation), `limits` |
| `routes` | one row per route of ours plus one `agency_only` row per unmatched agency route. Columns: `status`, `our_route_key`, `our_line_ids`, `our_line_names`, `our_mode`, `our_n_nodes`, `short_route`, `agency_route_key`, `agency_type`, `agency_name`, `agency_line_name`, `agency_n_stops`, `cov_ours`, `cov_agency`, `score`, then `median_dist_raw_m`, `median_dist_corr_m`, `max_dist_corr_m` of the chosen pair, `candidates` (`key (score)` for every candidate), `agency_n_our_routes`, `year_operation`, `year_cancel`, `source_plan` (translated through the metadata workbook when given), `reason` |
| `routes_only_ours` | the `routes` rows with status `ours_only` |
| `routes_only_agency` | the `routes` rows with status `agency_only` |
| `mode_summary` | routes per mode on each side by status: `side` (`ours` / `agency`), `mode`, `n_routes`, one column per status, `other`. Our side groups on our mode names, the agency side on agency types, each agency route counted once (`agency_only` if it has such a row, else the best status of the routes of ours that chose it, else `other`) |
| `hubs` | one row per pair plus the `agency_only` and `ours_only` rows. `relation`; agency side `agency_hub_id`, `agency_name` (most frequent station name), `agency_modes`, `agency_n_modes`, `agency_rail_hub`, `agency_type`, `agency_n_routes`, `agency_total_demand` (always empty), `tod_type_sum`, `tod_disagrees`; our side `group`, `hub_id`, `HubNameHE`, `Mode_Planned`, `n_modes`, `n_lines`, `TotalDemand`, `TotalTransfers`, `eligible`, `exclusion_reason`, `HubType`, `TotalScore_MC`, `RankByHubTypeMetro`; comparison `distance_m`, `modes_shared`, `modes_only_agency`, `modes_only_ours`, `routes_shared` (`agency key=our key`), `routes_only_agency`, `routes_only_ours`, `n_modes_diff` |
| `hubs_agency_only` | the `hubs` rows with relation `agency_only` |
| `hubs_ours_only` | the `hubs` rows with relation `ours_only` |
| `hub_routes` | long format, one row per hub row x route: `agency_hub_id`, `group`, `side` (`shared` / `only_agency` / `only_ours`), `our_route_key`, `agency_route_key`, `route_status` (the step-1 status of the route; for an agency route that is the statuses of its rows, `;`-joined) |
| `settings` | the effective `CompareConfig` (`key`, `value`) |
| `inputs` | one row per input: file name, SHA-256 and counts (`run`, `hub_groups_all`, `network_nodes`, `agency_gpkg`, plus `agency_meta` and `tod_gpkg` when given) |

`tod_type_sum` is the scraped map's `type_sum` for the nearest scraped hub within `tod_join_tol_m`
of the agency hub's stops (centroid); `tod_disagrees` is true where it differs from
`agency_n_modes`. Both are empty without `--tod-gpkg`.

### `network_comparison.gpkg` (EPSG:2039)

| layer | geometry and content |
|---|---|
| `route_pairs` | the agency route geometry with the match attributes of the route of ours that chose it (one row per route of ours with an agency route, then one `agency_only` row per unmatched agency route with empty `our_*` attributes), plus the distance statistics |
| `our_routes` | our nodes of each route joined in shortest-path order, from the offset-corrected positions; a Point for a one-node route; `visual_aid = true`, with `status`, `agency_route_key`, `score` of the route |
| `our_routes_raw` | the same rows in the same order from the raw (uncorrected) positions |
| `agency_hubs` | the agency hubs as MultiPoints of their stops, with `relation` and `paired_groups` |
| `our_groups` | every group of `hub_groups_all.csv` as a MultiPoint of its nodes, with all its columns, `relation` and `paired_agency_hubs` |
| `hub_ties` | a line between the nearest points of each paired agency hub and group, with `distance_m` and the relation |

### The two HTML pages

`network_comparison_routes.html` and `network_comparison_hubs.html` are single files with the data
embedded as JSON; Leaflet 1.9.4 is loaded from cdnjs and the basemap is OpenStreetMap (selector
"Basemap": OpenStreetMap / No basemap). Both have layer toggles, a legend, a picker that isolates
one item and "Zoom to all". Popups show the columns above.

- **Routes page.** Agency routes are solid and thick, coloured by match status; our routes are
  dashed and thin (a visual aid). Toggle "Our nodes at raw positions, not offset-corrected"
  switches our layer from `our_routes` to `our_routes_raw`. Filters: match status (with counts of
  agency / ours routes per status), mode, and the picker "Isolate one route" by our key or agency
  key (it ignores the other filters). An agency route can appear twice (an `agency_only` row and a
  `weak` or `mode_differs` row of ours on the same geometry); each row is its own feature.
- **Hubs page.** Agency hubs are rings (small dots mark their stops), sized by number of modes; our
  groups are filled circles, coloured by tier (`HubType`) or by eligible / not (selector "Colour our
  groups by"), grey when filtered out. Ties join paired hubs (a hub exactly on its group has no
  visible tie). Filters: relation (with counts of agency hubs / groups), mode, "Our groups shown"
  (all / eligible only / filtered out only), and the picker "Isolate one hub with its partners".

### Configuration and report

- `compare_config.json`: the effective `CompareConfig`.
- `compare_report.md` / `compare_report.json`: findings and metrics. Findings: the global offset
  (`offset_global_dx_m`, `offset_global_dy_m`, `offset_max_shift_m`), modes without an agency
  counterpart, stations that fit no rail feature (with their ids), route keys of stations that
  have no `lines` feature, dropped nodes. Metrics: `routes_<status>`, `hubs_<relation>`,
  `hubs_ours_only_eligible`, `routes_ours`, `routes_agency`, `hubs_agency`, `hubs_ours`.
  Always read the warnings first.

## Known behaviours and limits

- **No agency demand, no agency tier.** The agency files contain neither, so
  `agency_total_demand` is always empty. The "agency type" is the derived mode count with the
  `rail_hub` flag and the mode mix, not an agency classification. The scraped TOD `type_sum` is the
  number of distinct modes, not a tier; it is an optional cross-check only (`--tod-gpkg`).
- **`routes_only_ours` lists `ours_only` routes only.** Routes with status `weak` or
  `mode_differs` stay on the `routes` sheet.
- **`agency_type` in `routes`.** For `matched` / `partial` / `split_merge` / `weak` /
  `mode_differs` rows it is the type of the matched agency route; for `ours_only` rows it holds
  our mapped type (empty for a mode without a counterpart). Use `our_mode` for our side.
- **`agency_only` rows in `hubs`.** Their group columns (`group`, `hub_id`, `HubNameHE`, `eligible`,
  `exclusion_reason`) hold the **nearest** group, which is outside the tolerance, for information.
  Split rows by `relation`, never by empty ids. In `hub_routes`, rows of an `agency_only` hub have
  an empty `group`.
- **Hub route evidence** uses same-mode step-1 pairs with `score >= match_min_score` (not
  `split_merge` candidates below it). It is evidence shown, not part of the matching rule.
  `n_modes_diff` is the agency mode count minus our **mapped** mode count: our modes with no
  agency counterpart (Cable Line, buses) are not in the mode columns.
- **Our routes are a visual aid.** Our lines have no stop order or geometry; `our_routes` joins the
  nodes in shortest-path order, so it is not a route. Matching is only as good as the node
  positions.
- **The offset is an estimate.** The typical 40-60 m shift is estimated per node as a local median
  and assumed locally constant. A node with fewer than 5 pairs nearby takes the global median. When no
  usable estimate exists at all (fewer than 5 node-stop pairs within `stop_tol_m` in total, for
  example because the two networks use different coordinates) the shift is currently a zero
  shift, indistinguishable on the maps from a genuinely small one; check the offset line of
  `compare_report.md`.
- **The HTML pages need a network and a real browser.** Leaflet 1.9.4 is loaded from cdnjs without
  Subresource Integrity hashes and the basemap tiles come from OpenStreetMap. A page opened as a
  `file://` URL may be served a placeholder tile instead of the map; choose "No basemap". The pages
  were verified in the sandbox only with a stubbed Leaflet: open them once in a real browser.
- **Thresholds.** Scores are rounded to 9 digits and all coverage / score / distance thresholds
  are inclusive (`>=`, `<=`).
- **Rerun needed.** The run to compare must have been made with a version that writes
  `hub_groups_all.csv` and `network_nodes.csv`.

## Reading a result: where to look first

1. `compare_report.md`: warnings, the global offset, unmapped modes, stations dropped.
2. `summary` sheet and the console summary: counts per route status and hub relation.
3. `routes_only_agency` and `hubs_agency_only`: what the agency has that we do not. In
   `hubs_agency_only` the nearest group and its `exclusion_reason` often explain it (a group exists
   but was filtered for demand, a single mode or rail only).
4. `routes_only_ours` and `hubs_ours_only` (filter `eligible`): what we have that the agency does
   not.
5. `hubs` rows with `agency_splits`, `ours_merges` and `many_to_many`, and `n_modes_diff != 0`: the
   hubs that are defined differently.
6. Open the two HTML pages and isolate a route or hub from the sheet to see it on the map.
