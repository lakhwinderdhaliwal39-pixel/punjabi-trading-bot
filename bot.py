import os
import requests
import yfinance as yf
import feedparser
from datetime import datetime
import pytz

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
MODEL_ID = "gemini-3.5-flash"  # 3.5 ਮਾਡਲ ਸੈੱਟ ਕਰ ਦਿੱਤਾ ਗਿਆ ਹੈ

NIFTY100_LOW_PRICE = [
    "PNB.NS", "BANKBARODA.NS", "CANBK.NS", "SAIL.NS", "ETERNAL.NS",
    "IRCTC.NS", "POWERGRID.NS", "NTPC.NS", "COALINDIA.NS", "BHEL.NS",
    "ONGC.NS", "GAIL.NS", "IOC.NS", "BPCL.NS", "VEDL.NS",
    "HINDALCO.NS", "TATASTEEL.NS", "JSWSTEEL.NS", "DLF.NS", "DABUR.NS",
    "MARICO.NS", "WIPRO.NS", "TECHM.NS", "BEL.NS", "HAL.NS",
    "JIOFIN.NS", "ADANIPOWER.NS", "NHPC.NS", "PFC.NS", "RECLTD.NS",
    "UNIONBANK.NS", "IDFCFIRSTB.NS", "MOTHERSON.NS"
]

def get_live_market_status():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    weekday = now.weekday()
    current_minutes = now.hour * 60 + now.minute

    is_weekday = weekday < 5
    nse_live = is_weekday and (555 <= current_minutes <= 930)
    mcx_live = is_weekday and (540 <= current_minutes <= 1410)
    crypto_live = True

    return now.strftime("%d-%b-%Y %I:%M %p IST"), nse_live, mcx_live, crypto_live

def ask_gemini(prompt):
    api_key = (GEMINI_API_KEY or "").strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_ID}:generateContent?key={api_key}"

    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    for attempt in range(2):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=120)
            res_json = response.json()
            if 'candidates' in res_json and len(res_json['candidates']) > 0:
                return res_json['candidates'][0]['content']['parts'][0]['text']
            return f"Gemini API Raw Response: {res_json}"
        except Exception as e:
            if attempt == 1:
                return f"Gemini API Error: {e}"
    return "Gemini API Error: Max retries reached."

def get_crypto_prices():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,binancecoin,solana&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true"
        res = requests.get(url, timeout=10).json()

        coins = []
        for cid, sym in [("bitcoin", "BTC"), ("ethereum", "ETH"), ("binancecoin", "BNB"), ("solana", "SOL")]:
            if cid in res:
                vol_b = res[cid].get('usd_24h_vol', 0) / 1e9
                coins.append(f"{sym}: ${res[cid]['usd']} ({res[cid]['usd_24h_change']:+.2f}% | 24h Vol: ${vol_b:.2f}B)")
        return " | ".join(coins) if coins else "No crypto data available."
    except Exception as e:
        return f"Crypto Data Error: {e}"

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

def get_live_indices_and_mcx(nse_live, mcx_live):
    symbols = {}
    if nse_live:
        symbols["NIFTY 50"] = "^NSEI"
        symbols["BANK NIFTY"] = "^NSEBANK"
    if mcx_live:
        symbols["GOLD (MCX Ref)"] = "GC=F"
        symbols["SILVER (MCX Ref)"] = "SI=F"

    if not symbols:
        return ""

    report = []
    for name, sym in symbols.items():
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="5d")
            if len(hist) >= 2:
                curr_price = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2]
                day_high = hist['High'].iloc[-1]
                day_low = hist['Low'].iloc[-1]
                change_pct = ((curr_price - prev_close) / prev_close) * 100
                unit = "$" if "=F" in sym else "₹"
                report.append(f"{name}: {unit}{curr_price:.2f} ({change_pct:+.2f}%)")
        except Exception:
            continue
    return " | ".join(report)

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

                    info = f"{clean_name}: ₹{curr_price:.2f} ({day_change_pct:+.2f}%, Vol: {vol_ratio:.1f}x)"

                    if abs(day_change_pct) >= 1.2 and vol_ratio >= 1.35:
                        intraday_movers.append(((vol_ratio * 2.5) + abs(day_change_pct), info))

            except Exception:
                continue
    except Exception:
        pass

    intraday_movers.sort(key=lambda x: x[0], reverse=True)
    top5_intra = "\n".join([x[1] for x in intraday_movers[:5]]) or "NO_CONFIRMED_INTRADAY"
    traps_str = ", ".join(fake_traps_detected[:3]) if fake_traps_detected else "None"

    return f"INTRADAY MOVERS:\n{top5_intra}\nREJECTED TRAPS:\n{traps_str}"

def send_telegram_alert(full_message):
    token = (TELEGRAM_BOT_TOKEN or "").strip()
    chat_id = (TELEGRAM_CHAT_ID or "").strip()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    chunks = [full_message[i : i + 4000] for i in range(0, len(full_message), 4000)]
    for chunk in chunks:
        payload = {"chat_id": chat_id, "text": chunk}
        res = requests.post(url, json=payload, timeout=15)
        print("Telegram Status:", res.status_code, res.text)

def analyze_everything():
    time_str, nse_live, mcx_live, crypto_live = get_live_market_status()

    crypto_info = get_crypto_prices() if crypto_live else ""
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

    mcx_intra_line = "- MCX Intraday (Gold, Silver): Action | Entry | Target | SL" if mcx_live else ""
    nse_idx_intra_line = "- Index Intraday (Nifty 50, Bank Nifty): Action | Entry | Target | SL" if mcx_live else ""
    nse_stk_intra_line = "- Nifty 100 Top 5 (<₹1000) INTRADAY: ਜੇ ਕੋਈ ਸੈੱਟਅੱਪ ਨਹੀਂ ਹੈ ਤਾਂ ਲਿਖੋ 'ਕੋਈ ਪੱਕਾ ਸੈੱਟਅੱਪ ਨਹੀਂ, WAIT'। ਨਹੀਂ ਤਾਂ: ਦਿਸ਼ਾ | Entry | Target | SL" if nse_live else ""

    prompt = (
        "Act as an elite Institutional Smart Money Trader and Risk Manager.\n"
        f"Current Time: {time_str}\n"
        f"ACTIVE MARKETS: {', '.join(active_markets)}\n\n"
        "RULES:\n"
        "1. Never force a trade. If sideways or fake break, mark 'WAIT / NO TRADE'.\n"
        "2. Give exact Entry, Target, and Stop-Loss (SL) for valid setups.\n\n"
        "DATA:\n"
        f"- Crypto: {crypto_info}\n"
        f"- Indices/MCX: {live_market_data}\n"
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

    analysis_text = ask_gemini(prompt)
    send_telegram_alert(f"🛡️ LIVE SMART MONEY & VERIFIED SETUP REPORT ({time_str})\n\n" + analysis_text)

if __name__ == "__main__":
    analyze_everything()
