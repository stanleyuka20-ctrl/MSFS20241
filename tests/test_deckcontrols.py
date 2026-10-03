import numpy as np
import synthetic as S

from nycroads.deckcontrols import controls_from_points


def test_controls_from_class17_points_ignore_water_and_clutter():
    rng = np.random.default_rng(1)
    pts, cls = [], []
    for y in np.arange(-100, 100.1, 0.5):
        for dx in (-0.6, 0.0, 0.6):
            z = 8.0 - 3.0 * (y / 100) ** 2
            pts.append((S.X0 + 300 + dx, S.Y0 + y, z + rng.normal(0, 0.03))); cls.append(17)
        pts.append((S.X0 + 300, S.Y0 + y, 0.0)); cls.append(9)            # water below
    pts.append((S.X0 + 300, S.Y0 + 0.2, 14.0)); cls.append(17)            # lamp post misclassified
    line = [S.ll(300, -100), S.ll(300, 100)]
    out = controls_from_points(line, np.array(pts), np.array(cls), "EPSG:32618",
                               to_sim=lambda lon, lat, z: z, step_m=50)
    assert len(out) == 5
    mid = out[2]
    assert abs(mid["z_sim_m"] - 8.0) < 0.05
    assert all(o["z_sim_m"] > 4.0 for o in out)
