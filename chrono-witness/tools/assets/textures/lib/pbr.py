"""PBR map construction + output (albedo / OpenGL normal / ORM JPEGs)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageFile

ImageFile.MAXBLOCK = 1 << 25

from .core import blur, lin_to_srgb, luminance

JPEG_QUALITY = 88          # albedo
JPEG_QUALITY_DATA = 85     # normal + ORM (size budget ~1 MB per set)


@dataclass
class Material:
    name: str
    tile_m: float
    albedo: np.ndarray            # HxWx3 linear
    height: np.ndarray            # HxW metres
    rough: np.ndarray             # HxW 0..1
    metal: np.ndarray | None = None
    ao_extra: np.ndarray | None = None   # multiplied into AO
    notes: str = ""
    normal_strength: float = 1.0
    ao_radii_m: tuple = (0.004, 0.015, 0.05)
    ao_strength: float = 1.0
    normal_override: np.ndarray | None = None  # HxWx3 unit vectors (if given)
    extra: dict = field(default_factory=dict)


def height_to_normal(h_m, tile_m, strength=1.0, pre_blur=0.0):
    n = h_m.shape[0]
    px = tile_m / n
    h = blur(h_m, pre_blur) if pre_blur > 0 else h_m
    dhdx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / (2 * px)
    dhdr = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) / (2 * px)
    nx = -dhdx * strength
    ny = dhdr * strength          # OpenGL: +Y (green) points "up" the texture (towards row 0)
    nz = np.ones_like(nx)
    L = np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.stack([nx / L, ny / L, nz / L], -1).astype(np.float32)


def ao_from_height(h_m, tile_m, radii_m=(0.004, 0.015, 0.05), strength=1.0):
    n = h_m.shape[0]
    px = tile_m / n
    occ = np.zeros_like(h_m)
    for r in radii_m:
        s = max(r / px, 0.7)
        b = blur(h_m, s)
        occ += np.clip((b - h_m) / r, 0, None)
    occ /= len(radii_m)
    return np.clip(np.exp(-occ * 3.0 * strength), 0.0, 1.0).astype(np.float32)


def encode_normal(nrm):
    return np.clip(np.round((nrm * 0.5 + 0.5) * 255), 0, 255).astype(np.uint8)


def to8(a):
    return np.clip(np.round(a * 255), 0, 255).astype(np.uint8)


def finalize(m: Material):
    """Compute normal/AO and return dict of 8-bit images + stats."""
    nrm = m.normal_override if m.normal_override is not None else \
        height_to_normal(m.height, m.tile_m, m.normal_strength)
    ao = ao_from_height(m.height, m.tile_m, m.ao_radii_m, m.ao_strength)
    if m.ao_extra is not None:
        ao = ao * m.ao_extra
    ao = np.clip(ao, 0.05, 1.0)
    metal = m.metal if m.metal is not None else np.zeros_like(m.rough)
    alb = np.clip(m.albedo, 0.012, 0.88)
    alb8 = to8(lin_to_srgb(alb))
    orm8 = np.stack([to8(ao), to8(np.clip(m.rough, 0.02, 1.0)), to8(np.clip(metal, 0, 1))], -1)
    lum = luminance(alb)
    stats = dict(albedo_lum_p1=float(np.percentile(lum, 1)), albedo_lum_mean=float(lum.mean()),
                 albedo_lum_p99=float(np.percentile(lum, 99)),
                 rough_min=float(m.rough.min()), rough_mean=float(m.rough.mean()), rough_max=float(m.rough.max()),
                 metal_mean=float(metal.mean()), ao_mean=float(ao.mean()))
    return dict(albedo=alb8, normal=encode_normal(nrm), orm=orm8), stats


SET_BUDGET_BYTES = 1_100_000   # per set (albedo + normal + ORM); "about 1 MB"
_SAVE_ARGS = {"albedo": dict(quality=JPEG_QUALITY, subsampling="4:2:0"),
              "normal": dict(quality=JPEG_QUALITY_DATA, subsampling="4:4:4"),
              "orm": dict(quality=JPEG_QUALITY_DATA, subsampling="4:4:4")}


def _encode(arr, key):
    import io
    b = io.BytesIO()
    Image.fromarray(arr).save(b, "JPEG", optimize=True, **_SAVE_ARGS[key])
    return b.getvalue()


def _soften(arr, key, sigma):
    """Remove texel-level detail (the costliest part for JPEG) with a periodic Gaussian; normals are
    re-normalised so the map stays valid."""
    a = arr.astype(np.float32) / 255.0
    a = blur(a, sigma)
    if key == "normal":
        v = a * 2 - 1
        v /= np.linalg.norm(v, axis=-1, keepdims=True) + 1e-6
        a = v * 0.5 + 0.5
    return np.clip(np.round(a * 255), 0, 255).astype(np.uint8)


def save_set(m: Material, out_root: str, budget=SET_BUDGET_BYTES):
    imgs, stats = finalize(m)
    d = os.path.join(out_root, m.name)
    os.makedirs(d, exist_ok=True)
    data = {k: _encode(v, k) for k, v in imgs.items()}
    sigma = {k: 0.0 for k in imgs}
    caps = {"albedo": 0.8, "normal": 1.2, "orm": 1.4}
    # size budget: repeatedly soften the currently largest map (never beyond its cap)
    while sum(len(v) for v in data.values()) > budget:
        cand = [k for k in data if sigma[k] < caps[k]]
        if not cand:
            break
        k = max(cand, key=lambda q: len(data[q]) * (0.6 if q == "albedo" else 1.0))
        sigma[k] = min(caps[k], sigma[k] + 0.25 if sigma[k] else 0.45)
        data[k] = _encode(_soften(imgs[k], k, sigma[k]), k)
    for k, suffix in (("albedo", "albedo"), ("normal", "normal"), ("orm", "orm")):
        with open(os.path.join(d, f"{m.name}_{suffix}.jpg"), "wb") as f:
            f.write(data[k])
    stats["bytes"] = sum(len(v) for v in data.values())
    stats["soften"] = {k: round(v, 2) for k, v in sigma.items() if v}
    return stats


def write_manifest(entries: dict, out_root: str):
    path = os.path.join(out_root, "manifest.json")
    old = {}
    if os.path.exists(path):
        with open(path) as f:
            old = json.load(f)
    old.update(entries)
    with open(path, "w") as f:
        json.dump(dict(sorted(old.items())), f, indent=2)
        f.write("\n")
