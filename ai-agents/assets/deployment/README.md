# Deployment configs

Production-ready конфигурации для деплоя AI-агента.

```
deployment/
├── docker-compose.yml    # локальный запуск (агент + vector db + API)
├── Dockerfile             # multi-stage сборка
├── deploy.sh              # canary deploy script
├── k8s/
│   ├── deployment.yaml    # Kubernetes Deployment
│   ├── service.yaml       # Kubernetes Service
│   └── configmap.yaml     # конфигурация
└── README.md             # этот файл
```

## Быстрый старт

```bash
# Локальный запуск
docker compose up -d

# Деплой в Kubernetes
kubectl apply -f k8s/
```

## Переменные окружения

| Переменная | Описание |
|-----------|----------|
| `LLM_API_KEY` | API ключ LLM-провайдера |
| `LLM_MODEL` | Модель по умолчанию |
| `AGENT_NAME` | Имя агента |
| `LOG_LEVEL` | debug / info / warn / error |
| `VECTOR_DB_URL` | URL векторной БД |
| `MAX_TOKENS` | Лимит токенов на сессию |
