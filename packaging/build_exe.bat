@echo off
rem Builds dist\Mixie.exe on Windows (needs Python 3.10+). The GitHub workflow does the same.
cd /d "%~dp0\.."
py -m pip install -r requirements.txt pyinstaller || goto :error
py packaging\make_icon.py || goto :error
py -m PyInstaller --noconfirm --clean packaging\mixie.spec || goto :error
echo.
echo Done: dist\Mixie.exe
goto :eof
:error
echo Build failed.
exit /b 1
