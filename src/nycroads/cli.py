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

    boroughs = None
    if cfg.get("overture_segments"):
        from . import overture
        paths = [_p(cfg, "overture_segments")]
        bb = cfg.get("inventory_bbox")
        data, conv_stats = overture.to_osmdata(paths[0], tuple(bb) if bb else None)
        if cfg.get("overture_divisions"):
            boroughs = overture.borough_polygons(_p(cfg, "overture_divisions"))
    else:
        paths = [ROOT / p for p in cfg["osm"]]
        data = OsmData.load(*paths)
        conv_stats = {}
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
    if conv_stats:
        inv.sources.append({"conversion": conv_stats})
    return inv, reg


def load_profiles(build_dir: Path) -> dict:
    raw = json.loads((build_dir / "profiles.json").read_text())
    return {sid: SimpleNamespace(segment_id=sid, s=np.array(v["s"]), z_sim=np.array(v["z_sim"]),
                                 xy_utm=np.array(v["xy_utm"]), source=v["source"], info=v.get("info", {}))
            for sid, v in raw.items()}


def cmd_fetch(a):
    from . import osm
    if a.what in ("usgs-dem", "usgs-lidar"):
        from . import usgs
        cfg = _load_release(a.release)
        bbox = tuple(cfg.get("inventory_bbox") or cfg["bbox"])
        if a.what == "usgs-dem":
            proj = cfg["dem"].get("usgs_project", "NY_CMPG_2013")
            print(usgs.fetch_dem(bbox, proj, ROOT / cfg["dem"]["path"]))
        else:
            print(usgs.fetch_lidar_surface(bbox, cfg.get("lidar_ept", "NY_NewYorkCity"),
                                           _p(cfg, "lidar_surface"), ROOT / "data/raw/ept_cache"))
        return
    out = Path(a.out)
    if a.what.startswith("overture"):
        from . import overture
        bbox = tuple(float(x) for x in a.bbox.split(",")) if a.bbox else osm.NYC_BBOX
        if a.what == "overture-roads":
            import pyarrow.compute as pc
            overture.fetch("transportation", "segment", bbox, out, extra_filter=pc.field("subtype") == "road")
        else:
            overture.fetch("divisions", "division_area", bbox, out)
        return
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
    controls = load_deck_controls(_p(cfg, "deck_controls"), vref)
    if cfg.get("bbox") or cfg.get("segment_ids"):
        sel = select_segments(inv, tuple(cfg["bbox"]) if cfg.get("bbox") else None, cfg.get("segment_ids"))
    else:
        sel = select_segments(inv, ids=list(inv.segments))   # whole inventory
    excluded = {}
    for grp in cfg.get("excluded_segments", []):
        for sid in grp["ids"]:
            if sid not in inv.segments:
                sys.exit(f"excluded segment {sid} not in inventory (IDs changed?)")
            excluded[sid] = "excluded: " + grp["reason"]
    sel -= set(excluded)
    out = ROOT / cfg.get("build_dir", f"build/{cfg['release']}")
    marker = None
    if cfg.get("orientation_marker_at"):
        lon, lat = cfg["orientation_marker_at"]
        z = float(vref.to_sim(lon, lat, dem.sample([lon], [lat]))[0])
        marker = (lon, lat, z)
    lidar = None
    if cfg.get("lidar_surface"):
        from .lidarsurface import LidarSurface
        lidar = LidarSurface(_p(cfg, "lidar_surface"))
    rep = build(inv, sel, dem, vref, controls, msfs_cfg, out, cfg["package_name"],
                _p(cfg, "package_root"), marker, lidar, excluded)
    if cfg.get("demo"):
        profiles = load_profiles(out)
        demo = evaluate(inv, sel, profiles)
        (out / "demo_acceptance.json").write_text(json.dumps(demo, indent=1, default=str))
        print("demo acceptance:", json.dumps({k: v.get("pass") if isinstance(v, dict) else v
                                              for k, v in demo.items()}))
    store = StatusStore(ROOT / cfg.get("status", "data/status.json"))
    store.record_build(rep["build_id"], set(rep["_generated"]), rep["issues"], rep["blocked"])
    store.save()
    print(f"build {rep['build_id']}: {rep['generated_segments']} segments, {rep['surface_groups']} surface groups, "
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
    """Deck elevation controls from classified lidar (local LAS/LAZ or a USGS EPT dataset)."""
    from pyproj import Transformer

    from .deckcontrols import controls_with_fallback, read_las, update_controls_file
    from .elevation import FT, VerticalReference
    from .pipeline import select_segments

    cfg = _load_release(a.release)
    inv, _ = load_inventory(cfg)
    if a.all:
        sel = select_segments(inv, tuple(cfg["bbox"]) if cfg.get("bbox") else None, cfg.get("segment_ids"))
        decks = [d for d in inv.bridge_decks.values() if set(d.segment_ids) & sel]
    else:
        decks = [d for d in inv.bridge_decks.values() if a.key in (d.id, d.crossing_id)]
    if not decks:
        sys.exit("no matching bridge decks in this release's inventory")
    vref = VerticalReference.load(_p(cfg, "vertical_reference"))
    scale = {"m": 1.0, "ft": 0.3048, "ftUS": FT}[a.z_units]
    if a.ept:
        from .ept import EPT
        to3857 = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        xs, ys = [], []
        for d in decks:
            for sid in d.segment_ids:
                x, y = to3857.transform(*np.array(inv.segments[sid].coords).T)
                xs += list(x); ys += list(y)
        box = (min(xs) - 60, min(ys) - 60, max(xs) + 60, max(ys) + 60)
        pts = EPT(a.ept, cache=ROOT / "data/raw/ept_cache").query(box)
        lon, lat = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True).transform(pts["x"], pts["y"])
        ux, uy = Transformer.from_crs("EPSG:4326", "EPSG:32618", always_xy=True).transform(lon, lat)
        P, cls, crs = np.column_stack([ux, uy, pts["z"]]), pts["classification"], "EPSG:32618"
        src = f"lidar-class17:usgs-lidar-public/{a.ept}"
    else:
        P, cls, crs = None, None, a.crs
        for f in a.las:
            p, c, file_crs = read_las(Path(f))
            crs = crs or file_crs
            P = p if P is None else np.vstack([P, p])
            cls = c if cls is None else np.concatenate([cls, c])
        src = f"lidar-class17:{','.join(Path(f).name for f in a.las)}"
    if not crs:
        sys.exit("lidar CRS unknown: pass --crs")
    path = _p(cfg, "deck_controls")
    for d in decks:
        controls = []
        for sid in d.segment_ids:
            controls += controls_with_fallback(inv.segments[sid].coords, P, cls, crs, vref.to_sim,
                                             step_m=a.step, z_scale=scale, source=src,
                                             native_datum=a.native_datum)
        key = d.id
        update_controls_file(path, key, controls, extra={"name": d.name, "crossing_id": d.crossing_id,
                                                         "deck_length_m": d.length_m})
        print(f"{key} {d.name or '(unnamed)'}: {len(controls)} controls")


def cmd_test_plan(a):
    from .pipeline import select_segments
    from .testplan import make_plan, write
    cfg = _load_release(a.release)
    inv, _ = load_inventory(cfg)
    build_dir = ROOT / cfg.get("build_dir", f"build/{cfg['release']}")
    rep = json.loads((build_dir / "build_report.json").read_text())
    if cfg.get("bbox") or cfg.get("segment_ids"):
        sel = select_segments(inv, tuple(cfg["bbox"]) if cfg.get("bbox") else None, cfg.get("segment_ids"))
    else:
        sel = select_segments(inv, ids=list(inv.segments))
    plan = make_plan(inv, load_profiles(build_dir), rep, sel)
    out = ROOT / a.out
    write(plan, out, f"Driving test plan - {cfg['release']}")
    print(out / "TEST_PLAN.md")


def cmd_make_testpad(a):
    from .elevation import RasterDEM
    from .testpad import write
    cfg = _load_release(a.release)
    dem = RasterDEM(ROOT / cfg["dem"]["path"], cfg["dem"].get("z_units", "m"))
    print(write(cfg["testpad"]["lat0"], cfg["testpad"]["lon0"], dem.sample, ROOT / "data/testpad"))


def cmd_check_lidar_datum(a):
    from .usgs import lidar_dem_offset
    cfg = _load_release(a.release)
    r = lidar_dem_offset(_p(cfg, "lidar_surface"), ROOT / cfg["dem"]["path"])
    print(json.dumps(r))
    if abs(r["median_m"]) > 0.05 or r["mad_m"] > 0.15:
        sys.exit("lidar and DEM do not share a vertical datum/surface: resolve before using lidar heights")


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

    f = sp.add_parser("fetch", help="download OSM (Overpass) or Overture (AWS S3) data")
    f.add_argument("what", choices=["roads", "boroughs", "overture-roads", "overture-divisions", "usgs-dem", "usgs-lidar"])
    f.add_argument("--release", help="release config (usgs-dem / usgs-lidar read bbox and output paths from it)")
    f.add_argument("--bbox", help="s,w,n,e (default: NYC)")
    f.add_argument("--tiles", type=int, default=1, help="split bbox into N x N requests")
    f.add_argument("--out")
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
    p.add_argument("--key", help="crossing id (XS-*) or deck id (BRG-*)")
    p.add_argument("--all", action="store_true", help="every deck in the release's build selection")
    p.add_argument("--las", nargs="+", help="LAS/LAZ tiles covering the deck")
    p.add_argument("--ept", help="USGS EPT dataset name, e.g. NY_NewYorkCity")
    p.add_argument("--native-datum", default="NAVD88")
    p.add_argument("--crs", help="override lidar CRS if not in the file header")
    p.add_argument("--z-units", choices=["m", "ft", "ftUS"], default="m")
    p.add_argument("--step", type=float, default=25.0)
    p.set_defaults(fn=cmd_deck_controls)

    p = sp.add_parser("test-plan", help="concrete D1-D10 start points and segments for a build")
    p.add_argument("--release", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_test_plan)

    p = sp.add_parser("make-testpad", help="generate the Gate G1 test-pad layout (designed, not real roads)")
    p.add_argument("--release", required=True)
    p.set_defaults(fn=cmd_make_testpad)

    p = sp.add_parser("check-lidar-datum", help="compare lidar ground returns with the DEM (vertical datum check)")
    p.add_argument("--release", required=True)
    p.set_defaults(fn=cmd_check_lidar_datum)

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
