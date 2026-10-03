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
from .surface import build_surfaces
from .profile import grade_out
from .scenery import write_package_content, write_project_files


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


def _controls_for(d, deck_controls):
    return deck_controls.get(d.id) or (deck_controls.get(d.crossing_id) if d.crossing_id else None) or []


def compute_profiles(inv, sel: set[str], dem, vref: VerticalReference, deck_controls: dict, lidar=None):
    """Profile order:

    1. Decks WITH measured controls, from the controls alone (their abutment
       heights are measured, so the DEM is not consulted there).
    2. Ground junction heights from the DEM, except those measured abutments.
    3. Ground segments; at measured abutments they ignore nearby DEM samples and
       continue the deck grade.
    4. Decks WITHOUT controls (short spans only): interpolated between land
       abutments, continuing the approach grades.
    """
    decks = [d for d in inv.bridge_decks.values() if set(d.segment_ids) & sel]
    measured = [d for d in decks if _controls_for(d, deck_controls)]
    unmeasured = [d for d in decks if not _controls_for(d, deck_controls)]
    profiles, blockers = {}, {}

    def block(d, reason):
        blockers[d.id] = reason
        for sid in d.segment_ids:
            blockers[sid] = f"deck {d.id}: {reason}"

    for d in measured:
        profs, reason = deck_profile(d, inv, _controls_for(d, deck_controls), {})
        if reason:
            block(d, reason)
        else:
            profiles.update(profs)
    deck_h = deck_node_heights(profiles, inv)
    deck_grade_out = {}
    for sid, p in profiles.items():
        seg = inv.segments[sid]
        # grade continuing OUT of the deck into the approach = -(grade into the deck from that node)
        deck_grade_out.setdefault(seg.from_node, -grade_out(p.s, p.z_sim, True))
        deck_grade_out.setdefault(seg.to_node, -grade_out(p.s, p.z_sim, False))
    measured_nodes = set(deck_h)

    node_h = junction_heights(inv, dem, vref, skip_nodes=measured_nodes, lidar=lidar)
    node_h.update(deck_h)

    deck_only_nodes = set()
    for d in unmeasured:
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
            ma = {n: deck_grade_out[n] for n in (seg.from_node, seg.to_node) if n in measured_nodes}
            profiles[sid] = ground_profile(seg, dem, vref, node_h, ma, lidar)

    # Nodes left without a height (DEM rejected, no lidar) but shared by several ground
    # segments: pin them to the mean of those segments' free end heights and re-solve,
    # so adjoining segments meet exactly.
    ends = defaultdict(list)
    for sid, p in profiles.items():
        seg = inv.segments[sid]
        if seg.bridge:
            continue
        ends[seg.from_node].append((sid, float(p.z_sim[0])))
        ends[seg.to_node].append((sid, float(p.z_sim[-1])))
    redo = set()
    for n, v in ends.items():
        if n not in node_h and len(v) >= 2:
            node_h[n] = float(np.mean([z for _, z in v]))
            redo |= {sid for sid, _ in v}
    for sid in sorted(redo):
        seg = inv.segments[sid]
        ma = {n: deck_grade_out[n] for n in (seg.from_node, seg.to_node) if n in measured_nodes}
        profiles[sid] = ground_profile(seg, dem, vref, node_h, ma, lidar)

    grade_out_at = {}
    for sid, p in profiles.items():
        seg = inv.segments[sid]
        if seg.bridge:
            continue
        grade_out_at.setdefault(seg.from_node, []).append(grade_out(p.s, p.z_sim, True))
        grade_out_at.setdefault(seg.to_node, []).append(grade_out(p.s, p.z_sim, False))
    approach = {n: v[0] for n, v in grade_out_at.items() if len(v) == 1}  # unambiguous approaches only
    new = {}
    for d in unmeasured:
        profs, reason = deck_profile(d, inv, [], node_h, approach)
        if reason:
            block(d, reason)
        else:
            new.update(profs)
    profiles.update(new)
    for n, h in deck_node_heights(new, inv).items():
        node_h.setdefault(n, h)
    for sid in pending:
        profiles[sid] = ground_profile(inv.segments[sid], dem, vref, node_h, lidar=lidar)
    return profiles, blockers


def build(inv, sel: set[str], dem, vref, deck_controls: dict, msfs_cfg: dict, out_dir: Path,
          package_name: str, package_root: Path | None = None, marker_at: tuple | None = None,
          lidar=None, excluded: dict | None = None) -> dict:
    build_id = datetime.now(timezone.utc).strftime("B%Y%m%dT%H%M%SZ")
    profiles, blockers = compute_profiles(inv, sel, dem, vref, deck_controls, lidar)
    blockers.update(excluded or {})
    net = build_surfaces(inv, profiles)
    issues = run_checks(inv, profiles, net, {k: v for k, v in blockers.items() if k in inv.bridge_decks})

    # group geometry by tile (cell centre)
    by_tile = defaultdict(list)
    for (cx, cy), mesh in net.meshes:
        by_tile[tile_id_for(cx, cy, C.TILE_SIZE_M)].append(mesh)
    if marker_at:
        lon, lat, z = marker_at
        x, y = lonlat_to_utm(lon, lat)
        by_tile[tile_id_for(x, y, C.TILE_SIZE_M)].append(orientation_marker(x, y, z))

    axis = _axis_matrix(msfs_cfg["axis_mapping"])
    models_dir = out_dir / "models"
    if models_dir.exists():                      # never ship tiles left over from an older build
        for f in models_dir.glob(f"{package_name}-*"):
            f.unlink()
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
        write_project_files(package_root, package_name, f"NYC Drivable Roads - {package_name} (test build)")
        write_package_content(package_root, package_name, tiles)

    generated = {sid for g in net.groups.values() for sid in g.seg_ids}
    starts = start_locations(inv, profiles, {k for k in generated if not has_errors(issues.get(k, []))})
    report = {
        "build_id": build_id,
        "package": package_name,
        "selected_segments": len(sel),
        "generated_segments": len(generated),
        "surface_groups": len(net.groups),
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
               "xy_utm": p.xy_utm.round(3).tolist(), "source": p.source, "info": p.info}
         for sid, p in profiles.items()}, default=_np))
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
