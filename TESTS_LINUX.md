# Tester FM Speed Tool sous Linux (branche `linux`)

Notice pour la personne ou l'assistant qui teste sur une machine Linux. Réponds en français.

## Ce qu'il faut savoir

- FM Speed Tool lit **uniquement l'image** de la fenêtre de l'émulateur (aucune lecture mémoire).
- Sous Linux, la capture passe par **X11** (`fm_speedtool/capture_x11.py`) : l'émulateur est reconnu à
  son programme (`/proc/<pid>/exe` qui commence par `epsxe` ou `duckstation`), la fenêtre doit être
  visible et non recouverte, l'écran est copié avec `mss`.
- Une session **Wayland** native n'est pas lisible : il faut X11, Xvfb, ou lancer l'émulateur en
  XWayland (DuckStation : `QT_QPA_PLATFORM=xcb`).
- Le son (fusion / équipement) et le script LiveSplit `.asl` restent **Windows seulement** ; sous Linux
  LiveSplit est joint par son serveur TCP (LiveSplit sous Wine).
- Réglages : `~/.config/FMSpeedTool`.

## 1. Récupérer la branche

Il faut **Python 3.11 ou plus** (numpy 2.5). Sur Ubuntu 22.04 (Python 3.10), installer un Python
plus récent à part, par exemple avec `uv python install 3.13`, puis créer le venv avec lui.

```sh
git clone -b linux https://github.com/charlyg31/FMSpeedTool.git
cd FMSpeedTool
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

Il faut aussi Tk (`python3-tk` / `tk`), et pour un serveur sans écran : `xvfb` et un petit
gestionnaire de fenêtres (`openbox`). Si l'installation de paquets système est impossible (conteneur
sans droits root), dis-le et teste ce qui reste possible (étape 2 sans écran : imports seulement).

## 2. Test automatique (sans émulateur)

```sh
xvfb-run -a -s "-screen 0 1280x800x24" sh -c 'openbox & sleep 2; python .github/linux_smoke.py'
```

Il lance un faux émulateur nommé `duckstation-fake`, vérifie que l'outil le trouve, capture la bonne
image, puis lance le logiciel complet 40 s (tableur Final 6 compris). Attendu : `OK` à la fin.

Sans Xvfb, au minimum :

```sh
python -c "import sys; sys.path.insert(0, 'fm_speedtool'); import capture, tracker, vision, deckscreen, f6calc, starchips; print(capture.WindowCapture.__module__)"
```

(doit afficher `capture_x11`).

## 3. Test avec le vrai jeu (si possible)

Avec DuckStation pour Linux (AppImage), un BIOS PS1 et l'image du jeu (Yu-Gi-Oh! Forbidden Memories
US, 15 Card Mod) fournis par l'utilisateur :

1. Lancer DuckStation sur l'écran X (ou Xvfb) avec le jeu, fenêtre visible.
2. Lancer `python fm_speedtool/app.py`, choisir « Jeu : DuckStation » (le logiciel redémarre).
3. Vérifier : la ligne d'état indique `DuckStation : OK (~60 img/s)` ; sur l'écran titre, le journal
   indique « Cadrage trouvé » ; en appuyant sur NEW GAME, « Nouvelle partie (NEW GAME) ».
4. Si un écran ne marche pas, faire une capture d'écran de l'émulateur et noter le message du journal.

## 4. Construire l'exécutable

```sh
sh build_linux.sh          # donne dist/FMSpeedTool
```

## À rapporter

- Distribution, X11 / Wayland / Xvfb, version de Python.
- Résultat de chaque étape (sortie complète en cas d'erreur, contenu de
  `~/.config/FMSpeedTool/f6_error.txt` s'il existe).
- Ne pas pousser de commit sur `main`. Les corrections éventuelles vont sur la branche `linux`
  (ou sont simplement décrites dans le rapport).
