"""Central path configuration for the CHRONO WITNESS character pipeline.

Every path can be overridden with an environment variable so the pipeline can be
re-run on another machine (see README.md in this folder).
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

# Work directory for downloads / caches / intermediate files (not committed).
WORK = os.environ.get("CW_WORK", os.path.expanduser("~/.cache/chrono-witness/characters"))

# MakeHuman CC0 data folder (".../makehuman/makehuman/data")
MH_DATA = os.environ.get("CW_MH_DATA", os.path.join(WORK, "mh", "makehuman", "data"))

# Folder with unpacked CMU BVH files (cgspeed MotionBuilder-friendly conversion)
CMU_BVH = os.environ.get("CW_CMU_BVH", os.path.join(WORK, "bvh"))

OUT = os.environ.get("CW_OUT", os.path.join(PROJECT, "public", "assets", "characters"))
PREVIEWS = os.environ.get("CW_PREVIEWS", os.path.join(PROJECT, "docs", "previews", "characters"))
CACHE = os.path.join(WORK, "cache")

for _d in (WORK, CACHE, OUT, PREVIEWS):
    os.makedirs(_d, exist_ok=True)
