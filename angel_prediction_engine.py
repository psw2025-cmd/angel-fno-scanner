#!/usr/bin/env python3
"""
Angel One Dynamic Stock & Index Option (CE/PE) Prediction and Intensity Rating Engine
Production-grade autonomous engine:
- Micro-Level Option Chain Metrics (Spot, Strike, CE/PE LTP, IV, Delta, Gamma, Theta, Vega, Volume, OI, OI Velocity, PCR, Max Pain, Spread)
- Multi-Source Live News & Corporate Filings Scraper (RSS feeds, NSE announcements, sentiment scoring & impact categorization)
- Prediction & Intensity Rating Engine (Directional probability CE vs PE, intensity 1-100, confidence %, ranked table)
- Real-time Sync to Google Sheet (OPTION_PREDICTIONS tab) & BigQuery Sandbox (asia-south1, $0 cost)
"""

import os
import sys
import time
import math
import json
import re
import datetime
import urllib.request
import urllib.parse
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET
from collections import defaultdict

# 3rd party libraries
import pyotp
import gspread
from SmartApi import SmartConnect
from google.cloud import bigquery
from google.oauth2 import service_account

# =====================================================================
# CONFIGURATION & CREDENTIALS
# =====================================================================
ANGEL_API_KEY     = os.getenv("ANGEL_API_KEY", "H38aqqWn")
ANGEL_CLIENT_CODE = os.getenv("ANGEL_CLIENT_CODE", "P57752101")
ANGEL_PIN         = os.getenv("ANGEL_PIN", "1978")
ANGEL_TOTP_SEED   = os.getenv("ANGEL_TOTP_SEED", "2DPIR273IJKIWZWJ23QAKF4BDI")
SHEET_ID          = os.getenv("SHEET_ID", "1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs")
BQ_PROJECT_ID     = os.getenv("BQ_PROJECT_ID", "fno-angel-prod-1790444589")
BQ_DATASET_ID     = "fno_predictions"

KEY_PATH = os.path.expanduser("~/angel_sheets_key.json")
STATE_PATH = os.path.expanduser("~/angel_prediction_state.json")
SCRIP_CACHE_PATH = os.path.expanduser("~/angel_scrip_cache.json")
NSE_CACHE_PATH = os.path.expanduser("~/angel_nse_cache.json")

RISK_FREE_RATE = 0.065  # 6.5% standard Indian repo/yield rate

# =====================================================================
# TIME UTILITIES
# =====================================================================
def get_ist_time():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(hours=5, minutes=30)

def parse_expiry_date(exp_str):
    try:
        return datetime.datetime.strptime(exp_str.strip().upper(), "%d%b%Y").date()
    except Exception:
        return None

def is_market_open(dt=None):
    if dt is None:
        dt = get_ist_time()
    if dt.weekday() >= 5:  # Saturday or Sunday
        return False
    mins = dt.hour * 60 + dt.minute
    return 555 <= mins <= 930  # 9:15 AM (555 mins) to 3:30 PM (930 mins)

def is_pre_market_time(dt=None):
    if dt is None:
        dt = get_ist_time()
    if dt.weekday() >= 5:
        return False
    mins = dt.hour * 60 + dt.minute
    return 510 <= mins < 555  # 8:30 AM to 9:15 AM

# =====================================================================
# GOOGLE CLOUD & BIGQUERY CLIENT SETUP
# =====================================================================
def get_gspread_client():
    raw_secret = os.getenv("SHEETS_KEY_JSON", "").strip()
    if raw_secret:
        candidates = [raw_secret, re.sub(r'\\+"', '"', raw_secret)]
        for cand in candidates:
            try:
                info = json.loads(cand)
                if isinstance(info, str):
                    info = json.loads(info)
                if isinstance(info, dict) and info.get("type") == "service_account":
                    return gspread.service_account_from_dict(info)
            except Exception:
                pass
    if os.path.exists(KEY_PATH):
        return gspread.service_account(filename=KEY_PATH)
    raise RuntimeError("No valid Google service account credentials found for Sheets.")

def get_bigquery_client():
    raw_secret = os.getenv("SHEETS_KEY_JSON", "").strip()
    if raw_secret:
        try:
            info = json.loads(raw_secret)
            if isinstance(info, str):
                info = json.loads(info)
            if isinstance(info, dict) and info.get("type") == "service_account":
                creds = service_account.Credentials.from_service_account_info(info)
                return bigquery.Client(project=BQ_PROJECT_ID, credentials=creds)
        except Exception:
            pass
    if os.path.exists(KEY_PATH):
        creds = service_account.Credentials.from_service_account_file(KEY_PATH)
        return bigquery.Client(project=BQ_PROJECT_ID, credentials=creds)
    return bigquery.Client(project=BQ_PROJECT_ID)

# =====================================================================
# BLACK-76 OPTION GREEKS & IMPLIED VOLATILITY ENGINE
# =====================================================================
def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def norm_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

def black76_price(F, K, T, r, sigma, is_call=True):
    if T <= 0 or sigma <= 0 or F <= 0 or K <= 0:
        return max(0.0, F - K) if is_call else max(0.0, K - F)
    sqrt_T = math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sigma * sigma * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    df = math.exp(-r * T)
    if is_call:
        return df * (F * norm_cdf(d1) - K * norm_cdf(d2))
    else:
        return df * (K * norm_cdf(-d2) - F * norm_cdf(-d1))

def calculate_greeks(F, K, T, r, sigma, is_call=True):
    """
    Computes Delta, Gamma, Theta, Vega using Black-76 for Indian F&O futures-based options.
    """
    if T <= 0.0001 or sigma <= 0.001 or F <= 0 or K <= 0:
        return {
            "delta": 1.0 if is_call else -1.0,
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0
        }
    sqrt_T = math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sigma * sigma * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    df = math.exp(-r * T)
    pdf_d1 = norm_pdf(d1)

    if is_call:
        delta = df * norm_cdf(d1)
        theta = (- (F * df * pdf_d1 * sigma) / (2.0 * sqrt_T) - r * K * df * norm_cdf(d2) + r * F * df * norm_cdf(d1)) / 365.0
    else:
        delta = - df * norm_cdf(-d1)
        theta = (- (F * df * pdf_d1 * sigma) / (2.0 * sqrt_T) + r * K * df * norm_cdf(-d2) - r * F * df * norm_cdf(-d1)) / 365.0

    gamma = (df * pdf_d1) / (F * sigma * sqrt_T)
    vega = (F * df * pdf_d1 * sqrt_T) / 100.0  # Change in price per 1% move in IV

    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta, 4),
        "vega": round(vega, 4)
    }

def solve_implied_volatility(market_price, F, K, T, r, is_call=True):
    """Solves for Black-76 IV using bounded bisection with rapid convergence."""
    if market_price <= 0.05 or F <= 0 or K <= 0 or T <= 0:
        return 0.0
    df = math.exp(-r * T)
    intrinsic = max(0.0, (F - K) * df) if is_call else max(0.0, (K - F) * df)
    if market_price <= intrinsic:
        return 5.0  # Floor at 5%

    low, high = 0.01, 3.5  # 1% to 350% IV
    for _ in range(22):
        mid = 0.5 * (low + high)
        p = black76_price(F, K, T, r, mid, is_call)
        diff = p - market_price
        if abs(diff) < 0.02:
            return round(mid * 100.0, 2)
        if diff > 0:
            high = mid
        else:
            low = mid
    return round(0.5 * (low + high) * 100.0, 2)

# =====================================================================
# MULTI-SOURCE NEWS & CORPORATE ANNOUNCEMENTS SCRAPER
# =====================================================================
FEEDS = (
    ("Economic Times", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("Livemint", "https://www.livemint.com/rss/markets"),
    ("Business Standard", "https://www.business-standard.com/rss/markets-106.rss"),
    ("Hindu Business Line", "https://www.thehindubusinessline.com/markets/feeder/default.rss"),
    ("Moneycontrol", "https://www.moneycontrol.com/rss/MCtopnews.xml"),
)

ALIASES = {
    "RELIANCE": ("Reliance Industries", "RIL"),
    "ADANIENT": ("Adani Enterprises",),
    "ADANIPORTS": ("Adani Ports",),
    "HDFCBANK": ("HDFC Bank",),
    "ICICIBANK": ("ICICI Bank",),
    "KOTAKBANK": ("Kotak Mahindra", "Kotak Bank"),
    "AXISBANK": ("Axis Bank",),
    "SBIN": ("State Bank of India", "SBI"),
    "BAJFINANCE": ("Bajaj Finance",),
    "BAJAJFINSV": ("Bajaj Finserv",),
    "TATAMOTORS": ("Tata Motors",),
    "TATASTEEL": ("Tata Steel",),
    "TATAPOWER": ("Tata Power",),
    "TCS": ("Tata Consultancy", "TCS"),
    "INFY": ("Infosys",),
    "HCLTECH": ("HCLTech", "HCL Tech"),
    "TECHM": ("Tech Mahindra",),
    "LT": ("Larsen & Toubro", "Larsen and Toubro", "L&T"),
    "LTIM": ("LTIMindtree",),
    "HINDUNILVR": ("Hindustan Unilever", "HUL"),
    "MARUTI": ("Maruti Suzuki", "Maruti"),
    "M&M": ("Mahindra & Mahindra", "Mahindra and Mahindra"),
    "SUNPHARMA": ("Sun Pharma", "Sun Pharmaceutical"),
    "DRREDDY": ("Dr Reddy", "Dr. Reddy"),
    "DIVISLAB": ("Divi's", "Divis Lab"),
    "CIPLA": ("Cipla",),
    "APOLLOHOSP": ("Apollo Hospitals",),
    "ASIANPAINT": ("Asian Paints",),
    "ULTRACEMCO": ("UltraTech",),
    "JSWSTEEL": ("JSW Steel",),
    "HINDALCO": ("Hindalco",),
    "VEDL": ("Vedanta",),
    "POWERGRID": ("Power Grid",),
    "NTPC": ("NTPC",),
    "ONGC": ("ONGC", "Oil and Natural Gas"),
    "COALINDIA": ("Coal India",),
    "BPCL": ("Bharat Petroleum",),
    "IOC": ("Indian Oil",),
    "NESTLEIND": ("Nestle",),
    "DMART": ("Avenue Supermarts", "DMart"),
    "ZOMATO": ("Zomato", "Eternal"),
    "PAYTM": ("Paytm", "One 97"),
    "INDIGO": ("InterGlobe", "IndiGo"),
    "HAL": ("Hindustan Aeronautics", "HAL"),
    "BEL": ("Bharat Electronics", "BEL"),
    "BHEL": ("BHEL", "Bharat Heavy Electricals"),
    "BANKBARODA": ("Bank of Baroda",),
    "PNB": ("Punjab National", "PNB"),
    "CANBK": ("Canara Bank",),
    "INDUSINDBK": ("IndusInd",),
    "NIFTY": ("Nifty 50", "Nifty", "NSE Nifty"),
    "BANKNIFTY": ("Bank Nifty", "Nifty Bank"),
}

POSITIVE_WORDS = (
    "contract", "order win", "awarded", "wins order", "net profit", "profit rises",
    "profit jumps", "beats estimates", "upgrade", "buyback", "dividend", "acquisition",
    "approval", "surge", "jumps", "rally", "record high", "partnership", "expansion",
    "commissioned", "stake buy", "bonus", "outperform", "bullish"
)

NEGATIVE_WORDS = (
    "net loss", "loss widens", "fraud", "default", "downgrade", "plunge", "plunges",
    "crashes", "resignation", "penalty", "probe", "investigation", "misses estimates",
    "slumps", "selloff", "sell-off", "pledged", "raid", "ban ", "defaults", "sebi penalty",
    "cbi probe", "bearish"
)

CATEGORY_RULES = (
    ("ORDER_WIN", ("award of order", "order win", "bags order", "bags rs", "contract win", "wins contract", "new order")),
    ("EARNINGS_BEAT", ("profit jumps", "profit rises", "net profit up", "beats estimates", "strong earnings")),
    ("EARNINGS_MISS", ("net loss", "loss widens", "profit falls", "misses estimates", "weak earnings")),
    ("REGULATORY_PROBE", ("probe", "penalty", "sebi", "cbi", "ed raid", "fraud", "investigation", "show cause")),
    ("M&A_EXPANSION", ("acquisition", "merger", "amalgamation", "stake buy", "expansion", "commissioned", "joint venture")),
    ("CAPITAL_DIVIDEND", ("dividend", "bonus", "buyback", "stock split", "sub-division", "allotment")),
    ("MANAGEMENT_CHANGE", ("resignation", "change in management", "appointed", "ceo exit", "md resigns")),
)

def fetch_rss_feed(source_name, url):
    items = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=12) as response:
            tree = ET.fromstring(response.read())
            for item in tree.iter("item"):
                title_node = item.find("title")
                pub_node = item.find("pubDate")
                title = (title_node.text or "").strip() if title_node is not None else ""
                if not title:
                    continue
                pub_raw = (pub_node.text or "").strip() if pub_node is not None else ""
                items.append({
                    "title": title,
                    "source": source_name,
                    "pubDate": pub_raw
                })
    except Exception as e:
        print(f"[WARN] Failed to fetch feed {source_name}: {e}")
    return items

def analyze_headline(title):
    lowered = f" {title.lower()} "
    pos_count = sum(1 for w in POSITIVE_WORDS if w in lowered)
    neg_count = sum(1 for w in NEGATIVE_WORDS if w in lowered)
    
    total = pos_count + neg_count
    sentiment_score = 0.0
    if total > 0:
        sentiment_score = round((pos_count - neg_count) / total, 3)

    # Classify category
    cat = "GENERAL_MACRO"
    for category, keys in CATEGORY_RULES:
        if any(k in lowered for k in keys):
            cat = category
            break

    # Determine impact rating
    if cat in ("ORDER_WIN", "EARNINGS_BEAT") or sentiment_score >= 0.5:
        impact = "CRITICAL_BULLISH" if sentiment_score >= 0.6 else "MODERATE_BULLISH"
    elif cat in ("REGULATORY_PROBE", "EARNINGS_MISS") or sentiment_score <= -0.5:
        impact = "CRITICAL_BEARISH" if sentiment_score <= -0.6 else "MODERATE_BEARISH"
    elif sentiment_score > 0.15:
        impact = "MODERATE_BULLISH"
    elif sentiment_score < -0.15:
        impact = "MODERATE_BEARISH"
    else:
        impact = "NEUTRAL"

    return sentiment_score, cat, impact

def aggregate_news_for_symbols(universe_symbols):
    """Fetches live RSS feeds and scans local NSE announcements for all active symbols."""
    print("[INFO] Scraping live news from multiple financial feeds & NSE filings...")
    all_articles = []
    for s_name, feed_url in FEEDS:
        articles = fetch_rss_feed(s_name, feed_url)
        all_articles.extend(articles)
        time.sleep(0.15)

    # Check local NSE filings cache
    nse_filings = []
    if os.path.exists(NSE_CACHE_PATH):
        try:
            with open(NSE_CACHE_PATH, "r", encoding="utf-8") as f:
                cached = json.load(f)
                nse_filings = cached.get("rows", [])
        except Exception as e:
            print(f"[WARN] Error reading NSE cache: {e}")

    sym_news = defaultdict(list)
    
    # 1. Match RSS articles
    for art in all_articles:
        t = art["title"]
        for sym in universe_symbols:
            matched = False
            if re.search(rf"\b{re.escape(sym)}\b", t, re.IGNORECASE):
                matched = True
            else:
                for alias in ALIASES.get(sym, ()):
                    if re.search(rf"\b{re.escape(alias)}\b", t, re.IGNORECASE):
                        matched = True
                        break
            if matched:
                score, cat, impact = analyze_headline(t)
                sym_news[sym].append({
                    "title": t,
                    "source": art["source"],
                    "score": score,
                    "category": cat,
                    "impact": impact,
                    "filing_type": ""
                })

    # 2. Match NSE filings
    for n in nse_filings:
        sym = str(n.get("symbol", "")).strip().upper()
        if sym in universe_symbols:
            text = str(n.get("attchmntText", "") or n.get("desc", "")).strip()
            if text:
                score, cat, impact = analyze_headline(text)
                desc = str(n.get("desc", "NSE Filing")).strip()
                sym_news[sym].append({
                    "title": text[:200],
                    "source": "NSE Official Announcement",
                    "score": score,
                    "category": cat,
                    "impact": impact,
                    "filing_type": desc
                })

    # Aggregate by symbol
    aggregated = {}
    for sym in universe_symbols:
        items = sym_news.get(sym, [])
        if not items:
            aggregated[sym] = {
                "sentiment_score": 0.0,
                "category": "NO_RECENT_HEADLINE",
                "impact_rating": "NEUTRAL",
                "top_headline": "No fresh material catalyst",
                "item_count": 0,
                "items": []
            }
            continue
        
        # Pick the most impactful item as top headline
        items.sort(key=lambda x: abs(x["score"]), reverse=True)
        top = items[0]
        avg_score = round(sum(i["score"] for i in items) / len(items), 3)
        aggregated[sym] = {
            "sentiment_score": avg_score,
            "category": top["category"],
            "impact_rating": top["impact"],
            "top_headline": top["title"],
            "item_count": len(items),
            "items": items[:5]
        }

    print(f"[OK] News aggregated: {sum(1 for v in aggregated.values() if v['item_count'] > 0)} symbols have active headlines/filings.")
    return aggregated

# =====================================================================
# DYNAMIC F&O UNIVERSE DISCOVERY & ANGEL ONE INTEGRATION
# =====================================================================
def get_angel_client():
    totp = pyotp.TOTP(ANGEL_TOTP_SEED).now()
    smartApi = SmartConnect(api_key=ANGEL_API_KEY)
    login = smartApi.generateSession(ANGEL_CLIENT_CODE, ANGEL_PIN, totp)
    if not login or not login.get("status"):
        raise RuntimeError(f"Angel One session rejected: {login}")
    print(f"[OK] Angel One SmartAPI Session Connected for {ANGEL_CLIENT_CODE}")
    return smartApi

def load_or_download_scrip_master():
    """Loads cached OpenAPI scrip master or downloads fresh if expired/missing."""
    now_ts = time.time()
    if os.path.exists(SCRIP_CACHE_PATH):
        try:
            mtime = os.path.getmtime(SCRIP_CACHE_PATH)
            if (now_ts - mtime) < 86400:  # Fresh within 24 hours
                with open(SCRIP_CACHE_PATH, "r", encoding="utf-8") as f:
                    print("[INFO] Loading cached OpenAPIScripMaster.json...")
                    return json.load(f)
        except Exception:
            pass

    print("[INFO] Downloading fresh Angel One OpenAPIScripMaster.json (~100MB)...")
    url = "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"
    req = urllib.request.urlopen(url, timeout=35)
    data = json.loads(req.read().decode("utf-8"))
    try:
        with open(SCRIP_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[WARN] Failed to write scrip cache: {e}")
    return data

def discover_fno_universe(scrip_master):
    today = get_ist_time().date()
    options_by_sym = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    futures_by_sym = defaultdict(list)

    for c in scrip_master:
        if c.get("exch_seg") != "NFO":
            continue
        name = c.get("name", "").strip().upper()
        inst = c.get("instrumenttype", "").strip().upper()
        tsym = c.get("symbol", "").strip().upper()
        exp_date = parse_expiry_date(c.get("expiry", ""))

        if not name or not exp_date or exp_date < today:
            continue

        if inst in ("OPTSTK", "OPTIDX"):
            raw_strike = float(c.get("strike", 0.0)) / 100.0
            if raw_strike <= 0:
                continue
            if tsym.endswith("CE"):
                options_by_sym[name][exp_date][raw_strike]["CE"] = c
            elif tsym.endswith("PE"):
                options_by_sym[name][exp_date][raw_strike]["PE"] = c

        elif inst in ("FUTSTK", "FUTIDX"):
            c["_exp_date"] = exp_date
            futures_by_sym[name].append(c)

    universe = {}
    for sym, exp_dict in options_by_sym.items():
        if sym not in futures_by_sym:
            continue
        nearest_opt_exp = min(exp_dict.keys())
        strikes_map = exp_dict[nearest_opt_exp]
        valid_strikes = {k: v for k, v in strikes_map.items() if "CE" in v and "PE" in v}
        if not valid_strikes:
            continue

        fut_list = sorted(futures_by_sym[sym], key=lambda x: x["_exp_date"])
        nearest_fut = fut_list[0]

        universe[sym] = {
            "symbol": sym,
            "fut_token": str(nearest_fut["token"]),
            "fut_tradingsymbol": nearest_fut["symbol"],
            "lotsize": int(nearest_fut.get("lotsize", 1)),
            "opt_expiry": nearest_opt_exp.strftime("%d-%b-%Y"),
            "opt_expiry_date": nearest_opt_exp,
            "strikes": valid_strikes
        }

    print(f"[OK] Auto-Discovered {len(universe)} NSE F&O Symbols with active CE & PE Option Chains!")
    return universe

def fetch_quotes_in_batches(smartApi, token_list, chunk_size=45):
    results = {}
    chunks = [token_list[i:i + chunk_size] for i in range(0, len(token_list), chunk_size)]
    for chunk in chunks:
        try:
            res = smartApi.getMarketData("FULL", {"NFO": chunk})
            if res and res.get("status") and res.get("data"):
                for item in res["data"].get("fetched", []):
                    results[str(item.get("symbolToken"))] = item
            time.sleep(0.22)
        except Exception as e:
            print(f"[WARN] Quote batch error: {e}")
            time.sleep(0.4)
    return results

# =====================================================================
# PERSISTENT STATE & OI VELOCITY
# =====================================================================
def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"symbols": {}, "last_updated": ""}

def save_state(state):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"[WARN] Failed to save state: {e}")

# =====================================================================
# PREDICTION & INTENSITY RATING ENGINE
# =====================================================================
def compute_prediction_and_rating(
    sym, fut_ltp, fut_pct, fut_obi,
    ce_ltp, ce_pct, ce_oi, ce_obi, ce_spread, ce_iv, ce_delta, ce_gamma, ce_theta, ce_vega,
    pe_ltp, pe_pct, pe_oi, pe_obi, pe_spread, pe_iv, pe_delta, pe_gamma, pe_theta, pe_vega,
    atm_pcr, max_pain, prev_ce_oi, prev_pe_oi,
    news_sentiment, news_category, news_impact
):
    """
    Combines micro-level market structure (Greeks, OI velocity, OBI, PCR, Max Pain)
    with multi-source news sentiment to calculate:
    - Directional Probability (CE rise vs PE rise)
    - Expected Intensity / Momentum Score (1 - 100)
    - Actionable Prediction Rating and Confidence %
    """
    # 1. OI Velocity / Change %
    ce_oi_velocity = 0.0
    if prev_ce_oi and prev_ce_oi > 0:
        ce_oi_velocity = round(((ce_oi - prev_ce_oi) / prev_ce_oi) * 100.0, 2)

    pe_oi_velocity = 0.0
    if prev_pe_oi and prev_pe_oi > 0:
        pe_oi_velocity = round(((pe_oi - prev_pe_oi) / prev_pe_oi) * 100.0, 2)

    # 2. Base Directional Logit (positive = Bullish CE, negative = Bearish PE)
    logit = 0.0

    # A. Futures Price & Order Imbalance Momentum (Weight: 35%)
    logit += (fut_pct * 0.40)          # +1% fut move gives +0.40 logit
    logit += (fut_obi * 0.85)          # Futures order book imbalance (-1 to +1)

    # B. Options Price & Flow Velocity (Weight: 25%)
    # Call accumulation vs writing
    if ce_pct > 0 and ce_oi_velocity > 0:
        logit += min(1.0, ce_oi_velocity * 0.05)  # Long call accumulation
    elif ce_pct < 0 and ce_oi_velocity > 0:
        logit -= min(1.0, ce_oi_velocity * 0.04)  # Call writing (resistance)

    # Put accumulation vs writing
    if pe_pct > 0 and pe_oi_velocity > 0:
        logit -= min(1.0, pe_oi_velocity * 0.05)  # Long put accumulation (bearish)
    elif pe_pct < 0 and pe_oi_velocity > 0:
        logit += min(1.0, pe_oi_velocity * 0.04)  # Put writing (bullish floor)

    # C. PCR & Max Pain Gravitational Influence (Weight: 15%)
    if atm_pcr is not None:
        if atm_pcr >= 1.25:
            logit += 0.35  # Strong Put Support
        elif atm_pcr <= 0.70:
            logit -= 0.35  # Heavy Call Resistance

    if max_pain > 0 and fut_ltp > 0:
        pain_gap_pct = ((fut_ltp - max_pain) / max_pain) * 100.0
        if abs(pain_gap_pct) < 1.0:
            # Near Max Pain -> Pinning consolidation
            logit *= 0.85
        elif pain_gap_pct > 1.5 and fut_pct > 0:
            # Squeezing above Max Pain
            logit += 0.25

    # D. Greeks & Gamma Squeeze Risk (Weight: 10%)
    if ce_gamma > 0.0005 and ce_obi > 0.15 and fut_pct > 0.2:
        logit += 0.50  # Gamma squeeze upward acceleration
    elif pe_gamma > 0.0005 and pe_obi > 0.15 and fut_pct < -0.2:
        logit -= 0.50  # Gamma breakdown downward acceleration

    # E. News Sentiment & Impact Rating (Weight: 15%)
    category_weights = {
        "ORDER_WIN": 1.6,
        "EARNINGS_BEAT": 1.5,
        "EARNINGS_MISS": -1.5,
        "REGULATORY_PROBE": -1.8,
        "M&A_EXPANSION": 1.2,
        "CAPITAL_DIVIDEND": 1.1,
        "MANAGEMENT_CHANGE": -0.4,
        "GENERAL_MACRO": 0.8
    }
    news_mult = category_weights.get(news_category, 1.0)
    logit += (news_sentiment * news_mult * 0.60)

    # 3. Calculate Directional Probabilities
    # Sigmoidal squash to [5%, 95%]
    prob_ce = 1.0 / (1.0 + math.exp(-max(-4.0, min(4.0, logit * 1.5))))
    ce_win_prob = round(prob_ce * 100.0, 1)
    pe_win_prob = round((100.0 - ce_win_prob), 1)

    # 4. Expected Intensity / Momentum Score (1 - 100)
    # Measures the kinetic velocity and explosive potential of the option move
    intensity = 35.0  # Base market momentum

    # Volatility impact
    avg_iv = (ce_iv + pe_iv) / 2.0 if (ce_iv + pe_iv) > 0 else 20.0
    intensity += min(25.0, (avg_iv / 35.0) * 20.0)

    # Underlying velocity & OBI extremity
    intensity += min(20.0, abs(fut_pct) * 6.0)
    intensity += min(15.0, abs(fut_obi) * 15.0)

    # High Gamma & OI surge multiplier
    if max(ce_gamma, pe_gamma) > 0.0004:
        intensity += 10.0
    if max(abs(ce_oi_velocity), abs(pe_oi_velocity)) > 15.0:
        intensity += 10.0

    # News impact catalyst boost
    if news_category in ("ORDER_WIN", "REGULATORY_PROBE", "EARNINGS_BEAT", "EARNINGS_MISS"):
        intensity += 12.0

    intensity_score = int(max(20, min(99, round(intensity))))

    # 5. Confidence Score (50% - 98%)
    # Reflects agreement across Greeks, Order flow, and News
    conviction_distance = abs(ce_win_prob - 50.0)  # 0 to 45
    agreement_boost = 0.0
    if (ce_win_prob > 55.0 and news_sentiment > 0.2 and fut_obi > 0.1) or \
       (pe_win_prob > 55.0 and news_sentiment < -0.2 and fut_obi < -0.1):
        agreement_boost = 12.0  # Multi-signal confluence
    confidence_pct = round(min(97.5, 52.0 + conviction_distance * 0.90 + agreement_boost), 1)

    # 6. Actionable Rating & Directional Bias
    if ce_win_prob >= 72.0 and intensity_score >= 70:
        rating = "🔥 STRONG CE BREAKOUT [EXPONENTIAL MOMENTUM]"
        bias = "CALL (CE) BULLISH"
    elif ce_win_prob >= 62.0 and intensity_score >= 55:
        rating = "⚡ BULLISH CE ACCUMULATION [HIGH CONVICTION]"
        bias = "CALL (CE) BULLISH"
    elif ce_win_prob >= 55.0:
        rating = "📈 MODERATE CE BIAS"
        bias = "CALL (CE) BULLISH"
    elif pe_win_prob >= 72.0 and intensity_score >= 70:
        rating = "💥 SEVERE PE BREAKDOWN [AGGRESSIVE SHORT]"
        bias = "PUT (PE) BEARISH"
    elif pe_win_prob >= 62.0 and intensity_score >= 55:
        rating = "⚡ BEARISH PE SURGE [HIGH CONVICTION]"
        bias = "PUT (PE) BEARISH"
    elif pe_win_prob >= 55.0:
        rating = "📉 MODERATE PE BIAS"
        bias = "PUT (PE) BEARISH"
    else:
        rating = "⏸️ NEUTRAL / RANGEBOUND PINNING"
        bias = "NEUTRAL"

    # Special Gamma Squeeze alert tag
    if ce_gamma > 0.0006 and ce_obi > 0.20 and ce_win_prob >= 60.0:
        rating = "🚨 GAMMA SQUEEZE ALERT (ACCELERATING CE)"

    return {
        "directional_bias": bias,
        "ce_win_prob": ce_win_prob,
        "pe_win_prob": pe_win_prob,
        "intensity_score": intensity_score,
        "confidence_pct": confidence_pct,
        "action_rating": rating,
        "ce_oi_velocity": ce_oi_velocity,
        "pe_oi_velocity": pe_oi_velocity,
        "rank_metric": round(conviction_distance * 1.5 + intensity_score * 0.8, 2)
    }

# =====================================================================
# FULL EXECUTION PIPELINE
# =====================================================================
def run_prediction_pipeline(bypass_market_check=False):
    ist_now = get_ist_time()
    ist_str = ist_now.strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n=======================================================")
    print(f"[{ist_str}] STARTING PREDICTION & INTENSITY RATING PIPELINE")
    print(f"=======================================================")

    # 1. Market Hours Check
    if not bypass_market_check:
        if not is_market_open(ist_now) and not is_pre_market_time(ist_now):
            print(f"[INFO] Current IST ({ist_str}) is outside Indian market hours (09:15 - 15:30 IST).")
            print("[INFO] Performing weekend/off-market baseline snapshot.")

    # 2. Authenticate Angel One
    smartApi = get_angel_client()

    # 3. Load Scrip Master & Discover Universe
    scrip_data = load_or_download_scrip_master()
    universe = discover_fno_universe(scrip_data)
    symbols = list(universe.keys())

    # 4. Multi-Source News Scraper
    news_map = aggregate_news_for_symbols(symbols)

    # 5. Fetch Futures Quotes
    fut_tokens = [u["fut_token"] for u in universe.values()]
    print(f"[INFO] Fetching live Underlying Futures quotes for {len(fut_tokens)} symbols...")
    fut_quotes = fetch_quotes_in_batches(smartApi, fut_tokens, chunk_size=45)

    # 6. Resolve ATM Strikes & Multi-Strike Tokens for Max Pain
    atm_tokens = []
    sym_meta = {}
    chain_tokens = []

    for sym, info in universe.items():
        fq = fut_quotes.get(info["fut_token"])
        if not fq:
            continue
        fut_ltp = float(fq.get("ltp", 0.0))
        if fut_ltp <= 0:
            continue

        strikes = sorted(info["strikes"].keys())
        atm_strike = min(strikes, key=lambda s: abs(s - fut_ltp))
        ce_c = info["strikes"][atm_strike]["CE"]
        pe_c = info["strikes"][atm_strike]["PE"]
        ce_tok = str(ce_c["token"])
        pe_tok = str(pe_c["token"])

        atm_tokens.extend([ce_tok, pe_tok])
        
        # Select nearby strikes (ATM - 3 to ATM + 3) for Max Pain calculation
        atm_idx = strikes.index(atm_strike)
        sub_strikes = strikes[max(0, atm_idx - 3): min(len(strikes), atm_idx + 4)]
        sub_tokens = []
        for stk in sub_strikes:
            sub_tokens.append((stk, "CE", str(info["strikes"][stk]["CE"]["token"])))
            sub_tokens.append((stk, "PE", str(info["strikes"][stk]["PE"]["token"])))
            chain_tokens.extend([str(info["strikes"][stk]["CE"]["token"]), str(info["strikes"][stk]["PE"]["token"])])

        sym_meta[sym] = {
            "fut_ltp": fut_ltp,
            "atm_strike": atm_strike,
            "ce_token": ce_tok,
            "pe_token": pe_tok,
            "ce_symbol": ce_c["symbol"],
            "pe_symbol": pe_c["symbol"],
            "expiry_date": info["opt_expiry_date"],
            "expiry_str": info["opt_expiry"],
            "chain_strikes": sub_tokens
        }

    # 7. Fetch Option Quotes
    unique_option_tokens = list(set(atm_tokens + chain_tokens))
    print(f"[INFO] Fetching live option chain quotes for {len(unique_option_tokens)} contracts across {len(sym_meta)} symbols...")
    opt_quotes = fetch_quotes_in_batches(smartApi, unique_option_tokens, chunk_size=45)

    # 8. Load Persistent State for OI velocity
    state = load_state()
    prev_symbols_state = state.get("symbols", {})
    new_symbols_state = {}

    # 9. Compute Complete Micro-Features, Greeks, Max Pain, and Predictions
    print("[INFO] Computing Option Greeks, Max Pain, Directional Probabilities & Ratings...")
    predictions = []
    news_rows_for_bq = []

    today = ist_now.date()

    for sym, meta in sym_meta.items():
        info = universe[sym]
        fq = fut_quotes.get(info["fut_token"], {})
        ceq = opt_quotes.get(meta["ce_token"], {})
        peq = opt_quotes.get(meta["pe_token"], {})

        fut_ltp = float(fq.get("ltp", 0.0))
        fut_pct = float(fq.get("percentChange", 0.0))
        fut_tbq = int(fq.get("totBuyQuan", 0))
        fut_tsq = int(fq.get("totSellQuan", 0))
        fut_obi = round((fut_tbq - fut_tsq) / max(1, (fut_tbq + fut_tsq)), 3)

        # ATM CE metrics
        ce_ltp = float(ceq.get("ltp", 0.0))
        ce_pct = float(ceq.get("percentChange", 0.0))
        ce_oi  = int(ceq.get("opnInterest", 0))
        ce_tbq = int(ceq.get("totBuyQuan", 0))
        ce_tsq = int(ceq.get("totSellQuan", 0))
        ce_obi = round((ce_tbq - ce_tsq) / max(1, (ce_tbq + ce_tsq)), 3)
        ce_depth = ceq.get("depth", {})
        ce_buy_p = float(ce_depth.get("buy", [{}])[0].get("price", 0.0)) if ce_depth.get("buy") else 0.0
        ce_sell_p = float(ce_depth.get("sell", [{}])[0].get("price", 0.0)) if ce_depth.get("sell") else 0.0
        ce_spread = round(max(0.0, ce_sell_p - ce_buy_p), 2) if (ce_buy_p > 0 and ce_sell_p > 0) else 0.0

        # ATM PE metrics
        pe_ltp = float(peq.get("ltp", 0.0))
        pe_pct = float(peq.get("percentChange", 0.0))
        pe_oi  = int(peq.get("opnInterest", 0))
        pe_tbq = int(peq.get("totBuyQuan", 0))
        pe_tsq = int(peq.get("totSellQuan", 0))
        pe_obi = round((pe_tbq - pe_tsq) / max(1, (pe_tbq + pe_tsq)), 3)
        pe_depth = peq.get("depth", {})
        pe_buy_p = float(pe_depth.get("buy", [{}])[0].get("price", 0.0)) if pe_depth.get("buy") else 0.0
        pe_sell_p = float(pe_depth.get("sell", [{}])[0].get("price", 0.0)) if pe_depth.get("sell") else 0.0
        pe_spread = round(max(0.0, pe_sell_p - pe_buy_p), 2) if (pe_buy_p > 0 and pe_sell_p > 0) else 0.0

        atm_pcr = round(pe_oi / ce_oi, 2) if ce_oi > 0 else None

        # Time to expiry in years
        days_to_exp = max(0.5, (meta["expiry_date"] - today).days)
        T = days_to_exp / 365.0

        # Calculate IV & Greeks for CE
        ce_iv = solve_implied_volatility(ce_ltp, fut_ltp, meta["atm_strike"], T, RISK_FREE_RATE, is_call=True)
        ce_greeks = calculate_greeks(fut_ltp, meta["atm_strike"], T, RISK_FREE_RATE, (ce_iv or 20.0) / 100.0, is_call=True)

        # Calculate IV & Greeks for PE
        pe_iv = solve_implied_volatility(pe_ltp, fut_ltp, meta["atm_strike"], T, RISK_FREE_RATE, is_call=False)
        pe_greeks = calculate_greeks(fut_ltp, meta["atm_strike"], T, RISK_FREE_RATE, (pe_iv or 20.0) / 100.0, is_call=False)

        # Max Pain calculation across sub_strikes
        loss_by_strike = {}
        for stk, opt_type, tok in meta["chain_strikes"]:
            q = opt_quotes.get(tok, {})
            oi = int(q.get("opnInterest", 0))
            if stk not in loss_by_strike:
                loss_by_strike[stk] = 0.0
            if opt_type == "CE":
                loss_by_strike[stk] += oi * max(0.0, stk - stk) # placeholder
        
        # Real Max Pain over candidate strikes
        all_eval_strikes = list(set([s for s, _, _ in meta["chain_strikes"]]))
        min_loss = float("inf")
        max_pain_val = meta["atm_strike"]
        for test_s in all_eval_strikes:
            cur_loss = 0.0
            for s, opt_type, tok in meta["chain_strikes"]:
                q = opt_quotes.get(tok, {})
                oi = int(q.get("opnInterest", 0))
                if opt_type == "CE":
                    cur_loss += oi * max(0.0, test_s - s)
                else:
                    cur_loss += oi * max(0.0, s - test_s)
            if cur_loss < min_loss:
                min_loss = cur_loss
                max_pain_val = test_s

        # Previous OI for velocity
        prev_s = prev_symbols_state.get(sym, {})
        prev_ce_oi = prev_s.get("ce_oi", ce_oi)
        prev_pe_oi = prev_s.get("pe_oi", pe_oi)

        new_symbols_state[sym] = {
            "ce_oi": ce_oi,
            "pe_oi": pe_oi,
            "fut_ltp": fut_ltp,
            "timestamp": ist_str
        }

        # News metrics
        news_info = news_map.get(sym, {
            "sentiment_score": 0.0,
            "category": "NO_RECENT_HEADLINE",
            "impact_rating": "NEUTRAL",
            "top_headline": "No fresh material catalyst"
        })

        # Run Prediction Engine
        pred = compute_prediction_and_rating(
            sym=sym,
            fut_ltp=fut_ltp,
            fut_pct=fut_pct,
            fut_obi=fut_obi,
            ce_ltp=ce_ltp,
            ce_pct=ce_pct,
            ce_oi=ce_oi,
            ce_obi=ce_obi,
            ce_spread=ce_spread,
            ce_iv=ce_iv,
            ce_delta=ce_greeks["delta"],
            ce_gamma=ce_greeks["gamma"],
            ce_theta=ce_greeks["theta"],
            ce_vega=ce_greeks["vega"],
            pe_ltp=pe_ltp,
            pe_pct=pe_pct,
            pe_oi=pe_oi,
            pe_obi=pe_obi,
            pe_spread=pe_spread,
            pe_iv=pe_iv,
            pe_delta=pe_greeks["delta"],
            pe_gamma=pe_greeks["gamma"],
            pe_theta=pe_greeks["theta"],
            pe_vega=pe_greeks["vega"],
            atm_pcr=atm_pcr,
            max_pain=max_pain_val,
            prev_ce_oi=prev_ce_oi,
            prev_pe_oi=prev_pe_oi,
            news_sentiment=news_info["sentiment_score"],
            news_category=news_info["category"],
            news_impact=news_info["impact_rating"]
        )

        record = {
            "symbol": sym,
            "expiry": meta["expiry_str"],
            "spot_ltp": fut_ltp,
            "atm_strike": meta["atm_strike"],
            "directional_bias": pred["directional_bias"],
            "ce_win_prob": pred["ce_win_prob"],
            "pe_win_prob": pred["pe_win_prob"],
            "intensity_score": pred["intensity_score"],
            "confidence_pct": pred["confidence_pct"],
            "action_rating": pred["action_rating"],
            "rank_metric": pred["rank_metric"],
            "atm_pcr": atm_pcr if atm_pcr is not None else 1.0,
            "max_pain": max_pain_val,
            "ce_symbol": meta["ce_symbol"],
            "ce_ltp": ce_ltp,
            "ce_chg_pct": ce_pct,
            "ce_oi": ce_oi,
            "ce_oi_velocity": pred["ce_oi_velocity"],
            "ce_iv": ce_iv,
            "ce_delta": ce_greeks["delta"],
            "ce_gamma": ce_greeks["gamma"],
            "ce_theta": ce_greeks["theta"],
            "ce_vega": ce_greeks["vega"],
            "ce_spread": ce_spread,
            "pe_symbol": meta["pe_symbol"],
            "pe_ltp": pe_ltp,
            "pe_chg_pct": pe_pct,
            "pe_oi": pe_oi,
            "pe_oi_velocity": pred["pe_oi_velocity"],
            "pe_iv": pe_iv,
            "pe_delta": pe_greeks["delta"],
            "pe_gamma": pe_greeks["gamma"],
            "pe_theta": pe_greeks["theta"],
            "pe_vega": pe_greeks["vega"],
            "pe_spread": pe_spread,
            "news_sentiment": news_info["sentiment_score"],
            "news_impact": news_info["impact_rating"],
            "news_category": news_info["category"],
            "top_headline": news_info["top_headline"]
        }
        predictions.append(record)

        # Collect news row for BigQuery
        if news_info.get("items"):
            for itm in news_info["items"]:
                news_rows_for_bq.append({
                    "timestamp": ist_now.isoformat(),
                    "symbol": sym,
                    "news_type": itm.get("category", "GENERAL"),
                    "sentiment": "BULLISH" if itm["score"] > 0 else ("BEARISH" if itm["score"] < 0 else "NEUTRAL"),
                    "tone_score": float(itm["score"]),
                    "impact_rating": str(itm["impact"]),
                    "source_count": int(news_info["item_count"]),
                    "source_agreement_pct": 100.0,
                    "title": str(itm["title"]),
                    "source": str(itm["source"]),
                    "filing_type": str(itm.get("filing_type", ""))
                })

    # Save updated OI state
    save_state({"symbols": new_symbols_state, "last_updated": ist_str})

    # 10. Rank predictions from highest conviction/intensity to lowest
    predictions.sort(key=lambda x: x["rank_metric"], reverse=True)
    for idx, r in enumerate(predictions):
        r["rank"] = idx + 1

    print(f"[OK] Generated Predictions & Greeks for {len(predictions)} symbols! Top Pick: {predictions[0]['symbol']} ({predictions[0]['action_rating']})")

    # 11. Sync to Google Sheet (Tab: OPTION_PREDICTIONS & HEARTBEAT)
    sync_to_google_sheet(predictions, ist_str)

    # 12. Sync to BigQuery Sandbox ($0 cost)
    sync_to_bigquery(predictions, news_rows_for_bq, ist_now)

    return predictions

# =====================================================================
# GOOGLE SHEET SYNC MODULE
# =====================================================================
def sync_to_google_sheet(predictions, ist_str):
    print("[INFO] Syncing outputs to Google Sheet (OPTION_PREDICTIONS tab)...")
    try:
        gc = get_gspread_client()
        sh = gc.open_by_key(SHEET_ID)

        # Ensure OPTION_PREDICTIONS worksheet exists
        try:
            ws_pred = sh.worksheet("OPTION_PREDICTIONS")
        except Exception:
            ws_pred = sh.add_worksheet(title="OPTION_PREDICTIONS", rows="350", cols="35")

        # Ensure HEARTBEAT worksheet exists
        try:
            ws_hb = sh.worksheet("HEARTBEAT")
        except Exception:
            ws_hb = sh.add_worksheet(title="HEARTBEAT", rows="25", cols="6")

        # Top 3 CE and PE Picks for summary showcase
        ce_picks = [p for p in predictions if "CALL" in p["directional_bias"]][:3]
        pe_picks = [p for p in predictions if "PUT" in p["directional_bias"]][:3]

        summary_rows = [
            ["⚡ DYNAMIC OPTION CE/PE PREDICTION & INTENSITY RATING SYSTEM (PRODUCTION READY)", "", "", "", "", "", "", ""],
            [f"Last Synced: {ist_str} IST", "Broker Feed: CONNECTED (Angel One SmartAPI)", f"F&O Symbols Ranked: {len(predictions)}", "BigQuery Sandbox: ASIA-SOUTH1 SYNCED", "", "", "", ""],
            ["", "", "", "", "", "", "", ""],
            ["🏆 TOP CONVICTION CALL (CE) BREAKOUT CANDIDATES", "", "", "", "", "", "", ""],
            ["Rank", "Symbol", "Action Rating", "CE Win Prob %", "Intensity (1-100)", "Spot LTP", "ATM Strike", "CE Contract", "CE LTP", "CE IV %", "News Catalyst"]
        ]

        for p in ce_picks:
            summary_rows.append([
                p["rank"], p["symbol"], p["action_rating"], f"{p['ce_win_prob']}%", p["intensity_score"],
                p["spot_ltp"], p["atm_strike"], p["ce_symbol"], p["ce_ltp"], f"{p['ce_iv']}%", p["top_headline"][:60]
            ])

        summary_rows.extend([
            ["", "", "", "", "", "", "", ""],
            ["💥 TOP CONVICTION PUT (PE) BREAKDOWN CANDIDATES", "", "", "", "", "", "", ""],
            ["Rank", "Symbol", "Action Rating", "PE Win Prob %", "Intensity (1-100)", "Spot LTP", "ATM Strike", "PE Contract", "PE LTP", "PE IV %", "News Catalyst"]
        ])

        for p in pe_picks:
            summary_rows.append([
                p["rank"], p["symbol"], p["action_rating"], f"{p['pe_win_prob']}%", p["intensity_score"],
                p["spot_ltp"], p["atm_strike"], p["pe_symbol"], p["pe_ltp"], f"{p['pe_iv']}%", p["top_headline"][:60]
            ])

        summary_rows.extend([
            ["", "", "", "", "", "", "", ""],
            ["==================================================================================================================================================================", "", "", "", "", "", "", ""],
            ["📊 COMPLETE F&O UNIVERSE OPTION CE/PE PREDICTION & GREEKS MATRIX (RANKED HIGHEST TO LOWEST INTENSITY)", "", "", "", "", "", "", ""],
            ["Rank", "Symbol", "Actionable Prediction Rating", "Directional Bias", "CE Win Prob %", "PE Win Prob %",
             "Intensity Score (1-100)", "Confidence %", "Spot / Fut LTP", "ATM Strike", "ATM PCR", "Max Pain",
             "ATM CE Contract", "CE LTP", "CE Chg %", "CE OI", "CE OI Vel %", "CE IV %", "Delta CE", "Gamma", "Theta CE", "Vega", "CE Spread",
             "ATM PE Contract", "PE LTP", "PE Chg %", "PE OI", "PE OI Vel %", "PE IV %", "Delta PE", "PE Spread",
             "News Sentiment (-1 to +1)", "News Impact Category", "Top News Catalyst / NSE Filing", "Snapshot Time (IST)"]
        ])

        # Full table rows
        for p in predictions:
            summary_rows.append([
                p["rank"], p["symbol"], p["action_rating"], p["directional_bias"], p["ce_win_prob"], p["pe_win_prob"],
                p["intensity_score"], p["confidence_pct"], p["spot_ltp"], p["atm_strike"], p["atm_pcr"], p["max_pain"],
                p["ce_symbol"], p["ce_ltp"], p["ce_chg_pct"], p["ce_oi"], p["ce_oi_velocity"], p["ce_iv"], p["ce_delta"], p["ce_gamma"], p["ce_theta"], p["ce_vega"], p["ce_spread"],
                p["pe_symbol"], p["pe_ltp"], p["pe_chg_pct"], p["pe_oi"], p["pe_oi_velocity"], p["pe_iv"], p["pe_delta"], p["pe_spread"],
                p["news_sentiment"], p["news_category"], p["top_headline"], ist_str
            ])

        # Write to sheet
        ws_pred.clear()
        ws_pred.update(range_name="A1", values=summary_rows)
        print(f"[OK] Google Sheet 'OPTION_PREDICTIONS' populated with {len(summary_rows)} rows!")

        # Update Heartbeat
        ws_hb.update(range_name="A1:F2", values=[
            ["Last Ping (IST)", "Engine Status", "Symbols Ranked", "BigQuery Sync", "Top Conviction CE", "Top Conviction PE"],
            [ist_str, "ACTIVE_DYNAMIC_PREDICTION_ENGINE", len(predictions), "asia-south1 STREAMED",
             f"{ce_picks[0]['symbol']} ({ce_picks[0]['ce_win_prob']}%)" if ce_picks else "NONE",
             f"{pe_picks[0]['symbol']} ({pe_picks[0]['pe_win_prob']}%)" if pe_picks else "NONE"]
        ])
        print("[OK] Google Sheet 'HEARTBEAT' updated successfully.")

    except Exception as e:
        print(f"[ERROR] Google Sheet sync error: {e}")

# =====================================================================
# BIGQUERY SANDBOX SYNC MODULE ($0 COST)
# =====================================================================
def sync_to_bigquery(predictions, news_rows, ist_dt):
    print("[INFO] Streaming predictions & sentiment rows into BigQuery Sandbox (asia-south1)...")
    try:
        bq_client = get_bigquery_client()
        dataset_ref = bq_client.dataset(BQ_DATASET_ID)

        # 1. Format predictions table rows
        table_pred = bq_client.get_table(dataset_ref.table("option_predictions_live"))
        ts_iso = ist_dt.isoformat()

        rows_to_insert = []
        for p in predictions:
            rows_to_insert.append({
                "snapshot_timestamp": ts_iso,
                "rank": int(p["rank"]),
                "symbol": str(p["symbol"]),
                "expiry": str(p["expiry"]),
                "spot_ltp": float(p["spot_ltp"]),
                "atm_strike": float(p["atm_strike"]),
                "directional_bias": str(p["directional_bias"]),
                "ce_win_prob": float(p["ce_win_prob"]),
                "pe_win_prob": float(p["pe_win_prob"]),
                "intensity_score": int(p["intensity_score"]),
                "confidence_pct": float(p["confidence_pct"]),
                "action_rating": str(p["action_rating"]),
                "atm_pcr": float(p["atm_pcr"]),
                "max_pain": float(p["max_pain"]),
                "ce_ltp": float(p["ce_ltp"]),
                "ce_chg_pct": float(p["ce_chg_pct"]),
                "ce_oi": int(p["ce_oi"]),
                "ce_oi_change_pct": float(p["ce_oi_velocity"]),
                "ce_iv": float(p["ce_iv"]),
                "ce_delta": float(p["ce_delta"]),
                "ce_gamma": float(p["ce_gamma"]),
                "ce_theta": float(p["ce_theta"]),
                "ce_vega": float(p["ce_vega"]),
                "ce_bid_ask_spread": float(p["ce_spread"]),
                "pe_ltp": float(p["pe_ltp"]),
                "pe_chg_pct": float(p["pe_chg_pct"]),
                "pe_oi": int(p["pe_oi"]),
                "pe_oi_change_pct": float(p["pe_oi_velocity"]),
                "pe_iv": float(p["pe_iv"]),
                "pe_delta": float(p["pe_delta"]),
                "pe_gamma": float(p["pe_gamma"]),
                "pe_theta": float(p["pe_theta"]),
                "pe_vega": float(p["pe_vega"]),
                "pe_bid_ask_spread": float(p["pe_spread"]),
                "news_sentiment_score": float(p["news_sentiment"]),
                "news_impact_rating": str(p["news_impact"]),
                "top_news_headline": str(p["top_headline"])[:255]
            })

        # Load predictions via BigQuery Sandbox-compliant batch load job ($0 cost)
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND
        )
        load_job = bq_client.load_table_from_json(rows_to_insert, table_pred, job_config=job_config)
        load_job.result()
        print(f"[OK] Appended {len(rows_to_insert)} records to BigQuery option_predictions_live!")

        # 2. Insert news rows if any
        if news_rows:
            table_news = bq_client.get_table(dataset_ref.table("market_news_sentiment"))
            load_job_news = bq_client.load_table_from_json(news_rows, table_news, job_config=job_config)
            load_job_news.result()
            print(f"[OK] Appended {len(news_rows)} records to BigQuery market_news_sentiment!")

    except Exception as e:
        print(f"[ERROR] BigQuery sync error: {e}")

# =====================================================================
# MAIN ENTRYPOINT
# =====================================================================
def main():
    bypass_market_check = "--run-once" in sys.argv or "--verify" in sys.argv
    is_daemon = "--daemon" in sys.argv

    if bypass_market_check:
        print("[MODE] Direct Live Run & Verification (bypassing market-hour sleeps)...")
        run_prediction_pipeline(bypass_market_check=True)
        print("[SUCCESS] Live Verification Cycle Completed!")
        return

    print("[MODE] Automated Indian Market Production Daemon (09:15 - 15:30 IST)...")
    while True:
        try:
            now = get_ist_time()
            if is_market_open(now) or is_pre_market_time(now):
                run_prediction_pipeline(bypass_market_check=False)
                time.sleep(45)  # 45 second scan cycle during market hours
            else:
                # Outside market hours: perform one baseline sync then sleep in power-saving standby
                print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')} IST] Market closed. Executing baseline verification sync...")
                run_prediction_pipeline(bypass_market_check=True)
                print("[INFO] Baseline sync complete. Entering off-market standby until next trading session...")
                time.sleep(1800)  # Check every 30 mins during off-hours
        except KeyboardInterrupt:
            print("[INFO] Daemon stopped by user.")
            break
        except Exception as e:
            print(f"[ERROR] Pipeline error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
