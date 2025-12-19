# AHP Expert Questionnaire App

## Overview

This is a Streamlit web application for collecting expert pairwise comparisons using the **Analytic Hierarchy Process (AHP)** methodology. The app is designed for the Hub Prioritization Framework to determine criterion weights from expert input.

## Features

✅ **Professional UI** - Clean, modern interface with bilingual support (English/Hebrew)
✅ **Automatic Criteria Loading** - Reads criteria from `data/criteria.csv` (no manual configuration needed)
✅ **Results Persistence** - Saves all submissions to `data/ahp_results.csv` automatically
✅ **Real-time Validation** - Calculates consistency ratio (CR) and validates expert judgments
✅ **Streamlit Cloud Ready** - Fully compatible with Streamlit Cloud deployment
✅ **Data Export** - Download results as CSV for backup or further analysis

## Quick Start (Local)

### Install Dependencies

```bash
pip install -r requirements_streamlit.txt
```

### Run the App

```bash
streamlit run app/ahp_questionnaire.py
```

The app will open at `http://localhost:8501`

## Deploying to Streamlit Cloud

1. **Push to GitHub** (ensure all files are committed)
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Create new app:
   - Repository: `oh-da/HubPrioritizing`
   - Main file: `app/ahp_questionnaire.py`
4. Click "Deploy"

**Note:** On Streamlit Cloud, use the "Download Backup CSV" button for results (cloud has read-only filesystem).

## Configuration

### Criteria (`data/criteria.csv`)

Criteria are loaded automatically from CSV with columns:
- `criterion_id`: Unique ID
- `label_en`: English name
- `label_he`: Hebrew name
- `description`: Full description
- `icon`: Emoji icon

**To modify criteria**: Edit `data/criteria.csv` and restart the app.

### Results (`data/ahp_results.csv`)

Each submission saves one row with:
- Timestamp, expert name, consistency metrics
- All criterion weights
- All pairwise comparison values

## Usage

1. Enter your name in the sidebar
2. Review criteria on "Criteria Overview" tab
3. Make pairwise comparisons using sliders
4. Check "Results & Submit" tab:
   - Verify consistency ratio (CR < 0.10)
   - Review calculated weights
5. Submit results or download backup

## Technical Details

- **AHP Method**: Eigenvector method with consistency checking
- **Scale**: Saaty 1-9 scale (slider: -8 to +8)
- **Validation**: CR < 0.10 required for consistent judgments

## Troubleshooting

**Criteria not loading?**
- Check `data/criteria.csv` exists and has required columns

**Results not saving on cloud?**
- Expected (read-only filesystem)
- Use "Download Backup CSV" button instead

## References

- Saaty, T.L. (1980). *The Analytic Hierarchy Process*. McGraw-Hill.
- See `CLAUDE.md` for complete methodology documentation
