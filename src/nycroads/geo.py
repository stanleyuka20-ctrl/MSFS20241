"""Coordinate handling.

* Planar topology work (buffers, intersections, lengths) uses UTM zone 18N (EPSG:32618).
* Model geometry uses an exact local East-North-Up frame per tile origin, computed
  through ECEF, so models do not inherit UTM scale distortion (up to ~0.04 % here).
* Heights are carried as explicit (value, datum) pairs; see elevation.py.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from pyproj import Transformer

UTM18N = "EPSG:32618"
WGS84_2D = "EPSG:4326"
WGS84_3D = "EPSG:4979"
ECEF = "EPSG:4978"


@lru_cache(maxsize=None)
def _tr(src: str, dst: str) -> Transformer:
    return Transformer.from_crs(src, dst, always_xy=True)


def lonlat_to_utm(lon, lat):
    return _tr(WGS84_2D, UTM18N).transform(lon, lat)


def utm_to_lonlat(x, y):
    return _tr(UTM18N, WGS84_2D).transform(x, y)


@dataclass(frozen=True)
class ENUFrame:
    """Local tangent plane anchored at (lon0, lat0, h0); h0 is ellipsoidal height."""

    lon0: float
    lat0: float
    h0: float = 0.0

    @property
    def _origin_ecef(self):
        return np.array(_tr(WGS84_3D, ECEF).transform(self.lon0, self.lat0, self.h0))

    @property
    def _rot(self):
        lam, phi = math.radians(self.lon0), math.radians(self.lat0)
        sl, cl, sp, cp = math.sin(lam), math.cos(lam), math.sin(phi), math.cos(phi)
        return np.array([
            [-sl, cl, 0.0],
            [-sp * cl, -sp * sl, cp],
            [cp * cl, cp * sl, sp],
        ])

    def from_geodetic(self, lon, lat, h):
        """lon/lat (deg), h (m, ellipsoidal) -> (e, n, u) arrays in metres."""
        x, y, z = _tr(WGS84_3D, ECEF).transform(np.asarray(lon, float), np.asarray(lat, float),
                                                np.asarray(h, float))
        d = np.vstack([np.atleast_1d(x), np.atleast_1d(y), np.atleast_1d(z)]) - self._origin_ecef[:, None]
        e, n, u = self._rot @ d
        return e, n, u

    def to_geodetic(self, e, n, u):
        d = self._rot.T @ np.vstack([np.atleast_1d(e), np.atleast_1d(n), np.atleast_1d(u)])
        x, y, z = d + self._origin_ecef[:, None]
        return _tr(ECEF, WGS84_3D).transform(x, y, z)


def haversine_m(lon1, lat1, lon2, lat2) -> float:
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def tile_id_for(x_utm: float, y_utm: float, size: float) -> str:
    """Stable tile key from UTM coordinates, e.g. 'T18N-0586-4510' for 1 km tiles."""
    return f"T18N-{int(x_utm // size):04d}-{int(y_utm // size):04d}"


def tile_center_utm(tile_id: str, size: float):
    _, ix, iy = tile_id.split("-")
    return (int(ix) + 0.5) * size, (int(iy) + 0.5) * size
