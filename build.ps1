# Construit dist\FMSpeedTool.exe (un seul fichier) + script LiveSplit + fichiers de langue.
# pip install -r requirements.txt   puis   .\build.ps1
$here = $PSScriptRoot
python -m PyInstaller --noconfirm --onefile --windowed --name FMSpeedTool `
    --add-data "$here\fm_speedtool\assets;assets" --add-data "$here\fm_speedtool\lang;lang" `
    --paths "$here\fm_speedtool" `
    --collect-all formulas --collect-all schedula --collect-all dxcam --collect-all comtypes `
    --distpath "$here\dist" --workpath "$here\build" --specpath "$here\build" `
    "$here\fm_speedtool\app.py"
Copy-Item "$here\livesplit\FMSpeedTool.asl", "$here\README.md", "$here\README_FR.md" "$here\dist\"
New-Item -ItemType Directory -Force "$here\dist\lang" | Out-Null
Copy-Item "$here\fm_speedtool\lang\*.json" "$here\dist\lang\"
