import os
import requests
import yfinance as yf
import feedparser
from datetime import datetime
import pytz

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
MODEL_ID = "gemini-2.5-flash"

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
    weekday = now.weekday()  # 0=Mon, 4=Fri, 5=Sat, 6=Sun
    current_minutes = now.hour * 60 + now.minute

    is_weekday = weekday < 5
    # NSE Equity: 9:15 AM (555) to 3:30 PM (930)
    nse_live = is_weekday and (555 <= current_minutes <= 930)
    # MCX Commodity: 9:00 AM (540) to 11:30 PM (1410)
    mcx_live = is_weekday and (540 <= current_minutes <= 1410)

    return now.strftime("%d-%b-%Y %I:%M %p IST"), nse_live, mcx_live

def ask_gemini(prompt):
    url = f"https://googleapis.com{MODEL_ID}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(url, headers=headers, json=data, timeout=120)
        res_json = response.json()
        if 'candidates' in res_json and len(res_json['candidates']) > 0:
            return res_json['candidates']['content']['parts']['text']
        return f"Gemini API Raw Response: {res_json}"
    except Exception as e:
        return f"Gemini API Error: {e}"

def get_crypto_prices():
    try:
        url = "https://coingecko.com"
        res = requests.get(url, timeout=10).json()
        coins = []
        for cid, sym in [("bitcoin", "BTC"), ("ethereum", "ETH"), ("binancecoin", "BNB"), ("solana", "SOL")]:
            if cid in res:
                vol_b = res[cid].get('usd_24h_vol', 0) / 1e9
                coins.append(f"{sym}: ${res[cid]['usd']} ({res[cid]['usd_24h_change']:+.2f}% | 24h Vol: ${vol_b:.2f}B)")
        return " | ".join(coins)
    except Exception as e:
        return f"Crypto Data Error: {e}"

def get_world_comprehensive_news(nse_live, mcx_live):
    queries = [
        ("Global Macro & Institutional", "world+economy+US+Fed+inflation+geopolitics+war+oil+FII+institutional+news"),
        ("Crypto Whales & Regulation", "cryptocurrency+bitcoin+ethereum+whale+ETF+inflow+outflow+SEC+news")
    ]
    if mcx_live:
        queries.append(("Commodities & MCX", "gold+silver+crude+oil+MCX+commodity+price+news+today"))
    if nse_live:
        queries.append(("India Corporate & FII/DII", "NSE+BSE+stocks+order+win+FII+DII+block+deal+India+today"))

    all_headlines = []
    for category, q in queries:
        try:
            rss_url = f"https://google.com{q}&hl=en-IN&gl=IN&ceid=IN:en"
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
                if sym not in data.columns.levels:
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
                    low_5d = float(hist['Low'].iloc[-5:].min())
                    high_15d = float(hist['High'].max())
                    low_15d = float(hist['Low'].min())

                    clean_name = sym.replace(".NS", "")
                    day_range = day_high - day_low

                    # 1. FAKE BREAKOUT / TRAP CHECK (ਨਕਲੀ ਬ੍ਰੇਕਆਊਟ ਦੀ ਜਾਂਚ)
                    # ਜੇਕਰ ਕੀਮਤ ਦਿਨ ਦੇ High ਤੋਂ ਬਹੁਤ ਹੇਠਾਂ ਡਿੱਗ ਗਈ (ਵੱਡੀ Upper Wick) ਜਾਂ ਬਿਨਾਂ ਵਾਲੀਅਮ ਤੋਂ ਉੱਪਰ ਗਈ
                    upper_wick_ratio = ((day_high - curr_price) / day_range) if day_range > 0 else 0
                    lower_wick_ratio = ((curr_price - day_low) / day_range) if day_range > 0 else 0

                    if day_change_pct > 1.0 and (vol_ratio < 1.1 or upper_wick_ratio > 0.55):
                        fake_traps_detected.append(f"{clean_name} (Fake Bullish Trap: Vol {vol_ratio:.1f}x, High Rejection)")
                        continue  # ਇਸ ਨੂੰ ਟ੍ਰੇਡ ਲਿਸਟ ਵਿੱਚੋਂ ਬਾਹਰ ਕੱਢੋ

                    if day_change_pct < -1.0 and (vol_ratio < 1.1 or lower_wick_ratio > 0.55):
                        fake_traps_detected.append(f"{clean_name} (Fake Breakdown Trap: Vol {vol_ratio:.1f}x, Low Rejection)")
                        continue  # ਇਸ ਨੂੰ ਟ੍ਰੇਡ ਲਿਸਟ ਵਿੱਚੋਂ ਬਾਹਰ ਕੱਢੋ

                    # 2. GENUINE SMART MONEY FOOTPRINT (ਸਿਰਫ਼ 100% ਮਜ਼ਬੂਤ ਵਾਲੀਅਮ ਤੇ ਕਲੋਜ਼ਿੰਗ ਵਾਲੇ ਸਟਾਕ)
                    info = (
                        f"{clean_name}: Price ₹{curr_price:.2f} (Day: {day_change_pct:+.2f}%, Intraday: {intraday_move_pct:+.2f}%) | "
                        f"Smart Vol: {vol_ratio:.1f}x | 5D Range: ₹{low_5d:.2f}-₹{high_5d:.2f} | 15D Range: ₹{low_15d:.2f}-₹{high_15d:.2f}"
                    )

                    # Intraday: ਵਾਲੀਅਮ ਘੱਟੋ-ਘੱਟ 1.35x ਹੋਵੇ ਅਤੇ ਕੀਮਤ ਦਿਨ ਦੇ ਸਿਖਰ/ਤਲ ਦੇ ਨੇੜੇ ਹੋਵੇ
                    strong_bull_intra = (day_change_pct >= 1.2) and (vol_ratio >= 1.35) and (upper_wick_ratio <= 0.30)
                    strong_bear_intra = (day_change_pct <= -1.2) and (vol_ratio >= 1.35) and (lower_wick_ratio <= 0.30)

                    if strong_bull_intra or strong_bear_intra:
                        intra_score = (vol_ratio * 2.5) + abs(day_change_pct)
                        intraday_movers.append((intra_score, info))

                    # Swing: 15 ਦਿਨਾਂ ਦੇ ਬ੍ਰੇਕਆਊਟ/ਬ੍ਰੇਕਡਾਊਨ 'ਤੇ ਮਜ਼ਬੂਤ ਵਾਲੀਅਮ (1.3x+) ਨਾਲ ਟਿਕਿਆ ਹੋਵੇ
                    strong_bull_swing = (curr_price >= high_15d * 0.99) and (vol_ratio >= 1.3) and (upper_wick_ratio <= 0.30)
                    strong_bear_swing = (curr_price <= low_15d * 1.01) and (vol_ratio >= 1.3) and (lower_wick_ratio <= 0.30)

                    if strong_bull_swing or strong_bear_swing:
                        swing_score = (vol_ratio * 2) + abs(day_change_pct)
                        swing_movers.append((swing_score, info))

            except Exception:
                continue
    except Exception:
        pass

    intraday_movers.sort(key=lambda x: x, reverse=True)
    swing_movers.sort(key=lambda x: x, reverse=True)

    top5_intra = "\n".join([x for x in intraday_movers[:5]]) or "NO_100_PERCENT_CONFIRMED_INTRADAY"
    top5_swing = "\n".join([x for x in swing_movers[:5]]) or "NO_100_PERCENT_CONFIRMED_SWING"
    traps_str = ", ".join(fake_traps_detected[:5]) if fake_traps_detected else "None detected"

    return (
        f"VERIFIED INTRADAY (Smart Money Confirmed):\n{top5_intra}\n\n"
        f"VERIFIED SWING (Smart Money Confirmed):\n{top5_swing}\n\n"
        f"REJECTED FAKE BREAKOUTS/TRAPS:\n{traps_str}"
    )

def send_telegram_alert(full_message):
    url = f"https://telegram.org{TELEGRAM_BOT_TOKEN}/sendMessage"
    chunks = [full_message[i : i + 4000] for i in range(0, len(full_message), 4000)]
    for chunk in chunks:
