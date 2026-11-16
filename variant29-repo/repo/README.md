# Вариант 29 — Автономные самосвалы на карьере

Экзаменационный проект «Software Resilience and Risk Assessment».
Паттерн: **Bulkhead + приоритет аварийных команд**. Отказ: `dep-a` с задержкой 3000 мс. R = 4.

## Быстрая проверка (без кластера)
```bash
python -m unittest -v              # 14 тестов: паттерн (test_core.py) и metrics.py
python3 metrics.py results/sample20.csv   # 0,30 / 360 / 0,70 — контрольный пример
```

## Эксперимент в Killercoda (Kubernetes Playground)
```bash
git clone <URL этого репозитория> && cd <папка>
kubectl create configmap code --from-file=dep.py --from-file=core.py --from-file=loadgen.py
kubectl apply -f stand.yaml
kubectl get pods                          # все Running, READY 1/1 (dep-a/b/c + 4 app)
chmod +x experiment.sh tools/collect_core_metrics.sh
export FAULT='{"delay_ms": 3000}'         # отказ варианта 29
./experiment.sh off 2>&1 | tee results/off.log
./experiment.sh on  2>&1 | tee results/on.log
./tools/collect_core_metrics.sh on        # счётчики отсеков -> results/on_core_metrics.txt
git add results && git commit -m "Killercoda: прогоны off/on" && git push
```
Дополнительно (проверка изоляции отсеков): `kubectl set env deployment/app NORMAL_LIMIT=2`,
затем `./experiment.sh on`, `cp results/on.csv results/on_limit2.csv`,
`./tools/collect_core_metrics.sh on_limit2`; верните `NORMAL_LIMIT=8` и повторите обычный прогон `on`.

## Пороги паттерна (переменные окружения в stand.yaml)
| Переменная | По умолчанию | Смысл |
|---|---|---|
| `NORMAL_LIMIT` | 8 | одновременных обычных вызовов dep на реплику; лишние — сразу отказ |
| `EMERGENCY_LIMIT` | 4 | отдельный отсек аварийных команд |
| `NORMAL_TIMEOUT_S` | 0.8 | ожидание dep для обычного запроса, затем ответ `deferred` |
| `EMERGENCY_TIMEOUT_S` | 0.5 | ожидание dep-a и затем dep-b для аварийной команды |
| `EMERGENCY_EVERY` | 10 | каждый N-й запрос считается аварийной командой |

## Отчёт
`report/build.py` подставляет данные пары и цифры из `results/off.csv` / `results/on.csv`
(если их нет — из локальной репетиции `results/local_*.csv`) и печатает `report/report.pdf`:
```bash
python3 report/build.py
```
Локальная репетиция без Kubernetes: `python3 tools/local_experiment.py off|on`.
