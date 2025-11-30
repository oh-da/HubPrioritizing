# Quick Setup Guide
==================

## Installation

### Option 1: Automatic (Interactive)
Just run the pipeline - it will detect missing packages and offer to install them:
```bash
python scripts/run_complete_pipeline.py
```

When prompted, type `y` to auto-install missing dependencies.

### Option 2: Install Script
Run the dedicated install script:
```bash
python scripts/install_dependencies.py
```

### Option 3: Manual Installation
Install all dependencies manually:
```bash
pip install -r requirements.txt
```

Or install just the core packages:
```bash
pip install h3>=3.7.0 geopandas>=0.13.0 pandas>=2.0.0 numpy>=1.24.0 shapely>=2.0.0
```

## Running the Pipeline

After installation, configure your data paths and run:

```bash
# 1. Edit data paths in the script
nano scripts/run_complete_pipeline.py  # or use any editor

# 2. Run the pipeline
python scripts/run_complete_pipeline.py
```

See `docs/DATA_CONFIGURATION.md` for detailed data setup instructions.

## Troubleshooting

### "ModuleNotFoundError: No module named 'h3'"
- Run: `pip install h3`
- Or use automatic installation (Option 1 above)

### "No module named 'geopandas'"
- Run: `pip install geopandas`
- Note: geopandas requires GDAL/GEOS libraries
- On Colab/Jupyter: These are pre-installed
- On local machine: See https://geopandas.org/getting_started/install.html

### Installation fails with permission error
- Try: `pip install --user -r requirements.txt`
- Or use a virtual environment:
  ```bash
  python -m venv venv
  source venv/bin/activate  # On Windows: venv\Scripts\activate
  pip install -r requirements.txt
  ```

### On Google Colab
Most packages are pre-installed. You may only need:
```python
!pip install h3
```

Then run the pipeline normally.
