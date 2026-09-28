"""
planeFailureTrain.py
Trains the plane-failure FoS REGRESSOR (predicts the Factor of Safety
as a number, not stable/unstable).

Regression metrics:
  R2   = fraction of FoS variance explained (1.0 = perfect)
  MAE  = average error in FoS units
  RMSE = root mean squared error (penalizes big misses)
"""

import sys, os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PROJECT_ROOT, "Src"))

import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from sklearn.model_selection import KFold, cross_val_score, cross_val_predict
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

import config
from feature_engineering.FeaturePlane import make_plane_features


def main():
    print("Loading:", config.PLANE_DATA_PATH)
    df = pd.read_csv(config.PLANE_DATA_PATH)
    X = make_plane_features(df)
    y = df[config.PLANE_TARGET].values
    print(f"{len(df)} rows | {X.shape[1]} features | target: {config.PLANE_TARGET}")
    print(f"FoS range: {y.min():.2f} to {y.max():.2f}\n")

    cv = KFold(n_splits=5, shuffle=True, random_state=config.RANDOM_STATE)
    model = XGBRegressor(**config.XGB_REG_PARAMS)

    # cross-validated metrics
    r2  = cross_val_score(model, X, y, cv=cv, scoring="r2")
    mae = -cross_val_score(model, X, y, cv=cv, scoring="neg_mean_absolute_error")
    rmse = -cross_val_score(model, X, y, cv=cv, scoring="neg_root_mean_squared_error")

    print("=" * 45)
    print("CROSS-VALIDATED REGRESSION PERFORMANCE")
    print("=" * 45)
    print(f"  R2:   {r2.mean():.3f}  (+/- {r2.std():.3f})")
    print(f"  MAE:  {mae.mean():.3f}  FoS units")
    print(f"  RMSE: {rmse.mean():.3f}  FoS units")
    print()
    print(f"  Meaning: predictions are off by ~{mae.mean():.2f} FoS on average.")
    print()

    # train on all data and save
    model.fit(X, y)
    os.makedirs(os.path.join(PROJECT_ROOT, "Models"), exist_ok=True)
    path = os.path.join(PROJECT_ROOT, config.PLANE_MODEL_PATH)
    model.save_model(path)
    print(f"Model saved to: {path}")

    # feature importance
    print("\nFeature importance:")
    for name, imp in sorted(zip(config.PLANE_FEATURES, model.feature_importances_),
                            key=lambda x: -x[1]):
        print(f"  {name:28s}: {imp:.3f}")


if __name__ == "__main__":
    main()