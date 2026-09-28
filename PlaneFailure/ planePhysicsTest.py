"""
planePhysicsTest.py
Physics sanity test for the constrained plane FoS regressor.
Changes ONE parameter at a time and checks that predicted FoS
moves in the physically-correct direction.
"""

import sys, os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PROJECT_ROOT, "Src"))

import numpy as np
import pandas as pd
from xgboost import XGBRegressor
import config
from feature_engineering.FeaturePlane import make_plane_features


# --- train the constrained regressor ---
df = pd.read_csv(config.PLANE_DATA_PATH)
X = make_plane_features(df)
y = df[config.PLANE_TARGET].values
model = XGBRegressor(**config.XGB_REG_PARAMS)
model.fit(X, y)


def fos(slope_af, plane_dip, upper, H, gamma, phi, c, kh, water):
    """Predict FoS for one slope. Order matches PLANE_FEATURES."""
    row = pd.DataFrame([[slope_af, plane_dip, upper, H, gamma, phi, c, kh, water]],
                       columns=config.PLANE_FEATURES)
    return model.predict(row)[0]


# baseline slope - edit if you want a different starting point
base = dict(slope_af=60, plane_dip=35, upper=15, H=40,
            gamma=26, phi=30, c=40, kh=0.0, water=0.0)

print("=" * 55)
print("PHYSICS SANITY TEST - constrained plane FoS regressor")
print("Each change should move FoS the physically-correct way")
print("=" * 55)

print("\nWATER (dry->moderate->full): FoS should DROP")
for w in [0.0, 0.5, 1.0]:
    print(f"   water={w}: FoS = {fos(**{**base, 'water': w}):.3f}")

print("\nCOHESION (5->40->100 kPa): FoS should RISE")
for cc in [5, 40, 100]:
    print(f"   c={cc}: FoS = {fos(**{**base, 'c': cc}):.3f}")

print("\nFRICTION (15->30->45 deg): FoS should RISE")
for p in [15, 30, 45]:
    print(f"   phi={p}: FoS = {fos(**{**base, 'phi': p}):.3f}")

print("\nPLANE DIP (25->40->55 deg): FoS should DROP")
for pd_ in [25, 40, 55]:
    print(f"   plane_dip={pd_}: FoS = {fos(**{**base, 'plane_dip': pd_}):.3f}")

print("\nSEISMIC kh (0->0.08->0.15): FoS should DROP")
for k in [0.0, 0.08, 0.15]:
    print(f"   kh={k}: FoS = {fos(**{**base, 'kh': k}):.3f}")

print("\nHEIGHT (20->80->200 m): FoS should DROP")
for h in [20, 80, 200]:
    print(f"   H={h}: FoS = {fos(**{**base, 'H': h}):.3f}")

print()
print("If every group moves the right direction, the physics")
print("constraints are working and the model is physically consistent.")