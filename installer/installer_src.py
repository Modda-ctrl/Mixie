# Mixie installer – made by Modda-ctrl (https://github.com/Modda-ctrl/Mixie)
# Run by "Install Mixie.bat". Unpacks the version of Mixie that is embedded in the .bat file,
# installs it (or updates an existing install) and starts it.
import base64
import ctypes
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import time

APP = "Mixie"
NAME = "mixie.py"
FOLDER_DESKTOP = "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}"
FOLDER_PROGRAMS = "{A77F5D77-2E2B-44C3-A6A2-ABA601054A51}"


def say(msg=""):
    print(msg, flush=True)


def known_folder(guid):
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


def script_from_shortcut(lnk):
    """Returns the .py file a shortcut points to."""
    if not os.path.exists(lnk):
        return None
    try:
        import comtypes.client
        ws = comtypes.client.CreateObject("WScript.Shell", dynamic=True)
        args = ws.CreateShortcut(lnk).Arguments
        m = re.search(r'"?([^"]*' + re.escape(NAME) + r')"?', args, re.I)
        if m:
            return m.group(1)
    except Exception:
        pass
    try:  # fallback: look for the path directly in the shortcut file
        raw = open(lnk, "rb").read()
        for enc in ("utf-16-le", "latin-1"):
            m = re.search(r'([A-Za-z]:\\[^"\x00]*?' + re.escape(NAME) + ')', raw.decode(enc, "ignore"), re.I)
            if m:
                return m.group(1)
    except Exception:
        pass
    return None


def find_install_dir():
    for folder in (known_folder(FOLDER_DESKTOP), known_folder(FOLDER_PROGRAMS),
                   os.path.join(os.path.expanduser("~"), "Desktop")):
        if folder:
            target = script_from_shortcut(os.path.join(folder, APP + ".lnk"))
            if target and os.path.exists(target):
                return os.path.dirname(target), "found your existing install through its shortcut"
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP)
    if os.path.exists(os.path.join(path, NAME)):
        return path, "found your existing install"
    return path, "new install"


def window_python():
    folder, name = os.path.split(sys.executable)
    w = os.path.join(folder, "pythonw.exe")
    return w if os.path.exists(w) else sys.executable


def stop_running(names):
    """Closes Mixie if it is running, so the new version can start."""
    stopped = 0
    try:
        import psutil
    except Exception:
        return 0
    me = os.getpid()
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if proc.info["pid"] == me:
                continue
            cmd = " ".join(proc.info["cmdline"] or []).lower()
            if any(n.lower() in cmd for n in names) and "python" in (proc.info["name"] or "").lower():
                proc.terminate()
                try:
                    proc.wait(5)
                except Exception:
                    proc.kill()
                stopped += 1
        except Exception:
            continue
    return stopped


def ensure_packages():
    need = [pip for mod, pip in (("pycaw", "pycaw"), ("PIL", "pillow"))
            if importlib.util.find_spec(mod) is None]
    if need:
        say("  Installing " + ", ".join(need) + " ...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--user", "--quiet", "--only-binary=:all:",
                        *need])


def main():
    bat = sys.argv[1]
    data = open(bat, "rb").read()
    start, end = b"::" + b"PAYLOAD::", b"::" + b"PAYLOADEND::"
    payload = base64.b64decode(b"".join(data.split(start, 1)[1].split(end, 1)[0].split()))
    version = re.search(rb'APP_VERSION = "([^"]+)"', payload)
    version = version.group(1).decode() if version else "?"

    say(f"=== {APP} {version} - install / update ===")
    say("    made by Modda-ctrl - https://github.com/Modda-ctrl/Mixie")
    say()
    target_dir, why = find_install_dir()
    say(f"Folder: {target_dir}")
    say(f"  ({why})")
    os.makedirs(target_dir, exist_ok=True)
    target = os.path.join(target_dir, NAME)

    if stop_running([NAME]):
        say("  Closed the running copy of Mixie.")
        time.sleep(0.5)

    if os.path.exists(target):
        shutil.copy2(target, target + ".bak")
        say(f"  Backup: {NAME}.bak")
    with open(target, "wb") as f:
        f.write(payload)
    say(f"  Installed: {NAME}")
    for stale in (".running", ".extras_installed"):  # reset safe mode and package attempts
        try:
            os.remove(os.path.join(target_dir, stale))
        except Exception:
            pass

    ensure_packages()

    say("  Starting Mixie ...")
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    start_log = os.path.join(target_dir, "start_log.txt")
    log = open(start_log, "w", encoding="utf-8")
    proc = subprocess.Popen([window_python(), target], cwd=target_dir, creationflags=flags,
                            stdout=log, stderr=subprocess.STDOUT, close_fds=True)
    say("  (on the first start a few packages are downloaded - a small window shows the progress)")
    for _ in range(16):  # wait 8 seconds and make sure it doesn't close right away
        time.sleep(0.5)
        if proc.poll() is not None:
            break
    log.flush()
    say()
    if proc.poll() is None:
        say("Done! Mixie is running. You can close this window.")
        return
    say(f"Mixie closed right away (code {proc.returncode}). The error:")
    say("-" * 60)
    for path in (start_log, os.path.join(target_dir, "crash_log.txt")):
        try:
            text = open(path, encoding="utf-8", errors="replace").read().strip()
            if text:
                say(text[-2500:])
                say("-" * 60)
        except Exception:
            pass
    say("Please open an issue on GitHub with a screenshot of this window.")


try:
    main()
except Exception as e:
    say()
    say(f"Something went wrong: {e}")
    sys.exit(1)
