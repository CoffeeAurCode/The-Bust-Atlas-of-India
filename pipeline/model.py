"""LightGBM bust classifier with isotonic calibration."""

from __future__ import annotations

import pickle
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from pipeline.features import FEATURES

PARAMS = dict(
    objective="binary",
    learning_rate=0.03,
    num_leaves=15,
    min_child_samples=40,
    feature_fraction=0.8,
    bagging_fraction=0.8,
    bagging_freq=1,
    lambda_l2=1.0,
    verbose=-1,
    seed=0,
)


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


@dataclass
class BustModel:
    booster: lgb.Booster | None = None
    iso: IsotonicRegression | None = None
    features: list[str] = field(default_factory=lambda: list(FEATURES))
    meta: dict = field(default_factory=dict)

    def fit(self, df_train: pd.DataFrame, df_cal: pd.DataFrame, num_rounds: int = 400) -> "BustModel":
        X = df_train[self.features]
        y = df_train["bust"].astype(int)
        pos = max(int(y.sum()), 1)
        params = {**PARAMS, "scale_pos_weight": (len(y) - pos) / pos}
        dtrain = lgb.Dataset(X, y, categorical_feature=["season_code", "region_code"])
        dcal = lgb.Dataset(df_cal[self.features], df_cal["bust"].astype(int), reference=dtrain)
        self.booster = lgb.train(
            params, dtrain, num_boost_round=num_rounds, valid_sets=[dcal],
            callbacks=[lgb.early_stopping(50, verbose=False)],
        )
        raw = self.booster.predict(df_cal[self.features])
        self.iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        self.iso.fit(raw, df_cal["bust"].astype(float))
        self.meta = {
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "git_sha": _git_sha(),
            "train_years": sorted(df_train["year"].unique().tolist()),
            "cal_years": sorted(df_cal["year"].unique().tolist()),
            "n_train": int(len(df_train)),
            "n_train_pos": int(y.sum()),
            "best_iteration": int(self.booster.best_iteration or num_rounds),
            "features": self.features,
            "calibration": "isotonic",
            "params": params,
        }
        return self

    def predict_raw(self, df: pd.DataFrame) -> np.ndarray:
        assert self.booster is not None
        return self.booster.predict(df[self.features], num_iteration=self.booster.best_iteration)

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        assert self.iso is not None
        return self.iso.predict(self.predict_raw(df))

    def contributions(self, df: pd.DataFrame) -> np.ndarray:
        """Per-feature SHAP-style contributions (n, n_features), bias column dropped."""
        assert self.booster is not None
        c = self.booster.predict(df[self.features], pred_contrib=True,
                                 num_iteration=self.booster.best_iteration)
        return c[:, :-1]

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({"booster": self.booster.model_to_string(), "iso": self.iso,
                         "features": self.features, "meta": self.meta}, f)

    @classmethod
    def load(cls, path: str | Path) -> "BustModel":
        with open(path, "rb") as f:
            d = pickle.load(f)
        m = cls(features=d["features"], meta=d["meta"], iso=d["iso"])
        m.booster = lgb.Booster(model_str=d["booster"])
        return m
