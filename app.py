import os
import re
import uuid
import threading
import time
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template_string
import yt_dlp

app = Flask(__name__)

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# ファイルを1時間後に自動削除するキャッシュ
file_registry: dict[str, dict] = {}

def cleanup_file(filepath: str, delay: int = 3600):
    def _delete():
        time.sleep(delay)
        try:
            Path(filepath).unlink(missing_ok=True)
            file_registry.pop(filepath, None)
        except Exception:
            pass
    threading.Thread(target=_delete, daemon=True).start()


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

  /* ── Header line ── */
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

  /* ── Card ── */
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

  .card-header {
    margin-bottom: 32px;
  }
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

  /* ── Divider ── */
  .divider {
    height: 1px;
    background: linear-gradient(90deg, var(--gold-subtle), transparent);
    margin-bottom: 28px;
  }

  /* ── Input ── */
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
  button.primary:hover {
    opacity: 0.88;
    box-shadow: 0 5px 18px rgba(201,168,76,0.5);
  }
  button.primary:active { transform: scale(0.97); }
  button.primary:disabled {
    background: #e0e0e0;
    color: #aaa;
    box-shadow: none;
    cursor: not-allowed;
    transform: none;
    opacity: 1;
  }

  /* ── Quality ── */
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
  .quality-pills {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
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
  .quality-pills label.pill:hover {
    border-color: var(--gold);
    color: var(--gold-dark);
  }

  /* ── Progress ── */
  .progress-area {
    display: none;
    margin-bottom: 20px;
  }
  .progress-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }
  .progress-label {
    font-size: 0.83rem;
    font-weight: 500;
    color: var(--text-sub);
  }
  .progress-pct {
    font-size: 0.8rem;
    font-weight: 700;
    color: var(--gold);
  }
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
    transition: width 0.4s cubic-bezier(0.4,0,0.2,1);
    border-radius: 99px;
  }

  /* ── Result ── */
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
    width: 40px;
    height: 40px;
    background: linear-gradient(135deg, var(--gold), var(--gold-light));
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.1rem;
    flex-shrink: 0;
    box-shadow: 0 2px 8px rgba(201,168,76,0.3);
  }
  .result-info { min-width: 0; }
  .result-title {
    font-size: 0.93rem;
    font-weight: 600;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .result-meta {
    font-size: 0.8rem;
    color: var(--text-sub);
    margin-top: 2px;
  }
  .download-btn {
    width: 100%;
    background: var(--text);
    color: var(--white);
    font-family: inherit;
    font-size: 0.93rem;
    font-weight: 700;
    padding: 14px;
    border: none;
    border-radius: 11px;
    cursor: pointer;
    letter-spacing: 0.03em;
    transition: background 0.2s, transform 0.1s;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  }
  .download-btn:hover { background: #333; }
  .download-btn:active { transform: scale(0.98); }

  /* ── Error ── */
  .error {
    display: none;
    background: var(--error-bg);
    border: 1.5px solid var(--error-border);
    border-radius: 11px;
    padding: 13px 16px;
    color: var(--error-text);
    font-size: 0.87rem;
    font-weight: 500;
    margin-top: 8px;
  }

  /* ── Spinner ── */
  .spinner {
    display: inline-block;
    width: 13px;
    height: 13px;
    border: 2px solid rgba(255,255,255,0.4);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    vertical-align: middle;
    margin-right: 6px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ── Footer ── */
  .footer {
    margin-top: 24px;
    font-size: 0.76rem;
    color: #bbb;
    text-align: center;
    letter-spacing: 0.03em;
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
let jobId = null;
let pollTimer = null;

async function convert() {
  const url = document.getElementById('url').value.trim();
  if (!url) return;

  const quality = document.querySelector('input[name="quality"]:checked').value;
  const btn = document.getElementById('convertBtn');
  const errorBox = document.getElementById('errorBox');
  const resultBox = document.getElementById('resultBox');
  const progressArea = document.getElementById('progressArea');

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>変換中';
  errorBox.style.display = 'none';
  resultBox.style.display = 'none';
  progressArea.style.display = 'block';
  setProgress(5, '動画情報を取得中...');

  try {
    const res = await fetch('/api/convert', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url, quality})
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || '変換失敗');
    jobId = data.job_id;
    pollStatus();
  } catch(e) {
    showError(e.message);
    resetBtn();
  }
}

function pollStatus() {
  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`/api/status/${jobId}`);
      const data = await res.json();

      if (data.status === 'downloading') {
        setProgress(data.percent || 20, `ダウンロード中... ${data.percent || ''}%`);
      } else if (data.status === 'converting') {
        setProgress(80, 'MP3に変換中...');
      } else if (data.status === 'done') {
        clearInterval(pollTimer);
        setProgress(100, '完了!');
        showResult(data);
        resetBtn();
      } else if (data.status === 'error') {
        clearInterval(pollTimer);
        showError(data.error);
        resetBtn();
      }
    } catch(e) {
      clearInterval(pollTimer);
      showError('サーバーとの通信に失敗しました');
      resetBtn();
    }
  }, 1000);
}

function setProgress(pct, label) {
  document.getElementById('progressBar').style.width = pct + '%';
  document.getElementById('progressLabel').textContent = label;
  document.getElementById('progressPct').textContent = pct < 100 ? pct + '%' : '';
}

function showResult(data) {
  document.getElementById('progressArea').style.display = 'none';
  const box = document.getElementById('resultBox');
  document.getElementById('resultTitle').textContent = data.title;
  document.getElementById('resultMeta').textContent = `${data.duration} • ${data.filesize}`;
  document.getElementById('dlBtn').onclick = () => {
    window.location.href = `/api/download/${data.job_id}`;
  };
  box.style.display = 'block';
}

function showError(msg) {
  document.getElementById('progressArea').style.display = 'none';
  const box = document.getElementById('errorBox');
  box.textContent = '⚠ ' + msg;
  box.style.display = 'block';
}

function resetBtn() {
  const btn = document.getElementById('convertBtn');
  btn.disabled = false;
  btn.textContent = '変換';
}

document.getElementById('url').addEventListener('keydown', e => {
  if (e.key === 'Enter') convert();
});
</script>
</body>
</html>
"""

jobs: dict[str, dict] = {}


def run_download(job_id: str, url: str, quality: str):
    output_path = DOWNLOAD_DIR / f"{job_id}.mp3"

    def progress_hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            if total:
                pct = int(downloaded / total * 100)
                jobs[job_id]["percent"] = pct
            jobs[job_id]["status"] = "downloading"
        elif d["status"] == "finished":
            jobs[job_id]["status"] = "converting"

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(DOWNLOAD_DIR / f"{job_id}.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": quality,
        }],
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "audio")
            duration_sec = info.get("duration", 0)
            m, s = divmod(duration_sec, 60)
            duration_str = f"{m}:{s:02d}"

        # ファイルサイズ取得
        size = output_path.stat().st_size
        if size < 1024 * 1024:
            size_str = f"{size // 1024} KB"
        else:
            size_str = f"{size / 1024 / 1024:.1f} MB"

        jobs[job_id].update({
            "status": "done",
            "title": title,
            "duration": duration_str,
            "filesize": size_str,
            "filepath": str(output_path),
            "filename": re.sub(r'[\\/*?:"<>|]', "_", title) + ".mp3",
        })
        cleanup_file(str(output_path))

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/convert", methods=["POST"])
def convert():
    data = request.get_json()
    url = data.get("url", "").strip()
    quality = data.get("quality", "192")

    if not url:
        return jsonify({"error": "URLが必要です"}), 400

    # 簡易URLバリデーション
    if not re.search(r"(youtube\.com|youtu\.be)", url):
        return jsonify({"error": "YouTubeのURLを入力してください"}), 400

    if quality not in ("96", "128", "192", "320"):
        quality = "192"

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "downloading", "percent": 0}

    thread = threading.Thread(target=run_download, args=(job_id, url, quality), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "ジョブが見つかりません"}), 404
    return jsonify({**job, "job_id": job_id})


@app.route("/api/download/<job_id>")
def download(job_id: str):
    job = jobs.get(job_id)
    if not job or job.get("status") != "done":
        return jsonify({"error": "ファイルが見つかりません"}), 404

    filepath = job["filepath"]
    filename = job["filename"]

    return send_file(
        filepath,
        as_attachment=True,
        download_name=filename,
        mimetype="audio/mpeg",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
