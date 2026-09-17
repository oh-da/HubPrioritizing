"""Importing the package must not create directories or files."""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_importing_config_creates_no_directories(tmp_path):
    """Run the import in a fresh interpreter from a clean cwd and check nothing appears."""
    before = set(p.name for p in PROJECT_ROOT.iterdir())
    code = (
        "import src.config, src.utils.logging as L;"
        "lg = L.setup_logger('side_effect_probe');"
        "print(len(lg.handlers))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "1"  # console handler only
    after = set(p.name for p in PROJECT_ROOT.iterdir())
    assert after == before, f"import created: {after - before}"
    assert not (PROJECT_ROOT / "logs").exists()
    assert not list(tmp_path.iterdir()), "import wrote into the working directory"


def test_file_logging_is_opt_in(tmp_path):
    from src.utils.logging import setup_logger

    log_file = tmp_path / "nested" / "run.log"
    logger = setup_logger("opt_in_probe", log_file=log_file)
    logger.info("hello")
    for h in logger.handlers:
        h.flush()
    assert log_file.exists()
    assert "hello" in log_file.read_text(encoding="utf-8")
