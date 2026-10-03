"""End-to-end run of the CLI on the SYNTHETIC fixture (needs rasterio)."""
import csv
import json

import numpy as np
import pytest
import synthetic as S

rasterio = pytest.importorskip("rasterio")

from nycroads.cli import main  # noqa: E402


def overpass_json(d):
    els = [{"type": "node", "id": n, "lon": lon, "lat": lat} for n, (lon, lat) in d.nodes.items()]
    els += [{"type": "way", "id": w, "nodes": v["nodes"], "tags": v["tags"]} for w, v in d.ways.items()]
    return {"elements": els}


def write_dem(path):
    from rasterio.transform import from_origin
    res = 1.0
    xmin, ymax = S.X0 - 400, S.Y0 + 400
    nx, ny = 1000, 800
    xs = xmin + (np.arange(nx) + 0.5) * res - S.X0
    ys = ymax - (np.arange(ny) + 0.5) * res - S.Y0
    X, Y = np.meshgrid(xs, ys)
    Z = S.terrain(X, Y).astype("float32")
    with rasterio.open(path, "w", driver="GTiff", width=nx, height=ny, count=1, dtype="float32",
                       crs="EPSG:32618", transform=from_origin(xmin, ymax, res, res), nodata=-9999) as ds:
        ds.write(Z, 1)


def test_cli_inventory_build_analyse_coverage(tmp_path):
    (tmp_path / "osm.json").write_text(json.dumps(overpass_json(S.osm_data())))
    write_dem(tmp_path / "dem.tif")
    (tmp_path / "crossings.json").write_text(json.dumps({"crossings": S.CROSSINGS}))
    ctrl = {"XS-TEST": {"controls": [{"lon": c.lon, "lat": c.lat, "z_sim_m": c.z_sim_m, "source": c.source}
                                     for c in S.deck_controls()["XS-TEST"]]}}
    (tmp_path / "deck.json").write_text(json.dumps(ctrl))
    (tmp_path / "vref.json").write_text(json.dumps({"method": "calibrated_offset", "offset_m": 0.0}))
    cfg = {
        "release": "e2e", "package_name": "nycroads-e2e", "osm": [str(tmp_path / "osm.json")],
        "crossings": str(tmp_path / "crossings.json"), "id_registry": str(tmp_path / "ids.json"),
        "dem": {"path": str(tmp_path / "dem.tif"), "z_units": "m"},
        "vertical_reference": str(tmp_path / "vref.json"), "deck_controls": str(tmp_path / "deck.json"),
        "status": str(tmp_path / "status.json"), "demo": True,
        "build_dir": str(tmp_path / "build"), "package_root": str(tmp_path / "pkg"),
        "coverage_dir": str(tmp_path / "cov"), "results_dir": str(tmp_path / "results"),
        "inventory_dir": str(tmp_path / "inv"),
    }
    rel = tmp_path / "release.json"
    rel.write_text(json.dumps(cfg))

    main(["inventory", "--release", str(rel)])
    assert (tmp_path / "inv" / "segments.geojson").exists()
    with pytest.raises(SystemExit):
        main(["build", "--release", str(rel)])          # refuses: MSFS formats unverified
    main(["build", "--release", str(rel), "--allow-unverified"])
    rep = json.loads((tmp_path / "build" / "build_report.json").read_text())
    assert rep["generated_segments"] > 0 and not rep["segments_with_errors"]
    demo = json.loads((tmp_path / "build" / "demo_acceptance.json").read_text())
    assert demo["bridge"]["pass"] and demo["underpass"]["pass"]

    # synthetic telemetry: drive Avenue C north over the bridge
    prof = json.loads((tmp_path / "build" / "profiles.json").read_text())
    pts = []
    for sid, p in prof.items():
        xy = np.array(p["xy_utm"])
        if np.allclose(xy[:, 0] - S.X0, 300, atol=0.5):
            pts += [(y, z) for (x, y), z in zip(xy, p["z_sim"])]
    pts.sort()
    ys = np.array([y for y, _ in pts]) - S.Y0
    zs = np.array([z for _, z in pts])
    with open(tmp_path / "run.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t", "lat", "lon", "alt_m", "on_ground", "gs_mps", "vs_mps", "heading_deg", "brake", "event"])
        for k, y in enumerate(np.arange(-295, 296, 1.0)):
            lon, lat = S.ll(300, y)
            w.writerow([k * 0.1, lat, lon, np.interp(y, ys, zs) + 0.6, 1, 0 if k < 25 else 10, 0, 0, 0, ""])
    main(["analyse-run", "--release", str(rel), "--run", str(tmp_path / "run.csv")])
    res = json.loads((tmp_path / "results" / "run.json").read_text())
    assert not res["incidents"]
    main(["coverage", "--release", str(rel)])
    md = (tmp_path / "cov" / "COVERAGE.md").read_text()
    assert "geometry_verified" in md and "blocked" in md
