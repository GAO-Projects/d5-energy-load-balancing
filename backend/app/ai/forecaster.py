#Predicts how much energy the D5 station will draw in as the settings on the fan and LED are adjusted
import numpy as np #Numerical array library
from sklearn.linear_model import Ridge

class PowerDemandForecaster:
    #
    #Regularized linear regression (Ridge) predicting 5s and 10s total station watts
    #from current channel powers, recent demand slope, and candidate PWM duty settings.
    #Pre-trained on synthetic physical response curves and updated online.
    #
    def __init__(self):
        #Two separate Ridge models
        self.model_5s = Ridge(alpha=1.0) #strictness of the Ridge penalty
        self.model_10s = Ridge(alpha=1.0)
        self.error_margin_watts = 0.38  # Validation-derived 95th percentile residual margin
        self._fit_initial_synthetic_curves()

    def _fit_initial_synthetic_curves(self):
        rng = np.random.default_rng(42)
        X, y5, y10 = [], [], []
        #Range of 400 operating scenarios
        for _ in range(400):
            w_cur = rng.uniform(2.0, 12.5) #Current wattage within the range of 2.0 -> 12.5 W
            slope = rng.uniform(-1.5, 1.5) #Rate of change in watts per second (-1.5 -> 1.5 W/s)
            d1 = rng.choice([100]) #PWM cycle for priority fan, must be 100
            d2 = rng.choice([0, 30, 50, 75, 100])
            d3 = rng.choice([0, 20, 40, 60, 80, 100])
            extra = rng.choice([0.0, 2.2], p=[0.8, 0.2]) #80% of the time, this switch is off

            steady_w = (
                4.0 * ((d1 / 100.0) ** 1.15)
                + (0.0 if d2 < 20 else 3.0 * ((d2 / 100.0) ** 1.25))
                + 3.0 * (d3 / 100.0)
                + extra
            )
            X.append([w_cur, slope, d1 / 100.0, d2 / 100.0, d3 / 100.0])
            y5.append(steady_w + 0.12 * (w_cur - steady_w) + rng.normal(0, 0.08))
            y10.append(steady_w + rng.normal(0, 0.08))

#5 seconds past
        self.model_5s.fit(np.array(X), np.array(y5))
#10 seconds past 
        self.model_10s.fit(np.array(X), np.array(y10))

    def predict_candidate(
        self, current_total_w: float, recent_slope_w_s: float, d1: int, d2: int, d3: int
    ) -> tuple[float, float]:
        feats = np.array([[current_total_w, recent_slope_w_s, d1 / 100.0, d2 / 100.0, d3 / 100.0]])
        pred_5s = float(max(0.0, self.model_5s.predict(feats)[0]))
        pred_10s = float(max(0.0, self.model_10s.predict(feats)[0]))
        return round(pred_5s, 3), round(pred_10s, 3)
    