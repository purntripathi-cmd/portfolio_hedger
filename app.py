import yfinance as yf

# Live Market Data Loader with 60s Cache & Safe Fallback
@st.cache_data(ttl=60)
def fetch_live_market_data():
    """
    Fetches real-time / last closing values for NIFTY 50 and INDIA VIX.
    Includes fallback values in case Yahoo Finance API is rate-limited or offline.
    """
    # Defaults in case of weekend/holiday/API rate limit
    spot = 23477.80
    chg_pct = 0.20
    vix = 13.80

    try:
        # Nifty 50 Index (^NSEI)
        nifty_ticker = yf.Ticker("^NSEI")
        df_nifty = nifty_ticker.history(period="5d", interval="1d")
        if not df_nifty.empty and len(df_nifty) >= 2:
            spot = round(float(df_nifty["Close"].iloc[-1]), 2)
            prev_close = float(df_nifty["Close"].iloc[-2])
            chg_pct = round(((spot - prev_close) / prev_close) * 100, 2)

        # India VIX (^INDIAVIX)
        vix_ticker = yf.Ticker("^INDIAVIX")
        df_vix = vix_ticker.history(period="2d", interval="1d")
        if not df_vix.empty:
            vix = round(float(df_vix["Close"].iloc[-1]), 2)

        return spot, chg_pct, vix, "Live Market Data"
    except Exception as e:
        return spot, chg_pct, vix, "Offline / Fallback Data"

# Fetch live values
nifty_spot, nifty_chg_pct, india_vix, data_source_status = fetch_live_market_data()
