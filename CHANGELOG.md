# Changelog

## 1.3.0
- Mixie stays on the beat much better: her own beat clock follows the music smoothly, and audio that arrives
  in bursts no longer throws off the timing.
- Fixed: with NumPy 2 the beat times were stored with too little precision, which hurt the sync.
- Fixed: she could freeze on one picture (while still bouncing) when the tempo estimate went wrong.
- Fixed: her eyes flickered – she now blinks naturally every few seconds, and keeps the same eyes for a whole move.
- The BPM no longer disappears in breaks without drums; it holds for a few seconds and only changes when the
  tempo really does.
- Eight new dance moves: twist, cheer, kick, moonwalk, bop, pump, wave arms and squat (17 in total).
- While waiting she now also looks around and stretches.
- Seven new outfits: crown, bunny ears, flower crown, beanie, cap, devil horns and a party hat – with new seasonal picks.
- New settings panel with switches, and a new outfit picker with Mixie in every outfit.
- A bigger Mixie in the app and desktop icon.
- Pop-ups (settings, outfits, messages, About, hotkeys) open on the same screen as Mixie instead of always on
  the main screen, and messages are drawn in Mixie's own style.
- Changing outfit or song colour no longer causes a short stutter.
- **Mixie.exe**: a single file that runs without Python, built and tested automatically on GitHub.
- Microphone row: volume and mute for your default microphone, plus <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>N</kbd>
  to mute it from inside a game. Can be hidden in the settings.
- **Watch mode**: when a film, series or stream plays (YouTube, Twitch, Netflix, Disney+ and more) and there's
  no steady beat, Mixie curls up and naps instead of dancing. Music videos still get a dance.
- **Updates**: Mixie checks GitHub once a day and tells you when a new version is out.
- **Start with Windows** switch.
- **Play an app on another device** (right-click a card): e.g. the game in your headphones, Spotify on the speakers.
- **Your own profiles** with names, and *Game profile when a game is open* switches profiles by itself.
- <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>H</kbd> shows or hides Mixie (on top of the game for a moment).
- Mixie reacts more: she goes wild on the **drop**, covers her ears when it's too loud, says good luck when a game
  starts and gets sleepy late at night.
- **Seasons**: snow in December, bats in October – and a party hat and confetti on **your birthday**.
- **Low power mode** for slower PCs.
- A settings panel that is too long splits into two columns, so it fits on any screen.
- Watch mode: the sound waves calm down and stand still while she naps.
- Every panel and message has a close button (X); the audio device picker and the right-click menu are now
  panels like the others.
- Safety: only one Mixie runs at a time (starting it again brings the running one forward), a damaged
  settings file can no longer crash it and settings are saved safely, the installer checks a SHA-256 checksum
  before installing, update checks only ever open Mixie's own GitHub page (and can be switched off), and the
  device helper only accepts valid input. Releases come with checksums and a signed build attestation.
- Debug mode (settings or <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>D</kbd>): shows tempo, beat, dance and frame-rate
  numbers and writes `debug_log.txt`, to make problems easy to report.

## 1.2.3
- Links point to the right repository (`Modda-ctrl/Mixie`).

## 1.2.2
- More room above Mixie, so hats never get cut off – not even mid-jump.
- Taller, finished hats: witch hat with a bent tip and buckle, floppy santa hat with a pompom, pointy cat ears.

## 1.2.1
- Fixed a crash after a few seconds: an audio object was released twice.
- Desktop shortcuts are no longer created with COM on a background thread.

## 1.2.0
- Mixie dances in time with the music: tempo (BPM) and beat detection, with every move, bounce and note on the beat.
- The *Now playing* card shows the tempo.
- Faster sound waves (one shared glow, reused images) and a bounded image cache (lower memory use).

## 1.1.0
- New app icon: Mixie with her headphones.
- Six new dance moves: disco, side-step, clap, robot, headbang and spin.
- *About Mixie* in the menu.

## 1.0.0
- First public release: a slider per app, profiles, in-game hotkeys, lowering the music when someone talks,
  now playing with media buttons, audio device switching, compact mode, tray icon, neon sound waves and Mixie
  with outfits.
