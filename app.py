import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import yfinance as yf
from datetime import datetime, timedelta
from scipy.stats import norm
from charges_calculator import compute_zerodha_fo_charges

st.set_page_config(
    page_title="Portfolio Hedging & Paper Engine",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .block-container { padding-top: 0.8rem; padding-bottom: 2rem; padding-left: 1.5rem; padding-right: 1.5rem; }
    div[data-testid="stMetricValue"] { font-size: 1.20rem !important; font-weight: 700 !important; }
    div[data-testid="stMetricLabel"] { font-size: 0.78rem !important; }
    .stDataFrame { font-size: 0.80rem !important; }
    .number-in-words { color: #38BDF8; font-size: 0.82rem; margin-top: -12px; margin-bottom: 8px; font-weight: 500; }
    .drop-in-words { color: #38BDF8; font-size: 0.82rem; margin-top: -8px; margin-bottom: 8px; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

CSV_FILE = "data/paper_trades.csv"
README_FILE = "README.md"
# Official SEBI Revised NIFTY Lot Size
LOT_SIZE = 75
RISK_FREE_RATE = 0.068  # 10Y Indian Sovereign Yield ~6.80%

def format_inr_in_words(num: float) -> str:
    if abs(num) >= 10000000.0:
        return f"₹ {num / 10000000.0:.2f} Crore"
    elif abs(num) >= 100000.0:
        return f"₹ {num / 100000.0:.2f} Lakh"
    elif abs(num) >= 1000.0:
        return f"₹ {num / 1000.0:.2f} Thousand"
    return f"₹ {num:,.2f}"

# Ensure data directory and paper trade storage
if not os.path.exists(CSV_FILE):
    os.makedirs("data", exist_ok=True)
    pd.DataFrame(columns=[
        "trade_id", "timestamp", "strategy", "isin_symbol", "action", 
        "strike", "expiry", "entry_price", "cmp", "qty", "entry_charges", 
        "exit_charges", "total_invested", "current_value", "realized_pnl", "unrealized_pnl", "status"
    ]).to_csv(CSV_FILE, index=False)

# Live Market Feed
@st.cache_data(ttl=60)
def fetch_live_market_data():
    spot = 23477.80
    chg_pct = 0.20
    vix = 13.80
    status = "Fallback"
    try:
        nifty_ticker = yf.Ticker("^NSEI")
        df_nifty = nifty_ticker.history(period="5d", interval="1d")
        if not df_nifty.empty and len(df_nifty) >= 2:
            spot = round(float(df_nifty["Close"].iloc[-1]), 2)
            prev_close = float(df_nifty["Close"].iloc[-2])
            chg_pct = round(((spot - prev_close) / prev_close) * 100, 2)
            status = "Live"

        vix_ticker = yf.Ticker("^INDIAVIX")
        df_vix = vix_ticker.history(period="2d", interval="1d")
        if not df_vix.empty:
            vix = round(float(df_vix["Close"].iloc[-1]), 2)
    except Exception:
        pass
    return spot, chg_pct, vix, status

nifty_spot, nifty_chg_pct, india_vix, data_status = fetch_live_market_data()

# Quantitative Black-Scholes-Merton Pricing Engine
def black_scholes_pricing(S, K, T, r, sigma, option_type="put"):
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        intrinsic = max(0.0, K - S if option_type == "put" else S - K)
        return intrinsic, 0.0, 0.0, 0.0, 0.0

    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    if option_type == "put":
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = norm.cdf(d1) - 1.0
        theta = (- (S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) + r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365.0
    else:
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        delta = norm.cdf(d1)
        theta = (- (S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm.cdf(d2)) / 365.0

    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    vega = (S * norm.pdf(d1) * np.sqrt(T)) / 100.0

    return max(1.0, round(float(price), 2)), round(float(delta), 3), round(float(gamma), 5), round(float(theta), 2), round(float(vega), 2)

# Top Bar Header
h1, h2, h3, h4 = st.columns([3, 1.3, 1.1, 1])
with h1:
    st.title("🛡️ Institutional Portfolio Hedging Engine")
    st.caption(f"Black-Scholes-Merton Downside Insurance Optimizer & Greeks Engine ({data_status} Feed | Lot Size: {LOT_SIZE})")
with h2:
    st.metric(
        label="NIFTY 50 Benchmark", 
        value=f"{nifty_spot:,.2f}", 
        delta=f"{nifty_chg_pct:+.2f}% Today"
    )
with h3:
    sentiment_tag = "Elevated Volatility" if india_vix > 16.5 else ("Neutral / Balanced" if india_vix > 13.0 else "Low Volatility")
    st.metric(
        label="India VIX", 
        value=f"{india_vix:.2f}%", 
        delta=sentiment_tag, 
        delta_color="inverse"
    )
with h4:
    st.write("")
    if st.button("🔄 Refresh CMP", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

tab_advisor, tab_payoff, tab_paper, tab_analytics = st.tabs([
    "🎯 Hedging Advisory & Greeks", 
    "📊 Interactive Payoff Simulator",
    "📝 Active Paper Trades (Live P&L)", 
    "📈 Hedging KPIs & VaR Risk"
])

# ==========================================
# TAB 1: ADVISORY & GREEKS COMPARISON
# ==========================================
with tab_advisor:
    c_in1, c_in2, c_in3, c_in4 = st.columns(4)
    with c_in1:
        portfolio_val = st.number_input(
            "Portfolio Net Value (₹)", 
            min_value=100000.0, 
            value=2500000.0, 
            step=50000.0,
            help="Total equity market value of stock holdings and equity funds to protect."
        )
        st.markdown(f"<div class='number-in-words'>{format_inr_in_words(portfolio_val)}</div>", unsafe_allow_html=True)
        
    with c_in2:
        portfolio_beta = st.number_input(
            "Portfolio Beta (β)", 
            min_value=0.50, 
            max_value=2.50, 
            value=1.15, 
            step=0.05,
            help="Portfolio volatility relative to Nifty 50 (1.0 = Large caps, >1.2 = Mid/Small caps)."
        )
    with c_in3:
        downside_tol = st.slider(
            "Absorbable Market Drop (%)", 
            min_value=0.0, 
            max_value=10.0, 
            value=4.0, 
            step=0.5,
            help="Your insurance deductible. The percentage decline in Nifty 50 you absorb before protection triggers."
        )
        absorbed_rupees = portfolio_val * (downside_tol / 100.0)
        st.markdown(f"<div class='drop-in-words'>Equivalent to {format_inr_in_words(absorbed_rupees)} absorbed</div>", unsafe_allow_html=True)
        
    with c_in4:
        target_horizon = st.selectbox(
            "Hedge Horizon / Expiry", 
            ["Near Month (30D)", "Mid Month (60D)", "Far Forward (90D)"],
            help="Option maturity period. Longer horizons experience slower theta decay."
        )

    # Quant Sizing & Strike Determination
    days_to_exp = 30 if "30D" in target_horizon else (60 if "60D" in target_horizon else 90)
    t_years = days_to_exp / 365.0
    sigma_vix = (india_vix / 100.0)
    
    effective_exposure = portfolio_val * portfolio_beta
    single_contract_val = nifty_spot * LOT_SIZE
    optimal_lots = max(1, int(round(effective_exposure / single_contract_val)))
    total_qty = optimal_lots * LOT_SIZE
    exp_date = (datetime.today() + timedelta(days=days_to_exp)).strftime("%d-%b-%Y")

    otm_strike_primary = int(round((nifty_spot * (1.0 - (downside_tol / 100.0))) / 50.0) * 50)
    otm_strike_lower = otm_strike_primary - 800
    otm_call_strike = int(round((nifty_spot * 1.04) / 50.0) * 50)

    # Black-Scholes Pricing & Greeks
    p1_price, p1_delta, p1_gamma, p1_theta, p1_vega = black_scholes_pricing(nifty_spot, otm_strike_primary, t_years, RISK_FREE_RATE, sigma_vix, "put")
    p2_price, p2_delta, p2_gamma, p2_theta, p2_vega = black_scholes_pricing(nifty_spot, otm_strike_lower, t_years, RISK_FREE_RATE, sigma_vix, "put")
    c1_price, c1_delta, c1_gamma, c1_theta, c1_vega = black_scholes_pricing(nifty_spot, otm_call_strike, t_years, RISK_FREE_RATE, sigma_vix, "call")

    # Strategy Calculations with Zerodha Friction
    s1_charges = compute_zerodha_fo_charges("BUY", otm_strike_primary, p1_price, total_qty)
    
    s2_buy_chg = compute_zerodha_fo_charges("BUY", otm_strike_primary, p1_price, total_qty)
    s2_sell_chg = compute_zerodha_fo_charges("SELL", otm_strike_lower, p2_price, total_qty)
    s2_net_prem = max(1.0, round(p1_price - p2_price, 2))
    s2_total_charges = s2_buy_chg["total_charges"] + s2_sell_chg["total_charges"]

    s3_sell_chg = compute_zerodha_fo_charges("SELL", otm_call_strike, c1_price, total_qty)
    s3_net_prem = max(0.0, round(p1_price - c1_price, 2))
    s3_total_charges = s1_charges["total_charges"] + s3_sell_chg["total_charges"]

    st.markdown("---")
    st.subheader(f"📊 Evaluated Protection Strategies (Sizing: {optimal_lots} Lots | {total_qty} Units | Covered Exposure: {format_inr_in_words(single_contract_val * optimal_lots)})")

    comparison_data = [
        {
            "Strategy": "1. OTM Protective Put (Recommended)",
            "Structure": f"Buy {otm_strike_primary} PE",
            "Option Premium (₹)": f"₹ {p1_price:.2f}",
            "Delta (Δ)": f"{p1_delta:.3f}",
            "Theta (₹/Day)": f"₹ {p1_theta * total_qty:.1f}",
            "Portfolio Drag (%)": f"{(s1_charges['net_cost'] / portfolio_val) * 100:.2f}% ({format_inr_in_words(s1_charges['net_cost'])})",
            "Downside Protection": "Full tail-risk coverage below deductible",
            "Max Loss on Hedge": f"₹ {s1_charges['net_cost']:,.2f}"
        },
        {
            "Strategy": "2. Bear Put Spread (Cost-Optimized)",
            "Structure": f"Buy {otm_strike_primary} PE + Sell {otm_strike_lower} PE",
            "Option Premium (₹)": f"₹ {s2_net_prem:.2f} (Net)",
            "Delta (Δ)": f"{p1_delta - p2_delta:.3f}",
            "Theta (₹/Day)": f"₹ {(p1_theta - p2_theta) * total_qty:.1f}",
            "Portfolio Drag (%)": f"{(((s2_net_prem * total_qty) + s2_total_charges) / portfolio_val) * 100:.2f}% ({format_inr_in_words((s2_net_prem * total_qty) + s2_total_charges)})",
            "Downside Protection": f"Floored between {otm_strike_primary} & {otm_strike_lower}",
            "Max Loss on Hedge": f"₹ {(s2_net_prem * total_qty) + s2_total_charges:,.2f}"
        },
        {
            "Strategy": "3. Zero-Cost Collar (Upside Capped)",
            "Structure": f"Buy {otm_strike_primary} PE + Sell {otm_call_strike} CE",
            "Option Premium (₹)": f"₹ {s3_net_prem:.2f} (Net)",
            "Delta (Δ)": f"{p1_delta - c1_delta:.3f}",
            "Theta (₹/Day)": f"₹ {(p1_theta - c1_theta) * total_qty:.1f}",
            "Portfolio Drag (%)": f"{(((s3_net_prem * total_qty) + s3_total_charges) / portfolio_val) * 100:.2f}% ({format_inr_in_words((s3_net_prem * total_qty) + s3_total_charges)})",
            "Downside Protection": f"Floored at {otm_strike_primary}; Caps rally at {otm_call_strike}",
            "Max Loss on Hedge": f"₹ {(s3_net_prem * total_qty) + s3_total_charges:,.2f}"
        }
    ]

    st.dataframe(pd.DataFrame(comparison_data), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.write("##### ⚡ Direct Paper Trade Execution")
    col_exec1, col_exec2, _ = st.columns([2, 2, 4])
    with col_exec1:
        trade_strat = st.selectbox(
            "Select Strategy to Deploy into Paper Portfolio", 
            ["1. OTM Protective Put", "2. Bear Put Spread", "3. Zero-Cost Collar"]
        )
    with col_exec2:
        st.write("")
        if st.button("🚀 Deploy Paper Trade to CSV", type="primary", use_container_width=True):
            df_trades = pd.read_csv(CSV_FILE)
            tid = f"TRD-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            
            if "Protective Put" in trade_strat:
                entry_p = p1_price
                charges = s1_charges["total_charges"]
                strike_label = f"{otm_strike_primary} PE"
            elif "Spread" in trade_strat:
                entry_p = s2_net_prem
                charges = s2_total_charges
                strike_label = f"{otm_strike_primary}PE/{otm_strike_lower}PE"
            else:
                entry_p = s3_net_prem
                charges = s3_total_charges
                strike_label = f"{otm_strike_primary}PE/{otm_call_strike}CE"

            new_record = {
                "trade_id": tid,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "strategy": trade_strat,
                "isin_symbol": f"NIFTY-{exp_date}-{strike_label}",
                "action": "BUY",
                "strike": otm_strike_primary,
                "expiry": exp_date,
                "entry_price": entry_p,
                "cmp": entry_p,
                "qty": total_qty,
                "entry_charges": charges,
                "exit_charges": 0.0,
                "total_invested": round((entry_p * total_qty) + charges, 2),
                "current_value": round(entry_p * total_qty, 2),
                "realized_pnl": 0.0,
                "unrealized_pnl": round(-charges, 2),
                "status": "ACTIVE"
            }
            df_trades = pd.concat([df_trades, pd.DataFrame([new_record])], ignore_index=True)
            df_trades.to_csv(CSV_FILE, index=False)
            st.success(f"Executed Paper Trade `{tid}` successfully!")
            st.rerun()

# ==========================================
# TAB 2: INTERACTIVE PAYOFF SIMULATOR
# ==========================================
with tab_payoff:
    st.subheader("📊 Interactive Multi-Strategy Payoff Diagrams")
    st.caption("Visualizes total portfolio P&L (Equity + Derivative Hedge) across market crash and rally scenarios.")

    nifty_range_pct = np.linspace(-15, 12, 55)
    unhedged_pnl = [portfolio_val * (p / 100.0) * portfolio_beta for p in nifty_range_pct]

    # Protective Put Payoff
    put_payoffs = []
    spread_payoffs = []
    collar_payoffs = []

    for p in nifty_range_pct:
        sim_spot = nifty_spot * (1.0 + (p / 100.0))
        
        # 1. Protective Put
        p_gain = max(0.0, otm_strike_primary - sim_spot) * total_qty - s1_charges["net_cost"]
        put_payoffs.append(portfolio_val * (p / 100.0) * portfolio_beta + p_gain)

        # 2. Bear Put Spread
        sp_gain = (max(0.0, otm_strike_primary - sim_spot) - max(0.0, otm_strike_lower - sim_spot)) * total_qty - ((s2_net_prem * total_qty) + s2_total_charges)
        spread_payoffs.append(portfolio_val * (p / 100.0) * portfolio_beta + sp_gain)

        # 3. Collar
        col_gain = (max(0.0, otm_strike_primary - sim_spot) - max(0.0, sim_spot - otm_call_strike)) * total_qty - ((s3_net_prem * total_qty) + s3_total_charges)
        collar_payoffs.append(portfolio_val * (p / 100.0) * portfolio_beta + col_gain)

    fig_payoff = go.Figure()
    fig_payoff.add_trace(go.Scatter(x=nifty_range_pct, y=unhedged_pnl, name="Unhedged Portfolio (Beta 1.15)", line=dict(color="#EF4444", dash="dash", width=2)))
    fig_payoff.add_trace(go.Scatter(x=nifty_range_pct, y=put_payoffs, name="Hedged: Protective Put", line=dict(color="#10B981", width=3)))
    fig_payoff.add_trace(go.Scatter(x=nifty_range_pct, y=spread_payoffs, name="Hedged: Bear Put Spread", line=dict(color="#3B82F6", width=2)))
    fig_payoff.add_trace(go.Scatter(x=nifty_range_pct, y=collar_payoffs, name="Hedged: Zero-Cost Collar", line=dict(color="#F59E0B", width=2)))

    fig_payoff.add_hline(y=0, line_dash="solid", line_color="gray", opacity=0.4)
    fig_payoff.add_vline(x=0, line_dash="dot", line_color="gray", opacity=0.4)
    fig_payoff.update_layout(
        title="Portfolio Payoff Profile at Expiry (Equity Portfolio + Hedge Structure)",
        xaxis_title="Nifty 50 Movement (%)",
        yaxis_title="Net Combined P&L (₹)",
        hovermode="x unified",
        height=450,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    st.plotly_chart(fig_payoff, use_container_width=True)

# ==========================================
# TAB 3: ACTIVE PAPER TRADES & LIVE P&L
# ==========================================
with tab_paper:
    df_trades = pd.read_csv(CSV_FILE)
    st.subheader("📋 Managed Paper Trading Book")

    if df_trades.empty:
        st.info("No paper trades logged yet. Deploy a hedge from the 'Hedging Advisory' tab.")
    else:
        for idx, row in df_trades.iterrows():
            if row["status"] == "ACTIVE":
                base_p = row["entry_price"]
                market_drift = (row["strike"] - nifty_spot) * 0.45 if nifty_spot < row["strike"] else (23477.80 - nifty_spot) * 0.35
                live_p = max(0.50, round(base_p + market_drift, 2))
                cur_val = round(live_p * row["qty"], 2)
                unrealized = round(cur_val - row["total_invested"], 2)

                df_trades.at[idx, "cmp"] = live_p
                df_trades.at[idx, "current_value"] = cur_val
                df_trades.at[idx, "unrealized_pnl"] = unrealized

        df_trades.to_csv(CSV_FILE, index=False)

        def color_pnl(val):
            color = "#10B981" if val > 0 else "#EF4444" if val < 0 else "#94A3B8"
            return f"color: {color}; font-weight: bold;"

        st.dataframe(
            df_trades[[
                "trade_id", "timestamp", "strategy", "isin_symbol", 
                "entry_price", "cmp", "qty", "entry_charges", 
                "total_invested", "current_value", "unrealized_pnl", "status"
            ]].style.map(color_pnl, subset=["unrealized_pnl"]),
            use_container_width=True,
            hide_index=True
        )

        st.write("##### ⚡ Exit / Square-Off Active Position")
        c_ex1, c_ex2, _ = st.columns([3, 2, 3])
        with c_ex1:
            active_ids = df_trades[df_trades["status"] == "ACTIVE"]["trade_id"].tolist()
            selected_trade = st.selectbox("Select Trade ID to Close", active_ids if active_ids else ["None"])
        with c_ex2:
            st.write("")
            if st.button("Close Position & Realize P&L", type="secondary", disabled=(not active_ids)):
                target_idx = df_trades[df_trades["trade_id"] == selected_trade].index[0]
                row = df_trades.loc[target_idx]
                exit_chg = compute_zerodha_fo_charges("SELL", row["strike"], row["cmp"], row["qty"])["total_charges"]
                
                final_realized = round((row["cmp"] * row["qty"]) - row["total_invested"] - exit_chg, 2)
                df_trades.at[target_idx, "exit_charges"] = exit_chg
                df_trades.at[target_idx, "realized_pnl"] = final_realized
                df_trades.at[target_idx, "unrealized_pnl"] = 0.0
                df_trades.at[target_idx, "status"] = "CLOSED"
                df_trades.to_csv(CSV_FILE, index=False)
                st.success(f"Closed {selected_trade}. Realized P&L: ₹{final_realized:,.2f}")
                st.rerun()

# ==========================================
# TAB 4: KPIS & VALUE-AT-RISK (VAR) ANALYTICS
# ==========================================
with tab_analytics:
    df_trades = pd.read_csv(CSV_FILE)
    
    # Portfolio Value-at-Risk Engine
    daily_vol = (india_vix / np.sqrt(252)) / 100.0
    var_95_1d = portfolio_val * portfolio_beta * (1.645 * daily_vol)
    var_99_1d = portfolio_val * portfolio_beta * (2.326 * daily_vol)
    var_95_30d = var_95_1d * np.sqrt(30)

    st.subheader("🛡️ Portfolio Tail-Risk & Value-at-Risk (VaR) Analytics")
    v1, v2, v3, v4 = st.columns(4)
    v1.metric("1-Day VaR (95% Cl)", f"₹ {var_95_1d:,.0f}", delta=f"-{(var_95_1d/portfolio_val)*100:.2f}% Max 1D Loss")
    v2.metric("1-Day VaR (99% Cl)", f"₹ {var_99_1d:,.0f}", delta=f"-{(var_99_1d/portfolio_val)*100:.2f}% Extreme 1D Loss")
    v3.metric("30-Day Drawdown VaR (95%)", f"₹ {var_95_30d:,.0f}", help="Estimated max capital loss over 30 days under normal market conditions")
    v4.metric("Annualized Daily Volatility", f"{daily_vol*100:.2f}% / Day")

    st.markdown("---")
    kp1, kp2, kp3, kp4, kp5 = st.columns(5)
    total_trades = len(df_trades)
    active_hedges = len(df_trades[df_trades["status"] == "ACTIVE"])
    total_friction_paid = df_trades["entry_charges"].sum() + df_trades["exit_charges"].sum()
    net_realized = df_trades["realized_pnl"].sum()
    net_unrealized = df_trades["unrealized_pnl"].sum()

    kp1.metric("Total Paper Hedges", total_trades)
    kp2.metric("Active Insurances", active_hedges)
    kp3.metric("Friction Paid", f"₹ {total_friction_paid:,.2f}")
    kp4.metric("Net Realized P&L", f"₹ {net_realized:,.2f}")
    kp5.metric("Unrealized MTM", f"₹ {net_unrealized:,.2f}")
