import os
import requests
import yfinance as yf
import feedparser

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# ਸਹੀ ਮਾਡਲ ਨਾਮ (gemini-2.5-flash)
MODEL_ID = "gemini-2.5-flash"

# Nifty 100 ਦੇ ਘੱਟ ਕੀਮਤ (Low Price < ₹1000) ਵਾਲੇ ਚੋਟੀ ਦੇ ਸਟਾਕਸ
NIFTY100_LOW_PRICE = [
    "PNB.NS", "BANKBARODA.NS", "CANBK.NS", "SAIL.NS", "ETERNAL.NS",
    "IRCTC.NS", "POWERGRID.NS", "NTPC.NS", "COALINDIA.NS", "BHEL.NS",
    "ONGC.NS", "GAIL.NS", "IOC.NS", "BPCL.NS", "VEDL.NS",
    "HINDALCO.NS", "TATASTEEL.NS", "JSWSTEEL.NS", "DLF.NS", "DABUR.NS",
    "MARICO.NS", "WIPRO.NS", "TECHM.NS", "BEL.NS", "HAL.NS",
    "JIOFIN.NS", "ADANIPOWER.NS", "NHPC.NS", "PFC.NS", "RECLTD.NS",
    "UNIONBANK.NS", "IDFCFIRSTB.NS", "MOTHERSON.NS"
]

def ask_gemini(prompt):
    if not GEMINI_API_KEY:
        return "Error: GEMINI_API_KEY ਸੈੱਟ ਨਹੀਂ ਕੀਤੀ ਗਈ।"
    
    url = f"https://googleapis.com{MODEL_ID}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=120)
        res_json = response.json()
        if 'candidates' in res_json and len(res_json['candidates']) > 0:
            candidate = res_json['candidates'][0]
            if 'content' in candidate and 'parts' in candidate['content']:
                return candidate['content']['parts'][0]['text']
        return f"Gemini API Raw Response: {res_json}"
    except Exception as e:
        return f"Gemini API Error: {e}"

def get_crypto_prices():
    try:
        # ਸਹੀ URL (ਪਹਿਲਾਂ https://:// ਸੀ)
        url = "https://coingecko.com"
        res = requests.get(url, timeout=10).json()
        btc = f"BTC: ${res['bitcoin']['usd']} ({res['bitcoin']['usd_24h_change']:+.2f}%)"
        eth = f"ETH: ${res['ethereum']['usd']} ({res['ethereum']['usd_24h_change']:+.2f}%)"
        bnb = f"BNB: ${res['binancecoin']['usd']} ({res['binancecoin']['usd_24h_change']:+.2f}%)"
        return f"{btc} | {eth} | {bnb}"
    except Exception as e:
        return f"Crypto Data Error: {e}"

def get_global_and_stock_news():
    headlines = []
    try:
        # ਸਹੀ Google News RSS URLs
        rss_macro = "https://google.com"
        feed1 = feedparser.parse(rss_macro)
        for entry in feed1.entries[:4]:
            headlines.append(f"- [Macro] {entry.title}")

        rss_stocks = "https://google.com"
        feed2 = feedparser.parse(rss_stocks)
        for entry in feed2.entries[:5]:
            headlines.append(f"- [Stock News] {entry.title}")

        return "\n".join(headlines) if headlines else "No major breaking news right now."
    except Exception as e:
        return f"News Fetch Error: {e}"

def get_market_technicals():
    symbols = {
        "NIFTY 50": "^NSEI",
        "BANK NIFTY": "^NSEBANK",
        "GOLD (MCX Ref)": "GC=F",
        "SILVER (MCX Ref)": "SI=F"
    }
    report = []
    for name, sym in symbols.items():
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="5d")
            if len(hist) >= 2:
                curr_price = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2]
                change_pct = ((curr_price - prev_close) / prev_close) * 100
                high_5d = hist['High'].max()
                low_5d = hist['Low'].min()
                unit = "$" if "=F" in sym else "₹"
                report.append(f"{name}: {unit}{curr_price:.2f} ({change_pct:+.2f}%) [5D High: {unit}{high_5d:.2f}, Low: {unit}{low_5d:.2f}]")
        except Exception:
            continue
    return " | ".join(report) if report else "Market data unavailable"

def scan_top5_intraday_and_swing():
    movers = []
    try:
        data = yf.download(NIFTY100_LOW_PRICE, period="15d", group_by="ticker", progress=False, threads=True)
        for sym in NIFTY100_LOW_PRICE:
            try:
                if sym not in data.columns.levels[0]:
                    continue
                hist = data[sym].dropna()
                if len(hist) >= 10:
                    curr_price = float(hist['Close'].iloc[-1])
                    prev_close = float(hist['Close'].iloc[-2])
                    open_price = float(hist['Open'].iloc[-1])

                    if curr_price > 1000 or open_price == 0 or prev_close == 0:
                        continue

                    day_change_pct = ((curr_price - prev_close) / prev_close) * 100
                    intraday_move_pct = ((curr_price - open_price) / open_price) * 100

                    avg_vol = float(hist['Volume'].iloc[:-1].mean())
                    curr_vol = float(hist['Volume'].iloc[-1])
                    vol_ratio = (curr_vol / avg_vol) if avg_vol > 0 else 1.0

                    high_5d = float(hist['High'].iloc[-5:].max())
                    low_5d = float(hist['Low'].iloc[-5:].min())
                    high_15d = float(hist['High'].max())
                    low_15d = float(hist['Low'].min())

                    is_intraday = (vol_ratio >= 1.25) or (abs(intraday_move_pct) >= 1.0)
                    is_swing = (curr_price >= high_15d * 0.985) or (curr_price <= low_15d * 1.015)

                    if is_intraday or is_swing or abs(day_change_pct) >= 1.2:
                        score = (vol_ratio * 2) + abs(day_change_pct) + (1.5 if is_swing else 0)
                        clean_name = sym.replace(".NS", "")
                        tag = "BOTH (Intraday & Swing)" if (is_intraday and is_swing) else ("SWING" if is_swing else "INTRADAY")
                        info = (
                            f"{clean_name} [{tag}]: Price ₹{curr_price:.2f} (Day: {day_change_pct:+.2f}%, Open-to-Now: {intraday_move_pct:+.2f}%) | "
                            f"Vol: {vol_ratio:.1f}x | 5D Range: ₹{low_5d:.2f}-₹{high_5d:.2f} | 15D Range: ₹{low_15d:.2f}-₹{high_15d:.2f}"
                        )
                        movers.append((score, info))
            except Exception:
                continue
    except Exception:
        pass

    movers.sort(key=lambda x: x[0], reverse=True)
    top_5 = [info for score, info in movers[:5]]

    if not top_5:
        return "NO_STRONG_MOVE: ਇਸ ਵੇਲੇ Nifty 100 ਦੇ ਘੱਟ ਕੀਮਤ ਵਾਲੇ ਸ਼ੇਅਰਾਂ ਵਿੱਚ ਕੋਈ ਵੱਡਾ Intraday ਜਾਂ Swing ਬ੍ਰੇਕਆਊਟ ਨਹੀਂ ਬਣ ਰਿਹਾ।"
    return "\n".join(top_5)

def send_telegram_alert(full_message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram credentials missing!")
        print(full_message)
        return

    url = f"https://telegram.org{TELEGRAM_BOT_TOKEN}/sendMessage"
    chunk_size = 4000
    chunks = [full_message[i : i + chunk_size] for i in range(0, len(full_message), chunk_size)]

    for chunk in chunks:
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": chunk}
        try:
            response = requests.post(url, json=payload, timeout=15)
            if response.status_code == 200:
                print("✅ Telegram Alert Sent Successfully!")
            else:
                print(f"❌ Telegram Failed: {response.text}")
        except Exception as e:
            print(f"Error sending Telegram message: {e}")

def analyze_everything():
    print("🤖 AI ਮਾਰਕੀਟ, Breaking News, Intraday ਅਤੇ Swing ਸਟਾਕਸ ਸਕੈਨ ਕਰ ਰਿਹਾ ਹੈ...")
    crypto_info = get_crypto_prices()
    market_data = get_market_technicals()
    market_news = get_global_and_stock_news()
    top5_stocks = scan_top5_intraday_and_swing()

    prompt = f"""
    Act as an elite Institutional Hedge Fund Manager, Global Macro Trader, and Price Action Expert.

    REAL-TIME DATA COLLECTED:
    1. Crypto (BTC, ETH, BNB): {crypto_info}
    2. Indices & Commodities (Price, 5D High/Low as Support/Resistance): {market_data}
    3. Nifty 100 Low-Price (<₹1000) Top 5 Live Movers (Tagged with INTRADAY / SWING): {top5_stocks}
    4. Live Global Macro & Breaking Corporate/Stock News: {market_news}

    Provide a professional, highly detailed, and actionable trading report in PURE PUNJABI (Gurmukhi script) formatted for Telegram.
    Include the following sections clearly with emojis:

    1. 🌐 ਗਲੋਬਲ ਮਾਰਕੀਟ, ਤਾਜ਼ਾ ਖ਼ਬਰਾਂ & ਸਮਾਰਟ ਮਨੀ (Breaking News & FII Impact):
    - ਦੁਨੀਆ ਭਰ ਦੀਆਂ ਖ਼ਬਰਾਂ, ਵੱਡੇ ਖਿਡਾਰੀਆਂ (FII/DII) ਦਾ ਰੁਝਾਨ ਅਤੇ ਜੇਕਰ ਕਿਸੇ ਸਟਾਕ ਬਾਰੇ ਕੋਈ ਤਾਜ਼ਾ ਬ੍ਰੇਕਿੰਗ ਖ਼ਬਰ ਆਈ ਹੈ ਤਾਂ ਉਸਦਾ ਅਸਰ ਦੱਸੋ।
    - ਕੀ ਮਾਰਕੀਟ ਬੁੱਲਿਸ਼ ਹੈ, ਬੇਅਰਸ਼ ਹੈ, ਜਾਂ ਟਰੈਪ ਜ਼ੋਨ (Trap Zone) ਹੈ?

    2. 📊 ਇੰਡੈਕਸ, ਕ੍ਰਿਪਟੋ ਅਤੇ ਕਮੋਡਿਟੀਜ਼ (Nifty, BankNifty, Gold, Silver, Crypto):
    - ਹਰ ਇੱਕ ਲਈ ਸਾਫ਼-ਸਾਫ਼ ਲਿਖੋ: Action (BUY / SELL / WAIT), Entry Point, Stop-Loss (SL), ਅਤੇ Target.
    - ਸਪੋਰਟ (Support) ਅਤੇ ਰਜ਼ਿਸਟੈਂਸ (Resistance) ਦੇ ਆਧਾਰ 'ਤੇ ਲੈਵਲ ਦੱਸੋ।

    3. 🎯 ਰਿਟੇਲਰ ਟਰੈਪ ਤੋਂ ਬਚਣ ਦੀ ਸਲਾਹ (Retailer vs Smart Money):
    - ਆਮ ਲੋਕ ਕਿੱਥੇ ਫਸ ਰਹੇ ਹਨ ਅਤੇ ਅਸਲੀ ਮੂਵ ਕਿੱਥੇ ਆ ਸਕਦੀ ਹੈ?

    4. 🚀 Nifty 100 Top 5 ਲੋਅ-ਪ੍ਰਾਈਸ ਸਟਾਕਸ (Intraday ਅਤੇ Swing Trade ਵੱਖ-ਵੱਖ):
    - ਜੇਕਰ ਡੇਟਾ ਵਿੱਚ 'NO_STRONG_MOVE' ਲਿਖਿਆ ਹੈ, ਤਾਂ ਸਾਫ਼ ਲਿਖੋ ਕਿ "ਇਸ ਵੇਲੇ ਕਿਸੇ ਵੀ ਸਟਾਕ ਵਿੱਚ ਵੱਡਾ Intraday ਜਾਂ Swing ਸੈੱਟਅੱਪ ਨਹੀਂ ਬਣ ਰਿਹਾ, ਇਸ ਲਈ ਉਡੀਕ (WAIT) ਕਰੋ।"
    - ਜੇਕਰ ਸਟਾਕਸ ਦਿੱਤੇ ਗਏ ਹਨ, ਤਾਂ ਇਨ੍ਹਾਂ 5 ਸਟਾਕਸ ਨੂੰ ਦੋ ਵੱਖ-ਵੱਖ ਹਿੱਸਿਆਂ ਵਿੱਚ ਵੰਡ ਕੇ ਲਿਖੋ:
      • ⚡ [ਅੱਜ ਦੇ INTRADAY ਲਈ Best ਸਟਾਕਸ] (ਸਿਰਫ਼ ਅੱਜ 3:15 PM ਤੱਕ ਲਈ)
      • 🌊 [SWING TRADE ਲਈ Best ਸਟਾਕਸ] (2 ਤੋਂ 7 ਦਿਨਾਂ ਦੇ ਹੋਲਡ ਲਈ)
    - ਹਰ ਸਟਾਕ ਲਈ ਸਾਫ਼ ਲਿਖੋ:
      • ਦਿਸ਼ਾ (BUY - ਉੱਪਰ ਵੱਲ / SELL - ਹੇਠਾਂ ਵੱਲ) ਅਤੇ ਕਾਰਨ (ਵਾਲੀਅਮ/ਬ੍ਰੇਕਆਊਟ/ਖ਼ਬਰ)
      • ਸਹੀ Entry Point (₹)
      • Stop-Loss (SL) (₹)
      • Target 1 ਅਤੇ Target 2 (₹)

