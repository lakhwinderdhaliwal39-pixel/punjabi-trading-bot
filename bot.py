import os
import requests
import yfinance as yf
import feedparser
from datetime import datetime
import pytz

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
MODEL_ID = "gemini-3.8-flash"

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
    
    # NSE Stocks / Index Time: 9:15 AM (555 min) to 3:30 PM (930 min)
    nse_live = is_weekday and (555 <= current_minutes <= 930)
    
    # MCX Time: 9:00 AM (540 min) to 11:30 PM (1410 min)
    mcx_live = is_weekday and (540 <= current_minutes <= 1410)
    
    # Crypto is 24/7 (Always True)
    crypto_live = True

    return now.strftime("%d-%b-%Y %I:%M %p IST"), nse_live, mcx_live, crypto_live

def ask_gemini(prompt):
    api_key = (GEMINI_API_KEY or "").strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_ID}:generateContent?key={api_key}"

    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        # Timeout ਵਧਾ ਕੇ 180 ਸਕਿੰਟ ਕਰ ਦਿੱਤਾ ਗਿਆ ਹੈ
        response = requests.post(url, headers=headers, json=data, timeout=180)
        res_json = response.json()
        if 'candidates' in res_json and len(res_json['candidates']) > 0:
            return res_json['candidates'][0]['content']['parts'][0]['text']
        return f"Gemini API Raw Response: {res_json}"
    except Exception as e:
        return f"Gemini API Error: {e}"

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
            for entry in feed.entries[:4]:
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
                high_5d = hist['High'].max()
                low_5d = hist['Low'].min()
                unit = "$" if "=F" in sym else "₹"
                report.append(
                    f"{name}: {unit}{curr_price:.2f} ({change_pct:+.2f}%) | Today H/L: {unit}{day_high:.2f}/{unit}{day_low:.2f} | 5D H/L: {unit}{high_5d:.2f}/{unit}{low_5d:.2f}"
                )
        except Exception:
            continue
    return " | ".join(report)

def scan_top5_smart_money_only():
    intraday_movers = []
    swing_movers = []
    fake_traps_detected = []

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
                    day_high = float(hist['High'].iloc[-1])
                    day_low = float(hist['Low'].iloc[-1])

                    if curr_price > 1000 or open_price == 0 or prev_close == 0:
                        continue

                    day_change_pct = ((curr_price - prev_close) / prev_close) * 100
                    intraday_move_pct = ((curr_price - open_price) / open_price) * 100
                    avg_vol = float(hist['Volume'].iloc[:-1].mean())
                    curr_vol = float(hist['Volume'].iloc[-1])
                    vol_ratio = (curr_vol / avg_vol) if avg_vol > 0 else 1.0

                    high_5d = float(hist['High'].iloc[-5:].max())
                    low_5d = float(hist['High'].iloc[-5:].min())
                    high_15d = float(hist['High'].max())
                    low_15d = float(hist['Low'].min())

                    clean_name = sym.replace(".NS", "")
                    day_range = day_high - day_low

                    upper_wick_ratio = ((day_high - curr_price) / day_range) if day_range > 0 else 0
                    lower_wick_ratio = ((curr_price - day_low) / day_range) if day_range > 0 else 0

                    if day_change_pct > 1.0 and (vol_ratio < 1.1 or upper_wick_ratio > 0.55):
                        fake_traps_detected.append(f"{clean_name} (Fake Bullish Trap: Vol {vol_ratio:.1f}x, High Rejection)")
                        continue

                    if day_change_pct < -1.0 and (vol_ratio < 1.1 or lower_wick_ratio > 0.55):
                        fake_traps_detected.append(f"{clean_name} (Fake Breakdown Trap: Vol {vol_ratio:.1f}x, Low Rejection)")
                        continue

                    info = (
                        f"{clean_name}: Price ₹{curr_price:.2f} (Day: {day_change_pct:+.2f}%, Intraday: {intraday_move_pct:+.2f}%) | "
                        f"Smart Vol: {vol_ratio:.1f}x | 5D Range: ₹{low_5d:.2f}-₹{high_5d:.2f} | 15D Range: ₹{low_15d:.2f}-₹{high_15d:.2f}"
                    )

                    strong_bull_intra = (day_change_pct >= 1.2) and (vol_ratio >= 1.35) and (upper_wick_ratio <= 0.30)
                    strong_bear_intra = (day_change_pct <= -1.2) and (vol_ratio >= 1.35) and (lower_wick_ratio <= 0.30)

                    if strong_bull_intra or strong_bear_intra:
                        intra_score = (vol_ratio * 2.5) + abs(day_change_pct)
                        intraday_movers.append((intra_score, info))

                    strong_bull_swing = (curr_price >= high_15d * 0.99) and (vol_ratio >= 1.3) and (upper_wick_ratio <= 0.30)
                    strong_bear_swing = (curr_price <= low_15d * 1.01) and (vol_ratio >= 1.3) and (lower_wick_ratio <= 0.30)

                    if strong_bull_swing or strong_bear_swing:
                        swing_score = (vol_ratio * 2) + abs(day_change_pct)
                        swing_movers.append((swing_score, info))

            except Exception:
                continue
    except Exception:
        pass

    intraday_movers.sort(key=lambda x: x[0], reverse=True)
    swing_movers.sort(key=lambda x: x[0], reverse=True)

    top5_intra = "\n".join([x[1] for x in intraday_movers[:5]]) or "NO_100_PERCENT_CONFIRMED_INTRADAY"
    top5_swing = "\n".join([x[1] for x in swing_movers[:5]]) or "NO_100_PERCENT_CONFIRMED_SWING"
    traps_str = ", ".join(fake_traps_detected[:5]) if fake_traps_detected else "None detected"

    return (
        f"VERIFIED INTRADAY (Smart Money Confirmed):\n{top5_intra}\n\n"
        f"VERIFIED SWING (Smart Money Confirmed):\n{top5_swing}\n\n"
        f"REJECTED FAKE BREAKOUTS/TRAPS:\n{traps_str}"
    )

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

    mcx_intra_line = "- MCX Intraday (Gold, Silver): Action | Entry | Target | Stop-Loss (SL)" if mcx_live else ""
    nse_idx_intra_line = "- Index Intraday (Nifty 50, Bank Nifty): Action | Entry | Target | Stop-Loss (SL)" if nse_live else ""
    nse_stk_intra_line = "- Nifty 100 Top 5 (<₹1000) INTRADAY: ਜੇ ਕੋਈ 100% ਪੱਕਾ ਸੈੱਟਅੱਪ ਨਹੀਂ ਹੈ ਤਾਂ ਸਾਫ਼ ਲਿਖੋ 'ਇਸ ਵੇਲੇ ਕੋਈ 100% ਪੱਕਾ Intraday ਸੈੱਟਅੱਪ ਨਹੀਂ ਹੈ, Fake Move ਤੋਂ ਬਚੋ (WAIT)'। ਨਹੀਂ ਤਾਂ: ਦਿਸ਼ਾ | Smart Money ਕਾਰਨ | Entry (₹) | Target (₹) | Stop-Loss (₹)" if nse_live else ""

    mcx_swing_line = "- MCX Swing (Gold, Silver): Action | Entry Zone | Target | Stop-Loss (SL)" if mcx_live else ""
    nse_idx_swing_line = "- Index Swing (Nifty 50, Bank Nifty): Action | Entry Zone | Target | Stop-Loss (SL)" if nse_live else ""
    nse_stk_swing_line = "- Nifty 100 Top 5 (<₹1000) SWING: ਜੇ ਕੋਈ ਪੱਕਾ ਬ੍ਰੇਕਆਊਟ ਨਹੀਂ ਹੈ ਤਾਂ ਲਿਖੋ 'ਇਸ ਵੇਲੇ ਕੋਈ 100% ਪੱਕਾ Swing ਬ੍ਰੇਕਆਊਟ ਨਹੀਂ ਬਣ ਰਿਹਾ, ਉਡੀਕ ਕਰੋ'। ਨਹੀਂ ਤਾਂ: ਦਿਸ਼ਾ | ਅਸਲੀ ਬ੍ਰੇਕਆਊਟ ਕਾਰਨ | Entry (₹) | Target (₹) | Stop-Loss (₹)" if nse_live else ""

    prompt = (
        "Act as an elite Institutional Smart Money Trader, Liquidity Hunter, and Risk Manager.\n"
        f"Current Time: {time_str}\n"
        f"ACTIVE LIVE MARKETS RIGHT NOW: {', '.join(active_markets)}\n\n"
        "STRICT CAPITAL PROTECTION & 100% VERIFIED TRADING RULES:\n"
        "1. ONLY report on currently active markets as per their live timings. Do NOT give Indian Stock/Index calls when NSE is closed.\n"
        "2. NEVER force a trade! If volume is low, chart is sideways, or a Fake Breakout / Liquidity Sweep is detected, do NOT give a BUY/SELL call—strictly mark it as 'WAIT / NO TRADE (Fake Move Risk)'.\n"
        "3. Provide EXACT Entry, Target, and Stop-Loss (SL) for every valid setup. If a trade is not 100% high-conviction, reject it.\n"
        "4. Keep INTRADAY and SWING trades strictly separated.\n\n"
        "LIVE DATA FEED:\n"
        f"- Crypto (24/7 Live): {crypto_info}\n"
        f"- Live Indices/MCX: {live_market_data}\n"
        f"- Nifty 100 (<₹1000) Smart Money Scan:\n{top5_stocks}\n"
        f"- Global Major & Minor News Scan:\n{world_news}\n\n"
        "Output the report in PURE PUNJABI (Gurmukhi script) for Telegram:\n\n"
        "🕵️‍♂️ 1. ਵੱਡੇ ਖਿਡਾਰੀਆਂ ਦੀ ਚਾਲ, ਗਲੋਬਲ ਨਿਊਜ਼ & Fake Breakout ਚੇਤਾਵਨੀ\n"
        "- ਦੁਨੀਆ ਭਰ ਦੀਆਂ ਖ਼ਬਰਾਂ ਅਤੇ FIIs / Whales ਦੀ ਪੋਜ਼ੀਸ਼ਨ।\n"
        "- ਕਿੱਥੇ Fake Breakout ਬਣਾ ਕੇ ਰਿਟੇਲਰਾਂ ਨੂੰ ਫਸਾਇਆ ਜਾ ਰਿਹਾ ਹੈ।\n\n"
        "══════════════════════════\n"
        "⚡ ਭਾਗ A: INTRADAY TRADING (ਸਿਰਫ਼ 100% ਪੱਕੇ ਸੈੱਟਅੱਪ)\n"
        "══════════════════════════\n"
        "- Crypto Intraday (BTC, ETH, BNB, SOL): Action | Entry | Target | Stop-Loss (SL)\n"
        f"{mcx_intra_line}\n"
        f"{nse_idx_intra_line}\n"
        f"{nse_stk_intra_line}\n\n"
        "══════════════════════════\n"
        "🌊 ਭਾਗ B: SWING TRADING (ਸਿਰਫ਼ 100% ਪੱਕੇ ਬ੍ਰੇਕਆਊਟ)\n"
        "══════════════════════════\n"
        "- Crypto Swing (BTC, ETH, BNB, SOL): Action | Entry Zone | Target | Stop-Loss (SL)\n"
        f"{mcx_swing_line}\n"
        f"{nse_idx_swing_line}\n"
        f"{nse_stk_swing_line}\n\n"
        "Strictly avoid markdown asterisks (*) or underscores (_) that break Telegram formatting."
    )

    analysis_text = ask_gemini(prompt)
    send_telegram_alert(f"🛡️ LIVE SMART MONEY & VERIFIED SETUP REPORT ({time_str})\n\n" + analysis_text)

if __name__ == "__main__":
    analyze_everything()
