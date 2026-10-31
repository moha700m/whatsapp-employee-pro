"""Local-only HTTP server: serves static UI and POST /api/<method> -> Api.call()."""
import hmac, json, mimetypes, secrets, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from app.core.logger import get_logger
from app.web.api import ApiError

STATIC = Path(__file__).resolve().parent / "static"
mimetypes.add_type("font/ttf", ".ttf"); mimetypes.add_type("application/javascript", ".js")

def make_handler(api, token):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def _host_ok(self):   # DNS-rebinding guard: only our own loopback origin
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            mine = f"127.0.0.1:{self.server.server_address[1]}"
            return host == mine and (origin in (None, "null", "http://" + mine))
        def _authed(self):
            got = self.headers.get("X-Token") or ""
            ck = dict(x.strip().split("=", 1) for x in (self.headers.get("Cookie") or "").split(";") if "=" in x).get("wae_t", "")
            return hmac.compare_digest(got, token) or hmac.compare_digest(ck, token)
        def _send(self, code, body, ctype="application/json; charset=utf-8", cookie=False):
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code); self.send_header("Content-Type", ctype)
            self.send_header("X-Content-Type-Options", "nosniff"); self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            if cookie: self.send_header("Set-Cookie", f"wae_t={token}; HttpOnly; SameSite=Strict; Path=/")
            self.send_header("Content-Length", str(len(data))); self.send_header("Cache-Control", "no-store"); self.end_headers()
            self.wfile.write(data)
        def do_GET(self):
            path, _, qs = self.path.partition("?")
            if not self._host_ok(): return self._send(403, "forbidden", "text/plain")
            given = dict(p.split("=", 1) for p in qs.split("&") if "=" in p).get("t", "")
            first = bool(given) and hmac.compare_digest(given, token)
            if not (first or self._authed()):
                return self._send(403, "افتح البرنامج من START.bat", "text/plain; charset=utf-8")
            if path in ("/", ""): path = "/index.html"
            f = (STATIC / path.lstrip("/")).resolve()
            if STATIC not in f.parents or not f.is_file():
                return self._send(404, "not found", "text/plain")
            body = f.read_bytes()
            if f.name == "index.html":
                body = body.replace(b"__TOKEN__", token.encode())
            self._send(200, body, (mimetypes.guess_type(str(f))[0] or "application/octet-stream") + ("; charset=utf-8" if f.suffix in (".html", ".js", ".css") else ""), cookie=first)
        def do_POST(self):
            if not self.path.startswith("/api/"):
                return self._send(404, "{}")
            # token header (not cookie) + loopback Host/Origin + JSON body: blocks CSRF from any other web page
            if not self._host_ok() or not hmac.compare_digest(self.headers.get("X-Token") or "", token) \
                    or "application/json" not in (self.headers.get("Content-Type") or ""):
                return self._send(403, json.dumps({"ok": False, "error": "forbidden"}))
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n > 2_000_000: return self._send(413, json.dumps({"ok": False, "error": "الطلب كبير"}))
                params = json.loads(self.rfile.read(n).decode("utf-8") or "{}") if n else {}
                res = api.call(self.path[5:], params)
                self._send(200, json.dumps({"ok": True, "data": res}, ensure_ascii=False, default=str))
            except (ApiError, ValueError, PermissionError) as e:
                self._send(200, json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
            except Exception as e:
                get_logger().exception("api %s", self.path)
                self._send(200, json.dumps({"ok": False, "error": f"صار خطأ عندي، جرب مرة ثانية ({e})"}, ensure_ascii=False))
    return H

class UIServer:
    def __init__(self, api, port=0):
        self.token = secrets.token_urlsafe(16)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(api, self.token))
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}/"
        self.url = self.base + f"?t={self.token}"     # token travels once in the URL, then lives in an HttpOnly cookie
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True, name="ui-server")
    def start(self):
        self.thread.start(); return self.url
    def stop(self):
        self.httpd.shutdown(); self.httpd.server_close()
