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
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: #0f0f0f;
    color: #f1f1f1;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .card {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 16px;
    padding: 40px;
    width: 100%;
    max-width: 560px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
  }
  h1 {
    font-size: 1.6rem;
    font-weight: 700;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .subtitle {
    color: #888;
    font-size: 0.9rem;
    margin-bottom: 32px;
  }
  .input-row {
    display: flex;
    gap: 8px;
    margin-bottom: 20px;
  }
  input[type="text"] {
    flex: 1;
    background: #0f0f0f;
    border: 1px solid #333;
    border-radius: 10px;
    padding: 12px 16px;
    color: #f1f1f1;
    font-size: 0.95rem;
    outline: none;
    transition: border-color 0.2s;
  }
  input[type="text"]:focus {
    border-color: #ff4444;
  }
  button {
    background: #ff4444;
    color: white;
    border: none;
    border-radius: 10px;
    padding: 12px 22px;
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s, transform 0.1s;
    white-space: nowrap;
  }
  button:hover { background: #e03333; }
  button:active { transform: scale(0.97); }
  button:disabled { background: #444; cursor: not-allowed; transform: none; }

  .options {
    display: flex;
    gap: 16px;
    margin-bottom: 20px;
    flex-wrap: wrap;
  }
  .option-group label {
    font-size: 0.82rem;
    color: #888;
    display: block;
    margin-bottom: 4px;
  }
  select {
    background: #0f0f0f;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 8px 12px;
    color: #f1f1f1;
    font-size: 0.9rem;
    outline: none;
    cursor: pointer;
  }

  .progress-area {
    display: none;
    margin-bottom: 20px;
  }
  .progress-label {
    font-size: 0.85rem;
    color: #aaa;
    margin-bottom: 8px;
  }
  .progress-bar-bg {
    background: #2a2a2a;
    border-radius: 99px;
    height: 6px;
    overflow: hidden;
  }
  .progress-bar {
    background: linear-gradient(90deg, #ff4444, #ff7777);
    height: 100%;
    width: 0%;
    transition: width 0.3s;
    border-radius: 99px;
  }

  .result {
    display: none;
    background: #0f0f0f;
    border: 1px solid #2a2a2a;
    border-radius: 12px;
    padding: 20px;
    margin-top: 16px;
  }
  .result-title {
    font-size: 0.95rem;
    font-weight: 600;
    margin-bottom: 4px;
    color: #f1f1f1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .result-meta {
    font-size: 0.82rem;
    color: #888;
    margin-bottom: 16px;
  }
  .download-btn {
    width: 100%;
    background: #1db954;
    font-size: 1rem;
    padding: 14px;
    border-radius: 10px;
  }
  .download-btn:hover { background: #17a447; }

  .error {
    display: none;
    background: #2a1010;
    border: 1px solid #5a2020;
    border-radius: 10px;
    padding: 14px 16px;
    color: #ff8888;
    font-size: 0.88rem;
    margin-top: 16px;
  }
  .spinner {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 2px solid #ff4444;
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    vertical-align: middle;
    margin-right: 6px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="card">
  <h1>🎵 YouTube → MP3</h1>
  <p class="subtitle">URLを貼り付けてMP3に変換・ダウンロード</p>

  <div class="input-row">
    <input type="text" id="url" placeholder="https://www.youtube.com/watch?v=..." />
    <button id="convertBtn" onclick="convert()">変換</button>
  </div>

  <div class="options">
    <div class="option-group">
      <label>音質</label>
      <select id="quality">
        <option value="320">320 kbps</option>
        <option value="192" selected>192 kbps</option>
        <option value="128">128 kbps</option>
        <option value="96">96 kbps</option>
      </select>
    </div>
  </div>

  <div class="progress-area" id="progressArea">
    <div class="progress-label" id="progressLabel">処理中...</div>
    <div class="progress-bar-bg">
      <div class="progress-bar" id="progressBar"></div>
    </div>
  </div>

  <div class="error" id="errorBox"></div>

  <div class="result" id="resultBox">
    <div class="result-title" id="resultTitle"></div>
    <div class="result-meta" id="resultMeta"></div>
    <button class="download-btn" id="dlBtn">⬇ ダウンロード</button>
  </div>
</div>

<script>
let jobId = null;
let pollTimer = null;

async function convert() {
  const url = document.getElementById('url').value.trim();
  if (!url) return;

  const quality = document.getElementById('quality').value;
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
