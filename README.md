<p align="center">
  <img src="docs/banner.png" alt="Mixie – a per-app volume mixer for Windows with a pixel buddy who dances to your music" width="100%">
</p>

<p align="center">
  <a href="../../releases/latest"><img src="https://img.shields.io/github/v/release/Modda-ctrl/Mixie?style=for-the-badge&color=ff78be&label=download" alt="Latest release"></a>
  <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Windows 10 and 11">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10 or newer">
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Modda-ctrl/Mixie?style=for-the-badge&color=8a5cff" alt="MIT license"></a>
</p>

<p align="center">
  <a href="#-install"><b>Install</b></a> ·
  <a href="#-features"><b>Features</b></a> ·
  <a href="#-hotkeys"><b>Hotkeys</b></a> ·
  <a href="#-how-it-works"><b>How it works</b></a> ·
  <a href="CHANGELOG.md"><b>Changelog</b></a>
</p>

---

**Mixie** gives every program that is playing sound its own slider – Spotify, your browser, your game,
Discord – in one small window you can park on your second monitor. It was made for one simple thing:
turning the music down when the game gets loud, without alt-tabbing into the Windows volume mixer.

And while you play, **Mixie** – the pixel buddy in the corner – dances to your music, right on the beat.

<p align="center">
  <img src="docs/header.gif" alt="Neon sound waves and Mixie dancing" width="584">
</p>

## ✨ Features

<p align="center">
  <img src="docs/showcase.png" alt="The Mixie window, in normal and compact mode" width="100%">
</p>

- **A slider per app.** Every program that plays sound gets a card with its real icon. Drag the slider,
  scroll over a card, or hit the speaker button to mute it.
- **Now playing.** Song, artist and tempo from Spotify or YouTube, with previous, play/pause and next.
- **Profiles.** *Game* turns the music down and the game up, *Music* does the opposite – or save your own.
- **Switch audio device** between headphones, speakers and monitors in two clicks.
- **Your microphone too.** Its own slider and mute button – and a hotkey to mute it mid-game.
- **Play an app on another device** – right-click a card: the game in your headphones, Spotify on the speakers.
- **Your own profiles**, and an automatic switch to the *Game* profile while a game is open.
- **Compact mode**, **always on top**, **minimize to the tray**, **start with Windows** – and it remembers where
  you put it. Mixie tells you when there's a new version.

<p align="center">
  <img src="docs/dance.gif" alt="Mixie dancing in time with a 125 BPM song, with the beat lights" width="100%">
</p>

- **She dances on the beat.** Mixie works out the tempo (BPM) and where the beats fall, so every move,
  bounce and music note lands in time.
- **17 dance moves** – from swaying, bopping and the twist to the moonwalk, high kicks, fist pumps,
  headbanging and spins – picked to fit the music: calm songs get the gentle ones, heavy bass gets the wild ones.
  She keeps the beat through breaks without drums, so she never stops mid-song.
- **She has a life of her own.** She blinks, looks around and stretches while she waits for music, falls
  asleep after a while, waves when you hover over her and has something to say when you click her.
- **Watch mode.** Put on a film, a series or a Twitch stream and she curls up for a nap – a music video still
  gets a dance. She goes wild on the drop, covers her ears when it's too loud and gets sleepy late at night.
- **Neon sound waves** in an early-2010s style follow the bass, mids and treble, and change colour
  with every new song.

<p align="center">
  <img src="docs/moves.png" alt="Mixie's 17 dance moves" width="100%">
</p>

<p align="center">
  <img src="docs/outfits-showcase.png" alt="Thirteen outfits, from a bow and headphones to a crown, bunny ears and a party hat" width="100%">
</p>

- **Thirteen outfits.** Bow, headphones, cat ears, bunny ears, crown, flower crown, beanie, cap, sunglasses,
  devil horns, witch hat, santa hat and a party hat – or *Automatic*, which picks one by season. Snow falls in
  December, bats fly in October, and on your birthday (set it in the menu) she throws confetti. Her dress follows
  the colour of the waves.

<p align="center">
  <img src="docs/gaming.png" alt="Hotkeys that work in-game, and the music stepping aside when someone talks on Discord" width="100%">
</p>

- **Hotkeys that work in-game.** Change the music or the game you are in without leaving it.
- **The music steps aside when someone talks.** Mixie listens to Discord (and TeamSpeak, Mumble, Teams) and
  dips Spotify and your browser while someone is speaking, then brings them back.

## 📥 Install

**The easy way – no Python needed (Windows 10 or 11):**

1. Download **`Mixie.exe`** from the [latest release](../../releases/latest).
2. Double-click it. The first start puts a **Mixie** shortcut on your desktop and in the Start menu.

> [!NOTE]
> Mixie.exe is not signed, so Windows SmartScreen may say *Windows protected your PC*.
> Click **More info → Run anyway**. The exe is built from this repository by a
> [GitHub workflow](.github/workflows/build-exe.yml) you can read.

**With Python instead:** install **Python 3.10 or newer** from [python.org](https://www.python.org/downloads/)
(tick *Add python.exe to PATH*), download **`Install Mixie.bat`** from the release and double-click it.
It installs Mixie into `%LOCALAPPDATA%\Mixie`, sets up the packages and starts it. Running it again updates
Mixie and keeps your settings. Both ways share the same settings.

<details>
<summary><b>Run from source instead</b></summary>

```bat
git clone https://github.com/Modda-ctrl/Mixie.git
cd Mixie
py -m pip install -r requirements.txt
pyw mixie.py
```

Mixie also installs any missing packages by itself on the first start.
</details>

## ⌨️ Hotkeys

They work everywhere – including inside full-screen games. Switch them off in the **⋯** menu.

| Keys | Action |
| --- | --- |
| <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>↑</kbd> / <kbd>↓</kbd> | Music louder / quieter (Spotify first) |
| <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>Page Up</kbd> / <kbd>Page Down</kbd> | The program you are in (your game) louder / quieter |
| <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>M</kbd> | Mute / unmute the music |
| <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>Space</kbd> | Play / pause |
| <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>←</kbd> / <kbd>→</kbd> | Previous / next track |
| <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>1</kbd> / <kbd>2</kbd> | Game profile / Music profile |
| <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>N</kbd> | Mute / unmute your microphone |
| <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>H</kbd> | Show / hide Mixie |
| <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>D</kbd> | Debug mode on / off |

## 💡 Tips

- The buttons at the top right are **Outfit**, **Audio device**, **Profile** and **⋯** (settings).
- **Too many cards?** Point at one and click the **(-)** on its icon to hide it. Hidden programs that play sound
  wait as small chips in the *Hidden* strip at the bottom – click one to bring it back.
- **Right-click** a card for more: send it to another sound device, switch profile.
- **Click Mixie.** Try it while she's asleep, too.

<p align="center">
  <img src="docs/settings.png" alt="The settings panel and the outfit picker" width="100%">
</p>

## 🔧 How it works

| What | How |
| --- | --- |
| Per-app volume, mute, devices | Windows Core Audio through [pycaw](https://github.com/AndreMiras/pycaw) |
| Sound waves | WASAPI loopback capture through [SoundCard](https://github.com/bastibe/SoundCard) and an FFT with [NumPy](https://numpy.org/) |
| Tempo and beat sync | Spectral-flux onsets, autocorrelation for the tempo (kick drum and bass count extra) and a comb filter for where the beats fall |
| Now playing | The window titles of Spotify and your browser – no logins, permissions or APIs |
| Media buttons | Standard Windows media keys |
| Lowering the music | The live level of the voice-chat app's audio session |
| Watch mode | Video sites and players in the window titles, plus no steady beat in the sound |
| One app on another device | Windows' per-app device setting (the one EarTrumpet uses), in a separate helper process |
| Tray icon | [pystray](https://github.com/moses-palmer/pystray) |
| Interface | Tkinter, with everything drawn by [Pillow](https://python-pillow.org/) at 3× and scaled down for smooth edges |

The waves, the tray icon and song detection are optional – if a package is missing, Mixie still runs.
Only prebuilt packages are installed (`--only-binary`), so nothing is compiled on your machine.

## 🩺 Troubleshooting

- **Mixie closed or something went wrong.** Errors are written to `crash_log.txt` in `%LOCALAPPDATA%\Mixie`.
  After an unexpected close, Mixie starts in a safe mode (without audio capture and song detection).
  Please [open an issue](../../issues/new/choose) and paste the log.
- **A hotkey does nothing.** Another program may already use it – **⋯ → Show hotkeys…** lists the taken ones.
- **Something looks off (timing, freezes, lag).** Turn on **⋯ → Debug mode** (or <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>D</kbd>).
  Mixie shows what she measures and writes `debug_log.txt` – **⋯ → Open Mixie's folder** – attach it to an issue.
- **Mixie uses too much of a slow PC.** Turn on **⋯ → Low power mode** (half the frame rate, no snow).
- **A game shows a letter instead of its icon.** Some games with anti-cheat don't let other programs read
  their icon.

## 🛠️ Building

- **Mixie.exe:** `packaging\build_exe.bat` (PyInstaller). GitHub builds and self-tests it on every pull request,
  and attaches it to the release when a `v*` tag is pushed.
- **Install Mixie.bat:** a single file that contains both the installer and `mixie.py`. Rebuild it with
  `py installer\build_installer.py`.

## 🔒 Privacy and security

No accounts and no tracking. The only time Mixie goes online is a daily check for a new version, and you can
switch it off. Song names stay on your PC. Every release has checksums, and Mixie.exe comes with a signed build
attestation, so you can check that it was built from this code. More in [SECURITY.md](SECURITY.md).

## ❤️ Credits

Mixie is made by **[Modda-ctrl](https://github.com/Modda-ctrl)** – the app, the pixel art and the dance moves.
Bug reports and ideas are very welcome in the [issues](../../issues/new/choose).

## 📄 License

[MIT](LICENSE) © Modda-ctrl
