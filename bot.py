import os
import requests
import yfinance as yf
import feedparser

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
MODEL_ID = "gemini-3.5-flash"

# Nifty 100 ਦੇ ਘੱਟ ਕੀਮਤ (Low Price < ₹1000) ਵਾਲੇ ਚੋਟੀ ਦੇ ਸਟਾਕਸ
NIFTY100_LOW_PRICE = [
    "TATAMOTORS.NS", "PNB.NS", "BANKBARODA.NS", "CANBK.NS", "SAIL.NS",
    "ETERNAL.NS", "IRCTC.NS", "POWERGRID.NS", "NTPC.NS", "COALINDIA.NS",
    "BHEL.NS", "ONGC.NS", "GAIL.NS", "IOC.NS", "BPCL.NS",
    "VEDL.NS", "HINDALCO.NS", "TATASTEEL.NS", "JSWSTEEL.NS", "DLF.NS",
    "DABUR.NS", "MARICO.NS", "WIPRO.NS", "TECHM.NS", "BEL.NS",
    "HAL.NS", "JIOFIN.NS", "ADANIPOWER.NS", "NHPC.NS", "PFC.NS",
    "RECLTD.NS", "UNIONBANK.NS", "IDFCFIRSTB.NS", "MOTHERSON.NS"
]

def ask_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_ID}:generateContent?key={GEMINI_API_KEY}"
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
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,binancecoin&vs_currencies=usd&include_24hr_change=true"
        res = requests.get(url, timeout=10).json()
        btc = f"BTC: ${res['bitcoin']['usd']} ({res['bitcoin']['usd_24h_change']:+.2f}%)"
        eth = f"ETH: ${res['ethereum']['usd']} ({res['ethereum']['usd_24h_change']:+.2f}%)"
        bnb = f"BNB: ${res['binancecoin']['usd']} ({res['binancecoin']['usd_24h_change']:+.2f}%)"
        return f"{btc} | {eth} | {bnb}"
    except Exception as e:
        return f"Crypto Data Error: {e}"

def get_global_news():
    try:
        rss_url = "https://news.google.com/rss/search?q=stock+market+economy+FII+DII+inflation&hl=en-IN&gl=IN&ceid=IN:en"
        feed = feedparser.parse(rss_url)
        news_headlines = [f"- {entry.title}" for entry in feed.entries[:6]]
        return "\n".join(news_headlines) if news_headlines else "No major news right now."
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

def scan_top5_low_price_movers():
    movers = []
    for sym in NIFTY100_LOW_PRICE:
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="10d")
            if len(hist) >= 5:
                curr_price = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2]
                
                # ਸਿਰਫ਼ ₹1000 ਤੋਂ ਘੱਟ ਕੀਮਤ ਵਾਲੇ ਸ਼ੇਅਰ ਹੀ ਰੱਖੋ
                if curr_price > 1000:
                    continue
                
                change_pct = ((curr_price - prev_close) / prev_close) * 100
                avg_vol = hist['Volume'].iloc[:-1].mean()
                curr_vol = hist['Volume'].iloc[-1]
                vol_ratio = (curr_vol / avg_vol) if avg_vol > 0 else 1.0
                
                high_5d = hist['High'].iloc[-5:].max()
                low_5d = hist['Low'].iloc[-5:].min()
                
                # ਮੂਵ ਸਕੋਰ: ਵਾਲੀਅਮ ਸਪਾਈਕ + ਕੀਮਤ ਵਿੱਚ ਹਲਚਲ + ਬ੍ਰੇਕਆਊਟ ਨੇੜੇ
                near_breakout = (curr_price >= high_5d * 0.985) or (curr_price <= low_5d * 1.015)
                if vol_ratio >= 1.15 or abs(change_pct) >= 1.2 or near_breakout:
                    score = (vol_ratio * 2) + abs(change_pct) + (1.5 if near_breakout else 0)
                    clean_name = sym.replace(".NS", "")
                    info = f"{clean_name}: ₹{curr_price:.2f} ({change_pct:+.2f}%) | Vol: {vol_ratio:.1f}x | 5D Support: ₹{low_5d:.2f}, Resistance: ₹{high_5d:.2f}"
                    movers.append((score, info))
        except Exception:
            continue
            
    # ਸਭ ਤੋਂ ਵੱਧ ਮੂਵ ਵਾਲੇ Top 5 ਸਟਾਕ ਚੁਣੋ
    movers.sort(key=lambda x: x[0], reverse=True)
    top_5 = [item[1] for item in movers[:5]]
    
    if not top_5:
        return "NO_STRONG_MOVE: ਇਸ ਵੇਲੇ Nifty 100 ਦੇ ਘੱਟ ਕੀਮਤ ਵਾਲੇ ਸ਼ੇਅਰਾਂ ਵਿੱਚ ਕੋਈ ਵੱਡਾ ਬ੍ਰੇਕਆਊਟ ਜਾਂ ਤੇਜ਼ ਮੂਵ ਨਹੀਂ ਦਿਖ ਰਹੀ।"
    return "\n".join(top_5)

def send_telegram_alert(full_message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        chunk_size = 4000
        chunks = [full_message[i : i + chunk_size] for i in range(0, len(full_message), chunk_size)]
        for chunk in chunks:
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": chunk}
            response = requests.post(url, json=payload, timeout=15)
            if response.status_code == 200:
                print("✅ Telegram Alert Sent Successfully!")
            else:
                print(f"❌ Telegram Failed: {response.text}")
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

def analyze_everything():
    print("🤖 AI ਮਾਰਕੀਟ ਅਤੇ Nifty 100 ਦੇ ਘੱਟ ਕੀਮਤ ਵਾਲੇ ਚਾਰਟ ਸਕੈਨ ਕਰ ਰਿਹਾ ਹੈ...")
    crypto_info = get_crypto_prices()
    market_data = get_market_technicals()
    market_news = get_global_news()
    top5_stocks = scan_top5_low_price_movers()

    prompt = f"""
    Act as an elite Institutional Hedge Fund Manager, Global Macro Trader, and Price Action Expert.
    
    REAL-TIME DATA COLLECTED:
    1. Crypto (BTC, ETH, BNB): {crypto_info}
    2. Indices & Commodities (Price, 5D High/Low as Support/Resistance): {market_data}
    3. Nifty 100 Low-Price (<₹1000) High-Move Breakout Scanner (Top 5 Filtered):
    {top5_stocks}
    4. Live Global & Economic News (Triggers, FII/DII Sentiment, Macro Factors):
    {market_news}
    
    Provide a professional, highly detailed, and actionable trading report in PURE PUNJABI (Gurmukhi script) formatted for Telegram. Include the following sections clearly with emojis:
    
    1. 🌐 ਗਲੋਬਲ ਮਾਰਕੀਟ & ਬਿਗ ਪਲੇਅਰ ਫੁੱਟਪ੍ਰਿੰਟ (Smart Money & News Impact):
       - ਦੁਨੀਆ ਭਰ ਦੀਆਂ ਖ਼ਬਰਾਂ ਅਤੇ ਵੱਡੇ ਖਿਡਾਰੀਆਂ (Institutions/FII) ਦਾ ਰੁਝਾਨ ਮਾਰਕੀਟ 'ਤੇ ਕੀ ਅਸਰ ਪਾ ਰਿਹਾ ਹੈ?
       - ਕੀ ਇਹ ਮਾਰਕੀਟ ਬੁੱਲਿਸ਼ ਹੈ, ਬੇਅਰਸ਼ ਹੈ, ਜਾਂ ਟਰੈਪ (Trap Zone) ਹੈ?
    
    2. 📊 ਇੰਡੈਕਸ, ਕ੍ਰਿਪਟੋ ਅਤੇ ਕਮੋਡਿਟੀਜ਼ (Nifty, BankNifty, Gold, Silver, Crypto):
       - ਹਰ ਇੱਕ ਲਈ ਸਾਫ਼-ਸਾਫ਼ ਲਿਖੋ: Action (BUY / SELL / WAIT), Entry Point, Stop-Loss (SL), ਅਤੇ Target.
       - ਸਪੋਰਟ (Support) ਅਤੇ ਰਜ਼ਿਸਟੈਂਸ (Resistance) ਦੇ ਆਧਾਰ 'ਤੇ ਲੈਵਲ ਦੱਸੋ।
    
    3. 🎯 ਰਿਟੇਲਰ ਟਰੈਪ ਤੋਂ ਬਚਣ ਦੀ ਸਲਾਹ (Retailer vs Smart Money):
       - ਆਮ ਲੋਕ ਕਿੱਥੇ ਫਸ ਰਹੇ ਹਨ ਅਤੇ ਅਸਲੀ ਮੂਵ ਕਿੱਥੇ ਆ ਸਕਦੀ ਹੈ?
    
    4. 🚀 Nifty 100 Top 5 ਲੋਅ-ਪ੍ਰਾਈਸ ਮੂਵਰ ਸਟਾਕਸ (Breakout & Volume Alert):
       - ਜੇਕਰ ਡੇਟਾ ਵਿੱਚ 'NO_STRONG_MOVE' ਲਿਖਿਆ ਹੈ, ਤਾਂ ਸਾਫ਼ ਲਿਖੋ ਕਿ "ਇਸ ਵੇਲੇ ਕਿਸੇ ਵੀ ਘੱਟ ਕੀਮਤ ਵਾਲੇ ਸ਼ੇਅਰ ਵਿੱਚ ਵੱਡੀ ਮੂਵ ਜਾਂ ਬ੍ਰੇਕਆਊਟ ਨਹੀਂ ਬਣ ਰਿਹਾ, ਇਸ ਲਈ ਉਡੀਕ (WAIT) ਕਰੋ।"
       - ਜੇਕਰ ਸਟਾਕਸ ਦਿੱਤੇ ਗਏ ਹਨ, ਤਾਂ ਸਿਰਫ਼ ਉਨ੍ਹਾਂ 5 ਸਟਾਕਸ ਦਾ ਹੀ ਵਿਸ਼ਲੇਸ਼ਣ ਕਰੋ ਅਤੇ ਹਰ ਇੱਕ ਲਈ ਸਾਫ਼ ਲਿਖੋ:
         * ਦਿਸ਼ਾ (BUY - ਉੱਪਰ ਵੱਲ / SELL - ਹੇਠਾਂ ਵੱਲ) ਅਤੇ ਕਾਰਨ (ਵਾਲੀਅਮ/ਬ੍ਰੇਕਆਊਟ)
         * ਸਹੀ Entry Point (₹)
         * Stop-Loss (SL) (₹)
         * Target 1 ਅਤੇ Target 2 (₹)
    
    Keep it structured, punchy, professional, and easy to read on mobile. Avoid using markdown asterisks (*) or underscores (_) that might break Telegram formatting.
    """

    analysis_text = ask_gemini(prompt)
    send_telegram_alert("🚀 PRO AI TRADING & SMART MONEY REPORT\n\n" + analysis_text)

if __name__ == "__main__":
    analyze_everything()
