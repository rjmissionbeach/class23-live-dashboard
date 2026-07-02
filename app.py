import time
from datetime import datetime, timezone

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

st.title("📈 Finnhub Market Dashboard")

# Auto-refresh every 15 seconds
# interval is in milliseconds
refresh_count = st_autorefresh(
    interval=15_000,
    key="finnhub_market_refresh"
)

st.caption(f"Auto-refreshes every 15 seconds. Refresh count: {refresh_count}")


# ------------------------------------------------------------
# Finnhub API setup
# ------------------------------------------------------------

# In Streamlit Community Cloud:
# App → Settings → Secrets
#
# Add:
# FINNHUB_API_KEY = "your_api_key_here"
#
# Do NOT put the API key directly in app.py.
FINNHUB_API_KEY = st.secrets.get("FINNHUB_API_KEY")

if not FINNHUB_API_KEY:
    st.error(
        "Missing FINNHUB_API_KEY. Add it in Streamlit Community Cloud secrets "
        "or in .streamlit/secrets.toml for local testing."
    )
    st.stop()


BASE_URL = "https://finnhub.io/api/v1/quote"

HEADERS = {
    "X-Finnhub-Token": FINNHUB_API_KEY
}


# ------------------------------------------------------------
# Tickers
# ------------------------------------------------------------

market_overview = ["SPY", "QQQ", "DIA"]

watchlist = ["MSFT", "CVNA", "INTC", "NVDA", "SOFI"]

crypto_pairs = ["BINANCE:BTCUSDT", "BINANCE:ETHUSDT"]

groups = {
    "Market Overview": market_overview,
    "Watchlist": watchlist,
    "Crypto Pairs": crypto_pairs
}


# 10 total API calls every 15 seconds = about 40 calls/minute
# for one active app session, below Finnhub's listed free-tier limit.
# This short pause also avoids rapid back-to-back calls.
REQUEST_SLEEP_SECONDS = 0.50


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------

def get_finnhub_quote(symbol: str) -> dict:
    """
    Call Finnhub's /quote endpoint for one symbol.
    Returns the full JSON response.
    """
    response = requests.get(
        BASE_URL,
        params={"symbol": symbol},
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()
    return response.json()


def format_as_of_timestamp(raw_timestamp):
    """
    Finnhub's /quote response includes `t`, a Unix timestamp.
    This converts it into a readable UTC time.
    """
    if raw_timestamp is None or raw_timestamp == 0:
        return "No timestamp returned"

    try:
        raw_timestamp = int(raw_timestamp)

        # Finnhub quote timestamps are normally Unix seconds.
        # This handles milliseconds defensively.
        if raw_timestamp > 10_000_000_000:
            dt = datetime.fromtimestamp(raw_timestamp / 1000, tz=timezone.utc)
        else:
            dt = datetime.fromtimestamp(raw_timestamp, tz=timezone.utc)

        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    except Exception:
        return f"Unrecognized timestamp: {raw_timestamp}"


def render_quote_card(symbol: str, quote: dict):
    """
    Render one quote in a Streamlit metric-style card.
    Finnhub quote fields:
      c  = current price
      d  = change
      dp = percent change
      t  = timestamp
    """
    current_price = quote.get("c")
    change = quote.get("d")
    percent_change = quote.get("dp")
    timestamp = quote.get("t")

    as_of = format_as_of_timestamp(timestamp)

    with st.container(border=True):
        st.subheader(symbol)

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                label="Price",
                value="N/A" if current_price is None else f"{current_price:,.4f}"
            )

        with col2:
            st.metric(
                label="Change",
                value="N/A" if change is None else f"{change:,.4f}"
            )

        with col3:
            st.metric(
                label="Percent Change",
                value="N/A" if percent_change is None else f"{percent_change:,.2f}%"
            )

        st.caption(f"As of: {as_of}")

        with st.expander("Raw Finnhub response"):
            st.json(quote)


def render_group(group_name: str, symbols: list[str]):
    """
    Render one dashboard section.
    """
    st.header(group_name)

    for symbol in symbols:
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

total_symbols = sum(len(symbols) for symbols in groups.values())

st.info(
    f"This app calls Finnhub for {total_symbols} symbols every 15 seconds. "
    f"That is about {total_symbols * 4} calls per minute for one active session."
)

for group_name, symbols in groups.items():
    render_group(group_name, symbols)

st.divider()

st.caption(
    "Finnhub /quote response fields used here: "
    "`c` = current price, `d` = change, `dp` = percent change, `t` = timestamp."
)
