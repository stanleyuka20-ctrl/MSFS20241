"""USGS 3DEP downloads (public domain): 1 m DEM tiles and EPT lidar point clouds.

Both come from public AWS buckets (prd-tnm, usgs-lidar-public), reachable where
the USGS web APIs are not. Every output gets a provenance record.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from pyproj import Transformer

TNM = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects"


def dem_tiles(bbox, utm_epsg: str = "EPSG:26918") -> list[str]:
    """USGS 1 m tile names (xNNyNNN, 10 km, named by upper-left corner) covering bbox (s, w, n, e)."""
    s, w, n, e = bbox
    t = Transformer.from_crs("EPSG:4326", utm_epsg, always_xy=True)
    xs, ys = t.transform([w, e, w, e], [s, s, n, n])
    out = []
    for ix in range(int(min(xs) // 10000), int(max(xs) // 10000) + 1):
        for iy in range(int(math.ceil(min(ys) / 10000)), int(math.ceil(max(ys) / 10000)) + 1):
            out.append(f"x{ix}y{iy}")
    return out


def fetch_dem(bbox, project: str, out: Path, margin_m: float = 50.0) -> Path:
    """Mosaic + crop the project's 1 m DEM tiles to bbox; writes GeoTIFF + provenance."""
    import rasterio
    from rasterio.merge import merge

    s, w, n, e = bbox
    t = Transformer.from_crs("EPSG:4326", "EPSG:26918", always_xy=True)
    xs, ys = t.transform([w, e, w, e], [s, s, n, n])
    bounds = (min(xs) - margin_m, min(ys) - margin_m, max(xs) + margin_m, max(ys) + margin_m)
    srcs, used = [], []
    for tile in dem_tiles(bbox):
        url = f"/vsicurl/{TNM}/{project}/TIFF/USGS_one_meter_{tile}_{project}.tif"
        try:
            srcs.append(rasterio.open(url))
            used.append(tile)
        except Exception:   # tile not in this project
            continue
    if not srcs:
        raise SystemExit(f"no {project} DEM tiles cover {bbox}")
    arr, tr = merge(srcs, bounds=bounds, res=1.0, nodata=-9999.0)
    prof = srcs[0].profile
    prof.update(height=arr.shape[1], width=arr.shape[2], transform=tr, nodata=-9999.0, compress="deflate",
                tiled=True, blockxsize=256, blockysize=256, driver="GTiff", count=1, dtype="float32")
    out.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out, "w", **prof) as o:
        o.write(arr.astype("float32"))
    Path(str(out).replace(".tif", ".source.json")).write_text(json.dumps({
        "product": f"USGS 3DEP 1 m DEM, project {project}", "tiles": used, "source": f"{TNM}/{project}/TIFF/",
        "crs": "EPSG:26918 (NAD83 / UTM 18N)", "vertical": "NAVD88 metres (USGS 1 m DEM standard; see tile metadata)",
        "surface": "bare earth", "license": "public domain (USGS 3DEP)", "crop_bounds_utm": bounds,
        "retrieved_utc": datetime.now(timezone.utc).isoformat()}, indent=1))
    return out


def fetch_lidar_surface(bbox, dataset: str, out: Path, cache: Path, classes=(2, 17), chunks: int = 4) -> Path:
    """Classes 2 + 17 from a USGS EPT dataset over bbox -> compact npz (UTM 18N offsets) + provenance."""
    from .ept import EPT

    s, w, n, e = bbox
    t = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    x0, y0 = t.transform(w, s)
    x1, y1 = t.transform(e, n)
    ept = EPT(dataset, cache=cache)
    xs, ys = np.linspace(x0, x1, chunks + 1), np.linspace(y0, y1, chunks + 1)
    X, Y, Z, C = [], [], [], []
    for i in range(chunks):
        for j in range(chunks):
            p = ept.query((xs[i], ys[j], xs[i + 1], ys[j + 1]))
            m = np.isin(p["classification"], classes)
            X.append(p["x"][m]); Y.append(p["y"][m]); Z.append(p["z"][m]); C.append(p["classification"][m])
    X, Y, Z, C = map(np.concatenate, (X, Y, Z, C))
    lon, lat = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True).transform(X, Y)
    ux, uy = Transformer.from_crs("EPSG:4326", "EPSG:32618", always_xy=True).transform(lon, lat)
    ox, oy = float(np.floor(ux.min())), float(np.floor(uy.min()))
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, x=(ux - ox).astype(np.float32), y=(uy - oy).astype(np.float32),
                        z=Z.astype(np.float32), c=C.astype(np.uint8), origin=np.array([ox, oy]))
    Path(str(out).replace(".npz", ".source.json")).write_text(json.dumps({
        "dataset": f"s3://usgs-lidar-public/{dataset} (EPT, USGS 3DEP, public domain)",
        "classes_kept": list(classes), "crs": "EPSG:32618 (x,y stored as offsets from origin)",
        "vertical": "as delivered by the dataset; verify against the DEM with `nycroads check-lidar-datum`",
        "bbox_swne": list(bbox), "points": int(len(Z)), "retrieved_utc": datetime.now(timezone.utc).isoformat()},
        indent=1))
    return out


def lidar_dem_offset(lidar_npz: Path, dem_tif: Path, sample: int = 200000) -> dict:
    """Median/MAD of (lidar class-2 z - DEM) at the lidar points: establishes the lidar vertical datum."""
    import rasterio

    d = np.load(lidar_npz)
    g = np.where(d["c"] == 2)[0]
    if len(g) > sample:
        g = np.random.default_rng(0).choice(g, sample, replace=False)
    ux = d["x"][g].astype(float) + d["origin"][0]
    uy = d["y"][g].astype(float) + d["origin"][1]
    lon, lat = Transformer.from_crs("EPSG:32618", "EPSG:4326", always_xy=True).transform(ux, uy)
    with rasterio.open(dem_tif) as ds:
        tx, ty = Transformer.from_crs("EPSG:4326", ds.crs, always_xy=True).transform(lon, lat)
        v = np.array([s[0] for s in ds.sample(zip(tx, ty))])
        ok = v > -9000
    diff = d["z"][g][ok] - v[ok]
    med = float(np.median(diff))
    return {"n": int(ok.sum()), "median_m": round(med, 4), "mad_m": round(float(np.median(np.abs(diff - med))), 4),
            "p5_m": round(float(np.percentile(diff, 5)), 3), "p95_m": round(float(np.percentile(diff, 95)), 3)}
