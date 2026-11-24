#!/bin/sh
# Construit dist/FMSpeedTool (Linux, un seul fichier) + fichiers de langue et README.
# pip install -r requirements.txt   puis   sh build_linux.sh
set -e
here=$(cd "$(dirname "$0")" && pwd)
python -m PyInstaller --noconfirm --onefile --windowed --name FMSpeedTool \
    --add-data "$here/fm_speedtool/assets:assets" --add-data "$here/fm_speedtool/lang:lang" \
    --paths "$here/fm_speedtool" \
    --collect-all formulas --collect-all schedula \
    --hidden-import capture_x11 --hidden-import Xlib --collect-submodules Xlib \
    --distpath "$here/dist" --workpath "$here/build" --specpath "$here/build" \
    "$here/fm_speedtool/app.py"
cp "$here/README.md" "$here/README_FR.md" "$here/dist/"
mkdir -p "$here/dist/lang"
cp "$here"/fm_speedtool/lang/*.json "$here/dist/lang/"
