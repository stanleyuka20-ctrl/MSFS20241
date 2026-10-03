"""Minimal reader for Entwine Point Tile (EPT) lidar datasets over HTTP.

Used for the USGS 3DEP point clouds published at
https://usgs-lidar-public.s3.amazonaws.com/<dataset>/ (public domain), where
the horizontal CRS is EPSG:3857. Only the octree nodes whose 2D bounds
intersect the query box are downloaded (all depths, i.e. full resolution).
"""
from __future__ import annotations

import io
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests

USGS_EPT = "https://usgs-lidar-public.s3.amazonaws.com"


class EPT:
    def __init__(self, dataset: str, base: str = USGS_EPT, cache: Path | None = None):
        self.url = f"{base}/{dataset}"
        self.meta = requests.get(f"{self.url}/ept.json", timeout=60).json()
        self.bounds = np.array(self.meta["bounds"], float)  # cube: xmin ymin zmin xmax ymax zmax
        self.cache = cache
        if cache:
            cache.mkdir(parents=True, exist_ok=True)

    def _hier(self, key: str) -> dict:
        return requests.get(f"{self.url}/ept-hierarchy/{key}.json", timeout=60).json()

    def _node_bounds(self, key: str):
        d, x, y, z = map(int, key.split("-"))
        size = (self.bounds[3:] - self.bounds[:3]) / (2 ** d)
        lo = self.bounds[:3] + np.array([x, y, z]) * size
        return lo, lo + size

    def nodes(self, box2d) -> list[str]:
        """Keys of non-empty nodes intersecting (xmin, ymin, xmax, ymax) in the EPT CRS."""
        xmin, ymin, xmax, ymax = box2d
        out = []

        def hit(key):
            lo, hi = self._node_bounds(key)
            return lo[0] < xmax and hi[0] > xmin and lo[1] < ymax and hi[1] > ymin

        def walk(h: dict, key: str):
            if key not in h or not hit(key):
                return
            n = h[key]
            if n == -1:
                h = {**h, **self._hier(key)}
                n = h[key]
            if n > 0:
                out.append(key)
            d, x, y, z = map(int, key.split("-"))
            for dx in (0, 1):
                for dy in (0, 1):
                    for dz in (0, 1):
                        walk(h, f"{d + 1}-{2 * x + dx}-{2 * y + dy}-{2 * z + dz}")

        walk(self._hier("0-0-0-0"), "0-0-0-0")
        return out

    def _read(self, key: str) -> bytes:
        if self.cache and (self.cache / f"{key}.laz").exists():
            return (self.cache / f"{key}.laz").read_bytes()
        b = None
        for attempt in range(5):
            try:
                r = requests.get(f"{self.url}/ept-data/{key}.laz", timeout=300)
                r.raise_for_status()
                if "Content-Length" in r.headers and len(r.content) != int(r.headers["Content-Length"]):
                    raise IOError("truncated transfer")
                b = r.content
                break
            except (requests.RequestException, IOError):
                if attempt == 4:
                    raise
                time.sleep(2 ** (attempt + 1))
        if self.cache:
            (self.cache / f"{key}.laz").write_bytes(b)
        return b

    def query(self, box2d, fields=("classification", "return_number", "number_of_returns")):
        """Points inside box2d: dict of arrays x, y, z (+ fields)."""
        import laspy

        keys = self.nodes(box2d)
        xmin, ymin, xmax, ymax = box2d
        parts = []

        def load(k):
            las = laspy.read(io.BytesIO(self._read(k)))
            x, y = np.asarray(las.x), np.asarray(las.y)
            m = (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax)
            d = {"x": x[m], "y": y[m], "z": np.asarray(las.z)[m]}
            for f in fields:
                d[f] = np.asarray(las[f])[m]
            return d

        with ThreadPoolExecutor(8) as ex:
            parts = list(ex.map(load, keys))
        out = {k: np.concatenate([p[k] for p in parts]) if parts else np.zeros(0) for k in ("x", "y", "z", *fields)}
        out["_nodes"] = keys
        return out


def save_points(path: Path, pts: dict, meta: dict):
    np.savez_compressed(path, **{k: v for k, v in pts.items() if not k.startswith("_")})
    Path(str(path) + ".source.json").write_text(json.dumps(meta, indent=1))
