"""Road-surface heights from classified lidar (classes 2 ground and 17 bridge deck).

Why: a bare-earth DEM removes every structure. In NYC many streets that OSM does
not tag as bridges are carried on decks over trenches, rail cuts and tunnel
approaches (e.g. 11th Street / Jackson Avenue over the Queens-Midtown Tunnel
approach in Long Island City). There the DEM shows the trench floor metres
below the real street. Lidar measures the actual road surface.

Rules per station along a road centreline (points within ``radius_m``):
1. class 2 (ground) present -> median of class 2.
2. else class 17 (deck) present -> accepted only if it is continuous with the
   road's class-2 surface nearby (within ``max_jump_m`` of the median class-2
   height within ``ref_window_m`` along the road). This rejects the deck of an
   overpass ABOVE the road. Without a class-2 reference, accepted if within
   ``max_jump_m`` of the line between the segment's end heights, else rejected.
3. else no lidar -> caller falls back to the DEM (or interpolation).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


class LidarSurface:
    def __init__(self, path: Path, radius_m: float = 1.0, max_jump_m: float = 1.5, ref_window_m: float = 30.0):
        from scipy.spatial import cKDTree

        d = np.load(path)
        self.origin = d["origin"]
        self.xy = np.column_stack([d["x"], d["y"]]).astype(np.float64)
        self.z = d["z"].astype(np.float64)
        self.c = d["c"]
        self.tree = cKDTree(self.xy)
        self.radius = radius_m
        self.max_jump = max_jump_m
        self.ref_window = ref_window_m
        meta = Path(str(path).replace(".npz", ".source.json"))
        self.meta = json.loads(meta.read_text()) if meta.exists() else {}

    def _near(self, x, y, r):
        idx = self.tree.query_ball_point([x - self.origin[0], y - self.origin[1]], r)
        return np.asarray(idx, int)

    def station_values(self, xy_utm: np.ndarray):
        """Per station: (z_ground or nan, z_deck or nan)."""
        g = np.full(len(xy_utm), np.nan)
        dk = np.full(len(xy_utm), np.nan)
        for k, (x, y) in enumerate(xy_utm):
            idx = self._near(x, y, self.radius)
            if len(idx) == 0:
                continue
            c, z = self.c[idx], self.z[idx]
            if (c == 2).sum() >= 3:
                g[k] = np.median(z[c == 2])
            if (c == 17).sum() >= 3:
                dk[k] = np.median(z[c == 17])
        return g, dk

    def point_surface(self, x: float, y: float, r: float = 3.0, ref_r: float = 30.0):
        """Native road-surface height at a junction: class 2 near the point; else class 17
        if continuous with class-2 ground within ``ref_r`` (a junction on a deck);
        else None (caller falls back to the DEM)."""
        idx = self._near(x, y, r)
        if len(idx) == 0:
            return None
        c, z = self.c[idx], self.z[idx]
        if (c == 2).sum() >= 3:
            return float(np.median(z[c == 2]))
        if (c == 17).sum() >= 3:
            zd = float(np.median(z[c == 17]))
            ring = self._near(x, y, ref_r)
            g = self.z[ring][self.c[ring] == 2]
            if len(g) >= 10:
                # nearest-in-height class-2 cluster around the junction
                if np.min(np.abs(g - zd)) <= self.max_jump and abs(np.median(g[np.abs(g - zd) <= self.max_jump]) - zd) <= self.max_jump:
                    return zd
        return None


def choose_surface(s, g, dk, dem, ends=(None, None), max_jump=1.5, ref_window=30.0):
    """Per-station road surface (sim heights) from lidar ground ``g``, lidar deck ``dk``
    and DEM ``dem`` (nan = unavailable). Returns (z, source array)."""
    s = np.asarray(s, float)
    z = np.full(len(s), np.nan)
    src = np.full(len(s), "none", dtype=object)
    have_g = np.isfinite(g)
    z[have_g] = g[have_g]
    src[have_g] = "lidar_ground"
    for k in np.where(~have_g & np.isfinite(dk))[0]:
        win = np.abs(s - s[k]) <= ref_window
        ref = g[win & have_g]
        if len(ref) >= 3:
            ok = abs(dk[k] - np.median(ref)) <= max_jump
        elif ends[0] is not None and ends[1] is not None and s[-1] > 0:
            ok = abs(dk[k] - (ends[0] + (ends[1] - ends[0]) * s[k] / s[-1])) <= max_jump
        else:
            ok = False
        if ok:
            z[k], src[k] = dk[k], "lidar_deck"
        else:
            src[k] = "rejected_overhead"
    measured = np.isfinite(z)
    for k in np.where(~measured & np.isfinite(dem))[0]:
        win = np.abs(s - s[k]) <= ref_window
        ref = z[win & measured]
        if len(ref) == 0 or abs(dem[k] - np.median(ref)) <= max_jump:
            z[k], src[k] = dem[k], "dem"
        elif src[k] == "none":
            src[k] = "rejected_dem"
    return z, src


def dem_is_continuous(lidar: "LidarSurface", x: float, y: float, z_dem_native: float, r: float = 30.0) -> bool:
    """Accept a DEM height at a point only if it is within max_jump of the lidar ground
    (class 2) around it; with no class-2 ground nearby, accept."""
    ring = lidar._near(x, y, r)
    g = lidar.z[ring][lidar.c[ring] == 2]
    if len(g) < 10:
        return True
    return abs(z_dem_native - float(np.median(g))) <= lidar.max_jump
