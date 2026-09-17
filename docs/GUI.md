# The local web page (`hubs serve`)

A browser page for people who do not want the command line. It runs on your own computer,
uses the same functions as the `hubs` commands, and needs nothing beyond the package
(standard-library HTTP server, no JavaScript build, no internet).

```bash
hubs serve                       # opens http://127.0.0.1:8765/ in your browser
hubs serve --root D:\HubRuns     # the folder the page browses and lists versions from
hubs serve --port 0 --no-browser # any free port, print the address only
```

Stop it with Ctrl+C in the terminal.

## What the page does

**Run tab**

1. *Input folder*: type it or press Browse. The browser shows sub-folders and files and says
   whether a folder holds a complete set of model exports (it names the files it detected).
2. *Output folder*: defaults to `<input folder>/out`.
3. *Version name*: blank = the newest date among the export file names.
4. *Settings*: Monte Carlo iterations, spatial source, and any other `key=value` pairs
   (the same keys as `--set`; `docs/DEVIATIONS.md` lists them).
5. **Validate inputs**: the same check as `hubs validate`. Shows the file the run will use for
   every input, every problem (missing file, missing column, stale base layer), and the
   nodes whose rows disagree on position. The Run button unlocks only when validation
   passes.
6. **Run**: the pipeline runs in the background; the log streams into the page. When it
   finishes you get the hub counts per tier, the top ten, download links for every output
   file (workbook, CSV, cell layer, manifest, report) and the run report inline.

**Versions tab**

Pick the folder that holds your run output folders and press *List versions*: every
`run_manifest.json` found underneath is listed with its date, hub count, input files, base
layer vintage and code commit. Choose A (before) and B (after) and press *Compare*: the
page shows which inputs and settings differ, hubs added or removed, tier changes, the largest
score and rank moves, and links to the comparison files (`docs/VERSIONS.md`).

**Base layer tab**

When the H3 base layer was built, from which shapefiles, and whether it is still current.
*Rebuild* runs `hubs prepare-base` (about three minutes) with its log on the page.

## Rules it enforces

- One job at a time; a second Run while one is going is refused.
- The page can download only files under the served root, the reference folder, a folder it
  listed versions from, or an output folder written in this session.
- The server listens on 127.0.0.1 only, and every action request must carry a header that
  only the page sets, so a web site open in another tab cannot start a run.

## Layout that works well

```
HubRuns/                    <- hubs serve --root HubRuns
  2026_06/                  <- input folder (the exports)
    out/                    <- its results and run_manifest.json
  2026_09/
    out/
```

With that layout the Versions tab lists every run at once, and Compare works across them.

## Troubleshooting

- *Port already in use*: `hubs serve --port 8766`, or `--port 0` for any free port.
- *The browser did not open*: copy the address printed in the terminal.
- *Validate says the base layer is stale*: a reference shapefile changed; use the Base layer
  tab to rebuild, then commit the layer and its manifest.
- *Hebrew looks wrong in the page*: it is the file, not the page. The validation table shows
  the encoding detected for every CSV.
