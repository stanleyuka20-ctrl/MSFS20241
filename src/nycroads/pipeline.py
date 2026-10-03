"""Build orchestration: inventory selection -> profiles -> meshes -> checks -> tiles."""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, box

from . import config as C
from .checks import has_errors, run_checks
from .elevation import (VerticalReference, deck_node_heights, deck_profile, ground_profile,
                        junction_heights)
from .geo import ENUFrame, lonlat_to_utm, tile_center_utm, tile_id_for, utm_to_lonlat
from .gltf import _axis_matrix, orientation_marker, to_local, write_tile_gltf
from .meshgen import build_network
from .profile import grade_out
from .scenery import write_package_content


def select_segments(inv, bbox=None, ids=None) -> set[str]:
    """Segments intersecting bbox (s, w, n, e), expanded to whole bridge decks."""
    sel = set(ids or [])
    if bbox:
        s, w, n, e = bbox
        area = box(w, s, e, n)
        sel |= {sid for sid, seg in inv.segments.items() if LineString(seg.coords).intersects(area)}
    for d in inv.bridge_decks.values():
        if sel & set(d.segment_ids):
            sel |= set(d.segment_ids)
    return {i for i in sel if inv.segments[i].scope in ("in_scope", "secondary")}


def compute_profiles(inv, sel: set[str], dem, vref: VerticalReference, deck_controls: dict):
    """Order matters: ground junction heights -> ground segments that do not depend
    on a deck -> decks (continuing the approach grades) -> remaining ground segments."""
    node_h = junction_heights(inv, dem, vref)
    profiles, blockers = {}, {}
    deck_only_nodes = set()
    for d in inv.bridge_decks.values():
        for sid in d.segment_ids:
            sg = inv.segments[sid]
            deck_only_nodes |= {n for n in (sg.from_node, sg.to_node) if n not in node_h}
    pending = []
    for sid in sorted(sel):
        seg = inv.segments[sid]
        if seg.bridge:
            continue
        if seg.tunnel:
            blockers[sid] = "tunnel: separate feasibility task (docs/01-project-boundary.md#tunnels)"
            continue
        if {seg.from_node, seg.to_node} & deck_only_nodes:
            pending.append(sid)
        else:
            profiles[sid] = ground_profile(seg, dem, vref, node_h)

    grade_out_at = {}
    for sid, p in profiles.items():
        seg = inv.segments[sid]
        grade_out_at.setdefault(seg.from_node, []).append(grade_out(p.s, p.z_sim, True))
        grade_out_at.setdefault(seg.to_node, []).append(grade_out(p.s, p.z_sim, False))
    approach = {n: v[0] for n, v in grade_out_at.items() if len(v) == 1}  # unambiguous approaches only

    for d in inv.bridge_decks.values():
        if not (set(d.segment_ids) & sel):
            continue
        controls = deck_controls.get(d.id) or (deck_controls.get(d.crossing_id) if d.crossing_id else None) or []
        profs, reason = deck_profile(d, inv, controls, node_h, approach)
        if reason:
            blockers[d.id] = reason
            for sid in d.segment_ids:
                blockers[sid] = f"deck {d.id}: {reason}"
        else:
            profiles.update(profs)
    for n, h in deck_node_heights(profiles, inv).items():
        node_h.setdefault(n, h)
    for sid in pending:
        profiles[sid] = ground_profile(inv.segments[sid], dem, vref, node_h)
    return profiles, blockers


def build(inv, sel: set[str], dem, vref, deck_controls: dict, msfs_cfg: dict, out_dir: Path,
          package_name: str, package_root: Path | None = None, marker_at: tuple | None = None) -> dict:
    build_id = datetime.now(timezone.utc).strftime("B%Y%m%dT%H%M%SZ")
    profiles, blockers = compute_profiles(inv, sel, dem, vref, deck_controls)
    net = build_network(inv, profiles)
    issues = run_checks(inv, profiles, net, {k: v for k, v in blockers.items() if k in inv.bridge_decks})
    for sid, reason in blockers.items():
        if sid in inv.segments and inv.segments[sid].tunnel:
            issues.setdefault(sid, [])

    # group geometry by tile (segment midpoint / junction location)
    by_tile = defaultdict(list)
    for sid, meshes in net.meshes_by_segment.items():
        p = profiles[sid]
        mid = p.xy_utm[len(p.xy_utm) // 2]
        by_tile[tile_id_for(mid[0], mid[1], C.TILE_SIZE_M)].extend(meshes)
    jx = {j.id: j for j in inv.junctions.values()}
    for jid, pad in net.pads_by_junction.items():
        j = jx[jid]
        x, y = lonlat_to_utm(j.lon, j.lat)
        by_tile[tile_id_for(x, y, C.TILE_SIZE_M)].append(pad)
    if marker_at:
        lon, lat, z = marker_at
        x, y = lonlat_to_utm(lon, lat)
        by_tile[tile_id_for(x, y, C.TILE_SIZE_M)].append(orientation_marker(x, y, z))

    axis = _axis_matrix(msfs_cfg["axis_mapping"])
    models_dir = out_dir / "models"
    tiles, tile_stats = [], {}
    for tid, meshes in sorted(by_tile.items()):
        cx, cy = tile_center_utm(tid, C.TILE_SIZE_M)
        lon0, lat0 = utm_to_lonlat(cx, cy)
        z0 = math.floor(min(min(v[2] for v in m.vertices) for m in meshes if m.vertices))
        frame = ENUFrame(lon0, lat0, 0.0)
        local = to_local(meshes, frame, z0, axis)
        name = f"{package_name}-{tid}"
        path = models_dir / f"{name}.gltf"
        tile_stats[tid] = write_tile_gltf(path, local, msfs_cfg)
        tiles.append({"name": name, "gltf": path, "lat": lat0, "lon": lon0, "alt_m": float(z0), "heading": 0.0})

    if package_root:
        write_package_content(package_root, package_name, tiles)

    generated = set(net.meshes_by_segment) | set(net.pads_by_junction)
    starts = start_locations(inv, profiles, {k for k in net.meshes_by_segment
                                             if not has_errors(issues.get(k, []))})
    report = {
        "build_id": build_id,
        "package": package_name,
        "selected_segments": len(sel),
        "generated_segments": len(net.meshes_by_segment),
        "junction_pads": len(net.pads_by_junction),
        "blocked": {k: v for k, v in blockers.items()},
        "segments_with_errors": sorted(k for k, v in issues.items() if has_errors(v) and k in inv.segments),
        "issues": issues,
        "tiles": {t["name"]: {**tile_stats[t["name"].split(package_name + "-")[1]],
                              "lat": t["lat"], "lon": t["lon"], "alt_m": t["alt_m"]} for t in tiles},
        "vertical_reference": {"method": vref.method, "verified": vref.verified},
        "msfs_gltf_config_verified": bool(msfs_cfg.get("verified")),
        "start_locations": starts,
        "_generated": sorted(generated),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "build_report.json").write_text(json.dumps(report, indent=1, default=_np))
    (out_dir / "profiles.json").write_text(json.dumps(
        {sid: {"s": p.s.round(2).tolist(), "z_sim": p.z_sim.round(3).tolist(),
               "xy_utm": p.xy_utm.round(3).tolist(), "source": p.source} for sid, p in profiles.items()}))
    return report


def start_locations(inv, profiles, ok_ids: set[str]) -> list[dict]:
    """Candidate spawn points: middle of long, flat, error-free ground segments."""
    out = []
    for sid in sorted(ok_ids):
        seg, p = inv.segments[sid], profiles[sid]
        if seg.bridge or seg.length_m < 40 or seg.highway.startswith("motorway"):
            continue
        k = len(p.s) // 2
        g = np.diff(p.z_sim) / np.maximum(np.diff(p.s), 1e-6)
        if abs(g[min(k, len(g) - 1)]) > 0.03:
            continue
        x, y = p.xy_utm[k]
        dx, dy = p.xy_utm[min(k + 1, len(p.s) - 1)] - p.xy_utm[max(k - 1, 0)]
        hdg = math.degrees(math.atan2(dx, dy)) % 360
        if seg.oneway == "backward":
            hdg = (hdg + 180) % 360
        # keep right: offset a quarter width to the right of travel
        r = seg.width_m / 4 if seg.oneway == "both" else 0.0
        nx_, ny_ = math.cos(math.radians(hdg)), -math.sin(math.radians(hdg))
        lon, lat = utm_to_lonlat(x + nx_ * r, y + ny_ * r)
        out.append({"id": f"START-{sid}", "segment": sid, "lat": round(lat, 7), "lon": round(lon, 7),
                    "surface_alt_m": round(float(p.z_sim[k]), 2), "heading_deg": round(hdg, 1),
                    "name": seg.name})
    return out


def _np(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)
