import time
from datetime import datetime, timezone

import altair as alt
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
st.caption(
    "Market index data from Yahoo Finance via yfinance. "
    "Watchlist and crypto quotes from Finnhub."
)


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

# yfinance index tickers
market_overview = ["^GSPC", "^NDX", "^DJI"]

index_display_names = {
    "^GSPC": "S&P 500",
    "^NDX": "Nasdaq 100",
    "^DJI": "Dow Jones"
}

watchlist = ["MSFT", "CVNA", "INTC", "NVDA", "SOFI"]

crypto_pairs = [
    "BINANCE:BTCUSDT",
    "BINANCE:ETHUSDT",
    "BINANCE:DOTUSDT"
]

REQUEST_SLEEP_SECONDS = 0.35


# ------------------------------------------------------------
# Section styling
# ------------------------------------------------------------

def section_banner(title, subtitle, color_name):
    color_map = {
        "blue": "🔵",
        "violet": "🟣",
        "orange": "🟠",
        "green": "🟢"
    }

    icon = color_map.get(color_name, "🔵")

    st.markdown(f"## {icon} :{color_name}[{title}]")
    st.caption(subtitle)


# ------------------------------------------------------------
# Finnhub quote helpers
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


def render_finnhub_quote_card(symbol: str, quote: dict):
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


def render_finnhub_quote_grid(symbols: list[str]):
    for start in range(0, len(symbols), 3):
        row_symbols = symbols[start:start + 3]
        cols = st.columns(3)

        for col, symbol in zip(cols, row_symbols):
            with col:
                with st.container(border=True):
                    try:
                        quote = get_finnhub_quote(symbol)
                        render_finnhub_quote_card(symbol, quote)

                    except requests.exceptions.HTTPError as e:
                        st.error(f"{symbol}: HTTP error from Finnhub: {e}")

                    except requests.exceptions.RequestException as e:
                        st.error(f"{symbol}: Request error: {e}")

                    except Exception as e:
                        st.error(f"{symbol}: Unexpected error: {e}")

                time.sleep(REQUEST_SLEEP_SECONDS)


# ------------------------------------------------------------
# yfinance market index helpers
# ------------------------------------------------------------

@st.cache_data(ttl=900)
def get_yfinance_chart_data(symbols, period="1mo") -> pd.DataFrame:
    """
    Gets daily historical close prices from Yahoo Finance.
    Returns percent change from the first observation.
    Cached for 15 minutes.
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

    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"].copy()
    else:
        close = data[["Close"]].copy()
        close.columns = symbols

    close = close.dropna(how="all")

    pct_change = (close / close.iloc[0] - 1.0) * 100

    return pct_change


@st.cache_data(ttl=15)
def get_yfinance_latest_quotes(symbols) -> dict:
    """
    Gets recent intraday data from Yahoo Finance and computes:
    - latest price
    - change from previous close
    - percent change from previous close
    - latest timestamp

    Cached for 15 seconds, matching the app refresh rate.
    """
    data = yf.download(
        tickers=symbols,
        period="5d",
        interval="1m",
        auto_adjust=True,
        progress=False,
        group_by="column"
    )

    if data.empty:
        return {}

    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"].copy()
    else:
        close = data[["Close"]].copy()
        close.columns = symbols

    close = close.dropna(how="all")

    results = {}

    for symbol in symbols:
        if symbol not in close.columns:
            continue

        series = close[symbol].dropna()

        if series.empty:
            continue

        latest_price = float(series.iloc[-1])
        latest_time = series.index[-1]

        # Find the previous trading day's last available price.
        unique_dates = pd.Series(series.index.date).drop_duplicates().tolist()

        if len(unique_dates) >= 2:
            previous_date = unique_dates[-2]
            previous_day_series = series[pd.Series(series.index.date, index=series.index) == previous_date]
            previous_close = float(previous_day_series.iloc[-1])
        else:
            previous_close = float(series.iloc[0])

        change = latest_price - previous_close

        if previous_close != 0:
            percent_change = change / previous_close * 100
        else:
            percent_change = None

        results[symbol] = {
            "price": latest_price,
            "change": change,
            "percent_change": percent_change,
            "timestamp": latest_time
        }

    return results


def format_yfinance_timestamp(ts):
    if ts is None:
        return "No timestamp returned"

    try:
        if getattr(ts, "tzinfo", None) is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")

        return ts.strftime("%Y-%m-%d %H:%M:%S UTC")

    except Exception:
        return str(ts)


def render_market_chart():
    st.markdown("#### S&P 500, Nasdaq 100, Dow Jones — 1-month performance")

    try:
        chart_df = get_yfinance_chart_data(market_overview, period="1mo")

        if chart_df.empty:
            st.warning("No chart data returned from yfinance.")
            return

        chart_long = (
            chart_df
            .reset_index()
            .melt(
                id_vars=chart_df.index.name or "Date",
                var_name="Ticker",
                value_name="Percent Change"
            )
        )

        date_col = chart_df.index.name or "Date"

        chart_long["Ticker"] = chart_long["Ticker"].map(
            lambda x: index_display_names.get(x, x)
        )

        chart = (
            alt.Chart(chart_long)
            .mark_line(point=True)
            .encode(
                x=alt.X(f"{date_col}:T", title="Date"),
                y=alt.Y(
                    "Percent Change:Q",
                    title="Percent change since first day",
                    scale=alt.Scale(zero=False)
                ),
                color=alt.Color("Ticker:N", title="Index"),
                tooltip=[
                    alt.Tooltip(f"{date_col}:T", title="Date"),
                    alt.Tooltip("Ticker:N", title="Index"),
                    alt.Tooltip("Percent Change:Q", title="% change", format=".2f")
                ]
            )
            .properties(height=340)
            .interactive()
        )

        st.altair_chart(chart, use_container_width=True)

        st.caption(
            "Chart shows percent change from the first observation. "
            "The y-axis is allowed to zoom in so the movement is visible. "
            "Chart data is cached for 15 minutes."
        )

    except Exception as e:
        st.warning(f"Could not load chart data from yfinance: {e}")


def render_yfinance_quote_card(symbol: str, quote: dict):
    display_name = index_display_names.get(symbol, symbol)

    price = quote.get("price")
    change = quote.get("change")
    percent_change = quote.get("percent_change")
    timestamp = quote.get("timestamp")

    price_text = format_price(price)

    if change is None or percent_change is None:
        delta_text = None
    else:
        delta_text = f"{format_change(change)} | {format_percent(percent_change)}"

    st.metric(
        label=display_name,
        value=price_text,
        delta=delta_text
    )

    st.caption(f"As of: {format_yfinance_timestamp(timestamp)}")

    with st.expander(f"Raw yfinance-derived quote for {display_name}"):
        st.json(
            {
                "symbol": symbol,
                "display_name": display_name,
                "price": price,
                "change": change,
                "percent_change": percent_change,
                "timestamp": str(timestamp)
            }
        )


def render_market_quote_grid(symbols: list[str]):
    quotes = get_yfinance_latest_quotes(symbols)

    for start in range(0, len(symbols), 3):
        row_symbols = symbols[start:start + 3]
        cols = st.columns(3)

        for col, symbol in zip(cols, row_symbols):
            with col:
                with st.container(border=True):
                    if symbol in quotes:
                        render_yfinance_quote_card(symbol, quotes[symbol])
                    else:
                        st.error(f"No yfinance quote data returned for {symbol}")


# ------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------

finnhub_symbol_count = len(watchlist) + len(crypto_pairs)

st.info(
    f"This app requests {finnhub_symbol_count} Finnhub quotes every 15 seconds, "
    f"or about {finnhub_symbol_count * 4} Finnhub quote calls per minute for one active session. "
    "The market index section uses yfinance instead of Finnhub."
)

st.divider()


# ------------------------------------------------------------
# Section 1: Market Overview
# ------------------------------------------------------------

section_banner(
    title="Market Overview",
    subtitle="Actual index tickers from yfinance: S&P 500, Nasdaq 100, and Dow Jones.",
    color_name="blue"
)

with st.container(border=True):
    render_market_chart()
    st.divider()
    render_market_quote_grid(market_overview)


st.divider()


# ------------------------------------------------------------
# Section 2: Watchlist
# ------------------------------------------------------------

section_banner(
    title="Watchlist",
    subtitle="Selected individual stocks using Finnhub's quote endpoint.",
    color_name="violet"
)

with st.container(border=True):
    render_finnhub_quote_grid(watchlist)


st.divider()


# ------------------------------------------------------------
# Section 3: Crypto Pairs
# ------------------------------------------------------------

section_banner(
    title="Crypto Pairs",
    subtitle="Crypto quotes using Finnhub's exchange-prefixed crypto symbols.",
    color_name="orange"
)

with st.container(border=True):
    render_finnhub_quote_grid(crypto_pairs)


st.divider()

st.caption(
    "Market index data comes from yfinance. "
    "Watchlist and crypto data use Finnhub quote fields: "
    "c = current price, d = change, dp = percent change, t = timestamp."
)
