"""
planeTabpfnTest.py
Benchmarks TabPFN REGRESSOR on plane FoS prediction, across multiple
seeds, comparing to your XGBoost regressor.
Note: uses TabPFNRegressor (regression), not the classifier.
"""

import sys, os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PROJECT_ROOT, "Src"))

import numpy as np
import pandas as pd
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score, mean_absolute_error
import config
from feature_engineering.FeaturePlane import make_plane_features

df = pd.read_csv(config.PLANE_DATA_PATH)
X = make_plane_features(df).values
y = df[config.PLANE_TARGET].values
print(f"{len(df)} rows, target FoS\n")

from tabpfn import TabPFNRegressor

seeds = [42, 0, 7, 123, 2024]
r2_means, mae_means = [], []

print("Running TabPFN Regressor across 5 seeds (downloads model first run)...\n")
for seed in seeds:
    cv = KFold(n_splits=5, shuffle=True, random_state=seed)
    r2s, maes = [], []
    for tr, te in cv.split(X):
        reg = TabPFNRegressor()
        reg.fit(X[tr], y[tr])
        pred = reg.predict(X[te])
        r2s.append(r2_score(y[te], pred))
        maes.append(mean_absolute_error(y[te], pred))
    r2_means.append(np.mean(r2s))
    mae_means.append(np.mean(maes))
    print(f"  Seed {seed:4d}: R2={np.mean(r2s):.3f}  MAE={np.mean(maes):.3f}")

print()
print("=" * 45)
print(f"TabPFN Regressor across {len(seeds)} seeds:")
print(f"  R2:  {np.mean(r2_means):.3f}  (+/- {np.std(r2_means):.3f})")
print(f"  MAE: {np.mean(mae_means):.3f}")
print("=" * 45)
print()
print("Compare to your XGBoost regressor: R2 ~0.89, MAE ~0.13")
print("(Remember: TabPFN can't take physics constraints, like before)")