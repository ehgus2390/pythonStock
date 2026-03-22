import numpy as np
import pandas as pd


def _baseline_forecast(df: pd.DataFrame, horizon_days: int = 63) -> dict | None:
    close = df["Close"].dropna().astype(float)
    if len(close) < 40:
        return None

    y = close.values
    x = np.arange(len(y), dtype=float)
    w = np.linspace(0.6, 1.4, len(y))

    try:
        slope, intercept = np.polyfit(x, y, 1, w=w)
    except Exception:
        return None

    fx = np.arange(len(y), len(y) + horizon_days, dtype=float)
    future = np.maximum(intercept + slope * fx, 0.01)

    last_idx = pd.Timestamp(df.index[-1])
    if last_idx.tzinfo is not None:
        last_idx = last_idx.tz_localize(None)
    future_dates = pd.bdate_range(last_idx + pd.Timedelta(days=1), periods=horizon_days)
    forecast_path = pd.DataFrame({"Forecast": future}, index=future_dates)

    last_price = float(y[-1])
    ret_1m = (future[min(20, horizon_days - 1)] / last_price - 1) * 100
    ret_2m = (future[min(41, horizon_days - 1)] / last_price - 1) * 100
    ret_3m = (future[min(62, horizon_days - 1)] / last_price - 1) * 100

    returns = pd.Series(y).pct_change().dropna()
    vol = float(returns.std()) if len(returns) > 5 else 0.01
    confidence = min(95.0, max(5.0, abs(ret_3m) / max(vol * 100 * np.sqrt(63), 0.1) * 100))

    if ret_3m >= 3:
        signal = "BUY"
        signal_label = "예상 매수지점"
    elif ret_3m <= -3:
        signal = "SELL"
        signal_label = "예상 매도지점"
    else:
        signal = "HOLD"
        signal_label = "관망"

    return {
        "path": forecast_path,
        "ret_1m": ret_1m,
        "ret_2m": ret_2m,
        "ret_3m": ret_3m,
        "signal": signal,
        "signal_label": signal_label,
        "confidence": confidence,
        "model": "baseline",
        "mae": np.nan,
        "direction_acc": np.nan,
    }


def _make_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    close = df["Close"].astype(float)
    ret1 = close.pct_change()

    feat = pd.DataFrame(index=df.index)
    feat["ret_1d"] = ret1.shift(1)
    feat["ret_5d"] = close.pct_change(5).shift(1)
    feat["ret_20d"] = close.pct_change(20).shift(1)
    feat["vol_20d"] = ret1.rolling(20).std().shift(1)
    feat["dist_sma20"] = (close / close.rolling(20).mean() - 1).shift(1)
    feat["dist_sma60"] = (close / close.rolling(60).mean() - 1).shift(1)

    if "RSI" in df.columns:
        feat["rsi"] = (df["RSI"].astype(float) / 100.0).shift(1)
    else:
        feat["rsi"] = np.nan

    target = ret1
    data = feat.join(target.rename("target")).dropna()
    if data.empty:
        return pd.DataFrame(), pd.Series(dtype=float)

    X = data.drop(columns=["target"])
    y = data["target"]
    return X, y


def _fit_predict_ml(df: pd.DataFrame, model_name: str, horizon_days: int) -> dict | None:
    try:
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.linear_model import Ridge
    except Exception:
        return None

    X, y = _make_dataset(df)
    if len(X) < 120:
        return None

    split = int(len(X) * 0.8)
    split = max(60, min(split, len(X) - 20))
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    if model_name == "ridge":
        model = Ridge(alpha=1.0, random_state=None)
    elif model_name == "rf":
        model = RandomForestRegressor(n_estimators=300, max_depth=6, random_state=42, n_jobs=-1)
    else:
        return None

    model.fit(X_train, y_train)
    pred_test = pd.Series(model.predict(X_test), index=X_test.index)

    mae = float(np.mean(np.abs(y_test - pred_test))) * 100
    direction_acc = float((np.sign(y_test) == np.sign(pred_test)).mean() * 100)

    last_feat = X.iloc[[-1]]
    pred_daily = float(model.predict(last_feat)[0])
    pred_daily = float(np.clip(pred_daily, -0.08, 0.08))

    last_price = float(df["Close"].iloc[-1])
    steps = np.arange(1, horizon_days + 1)
    future = np.maximum(last_price * (1 + pred_daily) ** steps, 0.01)

    last_idx = pd.Timestamp(df.index[-1])
    if last_idx.tzinfo is not None:
        last_idx = last_idx.tz_localize(None)
    future_dates = pd.bdate_range(last_idx + pd.Timedelta(days=1), periods=horizon_days)
    forecast_path = pd.DataFrame({"Forecast": future}, index=future_dates)

    ret_1m = (future[min(20, horizon_days - 1)] / last_price - 1) * 100
    ret_2m = (future[min(41, horizon_days - 1)] / last_price - 1) * 100
    ret_3m = (future[min(62, horizon_days - 1)] / last_price - 1) * 100

    if ret_3m >= 3:
        signal = "BUY"
        signal_label = "예상 매수지점"
    elif ret_3m <= -3:
        signal = "SELL"
        signal_label = "예상 매도지점"
    else:
        signal = "HOLD"
        signal_label = "관망"

    confidence = max(5.0, min(95.0, direction_acc))

    return {
        "path": forecast_path,
        "ret_1m": ret_1m,
        "ret_2m": ret_2m,
        "ret_3m": ret_3m,
        "signal": signal,
        "signal_label": signal_label,
        "confidence": confidence,
        "model": model_name,
        "mae": mae,
        "direction_acc": direction_acc,
    }


def build_ml_forecast(df: pd.DataFrame, model_name: str = "baseline", horizon_days: int = 63) -> dict | None:
    if model_name == "baseline":
        return _baseline_forecast(df, horizon_days=horizon_days)

    ml = _fit_predict_ml(df, model_name=model_name, horizon_days=horizon_days)
    if ml is not None:
        return ml

    # Fallback for environments without sklearn or too-short history.
    return _baseline_forecast(df, horizon_days=horizon_days)
