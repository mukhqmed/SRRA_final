"""Расчёты заданий 4, 5, 6 для варианта 29 (только стандартная библиотека)."""
import json, math, random

H = 8760
# Задание 4
A = 1720 / (1720 + 4); B = 4100 / (4100 + 1); C = 0.999
sys_ = A * B * C
A2 = 1 - (1 - A) ** 2; B2 = 1 - (1 - B) ** 2
sys2 = A2 * B2 * C
r = {"A": A, "B": B, "C": C, "sys": sys_, "down_sys_h": (1 - sys_) * H,
     "down_A_h": (1 - A) * H, "down_B_h": (1 - B) * H, "down_C_h": (1 - C) * H,
     "A2": A2, "B2": B2, "sys2": sys2, "down_sys2_h": (1 - sys2) * H,
     "AB": A * B, "AB2": A2 * B2}
# Задание 5: FAIR
pert = lambda mn, ml, mx: (mn + 4 * ml + mx) / 6
LEF = pert(3, 6, 9); LM = pert(2, 5, 49); LM2 = pert(0.3, 0.6, 6.3); cost = 39
ALE = LEF * LM; ALE2 = LEF * LM2; ROSI = (ALE - ALE2 - cost) / cost
r.update(LEF=LEF, LM=LM, LM2=LM2, ALE=ALE, ALE2=ALE2, ROSI=ROSI)

# Монте-Карло: PERT-бета, LEF — Пуассон с интенсивностью из PERT
def pert_sample(mn, ml, mx, rnd):
    a = 1 + 4 * (ml - mn) / (mx - mn); b = 1 + 4 * (mx - ml) / (mx - mn)
    return mn + rnd.betavariate(a, b) * (mx - mn)

def poisson(lam, rnd):
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rnd.random()
        if p <= L: return k
        k += 1

rnd = random.Random(29); N = 20000
before, after = [], []
for _ in range(N):
    n = poisson(pert_sample(3, 6, 9, rnd), rnd)
    lb = sum(pert_sample(2, 5, 49, rnd) for _ in range(n))
    la = sum(pert_sample(0.3, 0.6, 6.3, rnd) for _ in range(n))
    before.append(lb); after.append(la)
q = lambda xs, p: sorted(xs)[int(p * (len(xs) - 1))]
r["mc"] = {"mean_before": sum(before) / N, "p50_before": q(before, .5), "p90_before": q(before, .9), "p95_before": q(before, .95),
           "mean_after": sum(after) / N, "p50_after": q(after, .5), "p90_after": q(after, .9), "p95_after": q(after, .95),
           "p_rosi_neg": sum(1 for b, a in zip(before, after) if b - a < cost) / N}
# Задание 6: выданные данные испытаний
r.update(POFOD=8 / 16000, ROCOF=6 / 720, AVAIL=(720 - 5.4) / 720, MTBF_obs=(720 - 5.4) / 6, MTTR_obs=5.4 / 6)
print(json.dumps(r, indent=1, ensure_ascii=False))
json.dump(r, open(__file__.replace("calculations.py", "results.json"), "w"), indent=1)
