import json
import xml.etree.ElementTree as ET

import numpy as np
import pygltflib
import synthetic as S

from nycroads.demo import evaluate
from nycroads.geo import ENUFrame
from nycroads.meshgen import build_network
from nycroads.scenery import model_guid


def test_build_outputs(built):
    rep = built["report"]
    assert rep["generated_segments"] > 0
    assert rep["junction_pads"] >= 1
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


def test_junction_pad_is_watertight(built, inv):
    net = build_network(inv, built["profiles"])
    centre = [j for j in inv.junctions.values() if len(j.segment_ids) == 4][0]
    pad = net.pads_by_junction[centre.id]
    pad_pts = {tuple(np.round(v, 4)) for v in pad.vertices}
    for sid in centre.segment_ids:
        surf = net.meshes_by_segment[sid][0]
        v = np.asarray(surf.vertices)
        n = len(v) // 2
        seg = inv.segments[sid]
        idx = 0 if seg.from_node == centre.osm_node_id else n - 1
        for p in (v[idx], v[n + idx]):
            assert tuple(np.round(p, 4)) in pad_pts


def test_connection_ends_share_vertices(built, inv):
    net = build_network(inv, built["profiles"])
    conn = [j for j in inv.junctions.values() if j.kind == "connection"
            and all(s in net.meshes_by_segment for s in j.segment_ids)
            and not any(inv.segments[s].bridge for s in j.segment_ids)][0]
    ends = []
    for sid in conn.segment_ids:
        v = np.asarray(net.meshes_by_segment[sid][0].vertices)
        n = len(v) // 2
        idx = 0 if inv.segments[sid].from_node == conn.osm_node_id else n - 1
        ends.append({tuple(np.round(v[idx], 3)), tuple(np.round(v[n + idx], 3))})
    assert ends[0] == ends[1]


def test_clearance_check_catches_low_deck(inv):
    from nycroads.pipeline import compute_profiles, select_segments
    from nycroads.checks import run_checks
    from nycroads.elevation import DeckControl
    low = {"XS-TEST": [DeckControl(*S.ll(300, -60), 3.0, "t"), DeckControl(*S.ll(300, 0), 3.0, "t"),
                       DeckControl(*S.ll(300, 60), 3.0, "t")]}
    sel = select_segments(inv, ids=list(inv.segments))
    profiles, blockers = compute_profiles(inv, sel, S.dem(), S.vref(), low)
    net = build_network(inv, profiles)
    issues = run_checks(inv, profiles, net, {})
    assert any(i["type"] == "underpass_clearance" for v in issues.values() for i in v)


def test_enu_roundtrip():
    f = ENUFrame(-73.95, 40.74, 0.0)
    e, n, u = f.from_geodetic([-73.951, -73.949], [40.741, 40.739], [10.0, 0.0])
    lon, lat, h = f.to_geodetic(e, n, u)
    assert np.allclose(lon, [-73.951, -73.949], atol=1e-9)
    assert np.allclose(h, [10.0, 0.0], atol=1e-6)
    assert e[0] < 0 < e[1] and n[0] > 0 > n[1]
