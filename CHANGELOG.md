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
- Six new outfits: crown, bunny ears, flower crown, beanie, cap and devil horns – with new seasonal picks.
- New settings panel with switches, and a new outfit picker with Mixie in every outfit.
- A bigger Mixie in the app and desktop icon.
- Changing outfit or song colour no longer causes a short stutter.

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
