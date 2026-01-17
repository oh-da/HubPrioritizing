# Changelog

All notable changes to the Hub Prioritization Framework will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.3] - 2025-01-17

### Changed
- **BREAKING**: Migrated all hardcoded demand updates to CSV format
- Removed Step 2.6.2 (hardcoded National Model updates) from pipeline notebook
- Removed Step 2.6.3 (hardcoded Shefaim LRT update) from pipeline notebook
- All demand overrides now centralized in `data/manual_demand_updates.csv`

### Added
- Enhanced `manual_demand_updates.csv` schema with metadata columns:
  - `data_source`: Source of demand data (e.g., "National Model 2025")
  - `confidence`: Confidence level (High/Medium/Low)
  - `is_override`: Boolean flag for override status
  - `last_updated`: Timestamp of last update
  - `updated_by`: User who made the update
  - `notes`: Explanation and reasoning for the update
- Migration script: `scripts/migrate_hardcoded_demand_updates.py`
  - Automated detection of hardcoded steps
  - Validation of CSV coverage
  - Automatic removal with backup creation
  - Dry-run mode for safe testing
- Complete inventory of manual updates in `MANUAL_UPDATES_INVENTORY_AND_INTEGRATION_PLAN.md`

### Documentation
- Updated `data/README_MANUAL_DEMAND_UPDATES.md` (v2.0) with:
  - Enhanced schema documentation
  - Migration guide from hardcoded to CSV
  - Best practices for transparency and auditability
  - Current updates inventory (8 nodes)
- Added migration plan for remaining manual updates (group corrections, overlays)

### Migration Guide
Users with custom hardcoded updates should:
1. Run `python scripts/migrate_hardcoded_demand_updates.py --check` to assess status
2. Add hardcoded values to `data/manual_demand_updates.csv` with metadata
3. Run `python scripts/migrate_hardcoded_demand_updates.py --migrate` to remove hardcoded cells
4. Verify Step 2.6.1 applies CSV updates correctly

### Notes
This release completes **Week 1** of the Transit Update System integration plan.
All demand overrides are now in version-controlled CSV files with complete
metadata for auditability. Steps 2.6.2 and 2.6.3 are deprecated and should be
removed from all notebooks. Future updates should use the CSV file exclusively.

**Current CSV coverage**: 8 nodes (5 from National Model, 1 from local study, 2 existing)

See `MANUAL_UPDATES_INVENTORY_AND_INTEGRATION_PLAN.md` for the complete
integration roadmap (Weeks 2-4: notification system, visual indicators, GUI).

## [1.3.2] - 2025-01-17

### Added
- Comprehensive versioning system for input data, model runs, and code versions
- Version metadata storage using JSON files and SQLite index
- CLI tools for listing and comparing versions (`list_versions.py`, `compare_versions.py`)
- Automatic version creation when uploading data or running pipeline
- Python API for programmatic version management
- Transit update system design with standardized CSV input formats
- Validation and preview workflow for data updates

### Changed
- Enhanced mode weight calculation for suburban rail (5.0 → 6.0)
- Enhanced mode weight calculation for metro (5.0 → 6.0)

### Documentation
- Added VERSIONING_SYSTEM_DESIGN.md with complete technical specification
- Added VERSIONING_GUIDE.md with user-friendly usage examples
- Added TRANSIT_UPDATE_SYSTEM_DESIGN.md for data update workflows

### Notes
This version introduces comprehensive version management and lays the foundation
for a user-friendly data update system via GUI. The versioning system enables
full reproducibility and traceability of all pipeline executions.

## [1.3.0] - 2025-12-17

### Added
- AHP (Analytic Hierarchy Process) scoring as alternative to Monte Carlo
- Monte Carlo distribution analysis for robustness metrics
- Enhanced configuration integration

### Notes
AHP provides alternative expert-driven methodology for criterion weighting,
enabling stakeholder engagement in the prioritization process.

## [1.0.0] - 2024-12-30

### Added
- Initial release of Hub Prioritization Framework
- H3-based spatial indexing for hub identification
- Multi-criteria scoring system
- Monte Carlo simulation for robust weighting
- Interactive visualization with maps and charts
- Comprehensive documentation (CLAUDE.md)

### Notes
First production release of the unified framework for identifying, classifying,
and prioritizing integrated transport hubs (מתח"מים) in Israel.
