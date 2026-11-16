"""Локальная репетиция эксперимента без Kubernetes (только для проверки кода).

Поднимает dep-a/dep-b/dep-c, R экземпляров core.py и простой балансировщик
round-robin вместо Service app-svc, затем повторяет сценарий experiment.sh:
0–30 с норма, 30–60 с отказ dep-a, 60–120 с восстановление.
Итоговые цифры для отчёта берутся из прогона в Killercoda (experiment.sh).

Запуск из корня репозитория:
    python3 tools/local_experiment.py off
    python3 tools/local_experiment.py on
"""
import argparse, json, os, subprocess, sys, threading, time, urllib.error, urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = argparse.ArgumentParser()
p.add_argument("mode", choices=["off", "on"])
p.add_argument("--replicas", type=int, default=4)              # R варианта 29
p.add_argument("--fault", default='{"delay_ms": 3000}')         # отказ варианта 29
p.add_argument("--duration", type=int, default=120)
p.add_argument("--fault-at", type=int, default=30)
p.add_argument("--fix-at", type=int, default=60)
p.add_argument("--tag", default="", help="суффикс имени файла результатов")
a = p.parse_args()

DEP_PORTS = {"dep-a": 18081, "dep-b": 18082, "dep-c": 18083}
CORE_PORTS = [18091 + i for i in range(a.replicas)]
LB_PORT = 18080
procs = []


def start(script, env):
    e = dict(os.environ, **env)
    procs.append(subprocess.Popen([sys.executable, os.path.join(ROOT, script)], env=e,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))


def post_fault(port, body):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/fault", data=body.encode(), method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.read().decode()


class LB(BaseHTTPRequestHandler):
    i = 0
    lock = threading.Lock()

    def do_GET(self):
        with LB.lock:
            port = CORE_PORTS[LB.i % len(CORE_PORTS)]
            LB.i += 1
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{self.path}", timeout=15) as r:
                code, data = r.status, r.read()
        except urllib.error.HTTPError as e:
            code, data = e.code, e.read()
        except Exception:
            code, data = 502, b"{}"
        try:
            self.send_response(code)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):
        pass


try:
    for name, port in DEP_PORTS.items():
        start("dep.py", {"NAME": name, "PORT": str(port)})
    for port in CORE_PORTS:
        start("core.py", {"PORT": str(port), "PATTERN": a.mode,
                          "DEP_URL": f"http://127.0.0.1:{DEP_PORTS['dep-a']}",
                          "DEP_URL_B": f"http://127.0.0.1:{DEP_PORTS['dep-b']}",
                          "DEP_URL_C": f"http://127.0.0.1:{DEP_PORTS['dep-c']}"})
    lb = ThreadingHTTPServer(("127.0.0.1", LB_PORT), LB)
    threading.Thread(target=lb.serve_forever, daemon=True).start()
    time.sleep(1.5)

    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    out_path = os.path.join(ROOT, "results", f"local_{a.mode}{a.tag}.csv")
    with open(out_path, "w") as out:
        load = subprocess.Popen([sys.executable, os.path.join(ROOT, "loadgen.py"),
                                 "--url", f"http://127.0.0.1:{LB_PORT}/work", "--rps", "20",
                                 "--duration", str(a.duration), "--timeout", "1.5"], stdout=out)
        t0 = time.time()
        print("0 с: нагрузка пошла", flush=True)
        time.sleep(max(0, t0 + a.fault_at - time.time()))
        print(post_fault(DEP_PORTS["dep-a"], a.fault), f"<- {a.fault_at} с: отказ включён", flush=True)
        time.sleep(max(0, t0 + a.fix_at - time.time()))
        print(post_fault(DEP_PORTS["dep-a"], '{"delay_ms": 0, "error_rate": 0, "down": false}'),
              f"<- {a.fix_at} с: отказ снят", flush=True)
        load.wait()

    totals = {}
    for port in CORE_PORTS:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=5) as r:
            for line in r.read().decode().splitlines():
                k, v = line.rsplit(" ", 1)
                totals[k] = totals.get(k, 0) + int(v)
    with open(os.path.join(ROOT, "results", f"local_{a.mode}{a.tag}_core_metrics.txt"), "w") as f:
        f.write("".join(f"{k} {v}\n" for k, v in sorted(totals.items())))
    print("core /metrics (сумма по репликам):")
    for k, v in sorted(totals.items()):
        print(" ", k, v)
    subprocess.run([sys.executable, os.path.join(ROOT, "metrics.py"), out_path])
finally:
    for pr in procs:
        pr.terminate()
