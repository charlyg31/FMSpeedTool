# FM Speed Tool

Outil de speedrun pour Yu-Gi-Oh! Forbidden Memories (US, 15 Card Mod) sur ePSXe.
**Tout passe par l'analyse de l'image de la fenêtre ePSXe, sans lire la RAM.** Tout est affiché sur une seule page.

## Lancer

- `FMSpeedTool.exe` et `FMSpeedTool.asl` (page Releases de GitHub), ou bien `python fm_speedtool\app.py`.
- La fenêtre d'ePSXe doit rester **visible et non recouverte**. Si elle est recouverte, le statut l'indique et rien n'est lu.
- **Toutes les tailles de fenêtre ePSXe fonctionnent** (testé de 640×480 à 1280×1024, et 640×480 à
  2560×1920 sur images) : l'image est ramenée en 640×512. Si ePSXe garde les proportions, les
  bandes noires autour du jeu sont détectées et retirées automatiquement.
- **LiveSplit, avec le script (recommandé)** : copie `FMSpeedTool.asl` (fourni avec le .exe) dans le
  dossier de LiveSplit, puis clic droit > Edit Layout… > (+) > Control > **Scriptable Auto Splitter** >
  Script Path : `FMSpeedTool.asl`. Coche Start / Split / Reset et, dans les réglages du script, les
  splits voulus (victoires, 1re défaite, fin de farm…). Choisis « Script FMSpeedTool.asl » en bas du
  logiciel. Le script ne lit pas la mémoire du jeu : il lit seulement ce que publie FMSpeedTool.exe,
  qui doit tourner pendant la run. Retire l'ancien autosplitter du layout pour ne pas splitter deux fois.
- **LiveSplit en TCP (secours)** : clic droit > Control > Start TCP Server, choisis « TCP » en bas du
  logiciel, puis « Connecter LiveSplit ».

## Automatique

| Fonction | Signal à l'image |
|---|---|
| Reset + départ | NEW GAME surligné sur l'écran titre, puis fondu au noir (validation) |
| Split victoire (campagne) | YOU WIN! / WINNER — YOU, puis split à l'apparition de RESULTS OF DUEL |
| Split 1re défaite (Heishin 1) | YOU LOSE / WINNER — COM |
| Free Duel | Écran « FREE DUEL / SELECT OPPONENT » : aucun split par duel |
| Free Duel / farm | Aucun split (option « Split fin de farm » désactivée par défaut) |
| Adversaire | Nom sur l'écran Free Duel, ou portrait dans le dialogue (Pegasus, Isis, Duel Master K) |
| Objectif A-TEC | Choisi tout seul contre Pegasus |

### Notes du duel en direct

| Stat | Signal |
|---|---|
| Tours | Le panneau YOU s'allume |
| Cartes utilisées / LP restants | Chiffres du HUD (0 à 9, appris sur la vidéo de run) |
| Fusions / Équipements | Flash blanc puis grande carte : illustration identique à la précédente = équipement, sinon fusion |
| Magie pure | Grande carte magie (cadre vert) jouée à ton tour (terrains compris) |
| Piège déclenché | Au tour du COM, la carte de droite du combat est un piège (cadre magenta) |
| Attaques efficaces | À ton tour, le monstre adverse en attaque (ATK en noir) est détruit |
| Victoires en défense | Au tour du COM, ton monstre en défense (DFD en noir) survit |
| Poses face cachée | Dos de carte au moment de valider la pose |

Le score (52 + points, borné à 0..99) et la bande (S-TEC à S-POW) se mettent à jour en direct.
Les boutons +/- corrigent une détection ratée (marquée d'un *).

Un historique sur la page donne le rang final de chaque duel de la run (campagne et Free Duel).

## Validé sur la vidéo du 20/10/2026

Rang estimé comparé au rang affiché par le jeu : type POW/TEC correct sur 34/34 duels,
lettre exacte sur 29/34 (les 5 autres à une lettre près), les 5 duels TEC contre Pegasus corrects.


`tools/extract_video.py` extrait les images du jeu et la ligne surlignée de LiveSplit (tes vrais splits).
`tools/replay_video.py` rejoue la run dans le moteur. `tools/rank_check.py` compare le rang estimé
au rang affiché par le jeu.

## Lecture du deck

Sur les écrans de construction du deck, le logiciel lit :
- **écran DECK** : la position (01..40) et le numéro de chaque carte, le compteur du deck, la carte sous le curseur ;
- **écran CHEST** : le numéro de chaque carte et ses exemplaires « dans le coffre / dans le deck ».

Il en déduit la composition du deck et compte chaque **ajout** et **retrait** (journal + totaux).
Fais défiler une fois tout le deck (5 pages) pour une lecture complète ; ensuite chaque
modification est suivie. Les types et ATK viennent de la base de YGO-FM-FusionCalc
(`tools/make_carddb.py`), identique à la liste de yugiohfm.com.

## Final 6

Les cartes utiles se remplissent depuis le deck lu (case « Deck lu automatiquement »), ou à la main : le % de victoire contre chaque adversaire et pour l'ensemble
du Final 6 se recalcule tout seul. Le calcul utilise les formules du tableur
« FM win rate calculator 2.1 » d'Exarion : `tools/make_f6_model.py` en extrait les cellules utiles
dans `fm_speedtool/assets/f6_model.xlsx`, et le test redonne au chiffre près les valeurs d'Excel.
« Dark Hole » se coche si tu commences avec Dark Hole au lieu de Raigeki ; les Raigeki/Dark Hole
en plus se comptent comme Crush Card (règle du tableur).
Le bouton « Ouvrir aussi sur fusion.lukadevv.com » copie un lien à coller via IMPORT sur le site.

## Mots de passe

Sur l'écran PASSWORD du jeu, la page est remplacée par les codes des cartes utiles achetables
(Thunders, dragons < 1600 / 1600+, terrains dont Umi, équipements, autres), avec leur prix en
étoiles ; la page normale revient quand tu quittes l'écran. Bouton « Mots de passe utiles » pour
l'afficher à tout moment.

## Langue / traduction

La langue se choisit en bas de la page (« Langue / Language ») et s'applique au redémarrage.
Par défaut : français si Windows est en français, sinon anglais (version anglaise : `README.md`).

Pour traduire dans une autre langue :
1. crée un dossier `lang` à côté de `FMSpeedTool.exe` ;
2. copies-y `template.json` (ou `en.json`) sous le nom `<code>.json`, par ex. `de.json` ;
3. remplis `"language"` (nom affiché, par ex. « Deutsch ») et chaque valeur de `"strings"` ;
   garde tels quels les `{noms}` entre accolades. Une valeur vide reste en français.
4. relance le logiciel et choisis la langue.

Les fichiers de langue livrés sont dans `fm_speedtool/lang`. Après un changement de texte dans le
code, `python tools/make_lang.py` met à jour `template.json` et ajoute les chaînes manquantes
dans chaque langue.

## Apprentissage

Bouton « Apprendre un écran… » : une fenêtre s'ouvre avec l'aperçu du jeu. « Figer l'image »,
tracer un rectangle, choisir l'action, « Apprendre ».
Tes données vont dans `%APPDATA%\FMSpeedTool`.

## Code source

```
pip install -r requirements.txt
python fm_speedtool\app.py      # lancer
python -m pytest tests          # tests
.\build.ps1                     # construire dist\FMSpeedTool.exe
```
Les tests qui rejouent des captures d'ePSXe ont besoin d'un dossier `captures/` (non publié) et sont
ignorés sans lui.

Licence MIT.
