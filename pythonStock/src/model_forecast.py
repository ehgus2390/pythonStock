import numpy as np
import pandas as pd


MONTH_TRADING_DAYS = 21


def _calc_horizon_returns(future: np.ndarray, last_price: float, horizon_days: int) -> dict[str, float]:
    idx_map = {
        "ret_1m": min(20, horizon_days - 1),
        "ret_2m": min(41, horizon_days - 1),
        "ret_3m": min(62, horizon_days - 1),
        "ret_6m": min(125, horizon_days - 1),
        "ret_12m": min(251, horizon_days - 1),
    }
    out: dict[str, float] = {}
    for key, idx in idx_map.items():
        out[key] = (future[idx] / last_price - 1) * 100
    return out


def _compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def _make_dataset_from_close(close: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    close = close.astype(float)
    ret1 = close.pct_change()

    feat = pd.DataFrame(index=close.index)
    feat["ret_1d"] = ret1.shift(1)
    feat["ret_5d"] = close.pct_change(5).shift(1)
    feat["ret_20d"] = close.pct_change(20).shift(1)
    feat["vol_20d"] = ret1.rolling(20).std().shift(1)
    feat["dist_sma20"] = (close / close.rolling(20).mean() - 1).shift(1)
    feat["dist_sma60"] = (close / close.rolling(60).mean() - 1).shift(1)
    feat["rsi"] = (_compute_rsi(close) / 100.0).shift(1)

    target = ret1
    data = feat.join(target.rename("target")).dropna()
    if data.empty:
        return pd.DataFrame(), pd.Series(dtype=float)

    X = data.drop(columns=["target"])
    y = data["target"]
    return X, y


def _future_dates(last_index: pd.Timestamp, horizon_days: int) -> pd.DatetimeIndex:
    last_idx = pd.Timestamp(last_index)
    if last_idx.tzinfo is not None:
        last_idx = last_idx.tz_localize(None)
    return pd.bdate_range(last_idx + pd.Timedelta(days=1), periods=horizon_days)


def _build_result(df: pd.DataFrame, future: np.ndarray, model: str, mae: float, direction_acc: float) -> dict:
    horizon_days = len(future)
    last_price = float(df["Close"].iloc[-1])
    rets = _calc_horizon_returns(future, last_price, horizon_days)

    if rets["ret_12m"] >= 8:
        signal = "BUY"
        signal_label = "예상 매수지점"
    elif rets["ret_12m"] <= -8:
        signal = "SELL"
        signal_label = "예상 매도지점"
    else:
        signal = "HOLD"
        signal_label = "관망"

    if np.isnan(direction_acc):
        returns = df["Close"].astype(float).pct_change().dropna()
        vol = float(returns.std()) if len(returns) > 5 else 0.01
        confidence = min(95.0, max(5.0, abs(rets["ret_12m"]) / max(vol * 100 * np.sqrt(252), 0.1) * 100))
    else:
        confidence = max(5.0, min(95.0, direction_acc))

    forecast_path = pd.DataFrame(
        {"Forecast": future},
        index=_future_dates(pd.Timestamp(df.index[-1]), horizon_days),
    )

    return {
        "path": forecast_path,
        **rets,
        "signal": signal,
        "signal_label": signal_label,
        "confidence": confidence,
        "model": model,
        "mae": mae,
        "direction_acc": direction_acc,
    }


def _predict_chunk_baseline(close_values: np.ndarray, chunk_days: int) -> np.ndarray:
    x = np.arange(len(close_values), dtype=float)
    w = np.linspace(0.6, 1.4, len(close_values))
    slope, intercept = np.polyfit(x, close_values, 1, w=w)
    fx = np.arange(len(close_values), len(close_values) + chunk_days, dtype=float)
    chunk = np.maximum(intercept + slope * fx, 0.01)
    return chunk


def _baseline_forecast(df: pd.DataFrame, horizon_days: int = 252) -> dict | None:
    close = df["Close"].dropna().astype(float)
    if len(close) < 40:
        return None

    work = close.values.copy()
    future_parts = []
    remaining = horizon_days

    while remaining > 0:
        chunk_days = min(MONTH_TRADING_DAYS, remaining)
        chunk = _predict_chunk_baseline(work, chunk_days)
        future_parts.append(chunk)
        work = np.concatenate([work, chunk])
        remaining -= chunk_days

    future = np.concatenate(future_parts)
    return _build_result(df, future, model="baseline", mae=np.nan, direction_acc=np.nan)


def _fit_eval_model(close: pd.Series, model_name: str):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import Ridge

    X, y = _make_dataset_from_close(close)
    if len(X) < 120:
        return None, np.nan, np.nan

    split = int(len(X) * 0.8)
    split = max(60, min(split, len(X) - 20))
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    if model_name == "ridge":
        model = Ridge(alpha=1.0)
    elif model_name == "rf":
        model = RandomForestRegressor(n_estimators=300, max_depth=6, random_state=42, n_jobs=-1)
    else:
        return None, np.nan, np.nan

    model.fit(X_train, y_train)
    pred_test = pd.Series(model.predict(X_test), index=X_test.index)
    mae = float(np.mean(np.abs(y_test - pred_test))) * 100
    direction_acc = float((np.sign(y_test) == np.sign(pred_test)).mean() * 100)
    return model, mae, direction_acc


def _sequential_ml(df: pd.DataFrame, model_name: str, horizon_days: int) -> dict | None:
    try:
        _ = __import__("sklearn")
    except Exception:
        return None

    close = df["Close"].dropna().astype(float)
    if len(close) < 120:
        return None

    _, mae, direction_acc = _fit_eval_model(close, model_name)

    work = close.copy()
    future_parts = []
    remaining = horizon_days

    while remaining > 0:
        chunk_days = min(MONTH_TRADING_DAYS, remaining)

        model, _, _ = _fit_eval_model(work, model_name)
        if model is None:
            return None

        X_all, _ = _make_dataset_from_close(work)
        if X_all.empty:
            return None
        last_feat = X_all.iloc[[-1]]
        pred_daily = float(model.predict(last_feat)[0])
        pred_daily = float(np.clip(pred_daily, -0.08, 0.08))

        last_price = float(work.iloc[-1])
        steps = np.arange(1, chunk_days + 1)
        chunk = np.maximum(last_price * (1 + pred_daily) ** steps, 0.01)

        future_parts.append(chunk)
        chunk_index = pd.bdate_range(work.index[-1] + pd.Timedelta(days=1), periods=chunk_days)
        work = pd.concat([work, pd.Series(chunk, index=chunk_index)])
        remaining -= chunk_days

    future = np.concatenate(future_parts)
    return _build_result(df, future, model=model_name, mae=mae, direction_acc=direction_acc)


def build_ml_forecast(df: pd.DataFrame, model_name: str = "baseline", horizon_days: int = 252) -> dict | None:
    if model_name == "baseline":
        return _baseline_forecast(df, horizon_days=horizon_days)

    ml = _sequential_ml(df, model_name=model_name, horizon_days=horizon_days)
    if ml is not None:
        return ml

    return _baseline_forecast(df, horizon_days=horizon_days)
