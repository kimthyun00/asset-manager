"""태현의 포트폴리오 대시보드 v5."""

import json
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
import yfinance as yf


st.set_page_config(page_title="태현의 투자 대시보드", page_icon="📊", layout="wide")

PORTFOLIO_FILE = Path("portfolio.json")
HISTORY_FILE = Path("history.json")
DEFAULT_EXCHANGE_RATE = 1370.0


def first_value(data: dict, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] not in [None, ""]:
            return data[key]
    return default


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def valid_price(value: Any) -> float | None:
    try:
        price = float(value)
        if price > 0:
            return price
    except Exception:
        pass
    return None


def normalize_holding(raw: dict) -> dict | None:
    ticker = str(first_value(raw, "종목", "Ticker", default="")).strip().upper()
    quantity = to_float(first_value(raw, "수량", "Quantity", default=0))
    buy_price = to_float(first_value(raw, "평균단가", "Buy Price", default=0))
    current_price = to_float(first_value(raw, "현재가", "Current Price", default=0))
    asset_type = first_value(raw, "자산구분", default="주식/ETF")
    currency = first_value(raw, "통화", default="USD")
    krw_amount = to_float(first_value(raw, "원화금액", default=0))

    if not ticker:
        return None

    if ticker == "CASH_USD":
        return {
            "종목": "CASH_USD",
            "자산구분": "현금",
            "통화": "USD",
            "수량": quantity,
            "평균단가": 1.0,
            "현재가": 1.0,
            "원화금액": 0.0,
        }

    if ticker == "CASH_KRW":
        return {
            "종목": "CASH_KRW",
            "자산구분": "현금",
            "통화": "KRW",
            "수량": quantity,
            "평균단가": 1.0,
            "현재가": 1.0,
            "원화금액": krw_amount,
        }

    if quantity <= 0 or buy_price <= 0:
        return None

    return {
        "종목": ticker,
        "자산구분": asset_type,
        "통화": currency,
        "수량": quantity,
        "평균단가": buy_price,
        "현재가": current_price,
        "원화금액": 0.0,
    }


def load_holdings() -> list[dict]:
    if not PORTFOLIO_FILE.exists():
        return []
    try:
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as file:
            raw_holdings = json.load(file)

        holdings = []
        for raw in raw_holdings:
            holding = normalize_holding(raw)
            if holding:
                holdings.append(holding)

        return holdings
    except Exception:
        return []


def save_holdings(holdings: list[dict]) -> None:
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as file:
        json.dump(holdings, file, indent=2, ensure_ascii=False)


def load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            history = json.load(file)
        return history if isinstance(history, list) else []
    except Exception:
        return []


def save_history(history: list[dict]) -> None:
    with open(HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(history, file, indent=2, ensure_ascii=False)


def save_today_value(total_value_usd: float, total_value_krw: float, exchange_rate: float) -> None:
    today = date.today().isoformat()
    history = load_history()

    new_record = {
        "날짜": today,
        "총 평가금액($)": float(total_value_usd),
        "총 평가금액(원)": float(total_value_krw),
        "적용 환율": float(exchange_rate),
    }

    updated = False
    for index, record in enumerate(history):
        if record.get("날짜") == today:
            history[index] = new_record
            updated = True
            break

    if not updated:
        history.append(new_record)

    history = sorted(history, key=lambda row: row["날짜"])
    save_history(history)


def get_from_fast_info(ticker: str) -> float | None:
    try:
        stock = yf.Ticker(ticker)
        fast_info = stock.fast_info

        for key in ["last_price", "regular_market_price", "previous_close"]:
            try:
                price = valid_price(fast_info.get(key))
                if price:
                    return price
            except Exception:
                pass

            try:
                price = valid_price(getattr(fast_info, key))
                if price:
                    return price
            except Exception:
                pass
    except Exception:
        pass

    return None


def get_from_history(ticker: str) -> float | None:
    try:
        stock = yf.Ticker(ticker)
        history = stock.history(period="5d", interval="1d", auto_adjust=False)
        if history is not None and not history.empty:
            close_prices = history["Close"].dropna()
            if not close_prices.empty:
                return valid_price(close_prices.iloc[-1])
    except Exception:
        pass
    return None


def get_from_yahoo_chart(ticker: str) -> float | None:
    try:
        safe_ticker = quote(ticker, safe="")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{safe_ticker}"
        response = requests.get(
            url,
            params={"range": "5d", "interval": "1d"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        response.raise_for_status()

        data = response.json()
        result = data["chart"]["result"][0]
        meta = result.get("meta", {})

        for key in ["regularMarketPrice", "previousClose", "chartPreviousClose"]:
            price = valid_price(meta.get(key))
            if price:
                return price

        closes = result["indicators"]["quote"][0].get("close", [])
        for close in reversed(closes):
            price = valid_price(close)
            if price:
                return price
    except Exception:
        pass
    return None


@st.cache_data(ttl=300, show_spinner=False)
def get_current_price(ticker: str) -> float | None:
    ticker = ticker.strip().upper()

    if not ticker:
        return None

    if ticker in ["CASH_USD", "CASH_KRW"]:
        return 1.0

    for getter in [get_from_fast_info, get_from_history, get_from_yahoo_chart]:
        price = getter(ticker)
        if price:
            return price

    return None


@st.cache_data(ttl=300, show_spinner=False)
def get_auto_usd_krw_rate() -> float:
    for ticker in ["USDKRW=X", "KRW=X"]:
        rate = get_current_price(ticker)
        if rate and 800 <= rate <= 2500:
            return rate
    return DEFAULT_EXCHANGE_RATE


def refresh_prices(holdings: list[dict]) -> tuple[list[dict], list[str]]:
    updated_holdings = []
    failed_tickers = []

    for holding in holdings:
        new_holding = holding.copy()
        ticker = new_holding["종목"]

        if ticker in ["CASH_USD", "CASH_KRW"]:
            new_holding["현재가"] = 1.0
            updated_holdings.append(new_holding)
            continue

        price = get_current_price(ticker)

        if price:
            new_holding["현재가"] = price
        else:
            failed_tickers.append(ticker)

        updated_holdings.append(new_holding)

    return updated_holdings, failed_tickers


def calculate_portfolio(holdings: list[dict], exchange_rate: float) -> pd.DataFrame:
    if not holdings:
        return pd.DataFrame()

    rows = []

    for holding in holdings:
        ticker = holding["종목"]
        quantity = to_float(holding.get("수량", 0))
        buy_price = to_float(holding.get("평균단가", 0))
        current_price = to_float(holding.get("현재가", 0))
        asset_type = holding.get("자산구분", "주식/ETF")
        currency = holding.get("통화", "USD")
        krw_amount = to_float(holding.get("원화금액", 0))

        if ticker == "CASH_USD":
            cost_usd = quantity
            value_usd = quantity
            profit_usd = 0.0
            return_pct = 0.0
            value_krw = value_usd * exchange_rate
            profit_krw = 0.0

        elif ticker == "CASH_KRW":
            value_krw = krw_amount
            value_usd = krw_amount / exchange_rate if exchange_rate > 0 else 0
            cost_usd = value_usd
            profit_usd = 0.0
            return_pct = 0.0
            profit_krw = 0.0
            quantity = value_usd
            buy_price = 1.0
            current_price = 1.0

        else:
            cost_usd = quantity * buy_price
            value_usd = quantity * current_price
            profit_usd = value_usd - cost_usd
            return_pct = profit_usd / cost_usd * 100 if cost_usd > 0 else 0
            value_krw = value_usd * exchange_rate
            profit_krw = profit_usd * exchange_rate

        rows.append(
            {
                "종목": ticker,
                "자산구분": asset_type,
                "통화": currency,
                "수량": quantity,
                "평균단가": buy_price,
                "현재가": current_price,
                "매수금액($)": cost_usd,
                "평가금액($)": value_usd,
                "손익($)": profit_usd,
                "수익률 %": return_pct,
                "평가금액(원)": value_krw,
                "손익(원)": profit_krw,
            }
        )

    portfolio = pd.DataFrame(rows)
    total_value = portfolio["평가금액($)"].sum()
    portfolio["비중 %"] = portfolio["평가금액($)"] / total_value * 100 if total_value > 0 else 0

    return portfolio


if "holdings" not in st.session_state:
    st.session_state.holdings = load_holdings()


st.title("📊 태현의 투자 대시보드")
st.write("주식, ETF, 달러 현금, 원화 현금, 포트 가치 추이를 한 번에 관리합니다.")

col_refresh, col_note = st.columns([1, 4])
with col_refresh:
    refresh_clicked = st.button("현재가/환율 새로고침")

if refresh_clicked:
    st.cache_data.clear()
    st.session_state.holdings, failed = refresh_prices(st.session_state.holdings)
    save_holdings(st.session_state.holdings)

    if failed:
        st.warning(f"현재가를 못 불러온 종목: {', '.join(failed)}")
    else:
        st.success("현재가와 환율을 새로 불러왔습니다.")

auto_exchange_rate = get_auto_usd_krw_rate()

exchange_rate = st.number_input(
    "적용 환율",
    min_value=0.0,
    value=float(round(auto_exchange_rate, 2)),
    step=1.0,
)

st.caption("환율이 이상하면 위 숫자를 직접 수정하세요. 예: 1380")

with st.form("add_holding", clear_on_submit=True):
    st.subheader("투자 추가")

    add_type = st.selectbox(
        "추가할 자산 종류",
        ["주식/ETF", "달러 현금", "원화 현금"],
    )

    if add_type == "주식/ETF":
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            ticker = st.text_input("종목 티커", placeholder="NVDA").strip().upper()

        with col2:
            quantity = st.number_input("수량", min_value=0.0, step=1.0)

        with col3:
            buy_price = st.number_input("평균단가 ($)", min_value=0.0, step=0.01)

        with col4:
            manual_current_price = st.number_input(
                "현재가 수동 입력",
                min_value=0.0,
                step=0.01,
                help="자동 조회가 실패할 때만 사용하세요.",
            )

    elif add_type == "달러 현금":
        ticker = "CASH_USD"
        quantity = st.number_input("달러 현금 금액 ($)", min_value=0.0, step=100.0)
        buy_price = 1.0
        manual_current_price = 1.0

    else:
        ticker = "CASH_KRW"
        krw_cash = st.number_input("원화 현금 금액 (₩)", min_value=0.0, step=10000.0)
        quantity = krw_cash / exchange_rate if exchange_rate > 0 else 0.0
        buy_price = 1.0
        manual_current_price = 1.0

    add_clicked = st.form_submit_button("포트폴리오 추가", type="primary")

    if add_clicked:
        if add_type == "주식/ETF":
            if not ticker:
                st.error("종목 티커를 입력하세요.")
            elif quantity <= 0 or buy_price <= 0:
                st.error("수량과 평균단가는 0보다 커야 합니다.")
            else:
                current_price = get_current_price(ticker)

                if current_price is None and manual_current_price > 0:
                    current_price = manual_current_price

                if current_price is None:
                    st.error(
                        f"{ticker}의 현재가를 불러오지 못했습니다. "
                        "티커를 확인하거나 현재가를 수동 입력하세요."
                    )
                else:
                    st.session_state.holdings.append(
                        {
                            "종목": ticker,
                            "자산구분": "주식/ETF",
                            "통화": "USD",
                            "수량": quantity,
                            "평균단가": buy_price,
                            "현재가": current_price,
                            "원화금액": 0.0,
                        }
                    )
                    save_holdings(st.session_state.holdings)
                    st.success(
                        f"{ticker}를 포트폴리오에 추가했습니다. "
                        f"적용 현재가: ${current_price:,.2f}"
                    )

        elif add_type == "달러 현금":
            if quantity <= 0:
                st.error("달러 현금 금액은 0보다 커야 합니다.")
            else:
                st.session_state.holdings.append(
                    {
                        "종목": "CASH_USD",
                        "자산구분": "현금",
                        "통화": "USD",
                        "수량": quantity,
                        "평균단가": 1.0,
                        "현재가": 1.0,
                        "원화금액": 0.0,
                    }
                )
                save_holdings(st.session_state.holdings)
                st.success(f"달러 현금 ${quantity:,.2f}를 추가했습니다.")

        else:
            if krw_cash <= 0:
                st.error("원화 현금 금액은 0보다 커야 합니다.")
            else:
                st.session_state.holdings.append(
                    {
                        "종목": "CASH_KRW",
                        "자산구분": "현금",
                        "통화": "KRW",
                        "수량": quantity,
                        "평균단가": 1.0,
                        "현재가": 1.0,
                        "원화금액": krw_cash,
                    }
                )
                save_holdings(st.session_state.holdings)
                st.success(f"원화 현금 ₩{krw_cash:,.0f}를 추가했습니다.")


portfolio = calculate_portfolio(st.session_state.holdings, exchange_rate)

if portfolio.empty:
    st.info("포트폴리오가 비어 있습니다. 시작하려면 종목을 추가하세요.")
else:
    total_cost = portfolio["매수금액($)"].sum()
    total_value = portfolio["평가금액($)"].sum()
    total_profit = portfolio["손익($)"].sum()
    total_return = total_profit / total_cost * 100 if total_cost > 0 else 0

    total_value_krw = portfolio["평가금액(원)"].sum()
    total_profit_krw = portfolio["손익(원)"].sum()

    st.subheader("포트폴리오 요약")

    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("총 평가금액($)", f"${total_value:,.2f}")
    metric2.metric("총 평가금액(원)", f"₩{total_value_krw:,.0f}")
    metric3.metric("총 손익", f"${total_profit:,.2f}", f"₩{total_profit_krw:,.0f}")
    metric4.metric("총 수익률", f"{total_return:,.2f}%")

    if st.button("오늘 가치 저장"):
        save_today_value(total_value, total_value_krw, exchange_rate)
        st.success("오늘 포트폴리오 가치를 저장했습니다.")

    st.subheader("보유 종목")

    st.dataframe(
        portfolio,
        hide_index=True,
        width="stretch",
        column_config={
            "수량": st.column_config.NumberColumn(format="%.4f"),
            "평균단가": st.column_config.NumberColumn(format="$%.2f"),
            "현재가": st.column_config.NumberColumn(format="$%.2f"),
            "매수금액($)": st.column_config.NumberColumn(format="$%.2f"),
            "평가금액($)": st.column_config.NumberColumn(format="$%.2f"),
            "손익($)": st.column_config.NumberColumn(format="$%.2f"),
            "수익률 %": st.column_config.NumberColumn(format="%.2f%%"),
            "평가금액(원)": st.column_config.NumberColumn(format="₩%.0f"),
            "손익(원)": st.column_config.NumberColumn(format="₩%.0f"),
            "비중 %": st.column_config.NumberColumn(format="%.2f%%"),
        },
    )

    st.subheader("포트폴리오 비중")

    pie_data = portfolio[portfolio["평가금액($)"] > 0].copy()

    fig = px.pie(
        pie_data,
        names="종목",
        values="평가금액($)",
        hole=0.35,
    )

    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("포트폴리오 가치 추이")

    history = load_history()

    if not history:
        st.info("아직 저장된 가치 기록이 없습니다. 위의 '오늘 가치 저장' 버튼을 눌러 시작하세요.")
    else:
        history_df = pd.DataFrame(history)
        history_df["날짜"] = pd.to_datetime(history_df["날짜"])

        fig_history = px.line(
            history_df,
            x="날짜",
            y="총 평가금액(원)",
            markers=True,
        )

        fig_history.update_layout(
            yaxis_title="총 평가금액(원)",
            xaxis_title="날짜",
        )

        st.plotly_chart(fig_history, use_container_width=True)

        st.dataframe(
            history_df.sort_values("날짜", ascending=False),
            hide_index=True,
            width="stretch",
            column_config={
                "총 평가금액($)": st.column_config.NumberColumn(format="$%.2f"),
                "총 평가금액(원)": st.column_config.NumberColumn(format="₩%.0f"),
                "적용 환율": st.column_config.NumberColumn(format="%.2f"),
            },
        )

    action1, action2 = st.columns(2)

    with action1:
        row_to_remove = st.selectbox(
            "삭제할 종목 선택",
            options=range(len(portfolio)),
            format_func=lambda row: f"{row + 1}번: {portfolio.iloc[row]['종목']}",
        )

        if st.button("선택 종목 삭제"):
            st.session_state.holdings.pop(row_to_remove)
            save_holdings(st.session_state.holdings)
            st.rerun()

    with action2:
        st.write("")
        st.write("")

        if st.button("포트폴리오 초기화"):
            st.session_state.holdings = []
            save_holdings(st.session_state.holdings)
            st.rerun()

st.caption("포트폴리오는 portfolio.json 파일에 저장되고, 가치 추이는 history.json 파일에 저장됩니다.")
