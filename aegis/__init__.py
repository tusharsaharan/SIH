"""AegisForecast - AI-based Network Attack Forecasting from Network Traffic Data."""

__version__ = "0.2.0"

WINDOW_SECONDS = 5          # rolling aggregation window
FORECAST_HORIZON_MIN = 30   # max forecast lead time
# Calibrated by scripts/recalibrate.py (post multi-host-benign retrain):
# 0.72 yields 15.24 min median lead (p10-p90 11.3-22.9) at 0.73 false
# alerts/hr with 100% attack coverage. Benign max sits ~0.72 - the sweep
# shows a sharp cliff (0.60-0.70 = FP storm, 0.75 = zero coverage).
ALERT_CONFIDENCE = 0.72
