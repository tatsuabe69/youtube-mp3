import os
import re
import uuid
import tempfile
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template_string
import yt_dlp

app = Flask(__name__)

TMP_DIR = Path(tempfile.gettempdir()) / "yt-mp3"
TMP_DIR.mkdir(exist_ok=True)

TITLES: dict[str, str] = {}  # token → title（ローカル用インメモリ）


def get_ffmpeg_dir() -> str | None:
    import sys, platform
    if getattr(sys, 'frozen', False):
        # --add-binary でバンドルした ffmpeg は _MEIPASS 直下に置かれる
        base = Path(sys._MEIPASS)
        ffmpeg = base / ('ffmpeg.exe' if platform.system() == 'Windows' else 'ffmpeg')
        if ffmpeg.exists():
            return str(base)
        return None
    try:
        import static_ffmpeg.run as sf
        ffmpeg, _ = sf.get_or_fetch_platform_executables_else_raise()
        return str(Path(ffmpeg).parent)
    except Exception:
        return None


HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>YouTube → MP3</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --gold: #c9a84c;
    --gold-light: #e8c97a;
    --gold-dark: #a07830;
    --gold-subtle: #f5ead6;
    --text: #1a1a1a;
    --text-sub: #6b6b6b;
    --border: #e8e0d0;
    --bg: #fafaf8;
    --white: #ffffff;
    --error-bg: #fff5f5;
    --error-border: #f5c6c6;
    --error-text: #c0392b;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }
  .top-bar {
    width: 100%;
    max-width: 580px;
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 28px;
  }
  .logo-mark {
    width: 36px;
    height: 36px;
    background: linear-gradient(135deg, var(--gold), var(--gold-light));
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
    box-shadow: 0 2px 8px rgba(201,168,76,0.35);
  }
  .logo-text {
    font-size: 1rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    color: var(--text);
  }
  .logo-text span { color: var(--gold); }
  .card {
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 40px 44px;
    width: 100%;
    max-width: 580px;
    box-shadow:
      0 1px 3px rgba(0,0,0,0.04),
      0 8px 32px rgba(0,0,0,0.06),
      0 0 0 1px rgba(201,168,76,0.08);
  }
  .card-header { margin-bottom: 32px; }
  h1 {
    font-size: 1.5rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--text);
    margin-bottom: 6px;
  }
  h1 .accent { color: var(--gold); }
  .subtitle {
    color: var(--text-sub);
    font-size: 0.88rem;
    font-weight: 400;
  }
  .divider {
    height: 1px;
    background: linear-gradient(90deg, var(--gold-subtle), transparent);
    margin-bottom: 28px;
  }
  .input-label {
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--gold-dark);
    margin-bottom: 8px;
  }
  .input-row {
    display: flex;
    gap: 8px;
    margin-bottom: 20px;
  }
  input[type="text"] {
    flex: 1;
    background: var(--bg);
    border: 1.5px solid var(--border);
    border-radius: 11px;
    padding: 13px 16px;
    color: var(--text);
    font-family: inherit;
    font-size: 0.9rem;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  input[type="text"]::placeholder { color: #bbb; }
  input[type="text"]:focus {
    border-color: var(--gold);
    box-shadow: 0 0 0 3px rgba(201,168,76,0.15);
  }
  button.primary {
    background: linear-gradient(135deg, var(--gold), var(--gold-light));
    color: var(--white);
    border: none;
    border-radius: 11px;
    padding: 13px 24px;
    font-family: inherit;
    font-size: 0.9rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    cursor: pointer;
    transition: opacity 0.2s, transform 0.1s, box-shadow 0.2s;
    white-space: nowrap;
    box-shadow: 0 3px 12px rgba(201,168,76,0.4);
  }
  button.primary:hover { opacity: 0.88; box-shadow: 0 5px 18px rgba(201,168,76,0.5); }
  button.primary:active { transform: scale(0.97); }
  button.primary:disabled {
    background: #e0e0e0;
    color: #aaa;
    box-shadow: none;
    cursor: not-allowed;
    transform: none;
    opacity: 1;
  }
  .options { margin-bottom: 24px; }
  .option-group label {
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--gold-dark);
    display: block;
    margin-bottom: 8px;
  }
  .quality-pills { display: flex; gap: 8px; flex-wrap: wrap; }
  .quality-pills input[type="radio"] { display: none; }
  .quality-pills label.pill {
    display: inline-block;
    padding: 6px 16px;
    border: 1.5px solid var(--border);
    border-radius: 99px;
    font-size: 0.83rem;
    font-weight: 500;
    color: var(--text-sub);
    cursor: pointer;
    transition: all 0.15s;
    letter-spacing: 0;
    text-transform: none;
    margin-bottom: 0;
  }
  .quality-pills input[type="radio"]:checked + label.pill {
    background: linear-gradient(135deg, var(--gold), var(--gold-light));
    border-color: transparent;
    color: white;
    font-weight: 700;
    box-shadow: 0 2px 8px rgba(201,168,76,0.35);
  }
  .quality-pills label.pill:hover { border-color: var(--gold); color: var(--gold-dark); }

  /* Progress */
  .progress-area { display: none; margin-bottom: 20px; }
  .progress-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }
  .progress-label { font-size: 0.83rem; font-weight: 500; color: var(--text-sub); }
  .progress-pct { font-size: 0.8rem; font-weight: 700; color: var(--gold); }
  .progress-bar-bg {
    background: var(--gold-subtle);
    border-radius: 99px;
    height: 5px;
    overflow: hidden;
  }
  .progress-bar {
    background: linear-gradient(90deg, var(--gold-dark), var(--gold-light));
    height: 100%;
    width: 0%;
    border-radius: 99px;
    transition: width 0.6s cubic-bezier(0.4,0,0.2,1);
  }
  /* slow fill animation while waiting */
  .progress-bar.loading {
    animation: slowfill 55s cubic-bezier(0.1,0,0.3,1) forwards;
  }
  @keyframes slowfill { from { width: 4% } to { width: 88% } }

  /* Result */
  .result {
    display: none;
    background: var(--gold-subtle);
    border: 1.5px solid var(--border);
    border-radius: 14px;
    padding: 20px 22px;
    margin-top: 8px;
  }
  .result-inner {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 16px;
  }
  .result-icon {
    width: 40px; height: 40px;
    background: linear-gradient(135deg, var(--gold), var(--gold-light));
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem; flex-shrink: 0;
    box-shadow: 0 2px 8px rgba(201,168,76,0.3);
  }
  .result-info { min-width: 0; }
  .result-title {
    font-size: 0.93rem; font-weight: 600; color: var(--text);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .result-meta { font-size: 0.8rem; color: var(--text-sub); margin-top: 2px; }
  .download-btn {
    width: 100%;
    background: var(--text);
    color: var(--white);
    font-family: inherit;
    font-size: 0.93rem; font-weight: 700;
    padding: 14px; border: none; border-radius: 11px;
    cursor: pointer; letter-spacing: 0.03em;
    transition: background 0.2s, transform 0.1s;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  }
  .download-btn:hover { background: #333; }
  .download-btn:active { transform: scale(0.98); }

  /* Error */
  .error {
    display: none;
    background: var(--error-bg);
    border: 1.5px solid var(--error-border);
    border-radius: 11px;
    padding: 13px 16px;
    color: var(--error-text);
    font-size: 0.87rem; font-weight: 500;
    margin-top: 8px;
  }

  /* Spinner */
  .spinner {
    display: inline-block;
    width: 13px; height: 13px;
    border: 2px solid rgba(255,255,255,0.4);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    vertical-align: middle;
    margin-right: 6px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* Footer */
  .footer {
    margin-top: 24px;
    font-size: 0.76rem; color: #bbb;
    text-align: center; letter-spacing: 0.03em;
  }
</style>
</head>
<body>

<div class="top-bar">
  <div class="logo-mark">♪</div>
  <div class="logo-text">YT<span>2</span>MP3</div>
</div>

<div class="card">
  <div class="card-header">
    <h1>YouTube を <span class="accent">MP3</span> に変換</h1>
    <p class="subtitle">URLを貼り付けるだけ — 高音質で即ダウンロード</p>
  </div>
  <div class="divider"></div>

  <div class="input-label">YouTube URL</div>
  <div class="input-row">
    <input type="text" id="url" placeholder="https://www.youtube.com/watch?v=..." />
    <button class="primary" id="convertBtn" onclick="convert()">変換</button>
  </div>

  <div class="options">
    <div class="option-group">
      <label>音質</label>
      <div class="quality-pills">
        <input type="radio" name="quality" id="q320" value="320">
        <label class="pill" for="q320">320 kbps</label>
        <input type="radio" name="quality" id="q192" value="192" checked>
        <label class="pill" for="q192">192 kbps</label>
        <input type="radio" name="quality" id="q128" value="128">
        <label class="pill" for="q128">128 kbps</label>
        <input type="radio" name="quality" id="q96" value="96">
        <label class="pill" for="q96">96 kbps</label>
      </div>
    </div>
  </div>

  <div class="progress-area" id="progressArea">
    <div class="progress-top">
      <span class="progress-label" id="progressLabel">処理中...</span>
      <span class="progress-pct" id="progressPct"></span>
    </div>
    <div class="progress-bar-bg">
      <div class="progress-bar" id="progressBar"></div>
    </div>
  </div>

  <div class="error" id="errorBox"></div>

  <div class="result" id="resultBox">
    <div class="result-inner">
      <div class="result-icon">🎵</div>
      <div class="result-info">
        <div class="result-title" id="resultTitle"></div>
        <div class="result-meta" id="resultMeta"></div>
      </div>
    </div>
    <button class="download-btn" id="dlBtn">ダウンロード</button>
  </div>
</div>

<div class="footer">個人利用のみ · 著作権に配慮してご利用ください</div>

<script>
async function convert() {
  const url = document.getElementById('url').value.trim();
  if (!url) return;

  const quality = document.querySelector('input[name="quality"]:checked').value;
  const btn = document.getElementById('convertBtn');
  const errorBox = document.getElementById('errorBox');
  const resultBox = document.getElementById('resultBox');
  const progressArea = document.getElementById('progressArea');
  const bar = document.getElementById('progressBar');
  const label = document.getElementById('progressLabel');

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>変換中';
  errorBox.style.display = 'none';
  resultBox.style.display = 'none';
  progressArea.style.display = 'block';
  label.textContent = 'ダウンロード・変換中...';

  // CSSアニメーションで擬似進捗
  bar.classList.remove('loading');
  void bar.offsetWidth; // reflow
  bar.style.width = '0%';
  bar.style.transition = 'none';
  void bar.offsetWidth;
  bar.classList.add('loading');

  try {
    const res = await fetch('/api/convert', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url, quality})
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || '変換失敗');

    // 完了アニメーション
    bar.classList.remove('loading');
    bar.style.transition = 'width 0.4s cubic-bezier(0.4,0,0.2,1)';
    bar.style.width = '100%';
    label.textContent = '完了!';
    await new Promise(r => setTimeout(r, 400));

    progressArea.style.display = 'none';
    document.getElementById('resultTitle').textContent = data.title;
    document.getElementById('resultMeta').textContent = `${data.duration} • ${data.filesize}`;
    document.getElementById('dlBtn').onclick = async () => {
      // pywebview GUI モードでは JS API 経由でPython側がファイルを保存
      if (window.pywebview) {
        const result = await window.pywebview.api.save_file(data.token);
        if (result && result.error) {
          errorBox.textContent = '⚠ ' + result.error;
          errorBox.style.display = 'block';
        }
      } else {
        // ブラウザモード（開発時）は従来通り
        window.location.href = `/api/download/${data.token}`;
      }
    };
    resultBox.style.display = 'block';
  } catch(e) {
    bar.classList.remove('loading');
    progressArea.style.display = 'none';
    errorBox.textContent = '⚠ ' + e.message;
    errorBox.style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.textContent = '変換';
  }
}

document.getElementById('url').addEventListener('keydown', e => {
  if (e.key === 'Enter') convert();
});
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/convert", methods=["POST"])
def api_convert():
    data = request.get_json()
    url = (data or {}).get("url", "").strip()
    quality = (data or {}).get("quality", "192")

    if not url or not re.search(r"(youtube\.com|youtu\.be)", url):
        return jsonify({"error": "YouTubeのURLを入力してください"}), 400

    if quality not in ("96", "128", "192", "320"):
        quality = "192"

    token = str(uuid.uuid4())[:8]
    output_path = TMP_DIR / f"{token}.mp3"

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(TMP_DIR / f"{token}.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": quality,
        }],
        "quiet": True,
        "no_warnings": True,
    }

    ffmpeg_dir = get_ffmpeg_dir()
    if ffmpeg_dir:
        ydl_opts["ffmpeg_location"] = ffmpeg_dir

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "audio")
            duration_sec = info.get("duration", 0) or 0
            m, s = divmod(int(duration_sec), 60)
            duration_str = f"{m}:{s:02d}"

        size = output_path.stat().st_size
        size_str = f"{size / 1024 / 1024:.1f} MB" if size >= 1024 * 1024 else f"{size // 1024} KB"

        TITLES[token] = title

        return jsonify({
            "token": token,
            "title": title,
            "duration": duration_str,
            "filesize": size_str,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/download/<token>")
def api_download(token: str):
    if not re.match(r'^[a-f0-9]{8}$', token):
        return jsonify({"error": "Invalid token"}), 400

    filepath = TMP_DIR / f"{token}.mp3"
    if not filepath.exists():
        return jsonify({"error": "ファイルが見つかりません（期限切れの可能性があります）"}), 404

    raw_title = TITLES.get(token, "audio")
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', raw_title).strip()[:200] or "audio"

    return send_file(
        filepath,
        as_attachment=True,
        download_name=safe_name + ".mp3",
        mimetype="audio/mpeg",
    )


if __name__ == "__main__":
    import threading, webbrowser
    threading.Timer(1.2, lambda: webbrowser.open("http://localhost:5000")).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
