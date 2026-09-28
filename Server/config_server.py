"""
config_server.py
Status logic for the platform. Each slope has its OWN user-defined FoS alert
threshold, so status is computed relative to that threshold (not a global FoS
cut-off):

    ALERT    (critical) : FoS <= threshold                 -> generate alert
    WARNING  (approach) : threshold < FoS <= threshold*1.10 -> approaching
    STABLE   (normal)   : FoS > threshold*1.10

The model itself (features, data) stays in Src/config.py. This file is only
about interpreting the model output for alerting and the dashboard.
"""

STABLE, WARNING, ALERT = "STABLE", "WARNING", "ALERT"
STATUS_COLORS = {STABLE: "#30D158", WARNING: "#FF9F0A", ALERT: "#FF453A"}
WARN_RATIO = 1.10   # within +10% of threshold counts as "approaching"


def classify(fos: float, threshold: float):
    """Return (status, alert_bool) for a FoS against a slope's threshold."""
    if fos <= threshold:
        return ALERT, True
    if fos <= threshold * WARN_RATIO:
        return WARNING, False
    return STABLE, False


def meta() -> dict:
    """Sent to the dashboard for colors + the warning band."""
    return {
        "warn_ratio": WARN_RATIO,
        "colors": STATUS_COLORS,
        "levels": [STABLE, WARNING, ALERT],
    }
