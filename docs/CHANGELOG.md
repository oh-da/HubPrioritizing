# Changelog

All notable changes to the Hub Prioritization Framework will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
