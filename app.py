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
# CSS: section backgrounds and quote cards
# ------------------------------------------------------------

st.markdown(
    """
    <style>
        .st-key-market_overview_section {
            background: linear-gradient(135deg, #dbeafe 0%, #eff6ff 100%);
            border: 1px solid rgba(37, 99, 235, 0.30);
            border-radius: 22px;
            padding: 1.25rem 1.25rem 0.85rem 1.25rem;
            margin-bottom: 1.25rem;
            box-shadow: 0 8px 24px rgba(30, 64, 175, 0.08);
        }

        .st-key-watchlist_section {
            background: linear-gradient(135deg, #f3e8ff 0%, #faf5ff 100%);
            border: 1px solid rgba(124, 58, 237, 0.30);
            border-radius: 22px;
            padding: 1.25rem 1.25rem 0.85rem 1.25rem;
            margin-bottom: 1.25rem;
            box-shadow: 0 8px 24px rgba(91, 33, 182, 0.08);
        }

        .st-key-crypto_section {
            background: linear-gradient(135deg, #fef3c7 0%, #fffbeb 100%);
            border: 1px solid rgba(245, 158, 11, 0.35);
            border-radius: 22px;
            padding: 1.25rem 1.25rem 0.85rem 1.25rem;
            margin-bottom: 1.25rem;
            box-shadow: 0 8px 24px rgba(146, 64, 14, 0.08);
        }

        .st-key-market_overview_section [data-testid="stMetric"],
        .st-key-watchlist_section [data-testid="stMetric"],
        .st-key-crypto_section [data-testid="stMetric"] {
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

REQUEST_SLEEP_SECONDS = 0.35


# ------------------------------------------------------------
# Formatting helpers
# ------------------------------------------------------------

def format_price(value, dollar=True):
    if value is None:
        return "N/A"

    try:
        value = float(value)
        prefix = "$" if dollar else ""

        if value >= 100:
            return f"{prefix}{value:,.2f}"
        elif value >= 1:
            return f"{prefix}{value:,.4f}"
        else:
            return f"{prefix}{value:,.6f}"

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
        value=format_price(current_price, dollar=True),
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
        # Common shape: first level is price field, second level is ticker.
        if "Close" in data.columns.get_level_values(0):
            close_data = data["Close"]

            if isinstance(close_data, pd.DataFrame):
                if symbol in close_data.columns:
                    close = close_data[symbol]
                else:
                    close = close_data.iloc[:, 0]
            else:
                close = close_data

        # Alternate shape: first level is ticker, second level is price field.
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
    Downloads each symbol separately so one missing symbol does not break the chart.
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

    Downloads each index separately for reliability.
    """
    results = {}

    for symbol in symbols_tuple:
        close = pd.Series(dtype=float, name=symbol)

        # Try 1-minute first. If that fails, try 5-minute.
        for interval in ["1m", "5m"]:
            data = yf.download(
                tickers=symbol,
                period="5d",
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
# Market overview rendering
# ------------------------------------------------------------

def render_market_chart():
    st.markdown("#### S&P 500, Nasdaq Composite, Dow Jones — 1-month performance")

    chart_df = get_yfinance_chart_data(tuple(market_overview), period="1mo")

    if chart_df.empty:
        st.warning("No chart data returned from yfinance.")
        return

    chart_df = chart_df.rename(columns=index_display_names)

    chart_long = (
        chart_df
        .reset_index()
        .melt(
            id_vars="Date",
            var_name="Index",
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
                title="Percent change since first day",
                scale=alt.Scale(zero=False)
            ),
            color=alt.Color("Index:N", title="Index"),
            tooltip=[
                alt.Tooltip("Date:T", title="Date"),
                alt.Tooltip("Index:N", title="Index"),
                alt.Tooltip("Percent Change:Q", title="% change", format=".2f")
            ]
        )
        .properties(height=340)
        .interactive()
    )

    st.altair_chart(chart, use_container_width=True)

    included = sorted(chart_long["Index"].unique().tolist())

    st.caption(
        "Chart shows percent change from each index's first valid observation. "
        "The y-axis is allowed to zoom in so the movement is visible. "
        f"Included series: {', '.join(included)}. "
        "Chart data is cached for 15 minutes."
    )


def render_yfinance_quote_card(symbol: str, quote: dict):
    display_name = index_display_names.get(symbol, symbol)

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
        value=format_price(price, dollar=False),
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
    quotes = get_yfinance_latest_quotes(tuple(symbols))

    cols = st.columns(3)

    for col, symbol in zip(cols, symbols):
        with col:
            if symbol in quotes:
                render_yfinance_quote_card(symbol, quotes[symbol])
            else:
                display_name = index_display_names.get(symbol, symbol)
                st.error(f"No yfinance quote data returned for {display_name}")


# ------------------------------------------------------------
# Section heading
# ------------------------------------------------------------

def section_heading(title, subtitle, icon):
    st.markdown(f"## {icon} {title}")
    st.caption(subtitle)


# ------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------

finnhub_symbol_count = len(watchlist) + len(crypto_pairs)

st.info(
    f"This app requests {finnhub_symbol_count} Finnhub quotes every 15 seconds, "
    f"or about {finnhub_symbol_count * 4} Finnhub quote calls per minute for one active session. "
    "The market index section uses yfinance instead of Finnhub."
)


with st.container(key="market_overview_section"):
    section_heading(
        title="Market Overview",
        subtitle="Actual market indexes from yfinance: S&P 500, Nasdaq Composite, and Dow Jones.",
        icon="🔵"
    )

    render_market_chart()
    st.divider()
    render_market_quote_grid(market_overview)


with st.container(key="watchlist_section"):
    section_heading(
        title="Watchlist",
        subtitle="Selected individual stocks using Finnhub's quote endpoint.",
        icon="🟣"
    )

    render_finnhub_quote_grid(watchlist)


with st.container(key="crypto_section"):
    section_heading(
        title="Crypto Pairs",
        subtitle="Crypto quotes using Finnhub's exchange-prefixed crypto symbols.",
        icon="🟠"
    )

    render_finnhub_quote_grid(crypto_pairs)


st.caption(
    "Market index data comes from yfinance. "
    "Watchlist and crypto data use Finnhub quote fields: "
    "c = current price, d = change, dp = percent change, t = timestamp."
)
