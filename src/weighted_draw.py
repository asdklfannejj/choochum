from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, List

def apply_eligibility(df: pd.DataFrame, expressions: List[str]) -> pd.DataFrame:
    if not expressions:
        return df
    out = df.copy()
    for expr in expressions:
        out = out.query(expr)
    return out

def factor_categorical(series: pd.Series, mapping: Dict[str, float], default: float) -> np.ndarray:
    return series.map(mapping).fillna(default).astype(float).to_numpy()

def factor_bucket(series: pd.Series, buckets: List[List[float]], default: float) -> np.ndarray:
    arr = series.astype(float).to_numpy()
    weights = np.full(arr.shape, default, dtype=float)
    for lo, hi, w in buckets:
        mask = (arr >= lo) & (arr <= hi)
        weights[mask] = w
    return weights

def compute_weights(df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
    defaults = config.get("defaults", {"categorical": 1.0, "bucket": 1.0})
    rules = config.get("weights", {})

    w = np.ones(len(df), dtype=float)

    for col, rule in rules.items():
        if col not in df.columns:
            continue
        rtype = rule.get("type", "categorical")
        if rtype == "categorical":
            mapping = rule.get("mapping", {})
            default = float(defaults.get("categorical", 1.0))
            w *= factor_categorical(df[col], mapping, default)
        elif rtype == "bucket":
            buckets = rule.get("buckets", [])
            default = float(defaults.get("bucket", 1.0))
            w *= factor_bucket(df[col], buckets, default)

    out = df.copy()
    out["___weight"] = w
    out.loc[out["___weight"] <= 0, "___weight"] = 1e-12
    return out

def draw_winners(df_weighted: pd.DataFrame, n_winners: int, unique_key: str, seed: int | None = None) -> pd.DataFrame:
    if unique_key not in df_weighted.columns:
        raise ValueError(f"unique_key '{unique_key}' column not found")

    base = df_weighted.drop_duplicates(subset=[unique_key], keep="last").reset_index(drop=True)
    weights = base["___weight"].to_numpy(dtype=float)
    if np.all(weights <= 0):
        raise ValueError("All weights are non-positive")

    probs = weights / weights.sum()
    rng = np.random.default_rng(seed)
    n = min(n_winners, len(base))
    idx = rng.choice(len(base), size=n, replace=False, p=probs)
    return base.iloc[idx].copy()

def run_raffle(df: pd.DataFrame, config: Dict[str, Any], n_winners: int, seed: int | None = None):
    eli_exprs = config.get("eligibility", [])
    df_eli = apply_eligibility(df, eli_exprs)
    df_w = compute_weights(df_eli, config)
    unique_key = config.get("unique_key", "고객ID")
    winners = draw_winners(df_w, n_winners, unique_key=unique_key, seed=seed)
    return {"eligible": df_eli, "weighted": df_w, "winners": winners}
