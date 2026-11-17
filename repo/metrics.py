"""Метрики надёжности по CSV от loadgen.py (ts,status,latency_ms).

POFOD  = неудачных запросов / всех запросов (неудачный — код не 200);
ROCOF  = эпизодов отказа / длительность в часах; эпизод — серия неудачных
         запросов с промежутками между ними меньше 2 с;
AVAIL  = доля секунд, в которые был хотя бы один удачный ответ;
p50/p95/p99 — сортировка задержек и элемент с номером ceil(p * n).

Запуск:  python3 metrics.py results/off.csv  [--json]
Только стандартная библиотека.
"""
import csv, json, math, sys

EPISODE_GAP_S = 2.0


def read_rows(path):
    rows = []
    with open(path, newline="") as f:
        for rec in csv.reader(f):
            if len(rec) != 3:
                continue                       # заголовок или посторонняя строка лога
            try:
                rows.append((float(rec[0]), int(rec[1]), int(rec[2])))
            except ValueError:
                continue
    rows.sort()
    return rows


def percentile(sorted_values, p):
    n = len(sorted_values)
    k = max(1, math.ceil(round(p * n, 9)))     # номер элемента, 1..n
    return sorted_values[min(k, n) - 1]


def count_episodes(fail_ts, gap=EPISODE_GAP_S):
    episodes, last = 0, None
    for t in fail_ts:
        if last is None or t - last >= gap:
            episodes += 1
        last = t
    return episodes


def compute(rows):
    if not rows:
        raise ValueError("нет данных")
    t0 = rows[0][0]
    n = len(rows)
    fails = [ts for ts, code, _ in rows if code != 200]
    duration_s = int(rows[-1][0] - t0) + 1                     # число целых секунд прогона
    ok_seconds = {int(ts - t0) for ts, code, _ in rows if code == 200}
    lat = sorted(ms for _, _, ms in rows)
    episodes = count_episodes(fails)
    return {
        "requests": n,
        "failed": len(fails),
        "POFOD": len(fails) / n,
        "episodes": episodes,
        "duration_s": duration_s,
        "ROCOF_per_h": episodes / (duration_s / 3600),
        "AVAIL": len(ok_seconds) / duration_s,
        "p50_ms": percentile(lat, 0.50),
        "p95_ms": percentile(lat, 0.95),
        "p99_ms": percentile(lat, 0.99),
    }


def fmt(m):
    return ("POFOD={POFOD:.4f} ROCOF={ROCOF_per_h:.1f}/ч AVAIL={AVAIL:.4f} "
            "p50/p95/p99={p50_ms}/{p95_ms}/{p99_ms} мс "
            "(запросов {requests}, неудачных {failed}, эпизодов {episodes}, {duration_s} с)").format(**m)


def main(argv):
    if len(argv) < 2:
        print("usage: python3 metrics.py results/off.csv [--json]")
        return 2
    m = compute(read_rows(argv[1]))
    print(json.dumps(m, ensure_ascii=False) if "--json" in argv else fmt(m))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
