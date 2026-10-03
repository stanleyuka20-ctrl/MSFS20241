"""SYNTHETIC test network. Not real geography.

Positions are metres east/north of an arbitrary origin, converted to lon/lat so
the real code paths (UTM / ENU transforms) are exercised. Layout:

  Street A   (residential, two-way)  y=0, x=-200..200, 4-way intersection at x=0 with Street B
  Street B   (residential)           x=0, y=-150..150, climbs a real 6 % hill for y in 0..100
  Street D   (residential)           y=0, x=200..450, continues Street A (2-way connection at x=200)
                                     and passes UNDER the Avenue C bridge at x=300 through a valley
  Avenue C   (primary)               x=300, y=-300..300; bridge (layer=1) for y in -100..100
  Street E   (residential, tunnel)   short tunnel stub
  plus excluded ways: a driveway and a footway

DEM: 5 m plain; valley to 0 m around (300, 0); 6 % hill on Street B; a 4 m
one-sample spike on Street A at x=-100 (a photogrammetry/DEM artefact).
"""
from __future__ import annotations

import numpy as np

from nycroads.elevation import DeckControl, FunctionDEM, VerticalReference
from nycroads.geo import lonlat_to_utm, utm_to_lonlat
from nycroads.osm import OsmData

ORIGIN_LONLAT = (-73.9500, 40.7400)
X0, Y0 = lonlat_to_utm(*ORIGIN_LONLAT)
NID0 = 9_000_000_000


def ll(x, y):
    return utm_to_lonlat(X0 + x, Y0 + y)


def local(lon, lat):
    x, y = lonlat_to_utm(lon, lat)
    return np.asarray(x) - X0, np.asarray(y) - Y0


def terrain(x, y):
    x, y = np.broadcast_arrays(np.asarray(x, float), np.asarray(y, float))
    z = np.full(x.shape, 5.0)
    z -= 5.0 * np.exp(-((x - 300) / 60) ** 2) * np.exp(-(y / 50) ** 2)          # valley under bridge
    hill = (np.abs(x) < 25) & (y > 0)
    z += np.where(hill, 0.06 * np.clip(y, 0, 100), 0.0)                          # 6 % hill on Street B
    spike = (np.abs(x + 100) < 2.6) & (np.abs(y) < 2.6)
    z += np.where(spike, 4.0, 0.0)                                               # artefact
    return z


def dem():
    return FunctionDEM(lambda lon, lat: terrain(*local(lon, lat)))


def osm_data() -> OsmData:
    d = OsmData()
    nid = [NID0]

    def node(x, y):
        nid[0] += 1
        d.nodes[nid[0]] = ll(x, y)
        return nid[0]

    def line(points):
        return [node(x, y) for x, y in points]

    # Street A: x -200..200, shared node with B at x=0
    a_w = node(-200, 0)
    a_mid = [node(x, 0) for x in range(-180, 0, 20)]
    center = node(0, 0)
    a_e = [node(x, 0) for x in range(20, 200, 20)]
    a_end = node(200, 0)
    d.ways[101] = {"nodes": [a_w, *a_mid, center, *a_e, a_end],
                   "tags": {"highway": "residential", "name": "Street A"}}
    # Street B: through the centre node
    b_s = line([(0, y) for y in range(-150, 0, 25)])
    b_n = line([(0, y) for y in range(10, 151, 10)])
    d.ways[102] = {"nodes": [*b_s, center, *b_n], "tags": {"highway": "residential", "name": "Street B"}}
    # Street D continues Street A (connection node a_end) and passes under the bridge
    d_rest = line([(x, 0) for x in range(210, 451, 10)])
    d.ways[103] = {"nodes": [a_end, *d_rest], "tags": {"highway": "residential", "name": "Street D"}}
    # Avenue C: approach / bridge / approach as three ways sharing nodes
    c_s = line([(300, y) for y in range(-300, -100, 20)])
    abut_s = node(300, -100)
    c_bridge = line([(300, y) for y in range(-80, 100, 20)])
    abut_n = node(300, 100)
    c_n = line([(300, y) for y in range(120, 301, 20)])
    d.ways[104] = {"nodes": [*c_s, abut_s], "tags": {"highway": "primary", "name": "Avenue C"}}
    d.ways[105] = {"nodes": [abut_s, *c_bridge, abut_n],
                   "tags": {"highway": "primary", "name": "Avenue C", "bridge": "yes", "layer": "1",
                            "bridge:name": "Synthetic Test Bridge"}}
    d.ways[106] = {"nodes": [abut_n, *c_n], "tags": {"highway": "primary", "name": "Avenue C"}}
    # Tunnel stub off Street B south end
    d.ways[107] = {"nodes": [b_s[0], *line([(-50, -150), (-100, -150)])],
                   "tags": {"highway": "residential", "tunnel": "yes", "layer": "-1", "name": "Street E"}}
    # Excluded
    d.ways[108] = {"nodes": [a_mid[3], *line([(-120, 30)])], "tags": {"highway": "service", "service": "driveway"}}
    d.ways[109] = {"nodes": line([(-50, 50), (-50, 80)]), "tags": {"highway": "footway"}}
    return d


CROSSINGS = [{"id": "XS-TEST", "name": "Synthetic Test Bridge", "osm_name_patterns": ["^Synthetic Test Bridge"]}]


def deck_controls():
    return {"XS-TEST": [DeckControl(*ll(300, -60), 7.0, "synthetic"),
                        DeckControl(*ll(300, 0), 8.0, "synthetic"),
                        DeckControl(*ll(300, 60), 7.0, "synthetic")]}


def vref():
    return VerticalReference(method="calibrated_offset", offset_m=0.0)


MSFS_CFG = {
    "verified": False,
    "axis_mapping": {"x": "-east", "y": "up", "z": "north"},
    "collision_node_extensions": {"ASOBO_tags": {"tags": ["Collision", "Road"]}},
    "collision_material_extensions": {"ASOBO_material_invisible": {}},
    "material_extensions": {},
    "materials": {k: {"baseColor": [0.5, 0.5, 0.5, 1], "roughness": 0.8, "metallic": 0.0}
                  for k in ("asphalt", "collision", "concrete_deck")},
}
