@echo off
echo Installing PyInstaller...
pip install pyinstaller

echo.
echo Building Cinema Tycoon Executable...
pyinstaller --onefile --name "Cinema Tycoon Demo" --add-data "cinema_tycoon\data\*;cinema_tycoon\data" --add-data "balance.json;." main.py

echo.
echo Build Complete!
echo You can find your executable in the "dist" folder!
pause
