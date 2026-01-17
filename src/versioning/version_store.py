"""
Version Store - Central Storage and Retrieval for All Versions
===============================================================
Handles storage, indexing, and querying of version metadata using
JSON files for human readability and SQLite for fast queries.
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import hashlib

from ..config import DATA_DIR, PROJECT_ROOT
from ..utils.logging import get_logger

logger = get_logger(__name__)


class VersionStore:
    """
    Central version storage and retrieval system.

    Uses dual storage:
    - JSON files: Human-readable metadata
    - SQLite: Fast querying and indexing
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize version store.

        Args:
            base_dir: Base directory for versions (default: DATA_DIR / 'versions')
        """
        self.base_dir = Path(base_dir) if base_dir else DATA_DIR / 'versions'
        self.db_path = self.base_dir / 'index.db'

        # Create directories
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database()

        logger.info(f"Version store initialized at {self.base_dir}")

    def _init_database(self):
        """Initialize SQLite database with schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Data versions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_versions (
                version_id TEXT PRIMARY KEY,
                data_type TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                source_file TEXT,
                file_hash TEXT,
                record_count INTEGER,
                created_by TEXT,
                notes TEXT,
                tags TEXT
            )
        ''')

        # Model runs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS model_runs (
                run_id TEXT PRIMARY KEY,
                run_number INTEGER,
                created_at TIMESTAMP NOT NULL,
                model_version TEXT,
                git_commit TEXT,
                status TEXT,
                execution_time REAL,
                created_by TEXT,
                run_purpose TEXT,
                notes TEXT,
                tags TEXT
            )
        ''')

        # Run data dependencies table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS run_data_dependencies (
                run_id TEXT,
                data_type TEXT,
                data_version_id TEXT,
                FOREIGN KEY (run_id) REFERENCES model_runs(run_id),
                FOREIGN KEY (data_version_id) REFERENCES data_versions(version_id)
            )
        ''')

        # Model versions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS model_versions (
                version TEXT PRIMARY KEY,
                version_date DATE NOT NULL,
                version_type TEXT,
                git_tag TEXT,
                git_commit TEXT,
                backward_compatible BOOLEAN,
                notes TEXT
            )
        ''')

        # Create indices for fast queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_data_type ON data_versions(data_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_data_created ON data_versions(created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_run_created ON model_runs(created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_run_status ON model_runs(status)')

        conn.commit()
        conn.close()

        logger.debug("Database schema initialized")

    # ==============================================================================
    # DATA VERSION OPERATIONS
    # ==============================================================================

    def save_data_version(self, metadata: Dict[str, Any]) -> str:
        """
        Save data version metadata to both JSON and database.

        Args:
            metadata: Data version metadata dictionary

        Returns:
            version_id: The version identifier
        """
        version_id = metadata['data_version_id']
        data_type = metadata['data_type']

        # Create directory for this version
        version_dir = self.base_dir / data_type / version_id
        version_dir.mkdir(parents=True, exist_ok=True)

        # Save JSON metadata
        json_path = version_dir / 'metadata.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # Save to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO data_versions
            (version_id, data_type, created_at, source_file, file_hash,
             record_count, created_by, notes, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            version_id,
            data_type,
            metadata['created_at'],
            metadata.get('source_file'),
            metadata.get('source_file_hash'),
            metadata.get('record_count'),
            metadata.get('created_by'),
            metadata.get('notes'),
            json.dumps(metadata.get('tags', []))
        ))

        conn.commit()
        conn.close()

        logger.info(f"Saved data version: {version_id}")
        return version_id

    def get_data_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve data version metadata.

        Args:
            version_id: Version identifier

        Returns:
            Metadata dictionary or None if not found
        """
        # Find the version directory (search all data types)
        for data_type_dir in self.base_dir.iterdir():
            if not data_type_dir.is_dir():
                continue

            version_dir = data_type_dir / version_id
            json_path = version_dir / 'metadata.json'

            if json_path.exists():
                with open(json_path, 'r', encoding='utf-8') as f:
                    return json.load(f)

        logger.warning(f"Data version not found: {version_id}")
        return None

    def get_latest_data_version(self, data_type: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest version of a specific data type.

        Args:
            data_type: Type of data (e.g., 'transit_lines')

        Returns:
            Latest version metadata or None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT version_id FROM data_versions
            WHERE data_type = ?
            ORDER BY created_at DESC
            LIMIT 1
        ''', (data_type,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return self.get_data_version(row[0])

        return None

    def list_data_versions(
        self,
        data_type: Optional[str] = None,
        limit: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        List data versions with optional filtering.

        Args:
            data_type: Filter by data type
            limit: Maximum number of results
            tags: Filter by tags (OR logic)

        Returns:
            List of version metadata dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = 'SELECT version_id FROM data_versions WHERE 1=1'
        params = []

        if data_type:
            query += ' AND data_type = ?'
            params.append(data_type)

        if tags:
            # Simple tag filtering (checks if any tag matches)
            tag_conditions = ' OR '.join(['tags LIKE ?' for _ in tags])
            query += f' AND ({tag_conditions})'
            params.extend([f'%{tag}%' for tag in tags])

        query += ' ORDER BY created_at DESC'

        if limit:
            query += ' LIMIT ?'
            params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [self.get_data_version(row[0]) for row in rows]

    # ==============================================================================
    # MODEL RUN OPERATIONS
    # ==============================================================================

    def save_run_version(self, metadata: Dict[str, Any]) -> str:
        """
        Save model run version metadata.

        Args:
            metadata: Run version metadata dictionary

        Returns:
            run_id: The run identifier
        """
        run_id = metadata['run_version_id']

        # Create directory for this run
        run_dir = self.base_dir.parent / 'results' / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Save JSON metadata
        json_path = run_dir / 'run_metadata.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # Save to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO model_runs
            (run_id, run_number, created_at, model_version, git_commit,
             status, execution_time, created_by, run_purpose, notes, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            run_id,
            metadata.get('run_number'),
            metadata['created_at'],
            metadata.get('model_version', {}).get('code_version'),
            metadata.get('model_version', {}).get('git_commit'),
            metadata.get('status', 'created'),
            metadata.get('execution_time_seconds'),
            metadata.get('created_by'),
            metadata.get('run_purpose'),
            metadata.get('notes'),
            json.dumps(metadata.get('tags', []))
        ))

        # Save data dependencies
        input_data_versions = metadata.get('input_data_versions', {})
        for data_type, data_version_id in input_data_versions.items():
            cursor.execute('''
                INSERT OR REPLACE INTO run_data_dependencies
                (run_id, data_type, data_version_id)
                VALUES (?, ?, ?)
            ''', (run_id, data_type, data_version_id))

        conn.commit()
        conn.close()

        logger.info(f"Saved run version: {run_id}")
        return run_id

    def get_run_version(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve model run metadata.

        Args:
            run_id: Run identifier

        Returns:
            Metadata dictionary or None if not found
        """
        run_dir = self.base_dir.parent / 'results' / run_id
        json_path = run_dir / 'run_metadata.json'

        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        logger.warning(f"Run version not found: {run_id}")
        return None

    def list_run_versions(
        self,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        List model run versions with optional filtering.

        Args:
            status: Filter by status ('created', 'running', 'completed', 'failed')
            limit: Maximum number of results
            tags: Filter by tags (OR logic)

        Returns:
            List of run metadata dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = 'SELECT run_id FROM model_runs WHERE 1=1'
        params = []

        if status:
            query += ' AND status = ?'
            params.append(status)

        if tags:
            tag_conditions = ' OR '.join(['tags LIKE ?' for _ in tags])
            query += f' AND ({tag_conditions})'
            params.extend([f'%{tag}%' for tag in tags])

        query += ' ORDER BY created_at DESC'

        if limit:
            query += ' LIMIT ?'
            params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [self.get_run_version(row[0]) for row in rows if self.get_run_version(row[0])]

    def get_runs_using_data(self, data_version_id: str) -> List[Dict[str, Any]]:
        """
        Find all runs that used a specific data version.

        Args:
            data_version_id: Data version identifier

        Returns:
            List of run metadata dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DISTINCT run_id FROM run_data_dependencies
            WHERE data_version_id = ?
            ORDER BY run_id DESC
        ''', (data_version_id,))

        rows = cursor.fetchall()
        conn.close()

        return [self.get_run_version(row[0]) for row in rows if self.get_run_version(row[0])]

    def update_run_status(
        self,
        run_id: str,
        status: str,
        execution_time: Optional[float] = None,
        results_summary: Optional[Dict[str, Any]] = None
    ):
        """
        Update run status and results.

        Args:
            run_id: Run identifier
            status: New status ('running', 'completed', 'failed')
            execution_time: Execution time in seconds
            results_summary: Results summary dictionary
        """
        metadata = self.get_run_version(run_id)
        if not metadata:
            raise ValueError(f"Run not found: {run_id}")

        metadata['status'] = status
        if execution_time:
            metadata['execution_time_seconds'] = execution_time
        if results_summary:
            metadata['results_summary'] = results_summary

        self.save_run_version(metadata)
        logger.info(f"Updated run {run_id}: status={status}")

    # ==============================================================================
    # MODEL VERSION OPERATIONS
    # ==============================================================================

    def save_model_version(self, metadata: Dict[str, Any]) -> str:
        """
        Save model code version metadata.

        Args:
            metadata: Model version metadata dictionary

        Returns:
            version: The version string
        """
        version = metadata['model_version']

        # Create versions directory
        versions_dir = PROJECT_ROOT / 'docs' / 'versions'
        versions_dir.mkdir(parents=True, exist_ok=True)

        # Save JSON metadata
        json_path = versions_dir / f'{version}.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # Save to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO model_versions
            (version, version_date, version_type, git_tag, git_commit,
             backward_compatible, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            version,
            metadata['version_date'],
            metadata['version_type'],
            metadata.get('git_info', {}).get('tag'),
            metadata.get('git_info', {}).get('commit'),
            metadata.get('backward_compatible', True),
            metadata.get('notes')
        ))

        conn.commit()
        conn.close()

        logger.info(f"Saved model version: {version}")
        return version

    def get_model_version(self, version: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve model version metadata.

        Args:
            version: Version string (e.g., '1.3.2')

        Returns:
            Metadata dictionary or None if not found
        """
        versions_dir = PROJECT_ROOT / 'docs' / 'versions'
        json_path = versions_dir / f'{version}.json'

        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        logger.warning(f"Model version not found: {version}")
        return None

    # ==============================================================================
    # UTILITY METHODS
    # ==============================================================================

    def compute_file_hash(self, filepath: Union[str, Path]) -> str:
        """
        Compute SHA256 hash of a file.

        Args:
            filepath: Path to file

        Returns:
            SHA256 hash string
        """
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return f"sha256:{sha256_hash.hexdigest()}"

    def get_next_run_number(self) -> int:
        """
        Get the next sequential run number.

        Returns:
            Next run number
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT MAX(run_number) FROM model_runs')
        row = cursor.fetchone()
        conn.close()

        return (row[0] or 0) + 1
