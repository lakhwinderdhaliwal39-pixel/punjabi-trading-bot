import os
import time
import requests
import yfinance as yf
import feedparser
from datetime import datetime
import pytz
from google import genai
from google.genai.errors import APIError
from fyers_apiv3 import fyersModel

# ==========================================
# 1. API KEYS & CONFIGURATION (GitHub Secrets / Env)
# ==========================================
GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or "").strip()
FYERS_CLIENT_ID = (os.environ.get("FYERS_CLIENT_ID") or "").strip()
FYERS_ACCESS_TOKEN = (os.environ.get("FYERS_ACCESS_TOKEN") or "").strip()
TELEGRAM_BOT_TOKEN = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
TELEGRAM_CHAT_ID = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()

client = genai.Client(api_key=GEMINI_API_KEY)
fyers = fyersModel.FyersModel(client_id=FYERS_CLIENT_ID, token=FYERS_ACCESS_TOKEN, log_path="")

# ਪੁਰਾਣੇ ਕੋਡ ਵਾਲੇ 33 Nifty 100 ਸਟਾਕ
NIFTY100_LOW_PRICE = [
    "PNB.NS", "BANKBARODA.NS", "CANBK.NS", "SAIL.NS", "ETERNAL.NS",
    "IRCTC.NS", "POWERGRID.NS", "NTPC.NS", "COALINDIA.NS", "BHEL.NS",
    "ONGC.NS", "GAIL.NS", "IOC.NS", "BPCL.NS", "VEDL.NS",
    "HINDALCO.NS", "TATASTEEL.NS", "JSWSTEEL.NS", "DLF.NS", "DABUR.NS",
    "MARICO.NS", "WIPRO.NS", "TECHM.NS", "BEL.NS", "HAL.NS",
    "JIOFIN.NS", "ADANIPOWER.NS", "NHPC.NS", "PFC.NS", "RECLTD.NS",
    "UNIONBANK.NS", "IDFCFIRSTB.NS", "MOTHERSON.NS"
]

# ==========================================
# 2. LIVE MARKET STATUS (IST TIMEZONE CHECK)
# ==========================================
def get_live_market_status():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    weekday = now.weekday()
    current_minutes = now.hour * 60 + now.minute

    is_weekday = weekday < 5
    nse_live = is_weekday and (555 <= current_minutes <= 930)   # 9:15 AM - 3:30 PM
    mcx_live = is_weekday and (540 <= current_minutes <= 1410)  # 9:00 AM - 11:30 PM
    crypto_live = True

    return now.strftime("%d-%b-%Y %I:%M %p IST"), nse_live, mcx_live, crypto_live

# ==========================================
# 3. 100% LIVE CRYPTO DATA (Binance API)
# ==========================================
def get_live_crypto():
    coins = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "BNB": "BNBUSDT", "SOL": "SOLUSDT"}
    report = []
    for name, symbol in coins.items():
        try:
            url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
            res = requests.get(url, timeout=8).json()
            price = float(res["lastPrice"])
            high = float(res["highPrice"])
            low = float(res["lowPrice"])
            chg = float(res["priceChangePercent"])
            vol_m = float(res["quoteVolume"]) / 1e6
            report.append(f"{name}: ${price:.2f} ({chg:+.2f}% | High: ${high:.2f}, Low: ${low:.2f} | Vol: ${vol_m:.1f}M)")
        except Exception as e:
            report.append(f"{name}: Error ({e})")
    return " | ".join(report)

# ==========================================
# 4. 100% LIVE INDICES & MCX (Fyers + YFinance Fallback)
# ==========================================
def get_live_indices_and_mcx(nse_live, mcx_live):
    if not nse_live and not mcx_live:
        return ""

    # ਪਹਿਲਾਂ Fyers ਤੋਂ 100% ਲਾਈਵ ਰੇਟ ਲੈਣ ਦੀ ਕੋਸ਼ਿਸ਼
    fyers_symbols = []
    if nse_live:
        fyers_symbols.extend(["NSE:NIFTY50-INDEX", "NSE:NIFTYBANK-INDEX"])
    if mcx_live:
        # ਨੋਟ: ਮੌਜੂਦਾ MCX ਐਕਸਪਾਇਰੀ ਮਹੀਨਾ ਚੈੱਕ ਰੱਖੋ (ਜਿਵੇਂ 26DECFUT)
        fyers_symbols.extend(["MCX:GOLD26DECFUT", "MCX:SILVER26DECFUT"])

    if FYERS_CLIENT_ID and FYERS_ACCESS_TOKEN and fyers_symbols:
        try:
            res = fyers.quotes(data={"symbols": ",".join(fyers_symbols)})
            if res.get("s") == "ok":
                report = []
                for item in res["d"]:
                    sym = item["n"]
                    v = item["v"]
                    ltp = v.get("lp", 0)
                    chg = v.get("chp", 0)
                    high = v.get("high_price", 0)
                    low = v.get("low_price", 0)
                    report.append(f"{sym}: ₹{ltp} ({chg:+.2f}% | H: ₹{high}, L: ₹{low})")
                if report:
                    return " | ".join(report)
        except Exception as e:
            print("Fyers Fallback triggered:", e)

    # ਜੇਕਰ Fyers ਟੋਕਨ ਐਕਸਪਾਇਰ ਹੋਵੇ ਤਾਂ YFinance ਬੈਕਅੱਪ
    yf_symbols = {}
    if nse_live:
        yf_symbols["NIFTY 50"] = "^NSEI"
        yf_symbols["BANK NIFTY"] = "^NSEBANK"
    if mcx_live:
        yf_symbols["GOLD (Global Ref)"] = "GC=F"
        yf_symbols["SILVER (Global Ref)"] = "SI=F"

    report = []
    for name, sym in yf_symbols.items():
        try:
            hist = yf.Ticker(sym).history(period="5d")
            if len(hist) >= 2:
                curr = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                chg = ((curr - prev) / prev) * 100
                unit = "$" if "=F" in sym else "₹"
                report.append(f"{name}: {unit}{curr:.2f} ({chg:+.2f}%)")
        except Exception:
            continue
    return " | ".join(report)

# ==========================================
# 5. SMART MONEY SCANNER & FAKE TRAP DETECTOR (33 Stocks)
# ==========================================
def scan_top5_smart_money_only():
    intraday_movers = []
    fake_traps_detected = []

    try:
        data = yf.download(NIFTY100_LOW_PRICE, period="10d", group_by="ticker", progress=False, threads=True)
        for sym in NIFTY100_LOW_PRICE:
            try:
                if sym not in data.columns.levels[0]:
                    continue
                hist = data[sym].dropna()
                if len(hist) >= 8:
                    curr_price = float(hist['Close'].iloc[-1])
                    prev_close = float(hist['Close'].iloc[-2])
                    open_price = float(hist['Open'].iloc[-1])
                    day_high = float(hist['High'].iloc[-1])
                    day_low = float(hist['Low'].iloc[-1])

                    if curr_price > 1000 or open_price == 0 or prev_close == 0:
                        continue

                    day_change_pct = ((curr_price - prev_close) / prev_close) * 100
                    avg_vol = float(hist['Volume'].iloc[:-1].mean())
                    curr_vol = float(hist['Volume'].iloc[-1])
                    vol_ratio = (curr_vol / avg_vol) if avg_vol > 0 else 1.0

                    clean_name = sym.replace(".NS", "")
                    day_range = day_high - day_low
                    upper_wick_ratio = ((day_high - curr_price) / day_range) if day_range > 0 else 0
                    lower_wick_ratio = ((curr_price - day_low) / day_range) if day_range > 0 else 0

                    if day_change_pct > 1.0 and (vol_ratio < 1.1 or upper_wick_ratio > 0.55):
                        fake_traps_detected.append(f"{clean_name} (Fake Bullish)")
                        continue

                    if day_change_pct < -1.0 and (vol_ratio < 1.1 or lower_wick_ratio > 0.55):
                        fake_traps_detected.append(f"{clean_name} (Fake Bearish)")
                        continue

                    info = f"{clean_name}: ₹{curr_price:.2f} ({day_change_pct:+.2f}%, Vol: {vol_ratio:.1f}x, H: ₹{day_high:.2f}, L: ₹{day_low:.2f})"

                    if abs(day_change_pct) >= 1.2 and vol_ratio >= 1.35:
                        intraday_movers.append(((vol_ratio * 2.5) + abs(day_change_pct), info))
            except Exception:
                continue
    except Exception:
        pass

    intraday_movers.sort(key=lambda x: x[0], reverse=True)
    top5_intra = "\n".join([x[1] for x in intraday_movers[:5]]) or "NO_CONFIRMED_INTRADAY"
    traps_str = ", ".join(fake_traps_detected[:5]) if fake_traps_detected else "None"

    return f"INTRADAY MOVERS:\n{top5_intra}\nREJECTED TRAPS:\n{traps_str}"

# ==========================================
# 6. GLOBAL MACRO, ETF & INDIA FII/DII NEWS
# ==========================================
def get_world_comprehensive_news(nse_live, mcx_live):
    queries = [
        ("Global Macro & Institutional", "world+economy+US+Fed+inflation+geopolitics+war+oil+FII+institutional+news"),
        ("Crypto Whales & Regulation", "cryptocurrency+bitcoin+ethereum+whale+ETF+inflow+outflow+SEC+news")
    ]
    if nse_live:
        queries.append(("India Corporate & FII/DII", "NSE+BSE+stocks+order+win+FII+DII+block+deal+India+today"))

    all_headlines = []
    rss_base = "https://news.google.com/rss/search?q="
    for category, q in queries:
        try:
            rss_url = f"{rss_base}{q}&hl=en-IN&gl=IN&ceid=IN:en"
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:3]:
                all_headlines.append(f"[{category}] {entry.title}")
        except Exception:
            continue

    return "\n".join(all_headlines) if all_headlines else "No major breaking news right now."

# ==========================================
# 7. GEMINI AI WITH 503 AUTO-RETRY & MODEL FALLBACK
# ==========================================
def ask_gemini_advanced(prompt):
    models_to_try = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.5-pro"]
    
    for model_name in models_to_try:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                if response and response.text:
                    return response.text
            except APIError as e:
                if e.code in [503, 429]:
                    print(f"[{model_name}] Busy (Code {e.code}), retrying in 5s...")
                    time.sleep(5)
                else:
                    print(f"[{model_name}] API Error: {e}")
                    break
            except Exception as ex:
                print(f"[{model_name}] Exception: {ex}")
                break
                
    return "ਸਰਵਰ ਹਾਈ ਡਿਮਾਂਡ (503) ਕਾਰਨ ਅਜੇ ਰਿਪੋਰਟ ਤਿਆਰ ਨਹੀਂ ਹੋ ਸਕੀ। ਅਗਲੇ ਸਲੌਟ ਵਿੱਚ ਆਟੋਮੈਟਿਕ ਕੋਸ਼ਿਸ਼ ਕੀਤੀ ਜਾਵੇਗੀ।"

# ==========================================
# 8. TELEGRAM ALERT (WITH 4000-CHAR CHUNKING)
# ==========================================
def send_telegram_alert(full_message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    chunks = [full_message[i : i + 4000] for i in range(0, len(full_message), 4000)]
    for chunk in chunks:
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": chunk}
        res = requests.post(url, json=payload, timeout=15)
        print("Telegram Status:", res.status_code)

# ==========================================
# 9. MAIN RUNNER
# ==========================================
def analyze_everything():
    time_str, nse_live, mcx_live, crypto_live = get_live_market_status()

    crypto_info = get_live_crypto() if crypto_live else ""
    live_market_data = get_live_indices_and_mcx(nse_live, mcx_live)
    world_news = get_world_comprehensive_news(nse_live, mcx_live)
    top5_stocks = scan_top5_smart_money_only() if nse_live else ""

    active_markets = []
    if crypto_live:
        active_markets.append("Crypto (24/7 Live)")
    if mcx_live:
        active_markets.append("MCX Commodity (Live)")
    if nse_live:
        active_markets.append("NSE Indian Stocks & Index (Live)")

    mcx_intra_line = "- MCX Intraday (Gold, Silver in ₹): Action | Entry | Target | SL" if mcx_live else ""
    nse_idx_intra_line = "- Index Intraday (Nifty 50, Bank Nifty): Action | Entry | Target | SL" if nse_live else ""
    nse_stk_intra_line = "- Nifty 100 Top 5 (<₹1000) INTRADAY: ਜੇ ਕੋਈ ਸੈੱਟਅੱਪ ਨਹੀਂ ਹੈ ਤਾਂ ਲਿਖੋ 'ਕੋਈ ਪੱਕਾ ਸੈੱਟਅੱਪ ਨਹੀਂ, WAIT'। ਨਹੀਂ ਤਾਂ: ਦਿਸ਼ਾ | Entry | Target | SL" if nse_live else ""

    prompt = (
        "Act as an elite Institutional Smart Money Trader and Risk Manager.\n"
        f"Current Time: {time_str}\n"
        f"ACTIVE MARKETS: {', '.join(active_markets)}\n\n"
        "STRICT RULES:\n"
        "1. Never guess prices. Use ONLY the exact live prices, Highs, and Lows provided in DATA.\n"
        "2. Never force a trade. If sideways, BTC is flat (<1% move), or fake break, mark 'WAIT / NO TRADE'.\n"
        "3. Give exact Entry, Target, and Stop-Loss (SL) for valid setups.\n"
        "4. Write MCX Gold/Silver prices in INR (₹) if Fyers INR data is present.\n\n"
        "DATA:\n"
        f"- Crypto (Binance Live): {crypto_info}\n"
        f"- Indices/MCX Live: {live_market_data}\n"
        f"- Nifty 100 Scan:\n{top5_stocks}\n"
        f"- News:\n{world_news}\n\n"
        "Output in PURE PUNJABI (Gurmukhi script) for Telegram with exact Entry, Target, and SL:\n\n"
        "🕵️‍♂️ 1. ਮਾਰਕੀਟ ਰਿਵਿਊ & Fake Breakout ਚੇਤਾਵਨੀ\n\n"
        "⚡ ਭਾਗ A: INTRADAY TRADING\n"
        "- Crypto Intraday (BTC, ETH, BNB, SOL): Action | Entry | Target | SL\n"
        f"{mcx_intra_line}\n"
        f"{nse_idx_intra_line}\n"
        f"{nse_stk_intra_line}\n\n"
        "Strictly avoid markdown asterisks (*) or underscores (_)."
    )

    analysis_text = ask_gemini_advanced(prompt)
    send_telegram_alert(f"🛡️ LIVE SMART MONEY & VERIFIED SETUP REPORT ({time_str})\n\n" + analysis_text)

if __name__ == "__main__":
    analyze_everything()
