"""
Mixie – a per-app volume mixer with a dancing pixel buddy (Windows).
Made by Modda-ctrl – https://github.com/Modda-ctrl/mixie

Shows a slider for every program that is playing sound right now (Spotify, Firefox,
games, Discord ...) plus the master volume. The window remembers where it was, so it
opens on your second monitor next time.

  * Click/drag a slider, or scroll the mouse wheel over a card
  * The speaker button mutes that program
  * Buttons in the top right: outfit, audio device, profile and menu
  * Right-click: hide a program / show hidden ones / create shortcut
  * "Always on top" keeps the window above other windows

The first start creates a "Mixie" shortcut on the desktop and in the Start menu.
"""
import base64
import ctypes
import importlib
import importlib.util
import json
import math
import queue
import re
import random
import os
import subprocess
import sys
import tempfile
import threading
import time
import zlib
import tkinter as tk
from tkinter import messagebox

APP_NAME = "Mixie"
APP_VERSION = "1.2.2"
AUTHOR = "Modda-ctrl"
REPO_URL = "https://github.com/Modda-ctrl/mixie"

# ---------------------------------------------------------------- crash reporting
# Everything that goes wrong is written to crash_log.txt in the program folder (hard crashes too).
import faulthandler  # noqa: E402
import traceback  # noqa: E402

_HERE0 = os.path.dirname(os.path.abspath(__file__))
CRASH_LOG = os.path.join(_HERE0, "crash_log.txt")
PREV_CRASH_LOG = os.path.join(_HERE0, "crash_log_previous.txt")
_RUN_MARK = os.path.join(_HERE0, ".running")
try:
    if os.path.exists(CRASH_LOG) and os.path.getsize(CRASH_LOG) > 0:
        os.replace(CRASH_LOG, PREV_CRASH_LOG)
    _crash_file = open(CRASH_LOG, "w", encoding="utf-8")
    _crash_file.write(f"{APP_NAME} {APP_VERSION} – Python {sys.version.split()[0]} – {sys.executable}\n")
    _crash_file.flush()
    faulthandler.enable(_crash_file)
except Exception:
    _crash_file = None


def log_error(text):
    try:
        if _crash_file:
            _crash_file.write(time.strftime("[%H:%M:%S] ") + text + "\n")
            _crash_file.flush()
    except Exception:
        pass


def report_crash(text, title="Mixie crashed"):
    log_error(text)
    try:
        root = tk._default_root or tk.Tk()
        if root is not tk._default_root:
            root.withdraw()
        messagebox.showerror(title, text[-1500:] + f"\n\nThe error was saved to:\n{CRASH_LOG}")
    except Exception:
        pass


def _excepthook(kind, value, tb):
    report_crash("".join(traceback.format_exception(kind, value, tb)))


sys.excepthook = _excepthook

# Safe mode: if the previous start died within 20 seconds, start without audio capture / song info.
SAFE_MODE = False
try:
    with open(_RUN_MARK, encoding="utf-8") as _f:
        _start, _beat = (float(v) for v in _f.read().split())
    SAFE_MODE = _beat - _start < 20
except Exception:
    pass


def run_mark(start=None):
    try:
        with open(_RUN_MARK, "w", encoding="utf-8") as f:
            f.write(f"{start or time.time()} {time.time()}")
    except Exception:
        pass


def clear_run_mark():
    try:
        os.remove(_RUN_MARK)
    except Exception:
        pass


_STARTED = time.time()
APP_ID = "Mixie.App"

# Sharp text on scaled displays (must be done before the window is created)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass
# Own icon in the taskbar (instead of the Python icon)
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
except Exception:
    pass

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# ---------------------------------------------------------------- packages
REQUIRED = {"pycaw": "pycaw", "PIL": "pillow"}           # required
# Extras: the waves that follow the bass, and the tray icon. The program works without them.
EXTRAS = {"soundcard": ["soundcard"], "numpy": ["numpy"], "pystray": ["pystray"]}
EXTRAS_VERSION = "4"
_EXTRAS_MARK = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".extras_installed")
PIP_TIMEOUT = 240


def _has(mod):
    try:
        return importlib.util.find_spec(mod) is not None
    except Exception:
        return False


def _missing(mods=None):
    mods = REQUIRED if mods is None else mods
    return [pip for mod, pip in mods.items() if not _has(mod)]


def _missing_extras():
    try:
        with open(_EXTRAS_MARK, encoding="utf-8") as f:
            if f.read().strip() == EXTRAS_VERSION:
                return []  # already tried – don't retry on every start
    except Exception:
        pass
    return [pips for mod, pips in EXTRAS.items() if not _has(mod)]


def console_python():
    exe = sys.executable
    folder, name = os.path.split(exe)
    if name.lower() == "pythonw.exe" and os.path.exists(os.path.join(folder, "python.exe")):
        return os.path.join(folder, "python.exe")
    return exe


def window_python():
    exe = sys.executable
    folder, name = os.path.split(exe)
    if name.lower() == "python.exe" and os.path.exists(os.path.join(folder, "pythonw.exe")):
        return os.path.join(folder, "pythonw.exe")
    return exe


def _pip(packages):
    """Installs into exactly the Python that runs the program. Only prebuilt packages
    (--only-binary), so pip never tries to build from source and gets stuck."""
    exe = console_python()
    base = [exe, "-m", "pip", "install", "--only-binary=:all:", "--disable-pip-version-check",
            "--no-input"]
    out = ""
    for extra in (["--user"], []):
        try:
            res = subprocess.run(base + extra + list(packages), capture_output=True, text=True,
                                 creationflags=NO_WINDOW, timeout=PIP_TIMEOUT)
        except subprocess.TimeoutExpired:
            return False, out + "\nTook too long – aborted."
        out += (res.stdout or "") + (res.stderr or "")
        if res.returncode == 0:
            return True, out
    return False, out


def install_with_window(groups):
    """Installs the package groups in a background thread while a small window shows progress.
    The window keeps responding the whole time (does not freeze)."""
    state = {"i": 0, "done": False, "log": ""}

    def work():
        for i, pkgs in enumerate(groups):
            state["i"] = i
            ok, out = _pip(pkgs)
            state["log"] += f"\n== {' '.join(pkgs)}: {'OK' if ok else 'FAILED'}\n" + out[-1500:]
        state["done"] = True

    root = tk.Tk()
    root.title(APP_NAME)
    root.resizable(False, False)
    root.configure(bg="#16171c")
    root.protocol("WM_DELETE_WINDOW", lambda: None)  # don't close halfway
    lbl = tk.Label(root, bg="#16171c", fg="#ffffff", font=("Segoe UI", 11), padx=34, pady=10,
                   text="Getting Mixie ready (first start only)")
    lbl.pack(pady=(14, 0))
    sub = tk.Label(root, bg="#16171c", fg="#9a9daa", font=("Segoe UI", 10), padx=34, pady=4)
    sub.pack()
    bar = tk.Canvas(root, width=300, height=6, bg="#2c2f38", highlightthickness=0)
    bar.pack(pady=(6, 20))
    dot = bar.create_rectangle(0, 0, 70, 6, fill="#ff8cc6", outline="")
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    root.geometry(f"+{(root.winfo_screenwidth() - w) // 2}+{(root.winfo_screenheight() - h) // 3}")
    threading.Thread(target=work, daemon=True).start()
    pos = [0, 6]

    def tick():
        if state["done"]:
            root.destroy()
            return
        names = " ".join(groups[min(state["i"], len(groups) - 1)])
        sub.config(text=f"Downloading {names} ({state['i'] + 1} of {len(groups)}) ...")
        pos[0] += pos[1]
        if pos[0] <= 0 or pos[0] >= 230:
            pos[1] = -pos[1]
        bar.coords(dot, pos[0], 0, pos[0] + 70, 6)
        root.after(30, tick)

    tick()
    root.mainloop()
    return state["log"]


_need = [[p] for p in _missing()]
_need_extras = _missing_extras()
if _need or _need_extras:
    _log = ""
    try:
        _log = install_with_window(_need + _need_extras)
    except Exception as _e:
        _log = str(_e)
    log_error("Package install:" + _log)
    if _need_extras:
        try:
            with open(_EXTRAS_MARK, "w", encoding="utf-8") as _f:
                _f.write(EXTRAS_VERSION)
        except Exception:
            pass
    import site
    importlib.reload(site)
    importlib.invalidate_caches()
    try:
        sys.path.append(site.getusersitepackages())
    except Exception:
        pass
    if _missing():
        report_crash(
            "Could not install: " + ", ".join(_missing()) + "\n\n"
            f"Python in use:\n{sys.executable}\n\n"
            "Open Command Prompt and run:\n"
            f'  "{console_python()}" -m pip install pycaw pillow\n\n'
            "Error message:\n" + _log[-800:], title=APP_NAME)
        sys.exit(1)

from pycaw.pycaw import AudioUtilities  # noqa: E402
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageTk  # noqa: E402

_RS = getattr(Image, "Resampling", Image)
LANCZOS, NEAREST, BILINEAR = _RS.LANCZOS, _RS.NEAREST, _RS.BILINEAR

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.abspath(__file__)
CONFIG_PATH = os.path.join(HERE, "mixie_config.json")
ICON_PATH = os.path.join(HERE, "mixie.ico")
ICON_VERSION = 3
REFRESH_MS = 1500
DANCE_MS = 140
WAVE_MS = 33  # sound waves: ~30 frames per second
SS = 3  # supersampling: shapes are drawn 3x larger and scaled down = smooth edges

# These are shown first (in this order) when they play sound
PRIORITY = ["spotify.exe", "firefox.exe"]
PRETTY = {
    "__master__": "Master volume",
    "__system__": "System sounds",
    "spotify.exe": "Spotify",
    "firefox.exe": "Firefox",
    "chrome.exe": "Chrome",
    "msedge.exe": "Edge",
    "discord.exe": "Discord",
    "steam.exe": "Steam",
    "steamwebhelper.exe": "Steam",
}

# ---------------------------------------------------------------- look and feel
BG_BASE = (6, 7, 10)
BG_GLOW = (26, 29, 40)
CARD = (27, 28, 33, 240)
CARD_ACTIVE = (44, 46, 54, 250)
WHITE = (255, 255, 255, 255)
TEXT = (255, 255, 255, 255)
SUB = (150, 153, 165, 255)
TRACK = (60, 62, 72, 255)
BTN = (52, 54, 63, 255)
TILE = (40, 41, 48, 255)
DIM = (92, 95, 108, 255)
MUTE_ORANGE = (255, 138, 0, 255)
DARK = (14, 15, 19, 255)
BLUE = (0, 112, 209, 255)
PINK = (255, 140, 198, 255)
# (base speed, waves across the width, strength, band: 0 bass, 1 low-mid, 2 mid, 3 treble)
WAVES = [(1.6, 1.2, 1.00, 0),
         (-2.0, 1.7, 0.75, 1),
         (2.4, 2.4, 0.70, 2),
         (-3.2, 3.4, 0.45, 3)]
WAVE_SS = 3  # the waves are drawn 3x larger and scaled down = smooth lines
# Neon colours (early 2010s). Every song gets one of these – the same song always gets the same one.
PALETTES = [
    [(0, 200, 255), (110, 90, 255), (255, 60, 190), (255, 255, 255)],   # cyan / purple / pink
    [(0, 255, 140), (0, 190, 255), (210, 255, 60), (255, 255, 255)],    # green dubstep
    [(255, 120, 0), (255, 40, 90), (255, 210, 60), (255, 240, 220)],    # sunset
    [(180, 70, 255), (255, 90, 200), (255, 170, 120), (255, 255, 255)], # vaporwave
    [(40, 120, 255), (0, 230, 255), (150, 220, 255), (255, 255, 255)],  # is
    [(255, 40, 60), (255, 0, 200), (255, 140, 40), (255, 230, 230)],    # red laser
    [(170, 255, 0), (0, 255, 200), (0, 140, 255), (255, 255, 255)],     # lime / turquoise
]
BAND_EDGES = [(25, 160), (160, 600), (600, 3500), (3500, 14000)]

APP_COLORS = {
    "__master__": (0, 112, 209),
    "__system__": (88, 94, 112),
    "spotify.exe": (29, 185, 84),
    "firefox.exe": (255, 113, 57),
    "discord.exe": (88, 101, 242),
    "chrome.exe": (66, 133, 244),
    "msedge.exe": (12, 140, 233),
    "steam.exe": (42, 111, 176),
    "steamwebhelper.exe": (42, 111, 176),
}
FALLBACK_COLORS = [(163, 113, 247), (229, 83, 75), (45, 191, 168),
                   (232, 163, 61), (224, 93, 155), (61, 143, 232)]

FONT_FILES = {
    "semilight": ["segoeuisl.ttf", "C:/Windows/Fonts/segoeuisl.ttf", "DejaVuSans.ttf"],
    "light": ["segoeuil.ttf", "C:/Windows/Fonts/segoeuil.ttf", "DejaVuSans-ExtraLight.ttf", "DejaVuSans.ttf"],
    "regular": ["segoeui.ttf", "C:/Windows/Fonts/segoeui.ttf", "DejaVuSans.ttf"],
    "semi": ["seguisb.ttf", "C:/Windows/Fonts/seguisb.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"],
}

# Sizes (at 100 % scale, multiplied by the display scaling)
PAD = 24
HEADER = 172
SPRITE_Y = 16      # the buddy, top right (low enough that hats never get cut off, even mid-jump)
WAVE_CY = 54       # centre line of the waves
WAVE_AMP = 34      # largest swing
TITLE_Y = 116      # the name, below the waves
SUB_Y = 146
BTN_Y = (122, 150) # the buttons to the right of the name
MARGIN = 16  # room around each card for the grow effect and glow
LAYOUTS = {
    "normal": dict(width=560, row_h=78, gap=12, icon=44, icon_x=20, icon_img=32, name_x=80, name_y=28,
                   name_font=15, slider_y=52, num_font=28, num_x=70, mute_x=38, mute_r=19, slider_r=132,
                   title_font=28, media_h=72, compact=False),
    "compact": dict(width=440, row_h=56, gap=8, icon=34, icon_x=14, icon_img=24, name_x=60, name_y=19,
                    name_font=13, slider_y=39, num_font=21, num_x=56, mute_x=30, mute_r=15, slider_r=110,
                    title_font=22, media_h=60, compact=True),
}

# ------------------------------------------------------------ app categories (profiles, ducking)
MUSIC_APPS = {"spotify.exe", "firefox.exe", "chrome.exe", "msedge.exe", "brave.exe", "opera.exe",
              "vlc.exe", "foobar2000.exe", "musicbee.exe", "applemusic.exe", "itunes.exe", "tidal.exe",
              "deezer.exe", "aimp.exe", "winamp.exe"}
VOICE_APPS = {"discord.exe", "discordptb.exe", "discordcanary.exe", "teamspeak.exe",
              "ts3client_win64.exe", "mumble.exe", "teams.exe", "ms-teams.exe"}


def category(key):
    if key == "__master__":
        return "master"
    if key == "__system__":
        return "system"
    if key in MUSIC_APPS:
        return "music"
    if key in VOICE_APPS:
        return "voice"
    return "game"


PROFILE_NAMES = ["Game", "Music"]
DEFAULT_PROFILES = {"Game": {"music": 25, "voice": 100, "game": 100},
                    "Music": {"music": 80, "voice": 70, "game": 35}}

# ------------------------------------------------------------ hotkeys
MOD_ALT, MOD_CONTROL = 0x1, 0x2
CA = MOD_CONTROL | MOD_ALT
HOTKEYS = [
    (1, CA, 0x26, ("music", 5), "Ctrl + Alt + Up", "Music louder"),
    (2, CA, 0x28, ("music", -5), "Ctrl + Alt + Down", "Music quieter"),
    (3, CA, 0x21, ("focus", 5), "Ctrl + Alt + Page Up", "Game (the program you are in) louder"),
    (4, CA, 0x22, ("focus", -5), "Ctrl + Alt + Page Down", "Game (the program you are in) quieter"),
    (5, CA, 0x4D, ("mute_music",), "Ctrl + Alt + M", "Mute / unmute the music"),
    (6, CA, 0x20, ("media", "play"), "Ctrl + Alt + Space", "Play / pause"),
    (7, CA, 0x27, ("media", "next"), "Ctrl + Alt + Right", "Next track"),
    (8, CA, 0x25, ("media", "prev"), "Ctrl + Alt + Left", "Previous track"),
    (9, CA, 0x31, ("profile", "Game"), "Ctrl + Alt + 1", "Game profile"),
    (10, CA, 0x32, ("profile", "Music"), "Ctrl + Alt + 2", "Music profile"),
]
MEDIA_VK = {"play": 0xB3, "next": 0xB0, "prev": 0xB1}

# ------------------------------------------------------------ outfits
OUTFITS = ["auto", "bow", "headphones", "cat", "santa", "witch", "sunglasses"]
OUTFIT_NAMES = {"auto": "Automatic (by season)", "bow": "Bow", "headphones": "Headphones",
                "cat": "Cat ears", "santa": "Santa hat", "witch": "Witch hat", "sunglasses": "Sunglasses"}


def season_outfit():
    m = time.localtime().tm_mon
    if m == 12:
        return "santa"
    if m == 10:
        return "witch"
    if m in (6, 7, 8):
        return "sunglasses"
    return "bow"


def pretty_name(key):
    if key in PRETTY:
        return PRETTY[key]
    name = key[:-4] if key.endswith(".exe") else key
    return (name[:1].upper() + name[1:])[:18]


def app_color(key):
    if key in APP_COLORS:
        return APP_COLORS[key] + (255,)
    return FALLBACK_COLORS[sum(map(ord, key)) % len(FALLBACK_COLORS)] + (255,)


_font_cache = {}


def font(kind, px):
    k = (kind, px)
    if k not in _font_cache:
        f = None
        for name in FONT_FILES[kind]:
            try:
                f = ImageFont.truetype(name, px)
                break
            except Exception:
                continue
        if f is None:
            try:
                f = ImageFont.load_default(px)
            except Exception:
                f = ImageFont.load_default()
        _font_cache[k] = f
    return _font_cache[k]


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


def point_on_screen(x, y):
    """Is the point on any connected monitor? (in case the second monitor is unplugged)"""
    try:
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        return bool(ctypes.windll.user32.MonitorFromPoint(POINT(x + 40, y + 20), 0))
    except Exception:
        return True


def dark_titlebar(win):
    """Dark title bar on Windows 10/11."""
    try:
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        val = ctypes.c_int(1)
        for attr in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(val), ctypes.sizeof(val)) == 0:
                break
    except Exception:
        pass


# ---------------------------------------------------------------- app icon

ICON_STYLE = {"acc": "headphones", "D": (0, 200, 255), "d": (0, 132, 168)}


def make_app_icon(size=256):
    """The app icon: Mixie's head with her headphones, in pixel art, on a dark neon tile."""
    f = dict(FRAMES[0], note=None, la="down", ra="down", eyes="happy", sing=False)
    head = make_sprite(f, ICON_STYLE).crop((1, SPRITE_TOP, 23, SPRITE_TOP + 19))   # 22 x 19 pixels
    s = size * 4
    tile = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    grad = Image.new("RGBA", (s, s))
    gd = ImageDraw.Draw(grad)
    for y in range(s):
        t = y / s
        c = tuple(round(a + (b - a) * t) for a, b in zip((44, 30, 78), (10, 10, 20)))
        gd.line((0, y, s, y), fill=c + (255,))
    glow = Image.new("L", (s, s), 0)        # soft pink glow behind her head
    ImageDraw.Draw(glow).ellipse((s * 0.14, s * 0.12, s * 0.86, s * 0.84), fill=120)
    glow = glow.filter(ImageFilter.GaussianBlur(s * 0.09))
    grad.paste(Image.new("RGBA", (s, s), (255, 120, 190, 255)), (0, 0), glow)
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.23), fill=255)
    tile.paste(grad, (0, 0), mask)
    ImageDraw.Draw(tile).rounded_rectangle((s * 0.012, s * 0.012, s * 0.988, s * 0.988), radius=int(s * 0.22),
                                           outline=(255, 255, 255, 45), width=max(2, int(s * 0.012)))
    tile = tile.resize((size, size), LANCZOS)
    k = int(size * 0.9 // 22)
    if k >= 1:      # whole pixels: crisp pixel art
        h = head.resize((22 * k, 19 * k), NEAREST)
    else:           # tiny sizes: scale down smoothly
        h = head.resize((22 * 11, 19 * 11), NEAREST).resize((round(size * 0.9), round(size * 0.9 * 19 / 22)),
                                                            LANCZOS)
    tile.alpha_composite(h, ((size - h.width) // 2, (size - h.height) // 2 + max(0, size // 64)))
    return tile


def save_ico(path, sizes=(16, 20, 24, 32, 40, 48, 64, 128, 256)):
    """Writes an .ico with plain 32-bit images (not PNG). Pillow's own .ico stores PNG
    inside, which neither Tk nor some parts of Windows can read – then the Python icon shows."""
    import struct
    flip = getattr(Image, "Transpose", Image).FLIP_TOP_BOTTOM
    blobs = []
    for sz in sizes:
        im = make_app_icon(sz)
        hdr = struct.pack("<IiiHHIIiiII", 40, sz, sz * 2, 1, 32, 0, 0, 0, 0, 0, 0)
        pixels = im.convert("RGBA").transpose(flip).tobytes("raw", "BGRA")
        and_mask = bytes(((sz + 31) // 32) * 4 * sz)
        blobs.append(hdr + pixels + and_mask)
    out = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    for sz, blob in zip(sizes, blobs):
        out += struct.pack("<BBBBHHII", sz % 256, sz % 256, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    with open(path, "wb") as f:
        f.write(out + b"".join(blobs))


def ensure_icon_file(cfg):
    if os.path.exists(ICON_PATH) and cfg.get("icon_v") == ICON_VERSION:
        return ICON_PATH
    try:
        save_ico(ICON_PATH)
        cfg["icon_v"] = ICON_VERSION
        try:   # ask Explorer to refresh icons, so shortcuts show the new one
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
        except Exception:
            pass
        return ICON_PATH
    except Exception:
        return ICON_PATH if os.path.exists(ICON_PATH) else None


_icon_handles = []


def set_window_icon(win, ico):
    """Sets the icon directly on the window, so it shows in the title bar, taskbar and Alt+Tab."""
    if not ico:
        return
    try:
        user32 = ctypes.windll.user32
        H = ctypes.c_void_p
        user32.GetParent.restype = H
        user32.GetParent.argtypes = [H]
        user32.LoadImageW.restype = H
        user32.LoadImageW.argtypes = [H, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        user32.SendMessageW.restype = H
        user32.SendMessageW.argtypes = [H, ctypes.c_uint, H, H]
        win.update_idletasks()
        hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
        for which, metric in ((1, 11), (0, 49)):  # ICON_BIG/SM_CXICON, ICON_SMALL/SM_CXSMICON
            size = user32.GetSystemMetrics(metric)
            h = user32.LoadImageW(None, ico, 1, size, size, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
            if h:
                _icon_handles.append(h)
                user32.SendMessageW(hwnd, 0x80, which, h)  # WM_SETICON
    except Exception:
        pass


# ---------------------------------------------------------------- desktop shortcut

FOLDER_DESKTOP = "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}"
FOLDER_PROGRAMS = "{A77F5D77-2E2B-44C3-A6A2-ABA601054A51}"


def known_folder(guid):
    """The right desktop, even when it lives in OneDrive."""
    try:
        class GUID(ctypes.Structure):
            _fields_ = [("a", ctypes.c_ulong), ("b", ctypes.c_ushort), ("c", ctypes.c_ushort),
                        ("d", ctypes.c_ubyte * 8)]
        g = GUID()
        ctypes.windll.ole32.CLSIDFromString(ctypes.c_wchar_p(guid), ctypes.byref(g))
        out = ctypes.c_void_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(out)) == 0:
            path = ctypes.wstring_at(out.value)
            ctypes.windll.ole32.CoTaskMemFree(out)
            return path
    except Exception:
        pass
    return None


def shortcut_targets():
    desktop = known_folder(FOLDER_DESKTOP) or os.path.join(os.path.expanduser("~"), "Desktop")
    links = [os.path.join(desktop, APP_NAME + ".lnk")]
    programs = known_folder(FOLDER_PROGRAMS)
    if programs:
        links.append(os.path.join(programs, APP_NAME + ".lnk"))
    return links


def _lnk_comtypes(links, target, args, icon):
    import comtypes
    import comtypes.client
    ws = comtypes.client.CreateObject("WScript.Shell", dynamic=True)   # main thread only
    for path in links:
        sc = ws.CreateShortcut(path)
        sc.TargetPath = target
        sc.Arguments = args
        sc.WorkingDirectory = HERE
        sc.IconLocation = icon
        sc.Description = APP_NAME
        sc.Save()
        del sc
    del ws


def _lnk_vbscript(links, target, args, icon):
    def q(v):
        return '"' + v.replace('"', '""') + '"'
    lines = ['Set ws = CreateObject("WScript.Shell")']
    for path in links:
        lines += [f"Set s = ws.CreateShortcut({q(path)})", f"s.TargetPath = {q(target)}",
                  f"s.Arguments = {q(args)}", f"s.WorkingDirectory = {q(HERE)}",
                  f"s.IconLocation = {q(icon)}", f"s.Description = {q(APP_NAME)}", "s.Save"]
    vbs = os.path.join(tempfile.gettempdir(), "mixie_shortcut.vbs")
    with open(vbs, "w", encoding="utf-16") as f:
        f.write("\r\n".join(lines) + "\r\n")
    res = subprocess.run(["cscript", "//nologo", vbs], capture_output=True, text=True,
                         creationflags=NO_WINDOW, timeout=30)
    if res.returncode != 0:
        raise RuntimeError((res.stderr or res.stdout).strip())


def _lnk_powershell(links, target, args, icon):
    def q(v):
        return "'" + v.replace("'", "''") + "'"
    script = "$ws = New-Object -ComObject WScript.Shell\n"
    for path in links:
        script += (f"$s = $ws.CreateShortcut({q(path)}); $s.TargetPath = {q(target)}; "
                   f"$s.Arguments = {q(args)}; $s.WorkingDirectory = {q(HERE)}; "
                   f"$s.IconLocation = {q(icon)}; $s.Description = {q(APP_NAME)}; $s.Save()\n")
    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    res = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc],
                         capture_output=True, text=True, creationflags=NO_WINDOW, timeout=30)
    if res.returncode != 0:
        raise RuntimeError((res.stderr or res.stdout).strip())


def create_shortcuts(icon_path, in_process=True):
    """Shortcut on the desktop and in the Start menu that starts the program without a console window.
    Tries up to three ways (PowerShell is often blocked) and checks that the shortcut really exists.
    in_process=False skips the COM way – used from a background thread, where COM objects could
    otherwise be cleaned up later on the wrong thread and crash the program.
    Returns (path to the desktop shortcut or None, error messages)."""
    links = shortcut_targets()
    target, args = window_python(), f'"{SCRIPT}"'
    icon = f"{icon_path},0" if icon_path else f"{target},0"
    errors = []
    ways = [("vbscript", _lnk_vbscript), ("powershell", _lnk_powershell)]
    if in_process:
        ways.insert(0, ("comtypes", _lnk_comtypes))
    for name, fn in ways:
        try:
            fn(links, target, args, icon)
        except Exception as e:
            errors.append(f"{name}: {str(e)[:200]}")
        if os.path.exists(links[0]):
            return links[0], errors
    return None, errors


# ---------------------------------------------------------------- icons from programs

def exe_icon(path, size=64):
    """Reads the program's real icon from its .exe file (Windows)."""
    if not path:
        return None
    try:
        from ctypes import wintypes
        user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
        HANDLE = ctypes.c_void_p
        user32.PrivateExtractIconsW.argtypes = [wintypes.LPCWSTR, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                                ctypes.POINTER(HANDLE), ctypes.POINTER(wintypes.UINT),
                                                wintypes.UINT, wintypes.UINT]
        user32.GetDC.restype = HANDLE
        user32.GetDC.argtypes = [HANDLE]
        user32.ReleaseDC.argtypes = [HANDLE, HANDLE]
        user32.FillRect.argtypes = [HANDLE, ctypes.POINTER(wintypes.RECT), HANDLE]
        user32.DrawIconEx.argtypes = [HANDLE, ctypes.c_int, ctypes.c_int, HANDLE, ctypes.c_int, ctypes.c_int,
                                      wintypes.UINT, HANDLE, wintypes.UINT]
        user32.DestroyIcon.argtypes = [HANDLE]
        gdi32.CreateCompatibleDC.restype = HANDLE
        gdi32.CreateCompatibleDC.argtypes = [HANDLE]
        gdi32.CreateDIBSection.restype = HANDLE
        gdi32.CreateDIBSection.argtypes = [HANDLE, ctypes.c_void_p, wintypes.UINT,
                                           ctypes.POINTER(ctypes.c_void_p), HANDLE, wintypes.DWORD]
        gdi32.SelectObject.restype = HANDLE
        gdi32.SelectObject.argtypes = [HANDLE, HANDLE]
        gdi32.DeleteObject.argtypes = [HANDLE]
        gdi32.DeleteDC.argtypes = [HANDLE]
        gdi32.CreateSolidBrush.restype = HANDLE

        hicon = HANDLE()
        got = user32.PrivateExtractIconsW(path, 0, size, size, ctypes.byref(hicon), None, 1, 0)
        if got < 1 or not hicon.value:
            return None

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                        ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                        ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                        ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                        ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

        shots = []
        screen = user32.GetDC(None)
        for bg in (0x000000, 0xFFFFFF):
            dc = gdi32.CreateCompatibleDC(screen)
            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth, bmi.biHeight = size, -size
            bmi.biPlanes, bmi.biBitCount = 1, 32
            bits = ctypes.c_void_p()
            bmp = gdi32.CreateDIBSection(dc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
            old = gdi32.SelectObject(dc, bmp)
            brush = gdi32.CreateSolidBrush(bg)
            rect = wintypes.RECT(0, 0, size, size)
            user32.FillRect(dc, ctypes.byref(rect), brush)
            gdi32.DeleteObject(brush)
            user32.DrawIconEx(dc, 0, 0, hicon, size, size, 0, None, 3)
            gdi32.GdiFlush()
            raw = ctypes.string_at(bits, size * size * 4)
            shots.append(Image.frombuffer("RGB", (size, size), raw, "raw", "BGRX", 0, 1).copy())
            gdi32.SelectObject(dc, old)
            gdi32.DeleteObject(bmp)
            gdi32.DeleteDC(dc)
        user32.ReleaseDC(None, screen)
        user32.DestroyIcon(hicon)

        # Work out the transparency: drawn on black and on white
        black, white = shots
        out = Image.new("RGBA", (size, size))
        pix = []
        for (br, bgc, bb), (wr, wg, wb) in zip(black.getdata(), white.getdata()):
            a = 255 - round(((wr - br) + (wg - bgc) + (wb - bb)) / 3)
            a = max(0, min(255, a))
            if a == 0:
                pix.append((0, 0, 0, 0))
            else:
                k = 255 / a
                pix.append((min(255, round(br * k)), min(255, round(bgc * k)), min(255, round(bb * k)), a))
        out.putdata(pix)
        if out.getbbox() is None:
            return None
        return out
    except Exception:
        return None


# ---------------------------------------------------------------- the dancing pixel buddy

SPRITE_TOP = 4                     # empty rows above her head, room for tall hats
SPRITE_W, SPRITE_H = 24, 28 + SPRITE_TOP
PAL = {
    "K": (27, 19, 38), "H": (255, 140, 198), "h": (214, 88, 154), "L": (255, 209, 234),
    "S": (255, 227, 209), "E": (75, 58, 140), "W": (255, 255, 255), "B": (255, 158, 176),
    "M": (212, 72, 106), "D": (122, 162, 255), "d": (79, 111, 224), "w": (255, 255, 255),
    "O": (74, 53, 96), "R": (255, 79, 122), "Y": (255, 216, 74),
    "P": (88, 44, 130), "p": (130, 74, 186), "G": (255, 150, 40), "g": (72, 74, 92),
    "Q": (34, 30, 48), "q": (130, 190, 255),
}


def draw_accessory(put, ox, oy, acc):
    """Hats etc. Coordinates relative to the head (0..15 wide, row 0 = top of the hair)."""
    def at(hx, hy, c):
        put(ox + hx, oy + hy, c)

    def span(hy, a, b, c):
        for hx in range(a, b + 1):
            at(hx, hy, c)

    if acc in ("bow", "sunglasses"):
        for hx in (10, 11, 12, 13):
            at(hx, 0, "R")
        at(10, -1, "R")
        at(13, -1, "R")
    if acc == "sunglasses":
        span(8, 3, 6, "Q")
        span(9, 3, 6, "Q")
        span(8, 9, 12, "Q")
        span(9, 9, 12, "Q")
        span(8, 7, 8, "Q")
        at(4, 8, "q")
        at(10, 8, "q")
    elif acc == "santa":           # the tip flops over to the right, with a pompom
        span(1, 1, 14, "W")
        span(0, 3, 12, "R")
        span(-1, 4, 12, "R")
        span(-2, 6, 13, "R")
        span(-3, 8, 14, "R")
        span(-4, 11, 15, "R")
        span(-3, 15, 16, "R")
        span(-2, 16, 16, "R")
        for hx, hy in ((15, -1), (16, -1), (17, -1), (15, 0), (16, 0), (17, 0), (16, -2), (17, -2)):
            at(hx, hy, "W")
        at(5, -1, "M")               # a little shading
        at(7, -2, "M")
    elif acc == "witch":           # tall pointy hat, tip bent to the right
        span(1, -1, 16, "P")
        span(0, 3, 12, "G")
        at(7, 0, "Y")                # buckle
        at(8, 0, "Y")
        span(-1, 4, 11, "P")
        span(-2, 5, 10, "P")
        span(-3, 6, 10, "P")
        span(-4, 7, 10, "P")
        span(-5, 9, 12, "P")
        span(-6, 12, 13, "P")
        for hx, hy in ((4, -1), (5, -2), (6, -3), (7, -4)):
            at(hx, hy, "p")          # highlight along the left side
    elif acc == "cat":             # taller, pointy ears
        for a, b, top, tip, inner in ((2, 4, (2, 3), 2, 3), (11, 13, (12, 13), 13, 12)):
            span(0, a, b, "H")
            span(-1, a, b, "H")
            span(-2, top[0], top[1], "H")
            at(tip, -3, "H")
            at(inner, -1, "L")
            at(inner, 0, "L")
    elif acc == "headphones":
        span(-1, 3, 12, "g")
        for hx, hy in ((1, 0), (2, 0), (0, 1), (0, 2), (0, 3), (13, 0), (14, 0), (15, 1), (15, 2), (15, 3)):
            at(hx, hy, "g")
        for side in (-2, 15):          # ear cups: grey with a pink centre
            for hy in range(4, 11):
                for hx in range(side, side + 3):
                    at(hx, hy, "g")
            for hy in (6, 7, 8):
                at(side + 1, hy, "R")
HEAD = [
    "....KKKKKKKK....",
    "..KKHHHHHHHHKK..",
    ".KHHLLHHHHHHHHK.",
    ".KHLHHHHHHHHHHK.",
    "KHHHHHHHHHHHHHHK",
    "KHHHhHHHHHHhHHHK",
    "KHHhSSShHhSSShHK",
    "KHhSSSSSSSSSSShK",
    "KHSSEESSSSEESSHK",
    "KHSSEWSSSSEWSSHK",
    "KhSBEESSSSEESBhK",
    "KhSSSSSMMSSSSShK",
    ".KSSSSSSSSSSSSK.",
    "..KKSSSSSSSSKK..",
    "......KSSK......",
]
NOTE = ["..YY", "..Y.", "..Y.", "YYY.", "YY.."]
ARMS = {
    "hips": [(-1, 0), (-2, 1), (-1, 2)],  # hands on hips (impatient)
    "down": [(-1, 0), (-1, 1), (-1, 2), (-1, 3)],
    "out": [(-1, 0), (-2, 0), (-3, -1), (-4, -1)],
    "up": [(-1, 0), (-2, -1), (-3, -1), (-4, -2), (-4, -3)],
    "wave1": [(-1, 0), (-2, -1), (-3, -2), (-4, -3), (-4, -4)],   # waving, hand out
    "wave2": [(-1, 0), (-1, -1), (-2, -2), (-2, -3), (-2, -4)],   # waving, hand up
    "point": [(-1, 0), (-2, -1), (-3, -2), (-4, -3), (-5, -4)],    # disco: pointing up
    "pointdown": [(-1, 0), (-2, 1), (-3, 2), (-4, 3)],             # disco: pointing down
    "clap_open": [(-1, 0), (-2, 1), (-3, 1)],                      # hands apart
    "clap": [(-1, 0), (-1, 1), (0, 2), (1, 2), (2, 2)],            # hands together in front
    "robot_up": [(-1, 0), (-2, 0), (-3, 0), (-3, -1), (-3, -2)],   # robot: elbow out, hand up
    "robot_down": [(-1, 0), (-2, 0), (-3, 0), (-3, 1), (-3, 2)],   # robot: elbow out, hand down
}
FRAMES = [
    dict(la="up", ra="up", b=0, sway=0, legs="both", note="l", sing=True),
    dict(la="up", ra="out", b=1, sway=1, legs="right"),
    dict(la="out", ra="out", b=0, sway=1, legs="both", note="r"),
    dict(la="down", ra="up", b=1, sway=0, legs="left", sing=True),
    dict(la="up", ra="up", b=0, sway=-1, legs="both", note="r", sing=True),
    dict(la="out", ra="up", b=1, sway=-1, legs="left"),
    dict(la="out", ra="out", b=0, sway=0, legs="both", note="l"),
    dict(la="up", ra="down", b=1, sway=1, legs="right", sing=True),
]


IDLE = dict(la="hips", ra="hips", b=0, sway=0, legs="both", eyes="bored", mouth="small")
TAP = dict(IDLE, legs="right")
BLINK = dict(IDLE, eyes="closed")
SIGH = dict(IDLE, la="down", ra="down", b=1, eyes="closed", sing=True)
SLUMP = dict(IDLE, la="down", ra="down")
# No music: stands and waits, taps her foot, blinks and sighs (~200 ms per frame)
IDLE_FRAMES = ([IDLE] * 4 + [TAP, IDLE, TAP, IDLE, TAP] + [IDLE] * 3 + [BLINK] + [IDLE] * 5
               + [SIGH] * 3 + [SLUMP] * 4 + [dict(SLUMP, eyes="closed")] + [SLUMP] * 4
               + [TAP, IDLE, TAP] + [IDLE] * 2)
IDLE_MS = 200

# Calm music: sways gently
CALM_FRAMES = [
    dict(la="down", ra="down", b=0, sway=0, legs="both"),
    dict(la="down", ra="out", b=0, sway=1, legs="right", eyes="happy"),
    dict(la="down", ra="down", b=1, sway=1, legs="both", eyes="happy"),
    dict(la="down", ra="down", b=0, sway=0, legs="both"),
    dict(la="out", ra="down", b=0, sway=-1, legs="left", eyes="happy"),
    dict(la="down", ra="down", b=1, sway=-1, legs="both", eyes="happy"),
]
# Lots of bass / energy: hands in the air, jumping
HYPE_FRAMES = [
    dict(la="up", ra="up", b=0, sway=1, legs="jump", sing=True, eyes="happy", note="l"),
    dict(la="wave2", ra="wave2", b=1, sway=-1, legs="both", mouth="open"),
    dict(la="up", ra="up", b=0, sway=-1, legs="jump", sing=True, eyes="happy", note="r"),
    dict(la="wave2", ra="wave2", b=1, sway=1, legs="both", mouth="open"),
]
# --- More dance moves. She switches between them while the music plays.
DISCO_FRAMES = [
    dict(la="hips", ra="point", b=0, sway=1, legs="left", eyes="happy"),
    dict(la="hips", ra="pointdown", b=1, sway=-1, legs="both"),
    dict(la="hips", ra="point", b=0, sway=1, legs="left", sing=True),
    dict(la="hips", ra="pointdown", b=1, sway=-1, legs="both"),
    dict(la="point", ra="hips", b=0, sway=-1, legs="right", eyes="happy"),
    dict(la="pointdown", ra="hips", b=1, sway=1, legs="both"),
    dict(la="point", ra="hips", b=0, sway=-1, legs="right", sing=True),
    dict(la="pointdown", ra="hips", b=1, sway=1, legs="both", note="l"),
]
SIDESTEP_FRAMES = [
    dict(la="out" if x >= 0 else "down", ra="down" if x >= 0 else "out", b=i % 2,
         sway=-1 if x > 0 else (1 if x < 0 else 0), legs="right" if i % 2 else "left", dx=x,
         eyes="happy" if i in (2, 6) else "open", sing=i in (2, 6))
    for i, x in enumerate((0, 1, 2, 1, 0, -1, -2, -1))
]
CLAP_FRAMES = [   # clap on the beat
    dict(la="clap", ra="clap", b=1, sway=1, legs="left", sing=True, note="l"),
    dict(la="clap_open", ra="clap_open", b=0, sway=0, legs="both", eyes="happy"),
    dict(la="clap", ra="clap", b=1, sway=-1, legs="right", sing=True, note="r"),
    dict(la="clap_open", ra="clap_open", b=0, sway=0, legs="both", eyes="happy"),
]
ROBOT_FRAMES = [
    dict(la="robot_up", ra="robot_down", b=0, sway=0, legs="both", mouth="small"),
    dict(la="robot_up", ra="robot_down", b=0, sway=0, legs="left", mouth="small", dx=1),
    dict(la="robot_down", ra="robot_up", b=0, sway=0, legs="both", mouth="small"),
    dict(la="robot_down", ra="robot_up", b=0, sway=0, legs="right", mouth="small", dx=-1),
]
HEADBANG_FRAMES = [   # head down on the beat
    dict(la="out", ra="out", b=1, sway=-2, legs="jump", eyes="closed", mouth="open", hb=1),
    dict(la="up", ra="up", b=0, sway=2, legs="both", eyes="closed", mouth="open"),
    dict(la="out", ra="out", b=1, sway=2, legs="jump", eyes="closed", mouth="open", hb=1),
    dict(la="up", ra="up", b=0, sway=-2, legs="both", eyes="closed", mouth="open"),
]
SPIN_FRAMES = [
    dict(la="out", ra="out", b=0, sway=0, legs="both", eyes="happy"),
    dict(la="out", ra="out", b=0, sway=-1, legs="left", dx=1),
    dict(la="out", ra="out", b=1, sway=-2, legs="both", back=True, dx=1),
    dict(la="out", ra="out", b=1, sway=2, legs="right", back=True, dx=-1),
    dict(la="out", ra="out", b=0, sway=1, legs="both", dx=-1, eyes="happy", sing=True),
    dict(la="up", ra="up", b=0, sway=0, legs="jump", eyes="happy", sing=True, note="r"),
    dict(la="out", ra="out", b=1, sway=0, legs="both", eyes="happy"),
    dict(la="up", ra="up", b=0, sway=0, legs="jump", eyes="happy", sing=True),
]
DANCE_MOVES = {"classic": FRAMES, "sway": CALM_FRAMES, "jump": HYPE_FRAMES, "disco": DISCO_FRAMES,
               "sidestep": SIDESTEP_FRAMES, "clap": CLAP_FRAMES, "robot": ROBOT_FRAMES,
               "headbang": HEADBANG_FRAMES, "spin": SPIN_FRAMES}
# Frames per beat for each move when she follows the tempo (sway is slow: one frame per beat)
MOVE_FPB = {"sway": 1}
# Which moves fit which kind of music
MOVE_POOLS = {"calm": ["sway", "clap", "sidestep"],
              "dance": ["classic", "disco", "sidestep", "clap", "robot"],
              "hype": ["jump", "headbang", "spin", "disco"]}

# Waves when the mouse is over her
WAVE_FRAMES = [
    dict(la="down", ra="wave1", b=0, sway=0, legs="both", eyes="happy", sing=True),
    dict(la="down", ra="wave2", b=0, sway=0, legs="both", eyes="happy", sing=True),
]
# Surprised (woken up, or clicked)
SURPRISE_FRAMES = [dict(la="out", ra="out", b=0, sway=0, legs="jump", mouth="open")]
# Sleeps after a long time without music: breathes calmly
SLEEP_A = dict(la="down", ra="down", b=1, sway=0, legs="both", eyes="closed", mouth="small")
SLEEP_B = dict(SLEEP_A, b=2)
SLEEP_FRAMES = [SLEEP_A] * 4 + [SLEEP_B] * 4
SLEEP_MS = 260
SLEEP_AFTER = 45          # seconds without music before she falls asleep
BLINK_CHANCE = 0.045      # chance per frame that she blinks while dancing

# Speech bubbles. A ♪ at the end of the text is drawn as a pixel note.
BUBBLE_TEXT = "Play some music\nso I can dance! \u266a"
MUTE_TEXT = "Hello? I can't\nhear anything!"
LOUD_TEXT = "Ouch, my ears!"
LINES_CLICK_PLAYING = ["Hi there! \u266a", "More bass please!", "I love\nthis song!", "Dance with me!",
                       "Hehe, that tickles!", "Turn it up! \u266a"]
LINES_CLICK_IDLE = ["Hi there!", "Play something,\nplease!", "I'm so bored...", "Hehe, that tickles!"]
LINES_WAKE = ["Huh?! I wasn't sleeping!", "Mmh... is it\nmorning already?", "I was just\nresting my eyes!"]
LINES_SONG = ["New song! \u266a", "Ooh, this one! \u266a", "Good pick! \u266a"]
LINES_BACK = ["Music, finally! \u266a", "Here we go! \u266a"]

# Pixel images for effects (X = coloured pixel)
FX_PATTERNS = {
    "note": ["..XX", "..X.", "..X.", "XXX.", "XX.."],
    "heart": [".XX.XX.", "XXXXXXX", "XXXXXXX", ".XXXXX.", "..XXX..", "...X..."],
    "z": ["XXXX", "..X.", ".X..", "XXXX"],
    "star": [".X.", "XXX", ".X."],
}


def make_sprite(f, style=None):
    style = style or {}
    pal = dict(PAL)
    if style.get("D"):
        pal["D"], pal["d"] = tuple(style["D"]), tuple(style["d"])
    acc = style.get("acc", "bow")
    px = [[None] * SPRITE_W for _ in range(SPRITE_H)]

    def put(x, y, c):
        if 0 <= x < SPRITE_W and 0 <= y < SPRITE_H:
            px[y][x] = c

    ox, oy = 4 + f.get("dx", 0), 2 + SPRITE_TOP + f["b"]
    body_oy = oy
    oy += f.get("hb", 0)        # head bob (headbang): only the head moves down
    back = f.get("back", False)  # seen from behind (spin)

    # pigtails (behind the head), swaying to the beat
    for y in range(3, 13):
        dx = round(f["sway"] * (y - 3) / 9 * 1.6)
        c = "H" if y < 12 else "h"
        for x in (ox - 2 + dx, ox - 1 + dx, ox + 16 + dx, ox + 17 + dx):
            put(x, oy + y, c)
    put(ox - 1, oy + 3, "R")
    put(ox + 16, oy + 3, "R")

    # head
    for y, row in enumerate(HEAD):
        for x, ch in enumerate(row):
            if ch != ".":
                if back and 5 <= y <= 13 and ch != "K":
                    ch = "h" if y >= 12 else "H"    # the back of her head is all hair
                put(ox + x, oy + y, ch)
    eyes = "none" if back else f.get("eyes", "open")
    for ex in (4, 5, 10, 11):
        if eyes == "bored":      # heavy eyelids
            put(ox + ex, oy + 8, "K")
        elif eyes == "closed":   # blinking / sighing / sleeping
            put(ox + ex, oy + 8, "S")
            put(ox + ex, oy + 9, "S")
            put(ox + ex, oy + 10, "K")
        elif eyes == "happy":    # happy, squeezed eyes ^^
            put(ox + ex, oy + 8, "S")
            put(ox + ex, oy + 9, "K")
            put(ox + ex, oy + 10, "S")
    if eyes == "happy":
        for ex in (4, 11):       # small corners in the eyes = ^
            put(ox + ex, oy + 10, "K")
    mouth = None if back else f.get("mouth")
    if mouth == "small":
        put(ox + 7, oy + 11, "S")
    elif mouth == "open":      # surprised / laughing
        for x in (7, 8):
            put(ox + x, oy + 11, "M")
            put(ox + x, oy + 12, "M")
    if f.get("sing") and not back:
        for x in (7, 8):
            put(ox + x, oy + 12, "M")

    # bow / hat / glasses
    draw_accessory(put, ox, oy, "bow" if back and acc == "sunglasses" else acc)

    # dress
    oy = body_oy
    def row(y, x0, x1, c):
        for x in range(x0, x1 + 1):
            put(ox + x, oy + y, c)

    for y in (15, 16, 17, 18):
        row(y, 5, 10, "D")
        put(ox + 10, oy + y, "d")
    put(ox + 7, oy + 15, "w")
    put(ox + 8, oy + 15, "w")
    row(19, 4, 11, "D")
    row(20, 3, 12, "D")
    put(ox + 11, oy + 19, "d")
    put(ox + 12, oy + 20, "d")
    row(21, 3, 12, "w")

    # legs (the feet stay put when she sways)
    feet_y = 26 + SPRITE_TOP
    for lx, lifted, shoe in ((5, f["legs"] in ("left", "jump"), (-1, 0, 1)),
                             (9, f["legs"] in ("right", "jump"), (0, 1, 2))):
        bottom = feet_y - 1 - (1 if lifted else 0)
        for y in range(oy + 22, bottom + 1):
            put(ox + lx, y, "S")
            put(ox + lx + 1, y, "S")
        for dx in shoe:
            put(ox + lx + dx, bottom + 1, "O")

    # arms
    for side, pose in (("l", f["la"]), ("r", f["ra"])):
        sx, sign = (ox + 5, 1) if side == "l" else (ox + 10, -1)
        for n, (dx, dy) in enumerate(ARMS[pose]):
            put(sx + dx * sign, oy + 16 + dy, "D" if n == 0 else "S")

    # music note
    if f.get("note"):
        nx = 0 if f["note"] == "l" else SPRITE_W - 4
        for y, r in enumerate(NOTE):
            for x, ch in enumerate(r):
                if ch != ".":
                    put(nx + x, y, ch)

    # automatic outline around everything
    out = [r[:] for r in px]
    for y in range(SPRITE_H):
        for x in range(SPRITE_W):
            if px[y][x] is None:
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < SPRITE_W and 0 <= ny < SPRITE_H and px[ny][nx] not in (None, "K"):
                        out[y][x] = "K"
                        break

    img = Image.new("RGBA", (SPRITE_W, SPRITE_H), (0, 0, 0, 0))
    for y in range(SPRITE_H):
        for x in range(SPRITE_W):
            c = out[y][x]
            if c:
                img.putpixel((x, y), pal[c] + (255,))
    return img


# ---------------------------------------------------------------- audio control

class SessionControl:
    """A program can have several audio sessions (e.g. Firefox) – control them all."""

    def __init__(self, volumes):
        self.volumes = volumes

    def get(self):
        for v in self.volumes:
            try:
                return v.GetMasterVolume()
            except Exception:
                continue
        return None

    def set(self, value):
        for v in self.volumes:
            try:
                v.SetMasterVolume(value, None)
            except Exception:
                pass

    def get_mute(self):
        for v in self.volumes:
            try:
                return bool(v.GetMute())
            except Exception:
                continue
        return None

    def set_mute(self, muted):
        for v in self.volumes:
            try:
                v.SetMute(1 if muted else 0, None)
            except Exception:
                pass


class MasterControl:
    def __init__(self, endpoint):
        self.ep = endpoint

    def get(self):
        try:
            return self.ep.GetMasterVolumeLevelScalar()
        except Exception:
            return None

    def set(self, value):
        try:
            self.ep.SetMasterVolumeLevelScalar(value, None)
        except Exception:
            pass

    def get_mute(self):
        try:
            return bool(self.ep.GetMute())
        except Exception:
            return None

    def set_mute(self, muted):
        try:
            self.ep.SetMute(1 if muted else 0, None)
        except Exception:
            pass


def find_master():
    try:
        dev = AudioUtilities.GetSpeakers()
        ep = getattr(dev, "EndpointVolume", None)  # newer pycaw
        if ep is None:  # older pycaw
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import IAudioEndpointVolume
            iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            ep = iface.QueryInterface(IAudioEndpointVolume)
        return MasterControl(ep)
    except Exception:
        return None


def find_meter():
    """Peak level of all sound playing right now (0..1), for the sound waves."""
    try:
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import IAudioMeterInformation
        dev = AudioUtilities.GetSpeakers()
        raw = getattr(dev, "_dev", dev)
        iface = raw.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None)
        # QueryInterface gives a properly counted reference. (ctypes.cast would make two
        # Python objects own the same COM object; it then gets released twice and crashes.)
        return iface.QueryInterface(IAudioMeterInformation)
    except Exception:
        return None


class TempoTracker:
    """Finds the tempo (BPM) and where the beats fall, from an onset-strength signal
    (how much new sound starts at each moment). Uses autocorrelation for the tempo and a
    comb filter for the beat phase, and smooths both so the buddy doesn't jump around."""

    MIN_BPM, MAX_BPM = 60, 200

    def __init__(self, fps, np):
        self.np = np
        self.fps = fps
        self.n = 512                     # ~5.5 s of history
        self.env = np.zeros(self.n, dtype=np.float32)       # onsets, all frequencies
        self.low = np.zeros(self.n, dtype=np.float32)       # onsets of kick drum and bass only
        self.count = 0                   # hops pushed so far
        self.bpm = 0.0
        self.period = 0.0                # in hops
        self.anchor = None               # hop index of a beat
        self.conf = 0.0
        self._cand, self._cand_n = 0.0, 0
        lags = np.arange(1, self.n // 2)
        bpms = 60.0 * fps / lags
        # prefer tempos people dance to (around 120 BPM), one octave either side
        self.prior = np.exp(-0.5 * (np.log2(bpms / 120.0) / 0.9) ** 2).astype(np.float32)

    def push(self, value, low=0.0):
        self.env[:-1] = self.env[1:]
        self.env[-1] = value
        self.low[:-1] = self.low[1:]
        self.low[-1] = low
        self.count += 1

    def _autocorr(self, sig):
        np = self.np
        x = sig - sig.mean()
        if float(x.std()) < 1e-6:
            return None
        f = np.fft.rfft(x, 2 * self.n)
        ac = np.fft.irfft(f * np.conj(f))[: self.n]
        return ac / (ac[0] + 1e-9)

    def estimate(self):
        np = self.np
        if self.count < self.n // 2:
            return
        ac = self._autocorr(self.env)
        if ac is None:
            self.conf *= 0.5
            return
        # The beat usually lives in the kick drum and bass, so their rhythm counts extra.
        # That keeps melodies or synths with their own rhythm from fooling the tempo.
        ac_low = self._autocorr(self.low)
        if ac_low is not None:
            ac = 0.4 * ac + 0.6 * ac_low
        lo = int(60.0 * self.fps / self.MAX_BPM)
        hi = int(60.0 * self.fps / self.MIN_BPM)
        lags = np.arange(lo, hi + 1)
        score = ac[lags] + 0.5 * ac[np.minimum(2 * lags, self.n - 1)]
        score = score * self.prior[lags - 1]
        i = int(np.argmax(score))
        lag = float(lags[i])
        if 0 < i < len(lags) - 1:        # parabolic interpolation for a finer tempo
            a, b, c = score[i - 1], score[i], score[i + 1]
            d = a - 2 * b + c
            if d < 0:
                lag += 0.5 * (a - c) / d
        conf = float(ac[int(round(lag))])
        bpm = 60.0 * self.fps / lag
        self.conf = 0.7 * self.conf + 0.3 * max(0.0, conf)

        # smooth the tempo; only switch to a new tempo when it has been seen a few times
        if self.bpm == 0 or abs(bpm / self.bpm - 1) < 0.04:
            self.bpm = bpm if self.bpm == 0 else 0.85 * self.bpm + 0.15 * bpm
            self._cand_n = 0
        else:
            if self._cand and abs(bpm / self._cand - 1) < 0.04:
                self._cand_n += 1
            else:
                self._cand, self._cand_n = bpm, 1
            if self._cand_n >= 3:
                self.bpm, self._cand_n = bpm, 0
                self.anchor = None
        self.period = 60.0 * self.fps / self.bpm

        # beat phase: which offset lines up best with the onsets over the last 4 beats
        P = self.period
        best_k, best = 0, -1.0
        last = self.n - 1
        comb = self.env / (float(self.env.max()) + 1e-9) + self.low / (float(self.low.max()) + 1e-9)
        for k in range(int(P)):
            pos = (last - k - np.arange(4) * P).round().astype(int)
            pos = pos[pos >= 0]
            v = float(comb[pos].sum())
            if v > best:
                best, best_k = v, k
        new_anchor = (self.count - 1) - best_k
        if self.anchor is None:
            self.anchor = float(new_anchor)
        else:
            err = ((new_anchor - self.anchor) / P + 0.5) % 1.0 - 0.5
            self.anchor += err * P * 0.35


class Analyzer:
    """Records what goes out to the speakers (loopback) and works out how strong the
    bass, low mids, mids and treble are right now, and the tempo and beat of the music.
    Runs in its own thread."""

    LATENCY = 0.03   # seconds between the sound and when we see it

    def __init__(self):
        self.bands = [0.0, 0.0, 0.0, 0.0]
        self.beats = 0          # increases on every bass hit
        self.updated = 0.0
        self.ok = False
        self.bpm = 0.0          # tempo, 0 = unknown
        self.beat_len = 0.0     # seconds per beat
        self.beat_at = 0.0      # wall-clock time of a beat (any beat on the grid)
        self.tempo_conf = 0.0   # how sure we are about the tempo (0..1)
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        try:
            import warnings
            warnings.filterwarnings("ignore")
            import numpy as np
            import soundcard as sc  # imported in the thread: own COM apartment, doesn't clash with pycaw
        except Exception:
            return
        sr, n, block = 48000, 2048, 512
        fps = sr / block
        window = np.hanning(n).astype(np.float32)
        freqs = np.fft.rfftfreq(n, 1 / sr)
        masks = [(freqs >= a) & (freqs < b) for a, b in BAND_EDGES]
        floors = [0.6, 0.35, 0.2, 0.08]   # below this counts as silence
        flux_top = int(np.searchsorted(freqs, 5000))
        flux_w = np.where(freqs[:flux_top] < 200, 2.0, 1.0).astype(np.float32)   # kick drums count double
        low_top = int(np.searchsorted(freqs, 150))
        while True:
            try:
                spk = sc.default_speaker()
                mic = sc.get_microphone(id=str(spk.name), include_loopback=True)
                buf = np.zeros(n, dtype=np.float32)
                prev_lm = np.zeros(flux_top, dtype=np.float32)
                tempo = TempoTracker(fps, np)
                peaks = [f * 4 for f in floors]
                bass_avg = 0.0
                last_beat = 0.0
                last_check = time.time()
                with mic.recorder(samplerate=sr, blocksize=block) as rec:
                    self.ok = True
                    while True:
                        data = rec.record(numframes=block)
                        mono = data.mean(axis=1) if data.ndim > 1 else data
                        k = len(mono)
                        if k:
                            if k >= n:
                                buf[:] = mono[-n:]
                            else:
                                buf[:-k] = buf[k:]
                                buf[-k:] = mono
                            spec = np.abs(np.fft.rfft(buf * window))
                            # onset strength: how much the (log) spectrum grew since last time
                            lm = np.log1p(spec[:flux_top] * 10.0)
                            rise = np.maximum(lm - prev_lm, 0.0)
                            tempo.push(float((rise * flux_w).sum()), float(rise[:low_top].sum()))
                            prev_lm = lm
                            if tempo.count % 24 == 0:          # ~4 times a second
                                tempo.estimate()
                                if tempo.bpm and tempo.anchor is not None:
                                    t_last = time.time() - self.LATENCY
                                    self.beat_len = tempo.period / fps
                                    self.beat_at = t_last - (tempo.count - 1 - tempo.anchor) / fps
                                    self.bpm = tempo.bpm
                                self.tempo_conf = tempo.conf
                            vals = []
                            for i, m in enumerate(masks):
                                e = float(np.sqrt(np.mean(spec[m] ** 2)))
                                # automatic gain: adapts to how loud things are playing
                                peaks[i] = max(e, peaks[i] * 0.9992, floors[i] * 4)
                                v = 0.0 if e < floors[i] else min(1.0, (e / peaks[i]) ** 0.9)
                                vals.append(v)
                            bass = vals[0]
                            now = time.time()
                            if bass > 0.55 and bass > bass_avg * 1.3 and now - last_beat > 0.18:
                                self.beats += 1
                                last_beat = now
                            bass_avg = bass_avg * 0.93 + bass * 0.07
                            self.bands = vals
                            self.updated = time.time()
                        if time.time() - last_check > 3:  # has the audio device changed?
                            last_check = time.time()
                            if sc.default_speaker().name != spk.name:
                                break
            except Exception:
                self.ok = False
                time.sleep(2)


class Off:
    """Replaces audio capture and song info in safe mode."""
    ok = False
    bands = [0.0, 0.0, 0.0, 0.0]
    beats = 0
    updated = 0.0
    bpm = 0.0
    beat_len = 0.0
    beat_at = 0.0
    tempo_conf = 0.0
    title = None
    changes = 0
    display = None
    paused = False
    app = None


SUFFIXES = (" \u2014 Mozilla Firefox", " - Mozilla Firefox", " - Google Chrome", " - Microsoft\u200b Edge",
            " - Microsoft Edge", " - Brave", " - Opera", " - VLC media player", " - foobar2000")
SITES = ((" - YouTube Music", "YouTube Music"), (" - YouTube", "YouTube"), (" | SoundCloud", "SoundCloud"),
         (" - SoundCloud", "SoundCloud"), (" - Twitch", "Twitch"))


def parse_title(app, raw):
    """'Artist - Song' (Spotify) or 'Song - YouTube — Mozilla Firefox' -> (song, artist/source)."""
    t = re.sub(r"^\(\d+\)\s*", "", raw.strip())
    for suf in SUFFIXES:
        if t.endswith(suf):
            t = t[: -len(suf)]
    if app == "spotify.exe" and " - " in t:
        artist, song = t.split(" - ", 1)
        return song.strip(), artist.strip()
    source = pretty_name(app) if app else ""
    for suf, name in SITES:
        if t.endswith(suf):
            t, source = t[: -len(suf)], name
            break
    if " - " in t:
        artist, song = t.split(" - ", 1)
        return song.strip(), artist.strip()
    return t.strip(), source


class NowPlaying:
    """Notices when the song changes. Spotify and browsers (YouTube etc.) show the song name in
    their window title, so reading the titles is enough – no extra packages needed."""

    PLAYERS = {"spotify.exe", "firefox.exe", "chrome.exe", "msedge.exe", "brave.exe", "opera.exe",
               "vlc.exe", "foobar2000.exe", "musicbee.exe", "applemusic.exe", "tidal.exe", "deezer.exe"}
    IDLE_TITLES = {"spotify", "spotify premium", "spotify free", "mozilla firefox", "google chrome",
                   "microsoft edge", "vlc media player", ""}
    MEDIA_HINTS = ("youtube", "soundcloud", "spotify", "twitch", "bandcamp", "tidal", "deezer", "music")

    def __init__(self):
        self.title = None
        self.changes = 0
        self.ok = False
        self.display = None     # (song, artist) to show
        self.paused = False
        self.app = None
        self.spotify_idle = False
        self._names = {}
        self._misses = 0
        threading.Thread(target=self.run, daemon=True).start()

    def proc_name(self, pid):
        name = self._names.get(pid)
        if name is None:
            try:
                import psutil
                name = psutil.Process(pid).name().lower()
            except Exception:
                name = ""
            if len(self._names) > 500:
                self._names.clear()
            self._names[pid] = name
        return name

    def titles(self):
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        found = []
        proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def cb(hwnd, _):
            try:
                if not user32.IsWindowVisible(hwnd):
                    return True
                n = user32.GetWindowTextLengthW(hwnd)
                if n <= 0:
                    return True
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                name = self.proc_name(pid.value)
                if name in self.PLAYERS:
                    found.append((name, buf.value))
            except Exception:
                pass
            return True

        user32.EnumWindows(proto(cb), 0)
        return found

    def current(self):
        wins = self.titles()
        self.spotify_idle = any(n == "spotify.exe" and t.strip().lower() in self.IDLE_TITLES for n, t in wins)
        for name, title in wins:      # Spotify first
            if name == "spotify.exe" and title.strip().lower() not in self.IDLE_TITLES:
                return name, title.strip()
        for name, title in wins:      # then music/video in browsers and players
            low = title.lower()
            if low.strip() in self.IDLE_TITLES:
                continue
            if name in ("vlc.exe", "foobar2000.exe", "musicbee.exe", "applemusic.exe", "tidal.exe",
                        "deezer.exe") or any(h in low for h in self.MEDIA_HINTS):
                return name, title.strip()
        return None

    def poll(self):
        res = self.current()
        if res:
            app, raw = res
            self._misses = 0
            if app == "spotify.exe":
                self.paused = False
            if raw != self.title:
                self.title, self.app = raw, app
                self.display = parse_title(app, raw)
                self.paused = False
                self.changes += 1
        elif self.display and self.app == "spotify.exe" and self.spotify_idle:
            self.paused = True          # Spotify only shows "Spotify" while paused
        else:
            self._misses += 1
            if self._misses >= 4:       # the player was closed
                self.display, self.paused = None, False

    def run(self):
        if sys.platform != "win32":
            return
        self.ok = True
        while True:
            try:
                self.poll()
            except Exception:
                pass
            time.sleep(1.0)


def make_bubble(text, unit, text_font):
    """Pixel-style speech bubble (square frame and a stepped arrow to the right) with smooth text.
    A ♪ at the end of the text is drawn as a small pixel note (not every font has the character)."""
    note = text.rstrip().endswith("\u266a")
    if note:
        text = text.rstrip()[:-1].rstrip()
    lines = text.split("\n")
    u = unit
    note_w = 6 * u if note else 0           # gap + a 4-pixel note
    widths = [text_font.getlength(line) for line in lines]
    widths[-1] += note_w
    tw = max(widths)
    asc, desc = text_font.getmetrics()
    lh = asc + desc
    w = int(tw) + 6 * u
    h = lh * len(lines) + 4 * u
    tail = 3 * u
    img = Image.new("RGBA", (w + tail, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ink = PAL["K"] + (255,)
    paper = (255, 255, 255, 255)
    # frame with clipped corners (pixel style)
    d.rectangle((u, 0, w - u - 1, h - 1), fill=ink)
    d.rectangle((0, u, w - 1, h - u - 1), fill=ink)
    d.rectangle((2 * u, u, w - 2 * u - 1, h - u - 1), fill=paper)
    d.rectangle((u, 2 * u, w - u - 1, h - 2 * u - 1), fill=paper)
    # stepped arrow towards the buddy
    cy = h // 2
    d.rectangle((w, cy - 2 * u, w + u - 1, cy + 2 * u - 1), fill=ink)          # arrow base
    d.rectangle((w + u, cy - u, w + 2 * u - 1, cy + u - 1), fill=ink)          # arrow tip
    d.rectangle((w - u, cy - u, w + u - 1, cy + u - 1), fill=paper)            # opening into the bubble
    y = 2 * u
    for i, line in enumerate(lines):
        last = i == len(lines) - 1
        cx = w / 2 - (note_w / 2 if last else 0)
        d.text((cx, y + lh / 2), line, font=text_font, fill=ink, anchor="mm")
        if last and note:
            nx = int(cx + text_font.getlength(line) / 2 + 2 * u)
            ny = int(y + lh / 2 - 2.5 * u)
            for py, r in enumerate(FX_PATTERNS["note"]):
                for px_, ch in enumerate(r):
                    if ch == "X":
                        d.rectangle((nx + px_ * u, ny + py * u, nx + (px_ + 1) * u - 1, ny + (py + 1) * u - 1),
                                    fill=PAL["R"] + (255,))
        y += lh
    return img


def make_fx(pattern, color, u):
    """A small pixel effect in four transparency steps (for fading out)."""
    rows = FX_PATTERNS[pattern]
    w, h = len(rows[0]) * u, len(rows) * u
    out = []
    for alpha in (255, 200, 135, 70):
        img = Image.new("RGBA", (w + 2 * u, h + 2 * u), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for y, r in enumerate(rows):       # dark edge so they show up against the waves
            for x, ch in enumerate(r):
                if ch == "X":
                    d.rectangle((x * u, y * u, (x + 3) * u - 1, (y + 3) * u - 1),
                                fill=(14, 12, 22, int(alpha * 0.55)))
        for y, r in enumerate(rows):
            for x, ch in enumerate(r):
                if ch == "X":
                    d.rectangle(((x + 1) * u, (y + 1) * u, (x + 2) * u - 1, (y + 2) * u - 1),
                                fill=tuple(color) + (alpha,))
        out.append(ImageTk.PhotoImage(img))
    return out


OWN_PID = os.getpid()


def media_key(name):
    """Sends a media key (play/pause, next, previous) – works with Spotify and browsers."""
    vk = MEDIA_VK[name]
    try:
        u = ctypes.windll.user32
        u.keybd_event(vk, 0, 0x1, 0)
        u.keybd_event(vk, 0, 0x1 | 0x2, 0)
    except Exception:
        pass


def output_devices():
    """[(id, name, is_default)] for all active playback devices."""
    import warnings
    from pycaw.constants import DEVICE_STATE, EDataFlow
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        enum = AudioUtilities.GetDeviceEnumerator()
        default = enum.GetDefaultAudioEndpoint(0, 1).GetId()
        out = []
        for dev in AudioUtilities.GetAllDevices(EDataFlow.eRender.value, DEVICE_STATE.ACTIVE.value):
            try:
                name = dev.FriendlyName or dev.id
            except Exception:
                name = dev.id
            out.append((dev.id, name, dev.id == default))
    return out


def default_device_name():
    import warnings
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return AudioUtilities.GetSpeakers().FriendlyName or ""
    except Exception:
        return ""


def set_output_device(dev_id):
    from pycaw.constants import ERole
    AudioUtilities.SetDefaultDevice(dev_id, roles=[ERole.eConsole, ERole.eMultimedia, ERole.eCommunications])


def short_device(name, n=26):
    # "Headphones (Arctis 7 Game)" -> "Arctis 7 Game"; long names are shortened
    m = re.match(r"^[^()]*\((.+)\)\s*$", name or "")
    name = m.group(1) if m else (name or "")
    return name if len(name) <= n else name[: n - 1] + "\u2026"


def foreground_app():
    """Name of the program you are in right now (e.g. the game)."""
    try:
        from ctypes import wintypes
        u = ctypes.windll.user32
        hwnd = u.GetForegroundWindow()
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == OWN_PID:
            return None
        import psutil
        return psutil.Process(pid.value).name().lower()
    except Exception:
        return None


class Hotkeys:
    """Global hotkeys (they also work inside games). Own thread with a Windows message loop."""

    def __init__(self, events):
        self.events = events
        self.failed = []
        self.tid = None
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        if sys.platform != "win32":
            return
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        self.tid = ctypes.windll.kernel32.GetCurrentThreadId()
        for hid, mods, vk, _, keys, _ in HOTKEYS:
            if not user32.RegisterHotKey(None, hid, mods, vk):
                self.failed.append(keys)
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == 0x0312:  # WM_HOTKEY
                self.events.put(("hotkey", int(msg.wParam)))
        for h in HOTKEYS:
            user32.UnregisterHotKey(None, h[0])

    def stop(self):
        if self.tid:
            try:
                ctypes.windll.user32.PostThreadMessageW(self.tid, 0x0012, 0, 0)  # WM_QUIT
            except Exception:
                pass


class Tray:
    """Icon down by the clock (notification area). Needs the pystray package."""

    def __init__(self, events, image):
        self.icon = None
        try:
            import pystray
        except Exception:
            return

        def send(*ev):
            return lambda icon, item: events.put(ev)
        menu = pystray.Menu(
            pystray.MenuItem("Show Mixie", send("show"), default=True),
            pystray.MenuItem("Game profile", send("profile", "Game")),
            pystray.MenuItem("Music profile", send("profile", "Music")),
            pystray.MenuItem("Play / pause", send("media", "play")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", send("quit")))
        try:
            self.icon = pystray.Icon(APP_ID, image, APP_NAME, menu)
            self.icon.run_detached()
        except Exception as e:
            log_error(f"Tray icon: {e}")
            self.icon = None

    def notify(self, text):
        try:
            if self.icon:
                self.icon.notify(text, APP_NAME)
        except Exception:
            pass

    def stop(self):
        try:
            if self.icon:
                self.icon.stop()
        except Exception:
            pass


def collect_sessions():
    groups = {}
    try:
        from pycaw.pycaw import IAudioMeterInformation
    except Exception:
        IAudioMeterInformation = None
    for s in AudioUtilities.GetAllSessions():
        try:
            proc = s.Process
            if proc and proc.pid == OWN_PID:
                continue  # Mixie itself
            key = proc.name().lower() if proc else "__system__"
            vol = s.SimpleAudioVolume
        except Exception:
            continue
        g = groups.setdefault(key, {"vols": [], "proc": None, "meters": []})
        g["vols"].append(vol)
        if key in VOICE_APPS and IAudioMeterInformation is not None:
            try:
                g["meters"].append(s._ctl.QueryInterface(IAudioMeterInformation))
            except Exception:
                pass
        if proc and g["proc"] is None:
            g["proc"] = proc
    return groups


def proc_exe(proc):
    try:
        return proc.exe() if proc else None
    except Exception:
        return None


# ---------------------------------------------------------------- drawing helpers

def draw_speaker(d, cx, cy, s, color, muted=False, xcolor=None):
    """Speaker icon drawn with shapes (s = icon size in pixels)."""
    d.rectangle((cx - 0.42 * s, cy - 0.16 * s, cx - 0.18 * s, cy + 0.16 * s), fill=color)
    d.polygon([(cx - 0.2 * s, cy - 0.16 * s), (cx + 0.06 * s, cy - 0.42 * s),
               (cx + 0.06 * s, cy + 0.42 * s), (cx - 0.2 * s, cy + 0.16 * s)], fill=color)
    w = max(1, round(0.085 * s))
    if muted:
        xc = xcolor or color
        a, b = cx + 0.3 * s, 0.13 * s
        d.line((a - b, cy - b, a + b, cy + b), fill=xc, width=w)
        d.line((a - b, cy + b, a + b, cy - b), fill=xc, width=w)
    else:
        for r in (0.24 * s, 0.44 * s):
            d.arc((cx + 0.06 * s - r, cy - r, cx + 0.06 * s + r, cy + r), -48, 48, fill=color, width=w)


def draw_layers_icon(d, cx, cy, s, color, width):
    """Two windows on top of each other (for 'Always on top')."""
    r = 0.08 * s
    d.rounded_rectangle((cx - 0.4 * s, cy - 0.15 * s, cx + 0.15 * s, cy + 0.38 * s), radius=r,
                        outline=color, width=width)
    d.rounded_rectangle((cx - 0.15 * s, cy - 0.4 * s, cx + 0.4 * s, cy + 0.13 * s), radius=r,
                        fill=color)


def device_kind(name):
    n = (name or "").lower()
    if any(k in n for k in ("hörlur", "headphone", "headset", "arctis", "hyperx", "earbud", "airpods",
                            "buds", "kraken", "blackshark", "astro", "corsair hs", "virtuoso", "wh-1000",
                            "beats", "jabra", "hands-free", "nari", "barracuda", "cloud")):
        return "headphones"
    if any(k in n for k in ("hdmi", "displayport", "nvidia high definition", "amd high definition",
                            "monitor", " tv", "tv ", "display audio", "intel(r) display")):
        return "monitor"
    return "speaker"


def draw_device_icon(d, cx, cy, s, kind, color, width=None):
    """Own icon per kind of audio device: headphones, speaker or monitor."""
    w = width or max(1, round(0.09 * s))
    if kind == "headphones":
        d.arc((cx - 0.38 * s, cy - 0.4 * s, cx + 0.38 * s, cy + 0.36 * s), 180, 360, fill=color, width=w)
        for sg in (-1, 1):
            x0, x1 = sorted((cx + sg * 0.42 * s, cx + sg * 0.2 * s))
            d.rounded_rectangle((x0, cy - 0.04 * s, x1, cy + 0.38 * s), radius=0.07 * s, fill=color)
    elif kind == "monitor":
        d.rounded_rectangle((cx - 0.44 * s, cy - 0.34 * s, cx + 0.44 * s, cy + 0.2 * s), radius=0.06 * s,
                            outline=color, width=w)
        d.line((cx, cy + 0.2 * s, cx, cy + 0.34 * s), fill=color, width=w)
        d.line((cx - 0.2 * s, cy + 0.36 * s, cx + 0.2 * s, cy + 0.36 * s), fill=color, width=w)
    else:  # speaker box
        d.rounded_rectangle((cx - 0.3 * s, cy - 0.44 * s, cx + 0.3 * s, cy + 0.44 * s), radius=0.08 * s,
                            outline=color, width=w)
        r1 = 0.15 * s
        d.ellipse((cx - r1, cy + 0.12 * s - r1, cx + r1, cy + 0.12 * s + r1), outline=color, width=w)
        r2 = 0.06 * s
        d.ellipse((cx - r2, cy - 0.24 * s - r2, cx + r2, cy - 0.24 * s + r2), fill=color)


def draw_dots_icon(d, cx, cy, s, color):
    r = 0.11 * s
    for dx in (-0.34, 0, 0.34):
        d.ellipse((cx + dx * s - r, cy - r, cx + dx * s + r, cy + r), fill=color)


def draw_profile_icon(d, cx, cy, s, color):
    """Two horizontal sliders."""
    w = max(1, round(0.1 * s))
    for dy, kx in ((-0.2, 0.18), (0.2, -0.2)):
        y = cy + dy * s
        d.line((cx - 0.4 * s, y, cx + 0.4 * s, y), fill=color, width=w)
        r = 0.13 * s
        d.ellipse((cx + kx * s - r, y - r, cx + kx * s + r, y + r), fill=color)


def draw_media_icon(d, cx, cy, s, kind, color):
    if kind in ("play", "pause_play"):
        d.polygon([(cx - 0.22 * s, cy - 0.32 * s), (cx + 0.32 * s, cy), (cx - 0.22 * s, cy + 0.32 * s)], fill=color)
    elif kind == "pause":
        for dx in (-0.2, 0.12):
            d.rectangle((cx + dx * s, cy - 0.3 * s, cx + (dx + 0.12) * s, cy + 0.3 * s), fill=color)
    elif kind in ("next", "prev"):
        sg = 1 if kind == "next" else -1
        d.polygon([(cx - 0.26 * s * sg, cy - 0.28 * s), (cx + 0.14 * s * sg, cy), (cx - 0.26 * s * sg, cy + 0.28 * s)],
                  fill=color)
        x = cx + 0.18 * s * sg
        d.rectangle((min(x, x + 0.1 * s * sg), cy - 0.28 * s, max(x, x + 0.1 * s * sg), cy + 0.28 * s), fill=color)


def outfit_head(style, u=1):
    """The buddy's head (pixel image) in the chosen outfit – used as an icon."""
    img = make_sprite(dict(FRAMES[0], note=None, la="down", ra="down", eyes="happy", sing=False), style)
    head = img.crop((1, 0, 23, SPRITE_TOP + 19))    # including tall hats
    return head.resize((head.width * u, head.height * u), NEAREST)


def menu_tile(head, auto=False, u=1):
    """Small dark tile with an icon inside, so it shows in both light and dark menus."""
    size = 26 * u
    tile = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
    ImageDraw.Draw(tile).rounded_rectangle((0, 0, size * SS - 1, size * SS - 1), radius=6 * u * SS,
                                           fill=(36, 37, 46, 255))
    tile = tile.reduce(SS)
    h = head.resize((head.width * 22 * u // max(head.width, head.height),
                     head.height * 22 * u // max(head.width, head.height)), NEAREST)
    tile.alpha_composite(h, ((size - h.width) // 2, (size - h.height) // 2 + u))
    if auto:   # small star = "by season"
        d = ImageDraw.Draw(tile)
        for dx, dy in ((0, -1), (-1, 0), (0, 0), (1, 0), (0, 1)):
            x, y = size - 4 * u + dx * u, 4 * u + dy * u
            d.rectangle((x, y, x + u - 1, y + u - 1), fill=(255, 216, 74, 255))
    return tile


def device_tile(kind, u=1):
    size = 26 * u
    big = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    d.rounded_rectangle((0, 0, size * SS - 1, size * SS - 1), radius=6 * u * SS, fill=(36, 37, 46, 255))
    col = {"headphones": (255, 140, 198, 255), "monitor": (120, 190, 255, 255)}.get(kind, (255, 255, 255, 255))
    draw_device_icon(d, size * SS / 2, size * SS / 2, 15 * u * SS, kind, col, width=max(2, round(1.5 * u * SS)))
    return big.reduce(SS)


def fit_text(text, fnt, maxw):
    if fnt.getlength(text) <= maxw:
        return text
    while text and fnt.getlength(text + "\u2026") > maxw:
        text = text[:-1]
    return text.rstrip() + "\u2026"


def make_background(w, h):
    base = Image.new("RGB", (w, h), BG_BASE)
    mask = ImageOps.invert(Image.radial_gradient("L"))
    g1 = mask.resize((int(w * 1.7), int(h * 1.1))).point(lambda v: int(v * 0.95))
    base.paste(Image.new("RGB", g1.size, BG_GLOW), (int(-w * 0.35), int(-h * 0.55)), g1)
    g2 = mask.resize((int(w * 1.2), int(h * 0.8))).point(lambda v: int(v * 0.45))
    base.paste(Image.new("RGB", g2.size, (16, 19, 30)), (int(w * 0.25), int(h * 0.55)), g2)
    return base.convert("RGBA")


def ribbon(pts, width):
    """Outline of a thick line along pts, as one polygon (much faster than a wide line with
    rounded joints, and just as smooth when the points are close together)."""
    h = width / 2
    left, right = [], []
    last = len(pts) - 1
    for i, (x, y) in enumerate(pts):
        x0, y0 = pts[i - 1] if i else pts[i]
        x1, y1 = pts[i + 1] if i < last else pts[i]
        dx, dy = x1 - x0, y1 - y0
        d = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / d * h, dx / d * h
        left.append((x + nx, y + ny))
        right.append((x - nx, y - ny))
    return left + right[::-1]


def sx(box):
    return [v * SS for v in box]


# ---------------------------------------------------------------- user interface

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.S = max(1.0, self.winfo_fpixels("1i") / 96.0)
        self.cfg = load_config()
        self.cfg.setdefault("hidden", [])
        self.cfg.setdefault("topmost", False)
        self.cfg.setdefault("compact", False)
        self.cfg.setdefault("tray", True)
        self.cfg.setdefault("hotkeys", True)
        self.cfg.setdefault("outfit", "auto")
        self.cfg.setdefault("dress_follow", True)
        self.cfg.setdefault("profiles", {})
        self.cfg.setdefault("profile", None)
        duck = self.cfg.setdefault("duck", {})
        duck.setdefault("on", False)
        duck.setdefault("level", 30)
        self.L = LAYOUTS["compact" if self.cfg["compact"] else "normal"]

        self.title(APP_NAME)
        self.configure(bg="#06070a")
        self.resizable(False, False)

        # app icon (window, taskbar, shortcut)
        self.icon_file = ensure_icon_file(self.cfg)
        try:
            self._icon_img = ImageTk.PhotoImage(make_app_icon(64))
            self.iconphoto(True, self._icon_img)
        except Exception:
            pass
        if self.icon_file:
            try:
                self.iconbitmap(default=self.icon_file)
            except Exception:
                pass

        self.W = self.p(self.L["width"])
        self.H = 0
        self.canvas = tk.Canvas(self, width=self.W, height=self.p(240), bg="#06070a",
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self.frame_item = self.canvas.create_image(0, 0, anchor="nw")
        self.header_item = self.canvas.create_image(0, 0, anchor="nw")
        self.hh = self.p(HEADER) - self.p(MARGIN)  # the header area with the waves

        # the dancer
        sc = max(2, round(3 * self.S))

        self.sc = sc
        self.sprite_cache = {}
        self.palette_i = 0
        self.build_sprites()
        self.sprite_w = SPRITE_W * sc
        self.sprite_h = SPRITE_H * sc
        self.sprite_x = self.W - self.p(PAD) - self.sprite_w + self.p(6)
        self.sprite_item = self.canvas.create_image(self.sprite_x, self.p(SPRITE_Y), anchor="nw",
                                                    image=self.idle_sprites[0])
        self.dance_i = 0
        self.move = None            # current dance move
        self.move_left = 0          # frames left before she switches move
        self.last_k = None          # last frame slot on the beat grid
        self.grid_beat = None       # last beat on the beat grid (for the music notes)
        self.idle_i = 0
        self.dancing = False
        self.last_sound = 0.0
        self.mode = "dance"         # calm / dance / hype
        self.energy = 0.0
        self.state_name = "idle"    # dance / idle / sleep
        self.react = None           # ("wave" | "surprise", ends_at)
        self.woken_at = time.time()
        self.speech = None          # (text, ends_at)
        self.last_lines = {}
        self.hop_t = None           # when she jumped (click)
        self.hover_girl_t = 0.0
        self.loud_t = 0.0
        self.last_note_t = 0.0
        self.last_z_t = 0.0
        self.started_t = time.time()
        self.bubbles = {}
        self.bubble_text = None
        self.bubble_y = self.p(SPRITE_Y) + (4 + SPRITE_TOP) * sc
        self.bubble_item = self.canvas.create_image(self.sprite_x - self.p(2), self.bubble_y,
                                                    anchor="ne", state="hidden")
        self.canvas.tag_raise(self.sprite_item)   # the buddy is drawn on top of her speech bubble
        self.fx = []
        self.fx_imgs = {}
        self.sprite_y = None

        self.rows = []
        self.order = None
        self.hover = None          # what the mouse is over, e.g. ("row", 2), ("media", "play"), ("girl",)
        self.drag = None           # row being dragged
        self.tiles = {}
        self.icons = {}
        self.bg = None
        self.bg_cache = {}
        self.wave_base = None
        self.photo = None
        self.header_photo = None
        self.last_sig = None
        self.ticks = 0
        self.level = 0.0
        self.analyzer = Off() if SAFE_MODE else Analyzer()
        self.band_vals = [0.0, 0.0, 0.0, 0.0]
        self.beat = 0.0
        self.seen_beats = 0
        self.phases = [k * 1.7 for k in range(len(WAVES))]
        self.now_playing = Off() if SAFE_MODE else NowPlaying()
        self.seen_changes = 0
        self.palette_i = 0
        self.wave_cols = [list(c) for c in PALETTES[0]]
        self.silent_since = None
        self._gap = False
        self.last_wave_t = time.perf_counter()
        self.master_ctl = find_master()
        self.meter = find_meter()
        self.menu_icons = {}
        self.events = queue.Queue()
        self.hotkeys = Hotkeys(self.events) if self.cfg["hotkeys"] else None
        self.tray = None
        self.voice_meters = []
        self.duck_amt = 1.0
        self.duck_last = 0.0
        self.media_sig = None
        self.device_name = default_device_name()

        self.menu = tk.Menu(self, tearoff=0, bg="#1b1c21", fg="#ffffff", activebackground="#ffffff",
                            activeforeground="#0e0f13", bd=0, font=("Segoe UI", 10))

        c = self.canvas
        c.bind("<Motion>", self.on_motion)
        c.bind("<Leave>", self.on_leave)
        c.bind("<ButtonPress-1>", self.on_press)
        c.bind("<B1-Motion>", self.on_drag)
        c.bind("<ButtonRelease-1>", self.on_release)
        c.bind("<Double-Button-1>", self.on_double)
        c.bind("<MouseWheel>", self.on_wheel)
        c.bind("<Button-3>", self.on_right)

        self.attributes("-topmost", self.cfg["topmost"])
        pos = self.cfg.get("position")
        if pos and point_on_screen(pos[0], pos[1]):
            self.geometry(f"+{pos[0]}+{pos[1]}")

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Unmap>", self.on_unmap)
        self.resize()
        dark_titlebar(self)
        set_window_icon(self, self.icon_file)
        self.refresh()
        self.dance()
        self.bounce()
        self.waves()
        self.after(800, self.first_run)
        self.after(100, self.duck_tick)
        self.after(600, self.start_tray)

    # -- first start: desktop shortcut
    def first_run(self):
        # Done if the program never got a shortcut, or if the folder was moved.
        if sys.platform != "win32":
            return
        is_new = not (self.cfg.get("shortcut_link") and self.cfg.get("shortcut_for") == SCRIPT)
        if not is_new and self.cfg.get("shortcut_icon_v") == ICON_VERSION:
            return
        result = {}
        threading.Thread(target=lambda: result.setdefault("r", create_shortcuts(self.icon_file, in_process=False)),
                         daemon=True).start()

        def done():
            if "r" not in result:
                self.after(200, done)
                return
            link, errors = result["r"]
            if link:
                self.cfg["shortcut_link"] = link
                self.cfg["shortcut_for"] = SCRIPT
                self.cfg["shortcut_icon_v"] = ICON_VERSION
                try:
                    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
                except Exception:
                    pass
                if not is_new:      # only the icon was refreshed – no need to tell anyone
                    save_config(self.cfg)
                    return
                messagebox.showinfo(APP_NAME, "A \"Mixie\" shortcut is now on your desktop "
                                              "and in the Start menu.\n\nUse it to start the program "
                                              "from now on.", parent=self)
            elif not self.cfg.get("shortcut_error_shown"):
                self.cfg["shortcut_error_shown"] = True
                self.shortcut_failed(errors)
            save_config(self.cfg)
        done()

    def shortcut_failed(self, errors):
        messagebox.showerror(
            APP_NAME,
            "Could not create the shortcut automatically.\n\n"
            "Do this instead:\n"
            "1. Right-click the desktop → New → Shortcut\n"
            f"2. Paste:\n   \"{window_python()}\" \"{SCRIPT}\"\n"
            "3. Name it Mixie\n\n"
            "Details:\n" + "\n".join(errors)[:600], parent=self)

    # -- sizes
    def p(self, v):
        return int(round(v * self.S))

    def media_shown(self):
        return getattr(self.now_playing, "display", None) is not None

    def media_top(self):
        return self.p(HEADER)

    def content_top(self):
        top = self.p(HEADER)
        if self.media_shown():
            top += self.p(self.L["media_h"]) + self.p(self.L["gap"])
        return top

    def row_top(self, i):
        return self.content_top() + i * (self.p(self.L["row_h"]) + self.p(self.L["gap"]))

    def track(self, i):
        L = self.L
        return self.p(PAD + L["name_x"]), self.W - self.p(PAD + L["slider_r"]), self.row_top(i) + self.p(L["slider_y"])

    def mute_center(self, i):
        return self.W - self.p(PAD + self.L["mute_x"]), self.row_top(i) + self.p(self.L["row_h"]) / 2

    def header_buttons(self):
        """The buttons to the right of the name: Outfit, Audio device, Profile, Menu (⋯)."""
        p = self.p
        x2 = self.W - p(PAD)
        y1, y2 = p(BTN_Y[0]), p(BTN_Y[1])
        out = {}
        for name, w in (("menubtn", 40), ("profbtn", 40), ("devbtn", 40), ("outfitbtn", 40)):
            out[name] = (x2 - p(w), y1, x2, y2)
            x2 -= p(w) + p(8)
        return out

    def shown_bpm(self):
        """The tempo to show, rounded and steady (None while unsure)."""
        an = self.analyzer
        if self.dancing and an.bpm and an.tempo_conf > 0.35:
            return int(round(an.bpm))
        return None

    def media_buttons(self):
        p, L = self.p, self.L
        top = self.media_top()
        cy = top + p(L["media_h"]) / 2
        r = p(15 if L["compact"] else 18)
        x = self.W - p(PAD) - p(16) - r
        out = {}
        for name in ("next", "play", "prev"):
            out[name] = (x, cy, r)
            x -= 2 * r + p(8)
        return out

    def hit(self, x, y):
        def inside(b):
            return b[0] <= x <= b[2] and b[1] <= y <= b[3]
        if inside(self.girl_box()):
            return ("girl",)
        for name, b in self.header_buttons().items():
            if inside(b):
                return (name,)
        if self.media_shown():
            for name, (cx, cy, r) in self.media_buttons().items():
                if (x - cx) ** 2 + (y - cy) ** 2 <= (r + self.p(3)) ** 2:
                    return ("media", name)
        if self.p(PAD) <= x <= self.W - self.p(PAD):
            for i in range(len(self.rows)):
                t = self.row_top(i)
                if t <= y <= t + self.p(self.L["row_h"]):
                    cx, cy = self.mute_center(i)
                    if (x - cx) ** 2 + (y - cy) ** 2 <= (self.p(self.L["mute_r"]) + self.p(3)) ** 2:
                        return ("mute", i)
                    return ("row", i)
        return None

    # -- rendering
    def window_height(self):
        n = len(self.rows)
        L = self.L
        h = self.content_top()
        if n:
            h += n * self.p(L["row_h"]) + (n - 1) * self.p(L["gap"]) + self.p(PAD)
        else:
            h += self.p(130)
        return h

    def background(self, h):
        bg = self.bg_cache.get(h)
        if bg is None:
            if len(self.bg_cache) > 12:
                self.bg_cache.clear()
            bg = self.bg_cache[h] = make_background(self.W, h)
        return bg

    def resize(self):
        h = self.window_height()
        if h == self.H:
            return
        self.H = h
        self.canvas.config(height=h)
        self.bg = self.background(h)
        # the background behind the waves
        self.wave_base = self.bg.crop((0, 0, self.W, self.hh)).convert("RGB")

    def cached(self, key, fn):
        """Small cache of finished pieces of the window. The most recently used are kept, the
        oldest are thrown away (dragging a slider makes a new picture for every value)."""
        tiles = self.tiles
        img = tiles.pop(key, None)
        if img is None:
            img = fn()
            if len(tiles) >= 90:
                for old in list(tiles)[:30]:
                    del tiles[old]
        tiles[key] = img      # (re)insert = mark as most recently used
        return img

    def header_tile(self):
        p, W, L = self.p, self.W, self.L
        n = len(self.rows) - (1 if self.rows and self.rows[0]["key"] == "__master__" else 0)
        prof = self.cfg.get("profile")
        hov = self.hover if self.hover and self.hover[0] in ("outfitbtn", "devbtn", "profbtn", "menubtn") else None
        dev = short_device(self.device_name, 18 if L["compact"] else 26)
        kind = device_kind(self.device_name)
        style = self.current_style()

        def build():
            h = self.hh
            big = Image.new("RGBA", (W * SS, h * SS), (0, 0, 0, 0))
            d = ImageDraw.Draw(big)
            boxes = self.header_buttons()
            for name, b in boxes.items():
                hovered = hov == (name,)
                rad = (b[3] - b[1]) * SS // 2
                d.rounded_rectangle(sx(b), radius=rad, fill=WHITE if hovered else CARD)
                col = DARK if hovered else SUB
                ix = (b[0] + b[2]) / 2 * SS
                iy = (b[1] + b[3]) / 2 * SS
                if name == "profbtn":
                    draw_profile_icon(d, ix, iy, p(16) * SS, col)
                elif name == "devbtn":
                    draw_device_icon(d, ix, iy, p(17) * SS, kind, col)
                elif name == "menubtn":
                    draw_dots_icon(d, ix, iy, p(18) * SS, col)
            img = big.reduce(SS)
            # outfit button: the buddy's head in the outfit she is wearing (pixel image)
            b = boxes["outfitbtn"]
            head = outfit_head(style, max(1, round(self.S)))
            img.alpha_composite(head, (int((b[0] + b[2]) / 2 - head.width / 2),
                                       int((b[1] + b[3]) / 2 - head.height / 2)))
            parts = ["Sound", "1 app" if n == 1 else f"{n} apps"]
            if prof:
                parts.append(prof)
            if dev:
                parts.append(dev)
            sub = "  \u00b7  ".join(parts)
            title_font, sub_font = font("semilight", p(L["title_font"])), font("regular", p(12 if L["compact"] else 13))
            t = ImageDraw.Draw(img)
            t.text((p(PAD), p(TITLE_Y)), APP_NAME, font=title_font, fill=TEXT, anchor="lm")
            maxw = boxes["outfitbtn"][0] - p(PAD) - p(10)
            t.text((p(PAD), p(SUB_Y)), fit_text(sub, sub_font, maxw), font=sub_font,
                   fill=(196, 199, 210, 255), anchor="lm")
            return img

        key = ("hdr", W, n, hov, prof, dev, kind, style["acc"], tuple(style["D"]), L["compact"])
        return self.cached(key, build)

    # -- the "now playing" card
    def media_tile(self):
        p, W, L = self.p, self.W, self.L
        np_ = self.now_playing
        song, artist = np_.display
        app = np_.app
        hov = self.hover[1] if self.hover and self.hover[0] == "media" else None
        has_icon = self.icons.get(app) is not None
        bpm = self.shown_bpm()
        key = ("media", W, song, artist, app, np_.paused, hov, has_icon, bpm)

        def build():
            h = p(L["media_h"])
            big = Image.new("RGBA", (W * SS, h * SS), (0, 0, 0, 0))
            d = ImageDraw.Draw(big)
            d.rounded_rectangle(sx((p(PAD), 0, W - p(PAD), h)), radius=p(18) * SS, fill=CARD)
            ts = h - p(24)
            tx, ty = p(PAD) + p(12), p(12)
            d.rounded_rectangle(sx((tx, ty, tx + ts, ty + ts)), radius=p(10) * SS,
                                fill=TILE if has_icon else app_color(app or "spotify.exe"))
            if not has_icon:
                for py, row in enumerate(FX_PATTERNS["note"]):
                    for px_, ch in enumerate(row):
                        if ch == "X":
                            u = ts / 9
                            x0, y0 = tx + ts / 2 - 2 * u + px_ * u, ty + ts / 2 - 2.5 * u + py * u
                            d.rectangle(sx((x0, y0, x0 + u, y0 + u)), fill=WHITE)
            top = self.media_top()
            for name, (cx, cy, r) in self.media_buttons().items():
                cy -= top
                primary = name == "play"
                hovered = hov == name
                fill = WHITE if primary or hovered else BTN
                d.ellipse(sx((cx - r, cy - r, cx + r, cy + r)), fill=fill)
                if hovered and primary:
                    d.ellipse(sx((cx - r, cy - r, cx + r, cy + r)), outline=BLUE, width=p(2) * SS)
                kind = name if name != "play" else ("play" if np_.paused else "pause")
                draw_media_icon(d, cx * SS, cy * SS, r * 1.15 * SS, kind, DARK if fill == WHITE else WHITE)
            img = big.reduce(SS)
            if has_icon:
                isz = int(ts * 0.72)
                ic = self.icon_tile(app, isz, False)
                if ic is not None:
                    img.alpha_composite(ic, (tx + (ts - isz) // 2, ty + (ts - isz) // 2))
            t = ImageDraw.Draw(img)
            x = tx + ts + p(14)
            maxw = self.media_buttons()["prev"][0] - self.media_buttons()["prev"][2] - x - p(12)
            f1 = font("semi", p(13 if L["compact"] else 15))
            f2 = font("regular", p(11 if L["compact"] else 12))
            label = "PAUSED  \u00b7  " if np_.paused else ""
            t.text((x, h / 2 - p(9)), fit_text(song, f1, maxw), font=f1, fill=TEXT, anchor="lm")
            line = label + artist
            if bpm and not np_.paused:
                tag = f"{bpm} BPM"
                tw = f2.getlength(tag) + p(12)
                line = fit_text(line, f2, maxw - tw)
                t.text((x + f2.getlength(line) + p(10), h / 2 + p(11)), tag, font=f2, fill=PINK, anchor="lm")
            t.text((x, h / 2 + p(11)), fit_text(line, f2, maxw), font=f2, fill=SUB, anchor="lm")
            return img

        return self.cached(key, build)

    def icon_tile(self, key, size, muted):
        """The app icon (or letter), ready to paste in, at the right size."""
        def build():
            src = self.icons.get(key)
            if src is None:
                return None
            img = src.resize((size, size), LANCZOS)
            if muted:
                a = img.getchannel("A")
                img = ImageOps.grayscale(img.convert("RGB")).point(lambda v: int(v * 0.55)).convert("RGBA")
                img.putalpha(a)
            return img
        return self.cached(("icon", key, size, muted, id(self.icons.get(key))), build)

    def row_tile(self, i, r):
        p, W, L = self.p, self.W, self.L
        active = self.hover in (("row", i), ("mute", i)) or self.drag == i
        hm = self.hover == ("mute", i)
        has_icon = self.icons.get(r["key"]) is not None
        ducked = self.duck_amt < 0.98 and category(r["key"]) == "music"
        key = ("row", W, r["key"], r["vol"], r["muted"], active, hm, has_icon, ducked and round(self.duck_amt, 2))

        def build():
            M = p(MARGIN)
            RH = p(L["row_h"])
            h = RH + 2 * M
            big = Image.new("RGBA", (W * SS, h * SS), (0, 0, 0, 0))
            d = ImageDraw.Draw(big)
            muted = r["muted"]
            grow = p(4) if active else 0
            rad = p(16 if L["compact"] else 18)

            # card
            box = ((p(PAD) - grow) * SS, (M - grow) * SS, (W - p(PAD) + grow) * SS, (M + RH + grow) * SS)
            d.rounded_rectangle(box, radius=rad * SS, fill=CARD_ACTIVE if active else CARD)
            if active:
                d.rounded_rectangle(box, radius=rad * SS, outline=WHITE, width=max(2, round(2.5 * self.S * SS)))

            # app tile
            ts = p(L["icon"])
            tx, ty = p(PAD + L["icon_x"]), M + (RH - ts) // 2
            tile_col = TILE if has_icon else (DIM if muted else app_color(r["key"]))
            d.rounded_rectangle(sx((tx, ty, tx + ts, ty + ts)), radius=p(L["icon"] * 0.27) * SS, fill=tile_col)
            if r["key"] in ("__master__", "__system__") and not has_icon:
                draw_speaker(d, (tx + ts / 2) * SS, (ty + ts / 2) * SS, ts * 0.55 * SS, WHITE)

            # slider
            tx0, tx1 = p(PAD + L["name_x"]), W - p(PAD + L["slider_r"])
            yy = M + p(L["slider_y"])
            th = p(4)
            fx = tx0 + (tx1 - tx0) * r["vol"] / 100
            col = DIM if muted else WHITE
            d.rounded_rectangle(sx((tx0, yy - th / 2, tx1, yy + th / 2)), radius=th * SS // 2, fill=TRACK)
            if ducked and not muted:   # where the music actually is while it is lowered
                dx = tx0 + (tx1 - tx0) * r["vol"] * self.duck_amt / 100
                if dx > tx0 + th:
                    d.rounded_rectangle(sx((tx0, yy - th / 2, dx, yy + th / 2)), radius=th * SS // 2,
                                        fill=PINK)
            elif fx > tx0 + th:
                d.rounded_rectangle(sx((tx0, yy - th / 2, fx, yy + th / 2)), radius=th * SS // 2, fill=col)
            kr = p(9) if active else p(6)
            d.ellipse(sx((fx - kr, yy - kr, fx + kr, yy + kr)), fill=col)

            # mute button (white when highlighted, like PS5 buttons)
            mx, my = W - p(PAD + L["mute_x"]), M + RH / 2
            mr = p(L["mute_r"])
            d.ellipse(sx((mx - mr, my - mr, mx + mr, my + mr)), fill=WHITE if hm else BTN)
            draw_speaker(d, (mx - p(2)) * SS, my * SS, mr * 1.05 * SS, DARK if hm else WHITE,
                         muted=muted, xcolor=MUTE_ORANGE)

            img = big.reduce(SS)

            # soft glow around the highlighted card
            if active:
                m = Image.new("L", (W, h), 0)
                ImageDraw.Draw(m).rounded_rectangle(
                    (p(PAD) - grow, M - grow, W - p(PAD) + grow, M + RH + grow), radius=rad, fill=255)
                m = m.filter(ImageFilter.GaussianBlur(p(9))).point(lambda v: int(v * 0.32))
                glow = Image.new("RGBA", (W, h), (255, 255, 255, 0))
                glow.putalpha(m)
                img = Image.alpha_composite(glow, img)

            if has_icon:
                isz = p(L["icon_img"])
                ic = self.icon_tile(r["key"], isz, muted)
                if ic is not None:
                    img.alpha_composite(ic, (tx + (ts - isz) // 2, ty + (ts - isz) // 2))

            t = ImageDraw.Draw(img)
            if not has_icon and r["key"] not in ("__master__", "__system__"):
                t.text((tx + ts / 2, ty + ts / 2), pretty_name(r["key"])[:1],
                       font=font("semi", int(ts * 0.43)), fill=TEXT, anchor="mm")
            name_font = font("semi", p(L["name_font"]))
            name = pretty_name(r["key"])
            t.text((p(PAD + L["name_x"]), M + p(L["name_y"])), name, font=name_font,
                   fill=SUB if muted else TEXT, anchor="lm")
            if ducked:
                t.text((p(PAD + L["name_x"]) + name_font.getlength(name) + p(8), M + p(L["name_y"])),
                       "lowered \u2013 someone is talking", font=font("regular", p(11)), fill=PINK, anchor="lm")
            t.text((W - p(PAD + L["num_x"]), M + RH / 2), str(r["vol"]), font=font("light", p(L["num_font"])),
                   fill=SUB if muted else TEXT, anchor="rm")
            return img

        return self.cached(key, build)

    def render(self):
        if self.bg is None:
            return
        frame = self.bg.copy()
        if self.media_shown():
            frame.alpha_composite(self.media_tile(), (0, self.media_top()))
        M = self.p(MARGIN)
        active = None
        for i, r in enumerate(self.rows):
            if self.hover in (("row", i), ("mute", i)) or self.drag == i:
                active = (i, r)
                continue
            frame.alpha_composite(self.row_tile(i, r), (0, self.row_top(i) - M))
        if active:
            i, r = active
            frame.alpha_composite(self.row_tile(i, r), (0, self.row_top(i) - M))
        if not self.rows:
            ImageDraw.Draw(frame).text(
                (self.W / 2, self.content_top() + self.p(60)),
                "No programs are playing sound right now\nStart Spotify, Firefox or your game",
                font=font("regular", self.p(15)), fill=SUB, anchor="mm", align="center")
        ph = self.photo
        if ph is None or ph.width() != frame.width or ph.height() != frame.height:
            self.photo = ImageTk.PhotoImage(frame)
            self.canvas.itemconfig(self.frame_item, image=self.photo)
        else:
            ph.paste(frame)
        self.draw_header()

    # -- sound waves behind the header
    def draw_header(self):
        if self.wave_base is None:
            return
        W, hh = self.W, self.hh
        out = self.wave_base.copy()
        Z = WAVE_SS
        cy = self.p(WAVE_CY)
        full = self.p(WAVE_AMP)
        beat = self.beat
        S = self.S
        waves = []
        for k, (speed, cycles, strength, band) in enumerate(WAVES):
            col = tuple(int(c) for c in self.wave_cols[k])
            e = self.band_vals[band]
            amp = full * strength * (0.06 + 0.94 * e) * (1 + 0.35 * beat)
            ph = self.phases[k]
            ripple = 0.22 * e if band >= 2 else 0.0   # mid/treble get a little extra ripple
            n = int(60 + cycles * (40 if ripple else 22))  # more points for dense waves = no corners
            sin = math.sin
            pts = []
            for j in range(n + 1):
                x = j / n
                env = (1 - (2 * x - 1) ** 2) ** 2
                a = x * cycles * 2 * math.pi + ph
                pts.append((x * W, cy + (sin(a) + ripple * sin(a * 3.1 - ph * 1.7)) * env * amp))
            waves.append((col, e, pts))

        # 1) soft glow for all four waves at once: drawn at half size, blurred once, then
        #    blended on with "screen" (adds light, like neon)
        G = 2
        glow = Image.new("RGB", (W // G, hh // G))
        gd = ImageDraw.Draw(glow)
        for col, e, pts in waves:
            g = min(1.0, 0.5 + 0.45 * beat + 0.25 * e)
            gd.polygon(ribbon([(x / G, y / G) for x, y in pts], max(1.5, 1.9 * S)),
                       fill=tuple(int(c * g) for c in col))
        glow = glow.filter(ImageFilter.GaussianBlur(2 * S)).resize((W, hh), BILINEAR)
        out = ImageChops.screen(out, glow)

        # 2) sharp core: drawn at 3x and scaled down = perfectly smooth edges.
        #    Only the strip where the wave is visible is drawn (fast, especially when quiet).
        cw = max(Z, round(1.6 * S * Z))
        for col, e, pts in waves:
            y0 = max(0, int(min(q[1] for q in pts)) - 3)
            y1 = min(hh, int(max(q[1] for q in pts)) + 4)
            sh = y1 - y0
            if sh <= 0:
                continue
            core = Image.new("L", (W * Z, sh * Z), 0)
            ImageDraw.Draw(core).polygon(ribbon([(x * Z, (y - y0) * Z) for x, y in pts], cw), fill=235)
            out.paste(col, (0, y0, W, y1), core.reduce(Z))
        out = out.convert("RGBA")
        out.alpha_composite(self.header_tile(), (0, 0))
        # Reuse the same Tk image and just update its pixels (much cheaper than a new image
        # every frame). The stacking order of the canvas items never changes, so no raising.
        hp = self.header_photo
        if hp is None or hp.width() != out.width or hp.height() != out.height:
            self.header_photo = ImageTk.PhotoImage(out)
            self.canvas.itemconfig(self.header_item, image=self.header_photo)
        else:
            hp.paste(out)

    def waves(self):
        try:
            if self.state() in ("iconic", "withdrawn"):  # minimized: go easy on the computer
                self.after(400, self.waves)
                return
        except Exception:
            pass
        now = time.perf_counter()
        dt = min(0.1, now - self.last_wave_t)
        self.last_wave_t = now

        an = self.analyzer
        if an.ok and time.time() - an.updated < 0.3:
            targets = list(an.bands)
            if an.beats != self.seen_beats:
                self.seen_beats = an.beats
                self.beat = 1.0
                self.on_beat()
        elif an.ok:
            targets = [0.0] * 4      # nothing playing
        else:
            # fallback if capture doesn't work: total level from Windows
            peak = 0.0
            if self.meter is not None:
                try:
                    peak = float(self.meter.GetPeakValue())
                except Exception:
                    pass
            lv = min(1.0, peak ** 0.6)
            targets = [lv, lv * 0.8, lv * 0.7, lv * 0.5]

        for i, tv in enumerate(targets):
            cur = self.band_vals[i]
            rate = 0.65 if tv > cur else 0.18      # fast up, softer down
            self.band_vals[i] = cur + (tv - cur) * rate
        self.beat *= 0.82 ** (dt / 0.033)
        self.level = max(self.band_vals)

        # is anything playing? (the buddy dances, otherwise she waits)
        t_now = time.time()
        if self.level > 0.07:
            self.last_sound = t_now
            self.silent_since = None
        elif self.silent_since is None:
            self.silent_since = t_now

        # new song -> new colour scheme
        np_ = self.now_playing
        if np_.changes != self.seen_changes:
            first = self.seen_changes == 0
            self.seen_changes = np_.changes
            self.pick_palette(np_.title)
            if not first:
                self.on_song_change()
        if not np_.ok:
            # fallback: silence for more than 1.5 s followed by sound counts as a new song
            if self.level > 0.07 and self._gap:
                self._gap = False
                self.pick_palette(None)
                self.on_song_change()
            elif self.silent_since and t_now - self.silent_since > 1.5:
                self._gap = True
        target = PALETTES[self.palette_i]
        fade = min(1.0, dt * 2.2)
        for c, tc in zip(self.wave_cols, target):
            for j in range(3):
                c[j] += (tc[j] - c[j]) * fade

        # the waves move faster the more happens in their band, and jolt on bass hits
        for k, (speed, _, _, band) in enumerate(WAVES):
            e = self.band_vals[band]
            self.phases[k] += dt * speed * (0.35 + 2.6 * e + 2.2 * self.beat)

        np_ = self.now_playing
        sig = (getattr(np_, "display", None), getattr(np_, "paused", False), self.shown_bpm())
        if sig != self.media_sig:
            shown_before = self.media_sig is not None and self.media_sig[0] is not None
            self.media_sig = sig
            if shown_before != (sig[0] is not None):
                self.resize()
            self.render()
        self.draw_header()
        self.after(WAVE_MS if self.level > 0.02 else WAVE_MS * 2, self.waves)

    def pick_palette(self, title):
        if title:
            i = zlib.crc32(title.encode("utf-8")) % len(PALETTES)
            if i == self.palette_i:
                i = (i + 1) % len(PALETTES)   # a new song should always be visible
        else:
            i = (self.palette_i + 1) % len(PALETTES)
        self.palette_i = i
        if self.cfg.get("dress_follow", True):
            self.after_idle(self.build_sprites)

    # -- the buddy's outfit
    def current_style(self):
        acc = self.cfg.get("outfit", "auto")
        if acc not in OUTFITS or acc == "auto":
            acc = season_outfit()
        if self.cfg.get("dress_follow", True):
            c = PALETTES[self.palette_i][0]
            return {"acc": acc, "D": c, "d": tuple(int(v * 0.66) for v in c)}
        return {"acc": acc, "D": PAL["D"], "d": PAL["d"]}

    def build_sprites(self):
        """Draws all frames of the buddy in the right outfit (cached, so each combination is drawn once)."""
        st = self.current_style()
        key = (st["acc"], tuple(st["D"]))
        sets = self.sprite_cache.get(key)
        if sets is None:
            sc = self.sc

            def sprite(f):
                return ImageTk.PhotoImage(make_sprite(f, st).resize((SPRITE_W * sc, SPRITE_H * sc), NEAREST))

            def many(frames, blink=False):
                normal = [sprite(f) for f in frames]
                return (normal, [sprite(dict(f, eyes="closed")) for f in frames]) if blink else normal
            sets = {
                "moves": {name: many(frames, True) for name, frames in DANCE_MOVES.items()},
                "idle": many(IDLE_FRAMES), "wave": many(WAVE_FRAMES),
                "surprise": many(SURPRISE_FRAMES), "sleep": many(SLEEP_FRAMES),
            }
            if len(self.sprite_cache) >= 4:      # ~3.5 MB per outfit/colour – keep the latest few
                del self.sprite_cache[next(iter(self.sprite_cache))]
            self.sprite_cache[key] = sets
        self.moves = sets["moves"]
        self.idle_sprites = sets["idle"]
        self.wave_sprites = sets["wave"]
        self.surprise_sprites = sets["surprise"]
        self.sleep_sprites = sets["sleep"]

    def set_outfit(self, acc):
        self.cfg["outfit"] = acc
        save_config(self.cfg)
        self.build_sprites()
        self.render()
        self.react = ("wave", time.time() + 1.4)
        self.say({"santa": "Ho ho ho!", "witch": "Boo! \u266a", "cat": "Meow!",
                  "sunglasses": "Cool, huh?", "headphones": "Now I can hear\neverything! \u266a"}.get(
            self.current_style()["acc"], "Thanks! \u266a"), 1.8)

    def toggle_dress(self):
        self.cfg["dress_follow"] = not self.cfg.get("dress_follow", True)
        save_config(self.cfg)
        self.build_sprites()
        self.render()

    # -- menus
    def popup_at(self, menu, box):
        x = self.canvas.winfo_rootx() + int(box[0])
        y = self.canvas.winfo_rooty() + int(box[3]) + self.p(4)
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def new_menu(self):
        return tk.Menu(self, tearoff=0, bg="#1b1c21", fg="#ffffff", activebackground="#ffffff",
                       activeforeground="#0e0f13", selectcolor="#ff8cc6", bd=0, font=("Segoe UI", 10))

    def open_main_menu(self):
        m = self.new_menu()
        self._menu_vars = []

        def check(label, value, cmd, state="normal"):
            v = tk.BooleanVar(value=bool(value))
            self._menu_vars.append(v)
            m.add_checkbutton(label=label, variable=v, command=cmd, state=state)

        check("Always on top", self.cfg["topmost"], self.toggle_topmost)
        check("Compact mode", self.cfg["compact"], self.toggle_compact)
        check("Minimize to the tray (by the clock)", self.cfg["tray"], self.toggle_tray,
              "normal" if self.tray and self.tray.icon else "disabled")
        m.add_separator()

        check("Lower the music when someone talks on Discord", self.cfg["duck"]["on"], self.toggle_duck)
        lvl_menu = self.new_menu()
        lv = tk.IntVar(value=self.cfg["duck"]["level"])
        self._menu_vars.append(lv)
        for pct, label in ((15, "A lot (15 %)"), (30, "Medium (30 %)"), (50, "A little (50 %)")):
            lvl_menu.add_radiobutton(label=label, value=pct, variable=lv,
                                     command=lambda pct=pct: self.set_duck_level(pct))
        m.add_cascade(label="How much the music is lowered", menu=lvl_menu)
        m.add_separator()

        check("Hotkeys", self.cfg["hotkeys"], self.toggle_hotkeys)
        m.add_command(label="Show hotkeys\u2026", command=self.show_hotkeys)
        m.add_separator()
        n = len(self.cfg["hidden"])
        if n:
            m.add_command(label=f"Show hidden programs ({n})", command=self.unhide_all)
        if sys.platform == "win32":
            m.add_command(label="Create desktop shortcut", command=self.make_shortcut)
        m.add_separator()
        m.add_command(label="About Mixie", command=self.show_about)
        m.add_command(label="Quit", command=self.on_close)
        self.popup_at(m, self.header_buttons()["menubtn"])

    def menu_icon(self, key, build):
        img = self.menu_icons.get(key)
        if img is None:
            if len(self.menu_icons) > 60:
                self.menu_icons.clear()
            img = self.menu_icons[key] = ImageTk.PhotoImage(build())
        return img

    def open_outfit_menu(self):
        m = self.new_menu()
        ov = tk.StringVar(value=self.cfg.get("outfit", "auto"))
        self._menu_vars = [ov]
        st = self.current_style()
        u = max(1, round(self.S))
        for acc in OUTFITS:
            shown = season_outfit() if acc == "auto" else acc
            look = dict(st, acc=shown)
            img = self.menu_icon(("outfit", shown, tuple(st["D"]), acc == "auto"),
                                 lambda look=look, auto=acc == "auto": menu_tile(outfit_head(look, u), auto, u))
            m.add_radiobutton(label="  " + OUTFIT_NAMES[acc], value=acc, variable=ov, image=img, compound="left",
                              command=lambda acc=acc: self.set_outfit(acc))
        m.add_separator()
        fv = tk.BooleanVar(value=self.cfg.get("dress_follow", True))
        self._menu_vars.append(fv)
        m.add_checkbutton(label="Dress follows the wave colours", variable=fv, command=self.toggle_dress)
        self.popup_at(m, self.header_buttons()["outfitbtn"])

    def open_device_menu(self):
        m = self.new_menu()
        try:
            devs = output_devices()
        except Exception as e:
            devs = []
            log_error(f"Audio devices: {e}")
        dv = tk.StringVar(value=next((d for d, _, default in devs if default), ""))
        self._menu_vars = [dv]
        u = max(1, round(self.S))
        for did, name, _ in devs:
            kind = device_kind(name)
            img = self.menu_icon(("dev", kind), lambda kind=kind: device_tile(kind, u))
            m.add_radiobutton(label="  " + name, value=did, variable=dv, image=img, compound="left",
                              command=lambda did=did, name=name: self.set_device(did, name))
        if not devs:
            m.add_command(label="No audio devices found", state="disabled")
        self.popup_at(m, self.header_buttons()["devbtn"])

    def show_about(self):
        if messagebox.askyesno(
                f"About {APP_NAME}",
                f"{APP_NAME} {APP_VERSION}\n"
                "A per-app volume mixer with a dancing pixel buddy.\n\n"
                f"Made by {AUTHOR}\n{REPO_URL}\n\n"
                "Open the project page on GitHub?", parent=self):
            import webbrowser
            webbrowser.open(REPO_URL)

    def open_profile_menu(self):
        m = self.new_menu()
        pv = tk.StringVar(value=self.cfg.get("profile") or "")
        self._menu_vars = [pv]
        for name in PROFILE_NAMES:
            hint = " (custom)" if name in self.cfg["profiles"] else ""
            m.add_radiobutton(label=f"{name}{hint}", value=name, variable=pv,
                              command=lambda name=name: self.apply_profile(name))
        m.add_separator()
        for name in PROFILE_NAMES:
            m.add_command(label=f"Save current volumes as \"{name}\"",
                          command=lambda name=name: self.save_profile(name))
        if self.cfg["profiles"]:
            m.add_command(label="Reset profiles", command=self.reset_profiles)
        self.popup_at(m, self.header_buttons()["profbtn"])

    # -- profiles
    def apply_profile(self, name):
        custom = self.cfg["profiles"].get(name)
        rules = DEFAULT_PROFILES.get(name, {})
        for i, r in enumerate(self.rows):
            k = r["key"]
            if k == "__master__":
                continue
            if custom is not None:
                if k in custom:
                    self.set_vol(i, custom[k])
            elif category(k) in rules:
                self.set_vol(i, rules[category(k)])
        self.cfg["profile"] = name
        save_config(self.cfg)
        self.render()
        self.say("Game mode!" if name == "Game" else "Music mode! \u266a", 1.6)

    def save_profile(self, name):
        self.cfg["profiles"][name] = {r["key"]: r["vol"] for r in self.rows if r["key"] != "__master__"}
        self.cfg["profile"] = name
        save_config(self.cfg)
        self.render()
        self.say(f"Saved \"{name}\"!", 1.6)

    def reset_profiles(self):
        self.cfg["profiles"] = {}
        save_config(self.cfg)
        self.say("Profiles have\nbeen reset", 1.6)

    # -- audio device
    def set_device(self, dev_id, name):
        try:
            set_output_device(dev_id)
        except Exception as e:
            log_error(f"Switch audio device: {e}")
            messagebox.showerror(APP_NAME, f"Could not switch audio device:\n{e}", parent=self)
            return
        self.device_name = name
        m = find_master()
        if m is not None:
            self.master_ctl = m
            for r in self.rows:
                if r["key"] == "__master__":
                    r["ctl"] = m
        self.meter = find_meter() or self.meter
        self.order = None
        self.refresh_now()
        self.render()
        self.say("Now playing on\n" + short_device(name, 20), 2.0)

    # -- compact mode
    def toggle_compact(self):
        self.cfg["compact"] = not self.cfg["compact"]
        save_config(self.cfg)
        self.apply_layout()

    def apply_layout(self):
        self.L = LAYOUTS["compact" if self.cfg["compact"] else "normal"]
        self.W = self.p(self.L["width"])
        self.canvas.config(width=self.W)
        self.H = 0
        self.tiles.clear()
        self.bg_cache.clear()
        self.hover = None
        self.sprite_x = self.W - self.p(PAD) - self.sprite_w + self.p(6)
        self.sprite_y = None
        self.resize()
        self.render()

    # -- tray icon
    def start_tray(self):
        if self.tray is None and not SAFE_MODE:
            self.tray = Tray(self.events, make_app_icon(64))

    def toggle_tray(self):
        self.cfg["tray"] = not self.cfg["tray"]
        save_config(self.cfg)

    def on_unmap(self, e):
        if e.widget is not self:
            return
        if self.cfg["tray"] and self.tray and self.tray.icon and self.state() == "iconic":
            self.after(10, self.withdraw)
            if not self.cfg.get("tray_told"):
                self.cfg["tray_told"] = True
                save_config(self.cfg)
                self.tray.notify("I'm still down here by the clock. Click the icon to bring me back.")

    def show_window(self):
        self.deiconify()
        self.state("normal")
        self.lift()
        self.attributes("-topmost", True)
        self.attributes("-topmost", self.cfg["topmost"])
        try:
            self.focus_force()
        except Exception:
            pass

    # -- hotkeys
    def toggle_hotkeys(self):
        self.cfg["hotkeys"] = not self.cfg["hotkeys"]
        save_config(self.cfg)
        if self.hotkeys:
            self.hotkeys.stop()
            self.hotkeys = None
        if self.cfg["hotkeys"]:
            self.hotkeys = Hotkeys(self.events)

    def show_hotkeys(self):
        lines = [f"{keys}:   {desc}" for _, _, _, _, keys, desc in HOTKEYS]
        failed = self.hotkeys.failed if self.hotkeys else []
        text = "These also work while you are inside a game:\n\n" + "\n".join(lines)
        if failed:
            text += "\n\nTaken by another program (not working):\n" + "\n".join(failed)
        if not self.cfg["hotkeys"]:
            text += "\n\n(Hotkeys are switched off right now – turn them on in the menu.)"
        messagebox.showinfo(f"{APP_NAME} \u2013 hotkeys", text, parent=self)

    def music_row(self):
        best = None
        for i, r in enumerate(self.rows):
            if category(r["key"]) == "music":
                if r["key"] == "spotify.exe":
                    return i
                if best is None:
                    best = i
        return best

    def handle_events(self):
        for _ in range(20):
            try:
                ev = self.events.get_nowait()
            except queue.Empty:
                return
            kind = ev[0]
            if kind == "hotkey":
                action = next((h[3] for h in HOTKEYS if h[0] == ev[1]), None)
                if action:
                    self.do_action(action)
            elif kind == "show":
                self.show_window()
            elif kind == "quit":
                self.on_close()
                return
            else:
                self.do_action(ev)

    def do_action(self, action):
        kind = action[0]
        if kind in ("music", "focus"):
            if kind == "music":
                i = self.music_row()
            else:
                name = foreground_app()
                i = next((j for j, r in enumerate(self.rows) if r["key"] == name), None)
                if i is None:
                    if name:
                        self.say("No sound\nfrom " + pretty_name(name), 1.6)
                    return
            if i is None:
                self.say("No music\nis playing", 1.4)
                return
            r = self.rows[i]
            self.set_vol(i, r["vol"] + action[1])
            self.say(f"{pretty_name(r['key'])}: {r['vol']} %", 1.2)
        elif kind == "mute_music":
            i = self.music_row()
            if i is not None:
                self.toggle_mute(i)
                r = self.rows[i]
                self.say(f"{pretty_name(r['key'])}: " + ("muted" if r["muted"] else "on"), 1.2)
        elif kind == "media":
            self.media_action(action[1])
        elif kind == "profile":
            self.apply_profile(action[1])

    def media_action(self, name):
        media_key(name)
        np_ = self.now_playing
        if name == "play" and getattr(np_, "display", None):
            np_.paused = not np_.paused   # corrected automatically if Spotify says otherwise
            self.media_sig = None
        elif name in ("next", "prev"):
            self.react = ("surprise", time.time() + 0.4)

    # -- lower the music when someone talks (ducking)
    def duck_tick(self):
        duck = self.cfg["duck"]
        now = time.time()
        talking = False
        if duck["on"]:
            for m in self.voice_meters:
                try:
                    if m.GetPeakValue() > 0.03:
                        talking = True
                        break
                except Exception:
                    pass
        if talking:
            self.duck_last = now
        target = duck["level"] / 100.0 if duck["on"] and now - self.duck_last < 1.2 else 1.0
        cur = self.duck_amt
        cur += (target - cur) * (0.55 if target < cur else 0.1)
        if abs(cur - target) < 0.01:
            cur = target
        if cur != self.duck_amt:
            was = self.duck_amt < 0.98
            self.duck_amt = cur
            for r in self.rows:
                if category(r["key"]) == "music":
                    r["ctl"].set(r["vol"] / 100.0 * cur)
            if was != (cur < 0.98) or abs(cur - target) < 0.02:
                self.render()
        self.after(80, self.duck_tick)

    def toggle_duck(self):
        self.cfg["duck"]["on"] = not self.cfg["duck"]["on"]
        save_config(self.cfg)
        if self.cfg["duck"]["on"]:
            self.say("I'll lower the music\nwhen someone talks", 2.0)

    def set_duck_level(self, pct):
        self.cfg["duck"]["level"] = pct
        save_config(self.cfg)

    # -- the buddy
    def master_muted(self):
        return any(r["key"] == "__master__" and r["muted"] for r in self.rows)

    def say(self, text, secs=2.4):
        self.speech = (text, time.time() + secs)
        self.update_bubble()

    def pick_line(self, lines, kind):
        choices = [x for x in lines if x != self.last_lines.get(kind)] or lines
        line = random.choice(choices)
        self.last_lines[kind] = line
        return line

    def bubble_image(self, text):
        img = self.bubbles.get(text)
        if img is None:
            img = self.bubbles[text] = ImageTk.PhotoImage(
                make_bubble(text, max(2, self.sc - 1), font("semi", self.p(11))))
        return img

    def update_bubble(self):
        now = time.time()
        text = None
        if self.speech and self.speech[1] > now:
            text = self.speech[0]
        else:
            self.speech = None
            if self.state_name == "idle" and now - self.last_sound > 3.0:
                text = MUTE_TEXT if self.master_muted() else BUBBLE_TEXT
        if text != self.bubble_text:
            self.bubble_text = text
            if text:
                self.canvas.itemconfig(self.bubble_item, image=self.bubble_image(text), state="normal")
            else:
                self.canvas.itemconfig(self.bubble_item, state="hidden")

    def girl_box(self):
        y = self.p(SPRITE_Y)
        return self.sprite_x, y, self.sprite_x + self.sprite_w, y + self.sprite_h

    def beat_clock(self):
        """(seconds per beat, time of a beat) when the tempo of the music is known, else None.
        Very fast songs are danced in half time and very slow ones in double time."""
        an = self.analyzer
        if not (an.bpm and an.tempo_conf > 0.35 and an.beat_len > 0 and time.time() - an.updated < 0.5):
            return None
        L = an.beat_len
        if 60.0 / L > 150:
            L *= 2
        elif 60.0 / L < 75:
            L /= 2
        return L, an.beat_at

    def grid(self, now, at, unit):
        """Slot number on the beat grid (counted from a fixed start, so it only ever goes up)
        and the time the next slot starts."""
        off = (at - self.started_t) % unit
        k = math.floor((now - self.started_t - off) / unit + 0.02)
        return k, self.started_t + off + (k + 1) * unit

    def dance(self):
        now = time.time()
        silence = now - self.last_sound
        if silence < 2.0:
            state = "dance"
        elif silence > SLEEP_AFTER and now - self.woken_at > SLEEP_AFTER:
            state = "sleep"
        else:
            state = "idle"
        if state != self.state_name:
            if state == "dance" and self.state_name == "sleep":
                self.react = ("surprise", now + 0.7)
                self.say(self.pick_line(LINES_BACK, "back"), 2.2)
                self.burst("star", 6)
            self.state_name = state
            self.dance_i = self.idle_i = 0
        self.dancing = state == "dance"

        # how intense is the music? (bass counts most) -> calm / normal / hype
        b = self.band_vals
        e = 0.6 * b[0] + 0.4 * (sum(b) / 4)
        self.energy += (e - self.energy) * 0.25
        if self.mode != "hype" and self.energy > 0.66:
            self.mode = "hype"
        elif self.mode != "calm" and self.energy < 0.26:
            self.mode = "calm"
        elif self.mode == "hype" and self.energy < 0.56 or self.mode == "calm" and self.energy > 0.34:
            self.mode = "dance"

        react = self.react if self.react and self.react[1] > now else None
        self.react = react
        if react:
            frames = self.wave_sprites if react[0] == "wave" else self.surprise_sprites
            self.idle_i = (self.idle_i + 1) % len(frames)
            img, delay = frames[self.idle_i], 180
        elif state == "dance":
            pool = MOVE_POOLS[self.mode]
            clock = self.beat_clock()
            if clock:
                # Follow the tempo: every frame lands exactly on the beat grid
                L, at = clock
                fpb = MOVE_FPB.get(self.move, 2)
                k, nxt = self.grid(now, at, L / fpb)
                if k != self.last_k:
                    self.last_k = k
                    self.move_left -= 1
                # switch moves on the first beat of a bar (every 4 beats)
                if self.move not in pool or (self.move_left <= 0 and k % (fpb * 4) == 0):
                    choices = [m for m in pool if m != self.move] or pool
                    self.move = random.choice(choices)
                    fpb = MOVE_FPB.get(self.move, 2)
                    k, nxt = self.grid(now, at, L / fpb)
                    self.last_k = k
                    self.move_left = fpb * 4 * random.choice((2, 3, 4))   # 2-4 bars
                normal, blink = self.moves[self.move]
                self.dance_i = k % len(normal)
                img = (blink if random.random() < BLINK_CHANCE else normal)[self.dance_i]
                delay = max(15, int((nxt - now) * 1000) + 2)
            else:
                # tempo unknown: dance at a speed that follows the bass
                if self.move not in pool or self.move_left <= 0:   # time for a new move
                    choices = [m for m in pool if m != self.move] or pool
                    self.move = random.choice(choices)
                    self.dance_i = -1
                    self.move_left = len(DANCE_MOVES[self.move]) * random.choice((2, 3, 4))
                normal, blink = self.moves[self.move]
                self.move_left -= 1
                self.dance_i = (self.dance_i + 1) % len(normal)
                img = (blink if random.random() < BLINK_CHANCE else normal)[self.dance_i]
                speed = {"calm": 1.6, "dance": 1.15 - 0.4 * b[0], "hype": 0.8}[self.mode]
                delay = int(DANCE_MS * speed)
        elif state == "sleep":
            self.idle_i = (self.idle_i + 1) % len(self.sleep_sprites)
            img, delay = self.sleep_sprites[self.idle_i], SLEEP_MS
            if now - self.last_z_t > 1.5:
                self.last_z_t = now
                x0, y0, x1, _ = self.girl_box()
                self.spawn("z", (205, 220, 255), x0 + self.p(18), y0 + self.p(10) + SPRITE_TOP * self.sc,
                           vx=-self.p(14), vy=-self.p(13), life=2.8)
        else:
            self.idle_i = (self.idle_i + 1) % len(self.idle_sprites)
            img, delay = self.idle_sprites[self.idle_i], IDLE_MS
        self.canvas.itemconfig(self.sprite_item, image=img)
        self.update_bubble()
        self.after(delay, self.dance)

    # -- effects: notes, hearts, Zzz, stars
    def fx_images(self, pattern, color):
        key = (pattern, tuple(color))
        imgs = self.fx_imgs.get(key)
        if imgs is None:
            if len(self.fx_imgs) > 80:
                self.fx_imgs.clear()
            u = max(2, self.sc - 1) + (1 if pattern == "z" else 0)
            imgs = self.fx_imgs[key] = make_fx(pattern, color, u)
        return imgs

    def spawn(self, pattern, color, x, y, vx=0.0, vy=-30.0, life=1.4):
        if len(self.fx) > 40:
            return
        imgs = self.fx_images(pattern, color)
        item = self.canvas.create_image(x, y, anchor="center", image=imgs[0], tags="fx")
        self.fx.append({"item": item, "imgs": imgs, "x": x, "y": y, "vx": vx, "vy": vy,
                        "t": 0.0, "life": life, "i": 0, "ph": random.random() * 6.3})
        if len(self.fx) == 1:
            self.after(33, self.anim)

    def burst(self, pattern, n, colors=None):
        x0, y0, x1, y1 = self.girl_box()
        cx, cy = (x0 + x1) / 2, y0 + self.p(2)     # above the head, not in front of the face
        colors = colors or [PALETTES[self.palette_i][i % 3] for i in range(n)]
        for i in range(n):
            ang = math.pi * (0.15 + 0.7 * i / max(1, n - 1)) + random.uniform(-0.15, 0.15)
            sp = self.p(random.uniform(45, 70))
            self.spawn(pattern, colors[i % len(colors)], cx, cy,
                       vx=-math.cos(ang) * sp, vy=-math.sin(ang) * sp, life=random.uniform(0.9, 1.3))

    def on_beat(self):
        if not self.dancing or self.beat_clock():
            return   # with a known tempo the notes follow the beat grid instead
        self.spawn_note()

    def spawn_note(self):
        now = time.time()
        gap = 0.22 if self.mode == "hype" else 0.4
        if now - self.last_note_t < gap or random.random() > (0.9 if self.mode == "hype" else 0.55):
            return
        self.last_note_t = now
        x0, y0, x1, _ = self.girl_box()
        left = random.random() < 0.6
        x = x0 + self.p(8) if left else x1 - self.p(8)
        col = random.choice(PALETTES[self.palette_i][:3])
        self.spawn("note", col, x, y0 + self.p(22), vx=self.p(random.uniform(-26, -8) if left else
                                                           random.uniform(-6, 10)),
                   vy=-self.p(random.uniform(26, 40)), life=random.uniform(1.2, 1.7))

    def on_song_change(self):
        if self.dancing and time.time() - self.started_t > 5:
            self.say(self.pick_line(LINES_SONG, "song"), 2.2)
            self.burst("star", 7)

    def anim(self):
        """Moves the effects and makes the buddy hop in time. Only runs while something is moving."""
        dt = 0.033
        alive = []
        for f in self.fx:
            f["t"] += dt
            if f["t"] >= f["life"] or f["y"] < -self.p(12):
                self.canvas.delete(f["item"])
                continue
            f["x"] += (f["vx"] + math.sin(f["t"] * 5 + f["ph"]) * self.p(10)) * dt
            f["y"] += f["vy"] * dt
            f["vx"] *= 0.97
            i = min(3, int((f["t"] / f["life"]) ** 1.6 * 4))
            if i != f["i"]:
                f["i"] = i
                self.canvas.itemconfig(f["item"], image=f["imgs"][i])
            self.canvas.coords(f["item"], f["x"], f["y"])
            alive.append(f)
        self.fx = alive
        if self.fx:
            self.after(33, self.anim)

    def bounce(self):
        """She bounces on the bass hits (more in hype mode) and jumps when you click her."""
        self.handle_events()
        if getattr(self, "_closing", False):
            return
        y = self.p(SPRITE_Y)
        clock = self.beat_clock() if self.dancing else None
        if clock:
            # bob down on every beat and up in between, in time with the music
            L, at = clock
            now = time.time()
            ph = ((now - at) / L) % 1.0
            amp = {"calm": 1.5, "dance": 3.5, "hype": 6.0}[self.mode]
            y -= self.p(amp) * math.sin(math.pi * ph)
            beat_no, _ = self.grid(now, at, L)
            if beat_no != self.grid_beat:
                self.grid_beat = beat_no
                self.spawn_note()
        elif self.dancing:
            amp = {"calm": 1.0, "dance": 3.0, "hype": 6.0}[self.mode]
            y -= self.p(amp) * self.beat
        if self.hop_t is not None:
            t = time.time() - self.hop_t
            if t < 0.42:
                y -= self.p(9) * math.sin(math.pi * t / 0.42)
            else:
                self.hop_t = None
        y = round(y)
        if y != self.sprite_y:
            self.sprite_y = y
            self.canvas.coords(self.sprite_item, self.sprite_x, y)
        bob = self.p(2) if (int(time.time() * 2.5) % 2) and self.bubble_text else 0
        self.canvas.coords(self.bubble_item, self.sprite_x - self.p(2), self.bubble_y - bob)
        self.after(33, self.bounce)

    def poke_girl(self):
        now = time.time()
        self.hop_t = now
        if self.state_name == "sleep":
            self.woken_at = now
            self.state_name = "idle"
            self.react = ("surprise", now + 1.1)
            self.say(self.pick_line(LINES_WAKE, "wake"), 2.6)
            self.burst("star", 5)
            return
        self.react = ("surprise", now + 0.5)
        if self.dancing:
            self.say(self.pick_line(LINES_CLICK_PLAYING, "click"), 2.0)
        else:
            self.woken_at = now
            self.say(self.pick_line(LINES_CLICK_IDLE, "click"), 2.0)
        self.burst("heart", 6, [(255, 110, 170), (255, 79, 122), (255, 170, 205)])

    def hover_girl(self):
        now = time.time()
        if self.state_name != "sleep" and now - self.hover_girl_t > 4 and not self.react:
            self.hover_girl_t = now
            self.react = ("wave", now + 1.6)

    # -- mouse
    def on_motion(self, e):
        h = self.hit(e.x, e.y)
        if h != self.hover:
            if h == ("girl",):
                self.hover_girl()
            self.hover = h
            self.canvas.config(cursor="hand2" if h else "")
            self.render()

    def on_leave(self, _e):
        if self.drag is None:
            self.hover = None
            self.render()

    def on_press(self, e):
        h = self.hit(e.x, e.y)
        if not h:
            return
        kind = h[0]
        if kind == "girl":
            self.poke_girl()
        elif kind == "menubtn":
            self.open_main_menu()
        elif kind == "profbtn":
            self.open_profile_menu()
        elif kind == "media":
            self.media_action(h[1])
        elif kind == "outfitbtn":
            self.open_outfit_menu()
        elif kind == "devbtn":
            self.open_device_menu()
        elif kind == "mute":
            self.toggle_mute(h[1])
        elif kind == "row":
            self.drag = h[1]
            self.set_from_x(h[1], e.x)

    def on_drag(self, e):
        if self.drag is not None:
            self.set_from_x(self.drag, e.x)

    def on_release(self, e):
        if self.drag is not None:
            self.drag = None
            self.hover = self.hit(e.x, e.y)
            self.render()

    def on_double(self, e):
        self.on_press(e)  # quick clicks should count as normal clicks

    def on_wheel(self, e):
        h = self.hit(e.x, e.y)
        if not h:
            return
        up = e.delta > 0
        if h[0] in ("row", "mute"):
            self.set_vol(h[1], self.rows[h[1]]["vol"] + (3 if up else -3))

    def on_right(self, e):
        h = self.hit(e.x, e.y)
        key = self.rows[h[1]]["key"] if h and h[0] in ("row", "mute") else None
        self.show_menu(e, key)

    # -- volume
    def set_from_x(self, i, x):
        tx0, tx1, _ = self.track(i)
        self.set_vol(i, round((x - tx0) / (tx1 - tx0) * 100))

    def set_vol(self, i, v):
        r = self.rows[i]
        v = max(0, min(100, int(v)))
        r["last"] = time.time()
        if v != r["vol"]:
            r["vol"] = v
            factor = self.duck_amt if category(r["key"]) == "music" else 1.0
            r["ctl"].set(v / 100.0 * factor)
            self.render()
            if r["key"] == "__master__" and v >= 95 and time.time() - self.loud_t > 8 and self.dancing:
                self.loud_t = time.time()
                self.react = ("surprise", time.time() + 0.8)
                self.say(LOUD_TEXT, 2.0)

    def toggle_mute(self, i):
        r = self.rows[i]
        r["muted"] = not r["muted"]
        r["ctl"].set_mute(r["muted"])
        r["last"] = time.time()
        self.render()
        if r["key"] == "__master__" and r["muted"]:
            self.react = ("surprise", time.time() + 0.8)
            self.say(MUTE_TEXT, 2.5)

    def sync_row(self, r, force=False):
        dragging = self.drag is not None and self.drag < len(self.rows) and self.rows[self.drag] is r
        if not force and (dragging or time.time() - r["last"] < 0.8):
            return
        if self.duck_amt < 0.999 and category(r["key"]) == "music":
            return   # the music was lowered by us – don't read back the lowered level
        v = r["ctl"].get()
        if v is not None:
            r["vol"] = round(v * 100)
        m = r["ctl"].get_mute()
        if m is not None:
            r["muted"] = m

    # -- updates
    def refresh(self):
        self.ticks += 1
        if self.ticks % 4 == 0:  # every 6 seconds: follow along if the audio device changes
            m = find_master()
            if m is not None:
                self.master_ctl = m
                for r in self.rows:
                    if r["key"] == "__master__":
                        r["ctl"] = m
            self.meter = find_meter() or self.meter
            name = default_device_name()
            if name and name != self.device_name:
                self.device_name = name
                self.render()
        self.refresh_now()
        self.after(REFRESH_MS, self.refresh)

    def refresh_now(self):
        try:
            groups = collect_sessions()
        except Exception:
            groups = None
        if groups is not None:
            self.apply(groups)

    def apply(self, groups):
        hidden = set(self.cfg["hidden"])

        def sort_key(k):
            if k in PRIORITY:
                return (0, PRIORITY.index(k), "")
            if k == "__system__":
                return (2, 0, "")
            return (1, 0, pretty_name(k).lower())

        keys = sorted((k for k in groups if k not in hidden), key=sort_key)
        if self.master_ctl and "__master__" not in hidden:
            keys.insert(0, "__master__")

        self.voice_meters = [m for k, g in groups.items() if k in VOICE_APPS for m in g.get("meters", [])]
        existing = {r["key"]: r for r in self.rows}
        rows = []
        for k in keys:
            r = existing.get(k)
            if k != "__master__" and k not in self.icons:
                self.icons[k] = exe_icon(proc_exe(groups[k]["proc"]))
            if r is None:
                ctl = self.master_ctl if k == "__master__" else SessionControl(groups[k]["vols"])
                r = {"key": k, "ctl": ctl, "vol": 0, "muted": False, "last": 0.0}
                self.sync_row(r, force=True)
            elif k != "__master__":
                r["ctl"].volumes = groups[k]["vols"]
            rows.append(r)
        self.rows = rows

        changed = keys != self.order
        if changed:
            self.order = keys
            self.drag = None
            if self.hover and self.hover[0] in ("row", "mute"):
                self.hover = None
            self.resize()

        for r in self.rows:
            self.sync_row(r)
        sig = tuple((r["key"], r["vol"], r["muted"]) for r in self.rows)
        if changed or sig != self.last_sig:
            self.last_sig = sig
            self.render()

    # -- right-click menu
    def show_menu(self, event, key):
        self.menu.delete(0, "end")
        if key:
            self.menu.add_command(label=f"Hide {pretty_name(key)}",
                                  command=lambda: self.hide(key))
        n = len(self.cfg["hidden"])
        if n:
            self.menu.add_command(label=f"Show hidden programs ({n})", command=self.unhide_all)
        if self.menu.index("end") is not None:
            self.menu.add_separator()
        for name in PROFILE_NAMES:
            self.menu.add_command(label=f"{name} profile", command=lambda name=name: self.apply_profile(name))
        if sys.platform == "win32":
            if self.menu.index("end") is not None:
                self.menu.add_separator()
            self.menu.add_command(label="Create desktop shortcut", command=self.make_shortcut)
        if self.menu.index("end") is not None:
            self.menu.tk_popup(event.x_root, event.y_root)

    def make_shortcut(self):
        link, errors = create_shortcuts(self.icon_file)
        if link:
            self.cfg["shortcut_link"] = link
            self.cfg["shortcut_for"] = SCRIPT
            save_config(self.cfg)
            messagebox.showinfo(APP_NAME, "The shortcut is now on your desktop and in the Start menu.", parent=self)
        else:
            self.shortcut_failed(errors)

    def hide(self, key):
        if key not in self.cfg["hidden"]:
            self.cfg["hidden"].append(key)
            save_config(self.cfg)
        self.order = None
        self.refresh_now()

    def unhide_all(self):
        self.cfg["hidden"] = []
        save_config(self.cfg)
        self.order = None
        self.refresh_now()

    # -- always on top
    def toggle_topmost(self):
        self.cfg["topmost"] = not self.cfg["topmost"]
        save_config(self.cfg)
        self.attributes("-topmost", self.cfg["topmost"])
        self.render()

    def report_callback_exception(self, kind, value, tb):
        text = "".join(traceback.format_exception(kind, value, tb))
        log_error(text)
        if not getattr(self, "_error_shown", False):
            self._error_shown = True
            messagebox.showerror(APP_NAME, "Something went wrong (the program keeps running):\n\n" + text[-1200:]
                                 + f"\n\nSaved to:\n{CRASH_LOG}", parent=self)

    def heartbeat(self):
        run_mark(_STARTED)
        self.after(5000, self.heartbeat)

    def on_close(self):
        if getattr(self, "_closing", False):
            return
        self._closing = True
        try:
            if self.state() == "normal":
                self.cfg["position"] = [self.winfo_x(), self.winfo_y()]
        except Exception:
            pass
        save_config(self.cfg)
        clear_run_mark()
        if self.duck_amt < 1.0:
            for r in self.rows:
                if category(r["key"]) == "music":
                    r["ctl"].set(r["vol"] / 100.0)
        if self.hotkeys:
            self.hotkeys.stop()
        if self.tray:
            self.tray.stop()
        self.destroy()


if __name__ == "__main__":
    try:
        app = App()
        run_mark(_STARTED)
        app.after(2000, app.heartbeat)
        if SAFE_MODE:
            app.after(1500, lambda: messagebox.showwarning(
                APP_NAME, "The program closed unexpectedly last time.\n\n"
                          "This time it runs without capturing audio for the waves and without song info.\n"
                          f"The error from last time is in:\n{PREV_CRASH_LOG}", parent=app))
        app.mainloop()
        os._exit(0)   # makes sure the tray icon's thread doesn't keep the program alive
    except SystemExit:
        raise
    except Exception:
        report_crash(traceback.format_exc())
