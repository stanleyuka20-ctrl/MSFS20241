"""Gate G1 test pad: a small DESIGNED (not real-world) road layout on open, flat
ground, used to prove vehicle control and ground support before the demo route.

Site: disused runway area at Floyd Bennett Field, Brooklyn. Checked against real
data before use (Overture buildings: none in the 588 m x 340 m area; USGS 1 m
DEM 3.6-4.2 m p5-p95). Layout, in metres east/north of the site origin:

  Main (two-way)        y=0,    x=-260..-20   flat start strip and approach
  Cross (two-way)       x=-140, y=-120..120   4-way intersection with Main at x=-140
  Bridge (two-way)      y=0,    x=-20..260    deck x=20..235: +5 % climb to ~5 m above
                                              ground, crown x=145..152, -8 % descent (hill
                                              start); every grade change spread over 20 m
  Underpass (two-way)   x=150,  y=-120..120   passes under the deck crown (not connected)

Deck heights are DESIGN values (source "design:g1-testpad"), stored relative to the
DEM ground at each abutment so they follow the vertical calibration like measured data.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .geo import lonlat_to_utm, utm_to_lonlat

NID0 = 8_100_000_000


def design(lat0: float, lon0: float, dem_sample) -> tuple[dict, dict]:
    """Returns (overpass-style JSON, deck controls JSON). ``dem_sample(lon, lat) -> NAVD88 m``."""
    X0, Y0 = lonlat_to_utm(lon0, lat0)
    nodes, ways = {}, []
    nid = [NID0]

    def node(x, y):
        nid[0] += 1
        lon, lat = utm_to_lonlat(X0 + x, Y0 + y)
        nodes[nid[0]] = (float(lon), float(lat))
        return nid[0]

    def line(pts):
        return [node(x, y) for x, y in pts]

    m_w = line([(x, 0) for x in range(-260, -140, 20)])
    centre = node(-140, 0)
    m_e = line([(x, 0) for x in range(-120, -20, 20)])
    j_main_bridge = node(-20, 0)
    ways.append((9001, [*m_w, centre, *m_e, j_main_bridge], {"highway": "residential", "name": "Testpad Main"}))
    c_s = line([(-140, y) for y in range(-120, 0, 20)])
    c_n = line([(-140, y) for y in range(20, 121, 20)])
    ways.append((9002, [*c_s, centre, *c_n], {"highway": "residential", "name": "Testpad Cross"}))
    g_w = line([(x, 0) for x in range(0, 20, 10)])
    abut_w = node(20, 0)
    deck = line([(x, 0) for x in range(30, 235, 10)])
    abut_e = node(235, 0)
    g_e = line([(x, 0) for x in (245, 260)])
    ways.append((9003, [j_main_bridge, *g_w, abut_w], {"highway": "primary", "name": "Testpad Bridge"}))
    ways.append((9004, [abut_w, *deck, abut_e], {"highway": "primary", "name": "Testpad Bridge", "bridge": "yes",
                                                  "layer": "1", "bridge:name": "Testpad Bridge"}))
    ways.append((9005, [abut_e, *g_e], {"highway": "primary", "name": "Testpad Bridge"}))
    u = line([(150, y) for y in range(-120, 121, 20)])
    ways.append((9006, u, {"highway": "residential", "name": "Testpad Underpass"}))

    els = [{"type": "node", "id": k, "lon": v[0], "lat": v[1]} for k, v in nodes.items()]
    els += [{"type": "way", "id": wid, "nodes": ns, "tags": t} for wid, ns, t in ways]
    osm = {"_about": "DESIGNED Gate G1 test layout (not real-world roads). See src/nycroads/testpad.py.",
           "elements": els}

    def ground(x, y):
        lon, lat = utm_to_lonlat(X0 + x, Y0 + y)
        return float(np.asarray(dem_sample([lon], [lat])).ravel()[0]), float(lon), float(lat)

    gw, _, _ = ground(20, 0)
    ge, _, _ = ground(235, 0)
    # Grade (rise/run) as a piecewise-linear function of x: every grade change is
    # spread over 20 m (vertical curves), so there is no kink a vehicle could jump on.
    gx = [20, 40, 115, 145, 152, 172, 214.5, 234.5]
    gg = [0.0, 0.05, 0.05, 0.0, 0.0, -0.08, -0.08, 0.0]
    xs = np.arange(20.0, 235.01, 0.5)
    grade = np.interp(xs, gx, gg)
    z = gw + np.concatenate([[0.0], np.cumsum((grade[1:] + grade[:-1]) / 2 * np.diff(xs))])
    z += (xs - 20) / (235 - 20) * (ge - (gw + (z[-1] - gw)))   # close exactly onto the east abutment ground
    controls = []
    for x in range(20, 236, 5):
        zx = float(np.interp(x, xs, z))
        _, lon, lat = ground(x, 0)
        controls.append({"lon": round(lon, 8), "lat": round(lat, 8), "z_sim_m": round(zx, 3), "z_native_m": round(zx, 3),
                         "native_datum": "NAVD88", "source": "design:g1-testpad", "n_points": 0, "spread_m": 0.0})
    deck_json = {"_about": "DESIGN heights of the G1 test-pad deck (not measured; this structure does not exist).",
                 "XS-TESTPAD": {"name": "Testpad Bridge", "controls": controls}}
    return osm, deck_json


def write(lat0, lon0, dem_sample, out_dir: Path) -> tuple[Path, Path]:
    osm, deck = design(lat0, lon0, dem_sample)
    out_dir.mkdir(parents=True, exist_ok=True)
    a, b = out_dir / "testpad_osm.json", out_dir / "deck_controls.json"
    a.write_text(json.dumps(osm, indent=0))
    b.write_text(json.dumps(deck, indent=1))
    return a, b
