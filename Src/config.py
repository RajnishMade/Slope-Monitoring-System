"""
config.py
Central settings for the plane-failure FoS regressor.
Everything the training code needs lives here: which columns, which
target, where the data is, where to save the model.
"""

# ---------------------------------------------------------------
# REPRODUCIBILITY
# ---------------------------------------------------------------

# Random seed so the split/model is the SAME every time you run.
# (reproducibility — critical for a thesis)
RANDOM_STATE = 42

# ---------------------------------------------------------------
# PLANE FAILURE (regression - predicts FoS)
# ---------------------------------------------------------------

PLANE_FEATURES = [
    "slope_angle_af_deg", "failure_plane_dip_ap_deg", "upper_slope_angle_as_deg",
    "h_m", "unit_weight_gamma_kNm3", "friction_angle_phi_deg", "cohesion_C_kPa",
    "seismic_kh", "water_level",
]

PLANE_TARGET = "FoS"

# adjust path to where you saved the cleaned file
PLANE_DATA_PATH = "Data/plane_failure_CLEAN.csv"
PLANE_MODEL_PATH = "Models/plane_regressor.json"

# Physics constraints for FoS regression (predicting FoS directly).
# Sign = effect on FoS: stabilizing = +1, destabilizing = -1, ambiguous = 0.
# Order matches PLANE_FEATURES:
# (slope_af, plane_dip, upper_slope, H, gamma, phi, c, kh, water)
#    -1        -1          -1       -1    0    +1  +1  -1   -1
PLANE_MONOTONE = (-1, -1, -1, -1, 0, 1, 1, -1, -1)

# regressor hyperparameters
XGB_REG_PARAMS = {
    "n_estimators": 300,
    "max_depth": 4,
    "learning_rate": 0.03,
    "subsample": 0.9,
    "colsample_bytree": 0.9,
    "random_state": RANDOM_STATE,
    "monotone_constraints": PLANE_MONOTONE,
}
