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


# ------------------------------------------------------------
# CSS: section backgrounds and metric cards
# ------------------------------------------------------------

st.markdown(
    """
    <style>
        .st-key-market_overview_section {
            background: linear-gradient(135deg, #dbeafe 0%, #eff6ff 100%);
            border: 1px solid rgba(37, 99, 235, 0.30);
            border-radius: 22px;
            padding: 1.25rem;
            margin-bottom: 1.25rem;
            box-shadow: 0 8px 24px rgba(30, 64, 175, 0.08);
        }

        .st-key-watchlist_section {
            background: linear-gradient(135deg, #f3e8ff 0%, #faf5ff 100%);
            border: 1px solid rgba(124, 58, 237, 0.30);
            border-radius: 22px;
            padding: 1.25rem;
            margin-bottom: 1.25rem;
            box-shadow: 0 8px 24px rgba(91, 33, 182, 0.08);
        }

        .st-key-crypto_section {
            background: linear-gradient(135deg, #fef3c7 0%, #fffbeb 100%);
            border: 1px solid rgba(245, 158, 11, 0.35);
            border-radius: 22px;
            padding: 1.25rem;
            margin-bottom: 1.25rem;
            box-shadow: 0 8px 24px rgba(146, 64, 14, 0.08);
        }

        .st-key-commodities_section {
            background: linear-gradient(135deg, #dcfce7 0%, #f0fdf4 100%);
            border: 1px solid rgba(22, 163, 74, 0.30);
            border-radius: 22px;
            padding: 1.25rem;
            margin-bottom: 1.25rem;
            box-shadow: 0 8px 24px rgba(21, 128, 61, 0.08);
        }

        .stMetric {
            background-color: rgba(255, 255, 255, 0.78);
            border: 1px solid rgba(255, 255, 255, 0.85);
            border-radius: 16px;
            padding: 0.85rem 0.95rem;
            box-shadow: 0 3px 10px rgba(0, 0, 0, 0.05);
        }
    </style>
    """,
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# Sidebar navigation
# ------------------------------------------------------------

st.sidebar.title("📊 Dashboard Sections")

selected_page = st.sidebar.radio(
    "Choose a section",
    [
        "Market Overview",
        "Watchlist",
        "Crypto",
        "Commodities"
    ]
)

st.sidebar.divider()
st.sidebar.caption("Auto-refreshes every 15 seconds.")


# ------------------------------------------------------------
# App title
# ------------------------------------------------------------

st.title("📈 Market Dashboard")

st.caption(
    "Use the left sidebar to switch between sections. "
    "Market indexes and commodities use yfinance. "
    "Watchlist and crypto quotes use Finnhub."
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
# Tickers
# ------------------------------------------------------------

market_overview = ["^GSPC", "^IXIC", "^DJI"]

index_display_names = {
    "^GSPC": "S&P 500",
    "^IXIC": "Nasdaq Composite",
    "^DJI": "Dow Jones"
}

watchlist = ["MSFT", "CVNA", "INTC", "NVDA", "SOFI"]

crypto_pairs = [
    "BINANCE:BTCUSDT",
    "BINANCE:ETHUSDT",
    "BINANCE:DOTUSDT"
]

commodities = ["CL=F", "GC=F", "KC=F"]

commodity_display_names = {
    "CL=F": "WTI Crude Oil",
    "GC=F": "Gold",
    "KC=F": "Coffee"
}

commodity_units = {
    "CL=F": "$/barrel",
    "GC=F": "$/oz",
    "KC=F": "¢/lb"
}

REQUEST_SLEEP_SECONDS = 0.35


# ------------------------------------------------------------
# Formatting helpers
# ------------------------------------------------------------

def format_price(value, prefix="", suffix=""):
    if value is None:
        return "N/A"

    try:
        value = float(value)

        if abs(value) >= 100:
            formatted = f"{value:,.2f}"
        elif abs(value) >= 1:
            formatted = f"{value:,.4f}"
        else:
            formatted = f"{value:,.6f}"

        return f"{prefix}{formatted}{suffix}"

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


def format_finnhub_timestamp(raw_timestamp):
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


def format_yfinance_timestamp(ts):
    if ts is None:
        return "No timestamp returned"

    try:
        ts = pd.Timestamp(ts)

        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")

        return ts.strftime("%Y-%m-%d %H:%M:%S UTC")

    except Exception:
        return str(ts)


# ------------------------------------------------------------
# Finnhub helpers
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


def render_finnhub_quote_card(symbol: str, quote: dict):
    current_price = quote.get("c")
    change = quote.get("d")
    percent_change = quote.get("dp")
    timestamp = quote.get("t")

    if change is None or percent_change is None:
        delta_text = None
    else:
        delta_text = f"{format_change(change)} | {format_percent(percent_change)}"

    st.metric(
        label=symbol,
        value=format_price(current_price, prefix="$"),
        delta=delta_text
    )

    st.caption(f"As of: {format_finnhub_timestamp(timestamp)}")

    with st.expander(f"Raw Finnhub response for {symbol}"):
        st.json(quote)


def render_finnhub_quote_grid(symbols: list[str]):
    for start in range(0, len(symbols), 3):
        row_symbols = symbols[start:start + 3]
        cols = st.columns(3)

        for col, symbol in zip(cols, row_symbols):
            with col:
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
# yfinance helpers
# ------------------------------------------------------------

def extract_close_series(data: pd.DataFrame, symbol: str) -> pd.Series:
    """
    Robustly extracts a Close series from yfinance output.
    Handles both single-level and multi-level columns.
    """
    if data.empty:
        return pd.Series(dtype=float, name=symbol)

    close = None

    if isinstance(data.columns, pd.MultiIndex):
        if "Close" in data.columns.get_level_values(0):
            close_data = data["Close"]

            if isinstance(close_data, pd.DataFrame):
                if symbol in close_data.columns:
                    close = close_data[symbol]
                else:
                    close = close_data.iloc[:, 0]
            else:
                close = close_data

        elif "Close" in data.columns.get_level_values(1):
            close_data = data.xs("Close", axis=1, level=1)

            if isinstance(close_data, pd.DataFrame):
                if symbol in close_data.columns:
                    close = close_data[symbol]
                else:
                    close = close_data.iloc[:, 0]
            else:
                close = close_data

    else:
        if "Close" in data.columns:
            close = data["Close"]

    if close is None:
        return pd.Series(dtype=float, name=symbol)

    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    close = pd.to_numeric(close.squeeze(), errors="coerce").dropna()
    close.name = symbol

    return close


@st.cache_data(ttl=900)
def get_yfinance_chart_data(symbols_tuple, period="1mo") -> pd.DataFrame:
    """
    Gets daily historical close prices from Yahoo Finance.
    Returns percent change from each ticker's first valid observation.
    Cached for 15 minutes.
    """
    close_series = []

    for symbol in symbols_tuple:
        data = yf.download(
            tickers=symbol,
            period=period,
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False
        )

        close = extract_close_series(data, symbol)

        if not close.empty:
            close_series.append(close)

    if not close_series:
        return pd.DataFrame()

    close_df = pd.concat(close_series, axis=1).dropna(how="all")

    pct_change = pd.DataFrame(index=close_df.index)

    for symbol in close_df.columns:
        series = close_df[symbol].dropna()

        if series.empty:
            continue

        first_value = series.iloc[0]
        pct_change.loc[series.index, symbol] = (series / first_value - 1.0) * 100

    pct_change.index.name = "Date"

    return pct_change


@st.cache_data(ttl=15)
def get_yfinance_latest_quotes(symbols_tuple) -> dict:
    """
    Gets recent intraday data from Yahoo Finance and computes:
    - latest price
    - change from previous close
    - percent change from previous close
    - latest timestamp

    Tries 1-minute, then 5-minute, then 1-day data.
    """
    results = {}

    for symbol in symbols_tuple:
        close = pd.Series(dtype=float, name=symbol)

        for interval, period in [
            ("1m", "5d"),
            ("5m", "5d"),
            ("1d", "1mo")
        ]:
            data = yf.download(
                tickers=symbol,
                period=period,
                interval=interval,
                auto_adjust=True,
                progress=False,
                threads=False
            )

            close = extract_close_series(data, symbol)

            if not close.empty:
                break

        if close.empty:
            continue

        latest_price = float(close.iloc[-1])
        latest_time = close.index[-1]

        date_index = pd.Series(close.index.date, index=close.index)
        unique_dates = date_index.drop_duplicates().tolist()

        if len(unique_dates) >= 2:
            previous_date = unique_dates[-2]
            previous_day_series = close[date_index == previous_date]
            previous_close = float(previous_day_series.iloc[-1])
        else:
            previous_close = float(close.iloc[0])

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


# ------------------------------------------------------------
# Chart rendering
# ------------------------------------------------------------

def render_percent_change_chart(
    symbols,
    display_names,
    title,
    y_title="Percent change since first day",
    period="1mo"
):
    chart_df = get_yfinance_chart_data(tuple(symbols), period=period)

    if chart_df.empty:
        st.warning("No chart data returned from yfinance.")
        return

    chart_df = chart_df.rename(columns=display_names)

    chart_long = (
        chart_df
        .reset_index()
        .melt(
            id_vars="Date",
            var_name="Series",
            value_name="Percent Change"
        )
        .dropna()
    )

    if chart_long.empty:
        st.warning("Chart data was returned, but no usable values were available.")
        return

    chart = (
        alt.Chart(chart_long)
        .mark_line(point=True)
        .encode(
            x=alt.X("Date:T", title="Date"),
            y=alt.Y(
                "Percent Change:Q",
                title=y_title,
                scale=alt.Scale(zero=False)
            ),
            color=alt.Color("Series:N", title="Series"),
            tooltip=[
                alt.Tooltip("Date:T", title="Date"),
                alt.Tooltip("Series:N", title="Series"),
                alt.Tooltip("Percent Change:Q", title="% change", format=".2f")
            ]
        )
        .properties(height=340)
        .interactive()
    )

    st.markdown(f"#### {title}")
    st.altair_chart(chart, use_container_width=True)

    included = sorted(chart_long["Series"].unique().tolist())

    st.caption(
        "Chart shows percent change from each series' first valid observation. "
        "The y-axis is allowed to zoom in so movement is visible. "
        f"Included series: {', '.join(included)}. "
        "Chart data is cached for 15 minutes."
    )


# ------------------------------------------------------------
# yfinance quote cards
# ------------------------------------------------------------

def render_yfinance_quote_card(
    symbol: str,
    quote: dict,
    display_names: dict,
    price_prefix="",
    price_suffix=""
):
    display_name = display_names.get(symbol, symbol)

    price = quote.get("price")
    change = quote.get("change")
    percent_change = quote.get("percent_change")
    timestamp = quote.get("timestamp")

    if change is None or percent_change is None:
        delta_text = None
    else:
        delta_text = f"{format_change(change)} | {format_percent(percent_change)}"

    st.metric(
        label=display_name,
        value=format_price(price, prefix=price_prefix, suffix=price_suffix),
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


def render_yfinance_quote_grid(
    symbols,
    display_names,
    price_prefix="",
    units_by_symbol=None
):
    units_by_symbol = units_by_symbol or {}
    quotes = get_yfinance_latest_quotes(tuple(symbols))

    for start in range(0, len(symbols), 3):
        row_symbols = symbols[start:start + 3]
        cols = st.columns(3)

        for col, symbol in zip(cols, row_symbols):
            with col:
                if symbol in quotes:
                    suffix = ""
                    if symbol in units_by_symbol:
                        suffix = f" {units_by_symbol[symbol]}"

                    render_yfinance_quote_card(
                        symbol=symbol,
                        quote=quotes[symbol],
                        display_names=display_names,
                        price_prefix=price_prefix,
                        price_suffix=suffix
                    )
                else:
                    display_name = display_names.get(symbol, symbol)
                    st.error(f"No yfinance quote data returned for {display_name}")


# ------------------------------------------------------------
# Section heading
# ------------------------------------------------------------

def section_heading(title, subtitle, icon):
    st.markdown(f"## {icon} {title}")
    st.caption(subtitle)


# ------------------------------------------------------------
# Pages
# ------------------------------------------------------------

def render_market_overview_page():
    with st.container(key="market_overview_section"):
        section_heading(
            title="Market Overview",
            subtitle="Actual market indexes from yfinance: S&P 500, Nasdaq Composite, and Dow Jones.",
            icon="🔵"
        )

        render_percent_change_chart(
            symbols=market_overview,
            display_names=index_display_names,
            title="S&P 500, Nasdaq Composite, Dow Jones — 1-month performance"
        )

        st.divider()

        render_yfinance_quote_grid(
            symbols=market_overview,
            display_names=index_display_names,
            price_prefix=""
        )


def render_watchlist_page():
    with st.container(key="watchlist_section"):
        section_heading(
            title="Watchlist",
            subtitle="Selected individual stocks using Finnhub's quote endpoint.",
            icon="🟣"
        )

        render_finnhub_quote_grid(watchlist)


def render_crypto_page():
    with st.container(key="crypto_section"):
        section_heading(
            title="Crypto",
            subtitle="Crypto quotes using Finnhub's exchange-prefixed crypto symbols.",
            icon="🟠"
        )

        render_finnhub_quote_grid(crypto_pairs)


def render_commodities_page():
    with st.container(key="commodities_section"):
        section_heading(
            title="Commodities",
            subtitle="WTI crude oil, gold, and coffee futures from yfinance.",
            icon="🟢"
        )

        render_percent_change_chart(
            symbols=commodities,
            display_names=commodity_display_names,
            title="WTI crude oil, gold, coffee — 1-month performance"
        )

        st.divider()

        render_yfinance_quote_grid(
            symbols=commodities,
            display_names=commodity_display_names,
            price_prefix="",
            units_by_symbol=commodity_units
        )


# ------------------------------------------------------------
# Dashboard router
# ------------------------------------------------------------

if selected_page == "Market Overview":
    render_market_overview_page()

elif selected_page == "Watchlist":
    st.info(
        f"This page requests {len(watchlist)} Finnhub quotes every 15 seconds, "
        f"or about {len(watchlist) * 4} calls per minute for one active session."
    )
    render_watchlist_page()

elif selected_page == "Crypto":
    st.info(
        f"This page requests {len(crypto_pairs)} Finnhub quotes every 15 seconds, "
        f"or about {len(crypto_pairs) * 4} calls per minute for one active session."
    )
    render_crypto_page()

elif selected_page == "Commodities":
    render_commodities_page()


st.divider()

st.caption(
    "Market index and commodity data come from yfinance. "
    "Watchlist and crypto data use Finnhub quote fields: "
    "c = current price, d = change, dp = percent change, t = timestamp."
)
