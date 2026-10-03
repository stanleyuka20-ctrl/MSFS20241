"""Offline geometry previews of a build (matplotlib, optional).

These are renders of the GENERATED geometry for review. They are not simulator
screenshots and are never evidence that a road is drivable.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def render(inv, profiles, surfaces, out_dir: Path, deck_controls: dict | None = None,
           lidar=None, focus: list[str] | None = None) -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    written = []

    # 1. plan view coloured by surface group
    fig, ax = plt.subplots(figsize=(12, 12))
    cmap = plt.get_cmap("tab10")
    keys = sorted(surfaces.footprints, key=str)
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MPath
    for i, k in enumerate(keys):
        fp = surfaces.footprints[k]
        col = "#555555" if k == ("ground", 0) else cmap(i % 10)
        first = True
        for poly in getattr(fp, "geoms", [fp]):
            if not hasattr(poly, "exterior"):
                continue
            verts, codes = [], []
            for ring in [poly.exterior, *poly.interiors]:     # holes drawn as holes
                cs = np.asarray(ring.coords)
                verts += cs.tolist()
                codes += [MPath.MOVETO] + [MPath.LINETO] * (len(cs) - 2) + [MPath.CLOSEPOLY]
            ax.add_patch(PathPatch(MPath(verts, codes), facecolor=col, edgecolor="none", alpha=0.85,
                                   label=":".join(map(str, k))[:40] if first else None))
            first = False
    for sid, p in profiles.items():
        ax.plot(p.xy_utm[:, 0], p.xy_utm[:, 1], color="white", lw=0.3)
    ax.autoscale()
    ax.set_aspect("equal")
    ax.set_title("Generated road surfaces by surface group (UTM 18N, m)")
    ax.legend(loc="upper left", fontsize=7)
    p = out_dir / "plan_surface_groups.png"
    fig.savefig(p, dpi=110, bbox_inches="tight")
    plt.close(fig)
    written.append(p)

    # 2. profiles of selected segments / decks
    for name in focus or []:
        sids = [s for s in profiles if inv.segments[s].name == name]
        if not sids:
            continue
        fig, ax = plt.subplots(figsize=(12, 4))
        for sid in sids:
            pr = profiles[sid]
            seg = inv.segments[sid]
            # project along the dominant axis for a readable x-axis
            ax.plot(pr.xy_utm[:, 1], pr.z_sim, "-", lw=2 if seg.bridge else 1.2,
                    color="tab:red" if seg.bridge else "tab:blue")
            if lidar is not None:
                g, dk = lidar.station_values(pr.xy_utm)
                ax.plot(pr.xy_utm[:, 1], g, ".", ms=2, color="tab:green")
                ax.plot(pr.xy_utm[:, 1], dk, ".", ms=2, color="tab:orange")
        if deck_controls:
            for key, cs in deck_controls.items():
                d = inv.bridge_decks.get(key)
                if d and inv.segments[d.segment_ids[0]].name == name:
                    from .geo import lonlat_to_utm
                    xy = np.array([lonlat_to_utm(c.lon, c.lat) for c in cs])
                    ax.plot(xy[:, 1], [c.z_sim_m for c in cs], "k^", ms=4)
        ax.set_xlabel("northing (m)")
        ax.set_ylabel("height (m, current sim reference)")
        ax.set_title(f"{name}: profile (blue ground / red deck), lidar ground (green), lidar deck (orange), "
                     f"deck controls (black)")
        p = out_dir / f"profile_{name.replace(' ', '_')}.png"
        fig.savefig(p, dpi=110, bbox_inches="tight")
        plt.close(fig)
        written.append(p)
    return written


def summary_json(out_dir: Path, report: dict) -> Path:
    p = out_dir / "preview_index.json"
    p.write_text(json.dumps({"build_id": report["build_id"], "note": "geometry renders, not simulator screenshots"}))
    return p
