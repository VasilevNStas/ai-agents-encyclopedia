# Multi-stage Dockerfile для AI-агента
# Использование: агент как Python-сервис с LLM-запросами

# === Stage 1: build ===
FROM python:3.13-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# === Stage 2: runtime ===
FROM python:3.13-slim AS runtime

WORKDIR /app

# Копируем только нужные пакеты (без кэша pip)
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Копируем код агента
COPY agent/ ./agent/
COPY config/ ./config/

# Non-root пользователь
RUN useradd -m -u 1000 agent && chown -R agent:agent /app
USER agent

ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=info

CMD ["python", "-m", "agent.main"]
