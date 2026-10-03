import synthetic as S

from nycroads.ids import IdRegistry
from nycroads.inventory import build_inventory, classify_way, width_of


def by_name(inv, name):
    return [s for s in inv.segments.values() if s.name == name]


def test_classification():
    assert classify_way({"highway": "residential"})[0] == "in_scope"
    assert classify_way({"highway": "service"})[0] == "secondary"
    assert classify_way({"highway": "service", "service": "driveway"})[0] == "excluded"
    assert classify_way({"highway": "primary", "access": "private"})[0] == "excluded"
    assert classify_way({"highway": "footway"})[0] == "excluded"
    assert classify_way({"highway": "busway"})[0] == "excluded"


def test_width_sources():
    assert width_of({"highway": "residential", "width": "12 m"}) == (12.0, "osm:width")
    w, src = width_of({"highway": "primary", "lanes": "4"})
    assert src == "osm:lanes" and w > 4 * 3.3


def test_segments_and_junctions(inv):
    # Street A splits at the centre (B) and at x=-120 where the excluded driveway does NOT split it
    assert len(by_name(inv, "Street A")) == 2
    kinds = {}
    for j in inv.junctions.values():
        kinds.setdefault(j.kind, []).append(j)
    centre = [j for j in kinds["intersection"] if len(j.segment_ids) == 4]
    assert len(centre) == 1
    assert any(len(j.segment_ids) == 2 for j in kinds["connection"])
    assert inv.excluded_counts["service=driveway"] == 1
    assert inv.excluded_counts["highway=footway"] == 1


def test_bridge_deck_and_grade_separation(inv):
    decks = list(inv.bridge_decks.values())
    assert len(decks) == 1
    deck = decks[0]
    assert deck.crossing_id == "XS-TEST" and deck.level == 1
    gs = [g for g in inv.grade_separations.values() if g.determinate]
    assert len(gs) == 1
    assert inv.segments[gs[0].upper_segment].bridge
    assert inv.segments[gs[0].lower_segment].name == "Street D"
    assert not [g for g in inv.grade_separations.values() if not g.determinate]


def test_tunnel_flagged(inv):
    t = [s for s in inv.segments.values() if s.tunnel]
    assert len(t) == 1 and t[0].name == "Street E"


def test_connectivity(inv):
    comps = {s.component for s in inv.segments.values() if s.scope == "in_scope"}
    # A+B+D+E connected; Avenue C is a separate component in this fixture
    assert len(comps) == 2


def test_ids_are_deterministic_and_stable(tmp_path):
    a = build_inventory(S.osm_data(), crossings=S.CROSSINGS)
    b = build_inventory(S.osm_data(), crossings=S.CROSSINGS)
    assert set(a.segments) == set(b.segments)
    assert set(a.bridge_decks) == set(b.bridge_decks)


def test_registry_inherits_id_when_way_renumbered(tmp_path):
    reg = IdRegistry(tmp_path / "reg.json")
    first = reg.assign_batch("segment", "SEG", [("101:1:2:0", "1:2:5")])
    reg.save()
    reg2 = IdRegistry(tmp_path / "reg.json")
    second = reg2.assign_batch("segment", "SEG", [("555:1:2:0", "1:2:5")])  # same nodes, new way id
    assert second["555:1:2:0"] == first["101:1:2:0"]
    third = reg2.assign_batch("segment", "SEG", [("556:7:8:0", "7:8:3")])
    assert third["556:7:8:0"] != first["101:1:2:0"]


def test_bridge_straddling_boundary_is_dropped_whole():
    from shapely.geometry import box
    # project area ends at y=50 (mid-span of the synthetic bridge)
    x0, y0 = S.ll(-400, -400)
    x1, y1 = S.ll(600, 50)
    inv = build_inventory(S.osm_data(), boroughs={"Test": box(x0, y0, x1, y1)}, crossings=S.CROSSINGS)
    assert not inv.bridge_decks
    assert not [s for s in inv.segments.values() if s.bridge]
    kinds = {j.kind for j in inv.junctions.values()}
    assert "boundary_bridge_cut" in kinds


def test_summary_km_matches_segment_lengths(inv):
    s = inv.summary()["segments_by_scope_borough"]
    total = sum(v["km"] for v in s.values())
    assert abs(total - sum(seg.length_m for seg in inv.segments.values()) / 1000) < 0.002
