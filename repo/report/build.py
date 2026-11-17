"""Сборка отчёта: подставляет данные пары и цифры эксперимента, рисует графики, печатает PDF.

1. Заполните ПАРАМЕТРЫ ниже.
2. После прогонов в Killercoda положите results/off.csv, results/on.csv
   (и, по желанию, results/on_core_metrics.txt, results/on_limit2.csv, results/on_limit2_core_metrics.txt).
   Пока их нет, берутся локальные репетиции results/local_*.csv.
3. python3 report/build.py   ->  report/report.pdf   (нужен Google Chrome или Chromium)
"""
import os, re, shutil, subprocess, sys

# ---------------- ПАРАМЕТРЫ ----------------
P = {
    "UNIVERSITY": "Название университета",
    "STUDENT_A": "Фамилия Имя (A)",
    "STUDENT_B": "Фамилия Имя (B)",
    "GROUP": "Группа",
    "PAIR_NO": "№ пары",
    "TEACHER": "Asel Zh.",
    "REPO_URL": "https://github.com/…/…",
    "CITY_YEAR": "2026",
    # Кто писал код — уточните у преподавателя: в документе и в презентации роли по коду указаны по-разному.
    "CODE_A": "metrics.py, test_metrics.py, расчёты report/calc",
    "CODE_B": "паттерн в core.py, test_core.py, stand.yaml, k8s/production-plan.yaml",
    "AI_NOTE": ("При подготовке использовался ассистент Claude (Anthropic) с разрешения преподавателя: "
                "черновики текста разделов, проверка расчётов, генерация схем и черновик кода, "
                "который пара проверила, запустила и может объяснить построчно. "
                "Все цифры эксперимента получены нашим прогоном в Killercoda."),
}
# -------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import metrics  # noqa: E402


def pick(name):
    real = os.path.join(ROOT, "results", f"{name}.csv")
    return (real, True) if os.path.exists(real) else (os.path.join(ROOT, "results", f"local_{name}.csv"), False)


def counters(name):
    for fn in (f"{name}_core_metrics.txt", f"local_{name}_core_metrics.txt"):
        path = os.path.join(ROOT, "results", fn)
        if os.path.exists(path):
            c = {}
            for line in open(path):
                if line.strip():
                    k, v = line.rsplit(" ", 1)
                    c[k] = int(v)
            return c
    return {}


num = lambda x, d=4: f"{x:.{d}f}".replace(".", ",")
pct = lambda x: f"{x * 100:.1f}%".replace(".", ",")

(off_p, off_real), (on_p, on_real) = pick("off"), pick("on")
off = metrics.compute(metrics.read_rows(off_p))
on = metrics.compute(metrics.read_rows(on_p))
real = off_real and on_real
P["SRC"] = ("прогоны в Killercoda (results/off.csv, results/on.csv)" if real else
            "локальная репетиция стенда без Kubernetes (tools/local_experiment.py); "
            "в Killercoda повторить и пересобрать отчёт")
for tag, m in (("OFF", off), ("ON", on)):
    P[f"{tag}_POFOD"] = num(m["POFOD"])
    P[f"{tag}_ROCOF"] = num(m["ROCOF_per_h"], 1)
    P[f"{tag}_AVAIL"] = num(m["AVAIL"])
    P[f"{tag}_P"] = f'{m["p50_ms"]} / {m["p95_ms"]} / {m["p99_ms"]}'
    P[f"{tag}_P99"] = str(m["p99_ms"])
    P[f"{tag}_N"] = str(m["requests"])
    P[f"{tag}_FAILED"] = str(m["failed"])
    P[f"{tag}_PCT"] = pct(m["POFOD"])

c = counters("on")
g = lambda d, kind, res: d.get(f'bulkhead_total{{kind="{kind}",result="{res}"}}', 0)
if c:
    e_ok = g(c, "emergency", "primary") + g(c, "emergency", "backup")
    e_all = e_ok + g(c, "emergency", "rejected")
    P["ON_EMERG"] = f"{e_ok} из {e_all}, из них {g(c, 'emergency', 'backup')} по резервному каналу"
    P["ON_DEFERRED"] = str(g(c, "normal", "deferred"))
    P["ON_COUNTERS"] = "<br>".join(f"<code>{k}</code> = {v}" for k, v in sorted(c.items()))
else:
    P["ON_EMERG"] = "см. счётчики core /metrics"
    P["ON_DEFERRED"] = "часть"
    P["ON_COUNTERS"] = "не сохранены (tools/collect_core_metrics.sh on)"

lim_csv = next((p for p in (os.path.join(ROOT, "results", "on_limit2.csv"), os.path.join(ROOT, "results", "local_on_limit2.csv")) if os.path.exists(p)), None)
lc = counters("on_limit2")
if lim_csv and lc:
    lm = metrics.compute(metrics.read_rows(lim_csv))
    P["LIM_POFOD"] = num(lm["POFOD"])
    P["LIM_REJECTED"] = str(g(lc, "normal", "rejected"))
    ok = g(lc, "emergency", "primary") + g(lc, "emergency", "backup")
    P["LIM_EMERG"] = f"{ok} из {ok + g(lc, 'emergency', 'rejected')}"
else:
    P.update(LIM_POFOD="—", LIM_REJECTED="—", LIM_EMERG="—")

subprocess.run([sys.executable, os.path.join(HERE, "calc", "figures.py"), ROOT], check=True)

html = open(os.path.join(HERE, "report.html"), encoding="utf-8").read()
html = re.sub(r"\{\{(\w+)\}\}", lambda m: str(P.get(m.group(1), m.group(0))), html)
left = re.findall(r"\{\{\w+\}\}", html)
if left:
    print("Не заполнено:", sorted(set(left)))
out_html = os.path.join(HERE, "_build.html")
open(out_html, "w", encoding="utf-8").write(html)

chrome = next((shutil.which(b) for b in ("google-chrome", "chromium", "chromium-browser", "chrome") if shutil.which(b)), None)
if not chrome:
    sys.exit("Нужен Google Chrome / Chromium для печати PDF; HTML лежит в report/_build.html")
pdf = os.path.join(HERE, "report.pdf")
subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                f"--print-to-pdf={pdf}", "file://" + out_html], check=True,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("Готово:", pdf, "| источник цифр:", "Killercoda" if real else "локальная репетиция")
