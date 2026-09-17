import pytest
import yaml

from src.pipeline.settings import (
    ConfigError,
    LineDropRule,
    PipelineConfig,
    default_yaml,
    load_config,
    parse_set_overrides,
)


def test_defaults_reproduce_notebook():
    cfg = PipelineConfig()
    assert cfg.h3_resolution == 10
    assert cfg.merge_threshold_m == 120
    assert cfg.influence_rings == (500, 1000, 1500)
    assert cfg.mc_iterations == 10000 and cfg.mc_seed == 42
    assert cfg.per_mode_lines_method == "even"
    assert cfg.renormalize_globally is False
    assert LineDropRule(pattern=r"^m", area="Haifa") in cfg.drop_line_rules


def test_yaml_then_set_overrides(tmp_path):
    y = tmp_path / "pipeline.yaml"
    y.write_text(yaml.safe_dump({"mc_iterations": 500, "influence_rings": [600, 1000, 1200]}), encoding="utf-8")
    cfg = load_config(y, parse_set_overrides(["mc_iterations=250", "apply_eligibility_filter=false"]))
    assert cfg.mc_iterations == 250  # --set wins over yaml
    assert cfg.influence_rings == (600, 1000, 1200)
    assert cfg.apply_eligibility_filter is False


def test_set_coercions():
    cfg = load_config(None, {"influence_rings": "400,800,1500", "extra_columns": "hub_id", "mc_seed": "7"})
    assert cfg.influence_rings == (400, 800, 1500)
    assert cfg.extra_columns == ("hub_id",)
    assert cfg.mc_seed == 7


def test_decay_midpoints_must_match_rings():
    cfg = load_config(None, {"influence_rings": "600,1000,1200", "pop_emp_decay_midpoints": "250,750,1250"})
    assert cfg.pop_emp_decay_midpoints == (250, 750, 1250)
    with pytest.raises(ConfigError):
        load_config(None, {"pop_emp_decay_midpoints": "250,750"})


def test_drop_rules_from_strings_and_mappings():
    cfg = load_config(None, {"drop_line_rules": ["Haifa:^m", {"pattern": "^X$"}]})
    assert cfg.drop_line_rules == (LineDropRule("^m", "Haifa"), LineDropRule("^X$", None))


@pytest.mark.parametrize(
    "overrides",
    [
        {"no_such_key": 1},
        {"per_mode_lines_method": "random"},
        {"influence_rings": "1000,500"},
        {"apply_eligibility_filter": "maybe"},
        {"mc_iterations": "0"},
    ],
)
def test_invalid_values_raise(overrides):
    with pytest.raises((ConfigError, ValueError)):
        load_config(None, overrides)


def test_default_yaml_round_trips():
    loaded = yaml.safe_load(default_yaml())
    cfg = load_config(None, loaded)
    assert cfg == PipelineConfig()
