def compute_zerodha_fo_charges(action: str, strike_price: float, premium: float, qty: int) -> dict:
    """
    Computes statutory charges and brokerage for Options as per Zerodha tariff:
    - Brokerage: Flat ₹20 per executed order
    - STT/CTT: 0.1% on sell-side option premium (recently revised in Finance Act)
    - Exchange Txn Charge: 0.05% on option premium (NSE)
    - SEBI Charges: ₹10 / Crore on turnover
    - Stamp Duty: 0.003% (₹300/Cr) on buy premium
    - GST: 18% on (Brokerage + Exchange Txn + SEBI)
    """
    turnover = round(premium * qty, 2)
    brokerage = 20.00
    
    # STT only applicable on sell side
    stt = round(turnover * 0.001, 2) if action.upper() == "SELL" else 0.0
    
    # Exchange turnover charge (NSE options: ~0.05% on premium)
    exchange_charges = round(turnover * 0.0005, 2)
    
    # SEBI turnover charge: ₹10 per crore
    sebi_charges = round((turnover / 10000000.0) * 10.0, 4)
    
    # Stamp duty: ₹300 per crore on buy orders only
    stamp_duty = round((turnover / 10000000.0) * 300.0, 2) if action.upper() == "BUY" else 0.0
    
    # GST: 18% on (Brokerage + Exchange Charges + SEBI charges)
    gst = round(0.18 * (brokerage + exchange_charges + sebi_charges), 2)
    
    total_charges = round(brokerage + stt + exchange_charges + sebi_charges + stamp_duty + gst, 2)
    
    return {
        "turnover": turnover,
        "brokerage": brokerage,
        "stt": stt,
        "exchange_charges": exchange_charges,
        "gst": gst,
        "stamp_duty": stamp_duty,
        "sebi_charges": sebi_charges,
        "total_charges": total_charges,
        "net_cost": round(turnover + total_charges if action.upper() == "BUY" else turnover - total_charges, 2)
    }
