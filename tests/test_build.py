import json
import xml.etree.ElementTree as ET

import numpy as np
import pygltflib
import synthetic as S

from nycroads.demo import evaluate
from nycroads.geo import ENUFrame
from nycroads.surface import build_surfaces
from nycroads.scenery import model_guid


def test_build_outputs(built):
    rep = built["report"]
    assert rep["generated_segments"] > 0
    assert rep["surface_groups"] >= 2
    assert rep["segments_with_errors"] == [], json.dumps(rep["issues"], indent=1)[:2000]
    # tunnel is blocked, not generated
    assert any("tunnel" in v for v in rep["blocked"].values())
    assert rep["start_locations"]


def test_gltf_is_valid_and_has_collision_node(built):
    files = list((built["out"] / "b" / "models").glob("*.gltf"))
    assert files
    for f in files:
        g = pygltflib.GLTF2().load(str(f))
        names = {n.name for n in g.nodes}
        assert {"visual", "collision"} <= names
        for acc in g.accessors:
            assert acc.count > 0
        assert "ASOBO_tags" in g.extensionsUsed


def test_package_xml_wellformed_and_stable_guid(built):
    pkg = built["out"] / "pkg" / "PackageSources"
    scene = ET.parse(pkg / "scene" / "nycroads-test.xml").getroot()
    objs = scene.findall("SceneryObject")
    assert objs and all(o.get("altitudeIsAgl") == "FALSE" for o in objs)
    name = objs[0].get("displayName")
    assert objs[0].find("LibraryObject").get("name") == model_guid(name)
    ET.parse(pkg / "modelLib" / "nycroads-test" / f"{name}.xml")


def test_demo_acceptance_on_fixture(built, inv):
    res = evaluate(inv, built["sel"], built["profiles"])
    assert res["street_and_intersection"]["pass"]
    assert res["slope"]["pass"]
    assert res["bridge"]["pass"]
    assert res["underpass"]["pass"]


def _top_meshes(res):
    return [m for _, m in res.meshes if m.collision and m.material in ("asphalt", "concrete_deck")]


def test_surface_has_no_overlaps_or_gaps(built, inv):
    res = build_surfaces(inv, built["profiles"], cell_m=60.0)   # small cells: many internal cuts
    tri_area = 0.0
    for m in _top_meshes(res):
        v = np.asarray(m.vertices)
        for a, b, c in m.triangles:
            (x1, y1), (x2, y2) = v[b, :2] - v[a, :2], v[c, :2] - v[a, :2]
            tri_area += abs(x1 * y2 - y1 * x2) / 2
    fp_area = sum(f.area for f in res.footprints.values())
    assert abs(tri_area - fp_area) / fp_area < 0.005


def test_surface_watertight_across_cells(built, inv):
    """Every edge used by only one triangle must lie on the footprint boundary, never on a cell cut."""
    from collections import Counter
    from shapely.geometry import Point
    res = build_surfaces(inv, built["profiles"], cell_m=60.0)
    edges = Counter()
    for m in _top_meshes(res):
        v = [tuple(np.round(p[:2], 3)) for p in m.vertices]
        for t in m.triangles:
            for i, j in ((0, 1), (1, 2), (2, 0)):
                edges[tuple(sorted((v[t[i]], v[t[j]])))] += 1
    boundary = [f.boundary for f in res.footprints.values()]
    for (p, q), n in edges.items():
        if n == 1:
            mid = Point((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
            assert min(b.distance(mid) for b in boundary) < 0.01, (p, q)


def test_surface_heights_follow_profiles(built, inv):
    res = build_surfaces(inv, built["profiles"])
    deck_key = next(k for k in res.groups if k[0] == "deck")
    hf = res.heights[deck_key]
    assert abs(hf(S.X0 + 300, S.Y0) - 8.0) < 0.05          # deck crown, not the valley floor (~0 m)
    ground = res.heights[("ground", 0)]
    assert abs(ground(S.X0 + 300, S.Y0 + 0.0) - (0.0 + 0.05)) < 0.3   # Street D in the valley under the deck


def test_clearance_check_catches_low_deck(inv):
    from nycroads.pipeline import compute_profiles, select_segments
    from nycroads.checks import run_checks
    from nycroads.elevation import DeckControl
    low = {"XS-TEST": [DeckControl(*S.ll(300, y), 3.0, "t") for y in (-95, -60, 0, 60, 95)]}
    sel = select_segments(inv, ids=list(inv.segments))
    profiles, blockers = compute_profiles(inv, sel, S.dem(), S.vref(), low)
    issues = run_checks(inv, profiles, build_surfaces(inv, profiles), {})
    assert any(i["type"] == "underpass_clearance" for v in issues.values() for i in v)


def test_enu_roundtrip():
    f = ENUFrame(-73.95, 40.74, 0.0)
    e, n, u = f.from_geodetic([-73.951, -73.949], [40.741, 40.739], [10.0, 0.0])
    lon, lat, h = f.to_geodetic(e, n, u)
    assert np.allclose(lon, [-73.951, -73.949], atol=1e-9)
    assert np.allclose(h, [10.0, 0.0], atol=1e-6)
    assert e[0] < 0 < e[1] and n[0] > 0 > n[1]
