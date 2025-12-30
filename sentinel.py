import yfinance as yf
import requests
import math
import os
from datetime import datetime, timedelta

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ⚙️ STRATEGY SETTINGS
TARGET_DTE = 45  # Target days to expiration
SAFETY_FACTOR = 1.0  # 1.0 = ~15 Delta (Aggressive), 1.3 = ~10 Delta (Safe)

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

    # 3. CALCULATE STRIKES (15 Delta Logic)
    time_factor = math.sqrt(TARGET_DTE / 365)
    expected_range = spx * (vix/100) * time_factor * SAFETY_FACTOR
    
    call_strike = 5 * round((spx + expected_range) / 5)
    put_strike = 5 * round((spx - expected_range) / 5)

    # 4. CALCULATE EXACT EXPIRY DATE
    # Add 45 days to today
    future_date = datetime.now() + timedelta(days=TARGET_DTE)
    # Find the Friday of that week (0=Mon, 4=Fri)
    # We calculate the difference between Friday (4) and the future_date's weekday
    days_to_friday = (4 - future_date.weekday())
    expiry_date = future_date + timedelta(days=days_to_friday)
    
    # Format: "13 Feb 2026 (Friday)"
    formatted_expiry = expiry_date.strftime("%d %b %Y (%A)")

    # 5. DECISION LOGIC
    decision = "✅ GO"
    reason = "Conditions Optimal"
    
    if vix < 11.0:
        decision = "⛔ NO GO"
        reason = "VIX too low (<11). Not enough premium."
    elif vix > 30:
        decision = "⛔ NO GO"
        reason = "VIX Extreme (>30). Wait for volatility crush."
    elif len(danger_headlines) > 0:
        decision = "⚠️ CAUTION"
        reason = "Fed News detected. Check calendar."

    # 6. BUILD REPORT
    msg = (
        f"🦅 **SENTINEL: 15 DELTA ({TARGET_DTE} DTE)**\n"
        f"-----------------------------\n"
        f"🚦 **DECISION: {decision}**\n"
        f"Reason: {reason}\n"
        f"-----------------------------\n"
        f"📉 **MARKET DATA**\n"
        f"SPX: {spx:.2f} | VIX: {vix:.2f}\n"
        f"-----------------------------\n"
        f"🎯 **ENTRY STRIKES (15Δ)**\n"
        f"Call: {call_strike} (+{expected_range:.0f} pts)\n"
        f"Put:  {put_strike} (-{expected_range:.0f} pts)\n"
        f"-----------------------------\n"
        f"🗓️ **EXPIRY TARGET:**\n"
        f"👉 {formatted_expiry}\n"
    )
    
    send_alert(msg)

if __name__ == "__main__":
    run_analysis()
