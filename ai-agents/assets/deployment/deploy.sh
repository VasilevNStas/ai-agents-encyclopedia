#!/bin/bash
# Canary deploy script for AI agent
set -euo pipefail

NAMESPACE="${NAMESPACE:-default}"
DEPLOYMENT="${DEPLOYMENT:-ai-agent}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
CANARY_PERCENT="${CANARY_PERCENT:-20}"
ROLLBACK_WAIT="${ROLLBACK_WAIT:-120}"

echo "=== Deploying AI Agent ==="
echo "Namespace: $NAMESPACE"
echo "Image tag: $IMAGE_TAG"
echo "Canary percent: $CANARY_PERCENT%"

# 1. Билд и пуш
echo "--- Building image ---"
docker build -t "registry.example.com/ai-agent:${IMAGE_TAG}" .
docker push "registry.example.com/ai-agent:${IMAGE_TAG}"

# 2. Canary deploy
echo "--- Deploying canary (${CANARY_PERCENT}%) ---"
kubectl set image "deployment/${DEPLOYMENT}-canary" \
  "agent=registry.example.com/ai-agent:${IMAGE_TAG}" \
  -n "$NAMESPACE"

kubectl scale "deployment/${DEPLOYMENT}-canary" --replicas=1 -n "$NAMESPACE"

# 3. Ожидание и проверка
echo "--- Waiting ${ROLLBACK_WAIT}s for canary health ---"
sleep "$ROLLBACK_WAIT"

if ! kubectl rollout status "deployment/${DEPLOYMENT}-canary" \
  -n "$NAMESPACE" --timeout=60s; then
  echo "❌ Canary failed! Rolling back..."
  kubectl rollout undo "deployment/${DEPLOYMENT}-canary" -n "$NAMESPACE"
  exit 1
fi

# 4. Проверка метрик
echo "--- Checking canary metrics ---"
CANARY_ERRORS=$(curl -s "http://localhost:9090/api/v1/query?query=rate(agent_errors_total[5m])" \
  | jq -r '.data.result[0].value[1]' || echo "0")

if (( $(echo "$CANARY_ERRORS > 0.01" | bc -l) )); then
  echo "❌ Error rate too high (${CANARY_ERRORS}). Rolling back..."
  kubectl rollout undo "deployment/${DEPLOYMENT}-canary" -n "$NAMESPACE"
  exit 1
fi

echo "✅ Canary healthy"

# 5. Полный rollout
echo "--- Full rollout ---"
kubectl set image "deployment/${DEPLOYMENT}" \
  "agent=registry.example.com/ai-agent:${IMAGE_TAG}" \
  -n "$NAMESPACE"

kubectl rollout status "deployment/${DEPLOYMENT}" \
  -n "$NAMESPACE" --timeout=120s

# 6. Отключаем canary
kubectl scale "deployment/${DEPLOYMENT}-canary" --replicas=0 -n "$NAMESPACE"

echo "=== Deploy complete ==="
