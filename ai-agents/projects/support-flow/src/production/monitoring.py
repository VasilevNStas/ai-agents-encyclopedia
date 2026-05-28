"""Monitoring, observability, metrics and alerting for SupportFlow."""

from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Any, Callable


# ── Metrics ────────────────────────────────────────────────────────


@dataclass
class StepMetrics:
    latency_ms: int = 0
    token_cost: float = 0.0
    success: bool = True
    guardrail_action: str = "allow"
    tool_name: str | None = None
    error: str | None = None


@dataclass
class SessionMetrics:
    session_id: str
    start_time: float
    steps: list[StepMetrics] = field(default_factory=list)
    total_cost: float = 0.0
    total_latency_ms: int = 0
    guardrail_triggers: int = 0
    tool_calls: int = 0
    errors: int = 0
    status: str = "active"

    def add_step(self, step: StepMetrics) -> None:
        self.steps.append(step)
        self.total_cost += step.token_cost
        self.total_latency_ms += step.latency_ms
        if step.guardrail_action != "allow":
            self.guardrail_triggers += 1
        if step.tool_name is not None:
            self.tool_calls += 1
        if step.error is not None:
            self.errors += 1

    def summary(self) -> dict:
        duration = (time.time() - self.start_time) * 1000
        step_count = len(self.steps)
        return {
            "session_id": self.session_id,
            "duration_ms": round(duration, 1),
            "steps": step_count,
            "total_cost": round(self.total_cost, 4),
            "total_latency_ms": self.total_latency_ms,
            "avg_latency_ms": round(self.total_latency_ms / max(step_count, 1), 1),
            "guardrail_triggers": self.guardrail_triggers,
            "tool_calls": self.tool_calls,
            "errors": self.errors,
            "status": self.status,
        }


class MetricsCollector:
    """Collects per-step and per-session metrics for observability.

    Records latency, token cost, success rate, and guardrail triggers.
    Produces JSON-serialisable summaries for dashboards and alerting.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionMetrics] = {}
        self._guardrail_events: list[dict] = []

    def record_step(
        self,
        session_id: str,
        *,
        latency_ms: int = 0,
        token_cost: float = 0.0,
        success: bool = True,
        guardrail_action: str = "allow",
        tool_name: str | None = None,
        error: str | None = None,
    ) -> None:
        """Record a single agent step."""
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionMetrics(
                session_id=session_id,
                start_time=time.time(),
            )

        step = StepMetrics(
            latency_ms=latency_ms,
            token_cost=token_cost,
            success=success,
            guardrail_action=guardrail_action,
            tool_name=tool_name,
            error=error,
        )
        self._sessions[session_id].add_step(step)

    def record_guardrail_trigger(
        self,
        rule: str,
        action: str,
        reason: str,
        session_id: str = "",
    ) -> None:
        """Record a guardrail trigger for alerting and audit."""
        event = {
            "rule": rule,
            "action": action,
            "reason": reason,
            "session_id": session_id,
            "timestamp": time.time(),
        }
        self._guardrail_events.append(event)

    def start_session(self, session_id: str) -> None:
        """Explicitly start a session with tracking."""
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionMetrics(
                session_id=session_id,
                start_time=time.time(),
            )

    def end_session(self, session_id: str, status: str = "completed") -> dict:
        session = self._sessions.get(session_id)
        if session is None:
            return {}
        session.status = status
        return session.summary()

    def session_summary(self, session_id: str) -> dict:
        session = self._sessions.get(session_id)
        return session.summary() if session else {}

    def aggregate_summary(self) -> dict:
        if not self._sessions:
            return {
                "sessions": 0,
                "total_steps": 0,
                "total_cost": 0.0,
                "avg_latency_ms": 0.0,
                "success_rate": 1.0,
                "guardrail_trigger_rate": 0.0,
            }

        all_steps = [step for s in self._sessions.values() for step in s.steps]
        total = len(all_steps)
        succeeded = sum(1 for s in all_steps if s.success)
        guardrail_count = sum(1 for s in all_steps if s.guardrail_action != "allow")
        total_latency = sum(s.latency_ms for s in all_steps)
        total_cost = sum(s.token_cost for s in all_steps)

        return {
            "sessions": len(self._sessions),
            "total_steps": total,
            "total_cost": round(total_cost, 4),
            "avg_latency_ms": round(total_latency / max(total, 1), 1),
            "success_rate": round(succeeded / max(total, 1), 4),
            "guardrail_trigger_rate": round(guardrail_count / max(total, 1), 4),
            "guardrail_triggers_total": guardrail_count,
        }

    def guardrail_events(self, limit: int = 50) -> list[dict]:
        return self._guardrail_events[-limit:]

    def to_json(self) -> str:
        data: dict[str, Any] = {"aggregate": self.aggregate_summary(), "sessions": {}}
        for sid, session in self._sessions.items():
            data["sessions"][sid] = session.summary()
        data["recent_guardrail_events"] = self.guardrail_events(20)
        return json.dumps(data, indent=2, default=str)


# ── Tracing (LangFuse mock) ────────────────────────────────────────

TraceSpan = dict[str, Any]


@dataclass
class TraceSpanData:
    span_id: str
    parent_id: str | None
    span_type: str  # "llm_call" | "tool_call" | "guardrail_check" | "agent_step"
    name: str
    start_time: float
    end_time: float | None = None
    input: Any = None
    output: Any = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "type": self.span_type,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": round((self.end_time or time.time()) - self.start_time, 1),
            "input": self._truncate(self.input),
            "output": self._truncate(self.output),
            "metadata": self.metadata,
        }

    def close(self) -> None:
        self.end_time = time.time()

    @staticmethod
    def _truncate(value: Any, max_len: int = 500) -> Any:
        if isinstance(value, str) and len(value) > max_len:
            return value[:max_len] + "..."
        return value


class LangFuseTracer:
    """Mock LangFuse-compatible tracer for development and testing.

    Records LLM calls, tool invocations, and guardrail checks as a
    structured span tree.  Exportable to JSON for debugging.
    """

    def __init__(self, secret_key: str | None = None, enabled: bool = True) -> None:
        self.secret_key = secret_key
        self.enabled = enabled
        self._traces: dict[str, list[TraceSpanData]] = defaultdict(list)
        self._current_session: str | None = None

    @property
    def is_ready(self) -> bool:
        return self.enabled and self.secret_key is not None

    def start_session(self, session_id: str) -> str:
        self._current_session = session_id
        return session_id

    def trace_llm_call(
        self,
        model: str,
        prompt: str,
        response: str,
        latency_ms: int,
        cost: float,
        session_id: str | None = None,
    ) -> str:
        sid = session_id or self._current_session or "default"
        span = TraceSpanData(
            span_id=uuid.uuid4().hex[:12],
            parent_id=None,
            span_type="llm_call",
            name=f"llm.{model}",
            start_time=time.time(),
            input={"model": model, "prompt_tokens": len(prompt) // 4},
            output={"response_tokens": len(response) // 4, "cost": cost},
            metadata={"latency_ms": latency_ms, "cost": cost, "model": model},
        )
        span.close()
        self._traces[sid].append(span)
        return span.span_id

    def trace_tool_call(
        self,
        tool: str,
        args: dict,
        result: Any,
        latency_ms: int,
        session_id: str | None = None,
    ) -> str:
        sid = session_id or self._current_session or "default"
        span = TraceSpanData(
            span_id=uuid.uuid4().hex[:12],
            parent_id=None,
            span_type="tool_call",
            name=f"tool.{tool}",
            start_time=time.time(),
            input=args,
            output={"result": str(result)[:200]},
            metadata={"latency_ms": latency_ms, "tool": tool},
        )
        span.close()
        self._traces[sid].append(span)
        return span.span_id

    def trace_guardrail_check(
        self,
        check_type: str,
        result: dict,
        session_id: str | None = None,
    ) -> str:
        sid = session_id or self._current_session or "default"
        span = TraceSpanData(
            span_id=uuid.uuid4().hex[:12],
            parent_id=None,
            span_type="guardrail_check",
            name=f"guardrail.{check_type}",
            start_time=time.time(),
            input={"check_type": check_type},
            output=result,
            metadata={"action": result.get("action", "unknown")},
        )
        span.close()
        self._traces[sid].append(span)
        return span.span_id

    def trace_agent_step(
        self,
        step_number: int,
        thought: str,
        action: str | None,
        latency_ms: int,
        session_id: str | None = None,
    ) -> str:
        sid = session_id or self._current_session or "default"
        span = TraceSpanData(
            span_id=uuid.uuid4().hex[:12],
            parent_id=None,
            span_type="agent_step",
            name=f"step.{step_number}",
            start_time=time.time(),
            input={"thought": thought[:200]},
            output={"action": action},
            metadata={"step_number": step_number, "latency_ms": latency_ms},
        )
        span.close()
        self._traces[sid].append(span)
        return span.span_id

    def get_trace(self, session_id: str) -> list[dict]:
        spans = self._traces.get(session_id, [])
        return [s.to_dict() for s in spans]

    def export(self, session_id: str | None = None) -> dict:
        if session_id:
            return {
                "session_id": session_id,
                "spans": self.get_trace(session_id),
            }
        return {
            "sessions": {
                sid: [s.to_dict() for s in spans] for sid, spans in self._traces.items()
            }
        }

    def export_json(self, session_id: str | None = None, indent: int = 2) -> str:
        return json.dumps(self.export(session_id), indent=indent, default=str)


# ── Alerting ───────────────────────────────────────────────────────

AlertAction = Callable[[dict], None]


@dataclass
class AlertRule:
    name: str
    metric: str
    operator: str  # "gt" | "gte" | "lt" | "lte" | "eq"
    threshold: float
    severity: str = "warning"
    description: str = ""
    enabled: bool = True

    def evaluate(self, current_value: float) -> bool:
        if not self.enabled:
            return False
        if self.operator == "gt":
            return current_value > self.threshold
        if self.operator == "gte":
            return current_value >= self.threshold
        if self.operator == "lt":
            return current_value < self.threshold
        if self.operator == "lte":
            return current_value <= self.threshold
        if self.operator == "eq":
            return abs(current_value - self.threshold) < 1e-9
        return False


@dataclass
class Alert:
    rule_name: str
    metric: str
    value: float
    threshold: float
    severity: str
    message: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


class AlertManager:
    """Threshold-based alerting for system metrics.

    Supports custom rules, severity levels, and pluggable notification
    callbacks (e.g. Slack, email, PagerDuty).
    """

    def __init__(self) -> None:
        self._rules: list[AlertRule] = []
        self._alerts: list[Alert] = []
        self._notification_hooks: list[AlertAction] = []

    def add_rule(self, rule: AlertRule) -> None:
        self._rules.append(rule)

    def add_notification_hook(self, hook: AlertAction) -> None:
        """Register a callback invoked for each new alert."""
        self._notification_hooks.append(hook)

    def evaluate(self, metrics: dict) -> list[Alert]:
        """Run all enabled rules against a flat metrics dictionary."""
        new_alerts: list[Alert] = []
        for rule in self._rules:
            value = self._resolve_metric(metrics, rule.metric)
            if value is None:
                continue
            if rule.evaluate(value):
                alert = Alert(
                    rule_name=rule.name,
                    metric=rule.metric,
                    value=value,
                    threshold=rule.threshold,
                    severity=rule.severity,
                    message=(
                        f"[{rule.severity.upper()}] {rule.name}: "
                        f"{rule.metric} is {value} (threshold: {rule.threshold})"
                    ),
                )
                self._alerts.append(alert)
                new_alerts.append(alert)
                for hook in self._notification_hooks:
                    hook(alert.to_dict())
        return new_alerts

    def recent_alerts(self, n: int = 10) -> list[Alert]:
        return self._alerts[-n:]

    def recent_alert_dicts(self, n: int = 10) -> list[dict]:
        return [a.to_dict() for a in self._alerts[-n:]]

    def clear(self) -> None:
        self._alerts.clear()

    @staticmethod
    def _resolve_metric(metrics: dict, path: str) -> float | None:
        """Resolve a dot-separated metric path (e.g. 'aggregate.avg_latency_ms')."""
        parts = path.split(".")
        current: Any = metrics
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return float(current) if current is not None else None


# ── Dashboard ──────────────────────────────────────────────────────


class MonitorDashboard:
    """Text-based monitoring dashboard rendered to stdout.

    Combines metrics from MetricsCollector with recent alerts from
    AlertManager into a human-readable summary.
    """

    SEPARATOR = "=" * 64

    def __init__(
        self,
        metrics_collector: MetricsCollector,
        alert_manager: AlertManager,
    ) -> None:
        self.metrics = metrics_collector
        self.alerts = alert_manager

    def render(self) -> str:
        lines: list[str] = []
        lines.append(self.SEPARATOR)
        lines.append("  SUPPORTFLOW — PRODUCTION DASHBOARD")
        lines.append(self.SEPARATOR)
        lines.append("")
        lines.append(self._render_metrics())
        lines.append("")
        lines.append(self._render_alerts())
        lines.append(self.SEPARATOR)
        return "\n".join(lines)

    def _render_metrics(self) -> str:
        agg = self.metrics.aggregate_summary()
        lines = ["  ── Aggregate Metrics ──", ""]
        lines.append(f"    Sessions:            {agg['sessions']}")
        lines.append(f"    Total steps:         {agg['total_steps']}")
        lines.append(f"    Total cost:          ${agg['total_cost']:.4f}")
        lines.append(f"    Avg latency:         {agg['avg_latency_ms']} ms")
        lines.append(f"    Success rate:        {agg['success_rate'] * 100:.1f}%")
        lines.append(
            f"    Guardrail triggers:  {agg['guardrail_triggers_total']} "
            f"({agg['guardrail_trigger_rate'] * 100:.1f}%)"
        )
        return "\n".join(lines)

    def _render_alerts(self) -> str:
        recent = self.alerts.recent_alerts(5)
        if not recent:
            return "  ── Alerts ──\n\n    (no recent alerts)\n"

        lines = ["  ── Alerts (last 5) ──", ""]
        for alert in recent:
            lines.append(f"    [{alert.severity.upper():>7}] {alert.message}")
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps(
            {
                "metrics": self.metrics.aggregate_summary(),
                "alerts": self.alerts.recent_alert_dicts(10),
                "guardrail_events": self.metrics.guardrail_events(20),
            },
            indent=2,
            default=str,
        )
