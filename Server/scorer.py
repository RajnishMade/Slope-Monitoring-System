"""
scorer.py
Wraps the TabPFN plane-failure regressor for real-time scoring.

TabPFN is an in-context learner: fit() just memorizes the 149-row training
set, and the real compute happens at predict() time. So we fit ONCE at server
startup, then every incoming sensor reading is scored with a single predict().

Feature vector (order fixed by Src/config.PLANE_FEATURES):
    slope_angle_af_deg, failure_plane_dip_ap_deg, upper_slope_angle_as_deg,
    h_m, unit_weight_gamma_kNm3, friction_angle_phi_deg, cohesion_C_kPa,
    seismic_kh, water_level
The first 8 are STATIC per node (geotechnical survey values); water_level is
DYNAMIC, derived from the water/rain sensors.
"""

import os
import sys
import threading

import numpy as np
import pandas as pd

# Make the project's Src/ importable regardless of the current working dir.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "Src"))

import config  # noqa: E402  (Src/config.py)
from feature_engineering.FeaturePlane import make_plane_features  # noqa: E402


class FosScorer:
    def __init__(self):
        self._lock = threading.Lock()   # torch model calls are serialized
        self.features = list(config.PLANE_FEATURES)
        self.model = None
        self.n_train = 0
        self.fos_min = None
        self.fos_max = None

    def load(self):
        """Fit TabPFN once on the cleaned plane-failure dataset."""
        from tabpfn import TabPFNRegressor

        data_path = os.path.join(PROJECT_ROOT, config.PLANE_DATA_PATH)
        df = pd.read_csv(data_path)
        X = make_plane_features(df).values
        y = df[config.PLANE_TARGET].values.astype(float)

        model = TabPFNRegressor(random_state=config.RANDOM_STATE)
        model.fit(X, y)

        self.model = model
        self.n_train = len(df)
        self.fos_min = float(y.min())
        self.fos_max = float(y.max())
        return self

    def predict_fos(self, feats: dict) -> float:
        """Score one reading. `feats` must contain all PLANE_FEATURES keys."""
        if self.model is None:
            raise RuntimeError("Scorer not loaded — call load() first.")
        missing = [f for f in self.features if f not in feats]
        if missing:
            raise KeyError(f"Missing features: {missing}")
        row = np.array([[float(feats[f]) for f in self.features]], dtype=float)
        with self._lock:
            pred = self.model.predict(row)
        return float(np.ravel(pred)[0])

    def meta(self) -> dict:
        return {
            "model": "TabPFNRegressor",
            "target": config.PLANE_TARGET,
            "features": self.features,
            "n_train": self.n_train,
            "fos_train_range": [self.fos_min, self.fos_max],
        }
