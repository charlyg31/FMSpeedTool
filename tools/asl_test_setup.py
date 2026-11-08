"""Prepare une COPIE de LiveSplit (dossier temporaire) avec FMSpeedTool.asl
dans le layout, pour tester le script sans toucher l'installation de l'utilisateur.

python tools/asl_test_setup.py DOSSIER_LIVESPLIT LAYOUT.lsl SPLITS.lss DESTINATION
"""

import os
import shutil
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
src, layout_src, splits_src, dest = sys.argv[1:5]
asl = os.path.join(ROOT, "livesplit", "FMSpeedTool.asl")

if os.path.isdir(dest):
    shutil.rmtree(dest)
shutil.copytree(src, dest, ignore=shutil.ignore_patterns("WebView2_cache"))

# Layout : le composant d'autosplit pointe sur notre script, Start/Split/Reset coches.
tree = ET.parse(layout_src)
for comp in tree.getroot().iter("Component"):
    if comp.findtext("Path") == "LiveSplit.ScriptableAutoSplit.dll":
        s = comp.find("Settings")
        s.find("ScriptPath").text = asl
        for tag in ("Start", "Reset", "Split"):
            s.find(tag).text = "True"
        s.remove(s.find("CustomSettings"))
        ET.SubElement(s, "CustomSettings")
layout = os.path.join(dest, "test.lsl")
tree.write(layout, encoding="UTF-8", xml_declaration=True)
splits = os.path.join(dest, "test.lss")
shutil.copy(splits_src, splits)

# Reglages de la copie : ce layout et ces splits, sans confirmation de reset.
cfg_path = os.path.join(dest, "settings.cfg")
cfg = ET.parse(cfg_path)
root = cfg.getroot()
root.find("WarnOnReset").text = "False"
rs = root.find("RecentSplits")
for e in list(rs):
    rs.remove(e)
f = ET.SubElement(rs, "SplitsFile", gameName="Yu-Gi-Oh! Forbidden Memories", categoryName="Any% 15 cards",
                  lastTimingMethod="RealTime", lastHotkeyProfile="Default")
f.text = splits
rl = root.find("RecentLayouts")
for e in list(rl):
    rl.remove(e)
ET.SubElement(rl, "LayoutPath").text = layout
cfg.write(cfg_path, encoding="UTF-8", xml_declaration=True)
print("copie prete :", dest)
