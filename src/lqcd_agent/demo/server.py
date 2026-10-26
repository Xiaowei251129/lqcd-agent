"""Small local demo over the same canonical CLI; no second workflow engine."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import subprocess
import sys

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/":
            self.send_error(404)
            return
        body = b'<!doctype html><meta charset="utf-8"><title>LQCD Agent</title><h1>LQCD Agent</h1><p>Current canonical mock workflow. No live provider or physics correctness claim.</p><button onclick="run()">Start synthetic run</button><pre id="result"></pre><script>async function run(){const r=await fetch("/run",{method:"POST"});document.getElementById("result").textContent=JSON.stringify(await r.json(),null,2)}</script>'
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        origin = self.headers.get("Origin")
        allowed = "http://127.0.0.1:" + str(self.server.server_port)
        if origin is not None and origin != allowed:
            self.send_error(403)
            return
        if self.path != "/run":
            self.send_error(404)
            return
        import secrets
        # No caller-provided paths, authority, shell commands or provider configuration.
        try:
            child = subprocess.run([sys.executable, "-B", "-m", "lqcd_agent", "start", "--key", secrets.token_hex(16)],
                                   capture_output=True, timeout=180)
            payload = json.loads(child.stdout) if child.returncode == 0 else {"error": child.stderr.decode()}
            status = 200 if child.returncode == 0 else 500
        except (subprocess.TimeoutExpired, ValueError) as error:
            payload, status = {"error": str(error)}, 500
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        server.serve_forever()

if __name__ == "__main__":
    main()
