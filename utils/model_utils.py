"""ML model definitions, Elo rating, training helpers, and persistence.

All artifacts are league-scoped and carry metadata; loading refuses artifacts
whose league_key is not 'wnba' (never reuse NBA fitted models).
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path

# Avoid joblib's Windows core-probe subprocess in restricted/headless runtimes.
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

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
from scipy.stats import norm

from utils.league_config import get_league_config

try:
    import lightgbm as lgb
    _LGB_AVAILABLE = True
except (OSError, ImportError):  # pragma: no cover
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
    "off_rating_diff_L10",
    "three_rate_diff_L10",
    "home_possessions_L10", "away_possessions_L10",
    "home_offensive_rating_L10", "away_offensive_rating_L10",
    "home_roster_continuity", "away_roster_continuity",
    "roster_continuity_diff",
    "home_travel_miles", "away_travel_miles", "travel_diff",
    "home_timezone_shift_hours", "away_timezone_shift_hours", "timezone_shift_diff",
    "home_games_last_4_days", "away_games_last_4_days", "workload_diff",
    "home_is_cross_country", "away_is_cross_country",
    "is_early_start", "is_commissioners_cup", "is_playoff", "neutral_site",
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

def train_logistic_regression(
    X: pd.DataFrame, y: pd.Series, sample_weight: np.ndarray | pd.Series | None = None,
) -> Pipeline:
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(C=1.0, max_iter=1000, random_state=42)),
    ])
    fit_params = {"clf__sample_weight": sample_weight} if sample_weight is not None else {}
    pipe.fit(X, y, **fit_params)
    return pipe


def train_xgboost(
    X: pd.DataFrame, y: pd.Series, sample_weight: np.ndarray | pd.Series | None = None,
) -> xgb.XGBClassifier:
    model = xgb.XGBClassifier(
        max_depth=4, learning_rate=0.05, n_estimators=300,
        subsample=0.8, colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=5,
        eval_metric="logloss", random_state=42, verbosity=0,
    )
    model.fit(X, y, sample_weight=sample_weight)
    return model


def train_lightgbm(X: pd.DataFrame, y: pd.Series, sample_weight=None):
    if not _LGB_AVAILABLE:
        raise RuntimeError("LightGBM unavailable (libgomp missing).")
    model = lgb.LGBMClassifier(
        num_leaves=31, learning_rate=0.05, n_estimators=300,
        subsample=0.8, colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=1,
        random_state=42, verbosity=-1,
    )
    model.fit(X, y, sample_weight=sample_weight)
    return model


def train_random_forest(X: pd.DataFrame, y: pd.Series, sample_weight=None) -> RandomForestClassifier:
    model = RandomForestClassifier(
        n_estimators=300, max_depth=8, min_samples_leaf=10, max_features="sqrt",
        random_state=42, n_jobs=1,
    )
    model.fit(X, y, sample_weight=sample_weight)
    return model


def train_ensemble(X: pd.DataFrame, y: pd.Series, sample_weight=None) -> dict:
    models: dict = {}
    models["logistic"] = train_logistic_regression(X, y, sample_weight)
    models["xgboost"] = train_xgboost(X, y, sample_weight)
    if _LGB_AVAILABLE:
        models["lightgbm"] = train_lightgbm(X, y, sample_weight)
    models["random_forest"] = train_random_forest(X, y, sample_weight)
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
            aligned = align_model_input(model, X)
            p = model.predict_proba(aligned)[:, 1]
            probs += wt * p
            total += wt
        except Exception:
            pass
    return probs / total if total > 0 else probs


def align_model_input(model, X: pd.DataFrame) -> pd.DataFrame:
    """Align current canonical features to an artifact's fitted feature order."""
    names = getattr(model, "feature_names_in_", None)
    if names is None and hasattr(model, "estimator"):
        names = getattr(model.estimator, "feature_names_in_", None)
    if names is None and hasattr(model, "get_booster"):
        try:
            names = model.get_booster().feature_names
        except Exception:
            names = None
    if names is None:
        return X
    return X.reindex(columns=list(names), fill_value=0.0).astype(float)


# ── Evaluation ─────────────────────────────────────────────────────────────────

def evaluate_model(y_true, y_prob: np.ndarray, threshold: float = 0.5) -> dict:
    y_pred = (np.asarray(y_prob) >= threshold).astype(int)
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "log_loss": round(float(log_loss(y_true, y_prob)), 4),
        "brier_score": round(float(brier_score_loss(y_true, y_prob)), 4),
    }


def calibration_report(y_true, y_prob, bins: int = 10) -> dict:
    """Reliability bins plus ECE and maximum calibration error."""
    truth = np.asarray(y_true, dtype=int)
    probability = np.clip(np.asarray(y_prob, dtype=float), 0.0, 1.0)
    if truth.size == 0:
        return {"ece": None, "mce": None, "bins": []}
    edges = np.linspace(0.0, 1.0, bins + 1)
    assignments = np.clip(np.digitize(probability, edges[1:-1], right=True), 0, bins - 1)
    records: list[dict] = []
    weighted_error = 0.0
    maximum_error = 0.0
    for index in range(bins):
        mask = assignments == index
        if not np.any(mask):
            continue
        predicted = float(np.mean(probability[mask]))
        observed = float(np.mean(truth[mask]))
        error = abs(predicted - observed)
        weighted_error += float(np.mean(mask)) * error
        maximum_error = max(maximum_error, error)
        records.append({
            "lower": round(float(edges[index]), 3),
            "upper": round(float(edges[index + 1]), 3),
            "n": int(mask.sum()),
            "mean_probability": round(predicted, 4),
            "observed_rate": round(observed, 4),
            "absolute_error": round(error, 4),
        })
    return {"ece": round(weighted_error, 4), "mce": round(maximum_error, 4), "bins": records}


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


def season_recency_weights(
    seasons: pd.Series,
    *,
    reference_season: int | None = None,
    half_life_seasons: float = 2.0,
) -> np.ndarray:
    """Exponential recency weights with a one-season minimum floor."""
    numeric = pd.to_numeric(seasons, errors="coerce")
    reference = int(reference_season or numeric.max())
    age = (reference - numeric.fillna(reference)).clip(lower=0)
    weights = np.exp(-math.log(2.0) * age / max(float(half_life_seasons), 0.25))
    return np.asarray(np.clip(weights, 0.08, 1.0), dtype=float)


def expanding_season_eval(
    df: pd.DataFrame,
    *,
    feature_cols: list[str] | None = None,
    minimum_train_seasons: int = 2,
    half_life_seasons: float = 2.0,
) -> pd.DataFrame:
    """Evaluate on each season using only earlier seasons for training."""
    if "season" not in df.columns:
        raise ValueError("expanding_season_eval requires a season column")
    data = df.sort_values(["season", "game_date"]).reset_index(drop=True)
    seasons = sorted(int(s) for s in pd.to_numeric(data["season"], errors="coerce").dropna().unique())
    records: list[dict] = []
    for test_season in seasons[minimum_train_seasons:]:
        train = data[pd.to_numeric(data["season"], errors="coerce") < test_season]
        test = data[pd.to_numeric(data["season"], errors="coerce") == test_season]
        if train.empty or test.empty or train["target"].nunique() < 2:
            continue
        X_train, cols = get_model_features(train, feature_cols)
        X_test = test.reindex(columns=cols, fill_value=0.0).astype(float)
        weights = season_recency_weights(
            train["season"], reference_season=test_season, half_life_seasons=half_life_seasons
        )
        models = train_ensemble(X_train, train["target"].astype(int), weights)
        probs = ensemble_predict_proba(models, X_test)
        metrics = evaluate_model(test["target"].astype(int), probs)
        metrics.update({
            "train_through": int(test_season - 1),
            "test_season": int(test_season),
            "n_train": int(len(train)),
            "n_test": int(len(test)),
        })
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

def train_margin_model(
    df: pd.DataFrame,
    feature_cols: list[str] | None = None,
    sample_weight: np.ndarray | pd.Series | None = None,
) -> xgb.XGBRegressor:
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
    weights = None
    if sample_weight is not None:
        weights = np.asarray(sample_weight)[subset.index]
    model.fit(X, y, sample_weight=weights)
    return model


def train_totals_model(
    df: pd.DataFrame,
    feature_cols: list[str] | None = None,
    sample_weight: np.ndarray | pd.Series | None = None,
) -> xgb.XGBRegressor:
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
    weights = None
    if sample_weight is not None:
        weights = np.asarray(sample_weight)[subset.index]
    model.fit(X, y, sample_weight=weights)
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


@dataclass
class DistributionCalibrator:
    """Empirical residual calibrator for one continuous target."""

    target: str
    residual_mean: float
    residual_sd: float
    q05: float
    q95: float
    fitted_rows: int

    @classmethod
    def fit(cls, target: str, y_true, y_pred) -> "DistributionCalibrator":
        residual = np.asarray(y_true, dtype=float) - np.asarray(y_pred, dtype=float)
        residual = residual[np.isfinite(residual)]
        if residual.size == 0:
            return cls(target, 0.0, 10.0, -16.45, 16.45, 0)
        sd = float(np.std(residual, ddof=1)) if residual.size > 1 else 10.0
        return cls(
            target=target,
            residual_mean=float(np.mean(residual)),
            residual_sd=max(sd, 0.5),
            q05=float(np.quantile(residual, 0.05)),
            q95=float(np.quantile(residual, 0.95)),
            fitted_rows=int(residual.size),
        )

    def predict(self, point_prediction) -> dict[str, np.ndarray]:
        mean = np.asarray(point_prediction, dtype=float) + self.residual_mean
        return {
            "mean": mean,
            "sd": np.repeat(self.residual_sd, len(np.atleast_1d(mean))),
            "low": np.asarray(point_prediction, dtype=float) + self.q05,
            "high": np.asarray(point_prediction, dtype=float) + self.q95,
        }

    def to_dict(self) -> dict:
        return asdict(self)


def save_distribution_calibrator(
    calibrator: DistributionCalibrator, name: str, suffix: str = "latest"
) -> Path:
    d = model_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}_distribution_cal_{suffix}.json"
    path.write_text(json.dumps(calibrator.to_dict(), indent=2), encoding="utf-8")
    return path


def load_distribution_calibrator(name: str, suffix: str = "latest") -> DistributionCalibrator | None:
    path = model_dir() / f"{name}_distribution_cal_{suffix}.json"
    if not path.exists():
        return None
    try:
        return DistributionCalibrator(**json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None


def gaussian_crps(y_true, mean, sd) -> float:
    """Mean continuous ranked probability score for Normal forecasts."""
    y = np.asarray(y_true, dtype=float)
    mu = np.asarray(mean, dtype=float)
    sigma = np.maximum(np.asarray(sd, dtype=float), 1e-6)
    z = (y - mu) / sigma
    score = sigma * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / math.sqrt(math.pi))
    return float(np.mean(score))


def evaluate_distribution(
    y_true, point_prediction, calibrator: DistributionCalibrator,
) -> dict:
    pred = calibrator.predict(point_prediction)
    y = np.asarray(y_true, dtype=float)
    return {
        "mae": round(float(mean_absolute_error(y, pred["mean"])), 3),
        "rmse": round(float(np.sqrt(np.mean((y - pred["mean"]) ** 2))), 3),
        "crps": round(gaussian_crps(y, pred["mean"], pred["sd"]), 3),
        "interval_90_coverage": round(float(np.mean((y >= pred["low"]) & (y <= pred["high"]))), 3),
        "residual_sd": round(float(calibrator.residual_sd), 3),
    }


def population_stability_index(reference, current, bins: int = 10) -> float:
    """Population Stability Index for automatic artifact drift checks."""
    ref = np.asarray(reference, dtype=float)
    cur = np.asarray(current, dtype=float)
    ref, cur = ref[np.isfinite(ref)], cur[np.isfinite(cur)]
    if ref.size < 20 or cur.size < 20:
        return 0.0
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    ref_p = np.histogram(ref, bins=edges)[0] / ref.size
    cur_p = np.histogram(cur, bins=edges)[0] / cur.size
    ref_p, cur_p = np.clip(ref_p, 1e-6, None), np.clip(cur_p, 1e-6, None)
    return float(np.sum((cur_p - ref_p) * np.log(cur_p / ref_p)))


def drift_report(reference: pd.DataFrame, current: pd.DataFrame, feature_cols: list[str]) -> dict:
    values: dict[str, float] = {}
    for col in feature_cols:
        if col in reference.columns and col in current.columns:
            values[col] = round(population_stability_index(reference[col], current[col]), 4)
    max_psi = max(values.values(), default=0.0)
    return {
        "max_psi": round(max_psi, 4),
        "warning_features": [key for key, value in values.items() if value >= 0.1],
        "suspended": bool(max_psi >= 0.25),
        "feature_psi": values,
    }


def release_gate(
    *,
    holdout_season: int | None,
    holdout_rows: int,
    priced_bets: int,
    distinct_games: int = 0,
    priced_by_market: dict[str, int] | None = None,
    mean_clv: float | None,
    drift_suspended: bool,
    required_holdout_season: int = 2025,
    minimum_evaluation_bets: int = 100,
    minimum_evaluation_games: int = 40,
    minimum_bets_per_market: int = 25,
    minimum_priced_bets: int = 300,
) -> dict:
    """Encode the audit's production release gate; failure means paper-only."""
    priced_by_market = priced_by_market or {}
    checks = {
        "untouched_2025_holdout": holdout_season == required_holdout_season and holdout_rows > 0,
        "limited_paper_sample": int(priced_bets) >= minimum_evaluation_bets,
        "limited_paper_games": int(distinct_games) >= minimum_evaluation_games,
        "limited_paper_market_coverage": all(
            int(priced_by_market.get(market, 0)) >= minimum_bets_per_market
            for market in ("moneyline", "spread", "total")
        ),
        "minimum_300_priced_bets": int(priced_bets) >= minimum_priced_bets,
        "positive_clv": mean_clv is not None and float(mean_clv) > 0,
        "drift_clear": not bool(drift_suspended),
    }
    production_checks = (
        "untouched_2025_holdout", "minimum_300_priced_bets", "positive_clv", "drift_clear"
    )
    evaluation_checks = (
        "untouched_2025_holdout", "limited_paper_sample", "limited_paper_games",
        "limited_paper_market_coverage", "drift_clear"
    )
    passed = all(checks[key] for key in production_checks)
    evaluation_ready = all(checks[key] for key in evaluation_checks)
    return {
        "status": "production_ready" if passed else "limited_paper" if evaluation_ready else "shadow_only",
        "passed": passed,
        "evaluation_ready": evaluation_ready,
        "paper_only": not passed,
        "checks": checks,
        "holdout_season": holdout_season,
        "holdout_rows": int(holdout_rows),
        "priced_bets": int(priced_bets),
        "mean_clv": None if mean_clv is None else round(float(mean_clv), 5),
        "drift_suspended": bool(drift_suspended),
    }


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
