import yfinance as yf
import requests
import math
import os

# --- CONFIGURATION (Loaded from GitHub Secrets) ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_alert(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ Error: Missing GitHub Secrets (TELEGRAM_TOKEN or CHAT_ID)")
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID, 
        "text": message, 
        "parse_mode": "Markdown",
        "disable_web_page_preview": True 
    }
    requests.post(url, json=payload)

def run_analysis():
    print("--- Sentinel Cloud Agent Starting ---")
    
    # 1. FETCH DATA (With Fallback)
    try:
        # Try Index first
        tickers = yf.Tickers("^GSPC ^VIX")
        spx = tickers.tickers['^GSPC'].history(period="1d")['Close'].iloc[-1]
        vix = tickers.tickers['^VIX'].history(period="1d")['Close'].iloc[-1]
    except:
        print("⚠️ Index data failed. Switching to SPY/VIXY fallback.")
        spy = yf.Ticker("SPY").history(period="1d")['Close'].iloc[-1]
        spx = spy * 10  # Approx SPX
        vix = 15.0      # Safety Default
    
    # 2. SCAN NEWS (The "Event Risk" Check)
    spy = yf.Ticker("SPY")
    news_items = spy.news
    fed_keywords = ["FED ", "POWELL", "FOMC", "CPI", "INFLATION", "PPI", "RATE HIKE"]
    
    danger_headlines = []
    for item in news_items[:8]:
        title = item.get('title', '').upper()
        if any(key in title for key in fed_keywords):
            danger_headlines.append(f"• {item.get('title')}")

    # 3. MODULE 4: THE DECISION ENGINE (Go/No-Go)
    decision = "✅ GO"
    reason = "Conditions Optimal"
    strategy = "Standard Iron Condor (10 Delta)"
    
    # Rule A: Event Risk
    if len(danger_headlines) > 0:
        decision = "⛔ NO GO"
        reason = "High Impact News Detected (Fed/CPI)"
        strategy = "Sit on hands. Wait for event to pass."
        
    # Rule B: Gamma Risk (VIX too low)
    elif vix < 11.5:
        decision = "⛔ NO GO"
        reason = "VIX too low (<11.5). Premiums not worth the Gamma risk."
        strategy = "Debit Spreads or No Trade."

    # Rule C: Crash Risk (VIX too high)
    elif vix > 28:
        decision = "⛔ NO GO"
        reason = "VIX Extreme (>28). Market unstable."
        strategy = "Wait for VIX crush."
        
    # Rule D: High Volatility (Wide Wings)
    elif 20 <= vix <= 28:
        decision = "⚠️ CAUTION"
        reason = "Elevated Volatility."
        strategy = "Iron Condor with WIDER wings (5 Delta)."

    # 4. CALCULATE STRIKES (10 Delta)
    # Math: Price * (VIX/100) * sqrt(1/365) * 1.3 (1.3 Std Dev)
    expected_move = spx * (vix/100) * math.sqrt(1/365) * 1.3
    call_strike = 5 * round((spx + expected_move) / 5)
    put_strike = 5 * round((spx - expected_move) / 5)

    # 5. BUILD REPORT
    msg = (
        f"🦅 **SENTINEL CLOUD AGENT**\n"
        f"-----------------------------\n"
        f"🚦 **DECISION: {decision}**\n"
        f"Reason: {reason}\n"
        f"Plan: {strategy}\n"
        f"-----------------------------\n"
        f"📉 **MARKET DATA**\n"
        f"SPX: {spx:.2f} | VIX: {vix:.2f}\n"
        f"-----------------------------\n"
        f"🎯 **STRIKES (If Trading)**\n"
        f"Call: {call_strike} | Put: {put_strike}\n"
        f"-----------------------------\n"
        f"🗞️ **RISK SCAN**\n"
        f"{chr(10).join(danger_headlines) if danger_headlines else '• No immediate Fed/CPI threats.'}"
    )
    
    send_alert(msg)
    print("Report Sent.")

if __name__ == "__main__":
    run_analysis()
