@echo off
cd /d "%~dp0"

echo [1/3] 仮想環境を準備しています...
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat

echo [2/3] パッケージをインストールしています...
pip install flask yt-dlp imageio-ffmpeg pywebview pyinstaller --quiet

echo [3/3] ビルドしています...
pyinstaller --onedir --windowed --name YT2MP3 ^
  --collect-all yt_dlp ^
  --collect-all imageio_ffmpeg ^
  --collect-all webview ^
  --hidden-import flask ^
  --hidden-import engineio.async_drivers.threading ^
  main.py

echo.
echo ===================================
echo  完了！dist\YT2MP3\YT2MP3.exe
echo ===================================
pause
