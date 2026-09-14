"""Frozen paper ledger, market-relative scoring, CLV, and replay summaries."""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from utils.data_contracts import BET_LEDGER_COLUMNS
from utils.league_config import get_league_config


def ledger_path() -> Path:
    return get_league_config().storage_namespace("evaluation", "paper_bet_ledger.parquet")


def load_bet_ledger() -> pd.DataFrame:
    path = ledger_path()
    if not path.exists():
        return pd.DataFrame(columns=BET_LEDGER_COLUMNS)
    try:
        return pd.read_parquet(path).reindex(columns=BET_LEDGER_COLUMNS)
    except Exception:
        return pd.DataFrame(columns=BET_LEDGER_COLUMNS)


def _id(*parts: object) -> str:
    value = "|".join(str(part) for part in parts)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def american_implied_probability(price: object) -> float | None:
    try:
        value = float(price)
    except (TypeError, ValueError):
        return None
    if value == 0:
        return None
    return 100 / (value + 100) if value > 0 else abs(value) / (abs(value) + 100)


def american_profit(price: object, stake: float = 1.0) -> float:
    value = float(price)
    return stake * value / 100 if value > 0 else stake * 100 / abs(value)


def _normal_over_probability(mean: float, sd: float, line: float) -> float:
    return float(1.0 - norm.cdf(float(line), loc=float(mean), scale=max(float(sd), 0.25)))


def freeze_prediction_ledger(
    predictions: pd.DataFrame,
    *,
    horizon: str,
    frozen_at: str | None = None,
) -> pd.DataFrame:
    """Append immutable, flat-stake paper decisions for every priced market."""
    if predictions is None or predictions.empty:
        return load_bet_ledger()
    frozen_at = frozen_at or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    rows: list[dict] = []
    for _, pred in predictions.iterrows():
        common = {
            "prediction_id": pred.get("prediction_id"),
            "game_id": str(pred.get("game_id", "")),
            "game_date": pred.get("game_date"),
            "frozen_at": frozen_at,
            "horizon": horizon,
            "book": "consensus",
            "stake_units": 1.0,
            "result": None,
            "profit_units": None,
            "status": "open",
            "paper_only": True,
            "model_version": pred.get("model_version"),
            "closing_price": None,
            "closing_line": None,
            "clv": None,
        }

        market_prob = pd.to_numeric(pred.get("market_home_prob"), errors="coerce")
        if pd.notna(market_prob):
            home_prob = float(pred.get("home_win_prob", 0.5))
            select_home = home_prob >= float(market_prob)
            selection = pred.get("home_team") if select_home else pred.get("away_team")
            model_prob = home_prob if select_home else 1.0 - home_prob
            rows.append({
                **common,
                "ledger_id": _id(pred.get("prediction_id"), horizon, "moneyline", selection),
                "market": "moneyline",
                "selection": selection,
                "model_probability": model_prob,
                "model_line": None,
                "price": None,
                "market_line": float(market_prob) if select_home else 1.0 - float(market_prob),
            })

        market_spread = pd.to_numeric(pred.get("market_spread"), errors="coerce")
        margin_mean = pd.to_numeric(pred.get("margin_mean", pred.get("predicted_spread")), errors="coerce")
        margin_sd = pd.to_numeric(pred.get("margin_sd"), errors="coerce")
        if pd.notna(market_spread) and pd.notna(margin_mean) and pd.notna(margin_sd):
            home_cover = _normal_over_probability(float(margin_mean), float(margin_sd), -float(market_spread))
            select_home = home_cover >= 0.5
            selection = pred.get("home_team") if select_home else pred.get("away_team")
            rows.append({
                **common,
                "ledger_id": _id(pred.get("prediction_id"), horizon, "spread", selection),
                "market": "spread",
                "selection": selection,
                "model_probability": home_cover if select_home else 1.0 - home_cover,
                "model_line": -float(margin_mean),
                "price": -110,
                "market_line": float(market_spread) if select_home else -float(market_spread),
            })

        market_total = pd.to_numeric(pred.get("market_total"), errors="coerce")
        total_mean = pd.to_numeric(pred.get("total_mean", pred.get("predicted_total")), errors="coerce")
        total_sd = pd.to_numeric(pred.get("total_sd"), errors="coerce")
        if pd.notna(market_total) and pd.notna(total_mean) and pd.notna(total_sd):
            over_prob = _normal_over_probability(float(total_mean), float(total_sd), float(market_total))
            selection = "Over" if over_prob >= 0.5 else "Under"
            rows.append({
                **common,
                "ledger_id": _id(pred.get("prediction_id"), horizon, "total", selection),
                "market": "total",
                "selection": selection,
                "model_probability": max(over_prob, 1.0 - over_prob),
                "model_line": float(total_mean),
                "price": -110,
                "market_line": float(market_total),
            })

    if not rows:
        return load_bet_ledger()
    incoming = pd.DataFrame(rows).reindex(columns=BET_LEDGER_COLUMNS)
    existing = load_bet_ledger()
    combined = pd.concat([existing, incoming], ignore_index=True).drop_duplicates("ledger_id", keep="first")
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(path, index=False)
    return combined


def attach_closing_lines(ledger: pd.DataFrame, closing_odds: pd.DataFrame) -> pd.DataFrame:
    """Attach close data without changing any frozen forecast/price fields."""
    if ledger is None or ledger.empty or closing_odds is None or closing_odds.empty:
        return ledger.copy() if ledger is not None else pd.DataFrame(columns=BET_LEDGER_COLUMNS)
    result = ledger.copy()
    closing = closing_odds.copy()
    if "is_closing" in closing.columns and closing["is_closing"].fillna(False).any():
        closing = closing[closing["is_closing"].fillna(False)]
    for idx, bet in result[result["status"].eq("open")].iterrows():
        game = closing[closing["canonical_game_id"].astype(str) == str(bet["game_id"])]
        if game.empty:
            continue
        market_name = {"moneyline": "h2h", "spread": "spreads", "total": "totals"}.get(bet["market"])
        market = game[game["market"] == market_name]
        if market.empty:
            continue
        selection = str(bet["selection"])
        if bet["market"] == "moneyline":
            row = market[market["name"].astype(str) == selection]
            if row.empty:
                continue
            close_price = pd.to_numeric(row["price"], errors="coerce").mean()
            close_prob = american_implied_probability(close_price)
            frozen_prob = pd.to_numeric(bet["market_line"], errors="coerce")
            result.at[idx, "closing_price"] = close_price
            result.at[idx, "clv"] = float(frozen_prob - close_prob) if close_prob is not None and pd.notna(frozen_prob) else None
        else:
            name = selection if bet["market"] == "spread" else selection
            row = market[market["name"].astype(str).str.lower() == str(name).lower()]
            if row.empty:
                continue
            close_line = pd.to_numeric(row["point"], errors="coerce").mean()
            frozen_line = pd.to_numeric(bet["market_line"], errors="coerce")
            direction = 1.0 if bet["market"] == "spread" or selection.lower() == "over" else -1.0
            result.at[idx, "closing_line"] = close_line
            result.at[idx, "clv"] = direction * float(frozen_line - close_line) if pd.notna(frozen_line) else None
    return result.reindex(columns=BET_LEDGER_COLUMNS)


def grade_ledger(ledger: pd.DataFrame, completed_games: pd.DataFrame) -> pd.DataFrame:
    """Grade completed flat-stake paper bets.  Pushes return zero units."""
    if ledger is None or ledger.empty or completed_games is None or completed_games.empty:
        return ledger.copy() if ledger is not None else pd.DataFrame(columns=BET_LEDGER_COLUMNS)
    result = ledger.copy()
    games = completed_games.copy()
    game_key = "canonical_game_id" if "canonical_game_id" in games.columns else "game_id"
    for idx, bet in result[result["status"].eq("open")].iterrows():
        match = games[games[game_key].astype(str) == str(bet["game_id"])]
        if match.empty:
            continue
        game = match.iloc[-1]
        home_score = pd.to_numeric(game.get("home_score"), errors="coerce")
        away_score = pd.to_numeric(game.get("away_score"), errors="coerce")
        if pd.isna(home_score) or pd.isna(away_score):
            continue
        home_name, away_name = str(game.get("home_team", "")), str(game.get("away_team", ""))
        margin, total = float(home_score - away_score), float(home_score + away_score)
        result_code = "push"
        if bet["market"] == "moneyline":
            winner = home_name if margin > 0 else away_name
            result_code = "win" if str(bet["selection"]) == winner else "loss"
        elif bet["market"] == "spread":
            is_home = str(bet["selection"]) == home_name
            covered_margin = margin + float(bet["market_line"]) if is_home else -margin + float(bet["market_line"])
            result_code = "win" if covered_margin > 0 else "loss" if covered_margin < 0 else "push"
        elif bet["market"] == "total":
            delta = total - float(bet["market_line"])
            if delta != 0:
                result_code = "win" if (delta > 0) == (str(bet["selection"]).lower() == "over") else "loss"
        stake = float(bet.get("stake_units") or 1.0)
        price = bet.get("price") if pd.notna(bet.get("price")) else -110
        profit = american_profit(price, stake) if result_code == "win" else -stake if result_code == "loss" else 0.0
        result.at[idx, "result"] = result_code
        result.at[idx, "profit_units"] = profit
        result.at[idx, "status"] = "graded"
    return result.reindex(columns=BET_LEDGER_COLUMNS)


def save_bet_ledger(ledger: pd.DataFrame) -> Path:
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger.reindex(columns=BET_LEDGER_COLUMNS).to_parquet(path, index=False)
    return path


def ledger_summary(ledger: pd.DataFrame | None = None) -> dict:
    ledger = load_bet_ledger() if ledger is None else ledger
    if ledger.empty:
        return {
            "priced_bets": 0, "graded_bets": 0, "mean_clv": None,
            "distinct_games": 0, "priced_by_market": {}, "roi": None,
            "profit_units": 0.0, "by_market": [],
        }
    priced = ledger[ledger["market_line"].notna()]
    graded = ledger[ledger["status"].eq("graded")]
    stakes = pd.to_numeric(graded["stake_units"], errors="coerce").sum()
    profit = pd.to_numeric(graded["profit_units"], errors="coerce").sum()
    clv = pd.to_numeric(priced["clv"], errors="coerce").dropna()
    by_market = []
    for market, group in graded.groupby("market"):
        group_stakes = pd.to_numeric(group["stake_units"], errors="coerce").sum()
        group_profit = pd.to_numeric(group["profit_units"], errors="coerce").sum()
        by_market.append({
            "market": market,
            "bets": int(len(group)),
            "profit_units": round(float(group_profit), 3),
            "roi": round(float(group_profit / group_stakes), 4) if group_stakes else None,
        })
    priced_by_market = {
        str(market): int(len(group))
        for market, group in priced.groupby("market")
    }
    return {
        "priced_bets": int(len(priced)),
        "graded_bets": int(len(graded)),
        "distinct_games": int(priced["game_id"].nunique()),
        "priced_by_market": priced_by_market,
        "mean_clv": round(float(clv.mean()), 5) if not clv.empty else None,
        "roi": round(float(profit / stakes), 4) if stakes else None,
        "profit_units": round(float(profit), 3),
        "by_market": by_market,
    }


def evaluate_market_baseline(scored: pd.DataFrame) -> dict:
    """Compare model winner probabilities to de-vigged market probabilities."""
    if scored is None or scored.empty:
        return {}
    result: dict = {}
    def metrics(prob: np.ndarray) -> dict:
        return {
            "accuracy": round(float(np.mean((prob >= 0.5) == y)), 4),
            "log_loss": round(float(-np.mean(y * np.log(prob) + (1 - y) * np.log(1 - prob))), 4),
            "brier_score": round(float(np.mean((prob - y) ** 2)), 4),
        }
    winner_needed = {"target", "home_win_prob", "market_home_prob"}
    if winner_needed.issubset(scored.columns):
        frame = scored.dropna(subset=list(winner_needed)).copy()
        if not frame.empty:
            y = frame["target"].astype(int).to_numpy()
            model = np.clip(frame["home_win_prob"].astype(float).to_numpy(), 1e-6, 1 - 1e-6)
            market = np.clip(frame["market_home_prob"].astype(float).to_numpy(), 1e-6, 1 - 1e-6)
            result["winner"] = {
                "n_priced": int(len(frame)), "model": metrics(model), "market": metrics(market)
            }
    if {"margin", "margin_prediction", "market_spread"}.issubset(scored.columns):
        frame = scored.dropna(subset=["margin", "margin_prediction", "market_spread"])
        if not frame.empty:
            actual = frame["margin"].astype(float).to_numpy()
            model_margin = frame["margin_prediction"].astype(float).to_numpy()
            market_margin = -frame["market_spread"].astype(float).to_numpy()
            result["spread"] = {
                "n_priced": int(len(frame)),
                "model_mae": round(float(np.mean(np.abs(actual - model_margin))), 4),
                "market_mae": round(float(np.mean(np.abs(actual - market_margin))), 4),
                "model_ats_accuracy": round(float(np.mean(np.sign(model_margin - market_margin) == np.sign(actual - market_margin))), 4),
            }
    if {"total_points", "total_prediction", "market_total"}.issubset(scored.columns):
        frame = scored.dropna(subset=["total_points", "total_prediction", "market_total"])
        if not frame.empty:
            actual = frame["total_points"].astype(float).to_numpy()
            model_total = frame["total_prediction"].astype(float).to_numpy()
            market_total = frame["market_total"].astype(float).to_numpy()
            result["total"] = {
                "n_priced": int(len(frame)),
                "model_mae": round(float(np.mean(np.abs(actual - model_total))), 4),
                "market_mae": round(float(np.mean(np.abs(actual - market_total))), 4),
                "model_side_accuracy": round(float(np.mean(np.sign(model_total - market_total) == np.sign(actual - market_total))), 4),
            }
    return result
