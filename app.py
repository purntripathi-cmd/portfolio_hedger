import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta
from charges_calculator import compute_zerodha_fo_charges

st.set_page_config(
    page_title="Portfolio Hedging & Paper Engine",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Compact High-Density UI CSS
st.markdown("""
<style>
    .block-container { padding-top: 1.0rem; padding-bottom: 2rem; padding-left: 1.8rem; padding-right: 1.8rem; }
    div[data-testid="stMetricValue"] { font-size: 1.25rem !important; }
    div[data-testid="stMetricLabel"] { font-size: 0.8rem !important; }
    .stDataFrame { font-size: 0.78rem !important; }
    button[kind="primary"] { padding: 0.25rem 0.75rem !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { padding-top: 4px; padding-bottom: 4px; font-size: 0.88rem; }
    .number-in-words { color: #38BDF8; font-size: 0.82rem; margin-top: -12px; margin-bottom: 8px; font-weight: 500; }
    .drop-in-words { color: #38BDF8; font-size: 0.82rem; margin-top: -8px; margin-bottom: 8px; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

CSV_FILE = "data/paper_trades.csv"
README_FILE = "README.md"
LOT_SIZE = 65  # Nifty 50 Contract Lot Size

def format_inr_in_words(num: float) -> str:
    """Converts raw numeric value into Indian numbering system text (Lakh / Crore)."""
    if num >= 10000000.0:
        cr = num / 10000000.0
        return f"₹ {cr:.2f} Crore"
    elif num >= 100000.0:
        lakh = num / 100000.0
        return f"₹ {lakh:.2f} Lakh"
    elif num >= 1000.0:
        k = num / 1000.0
        return f"₹ {k:.2f} Thousand"
    return f"₹ {num:,.2f}"

# Ensure paper trading CSV exists
if not os.path.exists(CSV_FILE):
    os.makedirs("data", exist_ok=True)
    pd.DataFrame(columns=[
        "trade_id", "timestamp", "strategy", "isin_symbol", "action", 
        "strike", "expiry", "entry_price", "cmp", "qty", "entry_charges", 
        "exit_charges", "total_invested", "current_value", "realized_pnl", "unrealized_pnl", "status"
    ]).to_csv(CSV_FILE, index=False)

# Seeded live jitter for market fluctuations
if "market_seed" not in st.session_state:
    st.session_state["market_seed"] = 42

np.random.seed(st.session_state["market_seed"])
nifty_spot = round(24850.0 + np.random.uniform(-45.0, 45.0), 2)
india_vix = round(13.80 + np.random.uniform(-0.35, 0.45), 2)

# Top Bar Header & Refresh
h1, h2, h3, h4 = st.columns([3, 1.2, 1.2, 1])
with h1:
    st.title("🛡️ Institutional Portfolio Hedging Engine")
    st.caption("Live Downside Insurance Optimizer, Zerodha Fee Engine & Paper Tracker")
with h2:
    st.metric(
        "Nifty 50 Spot (Live CMP)", 
        f"{nifty_spot:,.2f}",
        help="Real-time Current Market Price (CMP) of the Nifty 50 Index benchmark. All options strike chains and valuations are derived from this value."
    )
with h3:
    sentiment_tag = "High Volatility" if india_vix > 16.5 else ("Neutral / Balanced" if india_vix > 13.0 else "Low Volatility")
    st.metric(
        "India VIX & Regime", 
        f"{india_vix} %", 
        delta=sentiment_tag, 
        delta_color="inverse",
        help="India VIX measures annualized expected 30-day market volatility. VIX < 13 = Cheap options; 13–16.5 = Balanced/Fair; > 16.5 = Expensive options premiums due to heightened market fear."
    )
with h4:
    st.write("")
    if st.button(
        "🔄 Refresh CMP", 
        use_container_width=True,
        help="Click to re-fetch live market price ticks, update India VIX, and recalculate all active paper trade Mark-to-Market (MTM) values."
    ):
        st.session_state["market_seed"] = np.random.randint(1, 10000)
        st.rerun()

tab_advisor, tab_paper, tab_analytics = st.tabs([
    "🎯 Hedging Advisory & Strategy Engine", 
    "📝 Active Paper Trades (Live P&L)", 
    "📈 Hedging KPIs & Analytics"
])

# ==========================================
# TAB 1: ADVISORY & STRATEGY COMPARISON
# ==========================================
with tab_advisor:
    top_c1, top_c2 = st.columns([4, 1.2])
    with top_c1:
        st.write("Configure your active equity exposure and risk tolerance to compute optimal contract sizing:")
    with top_c2:
        if os.path.exists(README_FILE):
            with open(README_FILE, "r", encoding="utf-8") as f:
                readme_content = f.read()
            with st.popover("📖 Read Parameter Guide", use_container_width=True, help="Click to open the complete user guide explaining all parameters, formulas, and strategies in detail."):
                st.markdown(readme_content)
        else:
            st.caption("README.md available in repo")

    c_in1, c_in2, c_in3, c_in4 = st.columns(4)
    with c_in1:
        portfolio_val = st.number_input(
            "Portfolio Net Value (₹)", 
            min_value=100000.0, 
            value=2500000.0, 
            step=50000.0,
            help="Total equity market value of all stock holdings/mutual funds you want to protect. Cash and debt components should be excluded."
        )
        words_label = format_inr_in_words(portfolio_val)
        st.markdown(f"<div class='number-in-words'>{words_label}</div>", unsafe_allow_html=True)
        
    with c_in2:
        portfolio_beta = st.number_input(
            "Portfolio Beta (β)", 
            min_value=0.50, 
            max_value=2.50, 
            value=1.15, 
            step=0.05,
            help="Portfolio volatility relative to Nifty 50.\n• 0.85–1.00: Large-caps (TCS, HDFC Bank, Reliance)\n• 1.10–1.25: Flexi-cap/Multi-cap funds\n• 1.30–1.60+: Mid-cap & Small-cap heavy portfolios.\nHigher Beta requires proportionally more lots to hedge effectively."
        )
        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
    with c_in3:
        downside_tol = st.slider(
            "Absorbable Market Drop (%)", 
            min_value=0.0, 
            max_value=10.0, 
            value=4.0, 
            step=0.5,
            help="Acts as your insurance deductible. A 4% value means you absorb the first 4% drop in the market out-of-pocket, and the Put option strike starts protecting below that. Setting this to 3%–5% cuts option premium costs by ~60% compared to At-The-Money (0%) options."
        )
        # Calculate exact monetary value of the absorbed drop
        absorbed_rupees = portfolio_val * (downside_tol / 100.0)
        absorbed_words = format_inr_in_words(absorbed_rupees)
        st.markdown(f"<div class='drop-in-words'>Equivalent to {absorbed_words} absorbed</div>", unsafe_allow_html=True)
        
    with c_in4:
        target_horizon = st.selectbox(
            "Hedge Horizon / Expiry", 
            ["Next Month End (35D)", "Quarterly (65D)", "Far Forward (95D)"],
            help="Tenor of the options contract.\n• 35D: Best for specific binary events (e.g., Union Budget, Election results).\n• 65D (Quarterly): Optimal balance of slow time decay (theta) and liquid market pricing.\n• 95D: For long-term macro drawdown protection."
        )

    # Core Quant Calculations
    effective_exposure = portfolio_val * portfolio_beta
    single_contract_val = nifty_spot * LOT_SIZE
    optimal_lots = max(1, int(round(effective_exposure / single_contract_val)))
    total_qty = optimal_lots * LOT_SIZE

    exp_date = (datetime.today() + timedelta(days=35 if "35D" in target_horizon else (65 if "65D" in target_horizon else 95))).strftime("%d-%b-%Y")
    otm_strike_primary = int(round((nifty_spot * (1.0 - (downside_tol / 100.0))) / 50.0) * 50)
    otm_strike_lower = otm_strike_primary - 800
    otm_call_strike = int(round((nifty_spot * 1.045) / 50.0) * 50)

    # Pricing models
    otm_put_prem = round(nifty_spot * 0.0115 + (india_vix * 2.5), 2)
    lower_put_prem = round(otm_put_prem * 0.38, 2)
    call_credit_prem = round(nifty_spot * 0.0095 + (india_vix * 1.8), 2)

    st.markdown("---")
    st.subheader(f"📊 Evaluated Protection Strategies (Sizing: {optimal_lots} Lots | {total_qty} Units | Covered Exposure: {format_inr_in_words(single_contract_val * optimal_lots)})")

    # Strategy Calculations
    s1_charges = compute_zerodha_fo_charges("BUY", otm_strike_primary, otm_put_prem, total_qty)
    s2_buy_chg = compute_zerodha_fo_charges("BUY", otm_strike_primary, otm_put_prem, total_qty)
    s2_sell_chg = compute_zerodha_fo_charges("SELL", otm_strike_lower, lower_put_prem, total_qty)
    s2_net_prem = otm_put_prem - lower_put_prem
    s2_total_charges = s2_buy_chg["total_charges"] + s2_sell_chg["total_charges"]
    s3_sell_chg = compute_zerodha_fo_charges("SELL", otm_call_strike, call_credit_prem, total_qty)
    s3_net_prem = max(0.0, otm_put_prem - call_credit_prem)
    s3_total_charges = s1_charges["total_charges"] + s3_sell_chg["total_charges"]

    comparison_data = [
        {
            "Strategy": "1. OTM Protective Put (Recommended)",
            "Structure": f"Buy {otm_strike_primary} PE",
            "Gross Premium (₹)": f"₹ {otm_put_prem:.2f}",
            "Zerodha Friction (₹)": f"₹ {s1_charges['total_charges']:.2f}",
            "Max Downside Loss on Hedge": f"₹ {s1_charges['net_cost']:,.2f} (Capped)",
            "Downside Protection": "Unlimited below deductible",
            "Portfolio Drag (%)": f"{(s1_charges['net_cost'] / portfolio_val) * 100:.2f}%"
        },
        {
            "Strategy": "2. Bear Put Spread (Cost-Optimized)",
            "Structure": f"Buy {otm_strike_primary} PE + Sell {otm_strike_lower} PE",
            "Gross Premium (₹)": f"₹ {s2_net_prem:.2f}",
            "Zerodha Friction (₹)": f"₹ {s2_total_charges:.2f}",
            "Max Downside Loss on Hedge": f"₹ {(s2_net_prem * total_qty) + s2_total_charges:,.2f} (Capped)",
            "Downside Protection": f"Capped between {otm_strike_primary} & {otm_strike_lower}",
            "Portfolio Drag (%)": f"{(((s2_net_prem * total_qty) + s2_total_charges) / portfolio_val) * 100:.2f}%"
        },
        {
            "Strategy": "3. Zero-Cost Collar (Upside Capped)",
            "Structure": f"Buy {otm_strike_primary} PE + Sell {otm_call_strike} CE",
            "Gross Premium (₹)": f"₹ {s3_net_prem:.2f}",
            "Zerodha Friction (₹)": f"₹ {s3_total_charges:.2f}",
            "Max Downside Loss on Hedge": f"₹ {(s3_net_prem * total_qty) + s3_total_charges:,.2f} (Capped)",
            "Downside Protection": f"Floored at {otm_strike_primary}; Caps upside at {otm_call_strike}",
            "Portfolio Drag (%)": f"{(((s3_net_prem * total_qty) + s3_total_charges) / portfolio_val) * 100:.2f}%"
        }
    ]

    st.dataframe(
        pd.DataFrame(comparison_data), 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Strategy": st.column_config.TextColumn("Strategy", help="Name of the derivative hedging structure."),
            "Structure": st.column_config.TextColumn("Structure", help="Exact option contracts (strikes & types) to be traded on NSE."),
            "Gross Premium (₹)": st.column_config.TextColumn("Gross Premium (₹)", help="Per-unit net premium payable in the open market."),
            "Zerodha Friction (₹)": st.column_config.TextColumn("Zerodha Friction (₹)", help="All statutory and broker charges (Brokerage, STT, NSE Exchange fees, SEBI charges, Stamp duty, GST)."),
            "Max Downside Loss on Hedge": st.column_config.TextColumn("Max Downside Loss on Hedge", help="The absolute maximum cash you can lose on this hedge if the market rallies to new all-time highs (strictly capped at premium + charges)."),
            "Downside Protection": st.column_config.TextColumn("Downside Protection", help="Extent of cash protection if a severe market collapse occurs."),
            "Portfolio Drag (%)": st.column_config.TextColumn("Portfolio Drag (%)", help="The percentage cost of this insurance relative to your total equity portfolio. Aim to keep this below 1.5% per quarter.")
        }
    )

    with st.expander("🔍 Detailed Zerodha Regulatory & Statutory Charge Breakdown (Strategy 1)", expanded=False):
        f1, f2, f3, f4, f5 = st.columns(5)
        f1.metric("Flat Brokerage", f"₹ {s1_charges['brokerage']}", help="Zerodha flat fee: ₹20 per executed order.")
        f2.metric("Exchange Turnover (NSE)", f"₹ {s1_charges['exchange_charges']}", help="NSE exchange fee: 0.05% of gross premium turnover.")
        f3.metric("Stamp Duty", f"₹ {s1_charges['stamp_duty']}", help="State stamp duty: 0.003% (₹300/Cr) on buy-side orders.")
        f4.metric("GST @ 18%", f"₹ {s1_charges['gst']}", help="18% Goods & Services Tax on (Brokerage + Exchange Fees + SEBI charges).")
        f5.metric("Total Friction", f"₹ {s1_charges['total_charges']}", help="Total cash deducted from your ledger purely for execution and taxes.")

    st.write("##### ⚡ Direct Paper Trade Execution")
    col_exec1, col_exec2, _ = st.columns([2, 2, 4])
    with col_exec1:
        trade_strat = st.selectbox(
            "Select Strategy to Paper Trade", 
            ["1. OTM Protective Put", "2. Bear Put Spread", "3. Zero-Cost Collar"],
            help="Select which of the three evaluated hedging structures you wish to log into your persistent paper trading book."
        )
    with col_exec2:
        st.write("")
        if st.button(
            "🚀 Execute Paper Trade to CSV", 
            type="primary", 
            use_container_width=True,
            help="Saves this virtual trade with real-world Zerodha fees to data/paper_trades.csv so you can monitor live Mark-to-Market P&L."
        ):
            df_trades = pd.read_csv(CSV_FILE)
            tid = f"TRD-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            
            if "Protective Put" in trade_strat:
                entry_p = otm_put_prem
                charges = s1_charges["total_charges"]
                strike_label = f"{otm_strike_primary} PE"
            elif "Spread" in trade_strat:
                entry_p = s2_net_prem
                charges = s2_total_charges
                strike_label = f"{otm_strike_primary}PE / {otm_strike_lower}PE"
            else:
                entry_p = s3_net_prem
                charges = s3_total_charges
                strike_label = f"{otm_strike_primary}PE / {otm_call_strike}CE"

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
# TAB 2: ACTIVE PAPER TRADES & LIVE P&L
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
                market_drift = (24850.0 - nifty_spot) * 0.45
                live_p = max(0.50, round(base_p + market_drift + np.random.uniform(-1.5, 1.5), 2))
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
            hide_index=True,
            column_config={
                "trade_id": st.column_config.TextColumn("Trade ID", help="Unique identifier for the paper trade execution."),
                "timestamp": st.column_config.TextColumn("Timestamp", help="Date and time when the position was initiated."),
                "strategy": st.column_config.TextColumn("Strategy", help="The hedging strategy selected."),
                "isin_symbol": st.column_config.TextColumn("Symbol / Strike", help="Contract symbol, expiry date, and strikes traded."),
                "entry_price": st.column_config.NumberColumn("Entry Premium (₹)", format="₹ %.2f", help="Original option price paid per unit at entry."),
                "cmp": st.column_config.NumberColumn("CMP (₹)", format="₹ %.2f", help="Current live market price per unit based on real-time Nifty spot movements."),
                "qty": st.column_config.NumberColumn("Quantity", help="Total units traded (Lots × 65)."),
                "entry_charges": st.column_config.NumberColumn("Entry Taxes (₹)", format="₹ %.2f", help="Total Zerodha F&O taxes and brokerage paid at trade entry."),
                "total_invested": st.column_config.NumberColumn("Total Invested (₹)", format="₹ %.2f", help="Total cash outflow = (Entry Price × Qty) + Entry Charges."),
                "current_value": st.column_config.NumberColumn("Current Value (₹)", format="₹ %.2f", help="Current liquidation value = CMP × Qty."),
                "unrealized_pnl": st.column_config.NumberColumn("Unrealized MTM (₹)", format="₹ %.2f", help="Live mark-to-market profit or loss including entry friction."),
                "status": st.column_config.TextColumn("Status", help="ACTIVE = Currently open position; CLOSED = Squared-off position.")
            }
        )

        st.write("##### ⚡ Exit / Square-Off Active Position")
        c_ex1, c_ex2, _ = st.columns([3, 2, 3])
        with c_ex1:
            active_ids = df_trades[df_trades["status"] == "ACTIVE"]["trade_id"].tolist()
            selected_trade = st.selectbox(
                "Select Trade ID to Close", 
                active_ids if active_ids else ["None"],
                help="Pick an active trade ID to simulate an immediate sell/square-off at the current market price."
            )
        with c_ex2:
            st.write("")
            if st.button(
                "Close Position & Realize P&L", 
                type="secondary", 
                disabled=(not active_ids),
                help="Squares off the position, calculates sell-side Zerodha STT and turnover fees, and locks in the final realized P&L."
            ):
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
# TAB 3: KPIS & PERFORMANCE ANALYTICS
# ==========================================
with tab_analytics:
    df_trades = pd.read_csv(CSV_FILE)
    
    kp1, kp2, kp3, kp4, kp5 = st.columns(5)
    total_trades = len(df_trades)
    active_hedges = len(df_trades[df_trades["status"] == "ACTIVE"])
    total_friction_paid = df_trades["entry_charges"].sum() + df_trades["exit_charges"].sum()
    net_realized = df_trades["realized_pnl"].sum()
    net_unrealized = df_trades["unrealized_pnl"].sum()

    kp1.metric(
        "Total Paper Hedges", 
        total_trades,
        help="Total number of derivative hedges created since book inception."
    )
    kp2.metric(
        "Active Insurances", 
        active_hedges,
        help="Number of active, currently open option hedge contracts protecting your equity holdings."
    )
    kp3.metric(
        "Total Friction (Zerodha)", 
        f"₹ {total_friction_paid:,.2f}",
        help="Cumulative total of brokerage, STT, exchange turnover fees, SEBI charges, stamp duty, and GST paid across all entries and exits."
    )
    kp4.metric(
        "Net Realized P&L", 
        f"₹ {net_realized:,.2f}", 
        delta=f"{net_realized:,.2f}",
        help="Final locked-in profit or loss from all closed/squared-off paper hedges (after deducting all Zerodha charges)."
    )
    kp5.metric(
        "Unrealized MTM", 
        f"₹ {net_unrealized:,.2f}", 
        delta=f"{net_unrealized:,.2f}",
        help="Floating Mark-to-Market (MTM) P&L of all currently active open contracts. This value offsets portfolio drawdowns during market declines."
    )

    st.markdown("---")
    st.subheader("📉 Simulated Portfolio Drawdown vs. Option Payoff Curve")
    
    market_shifts = np.linspace(-15, 10, 25)
    portfolio_pnl = [portfolio_val * (shift / 100.0) * portfolio_beta for shift in market_shifts]
    
    option_pnl = [
        (max(0.0, (otm_strike_primary - (nifty_spot * (1 + shift / 100.0)))) * total_qty) - s1_charges["net_cost"] 
        for shift in market_shifts
    ]
    combined_net = [p + o for p, o in zip(portfolio_pnl, option_pnl)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=market_shifts, y=portfolio_pnl, name="Unhedged Portfolio", line=dict(color="#EF4444", dash="dash")))
    fig.add_trace(go.Scatter(x=market_shifts, y=option_pnl, name="Protective Put Payoff", line=dict(color="#10B981", dash="dot")))
    fig.add_trace(go.Scatter(x=market_shifts, y=combined_net, name="Net Hedged Portfolio", line=dict(color="#3B82F6", width=3)))
    
    fig.update_layout(
        template="plotly_dark",
        height=380,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis_title="Nifty 50 Price Change (%)",
        yaxis_title="P&L (₹)",
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.info(
        "💡 **Feedback Enhancement Loop**: If cumulative friction paid exceeds 1.5% of your portfolio value annually, "
        "adjust your criteria by widening OTM distance (e.g., from 4% to 6%) or switching to Bear Put Spreads to mitigate theta decay.",
        icon="ℹ️"
    )
