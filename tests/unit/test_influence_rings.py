"""Buffer rings must follow the configured radii (they used to be hardcoded)."""

import math

import pytest

from src.data.influence_area_processor import InfluenceAreaProcessor


def _ring_area(inner: float, outer: float) -> float:
    return math.pi * (outer**2 - inner**2)


def test_default_rings_are_500_1000_1500(synthetic_hub_points):
    proc = InfluenceAreaProcessor()
    buffers = proc.create_buffer_zones(synthetic_hub_points)

    assert list(buffers) == ["zone1", "zone2", "zone3"]
    # Buffers are polygonal approximations, so compare within 1%.
    assert buffers["zone1"].area.iloc[0] == pytest.approx(_ring_area(0, 500), rel=0.01)
    assert buffers["zone2"].area.iloc[0] == pytest.approx(_ring_area(500, 1000), rel=0.01)
    assert buffers["zone3"].area.iloc[0] == pytest.approx(_ring_area(1000, 1500), rel=0.01)


def test_custom_rings_are_honoured(synthetic_hub_points):
    proc = InfluenceAreaProcessor()
    proc.buffer_zones = {"zone1": (0, 600), "zone2": (600, 1000), "zone3": (1000, 1200)}
    buffers = proc.create_buffer_zones(synthetic_hub_points)

    assert buffers["zone1"].area.iloc[0] == pytest.approx(_ring_area(0, 600), rel=0.01)
    assert buffers["zone3"].area.iloc[0] == pytest.approx(_ring_area(1000, 1200), rel=0.01)


def test_rings_do_not_overlap(synthetic_hub_points):
    proc = InfluenceAreaProcessor()
    buffers = proc.create_buffer_zones(synthetic_hub_points)
    z1, z2 = buffers["zone1"].iloc[0], buffers["zone2"].iloc[0]
    assert z1.intersection(z2).area == pytest.approx(0.0, abs=1e-6)


def test_non_contiguous_rings_are_rejected(synthetic_hub_points):
    proc = InfluenceAreaProcessor()
    proc.buffer_zones = {"zone1": (0, 500), "zone2": (600, 1000)}
    with pytest.raises(ValueError):
        proc.create_buffer_zones(synthetic_hub_points)


def test_zone_statistics_respect_ring_radii(synthetic_hub_points, synthetic_taz):
    """A 500 m circle fully inside a 2 km TAZ square gets the area-proportional share."""
    proc = InfluenceAreaProcessor()
    buffers = proc.create_buffer_zones(synthetic_hub_points)
    stats = proc.calculate_zone_statistics(synthetic_hub_points, synthetic_taz, buffers)

    hub0 = stats.iloc[0]
    taz_area = 2000.0 * 2000.0
    expected_pop = 4000.0 * _ring_area(0, 500) / taz_area
    assert hub0["pop_zone1"] == pytest.approx(expected_pop, rel=0.02)

    # With 600 m rings the inner-zone population must grow accordingly.
    proc.buffer_zones = {"zone1": (0, 600), "zone2": (600, 1000), "zone3": (1000, 1200)}
    stats_600 = proc.calculate_zone_statistics(
        synthetic_hub_points, synthetic_taz, proc.create_buffer_zones(synthetic_hub_points)
    )
    assert stats_600.iloc[0]["pop_zone1"] == pytest.approx(
        4000.0 * _ring_area(0, 600) / taz_area, rel=0.02
    )
    assert stats_600.iloc[0]["pop_zone1"] > hub0["pop_zone1"]
