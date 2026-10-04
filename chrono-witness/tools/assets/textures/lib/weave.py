"""Plain-weave fabric height/coverage generator (periodic)."""
from __future__ import annotations

import numpy as np

from .core import N, TAU, blur, spectral


def _thread_jitter(rng, count, n, amp_px, smooth=40.0):
    """Per-thread smooth lateral wander, periodic along the thread (count x n)."""
    w = rng.standard_normal((count, n)).astype(np.float32)
    k = np.fft.fftfreq(n) * n
    H = np.exp(-0.5 * (k / (n / smooth)) ** 2)
    w = np.real(np.fft.ifft(np.fft.fft(w, axis=1) * H[None, :], axis=1))
    w /= w.std() + 1e-9
    return (w * amp_px).astype(np.float32)


def plain_weave(rng, n_warp, n_weft, n=N, width=0.8, crimp=0.35, wander=0.35, slub=0.25, twist=0.3,
                hair=0.15):
    """Plain weave. Warp threads run along y (vertical), weft along x.
    Returns dict(h [units of thread pitch], cover 0..1, is_warp bool, thread_id, along)."""
    pw = n / n_warp
    pf = n / n_weft
    X, Y = np.meshgrid(np.arange(n, dtype=np.float32) + 0.5, np.arange(n, dtype=np.float32) + 0.5)
    best_h = np.full((n, n), -1.0, np.float32)
    cover = np.zeros((n, n), np.float32)
    is_warp = np.zeros((n, n), bool)
    tid = np.zeros((n, n), np.int32)
    yi = np.arange(n)
    for kind in ("warp", "weft"):
        if kind == "warp":
            count, pitch, other, P_across, P_along = n_warp, pw, pf, X, Y
        else:
            count, pitch, other, P_across, P_along = n_weft, pf, pw, Y, X
        jit = _thread_jitter(rng, count, n, wander * pitch)
        thick = 1.0 + slub * _thread_jitter(rng, count, n, 1.0, smooth=n / 12)
        base_w = np.exp(rng.normal(0, 0.12, count)).astype(np.float32)
        tphase = rng.uniform(0, TAU, count).astype(np.float32)
        a_idx = P_along.astype(int) % n
        i0 = np.floor(P_across / pitch - 0.5).astype(int)
        for off in (0, 1, -1, 2):
            i = i0 + off
            im = i % count
            c = (i + 0.5) * pitch + jit[im, a_idx]
            half = 0.5 * pitch * width * base_w[im] * thick[im, a_idx]
            d = P_across - c
            prof = np.sqrt(np.clip(1.0 - (d / np.maximum(half, 0.3)) ** 2, 0, 1))
            # crimp: thread goes over/under the crossing threads
            sgn = 1.0 if kind == "warp" else -1.0
            z = sgn * crimp * np.cos(np.pi * (P_along / other - 0.5) + np.pi * i)
            tw = twist * 0.15 * np.sin(TAU * ((P_along + d * 1.5) / (pitch * 0.9)) + tphase[im])
            hh = z + prof * 0.5 + tw * prof
            inside = (np.abs(d) < half) & (hh > best_h)
            best_h = np.where(inside, hh, best_h)
            cover = np.maximum(cover, np.clip((half - np.abs(d)) + 0.5, 0, 1))
            is_warp = np.where(inside, kind == "warp", is_warp)
            tid = np.where(inside, im + (0 if kind == "warp" else 100000), tid)
    gap = best_h < -0.9
    best_h = np.where(gap, -0.7, best_h)
    if hair > 0:
        fz = spectral(rng, beta=1.2, fmin=n // 8, n=n)
        best_h = best_h + hair * 0.15 * fz
    return dict(h=best_h.astype(np.float32), cover=np.clip(cover, 0, 1), is_warp=is_warp, gap=gap, tid=tid)
