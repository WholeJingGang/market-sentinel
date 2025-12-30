import yfinance as yf
import requests
import math
import os
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ⚙️ STRATEGY SETTINGS
TARGET_DTE = 45      # Weekly Rung Strategy
SAFETY_FACTOR = 1.0  # 15 Delta

# 🗓️ 2026 MARKET HOLIDAYS (Hardcoded for Safety)
NYSE_HOLIDAYS = [
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", 
    "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07", 
    "2026-11-26", "2026-12-25"
]

def send_alert(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ Error: Missing GitHub Secrets")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    requests.post(url, json=payload)

def run_analysis():
    print("--- Sentinel Cloud Agent Starting ---")
    
    # 1. FETCH DATA (Extended for SMA)
    try:
        tickers = yf.Tickers("^GSPC ^VIX")
        # We need 1 year of history to calculate the 200 SMA
        spx_hist = tickers.tickers['^GSPC'].history(period="2y") # Fetch 2y to be safe
        vix_hist = tickers.tickers['^VIX'].history(period="5d")
        
        spx = spx_hist['Close'].iloc[-1]
        vix = vix_hist['Close'].iloc[-1]
        
        # Calculate 200-Day SMA
        sma_200 = spx_hist['Close'].rolling(window=200).mean().iloc[-1]
    except:
        print("⚠️ Index data failed. Switching to SPY fallback.")
        spy = yf.Ticker("SPY").history(period="2y")
        spx = spy['Close'].iloc[-1] * 10
        sma_200 = spy['Close'].rolling(window=200).mean().iloc[-1] * 10
        vix = 15.0

    # 2. AUTOMATED CHECKS (Phase 1)
    # Trend Check
    if spx > sma_200:
        trend_status = "BULLISH 🟢 (Safe for Puts)"
    else:
        trend_status = "BEARISH 🔴 (Careful with Puts)"
        
    # Holiday Check
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    if tomorrow in NYSE_HOLIDAYS:
        market_status = "CLOSED TOMORROW ⛔"
    else:
        market_status = "OPEN TOMORROW ✅"

    # 3. SCAN NEWS
    spy = yf.Ticker("SPY")
    news_items = spy.news
    fed_keywords = ["FED ", "POWELL", "FOMC", "CPI", "INFLATION", "PPI", "RATE HIKE"]
    danger_headlines = []
    
    for item in news_items[:8]:
        title = item.get('title', '').upper()
        if any(key in title for key in fed_keywords):
            danger_headlines.append(f"• {item.get('title')}")

    # 4. CALCULATE STRIKES
    time_factor = math.sqrt(TARGET_DTE / 365)
    expected_range = spx * (vix/100) * time_factor * SAFETY_FACTOR
    
    call_strike = 5 * round((spx + expected_range) / 5)
    put_strike = 5 * round((spx - expected_range) / 5)

    # 5. EXPIRY DATE
    future_date = datetime.now() + timedelta(days=TARGET_DTE)
    days_to_friday = (4 - future_date.weekday())
    expiry_date = future_date + timedelta(days=days_to_friday)
    formatted_expiry = expiry_date.strftime("%d %b %Y (%A)")

    # 6. DECISION LOGIC
    decision = "✅ GO"
    reason = "Conditions Optimal"
    
    if vix < 11.0:
        decision = "⛔ NO GO"
        reason = "VIX too low (<11). Premium cheap."
    elif vix > 30:
        decision = "⛔ NO GO"
        reason = "VIX Extreme (>30). Wait."
    elif len(danger_headlines) > 0:
        decision = "⚠️ CAUTION"
        reason = "Fed News detected."
    elif spx < sma_200:
        decision = "⚠️ CAUTION"
        reason = "Market in Downtrend (<200 SMA)."

    # 7. BUILD REPORT
    msg = (
        f"🦅 **SENTINEL: FULL AUTO ({TARGET_DTE} DTE)**\n"
        f"-----------------------------\n"
        f"🚦 **DECISION: {decision}**\n"
        f"Reason: {reason}\n"
        f"-----------------------------\n"
        f"🤖 **PHASE 1: AUTO-CHECKS**\n"
        f"📈 **Trend (200 SMA):**\n"
        f"👉 {trend_status}\n"
        f"🗓️ **Holiday Check:**\n"
        f"👉 {market_status}\n"
        f"-----------------------------\n"
        f"📉 **MARKET DATA**\n"
        f"SPX: {spx:.2f} | SMA: {sma_200:.0f}\n"
        f"VIX: {vix:.2f}\n"
        f"-----------------------------\n"
        f"🎯 **ENTRY STRIKES (15Δ)**\n"
        f"Call: {call_strike} (+{expected_range:.0f} pts)\n"
        f"Put:  {put_strike} (-{expected_range:.0f} pts)\n"
        f"-----------------------------\n"
        f"🗓️ **EXPIRY TARGET:**\n"
        f"👉 {formatted_expiry}\n"
        f"-----------------------------\n"
        f"🗞️ **RISK SCAN**\n"
        f"{chr(10).join(danger_headlines) if danger_headlines else '• No immediate Fed/CPI threats.'}"
    )
    
    send_alert(msg)

if __name__ == "__main__":
    run_analysis()
