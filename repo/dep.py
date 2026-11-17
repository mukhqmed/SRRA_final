import json, os, random, threading, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

FAULT = {"delay_ms": 0, "error_rate": 0.0, "down": False}
LOCK = threading.Lock()
NAME = os.environ.get("NAME", "dep")
PORT = int(os.environ.get("PORT", "8080"))

class H(BaseHTTPRequestHandler):
    def send(self, code, body):
        data = json.dumps(body).encode()
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass                      # клиент уже не ждёт ответа

    def do_GET(self):
        if self.path.startswith("/health"):
            return self.send(200, {"ok": True})
        with LOCK:
            f = dict(FAULT)
        if f["down"]:
            return self.send(503, {"error": "down"})
        time.sleep(f["delay_ms"] / 1000)
        if random.random() < f["error_rate"]:
            return self.send(500, {"error": "injected"})
        self.send(200, {"source": NAME, "value": random.randint(1, 100)})

    def do_POST(self):
        if self.path != "/fault":
            return self.send(404, {})
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        with LOCK:
            FAULT.update(json.loads(body or b"{}"))
            snapshot = dict(FAULT)
        self.send(200, snapshot)

    def log_message(self, *args):
        pass

ThreadingHTTPServer(("", PORT), H).serve_forever()
