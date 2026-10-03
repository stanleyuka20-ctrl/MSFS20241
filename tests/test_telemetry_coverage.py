import numpy as np
import synthetic as S

from nycroads.coverage import StatusStore, coverage_report, derive_status
from nycroads.telemetry import Sample, analyse_run

REF = 0.6


def surface_z(profiles, inv, x, y, names=("Avenue C",)):
    best = None
    for sid, p in profiles.items():
        if inv.segments[sid].name not in names:
            continue
        d = np.hypot(p.xy_utm[:, 0] - (S.X0 + x), p.xy_utm[:, 1] - (S.Y0 + y))
        k = int(np.argmin(d))
        if best is None or d[k] < best[0]:
            best = (d[k], float(p.z_sim[k]))
    return best[1]


def drive_avenue_c(profiles, inv, north=True, fall_on_bridge=False, recovery_at=None, reverse_gear=False):
    ys = np.arange(-295, 296, 1.0)
    if not north:
        ys = ys[::-1]
    samples, t = [], 0.0
    for k, y in enumerate(ys):
        z = surface_z(profiles, inv, 300, y)
        if fall_on_bridge and -40 < y < 40:
            z = float(S.terrain(300, y))
        lon, lat = S.ll(300, y)
        heading = 0.0 if north else 180.0
        if reverse_gear:
            heading = (heading + 180) % 360
        ev = "recovery to start" if recovery_at is not None and abs(y - recovery_at) < 0.5 else ""
        gs = 0.0 if k < 25 else 10.0
        samples.append(Sample(t, lat, lon, z + REF, True, gs, 0.0, heading, 0.0, ev))
        t += 0.1
    return samples


def test_clean_drive_passes_both_directions(built, inv):
    pr = built["profiles"]
    r1 = analyse_run(drive_avenue_c(pr, inv, north=True), inv, pr, "r1", {})
    r2 = analyse_run(drive_avenue_c(pr, inv, north=False, reverse_gear=True), inv, pr, "r2", {})
    assert abs(r1.ref_height_m - REF) < 0.05
    assert not r1.incidents and not r2.incidents
    deck_segs = next(iter(inv.bridge_decks.values())).segment_ids
    for sid in deck_segs:
        assert r1.segments[sid]["forward"]["result"] == "pass"
        assert r2.segments[sid]["backward"]["result"] == "pass"
    assert r2.meta["reverse_distance_m"] > 400 and r1.meta["reverse_distance_m"] == 0


def test_fall_through_detected(built, inv):
    pr = built["profiles"]
    r = analyse_run(drive_avenue_c(pr, inv, fall_on_bridge=True), inv, pr, "r3", {}, ref_height_m=REF)
    assert any(i["type"] == "fall_through" for i in r.incidents)
    deck_segs = set(next(iter(inv.bridge_decks.values())).segment_ids)
    assert any(r.segments[s]["forward"]["result"] == "fail" for s in deck_segs if s in r.segments)


def test_recovery_fails_segment(built, inv):
    pr = built["profiles"]
    r = analyse_run(drive_avenue_c(pr, inv, recovery_at=-200), inv, pr, "r4", {}, ref_height_m=REF)
    assert any(i["type"] == "recovery" for i in r.incidents)
    assert any(v.get("forward", {}).get("result") == "fail" for v in r.segments.values())


def test_status_requires_both_directions_restart_and_current_build(built, inv, tmp_path):
    rep = built["report"]
    store = StatusStore(tmp_path / "status.json")
    store.record_build(rep["build_id"], set(rep["_generated"]), rep["issues"], rep["blocked"])
    deck_seg = next(iter(inv.bridge_decks.values())).segment_ids[0]
    seg = inv.segments[deck_seg]
    assert derive_status(seg, store.data["objects"][deck_seg]) == "geometry_verified"

    def run(rid, direction, after_restart, build_id=rep["build_id"], result="pass"):
        store.record_run({"run_id": rid, "meta": {"build_id": build_id, "after_restart": after_restart},
                          "segments": {deck_seg: {direction: {"result": result, "coverage": 1.0}}}})

    run("a", "forward", False)
    assert derive_status(seg, store.obj(deck_seg)) == "geometry_verified"   # backward missing
    run("b", "backward", False)
    assert derive_status(seg, store.obj(deck_seg)) == "driven"
    run("c", "forward", True)
    run("d", "backward", True)
    assert derive_status(seg, store.obj(deck_seg)) == "verified"
    run("e", "forward", True, result="fail")
    assert derive_status(seg, store.obj(deck_seg)) == "geometry_verified"   # latest failure wins
    store.record_build("NEWBUILD", set(rep["_generated"]), rep["issues"], rep["blocked"])
    assert derive_status(seg, store.obj(deck_seg)) == "geometry_verified"   # old evidence invalid


def test_coverage_report_counts_tunnel_as_blocked(built, inv, tmp_path):
    rep = built["report"]
    store = StatusStore(tmp_path / "status.json")
    store.record_build(rep["build_id"], set(rep["_generated"]), rep["issues"], rep["blocked"])
    cov = coverage_report(inv, store)
    tunnel = [s.id for s in inv.segments.values() if s.tunnel][0]
    assert cov["segment_status"][tunnel] == "blocked"
    assert "verified" not in cov["totals"]
