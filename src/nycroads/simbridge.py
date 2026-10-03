"""SimConnect bridge: telemetry recorder and explicit vehicle recovery (Windows only).

Uses the community ``SimConnect`` Python package (Python-SimConnect), which wraps
the SimConnect.dll shipped with the MSFS SDK. STATUS: UNVERIFIED against MSFS
2024 - run ``nycroads record --selftest`` while parked at a known location and
compare the printed values with the simulator before trusting a recording.

SimVars used (names from the SimConnect SimVar reference; units as returned by
the Python-SimConnect definitions, converted to SI below):
  PLANE_LATITUDE / PLANE_LONGITUDE (deg), PLANE_ALTITUDE (ft), SIM_ON_GROUND (bool),
  GROUND_VELOCITY (kt), VERTICAL_SPEED (ft/s), PLANE_HEADING_DEGREES_TRUE (rad),
  BRAKE_LEFT_POSITION (0..1 / position units).
"""
from __future__ import annotations

import csv
import math
import time
from pathlib import Path

FT = 0.3048
KT = 0.514444

FIELDS = ["t", "lat", "lon", "alt_m", "on_ground", "gs_mps", "vs_mps", "heading_deg", "brake", "event"]


def _connect():
    try:
        from SimConnect import AircraftRequests, SimConnect  # type: ignore
    except ImportError as e:  # pragma: no cover - Windows only
        raise SystemExit("SimConnect package not installed: pip install .[sim]  (Windows + running simulator)") from e
    sm = SimConnect()
    return sm, AircraftRequests(sm, _time=0)


def read_state(aq) -> dict:
    g = aq.get
    return {
        "lat": float(g("PLANE_LATITUDE")),
        "lon": float(g("PLANE_LONGITUDE")),
        "alt_m": float(g("PLANE_ALTITUDE")) * FT,
        "on_ground": int(bool(g("SIM_ON_GROUND"))),
        "gs_mps": float(g("GROUND_VELOCITY")) * KT,
        "vs_mps": float(g("VERTICAL_SPEED")) * FT,
        "heading_deg": math.degrees(float(g("PLANE_HEADING_DEGREES_TRUE"))) % 360,
        "brake": float(g("BRAKE_LEFT_POSITION") or 0.0),
    }


def record(out: Path, hz: float = 20.0, duration_s: float | None = None, marker_file: Path | None = None):
    """Record until Ctrl+C. Lines appended to ``marker_file`` (if given) are
    written into the 'event' column, e.g. 'restart_marker' or 'note: hill start'."""
    sm, aq = _connect()
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    seen = 0
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        try:
            while duration_s is None or time.monotonic() - t0 < duration_s:
                row = read_state(aq)
                row["t"] = round(time.monotonic() - t0, 3)
                row["event"] = ""
                if marker_file and marker_file.exists():
                    lines = marker_file.read_text().splitlines()
                    if len(lines) > seen:
                        row["event"] = " | ".join(lines[seen:])
                        seen = len(lines)
                w.writerow(row)
                time.sleep(max(0.0, 1.0 / hz))
        except KeyboardInterrupt:
            pass
    sm.exit()


def selftest():
    sm, aq = _connect()
    st = read_state(aq)
    for k, v in st.items():
        print(f"{k:12s} {v}")
    sm.exit()


def recover(lat: float, lon: float, alt_m: float, heading_deg: float, marker_file: Path | None = None):
    """Explicit recovery: place the vehicle at a verified start location.

    The action is ALWAYS logged to the marker file so the analyser fails the
    segment that was being driven (recovery never hides a broken connection).
    """
    if marker_file:
        with open(marker_file, "a") as f:
            f.write(f"recovery to {lat:.6f},{lon:.6f}\n")
    sm, aq = _connect()
    aq.set("PLANE_LATITUDE", lat)
    aq.set("PLANE_LONGITUDE", lon)
    aq.set("PLANE_ALTITUDE", alt_m / FT)
    aq.set("PLANE_HEADING_DEGREES_TRUE", math.radians(heading_deg))
    for v in ("VELOCITY_BODY_X", "VELOCITY_BODY_Y", "VELOCITY_BODY_Z"):
        try:
            aq.set(v, 0.0)
        except Exception:  # pragma: no cover
            pass
    sm.exit()
