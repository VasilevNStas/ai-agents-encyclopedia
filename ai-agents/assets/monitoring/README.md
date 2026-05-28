# Monitoring stack for AI agents

```
monitoring/
├── openlit-integration.py   # OpenTelemetry + LLM observability
├── langsmith-example.py     # LangSmith tracing example
├── prometheus.yml           # Prometheus config
├── alerts.yml               # Alerting rules
└── dashboard.json           # Grafana dashboard (LLM metrics)
```

## Quick start

```bash
# Start monitoring stack
docker compose -f ../deployment/docker-compose.yml -f monitoring/docker-compose.yml up -d

# Or standalone Prometheus + Grafana:
prometheus --config.file=monitoring/prometheus.yml
```

## Metrics collected

| Metric | Type | Description |
|--------|------|-------------|
| `llm_requests_total` | Counter | Total LLM requests |
| `llm_latency_seconds` | Histogram | Request latency |
| `llm_tokens_total` | Counter | Total tokens used |
| `llm_cost_total` | Counter | Total cost in USD |
| `agent_errors_total` | Counter | Agent errors by type |
| `agent_tool_calls_total` | Counter | Tool calls by tool name |
| `agent_guardrail_blocks_total` | Counter | Guardrail blocks by type |
