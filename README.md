# FM Speed Tool

*Version française : [README_FR.md](README_FR.md)*

Speedrun tool for Yu-Gi-Oh! Forbidden Memories (US, 15 Card Mod) on ePSXe.
**Everything comes from analysing the image of the ePSXe window: no memory reading, no input sent
to the game, nothing modified in the game or the emulator.** Everything is shown on a single page.

## Running it

- Download `FMSpeedTool.exe` and `FMSpeedTool.asl` from the Releases page, or run `python fm_speedtool\app.py`.
- The ePSXe window must stay **visible and not covered**. If it is covered, the status line says so
  and nothing is read.
- **Any ePSXe window size works** (tested from 640×480 to 1280×1024): the image is scaled to
  640×512, and black bars around the game (kept aspect ratio) are detected and removed.
- **LiveSplit with the script (recommended)**: copy `FMSpeedTool.asl` (shipped with the .exe) to the
  LiveSplit folder, then right click > Edit Layout… > (+) > Control > **Scriptable Auto Splitter** >
  Script Path: `FMSpeedTool.asl`. Tick Start / Split / Reset and, in the script settings, the splits
  you want (wins, first loss…). Pick "Script FMSpeedTool.asl" at the bottom of the tool. The script
  does not read the game memory: it only reads what FMSpeedTool.exe publishes, so the tool must run
  during the run. Remove any other autosplitter from the layout so you don't split twice.
- **LiveSplit over TCP (fallback)**: right click > Control > Start TCP Server, pick "TCP" at the
  bottom of the tool, then "Connect LiveSplit".

## Automatic

| Feature | Image signal |
|---|---|
| Reset + start | NEW GAME highlighted on the title screen, then fade to black (confirmation) |
| Win split (campaign) | YOU WIN! / WINNER — YOU, split when RESULTS OF DUEL appears |
| First loss split (Heishin 1) | YOU LOSE / WINNER — COM |
| Free Duel | "FREE DUEL / SELECT OPPONENT" screen: no split for those duels |
| Farm | No split ("Split at end of farm" option off by default) |
| Opponent | Name on the Free Duel screen, or portrait in the dialogue (Pegasus, Isis, Duel Master K) |
| A-TEC target | Selected automatically against Pegasus |

### Live duel stats

| Stat | Signal |
|---|---|
| Turns | The YOU panel lights up |
| Cards used / remaining LP | HUD digits |
| Fusions / Equips | White flash then big card: same art as before = equip, otherwise fusion |
| Pure magic | Big magic card (green frame) played on your turn (fields included) |
| Trap triggered | On the COM turn, the right card of the battle is a trap (magenta frame) |
| Effective attacks | On your turn, the opponent monster in attack position is destroyed |
| Defensive wins | On the COM turn, your monster in defense survives |
| Face-down plays | Card back shown when confirming the card position |

Score (52 + points, clamped to 0..99) and band (S-TEC to S-POW) update live, with advice to reach
the target. The +/- buttons fix a missed detection (marked with *). A history on the page gives the
final rank of every duel of the run (campaign and Free Duel).

Checked on a full run video: the estimated rank matches the rank shown by the game on all 34 duels
with a readable rank badge (34/34, including the 5 A-TEC duels against Pegasus).

## Deck reading

On the deck building screens the tool reads:
- **DECK screen**: position (01..40) and number of each card, deck counter, card under the cursor;
- **CHEST screen**: number of each card and its copies "in chest / in deck".

It works out the deck list and counts every **addition** and **removal**. Scroll once through the
whole deck (5 pages) for a complete read; after that every change is tracked. Types and ATK come
from the YGO-FM-FusionCalc database.

## Final 6

The useful cards are filled from the deck read ("Read the deck automatically" box), or by hand: the
win % against each opponent and for the whole Final 6 is recomputed live, using the formulas of
Exarion's "FM win rate calculator 2.1" spreadsheet. "Dark Hole" is ticked if you start with Dark
Hole instead of Raigeki; extra Raigeki/Dark Hole count as Crush Card (spreadsheet rule).
"Also open on fusion.lukadevv.com" copies a link to paste with IMPORT on that site.

## Passwords

On the game's PASSWORD screen, the page is replaced by the codes of useful cards you can buy
(cost ≤ 100: Thunders, dragons < 1600 / 1600+, Umi and Mountain, equips, others) with their price
in stars; the normal page comes back when you leave the screen. The "Useful passwords" button shows
it at any time.

## Language / translation

Pick the language at the bottom of the page ("Langue / Language"); it applies after a restart.
Default: French if Windows is in French, English otherwise.

To add a language:
1. create a `lang` folder next to `FMSpeedTool.exe`;
2. copy `template.json` (or `en.json`) into it as `<code>.json`, e.g. `de.json`;
3. fill `"language"` (displayed name, e.g. "Deutsch") and every value in `"strings"`; keep the
   `{names}` between braces as they are. An empty value stays in French (the source language).
4. restart the tool and pick your language.

Shipped language files are in `fm_speedtool/lang`. After changing a text in the code,
`python tools/make_lang.py` updates `template.json` and adds the missing strings to every language.

## Learning

"Learn a screen…" opens a window with the game preview: "Freeze image", draw a rectangle, pick the
action, "Learn". Your data goes to `%APPDATA%\FMSpeedTool`.

## Source code

```
pip install -r requirements.txt
python fm_speedtool\app.py      # run
python -m pytest tests          # tests
.\build.ps1                     # build dist\FMSpeedTool.exe
```
Tests that replay ePSXe screenshots need a `captures/` folder (not published) and are skipped
without it.

## Credits

Rank formula: game rank table (same as hippochan's FMRankCalc). Final 6 win rate: Exarion's
"FM win rate calculator 2.1". Card data: YGO-FM-FusionCalc.

Thanks to Hippochan, Exarion and lukadev for the information they shared.

License: MIT.
