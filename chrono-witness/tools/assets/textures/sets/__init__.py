"""Registry of PBR texture sets: name -> (builder(name, tile_m) -> Material, tileMetres, notes)."""
from . import ww1_ground, ww1_wood, ww1_fabric, ww1_metal, village, hq, blitz, berlin1945, normandy

REGISTRY = {}
for _mod in (ww1_ground, ww1_wood, ww1_fabric, ww1_metal, village, hq, blitz, berlin1945, normandy):
    REGISTRY.update(_mod.SETS)
