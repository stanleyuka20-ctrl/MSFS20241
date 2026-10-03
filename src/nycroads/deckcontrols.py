"""Derive bridge-deck control points from classified lidar.

Input: points (x, y, z, classification) in any projected CRS, typically read
from LAS/LAZ with laspy (``pip install laspy[lazrs]``). ASPRS class 17 is
"Bridge Deck". If a survey has no class 17, pass ``classes=(1,)`` etc. only
together with ``first_return_dsm=True`` provenance so the source is recorded as
the weaker DSM method (docs/05).

For each station along the deck centreline (every ``step_m``), the control
height is the median z of selected points within ``radius_m`` of the
centreline, after rejecting points more than ``reject_m`` from the local
median (lamp posts, vehicles, cables, overhead structures).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString

BRIDGE_DECK_CLASS = 17


def controls_from_points(centreline_lonlat, pts_xyz: np.ndarray, cls: np.ndarray, crs: str,
                         to_sim, step_m: float = 25.0, radius_m: float = 1.0, reject_m: float = 0.5,
                         classes=(BRIDGE_DECK_CLASS,), z_scale: float = 1.0, min_points: int = 5,
                         source: str = "lidar-class17") -> list[dict]:
    """Return deck control dicts ({lon, lat, z_sim_m, source, n_points, spread_m})."""
    fwd = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    inv = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    xs, ys = fwd.transform(*np.array(centreline_lonlat).T)
    line = LineString(zip(xs, ys))
    sel = np.isin(cls, classes)
    P = pts_xyz[sel]
    out = []
    for d in np.arange(0.0, line.length + 1e-6, step_m):
        p = line.interpolate(d)
        near = P[np.hypot(P[:, 0] - p.x, P[:, 1] - p.y) <= radius_m]
        if len(near) < min_points:
            continue
        z = near[:, 2] * z_scale
        med = np.median(z)
        z = z[np.abs(z - med) <= reject_m]
        if len(z) < min_points:
            continue
        lon, lat = inv.transform(p.x, p.y)
        z_sim = float(np.atleast_1d(to_sim(lon, lat, np.median(z)))[0])
        out.append({"lon": round(lon, 8), "lat": round(lat, 8), "z_sim_m": round(z_sim, 3),
                    "source": source, "n_points": int(len(z)),
                    "spread_m": round(float(np.percentile(z, 90) - np.percentile(z, 10)), 3)})
    return out


def read_las(path: Path):
    import laspy  # optional dependency

    las = laspy.read(str(path))
    crs = las.header.parse_crs()
    pts = np.column_stack([las.x, las.y, las.z])
    return pts, np.asarray(las.classification), (crs.to_string() if crs else None)


def update_controls_file(path: Path, key: str, controls: list[dict]) -> None:
    data = json.loads(Path(path).read_text()) if Path(path).exists() else {}
    data[key] = {"controls": controls, "status": f"{len(controls)} controls from lidar"}
    Path(path).write_text(json.dumps(data, indent=1))
