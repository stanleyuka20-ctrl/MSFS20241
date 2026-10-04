#!/usr/bin/env python3
"""CHRONO WITNESS — environment texture generator (entry point).

Regenerates every PBR set in public/assets/textures/<set>/ plus effect textures in
public/assets/textures/fx/, updates public/assets/textures/manifest.json and (optionally)
renders Blender previews into docs/previews/textures/.

  python generate_all.py                     # everything
  python generate_all.py --only mud_wet,sandbag
  python generate_all.py --fx-only
  python generate_all.py --preview           # also render previews (needs bpy)
  python generate_all.py --check             # seam check of written textures

All randomness is seeded from the set name -> output is deterministic.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(PROJECT, "public", "assets", "textures")
PREVIEW_DIR = os.path.join(PROJECT, "docs", "previews", "textures")

from lib.pbr import save_set, write_manifest  # noqa: E402
from sets import REGISTRY  # noqa: E402


def check_seams(names):
    import numpy as np
    from PIL import Image
    worst = []
    for s in names:
        for suf in ("albedo", "normal", "orm"):
            a = np.asarray(Image.open(os.path.join(OUT, s, f"{s}_{suf}.jpg")), np.float32)
            # compare against other 8-px JPEG block boundaries (blocking inflates those diffs too)
            bx = np.arange(8, a.shape[1], 8)
            inner_x = np.abs(a[:, bx] - a[:, bx - 1]).mean()
            inner_y = np.abs(a[bx] - a[bx - 1]).mean()
            edge_x = np.abs(a[:, 0] - a[:, -1]).mean()
            edge_y = np.abs(a[0] - a[-1]).mean()
            r = max(edge_x / (inner_x + 1e-6), edge_y / (inner_y + 1e-6))
            worst.append((r, s, suf))
            flag = "  <-- SEAM?" if r > 1.6 else ""
            print(f"{s:20s} {suf:7s} edge/inner ratio x={edge_x / (inner_x + 1e-6):.2f} "
                  f"y={edge_y / (inner_y + 1e-6):.2f}{flag}")
    return worst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--fx-only", action="store_true")
    ap.add_argument("--no-fx", action="store_true")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    names = [n for n in REGISTRY] if not args.only else [n.strip() for n in args.only.split(",") if n.strip()]
    if args.fx_only:
        names = []
    manifest = {}
    for name in names:
        fn, tile_m, notes = REGISTRY[name]
        t = time.time()
        m = fn(name, tile_m)
        m.notes = notes
        stats = save_set(m, OUT)
        manifest[name] = {"tileMetres": tile_m, "notes": notes, "source": "procedural (own work)"}
        print(f"[{time.time() - t:5.1f}s] {name:18s} albedoLum p1={stats['albedo_lum_p1']:.3f} "
              f"mean={stats['albedo_lum_mean']:.3f} p99={stats['albedo_lum_p99']:.3f} "
              f"rough {stats['rough_min']:.2f}/{stats['rough_mean']:.2f}/{stats['rough_max']:.2f} "
              f"metal {stats['metal_mean']:.2f} ao {stats['ao_mean']:.2f} | {stats['bytes'] / 1e6:.2f} MB"
              f"{' soften ' + str(stats['soften']) if stats['soften'] else ''}", flush=True)
    if manifest:
        write_manifest(manifest, OUT)

    if not args.no_fx and (not args.only or args.fx_only):
        import fx
        fx.generate_all(os.path.join(OUT, "fx"))

    if args.check and names:
        check_seams(names)
    if args.preview and names:
        subprocess.check_call([sys.executable, os.path.join(HERE, "preview_blender.py"), OUT, PREVIEW_DIR] + names)


if __name__ == "__main__":
    main()
