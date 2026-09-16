# Installation

The project is a regular Python package. Python 3.11 or newer is required.

```bash
git clone https://github.com/oh-da/HubPrioritizing.git
cd HubPrioritizing
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .[dev]              # runtime + test tooling
```

Optional extras:

```bash
pip install -e .[ahp]              # Streamlit questionnaire for AHP expert weights
pip install -e .[viz]              # folium maps, matplotlib charts
```

Verify:

```bash
pytest                              # unit tests (no external data needed)
hubs --help                         # one-command pipeline (available from PR 8 onwards)
```

## Dependencies worth knowing about

- **geopandas / pyogrio / shapely 2** read the shapefiles under `data/reference/` and do the
  metre-based buffering in EPSG:2039.
- **h3 4.x** is required. The code uses the v4 API (`latlng_to_cell`, `cell_to_boundary`);
  h3 3.x will fail with `AttributeError`.
- **openpyxl** writes the final `hub_prioritization_results.xlsx` workbook.

## Reference data

Stable inputs (metropolitan zones, districts, hub display names, manual group merges) ship
under `data/reference/`. See `data/reference/README.md` for the list and for the layers that
still have to be added (bus terminals, TAZ 2050).

## Troubleshooting

- `ModuleNotFoundError: No module named 'src'` — run `pip install -e .` from the repository
  root (the editable install makes the `src` package importable everywhere).
- GDAL/GEOS errors on install — pip wheels for `geopandas`, `shapely` and `pyogrio` bundle
  these libraries on Linux, macOS and Windows; upgrade pip (`pip install -U pip`) if wheels
  are not picked up.
- Hebrew shows as `����` — the reference shapefiles carry `.cpg` files declaring their code
  page (`CP1255` for `metro_2008`, `UTF-8` for `Districts`), and CSV inputs are read with
  automatic `utf-8-sig` / `cp1255` detection. If you add a new shapefile, add a `.cpg` next to it.
