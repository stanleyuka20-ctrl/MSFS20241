"""Vertical road profiles: despiking, smoothing with anchors, and checks.

The goal is to remove *artefacts* (DEM spikes, photogrammetry pits, tile steps)
while keeping *real* hills. Two tools do that:

1. A Hampel filter removes isolated outliers relative to a rolling median.
2. A Whittaker smoother (penalised least squares on second differences) gives a
   smooth curve; anchors (junction / abutment / deck control heights) are held
   with very large weights so neighbouring segments meet exactly.
"""
from __future__ import annotations

import numpy as np

from . import config as C


def stations(line_utm, spacing: float = C.STATION_SPACING_M):
    """Distances along a shapely LineString and the points at those distances.

    Always includes both ends and every original vertex, so corners are kept.
    """
    L = line_utm.length
    s = set(np.arange(0.0, L, spacing).tolist()) | {L}
    acc = 0.0
    cs = list(line_utm.coords)
    for (x0, y0), (x1, y1) in zip(cs, cs[1:]):
        acc += float(np.hypot(x1 - x0, y1 - y0))
        s.add(min(acc, L))
    # merge stations closer than 0.25 m (duplicate vertices); both ends are kept exactly
    kept = [0.0]
    for v in sorted(s)[1:]:
        if v - kept[-1] > 0.25:
            kept.append(v)
    if L - kept[-1] <= 0.25 and len(kept) > 1:
        kept[-1] = L
    elif kept[-1] != L:
        kept.append(L)
    s = np.array(kept)
    pts = [line_utm.interpolate(d) for d in s]
    return s, np.array([[p.x, p.y] for p in pts])


def hampel(z: np.ndarray, half_window: int = 3, n_sigma: float = 3.0, min_dev: float = 0.3):
    """Replace outliers with the local median. Returns (filtered, mask_of_replaced)."""
    z = np.asarray(z, float).copy()
    n = len(z)
    out = np.zeros(n, bool)
    if n < 3:
        return z, out
    orig = z.copy()
    for i in range(n):
        lo, hi = max(0, i - half_window), min(n, i + half_window + 1)
        win = orig[lo:hi]
        med = np.median(win)
        mad = 1.4826 * np.median(np.abs(win - med))
        if abs(orig[i] - med) > max(n_sigma * mad, min_dev):
            z[i] = med
            out[i] = True
    return z, out


def whittaker(s: np.ndarray, z: np.ndarray, weights: np.ndarray, lam: float,
              diff_rows: list[tuple[int, int, float]] | None = None) -> np.ndarray:
    """Penalised least squares with a second-difference penalty on uneven spacing.

    ``diff_rows``: hard-ish constraints z[j] - z[i] = target (used for grade continuity).
    """
    n = len(s)
    if n < 3:
        z = np.asarray(z, float).copy()
        if n == 2 and diff_rows and weights[0] > weights[1]:
            i, j, t = diff_rows[0]
            z[1] = z[0] + (t if (i, j) == (0, 1) else -t)
        return z
    D = np.zeros((n - 2, n))
    for i in range(n - 2):
        h0, h1 = s[i + 1] - s[i], s[i + 2] - s[i + 1]
        # second derivative estimate (per m^2) scaled by spacing so lam is
        # roughly independent of station density
        D[i, i] = 2 / (h0 * (h0 + h1))
        D[i, i + 1] = -2 / (h0 * h1)
        D[i, i + 2] = 2 / (h1 * (h0 + h1))
        D[i] *= np.sqrt((h0 + h1) / 2)
    W = np.diag(weights)
    A = W + lam * D.T @ D
    b = W @ np.nan_to_num(z)
    for i, j, t in diff_rows or []:
        c = np.zeros(n)
        c[i], c[j] = -1.0, 1.0
        A += SLOPE_WEIGHT * np.outer(c, c)
        b += SLOPE_WEIGHT * c * t
    return np.linalg.solve(A, b)


ANCHOR_WEIGHT = 1e8
SLOPE_WEIGHT = 1e6


def smooth_profile(s, z_raw, anchors: dict[int, float] | None = None, lam: float = 400.0,
                   data_mask: np.ndarray | None = None, end_grades: dict[str, float] | None = None):
    """Smooth a raw elevation profile.

    ``anchors``: station index -> fixed height (junctions, abutments, deck controls).
    ``data_mask``: False where raw samples must be ignored (e.g. bridge spans,
    where the DEM shows water / the street below, never the deck).
    ``end_grades``: {"start"|"end": grade in the direction of increasing s} to make
    the profile continue the grade of the adjoining segment (no kink at joints).
    Returns (z_smooth, info).
    """
    z_raw = np.asarray(z_raw, float)
    mask = np.ones(len(s), bool) if data_mask is None else np.asarray(data_mask, bool).copy()
    mask &= np.isfinite(z_raw)
    z_f = z_raw.copy()
    replaced = np.zeros(len(s), bool)
    if mask.sum() >= 3:
        z_f[mask], replaced[mask] = hampel(z_raw[mask])
    w = mask.astype(float)
    z_in = np.where(mask, z_f, 0.0)
    for i, h in (anchors or {}).items():
        w[i] = ANCHOR_WEIGHT
        z_in[i] = h
    if w.sum() == 0:
        raise ValueError("profile has neither data nor anchors")
    rows = []
    s_arr = np.asarray(s, float)
    n = len(s_arr)
    if end_grades and n >= 2:
        if "start" in end_grades:
            rows.append((0, 1, end_grades["start"] * (s_arr[1] - s_arr[0])))
        if "end" in end_grades:
            rows.append((n - 2, n - 1, end_grades["end"] * (s_arr[-1] - s_arr[-2])))
    z = whittaker(s_arr, z_in, w, lam, rows)
    return z, {"despiked": int(replaced.sum()), "ignored": int((~mask).sum())}


def grade_issues(s, z, highway: str) -> list[dict]:
    """Flag grades and grade changes beyond review thresholds."""
    s, z = np.asarray(s, float), np.asarray(z, float)
    issues = []
    if len(s) < 2:
        return issues
    g = np.diff(z) / np.maximum(np.diff(s), 1e-6)
    gmax = C.MAX_GRADE.get(highway, C.MAX_GRADE["default"])
    for i in np.where(np.abs(g) > gmax)[0]:
        issues.append({"type": "grade", "station_m": float(s[i]), "value": round(float(g[i]), 4),
                       "limit": gmax})
    if len(g) >= 2:
        dg = np.abs(np.diff(g))
        for i in np.where(dg > C.MAX_GRADE_CHANGE_PER_STATION)[0]:
            issues.append({"type": "grade_change", "station_m": float(s[i + 1]),
                           "value": round(float(dg[i]), 4), "limit": C.MAX_GRADE_CHANGE_PER_STATION})
    return issues


def grade_out(s, z, at_start: bool) -> float:
    """Grade measured moving AWAY from the given end, averaged over ~10 m."""
    s, z = np.asarray(s, float), np.asarray(z, float)
    if len(s) < 2:
        return 0.0
    if at_start:
        k = min(int(np.searchsorted(s, s[0] + 10.0)), len(s) - 1)
        return float((z[k] - z[0]) / max(s[k] - s[0], 1e-6))
    k = max(int(np.searchsorted(s, s[-1] - 10.0)) - 1, 0)
    return float((z[k] - z[-1]) / max(s[-1] - s[k], 1e-6))
