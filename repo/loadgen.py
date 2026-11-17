import argparse, threading, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

p = argparse.ArgumentParser()
p.add_argument("--url", default="http://app-svc/work")
p.add_argument("--rps", type=int, default=20)
p.add_argument("--duration", type=int, default=120)
p.add_argument("--timeout", type=float, default=1.5)   # сколько ждёт пользователь
a = p.parse_args()
OUT = threading.Lock()

def one(t0):
    start = time.time()
    try:
        with urllib.request.urlopen(a.url, timeout=a.timeout) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception:
        code = 0                      # не дождались ответа
    ms = int((time.time() - start) * 1000)
    with OUT:
        print(f"{t0:.3f},{code},{ms}", flush=True)

print("ts,status,latency_ms", flush=True)
with ThreadPoolExecutor(max_workers=300) as pool:
    t = time.time()
    for i in range(a.rps * a.duration):
        pool.submit(one, t)
        t += 1 / a.rps
        time.sleep(max(0, t - time.time()))
