# Contributing to Mixie

Thanks for wanting to help! Mixie is a small, friendly project. Ideas, bug reports, pixel art and code are all
welcome, and **you don't need to be an expert**: a new outfit for Mixie is a few lines of pixel coordinates.

## Ways to help

- 🐛 **Report a bug.** [Open an issue](../../issues/new/choose). If you can, turn on **⋯ → Debug mode** for a
  minute and attach `debug_log.txt` (from **⋯ → Open Mixie's folder**).
- 💡 **Suggest an idea.** Use the *Feature request* template.
- 🎨 **Give Mixie something new.** Add an outfit, a dance move or a seasonal effect. See below.
- 🌱 **Pick a [good first issue](../../labels/good%20first%20issue).** They're small and come with pointers.

## Running Mixie from source

You need Windows 10 or 11 and Python 3.10 or newer.

```bat
git clone https://github.com/Modda-ctrl/Mixie.git
cd Mixie
py -m pip install -r requirements.txt
py mixie.py
```

Everything lives in `mixie.py`. Search for the names below to find your way around.

## Adding an outfit

1. In `draw_accessory()`, add an `elif acc == "yourhat":` block. Coordinates are relative to Mixie's head:
   x goes from 0 to 15, row 0 is the top of her hair, and negative rows are above her head (up to −6).
   Use `at(x, y, colour)` for one pixel and `span(y, x_from, x_to, colour)` for a row.
   Colours are the letters in `PAL`, for example `"R"` red, `"Y"` yellow, `"W"` white, `"K"` outline. You can add
   your own. The black outline around everything is drawn automatically.
2. Add the name to `OUTFITS` and `OUTFIT_NAMES`.
3. Optional: give her something to say in `set_outfit()`.

## Adding a dance move

1. Make a list of frames like `TWIST_FRAMES`. Each frame is a `dict`:
   - `la` / `ra`: arm poses from `ARMS`. You can add new poses there.
   - `b`: how far down her body is (0–2).
   - `sway`: how her pigtails swing (−2 to 2).
   - `legs`: `both`, `left`, `right`, `jump`, `kickl` or `kickr`.
   - Optional: `eyes`, `mouth`, `sing`, `note`, `dx` (sideways step), `hb` (head bob) and `back` (seen from behind).
2. Add it to `DANCE_MOVES` and to one or more of the pools in `MOVE_POOLS` (`calm`, `dance`, `hype`).
3. Moves play **two frames per beat** by default. Slow ones can use one, set in `MOVE_FPB`.

## Before you open a pull request

- Start Mixie and check that your change works and nothing else broke. Try compact mode and both a light and a
  heavy song if you touched the dancing.
- Keep the style of the code around you. Name things plainly, and leave short comments that say *why*.
- `py -m pip install pyflakes` and then `py -m pyflakes mixie.py` should report nothing.
- Don't rebuild `Install Mixie.bat` or `Mixie.exe` in your PR. That happens when a release is made.
- A screenshot or GIF in the PR helps a lot for anything visual.

Every pull request is built and self-tested on Windows automatically. You'll see the result in the PR.

## Be kind

Be friendly and patient with each other. Everyone was new once.

By contributing, you agree that your work is released under the project's [MIT license](LICENSE).
