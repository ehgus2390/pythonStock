import datetime as dt
import hashlib
import hmac
import json
import os
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ModuleNotFoundError:
    OpenAI = None
    OPENAI_AVAILABLE = False

try:
    from pykrx import stock as krx_stock

    KRX_AVAILABLE = True
except ModuleNotFoundError:
    krx_stock = None
    KRX_AVAILABLE = False

try:
    import FinanceDataReader as fdr

    FDR_AVAILABLE = True
except ModuleNotFoundError:
    fdr = None
    FDR_AVAILABLE = False

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    PLOTLY_AVAILABLE = True
except ModuleNotFoundError:
    go = None
    make_subplots = None
    PLOTLY_AVAILABLE = False

try:
    from src.model_forecast import build_ml_forecast

    ML_FORECAST_AVAILABLE = True
except Exception:
    build_ml_forecast = None
    ML_FORECAST_AVAILABLE = False

try:
    _yf_cache = Path(__file__).resolve().parent / ".cache" / "yfinance"
    _yf_cache.mkdir(parents=True, exist_ok=True)
    if hasattr(yf, "set_tz_cache_location"):
        yf.set_tz_cache_location(str(_yf_cache))
except Exception:
    pass


st.set_page_config(page_title="Python Stock", layout="wide")
st.title("주식 분석 웹 (차트 + RSI + 매수/매도 신호 + 테마 + 1~12개월 예측)")


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

THEME_OPTIONS = [
    "없음",
    "로봇",
    "방산",
    "반도체",
    "항공/우주",
    "AI/소프트웨어",
    "2차전지/배터리",
    "전기차",
    "바이오/제약",
    "게임/콘텐츠",
    "인터넷/플랫폼",
    "통신/5G",
    "에너지/원전",
    "금융/은행",
    "철강/소재",
    "건설/인프라",
    "해운/물류",
    "소비재/유통",
]
FORECAST_MODELS = {
    "Baseline(추세)": "baseline",
    "ML-Ridge": "ridge",
    "ML-RandomForest": "rf",
}

THEME_KEYWORDS = {
    "로봇": ["로봇", "robot", "automation", "자동화"],
    "방산": ["방산", "defense", "defence", "military", "무기"],
    "반도체": ["반도체", "semiconductor", "chip", "chips", "fab"],
    "항공/우주": ["항공", "우주", "aerospace", "space", "aviation"],
    "AI/소프트웨어": ["ai", "artificial intelligence", "software", "cloud", "saas", "인공지능", "소프트웨어", "클라우드"],
    "2차전지/배터리": ["2차전지", "배터리", "battery", "cathode", "anode", "lithium"],
    "전기차": ["전기차", "ev", "electric vehicle", "자동차", "auto", "vehicle"],
    "바이오/제약": ["바이오", "제약", "pharma", "biotech", "drug", "health"],
    "게임/콘텐츠": ["게임", "game", "entertainment", "media", "content", "콘텐츠"],
    "인터넷/플랫폼": ["인터넷", "platform", "portal", "e-commerce", "커머스", "플랫폼"],
    "통신/5G": ["통신", "telecom", "5g", "network", "네트워크"],
    "에너지/원전": ["에너지", "원전", "nuclear", "solar", "wind", "power", "utility"],
    "금융/은행": ["금융", "은행", "bank", "financial", "insurance", "증권"],
    "철강/소재": ["철강", "소재", "steel", "metal", "chemical", "material"],
    "건설/인프라": ["건설", "infrastructure", "engineering", "cement", "플랜트"],
    "해운/물류": ["해운", "물류", "shipping", "logistics", "transport"],
    "소비재/유통": ["유통", "retail", "consumer", "food", "beverage", "화장품"],
}

THEME_KR_SEEDS = {
    "로봇": ["휴림로봇", "레인보우로보틱스", "로보로보", "로보티즈", "에브리봇", "유진로봇"],
    "방산": ["한화에어로스페이스", "한국항공우주", "LIG넥스원", "현대로템", "풍산", "빅텍"],
    "반도체": ["삼성전자", "SK하이닉스", "한미반도체", "DB하이텍", "주성엔지니어링", "원익IPS"],
    "항공/우주": ["한화에어로스페이스", "한국항공우주", "쎄트렉아이", "AP위성", "인텔리안테크", "제노코"],
    "AI/소프트웨어": ["네이버", "카카오", "더존비즈온", "솔트룩스", "코난테크놀로지"],
    "2차전지/배터리": ["LG에너지솔루션", "삼성SDI", "에코프로", "에코프로비엠", "포스코퓨처엠"],
    "전기차": ["현대차", "기아", "만도", "HL만도", "명신산업"],
    "바이오/제약": ["셀트리온", "삼성바이오로직스", "유한양행", "한미약품", "SK바이오사이언스"],
    "게임/콘텐츠": ["엔씨소프트", "넷마블", "크래프톤", "펄어비스", "카카오게임즈"],
    "인터넷/플랫폼": ["네이버", "카카오", "쿠팡", "NHN", "다날"],
    "통신/5G": ["SK텔레콤", "KT", "LG유플러스", "케이엠더블유", "쏠리드"],
    "에너지/원전": ["한국전력", "두산에너빌리티", "한전기술", "한전KPS", "씨에스윈드"],
    "금융/은행": ["KB금융", "신한지주", "하나금융지주", "우리금융지주", "삼성화재"],
    "철강/소재": ["POSCO홀딩스", "현대제철", "동국제강", "롯데케미칼", "금호석유"],
    "건설/인프라": ["삼성물산", "현대건설", "DL이앤씨", "GS건설", "대우건설"],
    "해운/물류": ["HMM", "팬오션", "대한해운", "CJ대한통운", "한진"],
    "소비재/유통": ["아모레퍼시픽", "LG생활건강", "이마트", "롯데쇼핑", "CJ제일제당"],
}

THEME_US_SEEDS = {
    "로봇": ["ISRG", "ROK", "ABB", "SYM", "TER"],
    "방산": ["LMT", "NOC", "RTX", "GD", "LHX"],
    "반도체": ["NVDA", "AMD", "TSM", "AVGO", "INTC", "QCOM"],
    "항공/우주": ["BA", "RKLB", "SPCE", "LMT", "NOC", "RTX"],
    "AI/소프트웨어": ["MSFT", "GOOGL", "META", "ORCL", "CRM", "PLTR"],
    "2차전지/배터리": ["TSLA", "ALB", "QS", "ENVX", "LTHM"],
    "전기차": ["TSLA", "RIVN", "LCID", "NIO", "XPEV", "GM", "F"],
    "바이오/제약": ["LLY", "JNJ", "PFE", "MRNA", "REGN", "AMGN"],
    "게임/콘텐츠": ["EA", "TTWO", "RBLX", "NFLX", "DIS", "WBD"],
    "인터넷/플랫폼": ["AMZN", "META", "GOOGL", "UBER", "ABNB", "SHOP"],
    "통신/5G": ["VZ", "T", "TMUS", "ERIC", "NOK"],
    "에너지/원전": ["XOM", "CVX", "NEE", "DUK", "SMR", "CCJ"],
    "금융/은행": ["JPM", "BAC", "WFC", "GS", "MS", "C"],
    "철강/소재": ["NUE", "X", "AA", "FCX", "CLF"],
    "건설/인프라": ["CAT", "DE", "URI", "VMC", "PWR"],
    "해운/물류": ["UPS", "FDX", "ZIM", "MATX"],
    "소비재/유통": ["WMT", "COST", "PG", "KO", "PEP", "MCD"],
}


APP_STATE_PATH = Path(__file__).resolve().parent / "user_state.json"
KRX_CACHE_PATH = Path(__file__).resolve().parent / "krx_universe_cache.json"
KRX_SNAPSHOT_PATH = Path(__file__).resolve().parent / "krx_universe_snapshot.csv"
KRX_CACHE_TTL_SEC = 60 * 60 * 24

BILLING_PRODUCTS = {
    "analysis_20": {"label": "분석 크레딧 20개", "credits": 20, "price_krw": 9900},
    "analysis_60": {"label": "분석 크레딧 60개", "credits": 60, "price_krw": 24900},
    "analysis_150": {"label": "분석 크레딧 150개", "credits": 150, "price_krw": 49900},
}


def _load_krx_cache_store() -> dict:
    if not KRX_CACHE_PATH.exists():
        return {}
    try:
        with KRX_CACHE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _get_cached_krx_rows(exchange_filter: str) -> list[dict[str, str]] | None:
    store = _load_krx_cache_store()
    by_exchange = store.get("by_exchange", {})
    now = int(time.time())

    def _is_fresh(ts: int) -> bool:
        return (now - int(ts)) <= KRX_CACHE_TTL_SEC

    if exchange_filter in {"KOSPI", "KOSDAQ", "KONEX"}:
        node = by_exchange.get(exchange_filter, {})
        ts = int(node.get("ts", 0) or 0)
        rows = node.get("rows", [])
        if ts and _is_fresh(ts) and isinstance(rows, list) and rows:
            return rows
        return None

    merged: list[dict[str, str]] = []
    ok_count = 0
    for exch in ["KOSPI", "KOSDAQ", "KONEX"]:
        node = by_exchange.get(exch, {})
        ts = int(node.get("ts", 0) or 0)
        rows = node.get("rows", [])
        if ts and _is_fresh(ts) and isinstance(rows, list) and rows:
            merged.extend(rows)
            ok_count += 1
    if ok_count >= 2 and merged:
        return merged
    return None


def _save_cached_krx_rows(exchange_filter: str, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    now = int(time.time())
    store = _load_krx_cache_store()
    by_exchange = store.get("by_exchange", {})

    if exchange_filter in {"KOSPI", "KOSDAQ", "KONEX"}:
        by_exchange[exchange_filter] = {"ts": now, "rows": rows}
    else:
        groups = {"KOSPI": [], "KOSDAQ": [], "KONEX": []}
        for row in rows:
            exch = str(row.get("exchange", ""))
            if exch in groups:
                groups[exch].append(row)
        for exch, grp_rows in groups.items():
            if grp_rows:
                by_exchange[exch] = {"ts": now, "rows": grp_rows}

    store["by_exchange"] = by_exchange
    try:
        with KRX_CACHE_PATH.open("w", encoding="utf-8") as f:
            json.dump(store, f, ensure_ascii=False)
    except Exception:
        pass


def _load_krx_snapshot_rows(exchange_filter: str) -> list[dict[str, str]]:
    if not KRX_SNAPSHOT_PATH.exists():
        return []
    try:
        df = pd.read_csv(KRX_SNAPSHOT_PATH, dtype=str)
    except Exception:
        return []
    if df.empty:
        return []
    for col in ["name", "symbol", "exchange", "currency", "price"]:
        if col not in df.columns:
            df[col] = ""
    if exchange_filter in {"KOSPI", "KOSDAQ", "KONEX"}:
        df = df[df["exchange"] == exchange_filter]
    rows = df[["name", "symbol", "exchange", "currency", "price"]].fillna("").to_dict("records")
    return dedupe_rows(rows, limit=20000)


def _save_krx_snapshot_rows(rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    try:
        df = pd.DataFrame(rows)
        for col in ["name", "symbol", "exchange", "currency", "price"]:
            if col not in df.columns:
                df[col] = ""
        df = df[["name", "symbol", "exchange", "currency", "price"]]
        df.to_csv(KRX_SNAPSHOT_PATH, index=False, encoding="utf-8-sig")
    except Exception:
        pass


@st.cache_data(show_spinner=False, ttl=60 * 10)
def get_krx_universe_df(exchange_filter: str = "전체") -> pd.DataFrame:
    rows = get_krx_universe(exchange_filter)
    if not rows:
        return pd.DataFrame(columns=["name", "symbol", "exchange", "currency", "price", "name_norm", "symbol_norm"])
    df = pd.DataFrame(rows)
    for col in ["name", "symbol", "exchange", "currency", "price"]:
        if col not in df.columns:
            df[col] = ""
    df = df[["name", "symbol", "exchange", "currency", "price"]].fillna("")
    df["name_norm"] = df["name"].astype(str).str.replace(" ", "", regex=False).str.lower()
    df["symbol_norm"] = df["symbol"].astype(str).str.replace(".", "", regex=False).str.lower()
    return df


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def get_us_universe_df() -> pd.DataFrame:
    rows = get_us_universe()
    if not rows:
        return pd.DataFrame(columns=["name", "symbol", "exchange", "currency", "price", "name_norm", "symbol_norm"])
    df = pd.DataFrame(rows)
    for col in ["name", "symbol", "exchange", "currency", "price"]:
        if col not in df.columns:
            df[col] = ""
    df = df[["name", "symbol", "exchange", "currency", "price"]].fillna("")
    df["name_norm"] = df["name"].astype(str).str.replace(" ", "", regex=False).str.lower()
    df["symbol_norm"] = df["symbol"].astype(str).str.lower()
    return df


def _default_app_state() -> dict:
    return {"recent": [], "favorites": [], "users": {}}


def load_user_state() -> dict:
    if not APP_STATE_PATH.exists():
        return _default_app_state()
    try:
        with APP_STATE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _default_app_state()
        data.setdefault("recent", [])
        data.setdefault("favorites", [])
        data.setdefault("users", {})
        if not isinstance(data["users"], dict):
            data["users"] = {}
        data["recent"] = [str(x) for x in data.get("recent", []) if str(x).strip()]
        data["favorites"] = [str(x) for x in data.get("favorites", []) if str(x).strip()]
        return data
    except Exception:
        return _default_app_state()


def save_user_state(state: dict) -> None:
    try:
        APP_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with APP_STATE_PATH.open("w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def add_recent_symbol(state: dict, symbol: str, limit: int = 30) -> dict:
    sym = str(symbol).strip().upper()
    if not sym:
        return state
    recent = [sym] + [x for x in state.get("recent", []) if str(x).upper() != sym]
    state["recent"] = recent[:limit]
    return state


def normalize_user_id(value: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    normalized = re.sub(r"[^a-z0-9가-힣@._-]+", "", raw)
    return normalized[:80]


def _today_key() -> str:
    return dt.date.today().isoformat()


def get_or_create_user_record(app_state: dict, user_id: str) -> dict:
    users = app_state.setdefault("users", {})
    if not isinstance(users, dict):
        app_state["users"] = {}
        users = app_state["users"]
    user_key = normalize_user_id(user_id) or "guest"
    record = users.setdefault(
        user_key,
        {
            "credits": 0,
            "plan": "free",
            "daily_usage": {},
            "recent": app_state.get("recent", []) if user_key == "guest" else [],
            "favorites": app_state.get("favorites", []) if user_key == "guest" else [],
            "applied_grant_codes": [],
        },
    )
    record.setdefault("credits", 0)
    record.setdefault("plan", "free")
    record.setdefault("daily_usage", {})
    record.setdefault("recent", [])
    record.setdefault("favorites", [])
    record.setdefault("applied_grant_codes", [])
    return record


def _env_int(name: str, default: int) -> int:
    try:
        return int(_get_secret_or_env(name) or default)
    except Exception:
        return default


def is_billing_enabled() -> bool:
    value = _get_secret_or_env("BILLING_ENABLED").lower()
    return value in {"1", "true", "yes", "on"}


def get_billing_config() -> dict:
    return {
        "free_daily_analyses": max(0, _env_int("FREE_DAILY_ANALYSES", 3)),
        "analysis_credit_cost": max(1, _env_int("ANALYSIS_CREDIT_COST", 1)),
        "ai_credit_cost": max(1, _env_int("AI_CREDIT_COST", 2)),
        "admin_credit_grant": max(1, _env_int("ADMIN_CREDIT_GRANT", 20)),
    }


def _grant_code_hash(code: str) -> str:
    return hashlib.sha256(str(code).strip().encode("utf-8")).hexdigest()


def apply_admin_credit_code(user_record: dict, code: str, grant_amount: int) -> tuple[bool, str]:
    expected = _get_secret_or_env("ADMIN_CREDIT_CODE")
    provided = str(code or "").strip()
    if not expected:
        return False, "관리자 충전 코드가 서버에 설정되어 있지 않습니다."
    if not provided or not hmac.compare_digest(provided, expected):
        return False, "충전 코드가 올바르지 않습니다."
    code_hash = _grant_code_hash(provided)
    applied = user_record.setdefault("applied_grant_codes", [])
    if code_hash in applied:
        return False, "이미 이 사용자에게 적용된 충전 코드입니다."
    user_record["credits"] = int(user_record.get("credits", 0) or 0) + int(grant_amount)
    applied.append(code_hash)
    user_record["last_credit_grant_at"] = dt.datetime.utcnow().isoformat()
    return True, f"{grant_amount} 크레딧이 충전되었습니다."


def consume_user_feature(user_record: dict, feature: str, billing_config: dict) -> tuple[bool, str]:
    today = _today_key()
    daily_usage = user_record.setdefault("daily_usage", {})
    today_usage = daily_usage.setdefault(today, {"analysis": 0, "ai_summary": 0})

    if feature == "analysis":
        used = int(today_usage.get("analysis", 0) or 0)
        free_limit = int(billing_config["free_daily_analyses"])
        if used < free_limit:
            today_usage["analysis"] = used + 1
            return True, f"오늘 무료 분석 {today_usage['analysis']}/{free_limit}회 사용"
        cost = int(billing_config["analysis_credit_cost"])
        label = "분석"
    elif feature == "ai_summary":
        cost = int(billing_config["ai_credit_cost"])
        label = "AI 요약"
    else:
        return False, "지원하지 않는 과금 기능입니다."

    credits = int(user_record.get("credits", 0) or 0)
    if credits < cost:
        return False, f"{label}에 필요한 크레딧이 부족합니다. 필요: {cost}, 보유: {credits}"
    user_record["credits"] = credits - cost
    if feature == "ai_summary":
        today_usage["ai_summary"] = int(today_usage.get("ai_summary", 0) or 0) + 1
    return True, f"{label} 크레딧 {cost}개 차감, 잔액 {user_record['credits']}개"


def convert_to_krw(price: float, currency: str, usdkrw: float | None) -> float | None:
    if price is None or pd.isna(price):
        return None
    cur = str(currency).upper()
    if cur in {"KRW", "KOR"}:
        return float(price)
    if cur in {"USD", "US$", "$"} and usdkrw is not None:
        return float(price) * float(usdkrw)
    return None


def get_company_name_by_symbol(symbol: str, market: str) -> str:
    sym = str(symbol).strip().upper()
    if not sym:
        return ""
    if market == "KR":
        code = sym.split(".")[0]
        if KRX_AVAILABLE and len(code) == 6 and code.isdigit():
            try:
                name = krx_stock.get_market_ticker_name(code)
                if name:
                    return str(name).strip()
            except Exception:
                pass
        suffix = ".KQ" if sym.endswith(".KQ") else (".KS" if sym.endswith(".KS") else "")
        if suffix:
            df = get_krx_universe_df("KOSDAQ" if suffix == ".KQ" else "KOSPI")
            matched = df.loc[df["symbol"].astype(str).str.upper() == sym, "name"]
            if not matched.empty:
                return str(matched.iloc[0]).strip()
        return ""
    df = get_us_universe_df()
    matched = df.loc[df["symbol"].astype(str).str.upper() == sym, "name"]
    if not matched.empty:
        return str(matched.iloc[0]).strip()
    return ""


@st.cache_data(show_spinner=False, ttl=60 * 30)
def get_usdkrw_rate() -> float | None:
    try:
        fx = yf.download("KRW=X", period="5d", interval="1d", auto_adjust=False, progress=False)
        if fx is None or fx.empty:
            return None
        if isinstance(fx.columns, pd.MultiIndex):
            fx.columns = [x[0] for x in fx.columns]
        if "Close" not in fx.columns:
            return None
        return float(fx["Close"].dropna().iloc[-1])
    except Exception:
        return None

def dedupe_rows(rows: list[dict[str, str]], limit: int = 5000) -> list[dict[str, str]]:
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


def filter_candidates_by_exchange(rows: list[dict[str, str]], market: str, exchange_choice: str) -> list[dict[str, str]]:
    if exchange_choice == "전체":
        return rows
    out = []
    for row in rows:
        exch = str(row.get("exchange", ""))
        if market == "KR":
            if exch == exchange_choice:
                out.append(row)
        else:
            if exch == exchange_choice:
                out.append(row)
    return out


def detect_theme(query: str) -> str:
    q = query.strip().lower()
    if not q:
        return "없음"
    for theme, keys in THEME_KEYWORDS.items():
        if any(k in q for k in keys):
            return theme
    return "없음"


@st.cache_data(show_spinner=False, ttl=60 * 10)
def get_krx_universe(exchange_filter: str = "전체") -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    target_exchange = exchange_filter if exchange_filter in {"KOSPI", "KOSDAQ", "KONEX"} else "전체"

    snapshot_rows = _load_krx_snapshot_rows(target_exchange)
    if snapshot_rows:
        return dedupe_rows(snapshot_rows, limit=20000)

    cached_rows = _get_cached_krx_rows(target_exchange)
    if cached_rows:
        return dedupe_rows(cached_rows, limit=20000)
    if KRX_AVAILABLE:
        market_specs = [
            ("KOSPI", ".KS"),
            ("KOSDAQ", ".KQ"),
            ("KONEX", ".KQ"),
        ]
        if target_exchange != "전체":
            market_specs = [x for x in market_specs if x[0] == target_exchange]
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

    if (not records) and FDR_AVAILABLE:
        def _append_fdr_listing(df: pd.DataFrame, fallback_exch: str) -> None:
            if df is None or df.empty:
                return
            for _, row in df.iterrows():
                code = str(row.get("Code", "")).zfill(6)
                name = str(row.get("Name", "")).strip()
                market_name = str(row.get("Market", fallback_exch)).upper()
                if len(code) != 6 or not name:
                    continue
                if "KOSDAQ" in market_name:
                    suffix = ".KQ"
                    exch = "KOSDAQ"
                elif "KONEX" in market_name:
                    suffix = ".KQ"
                    exch = "KONEX"
                else:
                    suffix = ".KS"
                    exch = "KOSPI"
                records.append(
                    {
                        "name": name,
                        "symbol": f"{code}{suffix}",
                        "exchange": exch,
                        "currency": "KRW",
                        "price": "-",
                    }
                )

        if target_exchange == "전체":
            # Try broad KRX listing first.
            try:
                _append_fdr_listing(fdr.StockListing("KRX"), "KOSPI")
            except Exception:
                pass

            # Retry by each market to increase resilience when KRX endpoint is flaky.
            if not records:
                for m in ["KOSPI", "KOSDAQ", "KONEX"]:
                    try:
                        _append_fdr_listing(fdr.StockListing(m), m)
                    except Exception:
                        continue
        else:
            try:
                _append_fdr_listing(fdr.StockListing(target_exchange), target_exchange)
            except Exception:
                pass

    # 3rd fallback: KRX KIND downloadable corp list (works without pykrx/FDR).
    if not records:
        market_params = [
            ("stockMkt", "KOSPI", ".KS"),
            ("kosdaqMkt", "KOSDAQ", ".KQ"),
            ("konexMkt", "KONEX", ".KQ"),
        ]
        if target_exchange != "전체":
            market_params = [x for x in market_params if x[1] == target_exchange]
        for market_type, exch, suffix in market_params:
            try:
                url = f"https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&marketType={market_type}"
                # KRX endpoint is often served as html table; read_html handles it well.
                table = pd.read_html(url, header=0)[0]
            except Exception:
                continue

            if table is None or table.empty:
                continue

            # Normalize expected Korean column names.
            col_name = None
            col_code = None
            for c in table.columns:
                cs = str(c).strip()
                if cs in ["회사명", "기업명"]:
                    col_name = c
                if cs in ["종목코드", "종목 코드", "코드"]:
                    col_code = c
            if col_name is None or col_code is None:
                continue

            for _, row in table.iterrows():
                name = str(row.get(col_name, "")).strip()
                code = str(row.get(col_code, "")).strip()
                code = code.zfill(6)
                if not name or len(code) != 6 or (not code.isdigit()):
                    continue
                records.append(
                    {
                        "name": name,
                        "symbol": f"{code}{suffix}",
                        "exchange": exch,
                        "currency": "KRW",
                        "price": "-",
                    }
                )

    # 4th fallback: Naver Finance market-cap pages (cloud에서 상대적으로 안정적).
    if not records:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": "https://finance.naver.com/",
        }

        def _append_from_naver_market(sosok: int, exch: str, suffix: str) -> None:
            try:
                first_url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page=1"
                first_resp = requests.get(first_url, headers=headers, timeout=10)
                first_resp.raise_for_status()
                first_resp.encoding = "euc-kr"
                html = first_resp.text
            except Exception:
                return

            pages = [int(x) for x in re.findall(r"page=(\d+)", html)]
            max_page = min(max(pages) if pages else 1, 120)
            seen_codes: set[str] = set()

            for page in range(1, max_page + 1):
                try:
                    page_url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page={page}"
                    resp = requests.get(page_url, headers=headers, timeout=10)
                    resp.raise_for_status()
                    resp.encoding = "euc-kr"
                    page_html = resp.text
                except Exception:
                    continue

                matches = re.findall(r'/item/main\.naver\?code=(\d{6})"[^>]*>([^<]+)</a>', page_html)
                for code, name in matches:
                    code = str(code).strip()
                    name = str(name).strip()
                    if len(code) != 6 or (not code.isdigit()) or (not name):
                        continue
                    if code in seen_codes:
                        continue
                    seen_codes.add(code)
                    records.append(
                        {
                            "name": name,
                            "symbol": f"{code}{suffix}",
                            "exchange": exch,
                            "currency": "KRW",
                            "price": "-",
                        }
                    )

        if target_exchange in {"전체", "KOSPI"}:
            _append_from_naver_market(sosok=0, exch="KOSPI", suffix=".KS")
        if target_exchange in {"전체", "KOSDAQ"}:
            _append_from_naver_market(sosok=1, exch="KOSDAQ", suffix=".KQ")
    out = dedupe_rows(records, limit=20000)
    if out:
        _save_cached_krx_rows(target_exchange, out)
        if target_exchange == "전체":
            _save_krx_snapshot_rows(out)
    return out


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


@st.cache_data(show_spinner=False, ttl=60 * 60 * 12)
def get_krx_index_constituents(index_key: str) -> list[dict[str, str]]:
    """
    index_key: 'KOSPI50' or 'KOSDAQ100'
    """
    target_name_map = {
        "KOSPI50": ["코스피 50", "코스피50", "KOSPI 50"],
        "KOSDAQ100": ["코스닥 100", "코스닥100", "KOSDAQ 100"],
    }
    target_market_map = {
        "KOSPI50": "KOSPI",
        "KOSDAQ100": "KOSDAQ",
    }
    target_size_map = {
        "KOSPI50": 50,
        "KOSDAQ100": 100,
    }

    rows_df = get_krx_universe_df()
    by_code = {}
    if not rows_df.empty:
        for _, r in rows_df.iterrows():
            code = str(r.get("symbol", "")).split(".")[0]
            if len(code) == 6 and code.isdigit():
                by_code[code] = {
                    "name": str(r.get("name", "")),
                    "symbol": str(r.get("symbol", "")),
                    "exchange": str(r.get("exchange", "")),
                    "currency": str(r.get("currency", "")),
                    "price": str(r.get("price", "-")),
                }

    out: list[dict[str, str]] = []
    code_set: set[str] = set()

    # 1) primary: pykrx index constituents
    if KRX_AVAILABLE:
        try:
            idx_markets = ["KOSPI", "KOSDAQ", "KRX", "테마"]
            matched_idx = None
            for mk in idx_markets:
                tickers = krx_stock.get_index_ticker_list(market=mk)
                for idx_t in tickers:
                    idx_name = krx_stock.get_index_ticker_name(idx_t)
                    if any(k in str(idx_name) for k in target_name_map.get(index_key, [])):
                        matched_idx = idx_t
                        break
                if matched_idx:
                    break

            if matched_idx:
                members = krx_stock.get_index_portfolio_deposit_file(matched_idx) or []
                for code in members:
                    code = str(code).zfill(6)
                    if len(code) == 6 and code.isdigit():
                        code_set.add(code)
        except Exception:
            pass

    # 2) fallback: top market-cap by exchange
    if not code_set and FDR_AVAILABLE:
        try:
            market_name = target_market_map[index_key]
            top_n = target_size_map[index_key]
            listing = fdr.StockListing(market_name)
            if not listing.empty and "Code" in listing.columns and "Name" in listing.columns:
                if "Marcap" in listing.columns:
                    listing = listing.sort_values("Marcap", ascending=False)
                listing = listing.head(top_n)
                for _, rr in listing.iterrows():
                    code = str(rr.get("Code", "")).zfill(6)
                    if len(code) == 6 and code.isdigit():
                        code_set.add(code)
        except Exception:
            pass

    # build rows
    for code in sorted(code_set):
        if code in by_code:
            out.append(by_code[code])
        else:
            suffix = ".KQ" if index_key == "KOSDAQ100" else ".KS"
            exch = "KOSDAQ" if index_key == "KOSDAQ100" else "KOSPI"
            out.append(
                {
                    "name": code,
                    "symbol": f"{code}{suffix}",
                    "exchange": exch,
                    "currency": "KRW",
                    "price": "-",
                }
            )

    return dedupe_rows(out, limit=2000)


def get_theme_candidates(theme: str, market: str, exchange_choice: str = "전체", limit: int = 5000) -> list[dict[str, str]]:
    if theme == "없음":
        return []

    if market == "KR":
        rows_df = get_krx_universe_df(exchange_choice)
        seeds = set(THEME_KR_SEEDS.get(theme, []))
        keys = [k.lower() for k in THEME_KEYWORDS.get(theme, [])]

        # Primary path: full KRX universe match
        if not rows_df.empty:
            seed_norm = {s.replace(" ", "").lower() for s in seeds}
            mask = rows_df["name_norm"].isin(seed_norm)
            if keys:
                safe_keys = [re.escape(k) for k in keys if k]
                if safe_keys:
                    regex = "|".join(safe_keys)
                    mask = mask | rows_df["name"].astype(str).str.lower().str.contains(regex, regex=True, na=False)
            matched_df = rows_df.loc[mask, ["name", "symbol", "exchange", "currency", "price"]]
            if not matched_df.empty:
                return dedupe_rows(matched_df.to_dict("records"), limit=limit)

        # Fallback path: when pykrx universe is unavailable on runtime
        # Use seed names + keyword search through Yahoo lookup.
        fallback_rows: list[dict[str, str]] = []
        for seed_name in THEME_KR_SEEDS.get(theme, []):
            seed_matches = search_candidates(seed_name, "KR", exchange_choice=exchange_choice, max_results=50)
            fallback_rows.extend(seed_matches)

        for k in keys:
            if len(k) >= 2 and not k.isascii():
                key_matches = search_candidates(k, "KR", exchange_choice=exchange_choice, max_results=50)
                fallback_rows.extend(key_matches)

        return dedupe_rows(fallback_rows, limit=limit)

    rows = get_us_universe()
    seeds = {s.upper() for s in THEME_US_SEEDS.get(theme, [])}
    keys = [k.lower() for k in THEME_KEYWORDS.get(theme, [])]
    matched = []
    for row in rows:
        name = row["name"].lower()
        symbol = row["symbol"].upper()
        if (symbol in seeds) or any(k in name for k in keys):
            matched.append(row)
    return dedupe_rows(matched, limit=limit)


@st.cache_data(show_spinner=False, ttl=600)
def search_candidates(query: str, market: str, exchange_choice: str = "전체", max_results: int = 5000) -> list[dict[str, str]]:
    keyword = query.strip()
    if not keyword:
        return []

    key = keyword.replace(" ", "").lower()

    if market == "KR":
        krx_df = get_krx_universe_df(exchange_choice)
        if not krx_df.empty:
            mask = krx_df["name_norm"].str.contains(re.escape(key), regex=True, na=False) | krx_df["symbol_norm"].str.contains(
                re.escape(key), regex=True, na=False
            )
            matched_df = krx_df.loc[mask, ["name", "symbol", "exchange", "currency", "price", "name_norm"]].copy()
            if not matched_df.empty:
                matched_df["_exact_first"] = (matched_df["name_norm"] != key).astype(int)
                matched_df = matched_df.sort_values(by=["_exact_first", "name"])
                return matched_df[["name", "symbol", "exchange", "currency", "price"]].head(max_results).to_dict("records")
    else:
        us_df = get_us_universe_df()
        if not us_df.empty:
            mask = us_df["name_norm"].str.contains(re.escape(key), regex=True, na=False) | us_df["symbol_norm"].str.contains(
                re.escape(key), regex=True, na=False
            )
            matched_df = us_df.loc[mask, ["name", "symbol", "exchange", "currency", "price", "name_norm", "symbol_norm"]].copy()
            if not matched_df.empty:
                exact_rank = ((matched_df["symbol_norm"] != key) & (matched_df["name_norm"] != key)).astype(int)
                matched_df["_exact_first"] = exact_rank
                matched_df = matched_df.sort_values(by=["_exact_first", "name"])
                return matched_df[["name", "symbol", "exchange", "currency", "price"]].head(max_results).to_dict("records")

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

    return dedupe_rows(results, limit=max_results)


def resolve_ticker(raw_input: str, market: str, kr_exchange: str, exchange_choice: str = "전체") -> tuple[str, str]:
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
        scope_exchange = exchange_choice if exchange_choice in {"KOSPI", "KOSDAQ", "KONEX"} else "전체"
        kr_df = get_krx_universe_df(scope_exchange)
        if not kr_df.empty:
            exact_df = kr_df.loc[kr_df["name_norm"] == key, "symbol"]
            if not exact_df.empty:
                return str(exact_df.iloc[0]), "krx_exact"
            partial_df = kr_df.loc[kr_df["name_norm"].str.contains(re.escape(key), regex=True, na=False), "symbol"]
            if key and not partial_df.empty:
                return str(partial_df.iloc[0]), "krx_partial"
    else:
        us_df = get_us_universe_df()
        if not us_df.empty:
            exact_df = us_df.loc[(us_df["symbol_norm"] == key) | (us_df["name_norm"] == key), "symbol"]
            if not exact_df.empty:
                return str(exact_df.iloc[0]), "us_exact"
            partial_df = us_df.loc[
                us_df["name_norm"].str.contains(re.escape(key), regex=True, na=False)
                | us_df["symbol_norm"].str.contains(re.escape(key), regex=True, na=False),
                "symbol",
            ]
            if key and not partial_df.empty:
                return str(partial_df.iloc[0]), "us_partial"

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


def fetch_krx_ohlcv_fdr(symbol: str, period: str) -> pd.DataFrame:
    if not FDR_AVAILABLE:
        return pd.DataFrame()
    ticker = symbol.split(".")[0]
    if (not ticker.isdigit()) or len(ticker) != 6:
        return pd.DataFrame()

    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=period_to_days(period))
    try:
        df = fdr.DataReader(ticker, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()
    needed = ["Open", "High", "Low", "Close"]
    for col in needed:
        if col not in df.columns:
            return pd.DataFrame()
    if "Volume" not in df.columns:
        df["Volume"] = 0
    df.index = pd.to_datetime(df.index)
    return df[["Open", "High", "Low", "Close", "Volume"]]


@st.cache_data(show_spinner=False, ttl=60 * 30)
def get_kr_investor_ratio(symbol: str, lookback_days: int = 60) -> dict | None:
    if not KRX_AVAILABLE:
        return None
    code = str(symbol).split(".")[0]
    if (not code.isdigit()) or len(code) != 6:
        return None

    to_date = dt.date.today()
    from_date = to_date - dt.timedelta(days=lookback_days)
    from_s = from_date.strftime("%Y%m%d")
    to_s = to_date.strftime("%Y%m%d")

    try:
        buy_df = krx_stock.get_market_trading_value_by_date(from_s, to_s, code, on="매수")
        sell_df = krx_stock.get_market_trading_value_by_date(from_s, to_s, code, on="매도")
    except Exception:
        return None

    if buy_df is None or buy_df.empty:
        return None

    def _col(df: pd.DataFrame, names: list[str]) -> float:
        for n in names:
            if n in df.columns:
                try:
                    return float(df[n].fillna(0).sum())
                except Exception:
                    return 0.0
        return 0.0

    foreign_buy = _col(buy_df, ["외국인합계", "외국인"])
    individual_buy = _col(buy_df, ["개인"])

    foreign_sell = _col(sell_df, ["외국인합계", "외국인"]) if sell_df is not None and not sell_df.empty else 0.0
    individual_sell = _col(sell_df, ["개인"]) if sell_df is not None and not sell_df.empty else 0.0

    total_buy = foreign_buy + individual_buy
    foreign_buy_ratio = (foreign_buy / total_buy * 100.0) if total_buy > 0 else np.nan
    individual_buy_ratio = (individual_buy / total_buy * 100.0) if total_buy > 0 else np.nan

    foreign_net = foreign_buy - foreign_sell
    individual_net = individual_buy - individual_sell

    return {
        "foreign_buy_ratio": foreign_buy_ratio,
        "individual_buy_ratio": individual_buy_ratio,
        "foreign_net": foreign_net,
        "individual_net": individual_net,
        "lookback_days": lookback_days,
    }


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
        for sym in dedup_candidates:
            df = fetch_krx_ohlcv_pykrx(sym, period)
            if not df.empty:
                return df, f"pykrx:{sym}(interval=1d)", sym
        for sym in dedup_candidates:
            df = fetch_krx_ohlcv_fdr(sym, period)
            if not df.empty:
                return df, f"fdr:{sym}(interval=1d)", sym

    return pd.DataFrame(), f"failed:{','.join(tried)}", ticker


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "Volume" not in out.columns:
        out["Volume"] = 0
    out["SMA20"] = out["Close"].rolling(20).mean()
    out["SMA60"] = out["Close"].rolling(60).mean()
    out["VOL_SMA20"] = out["Volume"].rolling(20).mean()
    std20 = out["Close"].rolling(20).std()
    out["BB_UPPER"] = out["SMA20"] + (2 * std20)
    out["BB_LOWER"] = out["SMA20"] - (2 * std20)
    out["BB_WIDTH"] = (out["BB_UPPER"] - out["BB_LOWER"]) / out["SMA20"].replace(0, np.nan)

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


def resample_price_data(df: pd.DataFrame, view_mode: str) -> pd.DataFrame:
    if view_mode == "일별":
        return df.copy()
    rule_map = {
        "주별": "W-FRI",
        "월별": "M",
        "년별": "Y",
    }
    rule = rule_map.get(view_mode)
    if not rule:
        return df.copy()
    agg = {
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }
    out = df.resample(rule).agg(agg).dropna(subset=["Open", "High", "Low", "Close"])
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


def get_benchmark_symbol(market: str, exchange_choice: str) -> str:
    if market == "KR":
        if exchange_choice == "KOSDAQ":
            return "^KQ11"
        return "^KS11"
    return "^GSPC"


@st.cache_data(show_spinner=False, ttl=60 * 60)
def get_benchmark_close_series(market: str, exchange_choice: str, period: str = "2y") -> pd.Series:
    symbol = get_benchmark_symbol(market, exchange_choice)
    df = yfinance_download_safe(symbol, period=period, interval="1d")
    if df.empty or "Close" not in df.columns:
        return pd.Series(dtype=float)
    out = df["Close"].astype(float).dropna()
    out.index = pd.to_datetime(out.index)
    return out


def enrich_forecast(df: pd.DataFrame, forecast: dict | None) -> dict | None:
    if forecast is None:
        return None
    if "path" not in forecast or forecast["path"] is None or forecast["path"].empty:
        return forecast

    fdf = forecast["path"].copy()
    base = fdf["Forecast"].astype(float).values
    if len(base) == 0:
        return forecast

    close_ret = df["Close"].astype(float).pct_change().dropna()
    vol = float(close_ret.std()) if len(close_ret) > 20 else 0.015
    vol = float(np.clip(vol, 0.005, 0.06))

    t = np.arange(1, len(base) + 1, dtype=float)
    band = np.clip(vol * np.sqrt(t) * 1.15, 0.0, 0.90)
    bull = np.maximum(base * np.exp(band), 0.01)
    bear = np.maximum(base * np.exp(-band), 0.01)

    fdf["Bull"] = bull
    fdf["Bear"] = bear
    forecast["path"] = fdf

    last_price = float(df["Close"].iloc[-1])
    forecast["ret_12m_bull"] = (bull[-1] / last_price - 1) * 100
    forecast["ret_12m_bear"] = (bear[-1] / last_price - 1) * 100

    h = len(base)
    front = max(10, min(63, h // 3 if h >= 3 else h))
    if front >= h:
        front = max(1, h - 1)

    if float(forecast.get("ret_12m", 0.0)) >= 0:
        buy_idx = int(np.argmin(base[:front]))
        sell_idx = buy_idx + int(np.argmax(base[buy_idx:]))
    else:
        sell_idx = int(np.argmax(base[:front]))
        buy_idx = sell_idx + int(np.argmin(base[sell_idx:]))

    buy_idx = int(np.clip(buy_idx, 0, h - 1))
    sell_idx = int(np.clip(sell_idx, 0, h - 1))
    if buy_idx == sell_idx and h >= 2:
        sell_idx = min(h - 1, buy_idx + 1)

    forecast["entry_point"] = {"x": fdf.index[buy_idx], "y": float(fdf["Forecast"].iloc[buy_idx])}
    forecast["exit_point"] = {"x": fdf.index[sell_idx], "y": float(fdf["Forecast"].iloc[sell_idx])}
    return forecast


def compute_decision_score(df: pd.DataFrame, forecast: dict | None, market: str, exchange_choice: str) -> dict:
    latest = df.iloc[-1]

    trend_score = 0.0
    if pd.notna(latest.get("SMA20", np.nan)) and pd.notna(latest.get("SMA60", np.nan)):
        if float(latest["SMA20"]) > float(latest["SMA60"]):
            trend_score += 0.6
    rsi = latest.get("RSI", np.nan)
    if pd.notna(rsi):
        rsi_v = float(rsi)
        if 50 <= rsi_v <= 70:
            trend_score += 0.4
        elif 45 <= rsi_v < 50:
            trend_score += 0.2

    breakout_score = 0.0
    width_series = df["BB_WIDTH"].dropna().tail(120)
    width_q35 = float(width_series.quantile(0.35)) if len(width_series) >= 20 else np.nan
    squeeze = pd.notna(width_q35) and pd.notna(latest.get("BB_WIDTH", np.nan)) and float(latest["BB_WIDTH"]) <= width_q35
    vol_ok = pd.notna(latest.get("VOL_SMA20", np.nan)) and float(latest.get("VOL_SMA20", 0)) > 0 and float(latest["Volume"]) >= float(latest["VOL_SMA20"]) * 1.2
    price_break = pd.notna(latest.get("BB_UPPER", np.nan)) and float(latest["Close"]) > float(latest["BB_UPPER"])
    if squeeze and vol_ok and price_break:
        breakout_score = 1.0
    elif price_break:
        breakout_score = 0.6
    elif squeeze:
        breakout_score = 0.4

    rs_score = 0.5
    benchmark = get_benchmark_close_series(market, exchange_choice, period="2y")
    if not benchmark.empty and len(df) >= 65:
        try:
            stock_close = df["Close"].astype(float).dropna()
            combined = pd.concat([stock_close.rename("stock"), benchmark.rename("bench")], axis=1).dropna()
            if len(combined) >= 65:
                sret = combined["stock"].iloc[-1] / combined["stock"].iloc[-61] - 1
                bret = combined["bench"].iloc[-1] / combined["bench"].iloc[-61] - 1
                rel = float(sret - bret)
                if rel > 0.05:
                    rs_score = 1.0
                elif rel > 0.0:
                    rs_score = 0.7
                elif rel > -0.03:
                    rs_score = 0.4
                else:
                    rs_score = 0.1
        except Exception:
            rs_score = 0.5

    forecast_score = 0.5
    ret12 = float(forecast.get("ret_12m", 0.0)) if forecast is not None else 0.0
    if ret12 >= 12:
        forecast_score = 1.0
    elif ret12 >= 5:
        forecast_score = 0.8
    elif ret12 <= -12:
        forecast_score = 0.0
    elif ret12 <= -5:
        forecast_score = 0.2

    weights = {"trend": 0.35, "breakout": 0.20, "relative_strength": 0.20, "forecast": 0.25}
    buy_score = (
        trend_score * weights["trend"]
        + breakout_score * weights["breakout"]
        + rs_score * weights["relative_strength"]
        + forecast_score * weights["forecast"]
    ) * 100.0
    buy_score = float(np.clip(buy_score, 0.0, 100.0))
    sell_score = float(np.clip(100.0 - buy_score, 0.0, 100.0))

    if buy_score >= 65:
        decision = "BUY"
        decision_label = "매수 우세"
    elif buy_score <= 35:
        decision = "SELL"
        decision_label = "매도 우세"
    else:
        decision = "HOLD"
        decision_label = "관망"

    return {
        "buy_score": buy_score,
        "sell_score": sell_score,
        "decision": decision,
        "decision_label": decision_label,
        "component_scores": {
            "trend_momentum": trend_score * 100.0,
            "volatility_breakout": breakout_score * 100.0,
            "relative_strength": rs_score * 100.0,
            "forecast_12m": forecast_score * 100.0,
        },
    }


def analyze_trade_setup(df: pd.DataFrame, forecast: dict | None, decision: dict, investment_amount: float) -> dict:
    latest_close = float(df["Close"].iloc[-1])
    out = {
        "max_loss_pct": np.nan,
        "max_loss_amount": np.nan,
        "reward_risk_ratio": np.nan,
        "mandatory_pass": False,
        "mandatory_pass_count": 0,
        "mandatory_conditions": {},
    }
    if forecast is None or "path" not in forecast or forecast["path"] is None or forecast["path"].empty:
        return out

    fdf = forecast["path"]
    bear_series = fdf["Bear"] if "Bear" in fdf.columns else fdf["Forecast"]
    bull_series = fdf["Bull"] if "Bull" in fdf.columns else fdf["Forecast"]

    worst_future_price = float(pd.Series(bear_series).min())
    best_future_price = float(pd.Series(bull_series).max())

    max_loss_pct = (worst_future_price / latest_close - 1.0) * 100.0
    max_gain_pct = (best_future_price / latest_close - 1.0) * 100.0
    downside_pct = abs(min(max_loss_pct, 0.0))
    upside_pct = max(max_gain_pct, 0.0)
    reward_risk_ratio = (upside_pct / downside_pct) if downside_pct > 0 else np.nan

    cond_trend = bool(decision["component_scores"].get("trend_momentum", 0.0) >= 60.0)
    cond_rs = bool(decision["component_scores"].get("relative_strength", 0.0) >= 70.0)
    cond_forecast = bool(float(forecast.get("ret_6m", np.nan)) > 0 and float(forecast.get("ret_12m", np.nan)) > 0)
    mandatory_conditions = {
        "trend_momentum": cond_trend,
        "relative_strength": cond_rs,
        "positive_mid_long_forecast": cond_forecast,
    }
    pass_count = sum(1 for x in mandatory_conditions.values() if x)

    out.update(
        {
            "max_loss_pct": max_loss_pct,
            "max_loss_amount": investment_amount * (max_loss_pct / 100.0),
            "reward_risk_ratio": reward_risk_ratio,
            "mandatory_pass": pass_count == len(mandatory_conditions),
            "mandatory_pass_count": pass_count,
            "mandatory_conditions": mandatory_conditions,
        }
    )
    return out


def _get_openai_api_key() -> str:
    try:
        key = st.secrets.get("OPENAI_API_KEY", "")
    except Exception:
        key = ""
    return str(key or os.getenv("OPENAI_API_KEY", "")).strip()


def _get_secret_or_env(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.getenv(name, "")).strip()


def verify_premium_code(code: str) -> bool:
    expected = _get_secret_or_env("PREMIUM_ACCESS_CODE")
    if not expected:
        return False
    return hmac.compare_digest(str(code).strip(), expected)


def build_ai_analysis_payload(
    resolved_symbol: str,
    company_name: str,
    market: str,
    latest: pd.Series,
    forecast: dict | None,
    decision: dict,
    trade_setup: dict,
    investor_ratio: dict | None,
    total_return: float,
    trade_count: int,
    win_rate: float,
) -> dict:
    payload = {
        "symbol": resolved_symbol,
        "company_name": company_name or "",
        "market": market,
        "current_price": float(latest["Close"]),
        "rsi_14": float(latest["RSI"]) if pd.notna(latest.get("RSI", np.nan)) else None,
        "decision": decision,
        "trade_setup": trade_setup,
        "backtest": {
            "total_return_pct": float(total_return),
            "trade_count": int(trade_count),
            "win_rate_pct": float(win_rate),
        },
        "investor_flow_60d": investor_ratio,
    }
    if forecast is not None:
        payload["forecast"] = {
            "ret_1m_pct": float(forecast.get("ret_1m", np.nan)),
            "ret_2m_pct": float(forecast.get("ret_2m", np.nan)),
            "ret_3m_pct": float(forecast.get("ret_3m", np.nan)),
            "ret_6m_pct": float(forecast.get("ret_6m", np.nan)),
            "ret_12m_pct": float(forecast.get("ret_12m", np.nan)),
            "ret_12m_bull_pct": float(forecast.get("ret_12m_bull", np.nan)),
            "ret_12m_bear_pct": float(forecast.get("ret_12m_bear", np.nan)),
            "signal_label": str(forecast.get("signal_label", "")),
            "confidence_pct": float(forecast.get("confidence", np.nan)),
        }
    return payload


@st.cache_data(show_spinner=False, ttl=60 * 20)
def generate_ai_analysis(payload_json: str, model: str = "gpt-5.4-mini") -> str:
    if not OPENAI_AVAILABLE:
        return "OpenAI 패키지가 설치되어 있지 않습니다. requirements.txt 배포 후 다시 시도하세요."
    api_key = _get_openai_api_key()
    if not api_key:
        return "OPENAI_API_KEY가 설정되어 있지 않습니다. Streamlit Secrets 또는 환경변수에 API 키를 추가하세요."

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model,
            instructions=(
                "너는 주식 분석 웹의 보조 해설자다. 사용자가 제공한 계산 결과만 근거로 한국어로 설명한다. "
                "새로운 가격, 뉴스, 실적, 재무정보를 추측하지 않는다. 투자 권유처럼 단정하지 말고 "
                "'데이터상', '조건상', '주의' 표현을 사용한다. 마지막에는 참고용 분석이며 최종 판단은 사용자 책임이라고 짧게 적는다."
            ),
            input=(
                "아래 JSON은 앱이 계산한 주식 분석 결과다. "
                "1) 핵심 요약 4줄, 2) 긍정 요인, 3) 위험 요인, 4) 지금 확인할 조건을 간결하게 작성하라.\n\n"
                f"{payload_json}"
            ),
        )
        return response.output_text
    except Exception as exc:
        err_name = type(exc).__name__
        err_text = str(exc).lower()
        if "rate" in err_text or "quota" in err_text or err_name in {"RateLimitError", "APIStatusError"}:
            return "AI 요약을 생성하지 못했습니다. OpenAI 사용량 한도 또는 결제/쿼터 제한에 걸린 상태입니다. 잠시 후 다시 시도하거나 OpenAI 결제/사용량 설정을 확인하세요."
        return f"AI 요약을 생성하지 못했습니다. 오류 유형: {err_name}"


def build_forecast(df: pd.DataFrame, model_name: str = "baseline", horizon_days: int = 252) -> dict | None:
    if ML_FORECAST_AVAILABLE and build_ml_forecast is not None:
        return build_ml_forecast(df, model_name=model_name, horizon_days=horizon_days)

    # Fallback when module import fails in some environments.
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
    ret_6m = (future[min(125, horizon_days - 1)] / last_price - 1) * 100
    ret_12m = (future[min(251, horizon_days - 1)] / last_price - 1) * 100

    if ret_12m >= 8:
        signal = "BUY"
        signal_label = "예상 매수지점"
    elif ret_12m <= -8:
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
        "ret_6m": ret_6m,
        "ret_12m": ret_12m,
        "signal": signal,
        "signal_label": signal_label,
        "confidence": 50.0,
        "model": "baseline",
        "mae": np.nan,
        "direction_acc": np.nan,
    }


def build_chart(df: pd.DataFrame, ticker: str, mobile_mode: bool, forecast: dict | None = None):
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
            increasing_line_color="#d93025",
            increasing_fillcolor="#d93025",
            decreasing_line_color="#1f6feb",
            decreasing_fillcolor="#1f6feb",
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

    if forecast is not None:
        fdf = forecast["path"]
        horizon_days = len(fdf)
        horizon_months = max(1, int(round(horizon_days / 21)))
        up = forecast["signal"] == "BUY"
        down = forecast["signal"] == "SELL"
        fc_color = "#9ec5fe" if up else ("#ffc9c9" if down else "#ced4da")
        marker_color = "#1971c2" if up else ("#c92a2a" if down else "#495057")

        fig.add_trace(
            go.Scatter(
                x=fdf.index,
                y=fdf["Forecast"],
                mode="lines",
                name=f"예측 경로({horizon_months}개월)",
                line=dict(color=fc_color, width=3, dash="dot"),
            ),
            row=1,
            col=1,
        )
        if "Bull" in fdf.columns:
            fig.add_trace(
                go.Scatter(
                    x=fdf.index,
                    y=fdf["Bull"],
                    mode="lines",
                    name="낙관 시나리오",
                    line=dict(color="#74c0fc", width=1.8, dash="dash"),
                ),
                row=1,
                col=1,
            )
        if "Bear" in fdf.columns:
            fig.add_trace(
                go.Scatter(
                    x=fdf.index,
                    y=fdf["Bear"],
                    mode="lines",
                    name="비관 시나리오",
                    line=dict(color="#ffa8a8", width=1.8, dash="dash"),
                ),
                row=1,
                col=1,
            )

        horizon_points = [("1M", 20), ("2M", 41), ("3M", 62), ("6M", 125), ("12M", 251)]
        hx = []
        hy = []
        htext = []
        for label, idx in horizon_points:
            if idx < horizon_days:
                hx.append(fdf.index[idx])
                hy.append(float(fdf["Forecast"].iloc[idx]))
                htext.append(label)
        if hx:
            fig.add_trace(
                go.Scatter(
                    x=hx,
                    y=hy,
                    mode="markers+text",
                    name="예측 구간",
                    marker=dict(symbol="circle", size=7, color=fc_color, line=dict(width=1, color="#495057")),
                    text=htext,
                    textposition="top center",
                ),
                row=1,
                col=1,
            )

        fig.add_trace(
            go.Scatter(
                x=[df.index[-1]],
                y=[df["Close"].iloc[-1]],
                mode="markers+text",
                name="예측 신호",
                marker=dict(symbol="diamond", size=12, color=marker_color),
                text=[forecast["signal_label"]],
                textposition="top center",
            ),
            row=1,
            col=1,
        )
        if "entry_point" in forecast:
            ep = forecast["entry_point"]
            fig.add_trace(
                go.Scatter(
                    x=[ep["x"]],
                    y=[ep["y"]],
                    mode="markers+text",
                    name="예상 매수지점",
                    marker=dict(symbol="triangle-up", size=14, color="#2b8a3e"),
                    text=["예상 매수지점"],
                    textposition="bottom right",
                ),
                row=1,
                col=1,
            )
        if "exit_point" in forecast:
            xp = forecast["exit_point"]
            fig.add_trace(
                go.Scatter(
                    x=[xp["x"]],
                    y=[xp["y"]],
                    mode="markers+text",
                    name="예상 매도지점",
                    marker=dict(symbol="triangle-down", size=14, color="#c92a2a"),
                    text=["예상 매도지점"],
                    textposition="top right",
                ),
                row=1,
                col=1,
            )
        max_x = fdf.index.max() + pd.Timedelta(days=5)
    else:
        max_x = df.index.max() + pd.Timedelta(days=5)

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
        template="plotly_dark",
        paper_bgcolor="#0b0f19",
        plot_bgcolor="#0b0f19",
        font=dict(color="#f4f7fb"),
        xaxis_rangeslider_visible=False,
        height=900 if mobile_mode else 980,
        legend=dict(orientation="h", y=1.02, x=0.01),
        margin=dict(l=20, r=20, t=60, b=20),
        dragmode="pan" if mobile_mode else "zoom",
        hovermode="x unified",
        uirevision="keep_pan_state",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#273244", zerolinecolor="#39465d")
    fig.update_yaxes(showgrid=True, gridcolor="#273244", zerolinecolor="#39465d")
    fig.update_xaxes(fixedrange=False)
    fig.update_yaxes(fixedrange=mobile_mode)

    window_bars = 120 if mobile_mode else 220
    start_idx = max(0, len(df) - window_bars)
    start_x = df.index[start_idx]
    fig.update_xaxes(range=[start_x, max_x], row=1, col=1)
    fig.update_xaxes(range=[start_x, max_x], row=2, col=1)
    return fig


st.sidebar.header("설정")
app_state = load_user_state()
billing_enabled = is_billing_enabled()
billing_config = get_billing_config()

if "billing_user_id" not in st.session_state:
    st.session_state["billing_user_id"] = ""

st.sidebar.markdown("**사용자/과금**")
user_id_input = st.sidebar.text_input(
    "사용자 ID",
    value=st.session_state["billing_user_id"],
    placeholder="이메일 또는 닉네임",
    help="사용자별 최근 종목, 즐겨찾기, 무료 사용량, 크레딧을 분리합니다.",
)
current_user_id = normalize_user_id(user_id_input)
st.session_state["billing_user_id"] = current_user_id
if billing_enabled and not current_user_id:
    st.sidebar.warning("과금 모드에서는 사용자 ID가 필요합니다.")
current_user_record = get_or_create_user_record(app_state, current_user_id or "guest")
today_usage = current_user_record.setdefault("daily_usage", {}).setdefault(
    _today_key(), {"analysis": 0, "ai_summary": 0}
)
st.sidebar.caption(
    f"크레딧 {int(current_user_record.get('credits', 0) or 0)}개 | "
    f"오늘 무료 분석 {int(today_usage.get('analysis', 0) or 0)}/{billing_config['free_daily_analyses']}회"
)
if billing_enabled:
    grant_code = st.sidebar.text_input("크레딧 충전 코드", type="password", value="", placeholder="관리자/결제 코드")
    if st.sidebar.button("크레딧 충전"):
        ok, msg = apply_admin_credit_code(current_user_record, grant_code, billing_config["admin_credit_grant"])
        save_user_state(app_state)
        if ok:
            st.sidebar.success(msg)
            st.rerun()
        else:
            st.sidebar.warning(msg)
    with st.sidebar.expander("크레딧 상품 예시", expanded=False):
        for product in BILLING_PRODUCTS.values():
            st.write(f"{product['label']}: {product['price_krw']:,}원")
        st.caption("현재는 관리자 충전 코드 방식입니다. 이후 Toss/Stripe 결제 승인 후 자동 충전으로 교체합니다.")
else:
    st.sidebar.caption("과금 모드 꺼짐: `BILLING_ENABLED=true` 설정 시 사용자별 크레딧 차감이 활성화됩니다.")

recent_symbols = current_user_record.get("recent", [])
favorite_symbols = current_user_record.get("favorites", [])

if "is_premium" not in st.session_state:
    st.session_state["is_premium"] = False

st.sidebar.markdown("**멤버십**")
premium_code = st.sidebar.text_input("프리미엄 코드", type="password", value="", placeholder="코드 입력")
if st.sidebar.button("프리미엄 활성화"):
    if verify_premium_code(premium_code):
        st.session_state["is_premium"] = True
        st.sidebar.success("프리미엄 기능이 활성화되었습니다.")
    else:
        st.sidebar.warning("프리미엄 코드가 올바르지 않습니다.")
if st.session_state["is_premium"]:
    st.sidebar.caption("현재 플랜: 프리미엄")
    if st.sidebar.button("프리미엄 해제"):
        st.session_state["is_premium"] = False
        st.rerun()
else:
    st.sidebar.caption("현재 플랜: 무료")
has_credit_access = billing_enabled and int(current_user_record.get("credits", 0) or 0) > 0
is_premium = bool(st.session_state["is_premium"] or has_credit_access)
if billing_enabled and has_credit_access:
    st.sidebar.caption("유료 크레딧 보유: 프리미엄 분석 기능 사용 가능")

market = st.sidebar.selectbox("시장", ["US", "KR"], index=0)
if market == "KR":
    exchange_choice = st.sidebar.selectbox("거래소", ["전체", "KOSPI", "KOSDAQ", "KONEX"], index=0)
    kr_exchange = "KOSDAQ" if exchange_choice == "KOSDAQ" else "KOSPI"
    index_basket_label = st.sidebar.selectbox("대표지수 구성종목", ["없음", "KOSPI 50", "KOSDAQ 100"], index=0)
else:
    exchange_choice = st.sidebar.selectbox("거래소", ["전체", "NASDAQ", "NYSE", "NYSE American", "NYSE Arca", "IEX", "BATS"], index=0)
    kr_exchange = "KOSPI"
    index_basket_label = "없음"

theme_choice = st.sidebar.selectbox("테마 카테고리", THEME_OPTIONS, index=0)

if theme_choice != "없음":
    input_label = "테마 내 회사명 필터(선택)"
    default_value = ""
else:
    input_label = "티커 또는 회사명"
    default_value = ""
user_input = st.sidebar.text_input(input_label, value=default_value).strip()

theme_candidates = filter_candidates_by_exchange(
    get_theme_candidates(theme_choice, market, exchange_choice=exchange_choice, limit=5000),
    market,
    exchange_choice,
)
search_base_candidates = filter_candidates_by_exchange(
    search_candidates(user_input, market, exchange_choice=exchange_choice, max_results=5000)
    if len(user_input) >= (2 if (market == "KR" and exchange_choice == "전체") else 1)
    else [],
    market,
    exchange_choice,
)

index_basket_rows: list[dict[str, str]] = []
if market == "KR" and index_basket_label != "없음":
    idx_key = "KOSPI50" if index_basket_label == "KOSPI 50" else "KOSDAQ100"
    index_basket_rows = get_krx_index_constituents(idx_key)
    st.sidebar.caption(f"{index_basket_label} 구성종목 {len(index_basket_rows)}개")

key = user_input.replace(" ", "").lower()
theme_filtered_all: list[dict[str, str]] = []
if theme_choice != "없음":
    base = theme_candidates
    filtered_theme = []
    for row in base:
        row_key = row["name"].replace(" ", "").lower()
        sym_key = row["symbol"].replace(".", "").lower()
        if (not key) or (key in row_key) or (key in sym_key):
            filtered_theme.append(row)
    theme_filtered_all = dedupe_rows(filtered_theme, limit=5000)
    candidates_all = theme_filtered_all
else:
    if key:
        candidates_all = dedupe_rows(search_base_candidates, limit=5000)
    else:
        if market == "KR":
            # KR 전체는 초기 로딩이 무거워서 검색어 입력 전에는 목록 로딩을 생략한다.
            if exchange_choice == "전체":
                candidates_all = []
            else:
                candidates_all = dedupe_rows(get_krx_universe(exchange_choice), limit=5000)
        else:
            universe = get_us_universe()
            universe = filter_candidates_by_exchange(universe, market, exchange_choice)
            candidates_all = dedupe_rows(universe, limit=5000)

if index_basket_rows:
    idx_filtered = []
    for row in index_basket_rows:
        row_key = row["name"].replace(" ", "").lower()
        sym_key = row["symbol"].replace(".", "").lower()
        if (not key) or (key in row_key) or (key in sym_key):
            idx_filtered.append(row)
    candidates_all = dedupe_rows(idx_filtered, limit=5000)

theme_selected_symbol = ""
if theme_choice != "없음" and theme_filtered_all:
    st.sidebar.markdown("**테마 관련회사 선택**")
    st.sidebar.caption(f"테마 필터 후보 총 {len(theme_filtered_all)}개")
    theme_page_size = st.sidebar.selectbox("테마 표시 수", [20, 50, 100], index=1, key="theme_page_size")
    theme_total_pages = max(1, int(np.ceil(len(theme_filtered_all) / theme_page_size)))
    theme_page = int(
        st.sidebar.number_input("테마 페이지", min_value=1, max_value=theme_total_pages, value=1, step=1, key="theme_page")
    )
    t_start = (theme_page - 1) * theme_page_size
    theme_page_rows = theme_filtered_all[t_start : t_start + theme_page_size]
    st.sidebar.caption(f"테마 후보 {len(theme_filtered_all)}개 / 현재 {theme_page}/{theme_total_pages}")
    theme_option_labels = ["선택 안함"] + [
        f"{c['name']} | {c['symbol']} | {c['exchange']}" for c in theme_page_rows
    ]
    theme_choice_label = st.sidebar.selectbox("테마 회사", theme_option_labels, index=0, key="theme_company_select")
    if theme_choice_label != "선택 안함":
        theme_selected_symbol = theme_choice_label.split("|")[1].strip()
        st.sidebar.caption(f"테마 선택 티커: {theme_selected_symbol}")

index_selected_symbol = ""
if index_basket_rows:
    st.sidebar.markdown("**지수 구성종목 선택**")
    index_page_size = st.sidebar.selectbox("지수 표시 수", [20, 50, 100], index=1, key="index_page_size")
    index_total_pages = max(1, int(np.ceil(len(index_basket_rows) / index_page_size)))
    index_page = int(
        st.sidebar.number_input("지수 페이지", min_value=1, max_value=index_total_pages, value=1, step=1, key="index_page")
    )
    i_start = (index_page - 1) * index_page_size
    index_page_rows = index_basket_rows[i_start : i_start + index_page_size]
    st.sidebar.caption(f"지수 후보 {len(index_basket_rows)}개 / 현재 {index_page}/{index_total_pages}")
    index_option_labels = ["선택 안함"] + [
        f"{c['name']} | {c['symbol']} | {c['exchange']}" for c in index_page_rows
    ]
    index_choice_label = st.sidebar.selectbox("지수 회사", index_option_labels, index=0, key="index_company_select")
    if index_choice_label != "선택 안함":
        index_selected_symbol = index_choice_label.split("|")[1].strip()
        st.sidebar.caption(f"지수 선택 티커: {index_selected_symbol}")

selected_symbol = ""
if theme_choice == "없음":
    if market == "KR" and exchange_choice == "전체" and not key:
        st.sidebar.caption("KR 전체는 회사명/종목코드 2글자 이상 입력 시 후보를 불러옵니다.")
    st.sidebar.caption(f"검색 후보 총 {len(candidates_all)}개")
    page_size = st.sidebar.selectbox("후보 표시 수", [20, 50, 100, 200], index=2)
    total_pages = max(1, int(np.ceil(len(candidates_all) / page_size))) if candidates_all else 1
    candidate_page = int(
        st.sidebar.number_input("후보 페이지", min_value=1, max_value=total_pages, value=1, step=1)
    )
    start_idx = (candidate_page - 1) * page_size
    candidates = candidates_all[start_idx : start_idx + page_size]
    st.sidebar.caption(f"현재 페이지: {candidate_page}/{total_pages}")
else:
    candidates = []

if theme_choice == "없음" and candidates_all and candidates:
    option_labels = [
        f"{c['name']} | {c['symbol']} | {c['exchange']} | {c['currency']} | {c['price']}"
        for c in candidates
    ]
    label_to_symbol = {label: c["symbol"] for label, c in zip(option_labels, candidates)}
    selected_label = st.sidebar.selectbox("자동완성 후보", option_labels, index=0)
    selected_symbol = label_to_symbol[selected_label]
    st.sidebar.caption(f"선택 티커: {selected_symbol}")

quick_symbol = ""
st.sidebar.markdown("**최근 본 종목**")
if recent_symbols:
    for sym in recent_symbols[:10]:
        if st.sidebar.button(f"최근: {sym}", key=f"recent_btn_{sym}"):
            quick_symbol = sym
else:
    st.sidebar.caption("저장된 최근 종목이 없습니다.")

st.sidebar.markdown("**즐겨찾기**")
if favorite_symbols:
    for sym in favorite_symbols[:10]:
        if st.sidebar.button(f"★ {sym}", key=f"fav_btn_{sym}"):
            quick_symbol = sym
else:
    st.sidebar.caption("즐겨찾기 종목이 없습니다.")

candidate_symbol = index_selected_symbol or theme_selected_symbol or selected_symbol
if (not candidate_symbol) and user_input:
    r_ticker, _ = resolve_ticker(user_input, market, kr_exchange, exchange_choice)
    candidate_symbol = r_ticker

if candidate_symbol:
    cand_upper = candidate_symbol.upper()
    is_favorite = cand_upper in [x.upper() for x in favorite_symbols]
    fav_label = "즐겨찾기 삭제" if is_favorite else "즐겨찾기 추가"
    if st.sidebar.button(fav_label, key="fav_toggle_btn"):
        favs = [x.upper() for x in favorite_symbols]
        if is_favorite:
            favs = [x for x in favs if x != cand_upper]
        else:
            favs = [cand_upper] + [x for x in favs if x != cand_upper]
        current_user_record["favorites"] = favs[:50]
        save_user_state(app_state)
        st.rerun()

show_kosdaq_list = False
kosdaq_selected_symbol = ""
kosdaq_rows: list[dict[str, str]] = []
if market == "KR":
    use_kosdaq_picker = st.sidebar.toggle("KOSDAQ 빠른 선택 사용", value=False)
    show_kosdaq_list = st.sidebar.toggle("KOSDAQ 전체 목록 표 보기", value=False)
    if use_kosdaq_picker or show_kosdaq_list:
        kosdaq_rows = get_krx_universe("KOSDAQ")
    if use_kosdaq_picker and kosdaq_rows:
        st.sidebar.caption(f"KOSDAQ 상장사 {len(kosdaq_rows)}개")
        st.sidebar.markdown("**KOSDAQ 상장사 선택**")
        kosdaq_filter = st.sidebar.text_input("KOSDAQ 회사명 필터", value="", key="kosdaq_filter").strip()
        k_key = kosdaq_filter.replace(" ", "").lower()
        kosdaq_rows = sorted(kosdaq_rows, key=lambda r: (str(r.get("name", "")).lower(), str(r.get("symbol", ""))))
        if k_key:
            k_rows = [
                r
                for r in kosdaq_rows
                if (k_key in r["name"].replace(" ", "").lower()) or (k_key in r["symbol"].replace(".", "").lower())
            ]
        else:
            k_rows = kosdaq_rows
        st.sidebar.caption(f"필터 결과 {len(k_rows)}개")
        if (not k_key) and len(k_rows) > 400:
            st.sidebar.caption("회사명 필터를 입력하면 정확히 찾을 수 있습니다. (초기 400개만 표시)")
            visible_rows = k_rows[:400]
        else:
            visible_rows = k_rows
        options = ["선택 안함"] + [f"{r['name']} | {r['symbol']}" for r in visible_rows]
        picked = st.sidebar.selectbox("KOSDAQ 회사", options, index=0, key="kosdaq_company_select")
        if picked != "선택 안함":
            kosdaq_selected_symbol = picked.split("|")[1].strip()
            st.sidebar.caption(f"KOSDAQ 선택 티커: {kosdaq_selected_symbol} (선택 즉시 조회)")
    elif use_kosdaq_picker:
        st.sidebar.caption("KOSDAQ 상장사 데이터를 불러오지 못했습니다.")

period = st.sidebar.selectbox("기간", ["3mo", "6mo", "1y", "2y", "5y"], index=2)
interval = st.sidebar.selectbox("봉 간격", ["1d", "1h"], index=0)
view_mode = st.sidebar.selectbox("그래프 보기 단위", ["일별", "주별", "월별", "년별"], index=0)
forecast_model_label = st.sidebar.selectbox("예측 모델", list(FORECAST_MODELS.keys()), index=0)
forecast_horizon_options = [3, 6, 12] if is_premium else [3]
forecast_horizon_months = st.sidebar.selectbox("예측 그래프 기간(개월)", forecast_horizon_options, index=len(forecast_horizon_options) - 1)
if not is_premium:
    st.sidebar.caption("6개월/12개월 예측은 프리미엄 기능입니다.")
investment_amount = st.sidebar.number_input("가정 투자금", min_value=100000.0, value=1000000.0, step=100000.0)
mobile_mode = st.sidebar.toggle("모바일 최적화", value=True)

analyze_clicked = st.sidebar.button("분석 시작")
run_requested = analyze_clicked or bool(quick_symbol) or bool(kosdaq_selected_symbol)

if show_kosdaq_list:
    with st.expander("KOSDAQ 상장사 전체 목록", expanded=False):
        kdf = pd.DataFrame(kosdaq_rows)
        if kdf.empty:
            st.info("KOSDAQ 상장사 데이터를 불러오지 못했습니다. 잠시 후 다시 시도하세요.")
        else:
            for col in ["name", "symbol", "exchange", "currency"]:
                if col not in kdf.columns:
                    kdf[col] = ""
            kdf = kdf[["name", "symbol", "exchange", "currency"]]
            st.dataframe(kdf, use_container_width=True, height=420)

if run_requested:
    if kosdaq_selected_symbol:
        ticker, source = kosdaq_selected_symbol, "kosdaq_list"
    elif quick_symbol:
        ticker, source = quick_symbol, "quick_menu"
    elif index_selected_symbol:
        ticker, source = index_selected_symbol, "index_menu"
    elif theme_selected_symbol:
        ticker, source = theme_selected_symbol, "theme_menu"
    elif selected_symbol:
        ticker, source = selected_symbol, "autocomplete"
    else:
        ticker, source = resolve_ticker(user_input, market, kr_exchange, exchange_choice)
    if not ticker:
        st.error("티커 또는 회사명을 입력하세요.")
        st.stop()
    if billing_enabled and (analyze_clicked or bool(quick_symbol) or bool(kosdaq_selected_symbol)):
        if not current_user_id:
            st.error("사용자 ID를 입력해야 분석을 실행할 수 있습니다.")
            st.stop()
        ok, billing_msg = consume_user_feature(current_user_record, "analysis", billing_config)
        save_user_state(app_state)
        if not ok:
            st.error(billing_msg)
            st.info("크레딧 충전 코드가 있으면 왼쪽 사이드바에서 충전하세요.")
            st.stop()
        st.sidebar.success(billing_msg)
    st.session_state["last_analysis_request"] = {
        "ticker": ticker,
        "source": source,
        "market": market,
        "period": period,
        "interval": interval,
        "kr_exchange": kr_exchange,
        "exchange_choice": exchange_choice,
        "view_mode": view_mode,
        "forecast_model_label": forecast_model_label,
        "forecast_horizon_months": forecast_horizon_months,
        "investment_amount": float(investment_amount),
        "mobile_mode": bool(mobile_mode),
        "is_premium": bool(is_premium),
    }
elif "last_analysis_request" in st.session_state:
    req = st.session_state["last_analysis_request"]
    ticker = req["ticker"]
    source = req.get("source", "session")
    market = req.get("market", market)
    period = req.get("period", period)
    interval = req.get("interval", interval)
    kr_exchange = req.get("kr_exchange", kr_exchange)
    exchange_choice = req.get("exchange_choice", exchange_choice)
    view_mode = req.get("view_mode", view_mode)
    forecast_model_label = req.get("forecast_model_label", forecast_model_label)
    forecast_horizon_months = int(req.get("forecast_horizon_months", forecast_horizon_months))
    investment_amount = float(req.get("investment_amount", investment_amount))
    mobile_mode = bool(req.get("mobile_mode", mobile_mode))
    is_premium = bool(req.get("is_premium", is_premium))
    run_requested = True

if run_requested:
    with st.spinner("데이터를 가져오고 지표를 계산하는 중..."):
        raw, data_source, resolved_symbol = fetch_price_data(ticker, market, period, interval, kr_exchange)

    if raw.empty:
        st.error("데이터를 가져오지 못했습니다. 예: 애플/AAPL, 삼성전자/005930, 한화에어로스페이스")
    else:
        investor_ratio = None
        df_daily = add_indicators(raw)
        view_raw = resample_price_data(raw, view_mode)
        if view_raw.empty:
            view_raw = raw.copy()
        df = add_indicators(view_raw)
        forecast_model = FORECAST_MODELS[forecast_model_label]
        forecast = build_forecast(df_daily, model_name=forecast_model, horizon_days=forecast_horizon_months * 21)
        forecast = enrich_forecast(df_daily, forecast)
        decision = compute_decision_score(df_daily, forecast, market, exchange_choice)
        trade_setup = analyze_trade_setup(df_daily, forecast, decision, investment_amount)

        company_name = get_company_name_by_symbol(resolved_symbol, market)
        if company_name:
            st.success(f"{company_name} ({resolved_symbol}) 분석 완료")
        else:
            st.success(f"{resolved_symbol} 분석 완료")
        st.caption(
            f"입력 해석 방식: {source} | 데이터 소스: {data_source} | 업데이트 시간: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        current_user_record = add_recent_symbol(current_user_record, resolved_symbol, limit=30)
        save_user_state(app_state)

        chart = build_chart(df, resolved_symbol, mobile_mode, forecast)
        if chart is not None:
            if mobile_mode:
                plot_config = {
                    "displaylogo": False,
                    "scrollZoom": False,
                    "doubleClick": "reset",
                    "responsive": True,
                    "modeBarButtonsToRemove": [
                        "zoom2d",
                        "zoomIn2d",
                        "zoomOut2d",
                        "autoScale2d",
                        "lasso2d",
                        "select2d",
                    ],
                }
            else:
                plot_config = {
                    "displaylogo": False,
                    "scrollZoom": True,
                    "doubleClick": "reset+autosize",
                    "responsive": True,
                    "modeBarButtonsToRemove": [
                        "lasso2d",
                        "select2d",
                    ],
                }
            st.plotly_chart(chart, use_container_width=True, config=plot_config)
            if mobile_mode:
                st.caption("모바일 조작: 터치 후 끌어서 좌우 이동(팬) | 확대는 비활성화")
            else:
                st.caption("컴퓨터 조작: 마우스 드래그 확대(줌), 휠 확대/축소, 더블클릭 리셋")
        else:
            st.warning("현재 서버에 plotly가 없어 간단 차트로 표시합니다. requirements 재배포 후 캔들차트가 복구됩니다.")
            st.line_chart(df[["Close", "SMA20", "SMA60"]], use_container_width=True)

        latest = df.iloc[-1]
        quote_currency = "KRW" if market == "KR" else "USD"
        usdkrw_rate = get_usdkrw_rate()
        krw_value = convert_to_krw(float(latest["Close"]), quote_currency, usdkrw_rate)
        if bool(latest["BuySignal"]):
            signal_text = "매수"
        elif bool(latest["SellSignal"]):
            signal_text = "매도"
        else:
            signal_text = "관망"

        if mobile_mode:
            st.metric("현재가", f"{latest['Close']:.2f}")
            if krw_value is not None:
                st.metric("원화 환산가", f"{krw_value:,.0f} KRW")
            st.metric("RSI(14)", f"{latest['RSI']:.2f}" if pd.notna(latest["RSI"]) else "N/A")
            st.metric("최신 신호", signal_text)
        else:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("현재가", f"{latest['Close']:.2f}")
            col2.metric("원화 환산가", f"{krw_value:,.0f} KRW" if krw_value is not None else "N/A")
            col3.metric("RSI(14)", f"{latest['RSI']:.2f}" if pd.notna(latest["RSI"]) else "N/A")
            col4.metric("최신 신호", signal_text)

        if market == "KR" and is_premium:
            investor_ratio = get_kr_investor_ratio(resolved_symbol, lookback_days=60)
            if investor_ratio is not None:
                i1, i2, i3, i4 = st.columns(4)
                i1.metric("외국인 매수비율(60일)", f"{investor_ratio['foreign_buy_ratio']:.1f}%")
                i2.metric("개인 매수비율(60일)", f"{investor_ratio['individual_buy_ratio']:.1f}%")
                i3.metric("외국인 순매수(60일)", f"{investor_ratio['foreign_net']:,.0f}")
                i4.metric("개인 순매수(60일)", f"{investor_ratio['individual_net']:,.0f}")
            else:
                st.caption("외국인/개인 수급 비율 데이터: N/A")
        elif market == "KR":
            st.info("외국인/개인 수급 분석은 프리미엄 기능입니다.")

        if forecast is not None:
            if is_premium:
                p1, p2, p3, p4, p5 = st.columns(5)
                p1.metric("예상 수익률(1개월)", f"{forecast['ret_1m']:.2f}%")
                p2.metric("예상 수익률(2개월)", f"{forecast['ret_2m']:.2f}%")
                p3.metric("예상 수익률(3개월)", f"{forecast['ret_3m']:.2f}%")
                p4.metric("예상 수익률(6개월)", f"{forecast.get('ret_6m', np.nan):.2f}%")
                p5.metric("예상 수익률(1년)", f"{forecast.get('ret_12m', np.nan):.2f}%")
            else:
                p1, p2, p3 = st.columns(3)
                p1.metric("예상 수익률(1개월)", f"{forecast['ret_1m']:.2f}%")
                p2.metric("예상 수익률(2개월)", f"{forecast['ret_2m']:.2f}%")
                p3.metric("예상 수익률(3개월)", f"{forecast['ret_3m']:.2f}%")
                st.info("6개월/1년 예측과 시나리오 손익은 프리미엄 기능입니다.")
            st.caption(f"예측 신호: {forecast['signal_label']} | 추정 신뢰도: {forecast['confidence']:.1f}%")

            r1 = investment_amount * (forecast["ret_1m"] / 100.0)
            r2 = investment_amount * (forecast["ret_2m"] / 100.0)
            r3 = investment_amount * (forecast["ret_3m"] / 100.0)
            r6 = investment_amount * (forecast.get("ret_6m", np.nan) / 100.0)
            r12 = investment_amount * (forecast.get("ret_12m", np.nan) / 100.0)
            if is_premium:
                a1, a2, a3, a4, a5 = st.columns(5)
                a1.metric(f"예상 손익(1M, {investment_amount:,.0f})", f"{r1:,.0f}")
                a2.metric("예상 손익(2M)", f"{r2:,.0f}")
                a3.metric("예상 손익(3M)", f"{r3:,.0f}")
                a4.metric("예상 손익(6M)", f"{r6:,.0f}" if pd.notna(r6) else "N/A")
                a5.metric("예상 손익(1Y)", f"{r12:,.0f}" if pd.notna(r12) else "N/A")
            else:
                a1, a2, a3 = st.columns(3)
                a1.metric(f"예상 손익(1M, {investment_amount:,.0f})", f"{r1:,.0f}")
                a2.metric("예상 손익(2M)", f"{r2:,.0f}")
                a3.metric("예상 손익(3M)", f"{r3:,.0f}")

            if is_premium and pd.notna(forecast.get("ret_12m_bull", np.nan)) and pd.notna(forecast.get("ret_12m_bear", np.nan)):
                s1, s2, s3 = st.columns(3)
                s1.metric("12M 낙관 시나리오", f"{forecast['ret_12m_bull']:.2f}% / {investment_amount * (forecast['ret_12m_bull'] / 100.0):,.0f}")
                s2.metric("12M 기준 시나리오", f"{forecast['ret_12m']:.2f}% / {investment_amount * (forecast['ret_12m'] / 100.0):,.0f}")
                s3.metric("12M 비관 시나리오", f"{forecast['ret_12m_bear']:.2f}% / {investment_amount * (forecast['ret_12m_bear'] / 100.0):,.0f}")
            if pd.notna(forecast.get("mae", np.nan)):
                m1, m2 = st.columns(2)
                m1.metric("모델 MAE(일수익률)", f"{forecast['mae']:.3f}%")
                m2.metric("방향 정확도", f"{forecast.get('direction_acc', np.nan):.1f}%")

        d1, d2, d3 = st.columns(3)
        d1.metric("통합 매수 점수", f"{decision['buy_score']:.1f}/100")
        d2.metric("통합 매도 점수", f"{decision['sell_score']:.1f}/100")
        d3.metric("판단", decision["decision_label"])
        comp = decision["component_scores"]
        st.caption(
            "조건 점수 | "
            f"추세+모멘텀 {comp['trend_momentum']:.0f}, "
            f"변동성 돌파 {comp['volatility_breakout']:.0f}, "
            f"상대강도 {comp['relative_strength']:.0f}, "
            f"{'12M' if is_premium else '3M'} 예측 {comp['forecast_12m']:.0f}"
        )
        if is_premium:
            r1c, r2c, r3c = st.columns(3)
            r1c.metric("예상 최대손실", f"{trade_setup['max_loss_pct']:.2f}% / {trade_setup['max_loss_amount']:,.0f}" if pd.notna(trade_setup["max_loss_pct"]) else "N/A")
            r2c.metric("손익비", f"{trade_setup['reward_risk_ratio']:.2f}" if pd.notna(trade_setup["reward_risk_ratio"]) else "N/A")
            r3c.metric(
                "매수 필수조건",
                "통과" if trade_setup["mandatory_pass"] else f"{trade_setup['mandatory_pass_count']}/3 통과",
            )
            cond = trade_setup["mandatory_conditions"]
            st.caption(
                "필수조건 | "
                f"추세 우상향 {'OK' if cond.get('trend_momentum') else 'NO'}, "
                f"상대강도 우위 {'OK' if cond.get('relative_strength') else 'NO'}, "
                f"6M·12M 예측 양수 {'OK' if cond.get('positive_mid_long_forecast') else 'NO'}"
            )
        else:
            st.info("예상 최대손실, 손익비, 매수 필수조건 평가는 프리미엄 기능입니다.")

        equity, total_return, trade_count, win_rate = run_backtest(df_daily)

        st.subheader("AI 분석 요약")
        if is_premium:
            ai_payload = build_ai_analysis_payload(
                resolved_symbol=resolved_symbol,
                company_name=company_name,
                market=market,
                latest=latest,
                forecast=forecast,
                decision=decision,
                trade_setup=trade_setup,
                investor_ratio=investor_ratio,
                total_return=total_return,
                trade_count=trade_count,
                win_rate=win_rate,
            )
            if st.button("AI 분석 요약 생성", key=f"ai_summary_{resolved_symbol}"):
                if billing_enabled:
                    ok, billing_msg = consume_user_feature(current_user_record, "ai_summary", billing_config)
                    save_user_state(app_state)
                    if not ok:
                        st.warning(billing_msg)
                        st.stop()
                    st.caption(billing_msg)
                with st.spinner("AI가 계산 결과를 요약하는 중..."):
                    ai_text = generate_ai_analysis(json.dumps(ai_payload, ensure_ascii=False, default=str))
                if ai_text.startswith("AI 요약을 생성하지 못했습니다.") or ai_text.startswith("OPENAI_API_KEY") or ai_text.startswith("OpenAI 패키지"):
                    st.warning(ai_text)
                else:
                    st.write(ai_text)
            st.caption("AI 요약은 앱이 계산한 수치만 설명하며 투자 권유가 아닙니다.")
        else:
            st.info("AI 분석 요약은 프리미엄 기능입니다.")

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
        signal_table = df_daily.loc[df_daily["BuySignal"] | df_daily["SellSignal"], ["Close", "RSI", "BuySignal", "SellSignal"]].tail(10)
        st.dataframe(signal_table, use_container_width=True)
        st.caption("본 서비스는 데이터 분석 도구이며 투자자문 또는 투자 권유가 아닙니다. 모든 투자 판단과 손익 책임은 사용자에게 있습니다.")
else:
    st.info(
        "왼쪽에서 시장/회사명(또는 티커)을 입력한 뒤 '분석 시작'을 누르세요. 예: 애플, 삼성전자, 한화에어로스페이스, AAPL, 005930, 로봇, 방산, 반도체"
    )
    st.caption("본 서비스는 데이터 분석 도구이며 투자자문 또는 투자 권유가 아닙니다. 모든 투자 판단과 손익 책임은 사용자에게 있습니다.")
