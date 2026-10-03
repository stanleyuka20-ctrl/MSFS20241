import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import synthetic as S  # noqa: E402
from nycroads.inventory import build_inventory  # noqa: E402
from nycroads.pipeline import build, compute_profiles, select_segments  # noqa: E402


@pytest.fixture(scope="session")
def inv():
    return build_inventory(S.osm_data(), crossings=S.CROSSINGS)


@pytest.fixture(scope="session")
def built(inv, tmp_path_factory):
    out = tmp_path_factory.mktemp("build")
    sel = select_segments(inv, ids=list(inv.segments))
    rep = build(inv, sel, S.dem(), S.vref(), S.deck_controls(), S.MSFS_CFG, out / "b", "nycroads-test",
                out / "pkg", marker_at=(*S.ll(-150, 0), 5.0))
    profiles, _ = compute_profiles(inv, sel, S.dem(), S.vref(), S.deck_controls())
    return {"report": rep, "out": out, "sel": sel, "profiles": profiles}
