#!/usr/bin/env python3
"""
Flask web server for OptiBot log viewing and manual triggering.
Provides public endpoints for viewing logs and running scraper on-demand.
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from flask import Flask, Response, render_template_string, request, jsonify

app = Flask(__name__)

# Configuration
LOG_FILE = os.getenv('LOG_FILE', '/app/logs/optibot.log')
PORT = int(os.getenv('PORT', 8000))

# HTML template for web UI
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OptiBot Logs</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        header {
            background: #2d2d30;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }
        h1 {
            color: #4ec9b0;
            font-size: 28px;
            margin-bottom: 10px;
        }
        .subtitle {
            color: #858585;
            font-size: 14px;
        }
        .controls {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
            align-items: center;
        }
        button {
            background: #0e639c;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            font-family: inherit;
            transition: background 0.2s;
        }
        button:hover {
            background: #1177bb;
        }
        button:disabled {
            background: #555;
            cursor: not-allowed;
        }
        .status {
            padding: 8px 16px;
            background: #2d2d30;
            border-radius: 4px;
            font-size: 13px;
        }
        .status.success { color: #4ec9b0; }
        .status.error { color: #f48771; }
        .log-container {
            background: #1e1e1e;
            border: 1px solid #3e3e42;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }
        .log-header {
            background: #2d2d30;
            padding: 12px 20px;
            border-bottom: 1px solid #3e3e42;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .log-title {
            color: #858585;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .log-content {
            padding: 20px;
            font-size: 13px;
            line-height: 1.6;
            max-height: 70vh;
            overflow-y: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        .log-line {
            margin-bottom: 4px;
        }
        .timestamp {
            color: #858585;
        }
        .separator {
            color: #3e3e42;
        }
        .keyword {
            color: #4ec9b0;
            font-weight: bold;
        }
        .error {
            color: #f48771;
        }
        .success {
            color: #4ec9b0;
        }
        .footer {
            margin-top: 20px;
            text-align: center;
            color: #858585;
            font-size: 12px;
        }
        .footer a {
            color: #4ec9b0;
            text-decoration: none;
        }
        .footer a:hover {
            text-decoration: underline;
        }
        @media (max-width: 768px) {
            body { padding: 10px; }
            h1 { font-size: 22px; }
            .controls { flex-direction: column; width: 100%; }
            button { width: 100%; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 OptiBot Logs</h1>
            <p class="subtitle">Zendesk Article Scraper & OpenAI Vector Store Uploader</p>
        </header>

        <div class="controls">
            <button onclick="refreshLogs()">🔄 Refresh Logs</button>
            <button onclick="runNow()" id="runBtn">▶️ Run Now</button>
            <button onclick="downloadLogs()">⬇️ Download Logs</button>
            <select id="lineCount" onchange="refreshLogs()">
                <option value="100">Last 100 lines</option>
                <option value="500" selected>Last 500 lines</option>
                <option value="1000">Last 1000 lines</option>
                <option value="all">All logs</option>
            </select>
            <label>
                <input type="checkbox" id="autoRefresh" onchange="toggleAutoRefresh()" checked>
                Auto-refresh (30s)
            </label>
            <span class="status" id="status">Ready</span>
        </div>

        <div class="log-container">
            <div class="log-header">
                <span class="log-title">📋 Log Output</span>
                <span id="lastUpdate" style="color: #858585; font-size: 12px;">Loading...</span>
            </div>
            <div class="log-content" id="logContent">
                Loading logs...
            </div>
        </div>

        <div class="footer">
            <p>OptiBot | <a href="/logs/raw" target="_blank">Raw Logs</a> | <a href="/health">Health Check</a></p>
        </div>
    </div>

    <script>
        let autoRefreshInterval = null;

        function formatLog(text) {
            return text
                .replace(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/gm, '<span class="timestamp">$1</span>')
                .replace(/==+/g, '<span class="separator">$&</span>')
                .replace(/✅|🚀|Running|Started|Success|Completed/gi, '<span class="success">$&</span>')
                .replace(/❌|⚠️|Error|Failed|Warning/gi, '<span class="error">$&</span>')
                .replace(/\b(Added|Updated|Uploaded|Skipped):/gi, '<span class="keyword">$&</span>');
        }

        async function refreshLogs() {
            const lineCount = document.getElementById('lineCount').value;
            const url = lineCount === 'all' ? '/logs' : `/logs?lines=${lineCount}`;

            try {
                const response = await fetch(url);
                const text = await response.text();
                document.getElementById('logContent').innerHTML = formatLog(text) || '<span style="color: #858585;">No logs yet...</span>';
                document.getElementById('lastUpdate').textContent = `Last updated: ${new Date().toLocaleTimeString()}`;
                setStatus('Ready', 'success');
            } catch (error) {
                document.getElementById('logContent').textContent = `Error loading logs: ${error.message}`;
                setStatus('Error', 'error');
            }
        }

        async function runNow() {
            const btn = document.getElementById('runBtn');
            btn.disabled = true;
            setStatus('Running...', 'success');

            try {
                const response = await fetch('/run', { method: 'POST' });
                const data = await response.json();

                if (data.status === 'started') {
                    setStatus('Run started! Refreshing logs...', 'success');
                    setTimeout(refreshLogs, 2000);
                } else {
                    setStatus(data.message || 'Unknown error', 'error');
                }
            } catch (error) {
                setStatus(`Error: ${error.message}`, 'error');
            } finally {
                setTimeout(() => {
                    btn.disabled = false;
                    setStatus('Ready', 'success');
                }, 5000);
            }
        }

        function downloadLogs() {
            window.open('/logs/raw', '_blank');
        }

        function setStatus(message, type) {
            const statusEl = document.getElementById('status');
            statusEl.textContent = message;
            statusEl.className = `status ${type}`;
        }

        function toggleAutoRefresh() {
            const enabled = document.getElementById('autoRefresh').checked;

            if (enabled) {
                autoRefreshInterval = setInterval(refreshLogs, 30000);
                setStatus('Auto-refresh enabled', 'success');
            } else {
                clearInterval(autoRefreshInterval);
                setStatus('Auto-refresh disabled', 'success');
            }

            setTimeout(() => setStatus('Ready', 'success'), 2000);
        }

        // Initial load
        refreshLogs();
        toggleAutoRefresh();
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """Main web UI for viewing logs."""
    return render_template_string(HTML_TEMPLATE)


@app.route('/logs')
def get_logs():
    """Return log file content as plain text.

    Query params:
        lines: Number of lines to return (default: 500)
    """
    try:
        log_path = Path(LOG_FILE)

        if not log_path.exists():
            return "No logs yet. Waiting for first run...", 200

        # Get number of lines to return
        lines = request.args.get('lines', '500')

        if lines == 'all':
            # Return entire file
            with open(log_path, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            # Return last N lines
            try:
                line_count = int(lines)
                result = subprocess.run(
                    ['tail', f'-n{line_count}', str(log_path)],
                    capture_output=True,
                    text=True
                )
                content = result.stdout
            except (ValueError, subprocess.CalledProcessError):
                with open(log_path, 'r', encoding='utf-8') as f:
                    content = f.read()

        return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}

    except Exception as e:
        return f"Error reading logs: {str(e)}", 500


@app.route('/logs/raw')
def download_logs():
    """Download raw log file."""
    try:
        log_path = Path(LOG_FILE)

        if not log_path.exists():
            return "No logs yet.", 404

        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return Response(
            content,
            mimetype='text/plain',
            headers={
                'Content-Disposition': f'attachment; filename=optibot-{datetime.now().strftime("%Y%m%d-%H%M%S")}.log'
            }
        )

    except Exception as e:
        return f"Error downloading logs: {str(e)}", 500


@app.route('/health')
def health():
    """Health check endpoint for Render."""
    try:
        log_path = Path(LOG_FILE)
        log_exists = log_path.exists()

        # Check if cron is running
        cron_check = subprocess.run(
            ['pgrep', 'cron'],
            capture_output=True
        )
        cron_running = cron_check.returncode == 0

        status = {
            'status': 'healthy' if cron_running else 'degraded',
            'timestamp': datetime.now().isoformat(),
            'cron_running': cron_running,
            'log_file_exists': log_exists,
            'log_file_path': LOG_FILE
        }

        if log_exists:
            status['log_file_size'] = log_path.stat().st_size
            status['log_last_modified'] = datetime.fromtimestamp(
                log_path.stat().st_mtime
            ).isoformat()

        return jsonify(status), 200 if cron_running else 503

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/run', methods=['POST'])
def run_now():
    """Manually trigger a scraper run.

    Runs main.py in the background and returns immediately.
    """
    try:
        # Run main.py in background
        subprocess.Popen(
            ['/usr/local/bin/python', '/app/main.py'],
            stdout=open(LOG_FILE, 'a'),
            stderr=subprocess.STDOUT,
            cwd='/app'
        )

        # Log the manual trigger
        with open(LOG_FILE, 'a') as f:
            f.write(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Manual run triggered via web UI\n")

        return jsonify({
            'status': 'started',
            'message': 'Scraper run started in background. Check logs for progress.',
            'timestamp': datetime.now().isoformat()
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


if __name__ == '__main__':
    # Ensure log file exists
    log_path = Path(LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.touch(exist_ok=True)

    print(f"🚀 Starting OptiBot Web Server on port {PORT}")
    print(f"📋 Log file: {LOG_FILE}")
    print(f"🌐 Access at: http://0.0.0.0:{PORT}")

    # Run Flask server
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=False,
        threaded=True
    )
