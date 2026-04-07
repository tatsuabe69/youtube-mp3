"""
アプリ版エントリーポイント（pywebview でネイティブウィンドウ表示）
"""
import sys
import threading
import socket
import time


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def start_flask(port: int):
    from app import app
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    import webview

    port = get_free_port()

    t = threading.Thread(target=start_flask, args=(port,), daemon=True)
    t.start()

    # Flask が起動するまで少し待つ
    time.sleep(1.2)

    webview.create_window(
        'YT2MP3',
        f'http://127.0.0.1:{port}',
        width=680,
        height=560,
        resizable=True,
        min_size=(500, 420),
    )
    webview.start()
