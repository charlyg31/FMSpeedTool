# FM Speed Tool

*Version française : [README_FR.md](README_FR.md)*

Speedrun tool for Yu-Gi-Oh! Forbidden Memories (US, 15 Card Mod) on ePSXe.
**Everything comes from analysing the image of the ePSXe window: no memory reading, no input sent
to the game, nothing modified in the game or the emulator.** Everything is shown on a single page.

## Running it

- Download `FMSpeedTool.exe` and `FMSpeedTool.asl` from the Releases page, or run `python fm_speedtool\app.py`.
- **Game: ePSXe, DuckStation or PS2** (top right). The emulator is found by its program (not by its
  window title); with DuckStation only the game picture is read (no menus or bars).
- The game window must stay **visible and not covered**. If it is covered, the status line says so
  and nothing is read; the tool then looks for the game window again every second. **Recaler** starts
  over: window, black bars and framing.
- **Any ePSXe window size works** (tested from 640×480 to 1280×1024): the image is scaled to
  640×512, and black bars around the game (kept aspect ratio) are detected and removed.
- **Automatic framing**: if your ePSXe settings shift, stretch or zoom the picture a little
  (resolution, cropping, video plugin), the deck digits are no longer where they should be. From the
  title screen (NEW GAME / LOAD...) or the game menu (CAMPAIGN / BUILD DECK...), the tool finds the
  logo, the copyright and the hieroglyphs and corrects the picture by itself ("Framing found" in the
  log); the deck screen is used too (ORDER and DECK words, bottom of the list). The setting is kept and
  watched: if it changes, the framing follows. Until it is done, the status line shows "framing: title
  screen or deck". "Recalibrate" searches again.
- **LiveSplit with the script (recommended)**: copy `FMSpeedTool.asl` (shipped with the .exe) to the
  LiveSplit folder, then right click > Edit Layout… > (+) > Control > **Scriptable Auto Splitter** >
  Script Path: `FMSpeedTool.asl`. Tick Start / Split / Reset and, in the script settings, the splits
  you want (wins, first loss…). Pick "Script FMSpeedTool.asl" in the Options panel. The script
  does not read the game memory: it only reads what FMSpeedTool.exe publishes, so the tool must run
  during the run. Remove any other autosplitter from the layout so you don't split twice.
- **LiveSplit over TCP (fallback)**: right click > Control > Start TCP Server, pick "TCP" in the
  Options panel, then "Connect LiveSplit".
- **LiveSplit One** (web at one.livesplit.org or desktop; works on Linux and Mac too): pick
  "LiveSplit One" in the Options panel, then in LiveSplit One: Settings > Server Connection >
  Connect, address `ws://localhost:16835` (shown in the status line). Start, splits, reset and
  undo after a save load are sent by the tool. The first time, Chrome and Firefox ask whether
  one.livesplit.org may "access other apps and services on this device": click Allow (in Chrome,
  then click Connect once more). Close the LiveSplit One settings during the run: it refuses
  commands while they are open.

## Playing on PS2 (capture card)

At the top right, pick **Game: PS2** (the tool restarts), then in **Window** the window that shows
the game: for example an OBS windowed projector of your capture card source (right click the
source > Windowed Projector). This window must stay visible and show only the game, with no
overlay on top.
- **Automatic framing**: on the title menu (NEW GAME / LOAD...) or on the first duel, the tool
  sets the full framing (width and height) of your capture setup by itself, like for ePSXe
  ("Framing found" in the log). It is kept;
  "Recalibrate" searches again (after changing a setting).
- **Digits**: the PS2 video output draws the digits slightly differently. PS2 digits are built in.
- Tested on A3r1uS's PS2 run (YouTube video): run followed from start to end, framing found on the
  first duel, 60 fps live, exact rank on 18/27 duels (the others one letter off).

## Automatic

| Feature | Image signal |
|---|---|
| Reset + start | Pressing NEW GAME: the menu buttons slide away on the very next frame (fade to black as a backup). Moving the cursor or pressing LOAD never starts or resets |
| Win split (campaign) | YOU WIN! / WINNER — YOU, split when RESULTS OF DUEL appears |
| First loss split (Heishin 1) | YOU LOSE / WINNER — COM |
| Free Duel | "FREE DUEL / SELECT OPPONENT" screen: no split for those duels |
| Farm | No split ("Split at end of farm" option off by default) |
| Save loaded | SAVE COMPLETE! remembers how many splits are done, the deck read and the star chip total; LOAD COMPLETE! (after a death, for example) brings the run back to that save, deck and star chips included. Option 1 (default): undo in LiveSplit the splits made since the save. Option 2: don't count the splits of the replayed duels |
| Opponent | All 39 opponents: name written on the Free Duel screen (read letter by letter), or portrait of the dialogue just before a campaign duel. Checked on two All Duelists runs (YouTube and Twitch, two players): every duel gets the right opponent |
| All Duelists | Option "All Duelists (DMK + Heishin in Free Duel)" (off by default): the first Free Duel win against Duel Master K and the first one against Heishin (Heishin 1, lost in the campaign) split like campaign wins instead of being farm duels |
| A-TEC target | Selected automatically against Pegasus |

### Live duel stats

| Stat | Signal |
|---|---|
| Turns | The YOU panel lights up |
| Cards used / remaining LP | HUD digits |
| Fusions / Equips | Flash then big card; the game sound decides fusion or equip (see below); without sound: ATK/DEF counting up or purple glow = equip, otherwise fusion |
| Pure magic | Big magic card (green frame) played on your turn (fields included) |
| Trap triggered | On the COM turn, the right card of the battle is a trap (magenta frame) |
| Effective attacks | On your turn, the opponent monster in attack position is destroyed |
| Defensive wins | On the COM turn, your monster in defense survives |
| Face-down plays | Card back shown when confirming the card position |

Score (52 + points, clamped to 0..99) and band (S-TEC to S-POW) update live, with advice to reach
the target. The +/- buttons fix a missed detection (marked with *). A history on the page gives the
final rank of every duel of the run (campaign and Free Duel), with its opponent.

Small screen: the "Show" boxes at the bottom of the window hide the panels you don't use (Rank,
Final 6, History, Options). The window shrinks to the panels left, and the choice is kept.

Checked on a full run video: the estimated rank matches the rank shown by the game on all 34 duels
with a readable rank badge (34/34, including the 5 A-TEC duels against Pegasus).

## Game sound (fusion / equip)

Each action has its own sound: a fusion is a wide whoosh then a held low note, an equip ends with a
sharp rising sweep. The image sees that something happens (flash, big card); the sound decides
fusion or equip. Only the sound of the game program is captured (ePSXe, or the PS2 window's
program), not Discord, music or the microphone; the game sound must be on in ePSXe (it can be muted
in your headset). "Sound (fusion / equip)" turns it off; the status line shows "sound OK". Without
sound, or when the sound is not clear, the image decides as before. Tested on three run videos
(ePSXe, a Twitch stream with voice and music, a PS2 run): it fixes the cases where the image alone
was wrong.

## Deck reading

On the deck building screens the tool reads:
- **DECK screen**: position (01..40) and number of each card, deck counter, card under the cursor;
- **CHEST screen**: only **additions** count (a card whose "in deck" number goes up); removals are
  read on the DECK screen only.

The first deck check sets the base: scroll the deck once with R1, as fast as you like; the deck is
complete when every position up to the displayed counter has been read (40, or fewer right after a
removal). After that only additions and removals change it. Multiple copies are counted. The game
does not scroll faster than about 0.15 s per page, even when R1 is pressed faster: checked live on
ePSXe, 40/40 cards at that top speed (the tool analyses 58 to 60 frames/s on this screen), same
result as a slow read.
Types and ATK come from the YGO-FM-FusionCalc database.

## Final 6

The useful cards are filled from the deck read ("Read the deck automatically" box), or by hand: the
win % against each opponent and for the whole Final 6 is recomputed live, using the formulas of
Exarion's "FM win rate calculator 2.1" spreadsheet. "Dark Hole" is ticked if you start with Dark
Hole instead of Raigeki; extra Raigeki/Dark Hole count as Crush Card (spreadsheet rule).
Equips have one counter per type, several copies allowed (Megamorph has its own box); the
spreadsheet has 6 equip slots, so with more than 6 the best 6 count.
"Show the Final 6 window" (or the "Final 6 window" box of the "Show" line) shows or hides a separate
window that fills itself: the 6 bosses and the Final 6
with their %, then the deck cards as pictures with their count (greyed at 0). Click the Raigeki tile to
switch to Dark Hole. The window can be captured in OBS; its place is kept and it reopens at launch.
Right click in the window to customize it: layout (horizontal, wide, square, vertical, narrow column,
bosses left), size from 50 to 150 %, parts shown (bosses, current duel rank, rates,
names, summary, cards), hide cards at 0,
dark or green background (made transparent in OBS with the "Chroma Key" filter), always on top,
hide a tile. The card area always keeps the same size: with cards at 0 hidden, the owned cards gather
at the top while the window (and so the OBS source) keeps its size. Drag a card onto another to move it (bosses keep the game's order). These settings are kept.

The current duel rank can have its own window (right click panel, "Current duel rank" > "In its own
window"), to capture alone in OBS: dark or green background (chroma key), size from 50 to 150 %, your own
colours for the rank, the score and the target reached. Closing that window puts the rank back in the
Final 6 window. With the green background, pick a target colour that is not green.
The card pictures are the game's own, and the portraits come from the pre-duel dialogues.

## Passwords

On the game's PASSWORD screen, the page is replaced by the codes of useful cards you can buy
(cost ≤ 100: Thunders, dragons < 1600 / 1600+, Umi and Mountain, equips, others) with their price
in stars; the normal page comes back when you leave the screen. The "Useful passwords" button shows
it at any time.

## Star chips

The run's star chip total is shown at the top of the duel history and in a tile of the Final 6
window (can be hidden). Each win adds the stars shown on the RESULTS OF DUEL screen (rank D 1,
C 2, B 3, A 4, S 5; estimated rank if it is not read). On the PASSWORD screen, the total shown by
the game wins: purchases are taken off by themselves. A new game resets it to 0, loading a save
goes back to the save's total; + / − to fix it by hand.

## Language / translation

Pick the language at the bottom of the page ("Langue / Language"); it applies after a restart.
Default: French if Windows is in French, English otherwise.

To add a language:
1. create a `lang` folder next to `FMSpeedTool.exe`;
2. copy `template.json` (or `en.json`) into it as `<code>.json`, e.g. `de.json`;
3. fill `"language"` (displayed name, e.g. "Deutsch") and every value in `"strings"`; keep the
   `{names}` between braces as they are. An empty value stays in French (the source language).
4. restart the tool and pick your language.

Shipped language files are in `fm_speedtool/lang`.

## Options

The Options panel holds the timer and split options, what to do when a save is loaded (undo or
don't count the replayed duels), the LiveSplit link (script or TCP), the game sound, the language and the useful passwords.
Your settings go to `%APPDATA%\FMSpeedTool`.

## Source code

```
pip install -r requirements.txt
python fm_speedtool\app.py      # run
```

## Credits

Rank formula: game rank table (same as hippochan's FMRankCalc). Final 6 win rate: Exarion's
"FM win rate calculator 2.1". Card data: YGO-FM-FusionCalc.

Thanks to Hippochan, Exarion and lukadev for the information they shared.

Thanks to the players who tried the tool and sent feedback: AEtienne, Aifo0s.

License: MIT.
