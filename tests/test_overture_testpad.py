from collections import Counter

import numpy as np

from nycroads.overture import _breaks, _rules_at, map_tags
from nycroads.testpad import design


def row(**kw):
    base = {"id": "seg-1", "class": "primary", "subclass": None, "names": {"primary": "Test St"},
            "road_flags": None, "level_rules": None, "access_restrictions": None, "width_rules": None,
            "sources": [{"dataset": "OpenStreetMap", "record_id": "w123@4"}]}
    base.update(kw)
    return base


def test_map_tags_oneway_access_link():
    st = Counter()
    t = map_tags(row(access_restrictions=[{"access_type": "denied", "when": {"heading": "backward"}, "between": None}]), st)
    assert t["oneway"] == "yes" and t["osm_way"] == "123" and t["highway"] == "primary"
    t = map_tags(row(access_restrictions=[{"access_type": "allowed", "when": {"recognized": ["as_private"]}, "between": None}]), st)
    assert t["access"] == "private"
    t = map_tags(row(subclass="link"), st)
    assert t["highway"] == "primary_link"
    t = map_tags(row(access_restrictions=[{"access_type": "denied", "when": {"heading": "backward"}, "between": [0.1, 0.5]}]), st)
    assert "oneway" not in t and st["partial access rule ignored"] == 1
    t = map_tags(row(road_flags=[{"values": ["is_under_construction"], "between": None}]), st)
    assert t["highway"] == "construction"


def test_fractional_bridge_rules_split_points():
    r = row(road_flags=[{"values": ["is_bridge"], "between": [0.2, 0.7]}],
            level_rules=[{"value": 1, "between": [0.2, 0.7]}])
    assert _breaks(r) == [0.2, 0.7]
    assert _rules_at(r, 0.45) == {"bridge": "yes", "layer": "1"}
    assert _rules_at(r, 0.1) == {}


def test_testpad_design_grades_and_clearance():
    osm, deck = design(40.5930, -73.8940, lambda lon, lat: np.full(len(lon), 4.0))
    z = np.array([c["z_native_m"] for c in deck["XS-TESTPAD"]["controls"]])
    x = np.arange(20, 236, 5)
    g = np.diff(z) / 5.0
    assert z[0] == 4.0 and abs(z[-1] - 4.0) < 1e-6
    assert g.max() <= 0.0505 and g.min() >= -0.0805
    assert np.abs(np.diff(g)).max() <= 0.0201          # grade changes spread over 20 m
    crown = z[(x >= 145) & (x <= 152)]
    assert (crown - 1.2 - 4.0).min() >= 3.5           # deck underside clears the underpass road
    names = {e["tags"]["name"] for e in osm["elements"] if e["type"] == "way"}
    assert names == {"Testpad Main", "Testpad Cross", "Testpad Bridge", "Testpad Underpass"}
