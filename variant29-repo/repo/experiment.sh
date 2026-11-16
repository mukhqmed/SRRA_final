#!/bin/sh
# Запуск:  ./experiment.sh off   и затем   ./experiment.sh on
# Один прогон = 2 минуты нагрузки: 0–30 с норма, 30–60 с отказ dep-a, 60–120 с восстановление.
set -e
MODE=$1
FAULT=${FAULT:-'{"delay_ms": 2000}'}                       # отказ из своего варианта
OK='{"delay_ms": 0, "error_rate": 0, "down": false}'
mkdir -p results

# 1. Свежий код в кластер и режим PATTERN
kubectl create configmap code --from-file=dep.py --from-file=core.py --from-file=loadgen.py \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl set env deployment/app PATTERN=$MODE
kubectl rollout restart deployment/app
kubectl rollout status deployment/app

# 2. Нагрузка
kubectl delete job load --ignore-not-found
kubectl apply -f load-job.yaml
kubectl wait --for=condition=ready pod -l job-name=load --timeout=120s
echo "0 с: нагрузка пошла"; sleep 30

# 3. Отказ и восстановление
kubectl exec deploy/dep-a -- wget -qO- --post-data="$FAULT" localhost:8080/fault; echo " <- 30 с: отказ включён"
sleep 30
kubectl exec deploy/dep-a -- wget -qO- --post-data="$OK" localhost:8080/fault; echo " <- 60 с: отказ снят"

# 4. Результат
kubectl wait --for=condition=complete job/load --timeout=200s
kubectl logs job/load > results/$MODE.csv
python3 metrics.py results/$MODE.csv
