#!/usr/bin/env python3
"""
OpenTelemetry integration for AI agent monitoring.
Tracks LLM calls, tool usage, latency, and cost.
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.openai import OpenAIInstrumentor

import logging

logger = logging.getLogger(__name__)


def setup_telemetry(
    endpoint: str = "http://localhost:4317", service_name: str = "ai-agent"
):
    """Initialize OpenTelemetry tracing."""

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": service_name,
                "service.version": "1.0.0",
                "deployment.environment": "production",
            }
        )
    )

    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Auto-instrument OpenAI calls
    OpenAIInstrumentor().instrument()

    logger.info(f"Telemetry initialized: {endpoint}")


def trace_agent_step(
    agent_name: str, step: str, tokens: int, cost: float, latency_ms: float
):
    """Record a single agent step with custom attributes."""

    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("agent.step") as span:
        span.set_attribute("agent.name", agent_name)
        span.set_attribute("agent.step", step)
        span.set_attribute("llm.tokens", tokens)
        span.set_attribute("llm.cost_usd", cost)
        span.set_attribute("llm.latency_ms", latency_ms)


def trace_tool_call(tool_name: str, args: dict, result: str, duration_ms: float):
    """Trace a tool execution."""

    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("tool.call") as span:
        span.set_attribute("tool.name", tool_name)
        span.set_attribute("tool.args", str(args)[:500])
        span.set_attribute("tool.duration_ms", duration_ms)


def trace_guardrail(guard_type: str, action: str, reason: str):
    """Trace guardrail check."""

    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("guardrail.check") as span:
        span.set_attribute("guardrail.type", guard_type)
        span.set_attribute("guardrail.action", action)
        span.set_attribute("guardrail.reason", reason)
