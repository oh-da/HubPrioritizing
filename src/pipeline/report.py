"""
Run report: everything a planner needs to trust (or question) a run.

Stages call :meth:`RunReport.warn` / :meth:`RunReport.info` while they work; the
orchestrator writes the report next to the results as Markdown and JSON.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ReportEntry:
    level: str  # 'info' | 'warning' | 'error'
    section: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunReport:
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    entries: list[ReportEntry] = field(default_factory=list)
    inputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)

    # -- recording -------------------------------------------------------------------------
    def info(self, section: str, message: str, **data: Any) -> None:
        self.entries.append(ReportEntry("info", section, message, _jsonable(data)))

    def warn(self, section: str, message: str, **data: Any) -> None:
        self.entries.append(ReportEntry("warning", section, message, _jsonable(data)))

    def error(self, section: str, message: str, **data: Any) -> None:
        self.entries.append(ReportEntry("error", section, message, _jsonable(data)))

    def record_input(self, key: str, path: Path | None, **details: Any) -> None:
        self.inputs[key] = {"path": str(path) if path else None, **_jsonable(details)}

    def set_metric(self, name: str, value: Any) -> None:
        self.metrics[name] = _jsonable({"v": value})["v"]

    # -- querying ---------------------------------------------------------------------------
    @property
    def warnings(self) -> list[ReportEntry]:
        return [e for e in self.entries if e.level == "warning"]

    @property
    def errors(self) -> list[ReportEntry]:
        return [e for e in self.entries if e.level == "error"]

    def sections(self) -> list[str]:
        seen: list[str] = []
        for e in self.entries:
            if e.section not in seen:
                seen.append(e.section)
        return seen

    # -- rendering --------------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "inputs": self.inputs,
            "metrics": self.metrics,
            "entries": [
                {"level": e.level, "section": e.section, "message": e.message, "data": e.data}
                for e in self.entries
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = ["# Hub prioritization run report", "", f"Started: {self.started_at}", ""]
        if self.inputs:
            lines += ["## Inputs", "", "| Key | File | Details |", "|---|---|---|"]
            for key, info in self.inputs.items():
                details = ", ".join(f"{k}={v}" for k, v in info.items() if k != "path")
                lines.append(f"| `{key}` | `{info.get('path')}` | {details} |")
            lines.append("")
        if self.metrics:
            lines += ["## Metrics", ""]
            for k, v in self.metrics.items():
                lines.append(f"- **{k}**: {v}")
            lines.append("")
        n_warn, n_err = len(self.warnings), len(self.errors)
        lines += [f"## Findings ({n_err} errors, {n_warn} warnings)", ""]
        for section in self.sections():
            lines.append(f"### {section}")
            lines.append("")
            for e in self.entries:
                if e.section != section:
                    continue
                marker = {"info": "·", "warning": "⚠", "error": "✗"}[e.level]
                extra = f" `{json.dumps(e.data, ensure_ascii=False)}`" if e.data else ""
                lines.append(f"- {marker} {e.message}{extra}")
            lines.append("")
        return "\n".join(lines)

    def write(self, out_dir: Path, stem: str = "run_report") -> tuple[Path, Path]:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        md = out_dir / f"{stem}.md"
        js = out_dir / f"{stem}.json"
        md.write_text(self.to_markdown(), encoding="utf-8")
        js.write_text(self.to_json(), encoding="utf-8")
        return md, js


def _jsonable(data: dict[str, Any]) -> dict[str, Any]:
    """Make values JSON-serialisable (paths, sets, numpy scalars, tuples)."""
    out: dict[str, Any] = {}
    for k, v in data.items():
        out[k] = _jsonable_value(v)
    return out


def _jsonable_value(v: Any) -> Any:
    if isinstance(v, Path):
        return str(v)
    if isinstance(v, (set, frozenset)):
        return sorted(_jsonable_value(x) for x in v)
    if isinstance(v, (list, tuple)):
        return [_jsonable_value(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable_value(x) for k, x in v.items()}
    if hasattr(v, "item") and callable(v.item):  # numpy scalar
        try:
            return v.item()
        except Exception:  # pragma: no cover
            return str(v)
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)
