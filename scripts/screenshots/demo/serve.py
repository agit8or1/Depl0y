"""Serve the built Depl0y SPA and proxy /api/v1 to the demo backend."""
import os
import sys
import urllib.error
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn

DIST = sys.argv[1]
BACKEND = sys.argv[2]
PORT = int(sys.argv[3])
HOP = {"connection", "keep-alive", "transfer-encoding", "content-encoding", "content-length"}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DIST, **kw)

    def log_message(self, *a):
        pass

    def _proxy(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
        req = urllib.request.Request(BACKEND + self.path, data=body,
                                     headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                payload, code, hdrs = r.read(), r.status, r.headers
        except urllib.error.HTTPError as e:
            payload, code, hdrs = e.read(), e.code, e.headers
        except Exception as e:
            payload, code, hdrs = str(e).encode(), 502, {}
        self.send_response(code)
        for k, v in (hdrs.items() if hdrs else []):
            if k.lower() not in HOP:
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._proxy("GET")
        path = self.path.split("?")[0]
        candidate = os.path.join(DIST, path.lstrip("/"))
        if path != "/" and not os.path.exists(candidate):
            self.path = "/index.html"      # SPA fallback
        return super().do_GET()

    def do_POST(self):
        return self._proxy("POST")

    def do_PUT(self):
        return self._proxy("PUT")

    def do_PATCH(self):
        return self._proxy("PATCH")

    def do_DELETE(self):
        return self._proxy("DELETE")


class Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True


Server(("127.0.0.1", PORT), Handler).serve_forever()
