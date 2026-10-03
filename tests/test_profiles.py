import numpy as np
import pytest
import synthetic as S

from nycroads.elevation import deck_profile, junction_heights
from nycroads.profile import hampel, smooth_profile


def test_hampel_removes_isolated_spike():
    z = np.full(21, 5.0)
    z[10] = 9.0
    f, mask = hampel(z)
    assert mask[10] and abs(f[10] - 5.0) < 1e-9 and mask.sum() == 1


def test_smoothing_keeps_real_hill_and_anchors():
    s = np.arange(0, 201, 5.0)
    z = 5 + 0.06 * np.clip(s - 50, 0, 100)           # real 6 % hill
    zs, _ = smooth_profile(s, z, anchors={0: 5.0, len(s) - 1: 11.0})
    assert zs[0] == pytest.approx(5.0, abs=1e-4) and zs[-1] == pytest.approx(11.0, abs=1e-4)
    mid = np.diff(zs[14:24]) / 5.0                    # middle of the climb
    assert np.all(np.abs(mid - 0.06) < 0.01)


def test_spike_removed_in_ground_profile(built, inv):
    p = [p for sid, p in built["profiles"].items() if inv.segments[sid].name == "Street A"
         and inv.segments[sid].coords[0][0] < S.ORIGIN_LONLAT[0]][0]
    assert p.info["despiked"] >= 1
    assert p.z_sim.max() < 5.5


def test_deck_never_uses_terrain(inv):
    deck = next(iter(inv.bridge_decks.values()))
    node_h = junction_heights(inv, S.dem(), S.vref())
    profs, reason = deck_profile(deck, inv, S.deck_controls()["XS-TEST"], node_h)
    assert reason is None
    z_mid = [p.z_sim.max() for p in profs.values()]
    assert max(z_mid) == pytest.approx(8.0, abs=0.05)   # terrain under the deck is ~0 m


def test_major_deck_without_controls_is_blocked(inv):
    deck = next(iter(inv.bridge_decks.values()))
    node_h = junction_heights(inv, S.dem(), S.vref())
    profs, reason = deck_profile(deck, inv, [], node_h)
    assert profs == {} and "needs deck controls" in reason


def test_deck_continues_approach_grade_no_kink(built, inv):
    from nycroads.checks import run_checks
    from nycroads.surface import build_surfaces
    from nycroads.profile import grade_out
    pr = built["profiles"]
    deck = next(iter(inv.bridge_decks.values()))
    for sid in deck.segment_ids:
        seg = inv.segments[sid]
        for node, at_start in ((seg.from_node, True), (seg.to_node, False)):
            others = [o for o in inv.segments.values() if o.id != sid and o.id in pr
                      and node in (o.from_node, o.to_node) and not o.bridge]
            for o in others:
                g_deck = grade_out(pr[sid].s, pr[sid].z_sim, at_start)
                g_app = grade_out(pr[o.id].s, pr[o.id].z_sim, o.from_node == node)
                assert abs(g_deck + g_app) < 0.03
    issues = run_checks(inv, pr, build_surfaces(inv, pr), {})
    assert not any(i["type"] == "joint_kink" for v in issues.values() for i in v)


def test_kink_check_detects_grade_break_at_joint(built, inv):
    """Two ground segments meet at the same height but with a 6 % grade break -> joint_kink."""
    import copy
    from nycroads.checks import run_checks
    from nycroads.surface import build_surfaces
    pr = dict(built["profiles"])
    conn = [j for j in inv.junctions.values() if j.kind == "connection"
            and all(s in pr and not inv.segments[s].bridge for s in j.segment_ids)][0]
    sid = conn.segment_ids[1]
    p = copy.copy(pr[sid])
    at_start = inv.segments[sid].from_node == conn.osm_node_id
    dist = p.s if at_start else p.s[-1] - p.s
    p.z_sim = p.z_sim + 0.06 * dist          # same height at the joint, 6 % steeper leaving it
    pr[sid] = p
    issues = run_checks(inv, pr, build_surfaces(inv, pr), {})
    assert any(i["type"] == "joint_kink" for v in issues.values() for i in v)


def test_inconsistent_controls_block_deck(inv):
    from nycroads.elevation import DeckControl
    deck = next(iter(inv.bridge_decks.values()))
    node_h = junction_heights(inv, S.dem(), S.vref())
    ctl = S.deck_controls()["XS-TEST"] + [DeckControl(*S.ll(300, 10), 14.0, "overhead structure")]
    profs, reason = deck_profile(deck, inv, ctl, node_h)
    assert profs == {} and "inconsistent deck controls" in reason
