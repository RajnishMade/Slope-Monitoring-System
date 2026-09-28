"""
planeTabpfnReport.py
Full TabPFN report for the plane-failure FoS regressor.

Runs ONE 5-fold cross-validation (random_state = config.RANDOM_STATE) and
reports everything in one place:
  - correlation matrix (9 features + FoS target)
  - per-fold R2 / MAE / RMSE / MAPE, plus mean +/- std
  - overall metrics on the pooled out-of-fold (OOF) predictions
  - confusion matrix, thresholding FoS at 1.0 (>=1 = stable, <1 = unstable)

FoS is a continuous target, so the confusion matrix is derived: each slope's
true and predicted FoS are turned into stable/unstable at the FoS = 1.0 line,
which is the physical failure boundary.
"""

import sys, os, warnings
warnings.filterwarnings("ignore")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PROJECT_ROOT, "Src"))

import numpy as np
import pandas as pd
from sklearn.model_selection import KFold
from sklearn.metrics import (
    r2_score, mean_absolute_error, mean_squared_error,
    mean_absolute_percentage_error, confusion_matrix, classification_report,
)
from tabpfn import TabPFNRegressor

import config
from feature_engineering.FeaturePlane import make_plane_features

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)


def main():
    # ---- load ----
    print("Loading:", config.PLANE_DATA_PATH)
    df = pd.read_csv(config.PLANE_DATA_PATH)
    Xdf = make_plane_features(df)          # 9 engineered features (DataFrame)
    X = Xdf.values
    y = df[config.PLANE_TARGET].values.astype(float)
    print(f"{len(df)} rows | {X.shape[1]} features | target: {config.PLANE_TARGET}")
    print(f"FoS range: {y.min():.2f} to {y.max():.2f}\n")

    # ---- correlation matrix (features + target) ----
    corr = Xdf.copy()
    corr[config.PLANE_TARGET] = y
    print("=" * 70)
    print("CORRELATION MATRIX (Pearson) - 9 features + FoS")
    print("=" * 70)
    print(corr.corr().round(2).to_string())
    print("\nFeature vs FoS correlation (sorted):")
    print(corr.corr()[config.PLANE_TARGET].drop(config.PLANE_TARGET)
          .sort_values(ascending=False).round(3).to_string())
    print()

    # ---- 5-fold CV with TabPFN regressor ----
    cv = KFold(n_splits=5, shuffle=True, random_state=config.RANDOM_STATE)
    oof_pred = np.zeros_like(y, dtype=float)   # pooled out-of-fold predictions
    rows = []
    print("=" * 70)
    print("5-FOLD CROSS-VALIDATION  (TabPFN Regressor)")
    print("=" * 70)
    for k, (tr, te) in enumerate(cv.split(X), start=1):
        reg = TabPFNRegressor(random_state=config.RANDOM_STATE)
        reg.fit(X[tr], y[tr])
        pred = reg.predict(X[te])
        oof_pred[te] = pred
        r2   = r2_score(y[te], pred)
        mae  = mean_absolute_error(y[te], pred)
        rmse = np.sqrt(mean_squared_error(y[te], pred))
        mape = mean_absolute_percentage_error(y[te], pred) * 100
        rows.append((k, len(te), r2, mae, rmse, mape))
        print(f"  Fold {k}: n={len(te):3d}  R2={r2:6.3f}  MAE={mae:6.3f}  "
              f"RMSE={rmse:6.3f}  MAPE={mape:6.2f}%")

    res = pd.DataFrame(rows, columns=["fold", "n", "R2", "MAE", "RMSE", "MAPE"])
    print("\nPer-fold summary (mean +/- std across folds):")
    for m in ["R2", "MAE", "RMSE", "MAPE"]:
        unit = "%" if m == "MAPE" else ""
        print(f"  {m:5s}: {res[m].mean():.3f} +/- {res[m].std():.3f}{unit}")

    # ---- overall metrics on pooled OOF predictions ----
    print("\n" + "=" * 70)
    print(f"OVERALL  (pooled out-of-fold predictions, all {len(y)} slopes)")
    print("=" * 70)
    print(f"  R2   : {r2_score(y, oof_pred):.3f}")
    print(f"  MAE  : {mean_absolute_error(y, oof_pred):.3f}")
    print(f"  RMSE : {np.sqrt(mean_squared_error(y, oof_pred)):.3f}")
    print(f"  MAPE : {mean_absolute_percentage_error(y, oof_pred) * 100:.2f}%")

    # ---- confusion matrix (threshold FoS at 1.0) ----
    THRESH = 1.0
    # label 1 = UNSTABLE (FoS < 1), label 0 = STABLE (FoS >= 1)
    y_true_cls = (y < THRESH).astype(int)
    y_pred_cls = (oof_pred < THRESH).astype(int)
    cm = confusion_matrix(y_true_cls, y_pred_cls, labels=[0, 1])
    print("\n" + "=" * 70)
    print(f"CONFUSION MATRIX  (FoS threshold = {THRESH}:  >=1 stable, <1 unstable)")
    print("=" * 70)
    cm_df = pd.DataFrame(
        cm,
        index=["actual STABLE", "actual UNSTABLE"],
        columns=["pred STABLE", "pred UNSTABLE"],
    )
    print(cm_df.to_string())
    acc = (y_true_cls == y_pred_cls).mean()
    print(f"\nClassification accuracy at FoS=1.0 boundary: {acc:.3f}")
    print("\n" + classification_report(
        y_true_cls, y_pred_cls, target_names=["STABLE", "UNSTABLE"], digits=3))


if __name__ == "__main__":
    main()
