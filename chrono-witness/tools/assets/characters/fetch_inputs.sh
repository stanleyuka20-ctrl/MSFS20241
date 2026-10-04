#!/usr/bin/env bash
# Download the third-party inputs of the character pipeline into $CW_WORK
# (default ~/.cache/chrono-witness/characters):
#   - MakeHuman CC0 data (sparse checkout of github.com/makehumancommunity/makehuman)
#   - CMU mocap BVH takes (cgspeed conversion, mirror github.com/Shriinivas/cmubvh)
set -euo pipefail
WORK="${CW_WORK:-$HOME/.cache/chrono-witness/characters}"
mkdir -p "$WORK"
cd "$WORK"

MH_COMMIT=a8bc2d54ff0ac92e78ff71431b1023eda42bf482
if [ ! -d mh ]; then
  git clone --filter=blob:none --no-checkout https://github.com/makehumancommunity/makehuman.git mh
fi
git -C mh sparse-checkout init --no-cone
git -C mh sparse-checkout set '/LICENSE*' '/makehuman/data/3dobjs/' '/makehuman/data/rigs/' \
  '/makehuman/data/eyes/' '/makehuman/data/uvs/' '/makehuman/data/targets/macrodetails/' \
  '/makehuman/data/targets/head/' '/makehuman/data/targets/nose/' '/makehuman/data/targets/chin/' \
  '/makehuman/data/targets/mouth/' '/makehuman/data/targets/ears/' '/makehuman/data/targets/eyebrows/' \
  '/makehuman/data/targets/eyes/' '/makehuman/data/targets/cheek/' '/makehuman/data/targets/forehead/' \
  '/makehuman/data/targets/neck/'
git -C mh checkout -q "$MH_COMMIT"

CMU_COMMIT=3bc9c75c481ac6e622f3c378369b293d8de9be45
TAKES="08_01 09_11 35_01 91_16 77_02 111_28 19_08 82_05"
if [ ! -d cmubvh ]; then
  git clone --filter=blob:none --no-checkout https://github.com/Shriinivas/cmubvh.git cmubvh
fi
git -C cmubvh sparse-checkout init --no-cone
PATHS=('/README.md' '/READMEFIRST.txt' '/cmu-mocap-index-text.txt')
for t in $TAKES; do
  subj=${t%%_*}
  PATHS+=("/*/$subj/Data/$t.zip")
done
git -C cmubvh sparse-checkout set "${PATHS[@]}"
git -C cmubvh checkout -q "$CMU_COMMIT"
mkdir -p bvh
for t in $TAKES; do
  z=$(find cmubvh -name "$t.zip" | head -1)
  unzip -o -q "$z" -d bvh
done
echo "inputs ready in $WORK  (mh/, bvh/)"
