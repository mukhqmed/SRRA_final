import itertools, json, os, threading, time, urllib.error, urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

DEP_URL = os.environ.get("DEP_URL", "http://dep-a")
DEP_URL_B = os.environ.get("DEP_URL_B", "http://dep-b")     # резервный канал (только для аварийных команд)
PATTERN = os.environ.get("PATTERN", "off") == "on"
COUNT = {}
LOCK = threading.Lock()

def inc(name):
    with LOCK:
        COUNT[name] = COUNT.get(name, 0) + 1

def call_dep(timeout=10.0):
    with urllib.request.urlopen(DEP_URL + "/work", timeout=timeout) as r:
        return json.loads(r.read())

# ---------------------------------------------------------------------------
# Паттерн варианта 29 «Автономные самосвалы»: Bulkhead + приоритет аварийных команд.
#
# Запросы к зависимости (радиосеть карьера, dep-a) делятся на два отсека:
#   normal    — телеметрия, отчётность, назначение рейсов (можно отложить);
#   emergency — аварийная остановка машин (нельзя потерять).
# Правила:
#   1. Обычные запросы занимают не больше NORMAL_LIMIT потоков; лишние сразу
#      отклоняются (BulkheadFull), а не копятся в очереди и не съедают память.
#   2. Аварийные команды имеют свой отсек EMERGENCY_LIMIT, недоступный обычным
#      запросам: перегрузка обычного отсека их не задерживает.
#   3. Каждый вызов ограничен таймаутом отсека; обычный запрос по таймауту
#      получает ответ «отложено» (deferred) и освобождает поток.
#   4. Приоритет: аварийная команда при сбое или таймауте dep-a сразу уходит
#      по резервному каналу dep-b; обычные запросы резервный канал не занимают.
# Все пороги читаются из переменных окружения.
# ---------------------------------------------------------------------------
NORMAL_LIMIT = int(os.environ.get("NORMAL_LIMIT", "8"))
EMERGENCY_LIMIT = int(os.environ.get("EMERGENCY_LIMIT", "4"))
NORMAL_TIMEOUT = float(os.environ.get("NORMAL_TIMEOUT_S", "0.8"))
EMERGENCY_TIMEOUT = float(os.environ.get("EMERGENCY_TIMEOUT_S", "0.5"))
EMERGENCY_EVERY = int(os.environ.get("EMERGENCY_EVERY", "10"))   # каждый 10-й запрос — аварийная команда

NORMAL_POOL = threading.BoundedSemaphore(NORMAL_LIMIT)
EMERGENCY_POOL = threading.BoundedSemaphore(EMERGENCY_LIMIT)
_SEQ = itertools.count(1)


class BulkheadFull(Exception):
    """Отсек заполнен: запрос отклонён сразу, без ожидания."""


def call_backup(timeout=1.0):
    with urllib.request.urlopen(DEP_URL_B + "/work", timeout=timeout) as r:
        return json.loads(r.read())


def next_kind():
    # loadgen шлёт одинаковые запросы /work, поэтому смесь трафика моделируется
    # счётчиком: каждый EMERGENCY_EVERY-й запрос считается аварийной командой.
    return "emergency" if next(_SEQ) % EMERGENCY_EVERY == 0 else "normal"


def normal_request():
    if not NORMAL_POOL.acquire(blocking=False):            # правило 1
        inc('bulkhead_total{kind="normal",result="rejected"}')
        raise BulkheadFull("normal compartment full")
    try:
        try:
            body = call_dep(timeout=NORMAL_TIMEOUT)          # правило 3
            inc('bulkhead_total{kind="normal",result="ok"}')
            return {"kind": "normal", "status": "ok", **body}
        except Exception:
            inc('bulkhead_total{kind="normal",result="deferred"}')
            return {"kind": "normal", "status": "deferred"}
    finally:
        NORMAL_POOL.release()


def emergency_command():
    # Свой отсек (правило 2); аварийная команда может подождать слот,
    # но не дольше своего таймаута.
    if not EMERGENCY_POOL.acquire(timeout=EMERGENCY_TIMEOUT):
        inc('bulkhead_total{kind="emergency",result="rejected"}')
        raise BulkheadFull("emergency compartment full")
    try:
        try:
            body = call_dep(timeout=EMERGENCY_TIMEOUT)
            inc('bulkhead_total{kind="emergency",result="primary"}')
            return {"kind": "emergency", "status": "ok", "channel": "primary", **body}
        except Exception:                                    # правило 4
            body = call_backup(timeout=EMERGENCY_TIMEOUT)
            inc('bulkhead_total{kind="emergency",result="backup"}')
            return {"kind": "emergency", "status": "ok", "channel": "backup", **body}
    finally:
        EMERGENCY_POOL.release()


def do_work(kind=None):
    if not PATTERN:
        return call_dep()                      # без меры: ждём dep до 10 с
    kind = kind or next_kind()
    if kind == "emergency":
        return emergency_command()
    return normal_request()


class H(BaseHTTPRequestHandler):
    def reply(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if self.path == "/health":
            return self.reply(200, {"ok": True})
        if self.path == "/metrics":
            with LOCK:
                text = "".join(f"{k} {v}\n" for k, v in sorted(COUNT.items()))
            return self.reply(200, text, "text/plain")
        if self.path == "/work":
            try:
                body, code = do_work(), 200
            except Exception as e:
                body, code = {"error": str(e)}, 500
            inc(f'requests_total{{code="{code}"}}')
            return self.reply(code, body)
        self.reply(404, {})

    def log_message(self, *args):
        pass

if __name__ == "__main__":
    ThreadingHTTPServer(("", int(os.environ.get("PORT", "8080"))), H).serve_forever()
