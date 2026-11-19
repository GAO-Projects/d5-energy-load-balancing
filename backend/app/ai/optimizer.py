import time
import uuid
from dataclasses import dataclass
from typing import Dict, Tuple
from app.ai.forecaster import PowerDemandForecaster
from app.config import settings

@dataclass
class OptimizationResult:
    decision_id: str
    system_state: str       # OPTIMAL | SHEDDING | INFEASIBLE_BUDGET | STALE_FALLBACK | PASSIVE_MONITOR
    reason_code: str
    measured_total_watts: float
    forecast_5s_watts: float
    forecast_10s_watts: float
    error_margin_watts: float
    target_duties: Dict[int, int]
    anomaly_score: float

class PriorityLoadOptimizer:
    """
    Implements D5 Constrained Priority Optimization (Physical AI Guide p. 17):
    - Priority 1 (Ch 1 Essential Fan): Preserved at 100% unless hardware limit tripped.
    - Priority 2 (Ch 2 Flexible Fan): Preserved ahead of decorative lighting; excludes unstable <25% duties.
    - Priority 3 (Ch 3 LED Strip): Dimmed or shed first to stay within budget.
    """
    def __init__(self, forecaster: PowerDemandForecaster):
        self.forecaster = forecaster
        self.last_discretionary_change_ts = 0.0
        self.current_target: Dict[int, int] = {1: 100, 2: 100, 3: 100}

    def evaluate(
        self,
        channel_watts: Dict[int, float],
        last_update_age_s: float,
        budget_watts: float,
        slope_w_s: float,
        demo_track: str,
    ) -> OptimizationResult:
        decision_id = f"dec_{uuid.uuid4().hex[:8]}"
        w1 = channel_watts.get(1, 0.0)
        w2 = channel_watts.get(2, 0.0)
        w3 = channel_watts.get(3, 0.0)
        total_w = round(w1 + w2 + w3, 3)

        # Track B: AIoT Passive Mode ("No load is controlled by software")
        if demo_track == "aiot":
            p5, p10 = self.forecaster.predict_candidate(
                total_w, slope_w_s, self.current_target[1], self.current_target[2], self.current_target[3]
            )
            anomaly = round(min(1.0, abs(total_w - p5) / 2.5), 3)
            return OptimizationResult(
                decision_id=decision_id,
                system_state="PASSIVE_MONITOR",
                reason_code="AIOT_PASSIVE_FORECAST_ONLY",
                measured_total_watts=total_w,
                forecast_5s_watts=p5,
                forecast_10s_watts=p10,
                error_margin_watts=self.forecaster.error_margin_watts,
                target_duties=dict(self.current_target),
                anomaly_score=anomaly,
            )

        # Rule 1: Stale BLE telemetry (>2.0s) -> Immediate flexible load shedding
        if last_update_age_s > settings.STALE_THRESHOLD_SEC:
            self.current_target = {1: 100, 2: 0, 3: 0} #Fan 1 on, Fan 2 and LED are off
            return OptimizationResult(
                decision_id=decision_id,
                system_state="STALE_FALLBACK",
                reason_code=f"STALE_TELEMETRY_{last_update_age_s:.1f}S",
                measured_total_watts=total_w,
                forecast_5s_watts=w1,
                forecast_10s_watts=w1,
                error_margin_watts=self.forecaster.error_margin_watts,
                target_duties=dict(self.current_target),
                anomaly_score=1.0,
            )

        # Rule 2: Infeasible budget check (Essential load alone exceeds budget)
        if w1 > budget_watts:
            self.current_target = {1: 100, 2: 0, 3: 0}
            return OptimizationResult(
                decision_id=decision_id,
                system_state="INFEASIBLE_BUDGET",
                reason_code="ESSENTIAL_LOAD_EXCEEDS_BUDGET",
                measured_total_watts=total_w,
                forecast_5s_watts=round(w1, 3),
                forecast_10s_watts=round(w1, 3),
                error_margin_watts=self.forecaster.error_margin_watts,
                target_duties=dict(self.current_target),
                anomaly_score=0.95,
            )

        # Rule 3: Enumerate allowed candidate PWM pairs (exclude unstable fan duties 1..24%)
        allowed_fan2 = [100, 80, 60, 40, 25, 0]
        allowed_led3 = [100, 80, 60, 40, 20, 0]

        best_candidate: Tuple[int, int, int] = (100, 0, 0)
        best_penalty = float("inf")
        best_p5, best_p10 = 0.0, 0.0
        found_feasible = False

        for d2 in allowed_fan2:
            for d3 in allowed_led3:
                p5, p10 = self.forecaster.predict_candidate(total_w, slope_w_s, 100, d2, d3)
                worst_forecast = max(p5, p10) + self.forecaster.error_margin_watts
                if worst_forecast <= budget_watts:
                    # Service penalty: shedding Flexible Fan is 3x costlier than dimming LED Strip
                    penalty = 3.0 * (100 - d2) + 1.0 * (100 - d3)
                    if penalty < best_penalty:
                        best_penalty = penalty
                        best_candidate = (100, d2, d3)
                        best_p5, best_p10 = p5, p10
                        found_feasible = True

        if not found_feasible:
            best_candidate = (100, 0, 0)
            best_p5, best_p10 = self.forecaster.predict_candidate(total_w, slope_w_s, 100, 0, 0)

        new_target = {1: best_candidate[0], 2: best_candidate[1], 3: best_candidate[2]}
        now = time.time()
        over_budget_now = total_w > budget_watts

        # Enforce 3-second dwell for discretionary power increases; bypass dwell on over-budget curtailment
        if new_target != self.current_target:
            if over_budget_now or (now - self.last_discretionary_change_ts) >= settings.DWELL_SECONDS:
                self.current_target = new_target
                self.last_discretionary_change_ts = now

        state = "OPTIMAL" if self.current_target == {1: 100, 2: 100, 3: 100} else "SHEDDING"
        reason = (
            "FULL_CAPACITY_WITHIN_BUDGET"
            if state == "OPTIMAL"
            else f"BUDGET_CAP_{budget_watts:.1f}W_FAN2_{self.current_target[2]}%_LED_{self.current_target[3]}%"
        )
        anomaly = round(min(1.0, abs(total_w - best_p5) / 2.5), 3)

        return OptimizationResult(
            decision_id=decision_id,
            system_state=state,
            reason_code=reason,
            measured_total_watts=total_w,
            forecast_5s_watts=best_p5,
            forecast_10s_watts=best_p10,
            error_margin_watts=self.forecaster.error_margin_watts,
            target_duties=dict(self.current_target),
            anomaly_score=anomaly,
        )
    