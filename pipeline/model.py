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
from pipeline.calibrate import MonotoneCalibrator
from pipeline.features import FEATURES

# Early stopping is scored on AUC, not binary_logloss. With scale_pos_weight the
# training loss is class-weighted while the validation set is not, so unweighted
# logloss on the calibration year rises from the first round and early stopping bails
# at iteration 1 (this shipped once: the "model" was a single tree and lost to the
# spread baseline). Isotonic regression supplies the calibration afterwards, so the
# booster only has to rank.
PARAMS = dict(
    objective="binary",
    metric="auc",
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


N_SEEDS = 5
"""Boosters averaged per model. One year of Indian Z500 gives ~730 independent inits,
so a single seed's test PR-AUC swings by more than the model's margin over the spread
baseline. Averaging the raw scores of a few seeds makes the reported number a property
of the method rather than of the seed."""


@dataclass
class BustModel:
    boosters: list[lgb.Booster] = field(default_factory=list)
    cal: MonotoneCalibrator | None = None
    features: list[str] = field(default_factory=lambda: list(FEATURES))
    meta: dict = field(default_factory=dict)

    @property
    def booster(self) -> lgb.Booster | None:
        """First booster. For inspection only; prediction uses the whole ensemble."""
        return self.boosters[0] if self.boosters else None

    def fit(self, df_train: pd.DataFrame, df_cal: pd.DataFrame, num_rounds: int = 400,
            n_seeds: int = N_SEEDS) -> "BustModel":
        X = df_train[self.features]
        y = df_train["bust"].astype(int)
        pos = max(int(y.sum()), 1)
        params = {**PARAMS, "scale_pos_weight": (len(y) - pos) / pos}
        self.boosters = self._train(X, y, params, num_rounds, n_seeds, df_cal)
        self.cal = MonotoneCalibrator().fit(self.predict_raw(df_cal), df_cal["bust"].astype(int))
        self.meta = {
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "git_sha": _git_sha(),
            "train_years": sorted(df_train["year"].unique().tolist()),
            "cal_years": sorted(df_cal["year"].unique().tolist()),
            "n_train": int(len(df_train)),
            "n_train_pos": int(y.sum()),
            "n_seeds": n_seeds,
            "best_iterations": [int(b.best_iteration or num_rounds) for b in self.boosters],
            "features": self.features,
            "calibration": "isotonic + tie-break",
            "params": params,
        }
        return self

    def _train(self, X: pd.DataFrame, y: pd.Series, params: dict, num_rounds: int,
               n_seeds: int, df_valid: pd.DataFrame | None) -> list[lgb.Booster]:
        """n_seeds boosters. With df_valid they early-stop on it; without, they run the
        full num_rounds on every row (used for the final cross-fitted model, where the
        round count is already known from the folds and no data should be held back)."""
        cat = [c for c in ("season_code", "region_code") if c in self.features]
        out = []
        for seed in range(n_seeds):
            p = {**params, "seed": seed, "bagging_seed": seed, "feature_fraction_seed": seed}
            dtrain = lgb.Dataset(X, y, categorical_feature=cat)
            kw: dict = {}
            if df_valid is not None:
                kw["valid_sets"] = [lgb.Dataset(df_valid[self.features],
                                                df_valid["bust"].astype(int), reference=dtrain)]
                kw["callbacks"] = [lgb.early_stopping(50, verbose=False)]
            out.append(lgb.train(p, dtrain, num_boost_round=num_rounds, **kw))
        return out

    def _pick_rounds(self, dev: pd.DataFrame, inits: np.ndarray, num_rounds: int,
                     n_seeds: int) -> int:
        """Boosting rounds, chosen once on a single chronological 75/25 split of the
        development period. Per-seed early stopping is erratic here (best iterations
        ranged 5 to 70 on IFS ENS 2020-2021), so the median across seeds is taken and
        then held fixed everywhere else."""
        cut = inits[int(len(inits) * 0.75)]
        iv = dev["init"].to_numpy()
        probe = BustModel(features=list(self.features))
        probe.fit(dev[iv < cut], dev[iv >= cut], num_rounds=num_rounds, n_seeds=n_seeds)
        return max(int(np.median(probe.meta["best_iterations"])), 1)

    def fit_cv(self, df_dev: pd.DataFrame, n_folds: int = 5, num_rounds: int = 400,
               n_seeds: int = N_SEEDS) -> "BustModel":
        """Train on every pre-test year, calibrate on out-of-fold scores.

        The plain fit() spends a whole year on calibration alone, which on three years of
        archive is a third of the data. Here the development period is cut into n_folds
        contiguous blocks of initialisation dates; each block is scored by boosters that
        never saw it, and the calibrator is fitted on the pooled out-of-fold scores. Those
        cover every season, so the calibration is not hostage to whichever months happened
        to fall in a hold-out window.

        The number of boosting rounds is fixed up front rather than early-stopped per
        fold. That matters more than it looks: with early stopping each fold model also
        has to surrender a block to stop on, so it trains on half the development period
        and comes out blunter than the model actually deployed. Calibrating a sharp model
        with a blunt model's scores flattened the top of the curve onto 6.8% while the
        deployed model's top decile was busting at 15.3%, that is, at exactly the
        threshold the product calls unreliable. With rounds fixed, every fold model sees
        (n_folds - 1) / n_folds of the data and the mismatch closes.

        Folds are contiguous in time, never random: rows from one initialisation share a
        synoptic situation, so a random split would put near-duplicates on both sides.
        """
        dev = df_dev.sort_values("init")
        inits = np.sort(dev["init"].unique())
        if len(inits) < n_folds * 2:
            raise ValueError(f"{len(inits)} inits is too few for {n_folds} folds")
        n_rounds = self._pick_rounds(dev, inits, num_rounds, n_seeds)

        y = dev["bust"].astype(int)
        pos = max(int(y.sum()), 1)
        params = {**PARAMS, "scale_pos_weight": (len(y) - pos) / pos}
        blocks = np.array_split(inits, n_folds)
        init_vals = dev["init"].to_numpy()
        oof = np.full(len(dev), np.nan)
        for block in blocks:
            hold = np.isin(init_vals, block)
            keep = dev[~hold]
            boosters = self._train(keep[self.features], keep["bust"].astype(int),
                                   params, n_rounds, n_seeds, None)
            X = dev.loc[hold, self.features]
            oof[hold] = np.mean([b.predict(X) for b in boosters], axis=0)
        assert not np.isnan(oof).any(), "every development row must get an out-of-fold score"

        self.boosters = self._train(dev[self.features], y, params, n_rounds, n_seeds, None)
        self.cal = MonotoneCalibrator().fit(oof, y)
        self.meta = {
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "git_sha": _git_sha(),
            "train_years": sorted(dev["year"].unique().tolist()),
            "cal_years": sorted(dev["year"].unique().tolist()),
            "n_train": int(len(dev)),
            "n_train_pos": int(y.sum()),
            "n_seeds": n_seeds,
            "cv_folds": n_folds,
            "best_iterations": [n_rounds] * n_seeds,
            "features": self.features,
            "calibration": "isotonic on out-of-fold scores + tie-break",
            "params": params,
        }
        return self

    def predict_raw(self, df: pd.DataFrame) -> np.ndarray:
        assert self.boosters, "call fit or load first"
        X = df[self.features]
        return np.mean([b.predict(X, num_iteration=b.best_iteration) for b in self.boosters], axis=0)

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        assert self.cal is not None, "call fit or fit_cv first"
        return self.cal.predict(self.predict_raw(df))

    def contributions(self, df: pd.DataFrame) -> np.ndarray:
        """Per-feature SHAP-style contributions (n, n_features), bias column dropped."""
        assert self.boosters, "call fit or load first"
        X = df[self.features]
        c = np.mean([b.predict(X, pred_contrib=True, num_iteration=b.best_iteration)
                     for b in self.boosters], axis=0)
        return c[:, :-1]

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({"boosters": [b.model_to_string() for b in self.boosters],
                         "cal": self.cal, "features": self.features, "meta": self.meta}, f)

    @classmethod
    def load(cls, path: str | Path) -> "BustModel":
        with open(path, "rb") as f:
            d = pickle.load(f)
        m = cls(features=d["features"], meta=d["meta"], cal=d["cal"])
        m.boosters = [lgb.Booster(model_str=s) for s in d["boosters"]]
        return m
