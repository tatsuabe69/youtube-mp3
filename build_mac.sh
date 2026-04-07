#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "[1/3] 仮想環境を準備しています..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

echo "[2/3] パッケージをインストールしています..."
pip install flask yt-dlp imageio-ffmpeg pywebview pyinstaller --quiet

echo "[3/3] ビルドしています..."
pyinstaller --onedir --windowed --name YT2MP3 \
  --collect-all yt_dlp \
  --collect-all imageio_ffmpeg \
  --collect-all webview \
  --hidden-import flask \
  --osx-bundle-identifier com.yt2mp3.app \
  main.py

echo ""
echo "==================================="
echo " 完了！dist/YT2MP3.app"
echo "==================================="
