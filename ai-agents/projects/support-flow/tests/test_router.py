"""Tests for the model router and cost tracking."""

import pytest
import sys
from pathlib import Path

_cost_dir = Path(__file__).resolve().parent.parent / "05-cost"
if str(_cost_dir) not in sys.path:
    sys.path.insert(0, str(_cost_dir))

from model_router import ModelRouter, MODEL_COSTS, BASELINE_MODEL


class TestSimpleVsComplexClassification:
    def test_greeting_is_simple(self):
        router = ModelRouter()
        assert router.is_simple_query("Hello, how are you?") is True

    def test_thanks_is_simple(self):
        router = ModelRouter()
        assert router.is_simple_query("Thank you for your help") is True

    def test_short_queries_are_simple(self):
        router = ModelRouter()
        assert router.is_simple_query("Yes") is True
        assert router.is_simple_query("Ok") is True
        assert router.is_simple_query("No") is True

    def test_password_reset_is_simple(self):
        router = ModelRouter()
        assert router.is_simple_query("password reset") is True

    def test_complex_technical_question(self):
        router = ModelRouter()
        query = "Why does my application crash when I deploy and how do I fix it?"
        assert router.is_complex_query(query) is True

    def test_comparison_is_complex(self):
        router = ModelRouter()
        assert router.is_complex_query("Compare Sonnet and Haiku models") is True

    def test_long_queries_are_complex(self):
        router = ModelRouter()
        long = " ".join(["word"] * 300)
        assert router.is_complex_query(long) is True

    def test_simple_query_not_complex(self):
        router = ModelRouter()
        assert router.is_complex_query("Hi") is False

    def test_complex_query_not_simple(self):
        router = ModelRouter()
        q = "Analyze the deployment pipeline and explain why it failed"
        assert router.is_complex_query(q) is True
        assert router.is_simple_query(q) is False


class TestRoutingDecisions:
    def test_routes_greeting_to_haiku(self):
        router = ModelRouter()
        model = router.route("Hello")
        assert model == "claude-haiku-4.6"

    def test_routes_complex_to_sonnet(self):
        router = ModelRouter()
        model = router.route("Why does the system fail under high load?")
        assert model == "claude-sonnet-4.6"

    def test_routes_escalated_to_opus(self):
        router = ModelRouter()
        model = router.route("I'm angry", {"sentiment": "angry"})
        assert model == "claude-opus-4.7"

    def test_routes_high_priority_to_opus(self):
        router = ModelRouter()
        model = router.route("Critical system down", {"priority": "critical"})
        assert model == "claude-opus-4.7"

    def test_route_respects_escalated_flag(self):
        router = ModelRouter()
        model = router.route("simple", {"escalated": True})
        assert model == "claude-opus-4.7"

    def test_unknown_pattern_falls_to_sonnet(self):
        router = ModelRouter()
        model = router.route("xylophone zebra quantum")
        assert model == "claude-sonnet-4.6"


class TestCostTrackingAccuracy:
    def test_estimate_cost_returns_float(self):
        router = ModelRouter()
        cost = router.estimate_cost("Hello")
        assert isinstance(cost, float)
        assert cost > 0

    def test_haiku_cheaper_than_sonnet(self):
        router = ModelRouter()
        haiku_cost = router._estimate_call_cost("claude-haiku-4.6")
        sonnet_cost = router._estimate_call_cost("claude-sonnet-4.6")
        assert haiku_cost < sonnet_cost

    def test_sonnet_cheaper_than_opus(self):
        router = ModelRouter()
        sonnet_cost = router._estimate_call_cost("claude-sonnet-4.6")
        opus_cost = router._estimate_call_cost("claude-opus-4.7")
        assert sonnet_cost < opus_cost

    def test_tracks_total_queries(self):
        router = ModelRouter()
        router.route("Hello")
        router.route("Why does it fail?")
        router.route("Hi there")
        assert router.stats.total_queries == 3

    def test_counts_by_model(self):
        router = ModelRouter()
        router.route("Hello")
        router.route("Hi")
        router.route("Complex analysis please")
        assert router.stats.haiku_count == 2
        assert router.stats.sonnet_count == 1

    def test_shows_savings(self):
        router = ModelRouter()
        router.route("Hello")
        router.route("Analyze and compare")
        assert router.stats.savings > 0
        assert router.stats.savings_pct > 0

    def test_route_tracking_matches_stats(self):
        router = ModelRouter()
        models = [
            router.route("Hi"),
            router.route("Explain deployment"),
            router.route("I'm angry", {"sentiment": "angry"}),
        ]
        assert models == [
            "claude-haiku-4.6",
            "claude-sonnet-4.6",
            "claude-opus-4.7",
        ]
        assert router.stats.haiku_count == 1
        assert router.stats.sonnet_count == 1
        assert router.stats.opus_count == 1

    def test_savings_vs_baseline(self):
        router = ModelRouter()
        router.route("hello")
        router.route("complex problem analysis needed")
        baseline = 2 * router._estimate_call_cost(BASELINE_MODEL)
        assert router.stats.baseline_cost == pytest.approx(baseline)

    def test_empty_context_defaults(self):
        router = ModelRouter()
        model = router.route("hello", None)
        assert model == "claude-haiku-4.6"


class TestCostTracker:
    def test_records_and_returns_alert(self):
        from budget import CostTracker

        ct = CostTracker(daily_user_limit=0.10)
        alert = ct.record("user_1", "team_a", "claude-sonnet-4.6", 0.09)
        assert alert is not None
        assert alert.level == "warning"

    def test_can_proceed_within_budget(self):
        from budget import CostTracker

        ct = CostTracker(daily_user_limit=5.0)
        assert ct.can_proceed("user_1", "team_a", 0.50) is True

    def test_cannot_proceed_over_budget(self):
        from budget import CostTracker

        ct = CostTracker(daily_user_limit=1.0)
        assert ct.can_proceed("user_1", "team_a", 1.50) is False

    def test_user_summary(self):
        from budget import CostTracker

        ct = CostTracker()
        ct.record("user_1", "team_a", "claude-haiku-4.6", 0.01)
        summary = ct.user_summary("user_1")
        assert summary["user_id"] == "user_1"
        assert summary["call_count"] == 1
        assert summary["total"] > 0

    def test_team_summary(self):
        from budget import CostTracker

        ct = CostTracker()
        ct.record("user_1", "team_a", "claude-haiku-4.6", 0.01)
        ct.record("user_2", "team_a", "claude-sonnet-4.6", 0.02)
        summary = ct.team_summary("team_a")
        assert summary["team_id"] == "team_a"
        assert summary["active_users"] == 2
        assert summary["call_count"] == 2
