import yfinance as yf
import requests
import math
import os

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ⚙️ STRATEGY SETTINGS
# Change this to 45 for "Weekly Rung" Strategy
TARGET_DTE = 45  
# Multiplier: 1.0 = 16 Delta (Aggressive), 1.3 = 10 Delta (Safe), 2.0 = 5 Delta (Ultra Safe)
SAFETY_FACTOR = 1.3 

def send_alert(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ Error: Missing GitHub Secrets")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    requests.post(url, json=payload)

def run_analysis():
    print("--- Sentinel Cloud Agent Starting ---")
    
    # 1. FETCH DATA
    try:
        tickers = yf.Tickers("^GSPC ^VIX")
        spx = tickers.tickers['^GSPC'].history(period="1d")['Close'].iloc[-1]
        vix = tickers.tickers['^VIX'].history(period="1d")['Close'].iloc[-1]
    except:
        print("⚠️ Index data failed. Switching to SPY fallback.")
        spy = yf.Ticker("SPY").history(period="1d")['Close'].iloc[-1]
        spx = spy * 10
        vix = 15.0

    # 2. SCAN NEWS
    spy = yf.Ticker("SPY")
    news_items = spy.news
    fed_keywords = ["FED ", "POWELL", "FOMC", "CPI", "INFLATION", "PPI", "RATE HIKE"]
    danger_headlines = []
    
    for item in news_items[:8]:
        title = item.get('title', '').upper()
        if any(key in title for key in fed_keywords):
            danger_headlines.append(f"• {item.get('title')}")

    # 3. CALCULATE STRIKES (The Fix)
    # Volatility scales with square root of time
    time_factor = math.sqrt(TARGET_DTE / 365)
    
    # Expected Move = Price * (VIX/100) * sqrt(Days/365)
    # We multiply by SAFETY_FACTOR (1.3) to get ~10 Delta
    expected_range = spx * (vix/100) * time_factor * SAFETY_FACTOR
    
    call_strike = 5 * round((spx + expected_range) / 5)
    put_strike = 5 * round((spx - expected_range) / 5)

    # 4. DECISION LOGIC (Tweaked for 45 DTE)
    decision = "✅ GO"
    reason = "Conditions Optimal"
    
    # For 45 DTE, we are less scared of 1-day events, but VIX levels matter more
    if vix < 11.0:
        decision = "⛔ NO GO"
        reason = "VIX too low (<11). Not enough premium for 45 days."
    elif vix > 30:
        decision = "⛔ NO GO"
        reason = "VIX Extreme (>30). Wait for volatility crush."
    elif len(danger_headlines) > 0 and TARGET_DTE < 5:
        # Only block 0DTE trades on Fed news. 45 DTE can usually survive it.
        decision = "⚠️ CAUTION"
        reason = "Fed News detected, but 45 DTE timeframe allows room."

    # 5. BUILD REPORT
    msg = (
        f"🦅 **SENTINEL: WEEKLY RUNG ({TARGET_DTE} DTE)**\n"
        f"-----------------------------\n"
        f"🚦 **DECISION: {decision}**\n"
        f"Reason: {reason}\n"
        f"-----------------------------\n"
        f"📉 **MARKET DATA**\n"
        f"SPX: {spx:.2f} | VIX: {vix:.2f}\n"
        f"-----------------------------\n"
        f"🎯 **ENTRY STRIKES (10Δ)**\n"
        f"Call: {call_strike} (+{expected_range:.0f} pts)\n"
        f"Put:  {put_strike} (-{expected_range:.0f} pts)\n"
        f"-----------------------------\n"
        f"🗓️ **EXPIRY TARGET:** ~6 Weeks out\n"
    )
    
    send_alert(msg)

if __name__ == "__main__":
    run_analysis()
