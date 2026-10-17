# PyInstaller recipe for Mixie.exe - one file, no console window, Mixie's own icon.
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

root = os.path.abspath(os.path.join(SPECPATH, ".."))
datas, binaries, hidden = [], [], []
for pkg in ("soundcard", "pycaw", "pystray"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hidden += h
hidden += collect_submodules("comtypes") + ["psutil", "numpy", "PIL.ImageTk"]

a = Analysis([os.path.join(root, "mixie.py")], pathex=[root], binaries=binaries, datas=datas,
             hiddenimports=hidden, excludes=["matplotlib", "scipy", "pandas", "IPython"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="Mixie", console=False, upx=False,
          icon=os.path.join(root, "packaging", "mixie.ico"), version=None)
