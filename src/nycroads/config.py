"""Project-wide constants and scope rules.

Everything that decides *what counts as a road we must cover* lives here, so the
denominator of the coverage figure is explicit and reviewable.
"""
from __future__ import annotations

# --- Scope -------------------------------------------------------------------

# OSM highway=* values that are public motor-vehicle roads (the coverage denominator).
IN_SCOPE_HIGHWAY = {
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "unclassified", "residential", "living_street",
    "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link",
}

# Tracked but NOT in the denominator: publicly reachable service roads are inventoried
# so they can be added later, but private driveways / parking aisles never count.
TRACKED_SECONDARY_HIGHWAY = {"service"}
EXCLUDED_SERVICE_VALUES = {"driveway", "parking_aisle", "drive-through", "emergency_access"}

# access-style tags that remove a way from the public motor-vehicle network.
EXCLUDING_ACCESS = {"no", "private", "customers", "delivery", "agricultural", "forestry"}
ACCESS_KEYS = ("access", "motor_vehicle", "motorcar", "vehicle")

# --- Geometry defaults (used only when OSM has no width / lanes tags) ---------

LANE_WIDTH_M = 3.35  # NYC typical; ~11 ft
DEFAULT_LANES = {
    "motorway": 3, "trunk": 2, "primary": 2, "secondary": 2, "tertiary": 2,
    "unclassified": 2, "residential": 2, "living_street": 1, "service": 1,
    "motorway_link": 1, "trunk_link": 1, "primary_link": 1,
    "secondary_link": 1, "tertiary_link": 1,
}
# Extra paved width per side (shoulder / parking lane) by class, metres.
DEFAULT_SHOULDER_M = {
    "motorway": 2.5, "trunk": 1.5, "primary": 2.4, "secondary": 2.4, "tertiary": 2.4,
    "unclassified": 2.0, "residential": 2.4, "living_street": 1.0, "service": 0.5,
}

# --- Vertical design limits used by geometry checks ---------------------------
# Not legal design standards: thresholds above which a generated profile is
# flagged for human review (a real NYC street can exceed them; e.g. parts of
# Fort George / Washington Heights). Flagged != failed.
MAX_GRADE = {
    "motorway": 0.06, "trunk": 0.08, "motorway_link": 0.08, "trunk_link": 0.09,
    "default": 0.15,
}
# Max change of grade between consecutive 5 m stations: catches steps / kinks.
MAX_GRADE_CHANGE_PER_STATION = 0.02
STATION_SPACING_M = 5.0

# Continuity: max allowed vertical / horizontal gap where two generated surfaces meet.
MAX_JOINT_GAP_M = 0.01
# Minimum vertical clearance between an upper deck surface and a road below.
MIN_UNDERPASS_CLEARANCE_M = 3.5
# Ground-level road surface is lifted this much above the smoothed profile to
# avoid z-fighting with the terrain it lies on.
GROUND_ROAD_LIFT_M = 0.05

# --- Tiling -------------------------------------------------------------------
TILE_SIZE_M = 1000.0

# --- Status model -------------------------------------------------------------
# Ordered: a segment is promoted only when every check of the previous stage passed.
STATUSES = [
    "not_started",        # not yet in inventory
    "inventoried",        # in inventory with stable ID
    "generated",          # surface geometry generated
    "geometry_verified",  # automated geometry checks passed (offline, NOT a driving test)
    "driven",             # in-game player-vehicle drive passed in all permitted directions
    "verified",           # driven + re-test after simulator restart passed
]
BLOCKED = "blocked"       # has a recorded technical blocker; excluded from progress until resolved
