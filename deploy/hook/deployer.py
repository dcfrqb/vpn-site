"""Tiny webhook that lets GitHub Actions trigger deploy.sh without SSH.

Listens on 127.0.0.1:8041, nginx proxies https://vpn.crs-projects.com/_deploy here.
Request: POST, JSON {"sha": "<40 hex>", "ts": <unix seconds>},
header X-Signature: hex HMAC-SHA256(secret, raw body). Replays older than 5 min are rejected.
Only runs the fixed script; the sha is validated again inside deploy.sh.
"""

import hashlib
import hmac
import json
import os
import re
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SECRET = os.environ["DEPLOY_HOOK_SECRET"].encode()
SCRIPT = "/opt/vpn-site/deploy/deploy.sh"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MAX_BODY = 1024
MAX_SKEW = 300


class Handler(BaseHTTPRequestHandler):
    def _reply(self, code: int, text: str) -> None:
        body = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= MAX_BODY:
            return self._reply(400, "bad length")
        raw = self.rfile.read(length)
        sig = self.headers.get("X-Signature", "")
        expected = hmac.new(SECRET, raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return self._reply(403, "bad signature")
        try:
            data = json.loads(raw)
            sha, ts = str(data["sha"]), int(data["ts"])
        except (ValueError, KeyError, TypeError):
            return self._reply(400, "bad body")
        if not SHA_RE.match(sha) or abs(time.time() - ts) > MAX_SKEW:
            return self._reply(400, "bad sha or stale request")
        proc = subprocess.run(  # noqa: S603
            [SCRIPT, sha], capture_output=True, text=True, timeout=1500, check=False
        )
        tail = (proc.stdout + proc.stderr)[-4000:]
        self._reply(200 if proc.returncode == 0 else 500, tail)

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8041), Handler).serve_forever()
