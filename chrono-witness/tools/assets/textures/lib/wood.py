"""Periodic wood-grain fields (grain runs along x / U)."""
from __future__ import annotations

import numpy as np

from .core import N, TAU, blur, smoothstep, spectral, uv


def periodic_grain(rng, n=N, ring_px=9.0, wander=60.0, knots=4, knot_r=(5, 14), stretch=12.0,
                   ring_var=0.45, latewood=0.3, figure=1.0):
    """Returns dict with:
      late   0..1 latewood (dark, hard) intensity
      ring   continuous ring coordinate
      knot   0..1 knot mask, knot_rings 0..1 ring pattern inside knots
      fibre  zero-mean fine fibre noise (stretched along x)
    Periodic in both axes."""
    X, Y = np.meshgrid(np.arange(n, dtype=np.float32), np.arange(n, dtype=np.float32))
    W = spectral(rng, beta=3.6, fmin=1, fmax=10, stretch=(stretch, 1.0)) * wander * figure
    W += spectral(rng, beta=3.0, fmin=3, fmax=40, stretch=(stretch * 1.5, 1.0)) * wander * 0.06
    W += spectral(rng, beta=2.0, fmin=20, fmax=160, stretch=(stretch * 3, 1.0)) * 0.6
    coord = Y + W
    knot_mask = np.zeros((n, n), np.float32)
    knot_rings = np.zeros((n, n), np.float32)
    for _ in range(knots):
        kx, ky = rng.uniform(0, n, 2)
        kr = rng.uniform(*knot_r)
        dx = (X - kx + n / 2) % n - n / 2
        dy = (Y - ky + n / 2) % n - n / 2
        d = np.sqrt((dx / 2.4) ** 2 + dy ** 2)
        infl = np.exp(-(d / (kr * 2.6)) ** 2)
        coord = coord + np.tanh(dy / (kr * 0.8)) * infl * kr * 2.2
        dk = np.sqrt((dx / rng.uniform(1.0, 1.5)) ** 2 + dy ** 2)
        km = smoothstep(kr, kr * 0.75, dk)
        knot_mask = np.maximum(knot_mask, km)
        kring = 0.5 + 0.5 * np.cos(TAU * dk / max(2.0, kr * 0.22))
        knot_rings = np.maximum(knot_rings, km * kring)
    # irregular ring widths, exactly periodic over n pixels
    nr = max(4, int(round(n / ring_px)))
    widths = np.exp(rng.normal(0, ring_var, nr))
    widths = widths / widths.sum() * n
    bounds = np.concatenate([[0.0], np.cumsum(widths)])
    cm = np.mod(coord, n)
    idx = np.searchsorted(bounds, cm, side="right") - 1
    idx = np.clip(idx, 0, nr - 1)
    frac = (cm - bounds[idx]) / widths[idx]
    frac = frac + blur(rng.standard_normal((n, n)).astype(np.float32), 10, 0.8) * 0.02
    lw = latewood
    # earlywood darkens gradually into latewood, then an abrupt change to the next year's earlywood
    late = smoothstep(1.0 - lw - 0.35, 1.0 - lw * 0.3, frac) ** 1.5 * (1.0 - smoothstep(0.965, 0.995, frac))
    late = late * np.exp(rng.normal(0, 0.25, nr))[idx]  # ring-to-ring contrast variation
    fibre = spectral(rng, beta=1.6, fmin=20, stretch=(25.0, 1.0))
    return dict(late=np.clip(late, 0, 1.5).astype(np.float32), ring=(idx + frac).astype(np.float32),
                knot=knot_mask, knot_rings=knot_rings.astype(np.float32), fibre=fibre)


def board_bands(n, count, gap_px, rng=None, jitter=0.0):
    """Horizontal boards: returns (board_id, v_in_board 0..1, dist_to_edge_px, edges array)."""
    edges = np.round(np.linspace(0, n, count + 1)).astype(int)
    if rng is not None and jitter > 0:
        e = edges.astype(np.float64)
        e[1:-1] += rng.uniform(-jitter, jitter, count - 1) * (n / count)
        edges = np.round(e).astype(int)
    rows = np.arange(n)
    bid = np.searchsorted(edges, rows, side="right") - 1
    bid = np.clip(bid, 0, count - 1)
    top = edges[bid]
    bot = edges[bid + 1]
    vin = (rows - top) / np.maximum(bot - top, 1)
    dist = np.minimum(rows - top, bot - 1 - rows).astype(np.float32)
    return bid[:, None], vin.astype(np.float32)[:, None], dist[:, None], edges
