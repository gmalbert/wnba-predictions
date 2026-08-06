"""ML model definitions, Elo rating, training helpers, and persistence.

All artifacts are league-scoped and carry metadata; loading refuses artifacts
whose league_key is not 'wnba' (never reuse NBA fitted models).
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from utils.league_config import get_league_config

try:
    import lightgbm as lgb
    _LGB_AVAILABLE = True
except OSError:  # pragma: no cover
    lgb = None  # type: ignore[assignment]
    _LGB_AVAILABLE = False

_CFG = get_league_config()


def model_dir() -> Path:
    return _CFG.storage_namespace("model_artifacts")


def _artifact_metadata(**extra) -> dict:
    meta = {
        "league_key": _CFG.league_key,
        "season_format": _CFG.season_format,
        "regulation_minutes": _CFG.regulation_minutes,
        "normalization_minutes": _CFG.normalization_minutes,
        "current_season": _CFG.current_season,
    }
    meta.update(extra)
    return meta


def _verify_artifact(meta: dict) -> None:
    if meta.get("league_key") != _CFG.league_key:
        raise ValueError(
            f"Model artifact league mismatch: expected '{_CFG.league_key}', "
            f"found '{meta.get('league_key')}'. Refusing to load NBA artifacts."
        )


# ── Feature columns (WNBA canonical) ───────────────────────────────────────────

FEATURE_COLS_GAME = [
    "home_win_pct_season", "away_win_pct_season",
    "home_win_pct_L10", "away_win_pct_L10",
    "home_win_pct_L5", "away_win_pct_L5",
    "home_points_L10", "away_points_L10",
    "home_efg_pct_L10", "away_efg_pct_L10",
    "home_tov_pct_L10", "away_tov_pct_L10",
    "home_oreb_rate_L10", "away_oreb_rate_L10",
    "home_assists_L10", "away_assists_L10",
    "home_rest_days", "away_rest_days",
    "home_is_b2b", "away_is_b2b",
    "home_streak", "away_streak",
    "win_pct_diff",
    "pts_diff_L10",
    "rest_diff",
    "streak_diff",
    "efg_diff_L10",
    "tov_diff_L10",
    "oreb_diff_L10",
    "pace_diff_L10",
]

# Regression target columns
FEATURE_COLS_MARGIN = [c for c in FEATURE_COLS_GAME if not c.startswith("home_win") and c != "win_pct_diff"]
FEATURE_COLS_TOTALS = FEATURE_COLS_MARGIN


# ── Elo rating system ──────────────────────────────────────────────────────────

class EloSystem:
    """WNBA Elo with home-court advantage and margin-of-victory scaling."""

    def __init__(
        self,
        k: float = 20.0,
        home_advantage: float = 100.0,
        mov_scale: bool = True,
        season_carryover: float = 0.75,
        initial_rating: float = 1500.0,
    ):
        self.k = k
        self.home_advantage = home_advantage
        self.mov_scale = mov_scale
        self.season_carryover = season_carryover
        self.initial_rating = initial_rating
        self.ratings: dict[int, float] = {}

    def get_rating(self, team_id: int) -> float:
        return self.ratings.get(team_id, self.initial_rating)

    def win_probability(self, team_a_id: int, team_b_id: int, a_is_home: bool = True) -> float:
        ra = self.get_rating(team_a_id) + (self.home_advantage if a_is_home else 0)
        rb = self.get_rating(team_b_id) + (self.home_advantage if not a_is_home else 0)
        return 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))

    def _mov_multiplier(self, margin: float, winner_elo_diff: float) -> float:
        return np.log(abs(margin) + 1) * (2.2 / (winner_elo_diff * 0.001 + 2.2))

    def update(self, home_team_id: int, away_team_id: int, home_score: int, away_score: int):
        p_home = self.win_probability(home_team_id, away_team_id, a_is_home=True)
        home_win = int(home_score > away_score)
        margin = abs(home_score - away_score)

        k = self.k
        if self.mov_scale and margin > 0:
            elo_diff = self.get_rating(home_team_id) - self.get_rating(away_team_id)
            winner_diff = elo_diff if home_win else -elo_diff
            k *= self._mov_multiplier(margin, winner_diff)

        delta = k * (home_win - p_home)
        self.ratings[home_team_id] = self.get_rating(home_team_id) + delta
        self.ratings[away_team_id] = self.get_rating(away_team_id) - delta

    def new_season(self):
        for tid in self.ratings:
            self.ratings[tid] = (
                self.ratings[tid] * self.season_carryover
                + self.initial_rating * (1.0 - self.season_carryover)
            )

    def fit(self, games_df: pd.DataFrame) -> "EloSystem":
        """Fit on games with game_date, home_team_id, away_team_id, home_score, away_score, season."""
        df = games_df.sort_values("game_date").copy()
        df["game_date"] = pd.to_datetime(df["game_date"])
        prev_season = None
        for _, row in df.iterrows():
            season = str(row.get("season", ""))
            if season and prev_season and season != prev_season:
                self.new_season()
            prev_season = season
            self.update(
                int(row["home_team_id"]), int(row["away_team_id"]),
                int(row["home_score"]), int(row["away_score"]),
            )
        return self

    def get_all_ratings(self) -> pd.DataFrame:
        return (
            pd.DataFrame({"team_id": list(self.ratings.keys()), "elo": list(self.ratings.values())})
            .sort_values("elo", ascending=False)
            .reset_index(drop=True)
        )

    def save(self, path: str | Path | None = None) -> Path:
        path = Path(path) if path else model_dir() / "elo_system.pkl"
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        return path

    @classmethod
    def load(cls, path: str | Path | None = None) -> "EloSystem":
        path = Path(path) if path else model_dir() / "elo_system.pkl"
        return joblib.load(path)


# ── Feature extraction ─────────────────────────────────────────────────────────

def get_model_features(df: pd.DataFrame, feature_cols: list[str] | None = None) -> tuple[pd.DataFrame, list[str]]:
    cols = feature_cols or FEATURE_COLS_GAME
    available = [c for c in cols if c in df.columns]
    X = df[available].fillna(0).astype(float)
    return X, available


# ── Model builders ─────────────────────────────────────────────────────────────

def train_logistic_regression(X: pd.DataFrame, y: pd.Series) -> Pipeline:
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(C=1.0, max_iter=1000, random_state=42)),
    ])
    pipe.fit(X, y)
    return pipe


def train_xgboost(X: pd.DataFrame, y: pd.Series) -> xgb.XGBClassifier:
    model = xgb.XGBClassifier(
        max_depth=4, learning_rate=0.05, n_estimators=300,
        subsample=0.8, colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=5,
        eval_metric="logloss", random_state=42, verbosity=0,
    )
    model.fit(X, y)
    return model


def train_lightgbm(X: pd.DataFrame, y: pd.Series):
    if not _LGB_AVAILABLE:
        raise RuntimeError("LightGBM unavailable (libgomp missing).")
    model = lgb.LGBMClassifier(
        num_leaves=31, learning_rate=0.05, n_estimators=300,
        subsample=0.8, colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=1,
        random_state=42, verbosity=-1,
    )
    model.fit(X, y)
    return model


def train_random_forest(X: pd.DataFrame, y: pd.Series) -> RandomForestClassifier:
    model = RandomForestClassifier(
        n_estimators=300, max_depth=8, min_samples_leaf=10, max_features="sqrt",
        random_state=42, n_jobs=-1,
    )
    model.fit(X, y)
    return model


def train_ensemble(X: pd.DataFrame, y: pd.Series) -> dict:
    models: dict = {}
    models["logistic"] = train_logistic_regression(X, y)
    models["xgboost"] = train_xgboost(X, y)
    if _LGB_AVAILABLE:
        models["lightgbm"] = train_lightgbm(X, y)
    models["random_forest"] = train_random_forest(X, y)
    return models


DEFAULT_WEIGHTS = {
    "logistic": 0.15,
    "xgboost": 0.35,
    "lightgbm": 0.35,
    "random_forest": 0.15,
}


def ensemble_predict_proba(models: dict, X: pd.DataFrame, weights: dict | None = None) -> np.ndarray:
    w = weights or DEFAULT_WEIGHTS
    probs = np.zeros(len(X))
    total = 0.0
    for name, model in models.items():
        wt = w.get(name, 0.25)
        try:
            p = model.predict_proba(X)[:, 1]
            probs += wt * p
            total += wt
        except Exception:
            pass
    return probs / total if total > 0 else probs


# ── Evaluation ─────────────────────────────────────────────────────────────────

def evaluate_model(y_true, y_prob: np.ndarray, threshold: float = 0.5) -> dict:
    y_pred = (np.asarray(y_prob) >= threshold).astype(int)
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "log_loss": round(float(log_loss(y_true, y_prob)), 4),
        "brier_score": round(float(brier_score_loss(y_true, y_prob)), 4),
    }


def walk_forward_eval(df: pd.DataFrame, n_splits: int = 5, feature_cols: list[str] | None = None) -> pd.DataFrame:
    """TimeSeriesSplit walk-forward evaluation (chronological, no random splits)."""
    df = df.sort_values("game_date").reset_index(drop=True)
    X, cols = get_model_features(df, feature_cols)
    y = df["target"]

    tscv = TimeSeriesSplit(n_splits=n_splits)
    records = []
    for fold, (train_idx, test_idx) in enumerate(tscv.split(X)):
        X_tr, X_te = X.iloc[train_idx], X.iloc[test_idx]
        y_tr, y_te = y.iloc[train_idx], y.iloc[test_idx]
        if len(y_te) == 0:
            continue
        models = train_ensemble(X_tr, y_tr)
        probs = ensemble_predict_proba(models, X_te)
        metrics = evaluate_model(y_te, probs)
        metrics["fold"] = fold + 1
        metrics["n_test"] = len(y_te)
        records.append(metrics)
    return pd.DataFrame(records)


# ── Feature importance ─────────────────────────────────────────────────────────

def get_feature_importance(model, feature_cols: list[str]) -> pd.DataFrame:
    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
    elif hasattr(model, "named_steps"):
        clf = model.named_steps.get("clf")
        if hasattr(clf, "coef_"):
            importances = np.abs(clf.coef_[0])
        else:
            return pd.DataFrame(columns=["feature", "importance"])
    else:
        return pd.DataFrame(columns=["feature", "importance"])
    n = min(len(importances), len(feature_cols))
    return (
        pd.DataFrame({"feature": feature_cols[:n], "importance": importances[:n]})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )


# ── Persistence ────────────────────────────────────────────────────────────────

def save_models(models: dict, suffix: str = "latest") -> dict:
    d = model_dir()
    d.mkdir(parents=True, exist_ok=True)
    saved = {}
    for name, model in models.items():
        path = d / f"{name}_game_{suffix}.pkl"
        joblib.dump(model, path)
        saved[name] = str(path)
    (d / "metadata.json").write_text(
        json.dumps(_artifact_metadata(model_suffix=suffix), indent=2), encoding="utf-8"
    )
    return saved


def load_models(suffix: str = "latest") -> dict:
    d = model_dir()
    models = {}
    for name in ["logistic", "xgboost", "lightgbm", "random_forest"]:
        if name == "lightgbm" and not _LGB_AVAILABLE:
            continue
        path = d / f"{name}_game_{suffix}.pkl"
        if path.exists():
            try:
                models[name] = joblib.load(path)
            except Exception:
                pass
    return models


def load_eval_metrics() -> dict:
    path = model_dir() / "eval_metrics.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_eval_metrics(metrics: dict) -> Path:
    d = model_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / "eval_metrics.json"
    path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return path


# ── Regression models (margin / total) ────────────────────────────────────────

def train_margin_model(df: pd.DataFrame, feature_cols: list[str] | None = None) -> xgb.XGBRegressor:
    cols = feature_cols or FEATURE_COLS_MARGIN
    avail = [c for c in cols if c in df.columns]
    if "margin" not in df.columns:
        raise ValueError("DataFrame must contain 'margin'. Run build_training_dataset() first.")
    subset = df.dropna(subset=["margin"]).copy()
    X = subset[avail].fillna(subset[avail].median()).astype(float)
    y = subset["margin"].astype(float)
    model = xgb.XGBRegressor(
        max_depth=4, learning_rate=0.05, n_estimators=300,
        subsample=0.8, colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=5,
        random_state=42, verbosity=0,
    )
    model.fit(X, y)
    return model


def train_totals_model(df: pd.DataFrame, feature_cols: list[str] | None = None) -> xgb.XGBRegressor:
    cols = feature_cols or FEATURE_COLS_TOTALS
    avail = [c for c in cols if c in df.columns]
    if "total_points" not in df.columns:
        raise ValueError("DataFrame must contain 'total_points'. Run build_training_dataset() first.")
    subset = df.dropna(subset=["total_points"]).copy()
    X = subset[avail].fillna(subset[avail].median()).astype(float)
    y = subset["total_points"].astype(float)
    model = xgb.XGBRegressor(
        max_depth=4, learning_rate=0.05, n_estimators=300,
        subsample=0.8, colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=5,
        random_state=42, verbosity=0,
    )
    model.fit(X, y)
    return model


def evaluate_regression(model, df: pd.DataFrame, target_col: str, feature_cols: list[str] | None = None) -> dict:
    cols = feature_cols or FEATURE_COLS_MARGIN
    avail = [c for c in cols if c in df.columns]
    subset = df.dropna(subset=[target_col]).copy()
    if subset.empty:
        return {}
    X = subset[avail].fillna(0).astype(float)
    y_true = subset[target_col].values
    y_pred = model.predict(X)
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    return {f"{target_col}_mae": round(mae, 2), f"{target_col}_rmse": round(rmse, 2)}


def save_regression_model(model, name: str, suffix: str = "latest") -> Path:
    d = model_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}_{suffix}.pkl"
    joblib.dump(model, path)
    return path


def load_regression_model(name: str, suffix: str = "latest"):
    path = model_dir() / f"{name}_{suffix}.pkl"
    if not path.exists():
        return None
    try:
        return joblib.load(path)
    except Exception:
        return None


# ── Calibration ────────────────────────────────────────────────────────────────

def calibrate_models(models: dict, X_cal: pd.DataFrame, y_cal: pd.Series, method: str = "isotonic") -> dict:
    calibrated: dict = {}
    for name, model in models.items():
        try:
            cal = CalibratedClassifierCV(estimator=model, cv="prefit", method=method)
            cal.fit(X_cal, y_cal)
            calibrated[name] = cal
        except Exception:
            calibrated[name] = model
    return calibrated


def save_calibrated_models(models: dict, suffix: str = "latest") -> dict:
    d = model_dir()
    d.mkdir(parents=True, exist_ok=True)
    saved = {}
    for name, model in models.items():
        path = d / f"{name}_game_cal_{suffix}.pkl"
        joblib.dump(model, path)
        saved[name] = str(path)
    return saved


def load_calibrated_models(suffix: str = "latest") -> dict:
    d = model_dir()
    models = {}
    for name in ["logistic", "xgboost", "lightgbm", "random_forest"]:
        cal_path = d / f"{name}_game_cal_{suffix}.pkl"
        base_path = d / f"{name}_game_{suffix}.pkl"
        for p in (cal_path, base_path):
            if p.exists():
                try:
                    models[name] = joblib.load(p)
                    break
                except Exception:
                    pass
    return models
