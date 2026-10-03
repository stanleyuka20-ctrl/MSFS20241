"""Command line interface: ``python -m nycroads <command>`` (or ``nycroads``)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def _load_release(path: str) -> dict:
    cfg = json.loads(Path(path).read_text())
    cfg["_path"] = path
    return cfg


def _p(cfg, key):
    v = cfg.get(key)
    return None if v is None else (ROOT / v if not Path(v).is_absolute() else Path(v))


def load_inventory(cfg: dict):
    from .ids import IdRegistry
    from .inventory import build_inventory
    from .osm import OsmData, borough_polygons

    paths = [ROOT / p for p in cfg["osm"]]
    data = OsmData.load(*paths)
    boroughs = None
    if cfg.get("boroughs"):
        boroughs = borough_polygons(OsmData.load(_p(cfg, "boroughs")))
    extensions = None
    if cfg.get("extensions"):
        from shapely.geometry import shape
        ext = json.loads(_p(cfg, "extensions").read_text())
        extensions = {f["properties"]["name"]: shape(f["geometry"]) for f in ext["features"]}
    crossings = json.loads(_p(cfg, "crossings").read_text())["crossings"] if cfg.get("crossings") else []
    reg = IdRegistry(_p(cfg, "id_registry")) if cfg.get("id_registry") else IdRegistry(None)
    inv = build_inventory(data, boroughs, extensions, crossings, reg,
                          drop_outside=bool(boroughs) and not cfg.get("keep_outside", False))
    inv.sources = [json.loads(p.with_suffix(".source.json").read_text())
                   for p in paths if p.with_suffix(".source.json").exists()]
    return inv, reg


def load_profiles(build_dir: Path) -> dict:
    raw = json.loads((build_dir / "profiles.json").read_text())
    return {sid: SimpleNamespace(segment_id=sid, s=np.array(v["s"]), z_sim=np.array(v["z_sim"]),
                                 xy_utm=np.array(v["xy_utm"]), source=v["source"])
            for sid, v in raw.items()}


def cmd_fetch(a):
    from . import osm
    out = Path(a.out)
    if a.what == "boroughs":
        osm.fetch(osm.boroughs_query(), out)
    else:
        bbox = tuple(float(x) for x in a.bbox.split(",")) if a.bbox else osm.NYC_BBOX
        if a.tiles > 1:
            for k, b in enumerate(osm.split_bbox(bbox, a.tiles, a.tiles)):
                osm.fetch(osm.roads_query(b), out.with_name(f"{out.stem}_{k:02d}.json"))
        else:
            osm.fetch(osm.roads_query(bbox), out)


def cmd_inventory(a):
    cfg = _load_release(a.release)
    inv, reg = load_inventory(cfg)
    out = ROOT / cfg.get("inventory_dir", "build/inventory")
    inv.write(out)
    reg.save()
    print(json.dumps(inv.summary(), indent=1))


def cmd_build(a):
    from .coverage import StatusStore
    from .demo import evaluate
    from .elevation import RasterDEM, VerticalReference, load_deck_controls
    from .gltf import load_msfs_config
    from .pipeline import build, select_segments

    cfg = _load_release(a.release)
    msfs_cfg = load_msfs_config(ROOT / cfg.get("msfs_gltf_config", "config/msfs_gltf.json"))
    if not msfs_cfg.get("verified") and not a.allow_unverified:
        sys.exit("config/msfs_gltf.json is not verified against the installed SDK. "
                 "Verify it (docs/02) or pass --allow-unverified for a test build.")
    inv, reg = load_inventory(cfg)
    reg.save()
    d = cfg["dem"]
    dem = RasterDEM(_p(d, "path") if not Path(d["path"]).is_absolute() else Path(d["path"]),
                    d.get("z_units", "m"), d.get("datum", "NAVD88"))
    vref = VerticalReference.load(_p(cfg, "vertical_reference"))
    controls = load_deck_controls(_p(cfg, "deck_controls"))
    if cfg.get("bbox") or cfg.get("segment_ids"):
        sel = select_segments(inv, tuple(cfg["bbox"]) if cfg.get("bbox") else None, cfg.get("segment_ids"))
    else:
        sel = select_segments(inv, ids=list(inv.segments))   # whole inventory
    out = ROOT / cfg.get("build_dir", f"build/{cfg['release']}")
    marker = None
    if cfg.get("orientation_marker_at"):
        lon, lat = cfg["orientation_marker_at"]
        z = float(vref.to_sim(lon, lat, dem.sample([lon], [lat]))[0])
        marker = (lon, lat, z)
    rep = build(inv, sel, dem, vref, controls, msfs_cfg, out, cfg["package_name"],
                _p(cfg, "package_root"), marker)
    if cfg.get("demo"):
        profiles = load_profiles(out)
        demo = evaluate(inv, sel, profiles)
        (out / "demo_acceptance.json").write_text(json.dumps(demo, indent=1, default=str))
        print("demo acceptance:", json.dumps({k: v.get("pass") if isinstance(v, dict) else v
                                              for k, v in demo.items()}))
    store = StatusStore(ROOT / cfg.get("status", "data/status.json"))
    store.record_build(rep["build_id"], set(rep["_generated"]), rep["issues"], rep["blocked"])
    store.save()
    print(f"build {rep['build_id']}: {rep['generated_segments']} segments, {rep['junction_pads']} pads, "
          f"{len(rep['segments_with_errors'])} with errors, {len(rep['blocked'])} blocked -> {out}")


def cmd_analyse(a):
    from .coverage import StatusStore
    from .telemetry import analyse_run, load_run, save_result

    cfg = _load_release(a.release)
    inv, _ = load_inventory(cfg)
    build_dir = ROOT / cfg.get("build_dir", f"build/{cfg['release']}")
    rep = json.loads((build_dir / "build_report.json").read_text())
    profiles = load_profiles(build_dir)
    meta = json.loads(Path(a.meta).read_text()) if a.meta else {}
    meta.setdefault("build_id", rep["build_id"])
    meta["after_restart"] = a.after_restart or meta.get("after_restart", False)
    run_id = a.run_id or Path(a.run).stem
    res = analyse_run(load_run(Path(a.run)), inv, profiles, run_id, meta, a.ref_height)
    p = save_result(res, ROOT / cfg.get("results_dir", "tests/results"))
    store = StatusStore(ROOT / cfg.get("status", "data/status.json"))
    store.record_run(res.to_json())
    store.save()
    summary = ", ".join(k + ":" + "/".join(f"{d}={v['result']}" for d, v in dd.items())
                        for k, dd in res.segments.items())
    print(f"{p}: {len(res.incidents)} incidents; segments: {summary}")


def cmd_coverage(a):
    from .coverage import StatusStore, write_coverage

    cfg = _load_release(a.release)
    inv, _ = load_inventory(cfg)
    store = StatusStore(ROOT / cfg.get("status", "data/status.json"))
    rep = write_coverage(inv, store, ROOT / cfg.get("coverage_dir", "coverage"))
    print(json.dumps(rep["totals"], indent=1))


def cmd_deck_controls(a):
    from .deckcontrols import controls_from_points, read_las, update_controls_file
    from .elevation import FT, VerticalReference

    cfg = _load_release(a.release)
    inv, _ = load_inventory(cfg)
    decks = [d for d in inv.bridge_decks.values() if a.key in (d.id, d.crossing_id)]
    if not decks:
        sys.exit(f"no bridge deck with id/crossing {a.key} in this release's inventory")
    vref = VerticalReference.load(_p(cfg, "vertical_reference"))
    pts, cls = None, None
    crs = a.crs
    for f in a.las:
        p, c, file_crs = read_las(Path(f))
        crs = crs or file_crs
        pts = p if pts is None else np.vstack([pts, p])
        cls = c if cls is None else np.concatenate([cls, c])
    if not crs:
        sys.exit("lidar CRS unknown: pass --crs (e.g. EPSG:2263 or EPSG:6539 for NYC State Plane)")
    scale = {"m": 1.0, "ft": 0.3048, "ftUS": FT}[a.z_units]
    controls = []
    for d in decks:
        for sid in d.segment_ids:
            controls += controls_from_points(inv.segments[sid].coords, pts, cls, crs, vref.to_sim,
                                             step_m=a.step, z_scale=scale,
                                             source=f"lidar-class17:{','.join(Path(f).name for f in a.las)}")
    update_controls_file(_p(cfg, "deck_controls"), a.key, controls)
    print(f"{len(controls)} controls written for {a.key}"
          + ("" if vref.verified else " (vertical reference UNVERIFIED: heights are not yet in sim reference)"))


def cmd_record(a):
    from . import simbridge
    if a.selftest:
        simbridge.selftest()
    else:
        simbridge.record(Path(a.out), a.hz, a.duration, Path(a.markers) if a.markers else None)


def cmd_recover(a):
    from . import simbridge
    cfg = _load_release(a.release)
    rep = json.loads((ROOT / cfg.get("build_dir", f"build/{cfg['release']}") / "build_report.json").read_text())
    starts = {s["id"]: s for s in rep["start_locations"]}
    s = starts.get(a.start)
    if s is None:
        sys.exit(f"unknown start location {a.start}; known: {', '.join(list(starts)[:10])} ...")
    simbridge.recover(s["lat"], s["lon"], s["surface_alt_m"] + a.ref_height, s["heading_deg"],
                      Path(a.markers) if a.markers else None)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="nycroads")
    sp = ap.add_subparsers(dest="cmd", required=True)

    f = sp.add_parser("fetch", help="download OSM data via Overpass (needs network access)")
    f.add_argument("what", choices=["roads", "boroughs"])
    f.add_argument("--bbox", help="s,w,n,e (default: NYC)")
    f.add_argument("--tiles", type=int, default=1, help="split bbox into N x N requests")
    f.add_argument("--out", required=True)
    f.set_defaults(fn=cmd_fetch)

    for name, fn, h in (("inventory", cmd_inventory, "build the road/bridge inventory"),
                        ("build", cmd_build, "generate geometry, checks and package content"),
                        ("coverage", cmd_coverage, "write coverage map and tables")):
        p = sp.add_parser(name, help=h)
        p.add_argument("--release", required=True, help="release config JSON (see releases/)")
        if name == "build":
            p.add_argument("--allow-unverified", action="store_true",
                           help="build even though MSFS-specific formats are not yet verified (test builds only)")
        p.set_defaults(fn=fn)

    p = sp.add_parser("analyse-run", help="analyse a telemetry CSV and record the result")
    p.add_argument("--release", required=True)
    p.add_argument("--run", required=True)
    p.add_argument("--meta", help="JSON with sim version, vehicle, settings, tester")
    p.add_argument("--run-id")
    p.add_argument("--after-restart", action="store_true")
    p.add_argument("--ref-height", type=float, default=None)
    p.set_defaults(fn=cmd_analyse)

    p = sp.add_parser("deck-controls", help="derive deck elevation controls from classified lidar")
    p.add_argument("--release", required=True)
    p.add_argument("--key", required=True, help="crossing id (XS-*) or deck id (BRG-*)")
    p.add_argument("--las", nargs="+", required=True, help="LAS/LAZ tiles covering the deck")
    p.add_argument("--crs", help="override lidar CRS if not in the file header")
    p.add_argument("--z-units", choices=["m", "ft", "ftUS"], default="m")
    p.add_argument("--step", type=float, default=25.0)
    p.set_defaults(fn=cmd_deck_controls)

    p = sp.add_parser("record", help="record telemetry from the running simulator (Windows)")
    p.add_argument("--out", default="telemetry/run.csv")
    p.add_argument("--hz", type=float, default=20)
    p.add_argument("--duration", type=float)
    p.add_argument("--markers", help="text file; lines appended during the run become events")
    p.add_argument("--selftest", action="store_true")
    p.set_defaults(fn=cmd_record)

    p = sp.add_parser("recover", help="explicitly move the vehicle to a verified start location (logged)")
    p.add_argument("--release", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--ref-height", type=float, required=True)
    p.add_argument("--markers")
    p.set_defaults(fn=cmd_recover)

    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
