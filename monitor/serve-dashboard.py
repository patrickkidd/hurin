#!/usr/bin/env python3
"""
Serve the CI dashboard on localhost:8787.

Binds to 127.0.0.1 ONLY — not accessible from the internet.
Access via SSH tunnel: ssh -L 8787:localhost:8787 hurin
Then open: http://localhost:8787/ci-dashboard.html

Auto-regenerates the dashboard on each request (< 1s).
"""

import http.server
import os
import subprocess
import sys
from pathlib import Path

MONITOR_DIR = Path.home() / ".openclaw/monitor"
HOST = "127.0.0.1"  # Localhost only — NOT 0.0.0.0
PORT = 8787


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Serve files from MONITOR_DIR. Regenerate dashboard on request."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(MONITOR_DIR), **kwargs)

    def do_GET(self):
        # Regenerate dashboard on every request to /ci-dashboard.html
        if self.path in ("/", "/ci-dashboard.html"):
            try:
                subprocess.run(
                    [sys.executable, str(MONITOR_DIR / "ci-dashboard.py")],
                    capture_output=True, timeout=10,
                    cwd=str(MONITOR_DIR),
                )
            except Exception:
                pass  # Serve stale dashboard if regen fails
            if self.path == "/":
                self.path = "/ci-dashboard.html"
        super().do_GET()

    def log_message(self, format, *args):
        # Suppress noisy access logs
        pass


if __name__ == "__main__":
    server = http.server.HTTPServer((HOST, PORT), DashboardHandler)
    print(f"Dashboard serving on http://{HOST}:{PORT}/ci-dashboard.html")
    print(f"Access via: ssh -L {PORT}:localhost:{PORT} hurin")
    print("Then open: http://localhost:8787/ci-dashboard.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
