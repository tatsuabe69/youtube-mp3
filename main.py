"""
アプリ版エントリーポイント（pywebview でネイティブウィンドウ表示）
"""
import sys
import re
import shutil
import threading
import socket
import time
import tempfile
from pathlib import Path


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def start_flask(port: int):
    from app import app
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)


class DownloadApi:
    """pywebview JS API: ダウンロードボタンから呼ばれる"""

    def save_file(self, token: str):
        """変換済み MP3 をユーザーの Downloads フォルダにコピーする"""
        if not re.match(r'^[a-f0-9]{8}$', token):
            return {'error': 'Invalid token'}

        tmp_dir = Path(tempfile.gettempdir()) / 'yt-mp3'
        src = tmp_dir / f'{token}.mp3'
        if not src.exists():
            return {'error': 'ファイルが見つかりません（期限切れかもしれません）'}

        # タイトルを titles dict から取得（app モジュール経由）
        try:
            from app import TITLES
            raw = TITLES.get(token, 'audio')
        except Exception:
            raw = 'audio'

        safe_name = re.sub(r'[\\/:*?"<>|]', '_', raw).strip()[:200] or 'audio'
        downloads = Path.home() / 'Downloads'
        downloads.mkdir(exist_ok=True)

        dst = downloads / f'{safe_name}.mp3'
        # 同名ファイルが存在する場合は連番
        counter = 1
        while dst.exists():
            dst = downloads / f'{safe_name} ({counter}).mp3'
            counter += 1

        shutil.copy2(src, dst)

        # ファイルマネージャーでファイルを選択状態で開く
        import subprocess, platform
        if platform.system() == 'Windows':
            subprocess.Popen(['explorer', '/select,', str(dst)])
        elif platform.system() == 'Darwin':
            subprocess.Popen(['open', '-R', str(dst)])
        else:
            subprocess.Popen(['xdg-open', str(downloads)])

        return {'ok': True, 'path': str(dst)}


if __name__ == '__main__':
    import webview

    port = get_free_port()

    t = threading.Thread(target=start_flask, args=(port,), daemon=True)
    t.start()

    time.sleep(1.2)

    api = DownloadApi()
    webview.create_window(
        'YT2MP3',
        f'http://127.0.0.1:{port}',
        width=680,
        height=560,
        resizable=True,
        min_size=(500, 420),
        js_api=api,
    )
    import platform
    if platform.system() == 'Windows':
        webview.start(gui='edgechromium')
    else:
        webview.start()  # Mac: cocoa (デフォルト)
