import numpy as np

from nycroads.lidarsurface import choose_surface

S = np.arange(0, 101, 5.0)
NAN = np.nan


def test_street_on_unmapped_deck_uses_deck_returns_not_trench_dem():
    # street at ~6 m; stations 40-60 m are carried over a trench: no class 2, class 17 at 6.2, DEM 2.2
    g = np.where((S >= 40) & (S <= 60), NAN, 6.0)
    dk = np.where((S >= 40) & (S <= 60), 6.2, NAN)
    dem = np.where((S >= 40) & (S <= 60), 2.2, 6.0)
    z, src = choose_surface(S, g, dk, dem)
    assert np.all(np.abs(z - 6.1) < 0.2)
    assert set(src[(S >= 40) & (S <= 60)]) == {"lidar_deck"}


def test_overpass_deck_above_street_is_rejected():
    # street at 3 m passes under an overpass (class 17 at 9 m, no class 2 in its shadow)
    g = np.where((S >= 40) & (S <= 55), NAN, 3.0)
    dk = np.where((S >= 40) & (S <= 55), 9.0, NAN)
    dem = np.full(len(S), 3.0)
    z, src = choose_surface(S, g, dk, dem)
    assert np.all(np.abs(z - 3.0) < 1e-9)
    assert "lidar_deck" not in set(src)


def test_dem_outlier_without_lidar_is_rejected():
    g = np.where((S >= 40) & (S <= 50), NAN, 5.0)
    dk = np.full(len(S), NAN)
    dem = np.where((S >= 40) & (S <= 50), 1.0, 5.0)
    z, src = choose_surface(S, g, dk, dem)
    assert np.all(np.isnan(z[(S >= 40) & (S <= 50)]))
    assert set(src[(S >= 40) & (S <= 50)]) == {"rejected_dem"}
