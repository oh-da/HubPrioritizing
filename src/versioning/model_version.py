"""
Model Code Version Management
==============================
Track versions of the hub prioritization model code and methodology.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from .version_store import VersionStore
from ..config import PROJECT_ROOT
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ModelVersion:
    """
    Represents a version of the hub prioritization model code/methodology.
    """

    def __init__(self, metadata: Dict[str, Any], store: Optional[VersionStore] = None):
        """
        Initialize model version.

        Args:
            metadata: Version metadata dictionary
            store: Version store instance
        """
        self.metadata = metadata
        self.store = store or VersionStore()
        self.version = metadata['model_version']

    @classmethod
    def load(cls, version: str, store: Optional[VersionStore] = None):
        """
        Load existing model version.

        Args:
            version: Version string (e.g., '1.3.2')
            store: Version store instance

        Returns:
            ModelVersion instance
        """
        store = store or VersionStore()
        metadata = store.get_model_version(version)
        if not metadata:
            raise ValueError(f"Model version not found: {version}")
        return cls(metadata, store)


def get_current_model_version() -> str:
    """
    Get current model version from VERSION file.

    Returns:
        Version string (e.g., '1.3.2')
    """
    version_file = PROJECT_ROOT / 'VERSION'

    if version_file.exists():
        with open(version_file, 'r') as f:
            return f.read().strip()

    logger.warning("VERSION file not found, using default")
    return '1.0.0'


def create_model_version(
    version: str,
    version_type: str,
    changes: List[Dict[str, Any]],
    methodology_changes: Optional[Dict[str, Any]] = None,
    git_tag: Optional[str] = None,
    git_commit: Optional[str] = None,
    backward_compatible: bool = True,
    migration_required: bool = False,
    migration_guide: Optional[str] = None,
    dependencies: Optional[Dict[str, Any]] = None,
    authors: Optional[List[str]] = None,
    notes: Optional[str] = None,
    store: Optional[VersionStore] = None
) -> ModelVersion:
    """
    Create a new model version.

    Args:
        version: Version string (e.g., '1.3.2')
        version_type: Type of version ('major', 'minor', 'patch')
        changes: List of changes (each with type, description, files_modified)
        methodology_changes: Changes to scoring methodology
        git_tag: Git tag for this version
        git_commit: Git commit hash
        backward_compatible: Whether this version is backward compatible
        migration_required: Whether migration is needed
        migration_guide: Migration instructions if needed
        dependencies: Package dependencies
        authors: List of authors
        notes: Additional notes
        store: Version store instance

    Returns:
        ModelVersion instance
    """
    store = store or VersionStore()

    # Validate version format
    parts = version.split('.')
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Invalid version format: {version}. Must be MAJOR.MINOR.PATCH")

    # Create metadata
    metadata = {
        'model_version': version,
        'version_date': datetime.now().strftime('%Y-%m-%d'),
        'version_type': version_type,

        'changes': changes,

        'methodology_changes': methodology_changes or {
            'scoring_criteria': {'modified': [], 'added': [], 'removed': []},
            'thresholds': {},
            'algorithms': {'added': [], 'modified': [], 'removed': []}
        },

        'backward_compatible': backward_compatible,
        'migration_required': migration_required,
        'migration_guide': migration_guide,

        'git_info': {
            'tag': git_tag or f'v{version}',
            'commit': git_commit,
            'branch': 'main',
            'release_notes_url': None
        },

        'dependencies': dependencies or {
            'python': '>=3.9',
            'key_packages': {
                'pandas': '>=1.5.0',
                'geopandas': '>=0.12.0',
                'h3': '>=3.7.0',
                'numpy': '>=1.23.0'
            }
        },

        'validation': {
            'tests_passed': None,
            'test_coverage': None,
            'benchmark_performance': None
        },

        'authors': authors or [],
        'reviewed_by': [],
        'approved_by': [],

        'notes': notes or ''
    }

    # Save metadata
    store.save_model_version(metadata)

    # Update VERSION file
    version_file = PROJECT_ROOT / 'VERSION'
    with open(version_file, 'w') as f:
        f.write(version)

    # Update CHANGELOG.md
    update_changelog(version, version_type, changes, notes)

    logger.info(f"Created model version: {version}")
    logger.info(f"  Type: {version_type}")
    logger.info(f"  Changes: {len(changes)}")

    return ModelVersion(metadata, store)


def update_changelog(
    version: str,
    version_type: str,
    changes: List[Dict[str, Any]],
    notes: Optional[str] = None
):
    """
    Update CHANGELOG.md with new version entry.

    Args:
        version: Version string
        version_type: Type of version
        changes: List of changes
        notes: Additional notes
    """
    changelog_path = PROJECT_ROOT / 'docs' / 'CHANGELOG.md'

    # Read existing changelog or create new
    if changelog_path.exists():
        with open(changelog_path, 'r', encoding='utf-8') as f:
            existing = f.read()
    else:
        existing = "# Changelog\n\nAll notable changes to the Hub Prioritization Framework will be documented here.\n\n"

    # Create new entry
    date = datetime.now().strftime('%Y-%m-%d')
    entry = f"\n## [{version}] - {date}\n\n"

    # Group changes by type
    features = [c for c in changes if c.get('type') == 'feature']
    improvements = [c for c in changes if c.get('type') == 'improvement']
    fixes = [c for c in changes if c.get('type') == 'fix']

    if features:
        entry += "### Added\n"
        for change in features:
            entry += f"- {change['description']}\n"
        entry += "\n"

    if improvements:
        entry += "### Changed\n"
        for change in improvements:
            entry += f"- {change['description']}\n"
        entry += "\n"

    if fixes:
        entry += "### Fixed\n"
        for change in fixes:
            entry += f"- {change['description']}\n"
        entry += "\n"

    if notes:
        entry += f"### Notes\n{notes}\n\n"

    # Insert new entry after header
    lines = existing.split('\n')
    header_end = 0
    for i, line in enumerate(lines):
        if line.startswith('## ['):
            header_end = i
            break

    if header_end == 0:
        # No previous entries, append after header
        new_changelog = existing + entry
    else:
        # Insert before first entry
        new_changelog = '\n'.join(lines[:header_end]) + entry + '\n'.join(lines[header_end:])

    # Write updated changelog
    changelog_path.parent.mkdir(parents=True, exist_ok=True)
    with open(changelog_path, 'w', encoding='utf-8') as f:
        f.write(new_changelog)

    logger.info(f"Updated CHANGELOG.md with version {version}")


def parse_version(version: str) -> tuple:
    """
    Parse version string into (major, minor, patch) tuple.

    Args:
        version: Version string (e.g., '1.3.2')

    Returns:
        Tuple of (major, minor, patch) as integers
    """
    parts = version.split('.')
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {version}")

    return tuple(int(p) for p in parts)


def increment_version(current: str, increment_type: str) -> str:
    """
    Increment version number.

    Args:
        current: Current version (e.g., '1.3.2')
        increment_type: 'major', 'minor', or 'patch'

    Returns:
        New version string
    """
    major, minor, patch = parse_version(current)

    if increment_type == 'major':
        return f"{major + 1}.0.0"
    elif increment_type == 'minor':
        return f"{major}.{minor + 1}.0"
    elif increment_type == 'patch':
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Invalid increment_type: {increment_type}")
