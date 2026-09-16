"""Tier classification must match notebook cell 82 of COMPLETE_TRANSIT_PIPELINE."""

import pytest

from src.classification.hierarchy import classify_hub_tier
from src.config import TIER_LOCAL, TIER_METRO, TIER_NATIONAL


@pytest.mark.parametrize(
    "demand, modes, lines, expected",
    [
        # National: (HighSpeed | Interurban) & >=3 lines & >=50k
        (60000, ["HighSpeed Rail", "LRT"], 5, TIER_NATIONAL),
        (60000, ["Interurban Rail", "BRT"], 3, TIER_NATIONAL),
        # Falls to metro when demand < 50k
        (49999, ["Interurban Rail", "BRT"], 3, TIER_METRO),
        # Metro requires >= 5000 demand (notebook change of 2025-12-29)
        (5000, ["Suburban Rail", "LRT"], 3, TIER_METRO),
        (4999, ["Suburban Rail", "LRT"], 3, TIER_LOCAL),  # below 5000: LRT still qualifies as local
        (4999, ["Suburban Rail", "Interurban Rail"], 3, "Not Hub"),  # rail-only, no local fallback
        (20000, ["Metro", "BRT"], 4, TIER_METRO),
        # Local: (BRT | LRT) & >=3 lines & >=1000
        (1200, ["BRT", "LRT"], 3, TIER_LOCAL),
        (999, ["BRT", "LRT"], 3, "Not Hub"),
        (4999, ["Metro", "LRT"], 3, TIER_LOCAL),  # metro fails on demand, LRT qualifies as local
        # Train station: rail modes but <= 2 lines
        (80000, ["Suburban Rail"], 2, "Train Station"),
        (500, ["Interurban Rail", "HighSpeed Rail"], 1, "Train Station"),
        # Not a hub
        (3000, ["BRT"], 2, "Not Hub"),
    ],
)
def test_classify_hub_tier(demand, modes, lines, expected):
    assert classify_hub_tier(demand, modes, lines) == expected


def test_scalar_mode_is_wrapped():
    assert classify_hub_tier(70000, "HighSpeed Rail", 4) == TIER_NATIONAL
