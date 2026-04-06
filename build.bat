@echo off
echo === CS2 Translator Build ===
echo.
echo Installing dependencies...
pip install -r requirements.txt
echo.
echo Building .exe...
pyinstaller --onefile --windowed --name "CS2 Translator" --icon=NONE translator.py
echo.
echo Done! .exe is in the dist\ folder
pause
