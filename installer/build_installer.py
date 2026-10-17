# Builds "Install Mixie.bat": a single file that contains the installer and mixie.py.
#   python installer/build_installer.py
import base64
import os
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def block(name, data):
    b64 = base64.b64encode(data).decode()
    return f"::{name}::\n" + "\n".join(textwrap.wrap(b64, 100)) + f"\n::{name}END::\n"


def runner(name):
    return ('%PY% -X utf8 -c "import sys,base64;d=open(sys.argv[1],\'rb\').read();'
            f"a,b=b'::'+b'{name}::',b'::'+b'{name}END::';"
            "exec(compile(base64.b64decode(b''.join(d.split(a,1)[1].split(b,1)[0].split())),"
            f"'{name.lower()}','exec'))\" \"%~f0\"\n")


def build(out_path, pre_steps=None):
    installer = open(os.path.join(ROOT, "installer", "installer_src.py"), "rb").read()
    app = open(os.path.join(ROOT, "mixie.py"), "rb").read()
    head = r'''@echo off
chcp 65001 >nul
title Mixie - install / update
rem Mixie - made by Modda-ctrl - https://github.com/Modda-ctrl/Mixie
cd /d "%~dp0"

rem --- Find Python
set PY=
where py >nul 2>nul && set PY=py
if not defined PY (
    where python >nul 2>nul && set PY=python
)
if not defined PY (
    echo Python was not found.
    echo Install Python from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" during the installation.
    pause
    exit /b 1
)

rem --- Run the installer (the code is embedded further down in this file)
'''
    body = head
    if pre_steps:
        body += runner("PRESTEPS")
    body += runner("INSTALLER") + "echo.\npause\nexit /b\n\n"
    if pre_steps:
        body += block("PRESTEPS", pre_steps)
    body += block("INSTALLER", installer) + block("PAYLOAD", app)
    with open(out_path, "w", encoding="ascii", newline="\r\n") as f:
        f.write(body)
    return out_path


if __name__ == "__main__":
    out = build(os.path.join(ROOT, "Install Mixie.bat"))
    print("built:", out)
