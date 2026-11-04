"""CompareConfig: defaults, precedence, validation."""

import pytest

from src.compare.settings import COMPARE_KEYS, CompareConfig, load_compare_config
from src.pipeline.settings import ConfigError, parse_set_overrides


def test_defaults_match_spec():
    cfg = CompareConfig()
    assert cfg.route_tol_m == 100.0
    assert cfg.rail_tol_m == 250.0
    assert cfg.stop_tol_m == 150.0
    assert cfg.rail_assign_tol_m == 250.0
    assert cfg.match_min_score == 0.5
    assert cfg.full_cov == 0.8
    assert cfg.only_max_score == 0.2
    assert cfg.multi_cov == 0.3
    assert cfg.apply_offset is True
    assert cfg.offset_radius_m == 10000.0
    assert cfg.offset_passes == 2
    assert cfg.hub_match_tol_m == 400.0
    assert cfg.tod_join_tol_m == 200.0
    assert set(COMPARE_KEYS) == set(cfg.to_dict())
    assert load_compare_config() == cfg
    assert '"route_tol_m": 100.0' in cfg.to_json()


def test_yaml_then_set_precedence(tmp_path):
    yml = tmp_path / "compare.yaml"
    yml.write_text("route_tol_m: 120\nstop_tol_m: 200\napply_offset: false\n", encoding="utf-8")
    cfg = load_compare_config(yml)
    assert (cfg.route_tol_m, cfg.stop_tol_m, cfg.apply_offset) == (120.0, 200.0, False)
    over = parse_set_overrides(["stop_tol_m=90", "offset_passes=3", "apply_offset=yes"])
    cfg = load_compare_config(yml, over)
    assert cfg.route_tol_m == 120.0  # yaml survives
    assert cfg.stop_tol_m == 90.0  # override beats yaml
    assert cfg.offset_passes == 3 and isinstance(cfg.offset_passes, int)
    assert cfg.apply_offset is True


def test_unknown_key_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_compare_config(None, {"no_such_key": "1"})
    yml = tmp_path / "c.yaml"
    yml.write_text("bogus: 1\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_compare_config(yml)


def test_bad_values_raise():
    with pytest.raises(ConfigError):
        load_compare_config(None, {"route_tol_m": "abc"})
    with pytest.raises(ConfigError):
        load_compare_config(None, {"apply_offset": "maybe"})
    with pytest.raises(ConfigError):
        load_compare_config(None, {"route_tol_m": "0"})
    with pytest.raises(ConfigError):
        load_compare_config(None, {"offset_passes": "-1"})
    with pytest.raises(ConfigError):
        load_compare_config(None, {"full_cov": "1.5"})


def test_validate_rejects_bad_scores():
    with pytest.raises(ConfigError):
        CompareConfig(only_max_score=0.9, match_min_score=0.5).validate()


@pytest.mark.parametrize("key, value", [
    ("offset_passes", 2.7),  # a non-integral float for an int field
    ("offset_passes", "2.7"),
    ("offset_passes", True),  # a bool is not a number
    ("route_tol_m", True),
    ("route_tol_m", float("inf")),  # non-finite floats
    ("route_tol_m", "inf"),
    ("hub_match_tol_m", "nan"),
])
def test_coerce_rejects_bools_fractions_and_non_finite(key, value):
    with pytest.raises(ConfigError):
        load_compare_config(None, {key: value})


def test_coerce_accepts_integral_numbers_for_int_fields():
    assert load_compare_config(None, {"offset_passes": 3.0}).offset_passes == 3
    assert load_compare_config(None, {"offset_passes": "3.0"}).offset_passes == 3
    assert load_compare_config(None, {"route_tol_m": 120}).route_tol_m == 120.0
