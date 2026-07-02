import time
from datetime import datetime, timezone, timedelta
from html import escape

import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh


# ------------------------------------------------------------
# Page setup
# ------------------------------------------------------------

st.set_page_config(
    page_title="Finnhub Market Dashboard",
    page_icon="📈",
    layout="wide"
)

refresh_count = st_autorefresh(
    interval=15_000,
    key="finnhub_market_refresh"
)


# ------------------------------------------------------------
# Styling
# ------------------------------------------------------------

st.markdown(
    """
    <style>
        .main-title {
            font-size: 2.5rem;
            font-weight: 850;
            margin-bottom: 0.2rem;
        }

        .subtitle {
            font-size: 1rem;
            color: #666;
            margin-bottom: 1.2rem;
        }

        .section-header {
            padding: 0.75rem 1rem;
            border-radius: 14px;
            font-size: 1.35rem;
            font-weight: 800;
            margin-top: 1.5rem;
            margin-bottom: 1rem;
            color: white;
        }

        .market-header {
            background: linear-gradient(90deg, #1f4e79, #3b82f6);
        }

        .watchlist-header {
            background: linear-gradient(90deg, #5b2c83, #8b5cf6);
        }

        .crypto-header {
            background: linear-gradient(90deg, #8a4b08, #f59e0b);
        }

        .quote-card {
            border-radius: 18px;
            padding: 1.1rem;
            margin-bottom: 1rem;
            background: white;
            border: 1px solid #e5e7eb;
            box-shadow: 0 4px 14px rgba(0,0,0,0.08);
        }

        .symbol-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
        }

        .symbol {
            font-size: 1.35rem;
            font-weight: 850;
            color: #111827;
        }

        .badge-up {
            color: #065f46;
            background-color: #d1fae5;
            padding: 0.25rem 0.55rem;
            border-radius: 999px;
            font-weight: 750;
            font-size: 0.85rem;
        }

        .badge-down {
            color: #991b1b;
            background-color: #fee2e2;
            padding: 0.25rem 0.55rem;
            border-radius: 999px;
            font-weight: 750;
            font-size: 0.85rem;
        }

        .badge-flat {
            color: #374151;
            background-color: #e5e7eb;
            padding: 0.25rem 0.55rem;
            border-radius: 999px;
            font-weight: 750;
            font-size: 0.85rem;
        }

        .price {
            font-size: 2rem;
            font-weight: 850;
            color: #111827;
            margin-bottom: 0.25rem;
        }

        .change-up {
            color: #059669;
            font-size: 1rem;
            font-weight: 750;
        }

        .change-down {
            color: #dc2626;
            font-size: 1rem;
            font-weight: 750;
        }

        .change-flat {
            color: #6b7280;
            font-size: 1rem;
            font-weight: 750;
        }

        .as-of {
            margin-top: 0.8rem;
            color: #6b7280;
            font-size: 0.82rem;
        }

        .small-note {
            color: #6b7280;
            font-size: 0.9rem;
        }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="main-title">📈 Finnhub Market Dashboard</div>
    <div class="subtitle">
        Market overview, personal watchlist, and crypto quotes. Auto-refreshes every 15 seconds.
    </div>
    """,
    unsafe_allow_html=True
)

st.caption(f"Refresh count: {refresh_count}")


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
STOCK_CANDLE_URL = "https://finnhub.io/api/v1/stock/candle"

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
    "Market Overview": {
        "symbols": market_overview,
        "header_class": "market-header"
    },
    "Watchlist": {
        "symbols": watchlist,
        "header_class": "watchlist-header"
    },
    "Crypto Pairs": {
        "symbols": crypto_pairs,
        "header_class": "crypto-header"
    }
}


# 11 quote calls every 15 seconds = about 44 calls/minute for one active session.
# Candle data is cached separately, so it does not get pulled every refresh.
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
def get_stock_candles(symbol: str, days_back: int = 60) -> pd.DataFrame:
    """
    Pull daily stock candles from Finnhub and return a DataFrame with date and close.

    Cached for 15 minutes so the chart does not create 3 extra API calls
    on every 15-second app refresh.
    """
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days_back)

    params = {
        "symbol": symbol,
        "resolution": "D",
        "from": int(start_dt.timestamp()),
        "to": int(end_dt.timestamp())
    }

    response = requests.get(
        STOCK_CANDLE_URL,
        params=params,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()
    data = response.json()

    if data.get("s") != "ok":
        raise ValueError(f"Finnhub candle response for {symbol}: {data}")

    df = pd.DataFrame({
        "date": pd.to_datetime(data["t"], unit="s", utc=True),
        symbol: data["c"]
    })

    return df


def get_market_chart_data(symbols: list[str]) -> pd.DataFrame:
    """
    Combine close-price candle data for SPY, QQQ, and DIA.
    """
    combined = None

    for symbol in symbols:
        df = get_stock_candles(symbol)

        if combined is None:
            combined = df
        else:
            combined = combined.merge(df, on="date", how="outer")

    if combined is None or combined.empty:
        return pd.DataFrame()

    combined = combined.sort_values("date")
    return combined


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


def get_direction_classes(change):
    try:
        change = float(change)
    except Exception:
        return "badge-flat", "change-flat", "■", "Flat"

    if change > 0:
        return "badge-up", "change-up", "▲", "Up"
    elif change < 0:
        return "badge-down", "change-down", "▼", "Down"
    else:
        return "badge-flat", "change-flat", "■", "Flat"


def render_quote_card(symbol: str, quote: dict):
    current_price = quote.get("c")
    change = quote.get("d")
    percent_change = quote.get("dp")
    timestamp = quote.get("t")

    badge_class, change_class, arrow, direction_label = get_direction_classes(change)

    safe_symbol = escape(symbol)
    price_text = escape(format_price(current_price))
    change_text = escape(format_change(change))
    percent_text = escape(format_percent(percent_change))
    as_of_text = escape(format_as_of_timestamp(timestamp))

    st.markdown(
        f"""
        <div class="quote-card">
            <div class="symbol-row">
                <div class="symbol">{safe_symbol}</div>
                <div class="{badge_class}">{arrow} {direction_label}</div>
            </div>

            <div class="price">{price_text}</div>

            <div class="{change_class}">
                {change_text} &nbsp; | &nbsp; {percent_text}
            </div>

            <div class="as-of">
                As of: {as_of_text}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.expander(f"Raw Finnhub response for {symbol}"):
        st.json(quote)


def render_market_chart():
    st.subheader("SPY, QQQ, and DIA — recent daily close")

    try:
        chart_df = get_market_chart_data(market_overview)

        if chart_df.empty:
            st.warning("No candle data returned for the market overview chart.")
            return

        chart_df = chart_df.set_index("date")

        st.line_chart(chart_df, height=320)

        latest_date = chart_df.dropna(how="all").index.max()
        st.caption(
            f"Chart uses daily close data from Finnhub `/stock/candle`. "
            f"Latest candle shown: {latest_date.strftime('%Y-%m-%d')} UTC. "
            f"Candle data is cached for 15 minutes."
        )

    except Exception as e:
        st.warning(
            "Could not load Finnhub stock candle data for the chart. "
            "Your quote endpoint can still work even if the candle endpoint is unavailable "
            f"for your key. Error: {e}"
        )


def render_group(group_name: str, group_info: dict):
    symbols = group_info["symbols"]
    header_class = group_info["header_class"]

    st.markdown(
        f"""
        <div class="section-header {header_class}">
            {escape(group_name)}
        </div>
        """,
        unsafe_allow_html=True
    )

    if group_name == "Market Overview":
        render_market_chart()

    for start in range(0, len(symbols), 3):
        row_symbols = symbols[start:start + 3]
        cols = st.columns(3)

        for col, symbol in zip(cols, row_symbols):
            with col:
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


# ------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------

total_symbols = sum(len(group_info["symbols"]) for group_info in groups.values())

st.info(
    f"This dashboard requests {total_symbols} Finnhub quotes every 15 seconds, "
    f"or about {total_symbols * 4} quote calls per minute for one active session. "
    "The SPY/QQQ/DIA chart uses cached daily candle data."
)

for group_name, group_info in groups.items():
    render_group(group_name, group_info)

st.divider()

st.markdown(
    """
    <div class="small-note">
        Finnhub quote fields used here:
        <code>c</code> = current price,
        <code>d</code> = change,
        <code>dp</code> = percent change,
        <code>t</code> = timestamp.
        The chart uses daily close prices from Finnhub's stock candle endpoint.
    </div>
    """,
    unsafe_allow_html=True
)
