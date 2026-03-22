import datetime as dt

import pandas as pd
import streamlit as st
import yfinance as yf

try:
    from pykrx import stock as krx_stock

    KRX_AVAILABLE = True
except ModuleNotFoundError:
    krx_stock = None
    KRX_AVAILABLE = False

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    PLOTLY_AVAILABLE = True
except ModuleNotFoundError:
    go = None
    make_subplots = None
    PLOTLY_AVAILABLE = False


st.set_page_config(page_title="Python Stock", layout="wide")
st.title("주식 분석 웹 (차트 + RSI + 매수/매도 신호)")


NAME_ALIASES = {
    "apple": "AAPL",
    "애플": "AAPL",
    "tesla": "TSLA",
    "테슬라": "TSLA",
    "nvidia": "NVDA",
    "엔비디아": "NVDA",
    "microsoft": "MSFT",
    "마이크로소프트": "MSFT",
    "삼성전자": "005930.KS",
    "카카오": "035720.KS",
    "네이버": "035420.KS",
    "현대차": "005380.KS",
    "셀트리온": "068270.KS",
}


def dedupe_rows(rows: list[dict[str, str]], limit: int = 20) -> list[dict[str, str]]:
    dedup = []
    seen = set()
    for item in rows:
        symbol = item.get("symbol", "")
        if not symbol:
            continue
        if symbol in seen:
            continue
        seen.add(symbol)
        dedup.append(item)
        if len(dedup) >= limit:
            break
    return dedup


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def get_krx_universe() -> list[dict[str, str]]:
    if not KRX_AVAILABLE:
        return []

    records: list[dict[str, str]] = []
    market_specs = [
        ("KOSPI", ".KS"),
        ("KOSDAQ", ".KQ"),
        ("KONEX", ".KQ"),
    ]
    for market_name, suffix in market_specs:
        try:
            tickers = krx_stock.get_market_ticker_list(market=market_name)
        except Exception:
            tickers = []
        for ticker in tickers:
            try:
                name = krx_stock.get_market_ticker_name(ticker)
            except Exception:
                continue
            if not name:
                continue
            records.append(
                {
                    "name": str(name).strip(),
                    "symbol": f"{ticker}{suffix}",
                    "exchange": market_name,
                    "currency": "KRW",
                    "price": "-",
                }
            )
    return records


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def get_us_universe() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    exchange_map = {
        "A": "NYSE American",
        "N": "NYSE",
        "P": "NYSE Arca",
        "Q": "NASDAQ",
        "V": "IEX",
        "Z": "BATS",
    }

    try:
        nasdaq_df = pd.read_csv("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt", sep="|")
        nasdaq_df = nasdaq_df[nasdaq_df["Symbol"].notna()]
        nasdaq_df = nasdaq_df[nasdaq_df["Symbol"] != "File Creation Time"]
        for _, row in nasdaq_df.iterrows():
            symbol = str(row.get("Symbol", "")).strip().upper()
            if not symbol:
                continue
            records.append(
                {
                    "name": str(row.get("Security Name", symbol)).strip(),
                    "symbol": symbol,
                    "exchange": "NASDAQ",
                    "currency": "USD",
                    "price": "-",
                }
            )
    except Exception:
        pass

    try:
        other_df = pd.read_csv("https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt", sep="|")
        other_df = other_df[other_df["ACT Symbol"].notna()]
        other_df = other_df[other_df["ACT Symbol"] != "File Creation Time"]
        for _, row in other_df.iterrows():
            symbol = str(row.get("ACT Symbol", "")).strip().upper()
            if not symbol:
                continue
            exch_code = str(row.get("Exchange", "")).strip().upper()
            exchange = exchange_map.get(exch_code, exch_code or "US")
            records.append(
                {
                    "name": str(row.get("Security Name", symbol)).strip(),
                    "symbol": symbol,
                    "exchange": exchange,
                    "currency": "USD",
                    "price": "-",
                }
            )
    except Exception:
        pass

    return dedupe_rows(records, limit=20000)


@st.cache_data(show_spinner=False, ttl=600)
def search_candidates(query: str, market: str) -> list[dict[str, str]]:
    keyword = query.strip()
    if not keyword:
        return []

    key = keyword.replace(" ", "").lower()

    if market == "KR":
        krx_rows = get_krx_universe()
        if krx_rows:
            matched = []
            for row in krx_rows:
                row_key = row["name"].replace(" ", "").lower()
                symbol_key = row["symbol"].replace(".", "").lower()
                if key in row_key or key in symbol_key:
                    matched.append(row)
            matched.sort(key=lambda x: (x["name"].replace(" ", "").lower() != key, x["name"]))
            if matched:
                return matched[:20]
    else:
        us_rows = get_us_universe()
        if us_rows:
            matched = []
            for row in us_rows:
                row_key = row["name"].replace(" ", "").lower()
                symbol_key = row["symbol"].lower()
                if key in row_key or key in symbol_key:
                    matched.append(row)
            matched.sort(key=lambda x: (x["symbol"].lower() != key and x["name"].replace(" ", "").lower() != key, x["name"]))
            if matched:
                return matched[:20]

    results: list[dict[str, str]] = []
    try:
        quotes = yf.Search(keyword, max_results=20).quotes or []
    except Exception:
        quotes = []

    for q in quotes:
        symbol = str(q.get("symbol", "")).upper()
        name = str(q.get("shortname", "") or q.get("longname", "") or symbol).strip()
        q_type = str(q.get("quoteType", "")).upper()
        exchange = str(q.get("exchDisp", "") or q.get("exchange", "")).strip()
        currency = str(q.get("currency", "")).strip()
        last_price = q.get("regularMarketPrice", "")
        try:
            price_text = f"{float(last_price):.2f}" if last_price not in ("", None) else "-"
        except Exception:
            price_text = "-"
        if not symbol:
            continue

        item = {
            "symbol": symbol,
            "name": name,
            "exchange": exchange or "-",
            "currency": currency or "-",
            "price": price_text,
        }
        if market == "KR":
            if symbol.endswith(".KS") or symbol.endswith(".KQ"):
                results.append(item)
        else:
            if (not symbol.endswith(".KS")) and (not symbol.endswith(".KQ")) and q_type in {"EQUITY", "ETF", ""}:
                results.append(item)

    return dedupe_rows(results, limit=20)


def resolve_ticker(raw_input: str, market: str, kr_exchange: str) -> tuple[str, str]:
    query = raw_input.strip()
    if not query:
        return "", "empty"

    query_lower = query.lower()
    if query_lower in NAME_ALIASES:
        return NAME_ALIASES[query_lower], "alias"

    symbol = query.upper()

    if market == "KR" and "." not in symbol and symbol.isdigit() and len(symbol) == 6:
        suffix = ".KS" if kr_exchange == "KOSPI" else ".KQ"
        return f"{symbol}{suffix}", "kr_code"

    key = query.replace(" ", "").lower()

    if market == "KR":
        for row in get_krx_universe():
            row_key = row["name"].replace(" ", "").lower()
            if row_key == key:
                return row["symbol"], "krx_exact"
        for row in get_krx_universe():
            row_key = row["name"].replace(" ", "").lower()
            if key and key in row_key:
                return row["symbol"], "krx_partial"
    else:
        for row in get_us_universe():
            row_name = row["name"].replace(" ", "").lower()
            row_symbol = row["symbol"].lower()
            if key == row_symbol or key == row_name:
                return row["symbol"], "us_exact"
        for row in get_us_universe():
            row_name = row["name"].replace(" ", "").lower()
            row_symbol = row["symbol"].lower()
            if key and (key in row_name or key in row_symbol):
                return row["symbol"], "us_partial"

    if "." in symbol or (symbol.isalnum() and len(symbol) <= 6 and symbol == symbol.upper()):
        return symbol, "direct"

    try:
        search = yf.Search(query, max_results=10)
        quotes = search.quotes or []
    except Exception:
        quotes = []

    if market == "KR":
        for q in quotes:
            sym = str(q.get("symbol", "")).upper()
            if sym.endswith(".KS") or sym.endswith(".KQ"):
                return sym, "search"
    else:
        for q in quotes:
            sym = str(q.get("symbol", "")).upper()
            quote_type = str(q.get("quoteType", "")).upper()
            if (not sym.endswith(".KS")) and (not sym.endswith(".KQ")) and quote_type in {"EQUITY", "ETF", ""}:
                return sym, "search"

    return symbol, "fallback"


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    return df


def period_to_days(period: str) -> int:
    mapping = {
        "1mo": 35,
        "3mo": 100,
        "6mo": 200,
        "1y": 380,
        "2y": 760,
        "5y": 1900,
    }
    return mapping.get(period, 380)


def yfinance_download_safe(symbol: str, period: str, interval: str) -> pd.DataFrame:
    try:
        df = yf.download(symbol, period=period, interval=interval, auto_adjust=False, progress=False)
    except Exception:
        return pd.DataFrame()
    df = normalize_columns(df)
    if df.empty:
        return df
    needed = {"Open", "High", "Low", "Close"}
    if not needed.issubset(set(df.columns)):
        return pd.DataFrame()
    return df


def fetch_krx_ohlcv_pykrx(symbol: str, period: str) -> pd.DataFrame:
    if not KRX_AVAILABLE:
        return pd.DataFrame()
    ticker = symbol.split(".")[0]
    if (not ticker.isdigit()) or len(ticker) != 6:
        return pd.DataFrame()

    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=period_to_days(period))
    try:
        df = krx_stock.get_market_ohlcv_by_date(start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d"), ticker)
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()
    rename_map = {"시가": "Open", "고가": "High", "저가": "Low", "종가": "Close", "거래량": "Volume"}
    df = df.rename(columns=rename_map)
    for col in ["Open", "High", "Low", "Close"]:
        if col not in df.columns:
            return pd.DataFrame()
    if "Volume" not in df.columns:
        df["Volume"] = 0
    df.index = pd.to_datetime(df.index)
    return df[["Open", "High", "Low", "Close", "Volume"]]


def fetch_price_data(ticker: str, market: str, period: str, interval: str, kr_exchange: str) -> tuple[pd.DataFrame, str, str]:
    tried: list[str] = []
    candidates: list[str] = []

    if market == "KR":
        base = ticker.split(".")[0]
        if base.isdigit() and len(base) == 6:
            candidates.append(f"{base}.KS")
            candidates.append(f"{base}.KQ")
            if kr_exchange == "KOSDAQ":
                candidates = [f"{base}.KQ", f"{base}.KS"]
        candidates.append(ticker.upper())
    else:
        candidates.append(ticker.upper())

    dedup_candidates = []
    seen = set()
    for c in candidates:
        if c not in seen:
            seen.add(c)
            dedup_candidates.append(c)

    for sym in dedup_candidates:
        tried.append(sym)
        df = yfinance_download_safe(sym, period, interval)
        if not df.empty:
            return df, f"yfinance:{sym}", sym

    if market == "KR":
        # pykrx fallback is daily data; use when Yahoo is missing/incompatible.
        for sym in dedup_candidates:
            df = fetch_krx_ohlcv_pykrx(sym, period)
            if not df.empty:
                return df, f"pykrx:{sym}(interval=1d)", sym

    return pd.DataFrame(), f"failed:{','.join(tried)}", ticker


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["SMA20"] = out["Close"].rolling(20).mean()
    out["SMA60"] = out["Close"].rolling(60).mean()

    delta = out["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    out["RSI"] = 100 - (100 / (1 + rs))

    rsi_prev = out["RSI"].shift(1)
    out["BuySignal"] = (rsi_prev < 30) & (out["RSI"] >= 30)
    out["SellSignal"] = (rsi_prev > 70) & (out["RSI"] <= 70)
    return out


def run_backtest(df: pd.DataFrame) -> tuple[pd.Series, float, int, float]:
    bt = df.copy()
    bt["Position"] = 0
    bt.loc[bt["BuySignal"], "Position"] = 1
    bt.loc[bt["SellSignal"], "Position"] = 0
    bt["Position"] = bt["Position"].replace(0, pd.NA).ffill().fillna(0)
    bt.loc[bt["SellSignal"], "Position"] = 0
    bt["Position"] = bt["Position"].ffill().fillna(0)

    bt["Return"] = bt["Close"].pct_change().fillna(0)
    bt["StrategyReturn"] = bt["Return"] * bt["Position"].shift(1).fillna(0)
    equity = (1 + bt["StrategyReturn"]).cumprod()
    total_return = (equity.iloc[-1] - 1) * 100

    trade_returns = []
    in_position = False
    entry_price = 0.0
    for _, row in bt.iterrows():
        if (not in_position) and bool(row["BuySignal"]):
            in_position = True
            entry_price = float(row["Close"])
        elif in_position and bool(row["SellSignal"]):
            trade_returns.append((float(row["Close"]) / entry_price) - 1)
            in_position = False

    trade_count = len(trade_returns)
    win_rate = (sum(1 for r in trade_returns if r > 0) / trade_count * 100) if trade_count else 0.0
    return equity, total_return, trade_count, win_rate


def build_chart(df: pd.DataFrame, ticker: str, mobile_mode: bool):
    if not PLOTLY_AVAILABLE:
        return None
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.68, 0.32],
    )

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="Price",
            increasing_line_color="#1f6feb",
            increasing_fillcolor="#1f6feb",
            decreasing_line_color="#d93025",
            decreasing_fillcolor="#d93025",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["SMA20"],
            mode="lines",
            name="SMA20",
            line=dict(color="#f59f00", width=2),
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["SMA60"],
            mode="lines",
            name="SMA60",
            line=dict(color="#2f9e44", width=2),
        ),
        row=1,
        col=1,
    )

    buy_df = df[df["BuySignal"]]
    sell_df = df[df["SellSignal"]]

    fig.add_trace(
        go.Scatter(
            x=buy_df.index,
            y=buy_df["Low"] * 0.995,
            mode="markers",
            marker=dict(symbol="triangle-up", size=11, color="#7b2cbf"),
            name="Buy",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=sell_df.index,
            y=sell_df["High"] * 1.005,
            mode="markers",
            marker=dict(symbol="triangle-down", size=11, color="#ff8f00"),
            name="Sell",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["RSI"],
            mode="lines",
            name="RSI(14)",
            line=dict(color="#00897b", width=2),
        ),
        row=2,
        col=1,
    )
    fig.add_hline(y=70, line_dash="dot", line_color="#b71c1c", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#0d47a1", row=2, col=1)

    fig.update_layout(
        title=f"{ticker} Price / Signals",
        template="plotly_white",
        xaxis_rangeslider_visible=False,
        height=620 if mobile_mode else 820,
        legend=dict(orientation="h", y=1.02, x=0.01),
        margin=dict(l=20, r=20, t=60, b=20),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#eef2f7")
    fig.update_yaxes(showgrid=True, gridcolor="#eef2f7")
    return fig


st.sidebar.header("설정")
market = st.sidebar.selectbox("시장", ["US", "KR"], index=0)
kr_exchange = st.sidebar.selectbox("KR 거래소(숫자 코드 입력 시)", ["KOSPI", "KOSDAQ"], index=0)
input_label = "티커 또는 회사명"
default_value = "AAPL" if market == "US" else "005930"
user_input = st.sidebar.text_input(input_label, value=default_value).strip()
candidates = search_candidates(user_input, market) if len(user_input) >= 1 else []
selected_symbol = ""
if candidates:
    option_labels = [
        f"{c['name']} | {c['symbol']} | {c['exchange']} | {c['currency']} | {c['price']}"
        for c in candidates
    ]
    label_to_symbol = {label: c["symbol"] for label, c in zip(option_labels, candidates)}
    selected_label = st.sidebar.selectbox("자동완성 후보", option_labels, index=0)
    selected_symbol = label_to_symbol[selected_label]
    st.sidebar.caption(f"선택 티커: {selected_symbol}")
period = st.sidebar.selectbox("기간", ["3mo", "6mo", "1y", "2y", "5y"], index=2)
interval = st.sidebar.selectbox("봉 간격", ["1d", "1h"], index=0)
mobile_mode = st.sidebar.toggle("모바일 최적화", value=True)

if st.sidebar.button("분석 시작"):
    if selected_symbol:
        ticker, source = selected_symbol, "autocomplete"
    else:
        ticker, source = resolve_ticker(user_input, market, kr_exchange)
    if not ticker:
        st.error("티커 또는 회사명을 입력하세요.")
        st.stop()

    with st.spinner("데이터를 가져오고 지표를 계산하는 중..."):
        raw, data_source, resolved_symbol = fetch_price_data(ticker, market, period, interval, kr_exchange)

    if raw.empty:
        st.error("데이터를 가져오지 못했습니다. 예: 애플/AAPL, 삼성전자/005930, 한화에어로스페이스")
    else:
        df = add_indicators(raw)
        st.success(f"{resolved_symbol} 분석 완료")
        st.caption(
            f"입력 해석 방식: {source} | 데이터 소스: {data_source} | 업데이트 시간: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        chart = build_chart(df, resolved_symbol, mobile_mode)
        if chart is not None:
            st.plotly_chart(chart, use_container_width=True)
        else:
            st.warning("현재 서버에 plotly가 없어 간단 차트로 표시합니다. requirements 재배포 후 캔들차트가 복구됩니다.")
            st.line_chart(df[["Close", "SMA20", "SMA60"]], use_container_width=True)

        latest = df.iloc[-1]
        if bool(latest["BuySignal"]):
            signal_text = "매수"
        elif bool(latest["SellSignal"]):
            signal_text = "매도"
        else:
            signal_text = "관망"

        if mobile_mode:
            st.metric("현재가", f"{latest['Close']:.2f}")
            st.metric("RSI(14)", f"{latest['RSI']:.2f}" if pd.notna(latest["RSI"]) else "N/A")
            st.metric("최신 신호", signal_text)
        else:
            col1, col2, col3 = st.columns(3)
            col1.metric("현재가", f"{latest['Close']:.2f}")
            col2.metric("RSI(14)", f"{latest['RSI']:.2f}" if pd.notna(latest["RSI"]) else "N/A")
            col3.metric("최신 신호", signal_text)

        equity, total_return, trade_count, win_rate = run_backtest(df)

        if mobile_mode:
            st.metric("백테스트 수익률", f"{total_return:.2f}%")
            st.metric("거래 횟수", f"{trade_count}")
            st.metric("승률", f"{win_rate:.1f}%")
        else:
            b1, b2, b3 = st.columns(3)
            b1.metric("백테스트 수익률", f"{total_return:.2f}%")
            b2.metric("거래 횟수", f"{trade_count}")
            b3.metric("승률", f"{win_rate:.1f}%")

        st.subheader("전략 누적수익 곡선")
        equity_df = equity.to_frame(name="Equity")
        st.line_chart(equity_df, use_container_width=True)

        st.subheader("최근 신호")
        signal_table = df.loc[df["BuySignal"] | df["SellSignal"], ["Close", "RSI", "BuySignal", "SellSignal"]].tail(10)
        st.dataframe(signal_table, use_container_width=True)
else:
    st.info("왼쪽에서 시장/회사명(또는 티커)을 입력한 뒤 '분석 시작'을 누르세요. 예: 애플, 삼성전자, 한화에어로스페이스, AAPL, 005930")
