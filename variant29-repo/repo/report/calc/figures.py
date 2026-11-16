import csv, json, math, os, random, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
ROOT = sys.argv[1]; FIG = os.path.join(ROOT, "report", "fig")
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#9a9a92", "axes.labelcolor": "#3d3d3a",
                     "xtick.color": "#5f5e5a", "ytick.color": "#5f5e5a", "axes.grid": True,
                     "grid.color": "#e6e5e0", "grid.linewidth": 0.6})
BLUE, ORANGE, INK = "#2a78d6", "#eb6834", "#2b2b29"

# --- 1. Эксперимент: доля неудачных и p95 по секундам ---
def per_second(path):
    rows = []
    for r in csv.reader(open(path)):
        try: rows.append((float(r[0]), int(r[1]), int(r[2])))
        except (ValueError, IndexError): pass
    t0 = min(r[0] for r in rows); b = {}
    for ts, c, ms in rows: b.setdefault(int(ts - t0), []).append((c, ms))
    secs = sorted(b); fail = [sum(c != 200 for c, _ in b[s]) / len(b[s]) * 100 for s in secs]
    p95 = []
    for s in secs:
        l = sorted(ms for _, ms in b[s]); p95.append(l[max(1, math.ceil(.95 * len(l))) - 1])
    return secs, fail, p95
pick = lambda m: os.path.join(ROOT, "results", f"{m}.csv") if os.path.exists(os.path.join(ROOT, "results", f"{m}.csv")) else os.path.join(ROOT, "results", f"local_{m}.csv")
off = per_second(pick("off")); on = per_second(pick("on"))
fig, ax = plt.subplots(2, 1, figsize=(7.2, 4.6), sharex=True)
for a in ax: a.axvspan(30, 60, color="#f3f2ee", zorder=0); a.text(45, 0, "", ha="center")
ax[0].plot(off[0], off[1], color=BLUE, lw=2, label="PATTERN=off"); ax[0].plot(on[0], on[1], color=ORANGE, lw=2, label="PATTERN=on")
ax[0].set_ylabel("Неудачных запросов, %"); ax[0].set_ylim(-5, 105)
ax[0].text(45, 50, "отказ dep-a:\nзадержка 3000 мс", ha="center", color="#5f5e5a", fontsize=8)
ax[1].plot(off[0], off[2], color=BLUE, lw=2, label="PATTERN=off"); ax[1].plot(on[0], on[2], color=ORANGE, lw=2, label="PATTERN=on")
ax[1].axhline(1500, color="#9a9a92", lw=1, ls="--"); ax[1].text(2, 1560, "пользователь ждёт не дольше 1,5 с", va="bottom", fontsize=7.5, color="#5f5e5a"); ax[1].set_ylim(-50, 1800)
ax[1].set_ylabel("p95 задержки, мс"); ax[1].set_xlabel("Время прогона, с")
ax[0].legend(loc="upper right", frameon=False, fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_experiment.png"), dpi=200); plt.close(fig)

# --- 2. Матрица рисков 5×5 ---
risks = {"R1": (4, 5), "R2": (3, 5), "R3": (3, 4), "R4": (2, 5), "R5": (2, 5), "R6": (3, 3), "R7": (2, 3), "R8": (2, 4)}
fig, ax = plt.subplots(figsize=(5.6, 4.6)); ax.grid(False)
for v in range(1, 6):
    for i in range(1, 6):
        s = v * i; col = "#f6c9c9" if s >= 15 else ("#fde3b0" if s >= 8 else "#d6eed6")
        ax.add_patch(plt.Rectangle((i - .5, v - .5), 1, 1, facecolor=col, edgecolor="white", lw=2))
        ax.text(i + .38, v - .38, str(s), ha="right", va="bottom", fontsize=7, color="#5f5e5a")
cells = {}
for k, (v, i) in risks.items(): cells.setdefault((v, i), []).append(k)
for (v, i), ks in cells.items():
    ax.text(i, v + .05, "\n".join(ks), ha="center", va="center", fontsize=10, fontweight="bold", color=INK)
ax.set_xlim(.5, 5.5); ax.set_ylim(.5, 5.5); ax.set_xticks(range(1, 6)); ax.set_yticks(range(1, 6))
ax.set_xlabel("Воздействие →"); ax.set_ylabel("Вероятность →")
for sp in ax.spines.values(): sp.set_visible(False)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color="#f6c9c9", label="15–25 критический"), Patch(color="#fde3b0", label="8–14 высокий/средний"),
                   Patch(color="#d6eed6", label="1–7 низкий")], loc="upper center", bbox_to_anchor=(.5, -.13), ncol=3, frameon=False, fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_matrix.png"), dpi=200); plt.close(fig)

# --- 3. Монте-Карло: распределение годовых потерь ---
def pert_sample(mn, ml, mx, rnd):
    a = 1 + 4 * (ml - mn) / (mx - mn); b = 1 + 4 * (mx - ml) / (mx - mn)
    return mn + rnd.betavariate(a, b) * (mx - mn)
def poisson(lam, rnd):
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rnd.random()
        if p <= L: return k
        k += 1
rnd = random.Random(29); bef, aft = [], []
for _ in range(20000):
    n = poisson(pert_sample(3, 6, 9, rnd), rnd)
    bef.append(sum(pert_sample(2, 5, 49, rnd) for _ in range(n))); aft.append(sum(pert_sample(.3, .6, 6.3, rnd) for _ in range(n)))
fig, ax = plt.subplots(2, 1, figsize=(7.2, 3.8), sharex=True)
bins = [i * 5 for i in range(0, 50)]
ax[0].hist(bef, bins=bins, color=BLUE, edgecolor="white", linewidth=1); ax[0].set_title("До мер: среднее 71,2 млн ₸/год, P90 120,9", fontsize=9, loc="left")
ax[1].hist(aft, bins=bins, color=ORANGE, edgecolor="white", linewidth=1); ax[1].set_title("После мер: среднее 9,0 млн ₸/год, P90 15,3", fontsize=9, loc="left")
for a in ax: a.set_ylabel("Лет из 20 000")
ax[1].set_xlabel("Годовые потери, млн ₸"); ax[1].set_xlim(0, 245)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_mc.png"), dpi=200); plt.close(fig)
print("ok")
