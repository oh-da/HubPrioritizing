"""Our-mode -> agency-type mapping."""

from src.compare.modes import MODE_MAP_PATH, load_mode_map, map_mode
from src.config import MODE_TO_COLUMN


def test_shipped_map_covers_every_pipeline_mode():
    assert MODE_MAP_PATH.exists()
    mode_map = load_mode_map()
    for mode in MODE_TO_COLUMN:
        assert mode in mode_map, mode


def test_rail_variants():
    m = load_mode_map()
    assert map_mode("Suburban Rail", m) == "Rail"
    assert map_mode("Interurban Rail", m) == "Rail"
    assert map_mode("HighSpeed Rail", m) == "Rail fast"
    assert map_mode("Funicular", m) == "FUNI"
    assert map_mode("BRT", m) == "BRT"
    assert map_mode("LRT", m) == "LRT"
    assert map_mode("Metro", m) == "Metro"
    assert "Cable Line" in m and map_mode("Cable Line", m) is None


def test_unknown_mode_is_none():
    assert map_mode("Hovercraft", load_mode_map()) is None


def test_custom_path(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("our_mode,agency_type,note\nBRT,Bus Rapid,x\nCable Line,,none\n", encoding="utf-8")
    assert load_mode_map(p) == {"BRT": "Bus Rapid", "Cable Line": None}
