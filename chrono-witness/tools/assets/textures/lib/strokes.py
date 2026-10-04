"""Supersampled polygon stroke rasteriser (blades, roots, twigs, stitches) with wrap-around."""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw


class StrokeCanvas:
    """Several float channels drawn with the painter's algorithm at `ss`x resolution."""

    def __init__(self, n, channels, ss=2):
        self.n, self.ss = n, ss
        self.imgs = {k: Image.new("F", (n * ss, n * ss), float(v)) for k, v in channels.items()}
        self.draws = {k: ImageDraw.Draw(im) for k, im in self.imgs.items()}

    def polygon(self, pts, values):
        """pts in final-pixel units (Nx2, x,y). values: {channel: float}. Wraps around edges."""
        n, ss = self.n, self.ss
        pts = np.asarray(pts, np.float64)
        lo, hi = pts.min(0), pts.max(0)
        for ox in (-n, 0, n):
            if hi[0] + ox < -2 or lo[0] + ox > n + 2:
                continue
            for oy in (-n, 0, n):
                if hi[1] + oy < -2 or lo[1] + oy > n + 2:
                    continue
                q = [((x + ox) * ss, (y + oy) * ss) for x, y in pts]
                for k, v in values.items():
                    self.draws[k].polygon(q, fill=float(v))

    def ribbon(self, centre, widths, values_per_seg):
        """Tapered ribbon along a centreline. widths per point (final px).
        values_per_seg: function(i, t) -> {channel: value} for segment i (t in 0..1)."""
        c = np.asarray(centre, np.float64)
        d = np.gradient(c, axis=0)
        d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
        nrm = np.stack([-d[:, 1], d[:, 0]], 1)
        w = np.asarray(widths, np.float64)[:, None] * 0.5
        left, right = c + nrm * w, c - nrm * w
        m = len(c)
        for i in range(m - 1):
            quad = [left[i], left[i + 1], right[i + 1], right[i]]
            self.polygon(quad, values_per_seg(i, i / max(m - 2, 1)))

    def get(self, k):
        a = np.asarray(self.imgs[k], np.float32)
        if self.ss == 1:
            return a
        return cv2.resize(a, (self.n, self.n), interpolation=cv2.INTER_AREA)


def bezier(p0, p1, p2, m=10):
    t = np.linspace(0, 1, m)[:, None]
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t ** 2 * p2


def crack_lines(rng, n, count, length_px=(60, 300), width_px=(0.6, 1.6), wobble=0.25, branch=0.4, ss=2,
                angle=None, angle_jitter=None):
    """Random-walk crack polylines with occasional branches (wrapping). Returns coverage 0..1."""
    sc = StrokeCanvas(n, {"a": 0.0}, ss=ss)

    def walk(p, a, L, w0, depth):
        m = max(3, int(L / 4))
        pts = [p]
        for i in range(m - 1):
            a += rng.normal(0, wobble)
            pts.append(pts[-1] + 4.0 * np.array([np.cos(a), np.sin(a)]))
            if depth < 2 and rng.random() < branch / m:
                walk(pts[-1], a + rng.choice([-1, 1]) * rng.uniform(0.5, 1.2), L * rng.uniform(0.2, 0.5),
                     w0 * 0.6, depth + 1)
        pts = np.array(pts)
        widths = w0 * np.clip(np.sin(np.pi * np.linspace(0.05, 1.0, m)) ** 0.4, 0.3, 1)
        sc.ribbon(pts, widths, lambda i, t: {"a": 1.0})

    for k in range(count):
        p = rng.uniform(0, n, 2)
        a = rng.uniform(0, 2 * np.pi) if angle is None else angle + rng.normal(0, angle_jitter or 0.3)
        walk(p, a, rng.uniform(*length_px), rng.uniform(*width_px), 0)
    return np.clip(sc.get("a"), 0, 1)
