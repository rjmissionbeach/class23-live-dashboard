import time
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st
import yfinance as yf
from streamlit_autorefresh import st_autorefresh


# ------------------------------------------------------------
# Page setup
# ------------------------------------------------------------

st.set_page_config(
    page_title="Market Dashboard",
    page_icon="📈",
    layout="wide"
)

st_autorefresh(
    interval=15_000,
    key="market_dashboard_refresh"
)

st.title("📈 Market Dashboard")
st.caption("Live quotes from Finnhub. SPY/QQQ/DIA chart from Yahoo Finance via yfinance.")


# ------------------------------------------------------------
# Finnhub API setup
# ------------------------------------------------------------

FINNHUB_API_KEY = st.secrets.get("FINNHUB_API_KEY")

if not FINNHUB_API_KEY:
    st.error(
        "Missing FINNHUB_API_KEY. Add it in Streamlit Community Cloud secrets "
        "or in .streamlit/secrets.toml for local testing."
    )
    st.stop()

QUOTE_URL = "https://finnhub.io/api/v1/quote"

HEADERS = {
    "X-Finnhub-Token": FINNHUB_API_KEY
}


# ------------------------------------------------------------
# Ticker groups
# ------------------------------------------------------------

market_overview = ["SPY", "QQQ", "DIA"]

watchlist = ["MSFT", "CVNA", "INTC", "NVDA", "SOFI"]

crypto_pairs = [
    "BINANCE:BTCUSDT",
    "BINANCE:ETHUSDT",
    "BINANCE:DOTUSDT"
]

groups = {
    "Market Overview": market_overview,
    "Watchlist": watchlist,
    "Crypto Pairs": crypto_pairs
}

REQUEST_SLEEP_SECONDS = 0.35


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------

def get_finnhub_quote(symbol: str) -> dict:
    response = requests.get(
        QUOTE_URL,
        params={"symbol": symbol},
        headers=HEADERS,
        timeout=30
    )
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=900)
def get_yfinance_chart_data(symbols, period="1mo") -> pd.DataFrame:
    """
    Gets recent historical close prices from Yahoo Finance.
    Cached for 15 minutes so this does not reload every 15-second refresh.
    """
    data = yf.download(
        tickers=symbols,
        period=period,
        interval="1d",
        auto_adjust=True,
        progress=False,
        group_by="column"
    )

    if data.empty:
        return pd.DataFrame()

    # For multiple tickers, yfinance usually returns multi-level columns.
    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"].copy()
    else:
        close = data[["Close"]].copy()
        close.columns = symbols

    close = close.dropna(how="all")

    # Normalize to 100 so SPY, QQQ, and DIA are comparable on one chart.
    normalized = close / close.iloc[0] * 100

    return normalized


def format_price(value):
    if value is None:
        return "N/A"

    try:
        value = float(value)

        if value >= 100:
            return f"${value:,.2f}"
        elif value >= 1:
            return f"${value:,.4f}"
        else:
            return f"${value:,.6f}"

    except Exception:
        return str(value)


def format_change(value):
    if value is None:
        return "N/A"

    try:
        return f"{float(value):+,.4f}"
    except Exception:
        return str(value)


def format_percent(value):
    if value is None:
        return "N/A"

    try:
        return f"{float(value):+,.2f}%"
    except Exception:
        return str(value)


def format_as_of_timestamp(raw_timestamp):
    if raw_timestamp is None or raw_timestamp == 0:
        return "No timestamp returned"

    try:
        raw_timestamp = int(raw_timestamp)

        if raw_timestamp > 10_000_000_000:
            dt = datetime.fromtimestamp(raw_timestamp / 1000, tz=timezone.utc)
        else:
            dt = datetime.fromtimestamp(raw_timestamp, tz=timezone.utc)

        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    except Exception:
        return f"Unrecognized timestamp: {raw_timestamp}"


def render_quote_card(symbol: str, quote: dict):
    current_price = quote.get("c")
    change = quote.get("d")
    percent_change = quote.get("dp")
    timestamp = quote.get("t")

    price_text = format_price(current_price)

    if change is None or percent_change is None:
        delta_text = None
    else:
        delta_text = f"{format_change(change)} | {format_percent(percent_change)}"

    st.metric(
        label=symbol,
        value=price_text,
        delta=delta_text
    )

    st.caption(f"As of: {format_as_of_timestamp(timestamp)}")

    with st.expander(f"Raw Finnhub response for {symbol}"):
        st.json(quote)


def render_quote_section(section_name: str, symbols: list[str]):
    st.subheader(section_name)

    for start in range(0, len(symbols), 3):
        row_symbols = symbols[start:start + 3]
        cols = st.columns(3)

        for col, symbol in zip(cols, row_symbols):
            with col:
                with st.container(border=True):
                    try:
                        quote = get_finnhub_quote(symbol)
                        render_quote_card(symbol, quote)

                    except requests.exceptions.HTTPError as e:
                        st.error(f"{symbol}: HTTP error from Finnhub: {e}")

                    except requests.exceptions.RequestException as e:
                        st.error(f"{symbol}: Request error: {e}")

                    except Exception as e:
                        st.error(f"{symbol}: Unexpected error: {e}")

                time.sleep(REQUEST_SLEEP_SECONDS)


def render_market_chart():
    st.subheader("SPY, QQQ, DIA — 1-month indexed performance")

    try:
        chart_df = get_yfinance_chart_data(market_overview, period="1mo")

        if chart_df.empty:
            st.warning("No chart data returned from yfinance.")
            return

        st.line_chart(chart_df, height=320)

        st.caption(
            "Chart is indexed to 100 at the first observation so SPY, QQQ, and DIA "
            "can be compared on the same scale. Cached for 15 minutes."
        )

    except Exception as e:
        st.warning(f"Could not load chart data from yfinance: {e}")


# ------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------

total_symbols = sum(len(symbols) for symbols in groups.values())

st.info(
    f"This app requests {total_symbols} Finnhub quotes every 15 seconds, "
    f"or about {total_symbols * 4} quote calls per minute for one active session. "
    "The historical chart is cached separately."
)

st.divider()

# Section 1: Market Overview
render_market_chart()
render_quote_section("Market Overview", market_overview)

st.divider()

# Section 2: Watchlist
render_quote_section("Watchlist", watchlist)

st.divider()

# Section 3: Crypto Pairs
render_quote_section("Crypto Pairs", crypto_pairs)

st.divider()

st.caption(
    "Finnhub quote fields used: c = current price, d = change, "
    "dp = percent change, t = timestamp. "
    "Historical chart uses yfinance because Finnhub stock candles are not available "
    "on the free key used here."
)
