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

## Jouer sur PS2 (carte d'acquisition)

En haut à droite, choisis **Jeu : PS2** (le logiciel redémarre), puis dans **Fenêtre** la fenêtre
qui affiche le jeu : par exemple un projecteur OBS de la source de la carte d'acquisition
(clic droit sur la source > Projecteur fenêtré). Cette fenêtre doit rester visible et ne montrer
que le jeu, sans incrustation par-dessus.
- **Cadrage automatique** : sur le menu de l'écran titre (NEW GAME / LOAD...) ou au premier duel,
  le logiciel cale tout seul le décalage vertical propre à ta carte d'acquisition (« Cadrage PS2
  trouvé » dans le journal) : il est donc prêt avant le premier check du deck. Il est gardé ensuite ; « Recaler » le cherche à nouveau (après un changement de réglage).
- **Chiffres** : la sortie vidéo de la PS2 rend les chiffres un peu différemment. Des chiffres PS2
  sont intégrés ; s'il en manque, ils apparaissent dans « Chiffres à nommer ».
- Testé sur la run PS2 d'A3r1uS (vidéo YouTube) : run suivie du début à la fin, cadrage trouvé
  dès le premier duel, 60 img/s en direct, rang exact sur 18/27 duels (les autres à une lettre près).

## Automatique

| Fonction | Signal à l'image |
|---|---|
| Reset + départ | Appui sur NEW GAME : les boutons du menu s'écartent dès l'image suivante (fondu au noir en secours). Déplacer le curseur ou valider LOAD ne démarre et ne reset jamais rien |
| Split victoire (campagne) | YOU WIN! / WINNER — YOU, puis split à l'apparition de RESULTS OF DUEL |
| Split 1re défaite (Heishin 1) | YOU LOSE / WINNER — COM |
| Free Duel | Écran « FREE DUEL / SELECT OPPONENT » : aucun split par duel |
| Free Duel / farm | Aucun split (option « Split fin de farm » désactivée par défaut) |
| LOAD d'une save | SAVE COMPLETE! retient combien de splits sont faits ; LOAD COMPLETE! (après une mort par exemple) ramène la run à cette save. Option 1 (par défaut) : annuler dans LiveSplit les splits faits depuis la save. Option 2 : ne pas compter les splits des duels rejoués |
| Adversaire | Nom sur l'écran Free Duel, ou portrait dans le dialogue (Pegasus, Isis, Duel Master K) |
| Objectif A-TEC | Choisi tout seul contre Pegasus |

### Notes du duel en direct

| Stat | Signal |
|---|---|
| Tours | Le panneau YOU s'allume |
| Cartes utilisées / LP restants | Chiffres du HUD (0 à 9, appris sur la vidéo de run) |
| Fusions / Équipements | Flash puis grande carte ; le son du jeu tranche fusion ou équipement (voir plus bas) ; sans son : ATK/DFD qui défile ou halo violet = équipement, sinon fusion |
| Magie pure | Grande carte magie (cadre vert) jouée à ton tour (terrains compris) |
| Piège déclenché | Au tour du COM, la carte de droite du combat est un piège (cadre magenta) |
| Attaques efficaces | À ton tour, le monstre adverse en attaque (ATK en noir) est détruit |
| Victoires en défense | Au tour du COM, ton monstre en défense (DFD en noir) survit |
| Poses face cachée | Dos de carte au moment de valider la pose |

Le score (52 + points, borné à 0..99) et la bande (S-TEC à S-POW) se mettent à jour en direct.
Les boutons +/- corrigent une détection ratée (marquée d'un *).

Un historique sur la page donne le rang final de chaque duel de la run (campagne et Free Duel).

## Validé sur la vidéo du 20/10/2026

Rang estimé comparé au rang affiché par le jeu : exact sur les 34 duels dont le badge de rang est
lisible (34/34, dont les 5 duels A-TEC contre Pegasus).


`tools/extract_video.py` extrait les images du jeu et la ligne surlignée de LiveSplit (tes vrais splits).
`tools/replay_video.py` rejoue la run dans le moteur. `tools/rank_check.py` compare le rang estimé
au rang affiché par le jeu.

## Son du jeu (fusion / équipement)

Chaque action a son bruitage : la fusion fait un souffle large puis une note grave tenue,
l'équipement finit par une montée de fréquence très nette. L'image voit qu'il se passe quelque
chose (flash, grande carte) ; le son tranche entre fusion et équipement. Seul le son du programme du
jeu est capté (ePSXe, ou le programme de la fenêtre PS2) : ni Discord, ni la musique, ni le micro.
Le son du jeu doit être activé dans ePSXe (il peut être coupé dans le casque). La case « Son
(fusion / équipement) » le désactive ; la ligne d'état affiche « son OK ». Sans son, ou si le son
n'est pas net, l'image décide comme avant. Testé sur trois vidéos de run (ePSXe, un stream Twitch
avec voix et musique, une run PS2) : il corrige les cas où l'image seule se trompait.

## Lecture du deck

Sur les écrans de construction du deck, le logiciel lit :
- **écran DECK** : la position (01..40) et le numéro de chaque carte, le compteur du deck, la carte sous le curseur ;
- **écran CHEST** : seuls les **ajouts** comptent (une carte dont le nombre « dans le deck »
  augmente) ; les retraits se lisent uniquement sur l'écran DECK.

Le premier check du deck donne la base : fais défiler le deck une fois (R1, une page toutes les
0,2 s environ ou plus lentement) ; le deck est complet quand toutes les positions jusqu'au compteur
affiché sont lues (40, ou moins juste après un retrait). Ensuite seuls les ajouts et retraits le
modifient. Les exemplaires multiples sont comptés. Vérifié en direct sur ePSXe : 40/40 cartes avec
R1 toutes les 0,2 s, même résultat qu'une lecture lente. Les types et ATK viennent de la base de YGO-FM-FusionCalc
(`tools/make_carddb.py`), identique à la liste de yugiohfm.com.

## Final 6

Les cartes utiles se remplissent depuis le deck lu (case « Deck lu automatiquement »), ou à la main : le % de victoire contre chaque adversaire et pour l'ensemble
du Final 6 se recalcule tout seul. Le calcul utilise les formules du tableur
« FM win rate calculator 2.1 » d'Exarion : `tools/make_f6_model.py` en extrait les cellules utiles
dans `fm_speedtool/assets/f6_model.xlsx`, et le test redonne au chiffre près les valeurs d'Excel.
« Dark Hole » se coche si tu commences avec Dark Hole au lieu de Raigeki ; les Raigeki/Dark Hole
en plus se comptent comme Crush Card (règle du tableur).
Équipements : un compteur par type, plusieurs exemplaires possibles (Megamorph a sa propre case) ;
le tableur a 6 cases d'équipement, donc au-delà de 6 les 6 meilleurs comptent.
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

## Options

Le panneau Options regroupe le timer, les splits, le choix au LOAD d'une save (annuler ou ne
pas compter les duels rejoués), le son du jeu, la langue et les mots de passe utiles.
Tes réglages vont dans `%APPDATA%\FMSpeedTool`.

## Code source

```
pip install -r requirements.txt
python fm_speedtool\app.py      # lancer
python -m pytest tests          # tests
.\build.ps1                     # construire dist\FMSpeedTool.exe
```
Les tests qui rejouent des captures d'ePSXe ont besoin d'un dossier `captures/` (non publié) et sont
ignorés sans lui.

## Remerciements

Merci à Hippochan, Exarion et lukadev pour les informations partagées.

Licence MIT.
