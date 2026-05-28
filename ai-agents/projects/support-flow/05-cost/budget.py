"""Extended budget management — per-user, per-team cost tracking with alerts."""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional


@dataclass
class CostEntry:
    """A single tracked cost event."""

    user_id: str
    team_id: str
    model: str
    cost: float
    timestamp: float = field(default_factory=time.time)
    query_preview: str = ""

    @property
    def day_key(self) -> str:
        return datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d")

    @property
    def month_key(self) -> str:
        return datetime.fromtimestamp(self.timestamp).strftime("%Y-%m")


@dataclass
class BudgetAlert:
    """Alert raised when a budget threshold is crossed."""

    user_id: str
    team_id: str
    current_spend: float
    threshold: float
    level: str  # "warning" | "critical"
    timestamp: float = field(default_factory=time.time)
    acknowledged: bool = False


class CostTracker:
    """Multi-dimensional cost tracking with per-user and per-team aggregation.

    Integrates with ModelRouter to estimate costs before routing decisions.
    """

    def __init__(
        self,
        daily_user_limit: float = 5.0,
        monthly_user_limit: float = 100.0,
        daily_team_limit: float = 50.0,
        monthly_team_limit: float = 1000.0,
        warn_threshold_pct: float = 0.8,
        crit_threshold_pct: float = 0.95,
    ):
        self.daily_user_limit = daily_user_limit
        self.monthly_user_limit = monthly_user_limit
        self.daily_team_limit = daily_team_limit
        self.monthly_team_limit = monthly_team_limit
        self.warn_threshold_pct = warn_threshold_pct
        self.crit_threshold_pct = crit_threshold_pct

        self._entries: list[CostEntry] = []
        self._alerts: list[BudgetAlert] = []

    def record(
        self,
        user_id: str,
        team_id: str,
        model: str,
        cost: float,
        query_preview: str = "",
    ) -> Optional[BudgetAlert]:
        entry = CostEntry(
            user_id=user_id,
            team_id=team_id,
            model=model,
            cost=cost,
            query_preview=query_preview[:80],
        )
        self._entries.append(entry)
        return self._check_thresholds(entry)

    def _check_thresholds(self, entry: CostEntry) -> Optional[BudgetAlert]:
        user_daily = self.user_cost(entry.user_id, "daily")
        user_monthly = self.user_cost(entry.user_id, "monthly")
        team_daily = self.team_cost(entry.team_id, "daily")
        team_monthly = self.team_cost(entry.team_id, "monthly")

        thresholds: list[tuple[float, float, str]] = [
            (user_daily, self.daily_user_limit, f"user:{entry.user_id}/daily"),
            (user_monthly, self.monthly_user_limit, f"user:{entry.user_id}/monthly"),
            (team_daily, self.daily_team_limit, f"team:{entry.team_id}/daily"),
            (team_monthly, self.monthly_team_limit, f"team:{entry.team_id}/monthly"),
        ]

        for current, limit, label in thresholds:
            if limit <= 0:
                continue
            ratio = current / limit
            if ratio >= self.crit_threshold_pct:
                alert = BudgetAlert(
                    user_id=entry.user_id,
                    team_id=entry.team_id,
                    current_spend=round(current, 4),
                    threshold=limit,
                    level="critical",
                )
                self._alerts.append(alert)
                return alert
            if ratio >= self.warn_threshold_pct:
                alert = BudgetAlert(
                    user_id=entry.user_id,
                    team_id=entry.team_id,
                    current_spend=round(current, 4),
                    threshold=limit,
                    level="warning",
                )
                self._alerts.append(alert)
                return alert

        return None

    def can_proceed(self, user_id: str, team_id: str, estimated_cost: float) -> bool:
        user_daily = self.user_cost(user_id, "daily") + estimated_cost
        user_monthly = self.user_cost(user_id, "monthly") + estimated_cost
        team_daily = self.team_cost(team_id, "daily") + estimated_cost
        team_monthly = self.team_cost(team_id, "monthly") + estimated_cost

        if user_daily > self.daily_user_limit:
            return False
        if user_monthly > self.monthly_user_limit:
            return False
        if team_daily > self.daily_team_limit:
            return False
        if team_monthly > self.monthly_team_limit:
            return False
        return True

    def user_cost(self, user_id: str, period: str = "all") -> float:
        return self._aggregate(lambda e: e.user_id == user_id, period)

    def team_cost(self, team_id: str, period: str = "all") -> float:
        return self._aggregate(lambda e: e.team_id == team_id, period)

    def user_summary(self, user_id: str) -> dict:
        return {
            "user_id": user_id,
            "daily": round(self.user_cost(user_id, "daily"), 4),
            "monthly": round(self.user_cost(user_id, "monthly"), 4),
            "total": round(self.user_cost(user_id, "all"), 4),
            "call_count": sum(1 for e in self._entries if e.user_id == user_id),
        }

    def team_summary(self, team_id: str) -> dict:
        entries = [e for e in self._entries if e.team_id == team_id]
        users = set(e.user_id for e in entries)
        return {
            "team_id": team_id,
            "daily": round(self.team_cost(team_id, "daily"), 4),
            "monthly": round(self.team_cost(team_id, "monthly"), 4),
            "total": round(self.team_cost(team_id, "all"), 4),
            "active_users": len(users),
            "call_count": len(entries),
        }

    def report(self, period: str = "daily") -> str:
        today = date.today()
        if period == "daily":
            key = today.isoformat()
        elif period == "weekly":
            key = (today - timedelta(days=today.weekday())).isoformat()
        elif period == "monthly":
            key = today.strftime("%Y-%m")
        else:
            key = "all"

        entries = self._entries_for_period(period)

        users = set(e.user_id for e in entries)
        teams = set(e.team_id for e in entries)
        total_cost = round(sum(e.cost for e in entries), 4)
        model_breakdown: dict[str, float] = defaultdict(float)
        for e in entries:
            model_breakdown[e.model] += e.cost

        report_data = {
            "period": period,
            "key": key,
            "total_cost": total_cost,
            "active_users": len(users),
            "active_teams": len(teams),
            "call_count": len(entries),
            "model_breakdown": {
                m: round(c, 4) for m, c in sorted(model_breakdown.items())
            },
            "alerts": len(self._alerts),
            "generated_at": datetime.now().isoformat(),
        }

        return json.dumps(report_data, indent=2, ensure_ascii=False)

    def alerts(self, acknowledged: Optional[bool] = None) -> list[BudgetAlert]:
        if acknowledged is None:
            return list(self._alerts)
        return [a for a in self._alerts if a.acknowledged == acknowledged]

    def acknowledge_alert(self, alert: BudgetAlert) -> None:
        alert.acknowledged = True

    def _entries_for_period(self, period: str) -> list[CostEntry]:
        now = time.time()
        if period == "daily":
            cutoff = now - 86400
        elif period == "weekly":
            cutoff = now - 7 * 86400
        elif period == "monthly":
            cutoff = now - 30 * 86400
        else:
            return list(self._entries)
        return [e for e in self._entries if e.timestamp >= cutoff]

    def _aggregate(self, predicate, period: str) -> float:
        entries = self._entries_for_period(period) if period != "all" else self._entries
        return round(sum(e.cost for e in entries if predicate(e)), 4)
