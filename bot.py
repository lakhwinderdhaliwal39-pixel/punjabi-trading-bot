import os
import requests
import yfinance as yf
import feedparser

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
MODEL_ID = "gemini-3.8-flash"

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
        "SILVER (MCX Ref)": "SI=F",
        "ICICI BANK": "ICICIBANK.NS",
        "SBI": "SBIN.NS",
        "RELIANCE": "RELIANCE.NS"
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
    print("🤖 AI ਮਾਰਕੀਟ ਦਾ ਡਾਟਾ ਪੜ੍ਹ ਰਿਹਾ ਹੈ...")
    crypto_info = get_crypto_prices()
    market_data = get_market_technicals()
    market_news = get_global_news()

    prompt = f"""
    Act as an elite Institutional Hedge Fund Manager, Global Macro Trader, and Price Action Expert.
    
    REAL-TIME DATA COLLECTED:
    1. Crypto (BTC, ETH, BNB): {crypto_info}
    2. Indian Market, Indices & Key Stocks (Price, 5D High/Low as Support/Resistance): {market_data}
    3. Live Global & Economic News (Triggers, FII/DII Sentiment, Macro Factors):
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
    
    4. 🚀 ਸਭ ਤੋਂ ਵਧੀਆ ਸਟਾਕਸ (Intraday & Swing Trade Setup):
       - ਉਪਰੋਕਤ ਲਿਸਟ ਵਿੱਚੋਂ ਚੁਣੋ।
       - ਸਹੀ Entry, Stop-Loss (SL), ਅਤੇ Targets ₹ ਵਿੱਚ ਸਾਫ਼-ਸਾਫ਼ ਲਿਖੋ।
    
    Keep it structured, punchy, professional, and easy to read on mobile. Avoid using markdown asterisks (*) or underscores (_) that might break Telegram formatting.
    """

    analysis_text = ask_gemini(prompt)
    send_telegram_alert("🚀 PRO AI TRADING & SMART MONEY REPORT\n\n" + analysis_text)

if __name__ == "__main__":
    analyze_everything()
