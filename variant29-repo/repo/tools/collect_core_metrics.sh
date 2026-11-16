#!/bin/sh
# Сразу после ./experiment.sh on: суммирует счётчики /metrics всех реплик core.
# Запуск:  ./tools/collect_core_metrics.sh on   -> results/on_core_metrics.txt
MODE=${1:-on}
mkdir -p results
for p in $(kubectl get pods -l app=app -o name); do
  kubectl exec "$p" -- wget -qO- localhost:8080/metrics
done | awk '{s[$1]+=$2} END {for (k in s) print k, s[k]}' | sort > results/${MODE}_core_metrics.txt
cat results/${MODE}_core_metrics.txt
