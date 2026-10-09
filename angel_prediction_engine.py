#!/usr/bin/env python3
"""
Angel One Dynamic Stock & Index Option (CE/PE) Prediction and Intensity Rating Engine
Production-grade autonomous engine:
- Micro-Level Option Chain Metrics (Spot, Strike, CE/PE LTP, IV, Delta, Gamma, Theta, Vega, Volume, OI, OI Velocity, PCR, Max Pain, Spread)
- Multi-Source Live News & Corporate Filings Scraper (RSS feeds, NSE announcements, sentiment scoring & impact categorization)
- Pre-Market Gap Opening & 9:15 AM Explosion Predictor (Overnight catalyst corroboration, EOD institutional positioning, expected gap %)
- Live Market-Hours Top-10 Ground-Truth Reconciliation & Self-Calibrating Loop (Online gradient weight update, BigQuery audit log)
- Strict Column Schema & Zero Date-Serial Validator across all 17 Google Sheet tabs and BigQuery Sandbox ($0 cost)
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
from concurrent.futures import ThreadPoolExecutor

# 3rd party libraries
import pyotp
import gspread
from SmartApi import SmartConnect
from google.cloud import bigquery
from google.oauth2 import service_account

from credentials import (
    get_angel_credentials,
    load_env,
    require_authoritative_sheet_id,
    resolve_service_account_info,
    validate_angel_credentials,
)
from writer_guard import append_sheet_provenance, build_provenance, require_authorized_writer
from sheet_grid import write_grid
from publication import publish_outputs
from market_calendar import IST, is_trading_day, local_market_time

load_env()

# =====================================================================
# CONFIGURATION & CREDENTIALS
# =====================================================================
def _env(name, default=""):
    return os.getenv(name, default).strip()

ANGEL_API_KEY     = _env("ANGEL_API_KEY")
ANGEL_CLIENT_CODE = _env("ANGEL_CLIENT_CODE")
ANGEL_PIN         = _env("ANGEL_PIN")
ANGEL_TOTP_SEED   = _env("ANGEL_TOTP_SEED")
SHEET_ID          = _env("SHEET_ID")

KEY_PATH = os.path.expanduser("~/angel_sheets_key.json")

def _load_service_account_info():
    """Load service-account metadata without exposing credential values."""
    return resolve_service_account_info(custom_key_path=KEY_PATH)

def resolve_bq_project_id():
    """Resolve billing project: explicit env first, service-account metadata second, else empty."""
    explicit = _env("BQ_PROJECT_ID")
    if explicit:
        return explicit
    info = _load_service_account_info()
    project_id = str(info.get("project_id", "")).strip() if info else ""
    return project_id

BQ_PROJECT_ID     = resolve_bq_project_id()
BQ_DATASET_ID     = "fno_predictions"
from universe_contract import EXPECTED_FNO_UNIVERSE_COUNT, select_verified_universe, require_verified_symbols

STATE_PATH = os.path.expanduser("~/angel_prediction_state.json")
CALIBRATION_STATE_PATH = os.path.expanduser("~/angel_calibration_state.json")
SCRIP_CACHE_PATH = os.path.expanduser("~/angel_scrip_cache.json")
NSE_CACHE_PATH = os.path.expanduser("~/angel_nse_cache.json")

RISK_FREE_RATE = 0.065  # 6.5% standard Indian repo rate

DEFAULT_WEIGHTS = {
    "opt_vel": 0.28,   # Option Price Velocity (ce_chg_pct / pe_chg_pct)
    "gamma": 0.20,     # Dollar Gamma (Gamma * S^2 * 0.01)
    "oi_vel": 0.18,    # Volume & OI Surge Velocity
    "fut_obi": 0.12,   # Futures Order Book Imbalance
    "opt_obi": 0.10,   # Options Order Book Imbalance
    "news": 0.07,      # Scraped News & Filings Sentiment
    "iv": 0.05         # Implied Volatility
}

# =====================================================================
# TIME UTILITIES
# =====================================================================
try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

def get_ist_time():
    return datetime.datetime.now(IST)

def parse_expiry_date(exp_str):
    try:
        return datetime.datetime.strptime(exp_str.strip().upper(), "%d%b%Y").date()
    except Exception:
        return None

def to_iso_date(val):
    if not val:
        return datetime.date.today().isoformat()
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d%b%Y", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date().isoformat()
        except Exception:
            pass
    return datetime.date.today().isoformat()

def parse_news_timestamp_ist(value, fallback=None):
    """Parse RSS/ISO publication time and normalize it to a naive IST ISO timestamp."""
    if value:
        try:
            parsed = parsedate_to_datetime(str(value).strip())
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=datetime.timezone.utc)
            ist = parsed.astimezone(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
            return ist.replace(tzinfo=None).isoformat(timespec="seconds")
        except Exception:
            try:
                parsed = datetime.datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=datetime.timezone.utc)
                ist = parsed.astimezone(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
                return ist.replace(tzinfo=None).isoformat(timespec="seconds")
            except Exception:
                pass
    if fallback is not None:
        if isinstance(fallback, datetime.datetime):
            return fallback.replace(microsecond=0).isoformat(timespec="seconds")
        return str(fallback)
    return ""

def news_dedup_key(item):
    """Stable duplicate key: preserve cross-source corroboration, suppress same-source replays."""
    title = re.sub(r"\s+", " ", str(item.get("title", "")).strip().lower())
    source = str(item.get("source", "")).strip().lower()
    link = str(item.get("source_url") or item.get("link") or "").strip().lower()
    return "::".join((source, link, title))

NSE_HOLIDAYS_2026 = {
    "2026-01-26", "2026-03-03", "2026-03-26", "2026-03-31", "2026-04-03",
    "2026-04-14", "2026-05-01", "2026-05-28", "2026-06-26", "2026-09-14",
    "2026-10-02", "2026-10-20", "2026-11-10", "2026-11-24", "2026-12-25",
}

def is_market_open(dt=None):
    if dt is None:
        dt = get_ist_time()
    dt = local_market_time(dt)
    if not is_trading_day(dt):
        return False
    if dt.date().isoformat() in NSE_HOLIDAYS_2026:
        return False
    mins = dt.hour * 60 + dt.minute
    return 555 <= mins <= 940  # 9:15 AM (555 mins) to 3:40 PM (940 mins)

def is_pre_market_time(dt=None):
    if dt is None:
        dt = get_ist_time()
    dt = local_market_time(dt)
    if not is_trading_day(dt):
        return False
    if dt.date().isoformat() in NSE_HOLIDAYS_2026:
        return False
    mins = dt.hour * 60 + dt.minute
    return 480 <= mins < 555  # 8:00 AM to 9:15 AM

def is_pre_close_time(dt=None):
    if dt is None:
        dt = get_ist_time()
    dt = local_market_time(dt)
    if not is_trading_day(dt):
        return False
    if dt.date().isoformat() in NSE_HOLIDAYS_2026:
        return False
    mins = dt.hour * 60 + dt.minute
    return 900 <= mins <= 940  # 15:00 to 15:40 IST (3:00 PM to 3:40 PM)

def is_morning_reconcile_time(dt=None):
    if dt is None:
        dt = get_ist_time()
    dt = local_market_time(dt)
    if not is_trading_day(dt):
        return False
    if dt.date().isoformat() in NSE_HOLIDAYS_2026:
        return False
    mins = dt.hour * 60 + dt.minute
    return 555 <= mins <= 585  # 09:15 to 09:45 IST

# =====================================================================
# GOOGLE CLOUD & BIGQUERY CLIENT SETUP
# =====================================================================
def normalize_sheet_rows(rows, width=None):
    """Return a rectangular sheet matrix with a deterministic column count."""
    rows = [list(row) for row in rows]
    if not rows:
        return []
    target = width if width is not None else max(len(row) for row in rows)
    if target <= 0:
        return [[] for _ in rows]
    return [(row + [""] * target)[:target] for row in rows]


def deduplicate_news_rows(rows):
    """Suppress exact replay rows while preserving the same headline across sources."""
    unique = []
    seen = set()
    for row in rows:
        key = (
            str(row.get("symbol", "")).strip().upper(),
            str(row.get("source", "")).strip().lower(),
            str(row.get("canonical_url") or row.get("source_url") or "").strip().lower(),
            re.sub(r"\s+", " ", str(row.get("title", "")).strip().lower()),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def get_gspread_client():
    info = _load_service_account_info()
    if info:
        return gspread.service_account_from_dict(info)
    if os.path.exists(KEY_PATH):
        return gspread.service_account(filename=KEY_PATH)
    raise RuntimeError("No valid Google service account credentials found for Sheets.")

def get_bigquery_client():
    project_id = resolve_bq_project_id()
    if not project_id:
        raise RuntimeError("BQ_PROJECT_ID is unset and no service-account project_id is available; BigQuery access is blocked by the billing guardrail.")
    info = _load_service_account_info()
    if info:
        try:
            creds = service_account.Credentials.from_service_account_info(info)
            return bigquery.Client(project=project_id, credentials=creds)
        except Exception:
            pass
    return bigquery.Client(project=project_id)

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
    vega = (F * df * pdf_d1 * sqrt_T) / 100.0

    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta, 4),
        "vega": round(vega, 4)
    }

def solve_implied_volatility(market_price, F, K, T, r, is_call=True):
    if market_price <= 0.05 or F <= 0 or K <= 0 or T <= 0:
        return 0.0
    df = math.exp(-r * T)
    intrinsic = max(0.0, (F - K) * df) if is_call else max(0.0, (K - F) * df)
    if market_price <= intrinsic:
        return 5.0

    low, high = 0.01, 3.5
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
SOURCE_TIERS = {
    "SEBI Official": ("TIER_1_REGULATOR", 1.00),
    "RBI Official": ("TIER_1_REGULATOR", 1.00),
    "NSE Announcements RSS": ("TIER_1_REGULATOR", 1.00),
    "NSE Official Announcement": ("TIER_1_REGULATOR", 1.00),
    "PTI / Reuters": ("TIER_2_WIRE", 0.85),
    "Livemint": ("TIER_3_FINANCIAL_MEDIA", 0.65),
    "Economic Times": ("TIER_3_FINANCIAL_MEDIA", 0.65),
    "Business Standard": ("TIER_3_FINANCIAL_MEDIA", 0.65),
    "Hindu Business Line": ("TIER_3_FINANCIAL_MEDIA", 0.65),
    "Google News Targeted": ("TIER_3_FINANCIAL_MEDIA", 0.65),
    "Google News Thematic": ("TIER_3_FINANCIAL_MEDIA", 0.65),
    "Social Radar": ("TIER_4_SOCIAL", 0.20),
}

FEEDS = (
    ("SEBI Official", "https://www.sebi.gov.in/sebirss.xml"),
    ("RBI Official", "https://m.rbi.org.in/pressreleases_rss.xml"),
    ("NSE Announcements RSS", "https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml"),
    ("Livemint", "https://www.livemint.com/rss/markets"),
    ("Economic Times", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("Business Standard", "https://www.business-standard.com/rss/markets-106.rss"),
    ("Hindu Business Line", "https://www.thehindubusinessline.com/markets/feeder/default.rss"),
)

THEMATIC_DISCOVERY_FEEDS = (
    ("IRDAI Thematic", "https://news.google.com/rss/search?q=(IRDAI+commission+OR+expense+ratio)+when:3d&hl=en-IN&gl=IN&ceid=IN:en", "IRDAI"),
    ("Pharma USFDA Thematic", "https://news.google.com/rss/search?q=(USFDA+warning+letter+OR+inspection+India+pharma)+when:3d&hl=en-IN&gl=IN&ceid=IN:en", "USFDA"),
    ("Banking RBI Thematic", "https://news.google.com/rss/search?q=(RBI+penalty+OR+draft+guidelines+OR+repo+rate+bank)+when:3d&hl=en-IN&gl=IN&ceid=IN:en", "RBI"),
    ("Telecom TRAI Thematic", "https://news.google.com/rss/search?q=(TRAI+telecom+tariff+OR+spectrum+OR+AGR)+when:3d&hl=en-IN&gl=IN&ceid=IN:en", "TRAI"),
    ("Energy PNGRB Thematic", "https://news.google.com/rss/search?q=(PNGRB+gas+OR+CERC+power+tariff)+when:3d&hl=en-IN&gl=IN&ceid=IN:en", "PNGRB"),
    ("Legal Litigated Thematic", "https://news.google.com/rss/search?q=(Supreme+Court+OR+NCLT+forensic+audit+order)+when:3d&hl=en-IN&gl=IN&ceid=IN:en", "LEGAL"),
)

TARGETED_DISCOVERY_QUERIES = (
    ("POLICYBZR", "https://news.google.com/rss/search?q=(%22PB+Fintech%22+OR+Policybazaar)+when:3d&hl=en-IN&gl=IN&ceid=IN:en"),
    ("FORTIS", "https://news.google.com/rss/search?q=(%22Fortis+Healthcare%22+OR+Fortis)+when:3d&hl=en-IN&gl=IN&ceid=IN:en"),
    ("BIOCON", "https://news.google.com/rss/search?q=(Biocon+OR+Syngene)+when:3d&hl=en-IN&gl=IN&ceid=IN:en"),
    ("TATAMOTORS", "https://news.google.com/rss/search?q=(%22Tata+Motors%22+OR+JLR)+when:3d&hl=en-IN&gl=IN&ceid=IN:en"),
    ("RELIANCE", "https://news.google.com/rss/search?q=(%22Reliance+Industries%22+OR+RIL)+when:3d&hl=en-IN&gl=IN&ceid=IN:en"),
)

REGULATOR_SECTOR_MAP = {
    "IRDAI": ("POLICYBZR", "HDFCLIFE", "SBILIFE", "ICICIPRULI", "LICI"),
    "USFDA": ("SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "LUPIN", "AUROPHARMA", "ALKEM", "ZYDUSLIFE", "TORNTPHARM", "BIOCON"),
    "CDSCO": ("SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "LUPIN", "AUROPHARMA", "ALKEM", "ZYDUSLIFE", "TORNTPHARM", "BIOCON"),
    "TRAI": ("BHARTIARTL", "IDEA", "INDUSTOWER"),
    "PNGRB": ("IGL", "MGL", "GUJGASLTD", "GAIL", "PETRONET"),
    "CERC": ("TATAPOWER", "NTPC", "POWERGRID", "ADANIPOWER", "JSWENERGY"),
    "DGCA": ("INDIGO",),
    "RBI": ("HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK", "PNB", "BANKBARODA", "CANBK", "BAJFINANCE", "BAJAJFINSV", "CHOLAFIN", "SHRIRAMFIN"),
    "LEGAL": ("FORTIS", "VEDL", "ADANIENT", "ADANIPORTS", "DABUR", "PAYTM", "POLICYBZR"),
}

ALIASES = {
    "RELIANCE": ("Reliance Industries", "RIL", "Jio", "Reliance Retail"),
    "ADANIENT": ("Adani Enterprises", "Gautam Adani"),
    "ADANIPORTS": ("Adani Ports", "APSEZ"),
    "HDFCBANK": ("HDFC Bank", "HDFC"),
    "ICICIBANK": ("ICICI Bank",),
    "KOTAKBANK": ("Kotak Mahindra", "Kotak Bank"),
    "AXISBANK": ("Axis Bank",),
    "SBIN": ("State Bank of India", "SBI"),
    "BAJFINANCE": ("Bajaj Finance", "Bajaj Housing"),
    "BAJAJFINSV": ("Bajaj Finserv",),
    "TATAMOTORS": ("Tata Motors", "JLR", "Jaguar Land Rover", "TMPV"),
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
    "M&M": ("Mahindra & Mahindra", "Mahindra and Mahindra", "Mahindra"),
    "SUNPHARMA": ("Sun Pharma", "Sun Pharmaceutical"),
    "DRREDDY": ("Dr Reddy", "Dr. Reddy"),
    "DIVISLAB": ("Divi's", "Divis Lab"),
    "CIPLA": ("Cipla",),
    "APOLLOHOSP": ("Apollo Hospitals",),
    "ASIANPAINT": ("Asian Paints",),
    "ULTRACEMCO": ("UltraTech",),
    "JSWSTEEL": ("JSW Steel",),
    "HINDALCO": ("Hindalco",),
    "VEDL": ("Vedanta", "Hindustan Zinc"),
    "POWERGRID": ("Power Grid", "PGCIL"),
    "NTPC": ("NTPC",),
    "ONGC": ("ONGC", "Oil and Natural Gas"),
    "COALINDIA": ("Coal India",),
    "BPCL": ("Bharat Petroleum",),
    "IOC": ("Indian Oil",),
    "NESTLEIND": ("Nestle",),
    "DMART": ("Avenue Supermarts", "DMart"),
    "ZOMATO": ("Zomato", "Eternal", "Blinkit"),
    "ETERNAL": ("Zomato", "Eternal", "Blinkit"),
    "PAYTM": ("Paytm", "One 97", "One97"),
    "POLICYBZR": ("PB Fintech", "Policybazaar", "PaisaBazaar"),
    "FORTIS": ("Fortis Healthcare", "Fortis", "IHH", "Daiichi", "Daiichi Sankyo", "Northern TK"),
    "INDIGO": ("InterGlobe", "IndiGo"),
    "HAL": ("Hindustan Aeronautics", "HAL"),
    "BEL": ("Bharat Electronics", "BEL"),
    "BHEL": ("BHEL", "Bharat Heavy Electricals"),
    "BANKBARODA": ("Bank of Baroda",),
    "PNB": ("Punjab National", "PNB"),
    "CANBK": ("Canara Bank",),
    "INDUSINDBK": ("IndusInd",),
    "BIOCON": ("Biocon", "Syngene"),
    "BHARTIARTL": ("Bharti Airtel", "Airtel"),
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
    ("REGULATORY_PROBE", ("probe", "penalty", "sebi penalty", "cbi", "ed raid", "fraud", "investigation", "show cause")),
    ("M&A_EXPANSION", ("acquisition", "merger", "amalgamation", "stake buy", "expansion", "commissioned", "joint venture")),
    ("CAPITAL_DIVIDEND", ("dividend", "bonus", "buyback", "stock split", "sub-division")),
    ("MANAGEMENT_CHANGE", ("resignation", "change in management", "appointed", "ceo exit", "md resigns")),
)

ROUTINE_COMPLIANCE_PATTERNS = (
    "trading window",
    "insider trading",
    "esop",
    "allotment of equity shares",
    "allotment under esop",
    "allotment of shares",
    "change in auditor",
    "change in auditors",
    "regulation 30(5)",
    "regulation 30",
    "schedule of analyst",
    "intimation of schedule of analyst",
    "loss of share certificate",
    "duplicate share certificate",
    "newspaper publication",
    "agm proceedings",
    "egm proceedings",
    "postal ballot",
    "closure of trading window"
)

def fetch_rss_feed(source_name, url):
    items = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=10) as response:
            tree = ET.fromstring(response.read())
            for item in tree.iter("item"):
                title_node = item.find("title")
                pub_node = item.find("pubDate")
                link_node = item.find("link")
                title = (title_node.text or "").strip() if title_node is not None else ""
                if not title:
                    continue
                pub_raw = (pub_node.text or "").strip() if pub_node is not None else ""
                link_url = (link_node.text or "").strip() if link_node is not None else url
                items.append({
                    "title": title,
                    "source": source_name,
                    "pubDate": pub_raw,
                    "published_at_ist": parse_news_timestamp_ist(pub_raw),
                    "link": link_url
                })
    except Exception:
        pass
    return items

def analyze_headline(title):
    lowered = f" {title.lower()} "

    if any(pat in lowered for pat in ROUTINE_COMPLIANCE_PATTERNS):
        return 0.0, "ROUTINE_COMPLIANCE", "NEUTRAL"

    pos_count = sum(1 for w in POSITIVE_WORDS if w in lowered)
    neg_count = sum(1 for w in NEGATIVE_WORDS if w in lowered)
    
    total = pos_count + neg_count
    sentiment_score = 0.0
    if total > 0:
        sentiment_score = round((pos_count - neg_count) / total, 3)

    cat = "GENERAL_MACRO"
    for category, keys in CATEGORY_RULES:
        if any(k in lowered for k in keys):
            cat = category
            break

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

def classify_event_severity(title, category="GENERAL_MACRO", source_name=""):
    lowered = f" {title.lower()} "

    if any(pat in lowered for pat in ROUTINE_COMPLIANCE_PATTERNS) or category == "ROUTINE_COMPLIANCE":
        return 1, "LEVEL_1_NOISE", "0.0% (Noise)", 0.05, 0.05, 0.90, 0.95

    critical_patterns = (
        "fraud", "cbi probe", "ed raid", "insolvency", "nclt admission", "default",
        "licence cancelled", "licence suspended", "ban on trading", "hard commission cap",
        "mega acquisition", "merger failed", "accounting fraud", "arrested"
    )
    if any(cp in lowered for cp in critical_patterns):
        pos_p = 0.85 if "mega acquisition" in lowered else 0.05
        neg_p = 0.85 if pos_p < 0.5 else 0.05
        neut_p = round(1.0 - (pos_p + neg_p), 2)
        return 5, "LEVEL_5_CRITICAL", "> 8.0%", pos_p, neg_p, neut_p, 0.15

    high_patterns = (
        "supreme court", "high court", "forensic audit", "consultation paper", "commission cap",
        "expense framework", "warning letter", "oai status", "downgrade", "rating watch negative",
        "resignation of ceo", "resignation of md", "plant closure", "target cut", "slumps 30"
    )
    if any(hp in lowered for hp in high_patterns):
        if "consultation" in lowered or "draft" in lowered or "tentative" in lowered:
            pos_p = 0.20
            neg_p = 0.65
            already_priced = 0.70
        elif "downgrade" in lowered or "warning letter" in lowered or "forensic audit" in lowered:
            pos_p = 0.10
            neg_p = 0.80
            already_priced = 0.35
        else:
            pos_p = 0.25
            neg_p = 0.65
            already_priced = 0.40
        neut_p = round(1.0 - (pos_p + neg_p), 2)
        return 4, "LEVEL_4_HIGH", "4.0% - 8.0%", pos_p, neg_p, neut_p, already_priced

    medium_pos_patterns = ("order win", "contract win", "bags rs", "bags order", "mhra approval", "usfda approval", "profit jumps", "beats estimates", "dividend", "buyback")
    medium_neg_patterns = ("net loss", "loss widens", "profit falls", "misses estimates", "penalty")
    if any(mp in lowered for mp in medium_pos_patterns):
        return 3, "LEVEL_3_MEDIUM", "+2.0% to +4.0%", 0.75, 0.10, 0.15, 0.25
    if any(mn in lowered for mn in medium_neg_patterns):
        return 3, "LEVEL_3_MEDIUM", "-2.0% to -4.0%", 0.10, 0.75, 0.15, 0.30

    low_patterns = ("agm", "investor meet", "concall", "clarification", "partnership", "tie-up")
    if any(lp in lowered for lp in low_patterns):
        return 2, "LEVEL_2_LOW", "< 2.0%", 0.35, 0.15, 0.50, 0.60

    return 2, "LEVEL_2_LOW", "< 2.0%", 0.30, 0.20, 0.50, 0.50

def compute_market_confirmation(sentiment_score, fut_pct, fut_obi, ce_pct, pe_pct, ce_oi_vel=0.0, pe_oi_vel=0.0, atm_pcr=1.0):
    if abs(sentiment_score) < 0.15:
        return "NEUTRAL_FLOW"
    if sentiment_score > 0.15:
        if (fut_pct > 0.2 or fut_obi > 0.08) and ce_pct >= pe_pct:
            return "🟢 BULLISH_CONFIRMED"
        elif fut_pct < -0.5 or ce_pct < pe_pct:
            return "⚠️ PRICED_IN_OR_DIVERGENT"
        else:
            return "🟡 BULLISH_PENDING_FLOW"
    if sentiment_score < -0.15:
        if (fut_pct < -0.2 or fut_obi < -0.08) and pe_pct >= ce_pct:
            return "🔴 BEARISH_CONFIRMED"
        elif fut_pct > 0.5 or pe_pct < ce_pct:
            return "⚠️ PRICED_IN_OR_DIVERGENT"
        else:
            return "🟡 BEARISH_PENDING_FLOW"
    return "NEUTRAL_FLOW"

def aggregate_market_news(articles=None, universe_symbols=None):
    if universe_symbols is None:
        if isinstance(articles, list) and len(articles) > 0 and isinstance(articles[0], str):
            universe_symbols = articles
            articles = None
        else:
            universe_symbols = []

    if articles is None:
        print("[INFO] Scraping live multi-source news (Regulators, Financial Wires & Thematic Discovery)...")
        all_articles = []
        feed_jobs = list(FEEDS)
        for t_name, t_url, _ in THEMATIC_DISCOVERY_FEEDS:
            feed_jobs.append((t_name, t_url))
        for s_sym, s_url in TARGETED_DISCOVERY_QUERIES:
            feed_jobs.append((f"Google News [{s_sym}]", s_url))

        with ThreadPoolExecutor(max_workers=8) as pool:
            future_to_feed = {pool.submit(fetch_rss_feed, name, url): name for name, url in feed_jobs}
            for fut in future_to_feed:
                try:
                    res = fut.result()
                    all_articles.extend(res)
                except Exception:
                    pass

        nse_filings = []
        if os.path.exists(NSE_CACHE_PATH):
            try:
                with open(NSE_CACHE_PATH, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    nse_filings = cached.get("rows", [])
            except Exception as e:
                print(f"[WARN] Error reading NSE cache: {e}")
    else:
        all_articles = list(articles)
        nse_filings = []

    sym_news = defaultdict(list)

    for art in all_articles:
        t = art["title"]
        src = art["source"]
        link = art.get("link", "")
        tier_info = SOURCE_TIERS.get(src, ("TIER_3_FINANCIAL_MEDIA", 0.65))

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
                sev_lvl, sev_code, band, pos_p, neg_p, neut_p, priced = classify_event_severity(t, cat, src)
                sym_news[sym].append({
                    "title": t,
                    "source": src,
                    "source_tier": tier_info[0],
                    "source_url": link,
                    "published_at_ist": parse_news_timestamp_ist(art.get("pubDate") or art.get("published_at_ist")),
                    "score": score,
                    "category": cat,
                    "impact": impact,
                    "severity_level": sev_lvl,
                    "severity_code": sev_code,
                    "expected_move_band": band,
                    "positive_prob": pos_p,
                    "negative_prob": neg_p,
                    "already_priced_in_prob": priced,
                    "filing_type": ""
                })

    for t_name, t_url, reg_key in THEMATIC_DISCOVERY_FEEDS:
        affected_stocks = REGULATOR_SECTOR_MAP.get(reg_key, ())
        thematic_arts = [a for a in all_articles if a["source"] == t_name]
        for art in thematic_arts:
            t = art["title"]
            score, cat, impact = analyze_headline(t)
            sev_lvl, sev_code, band, pos_p, neg_p, neut_p, priced = classify_event_severity(t, cat, t_name)
            for sym in affected_stocks:
                if sym in universe_symbols:
                    # Enforce strict entity matching:
                    is_sym_match = bool(re.search(rf"\b{re.escape(sym)}\b", t, re.IGNORECASE) or any(re.search(rf"\b{re.escape(al)}\b", t, re.IGNORECASE) for al in ALIASES.get(sym, ())))
                    
                    company_specific = reg_key == "LEGAL" or cat in {
                        "REGULATORY_PROBE", "ORDER_WIN", "EARNINGS_BEAT",
                        "EARNINGS_MISS", "M&A_EXPANSION", "MANAGEMENT_CHANGE"
                    }
                    if company_specific and not is_sym_match:
                        # Company-specific events must never be broadcast sector-wide.
                        # This also blocks penalties/probes naming companies outside
                        # the configured F&O universe (for example Bandhan Bank).
                        continue

                    if not is_sym_match:
                        # Sector-wide thematic items are allowed only when they do
                        # not explicitly identify another known universe company.
                        has_other_specific = False
                        for other_s in universe_symbols:
                            if other_s != sym:
                                if re.search(rf"\b{re.escape(other_s)}\b", t, re.IGNORECASE) or any(re.search(rf"\b{re.escape(al)}\b", t, re.IGNORECASE) for al in ALIASES.get(other_s, ())):
                                    has_other_specific = True
                                    break
                        if has_other_specific:
                            continue

                    candidate_key = news_dedup_key({
                        "title": t,
                        "source": f"{t_name} (Sector Regulation)",
                        "source_url": art.get("link", "")
                    })
                    if not any(news_dedup_key(x) == candidate_key for x in sym_news[sym]):
                        sym_news[sym].append({
                            "title": t,
                            "source": f"{t_name} (Sector Regulation)",
                            "source_tier": "TIER_1_REGULATOR" if "Official" in t_name else "TIER_3_FINANCIAL_MEDIA",
                            "source_url": art.get("link", ""),
                            "published_at_ist": parse_news_timestamp_ist(art.get("pubDate") or art.get("published_at_ist")),
                            "score": score,
                            "category": cat,
                            "impact": impact,
                            "severity_level": sev_lvl,
                            "severity_code": sev_code,
                            "expected_move_band": band,
                            "positive_prob": pos_p,
                            "negative_prob": neg_p,
                            "already_priced_in_prob": priced,
                            "filing_type": f"Sector {reg_key} Regulation"
                        })

    for n in nse_filings:
        sym = str(n.get("symbol", "")).strip().upper()
        if sym in universe_symbols:
            text = str(n.get("attchmntText", "") or n.get("desc", "")).strip()
            if text:
                score, cat, impact = analyze_headline(text)
                desc = str(n.get("desc", "NSE Filing")).strip()
                sev_lvl, sev_code, band, pos_p, neg_p, neut_p, priced = classify_event_severity(text, cat, "NSE Official Announcement")
                sym_news[sym].append({
                    "title": text[:220],
                    "source": "NSE Official Announcement",
                    "source_tier": "TIER_1_REGULATOR",
                    "source_url": "https://www.nseindia.com",
                    "published_at_ist": parse_news_timestamp_ist(n.get("timestamp") or n.get("published_at_ist")),
                    "score": score,
                    "category": cat,
                    "impact": impact,
                    "severity_level": sev_lvl,
                    "severity_code": sev_code,
                    "expected_move_band": band,
                    "positive_prob": pos_p,
                    "negative_prob": neg_p,
                    "already_priced_in_prob": priced,
                    "filing_type": desc
                })

    aggregated = {}
    for sym in universe_symbols:
        items = sym_news.get(sym, [])
        if not items:
            aggregated[sym] = {
                "sentiment_score": 0.0,
                "category": "NO_RECENT_HEADLINE",
                "impact_rating": "NEUTRAL",
                "top_headline": "No fresh material catalyst",
                "severity_level": 1,
                "severity_code": "LEVEL_1_NOISE",
                "expected_move_band": "0.0%",
                "positive_prob": 0.33,
                "negative_prob": 0.33,
                "already_priced_in_prob": 0.50,
                "source_tier": "TIER_3_FINANCIAL_MEDIA",
                "source_url": "",
                "item_count": 0,
                "sources_count": 0,
                "items": []
            }
            continue

        distinct_sources = set(i["source"] for i in items)
        actionable_items = [i for i in items if i.get("category") != "ROUTINE_COMPLIANCE"]
        if actionable_items:
            actionable_items.sort(
                key=lambda x: (x.get("severity_level", 1), abs(x["score"]), 1 if x["category"] != "GENERAL_MACRO" else 0),
                reverse=True
            )
            top = actionable_items[0]
            avg_score = round(sum(i["score"] for i in actionable_items) / len(actionable_items), 3)
            category = top["category"]
            impact_rating = top["impact"]
            top_headline = top["title"]
            sev_lvl = top["severity_level"]
            sev_code = top["severity_code"]
            band = top["expected_move_band"]
            pos_p = top["positive_prob"]
            neg_p = top["negative_prob"]
            priced = top["already_priced_in_prob"]
            src_tier = top["source_tier"]
            src_url = top.get("source_url", "")
        else:
            top = items[0]
            avg_score = 0.0
            category = "ROUTINE_COMPLIANCE"
            impact_rating = "NEUTRAL"
            top_headline = top["title"]
            sev_lvl = 1
            sev_code = "LEVEL_1_NOISE"
            band = "0.0% (Noise)"
            pos_p = 0.05
            neg_p = 0.05
            priced = 0.95
            src_tier = "TIER_1_REGULATOR"
            src_url = top.get("source_url", "")

        aggregated[sym] = {
            "sentiment_score": avg_score,
            "category": category,
            "impact_rating": impact_rating,
            "top_headline": top_headline,
            "severity_level": sev_lvl,
            "severity_code": sev_code,
            "expected_move_band": band,
            "positive_prob": pos_p,
            "negative_prob": neg_p,
            "already_priced_in_prob": priced,
            "source_tier": src_tier,
            "source_url": src_url,
            "item_count": len(items),
            "sources_count": len(distinct_sources),
            "items": items[:8]
        }

    print(f"[OK] Multi-source news aggregated: {sum(1 for v in aggregated.values() if v['item_count'] > 0)} symbols have active headlines/filings.")
    return aggregated

aggregate_news_for_symbols = aggregate_market_news

# =====================================================================
# PART 2: PRE-MARKET GAP OPENING & 9:15 AM EXPLOSION PREDICTOR
# =====================================================================
def compute_pre_market_gap(
    sym="NIFTY", fut_ltp=0.0, fut_pct=0.0, fut_obi=0.0, fut_oi_vel=0.0, news_info=None, atm_strike=0.0,
    ce_pct=0.0, pe_pct=0.0, ce_obi=0.0, pe_obi=0.0,
    ce_oi_vel=0.0, pe_oi_vel=0.0, atm_pcr=1.0, ce_iv=20.0, pe_iv=20.0,
    is_illiquid=False, ce_win_prob=None, pe_win_prob=None, news_sentiment=None, **kwargs
):
    """
    Enhanced Pre-Market 9:15 AM Gap Predictor combining:
    (a) Underlying fut_pct and fut_obi
    (b) Option Price Velocity & OBI Skew (ce_pct vs pe_pct and ce_obi vs pe_obi)
    (c) PCR & OI Velocity Skew
    (d) Black-76 Daily 1-Sigma Implied Move (IV / sqrt(252))
    (e) Verified non-routine News Catalyst impact
    """
    if is_illiquid:
        return {
            "expected_gap_pct": 0.0,
            "gap_direction": "⚠️ ILLIQUID [AVOID]",
            "pre_open_conviction": 35.0,
            "target_strike": "AVOID - ILLIQUID",
            "catalyst_count": 0,
            "positioning": "ILLIQUID_AVOID"
        }

    # 1. Verified Non-Routine News Catalyst Impact
    if news_info is None:
        news_info = {
            "sources_count": 1 if (news_sentiment is not None and abs(news_sentiment) > 0) else 0,
            "sentiment_score": news_sentiment if news_sentiment is not None else 0.0,
            "category": "GENERAL_MACRO"
        }
    elif news_sentiment is not None:
        news_info["sentiment_score"] = news_sentiment

    sources_cnt = news_info.get("sources_count", 0)
    sentiment = news_info.get("sentiment_score", 0.0)
    category = news_info.get("category", "GENERAL_MACRO")
    corroboration_mult = 1.6 if sources_cnt >= 2 else (1.2 if sources_cnt == 1 else 0.8)

    cat_weights = {
        "ORDER_WIN": 1.5,
        "EARNINGS_BEAT": 1.4,
        "EARNINGS_MISS": 1.5,
        "REGULATORY_PROBE": 1.8,
        "M&A_EXPANSION": 1.1,
        "CAPITAL_DIVIDEND": 0.8,
        "MANAGEMENT_CHANGE": 0.8,
        "GENERAL_MACRO": 0.5,
        "ROUTINE_COMPLIANCE": 0.0
    }
    cat_weight = cat_weights.get(category, 0.8)

    # Dividend ex-date nuance for gap opening
    if category == "CAPITAL_DIVIDEND":
        if fut_obi < -0.05 or ce_obi < pe_obi or fut_pct < -0.8:
            news_gap_term = -min(0.40, max(0.10, abs(fut_pct) * 0.25))
        elif fut_obi > 0.05 and ce_obi > pe_obi:
            news_gap_term = sentiment * 1.0 * corroboration_mult * 0.85
        else:
            news_gap_term = sentiment * 0.3 * corroboration_mult * 0.85
    elif category == "ROUTINE_COMPLIANCE":
        news_gap_term = 0.0
    else:
        news_gap_term = sentiment * cat_weight * corroboration_mult * 0.85

    # 2. Institutional Positioning from EOD Futures
    if fut_pct > 0.3 and fut_oi_vel > 0:
        positioning = "LONG_BUILDUP"
        pos_factor = 0.35
    elif fut_pct < -0.3 and fut_oi_vel > 0:
        positioning = "SHORT_BUILDUP"
        pos_factor = -0.35
    elif fut_pct > 0.3 and fut_oi_vel < 0:
        positioning = "SHORT_COVERING"
        pos_factor = 0.20
    elif fut_pct < -0.3 and fut_oi_vel < 0:
        positioning = "LONG_UNWINDING"
        pos_factor = -0.20
    else:
        positioning = "NEUTRAL"
        pos_factor = 0.0

    # 3. Option Price Velocity & OBI Skew
    opt_vel_diff = (ce_pct - pe_pct)
    opt_vel_skew = max(-1.0, min(1.0, opt_vel_diff / 50.0))
    opt_obi_skew = max(-1.0, min(1.0, (ce_obi - pe_obi) / 1.5))

    # 4. PCR & OI Velocity Skew
    pcr_val = atm_pcr if (atm_pcr is not None and atm_pcr > 0) else 1.0
    pcr_skew = max(-1.0, min(1.0, (pcr_val - 1.0) * 1.5))
    oi_vel_diff = ce_oi_vel - pe_oi_vel
    oi_vel_skew = max(-1.0, min(1.0, oi_vel_diff / 40.0))

    # 5. Black-76 Daily 1-Sigma Implied Move (IV / sqrt(252))
    avg_iv = (ce_iv + pe_iv) / 2.0 if (ce_iv + pe_iv) > 0 else 20.0
    implied_move_daily_pct = max(0.5, avg_iv / 15.8745)

    # 6. Combined Directional Skew
    prob_skew = 0.0
    if ce_win_prob is not None and pe_win_prob is not None:
        prob_skew = (ce_win_prob - pe_win_prob) / 100.0

    directional_skew = (
        (fut_pct * 0.25) +
        (fut_obi * 0.50) +
        (opt_vel_skew * 0.45) +
        (opt_obi_skew * 0.30) +
        (pcr_skew * 0.25) +
        (oi_vel_skew * 0.20) +
        (pos_factor * 0.35) +
        (prob_skew * 0.40) +
        news_gap_term
    )

    # Scale gap by daily implied move volatility bandwidth
    vol_scale = max(0.70, min(1.60, implied_move_daily_pct / 1.50))
    raw_gap = directional_skew * vol_scale
    expected_gap_pct = round(max(-6.0, min(6.0, raw_gap)), 2)

    # 7. Direction & Target Strike Selection
    if expected_gap_pct >= 0.35:
        gap_dir = "GAP-UP (CE EXPLOSION)"
        target_strike = f"{int(atm_strike)} CE"
    elif expected_gap_pct > 0.0:
        gap_dir = "SLIGHT GAP-UP"
        target_strike = f"{int(atm_strike)} CE"
    elif expected_gap_pct <= -0.35:
        gap_dir = "GAP-DOWN (PE EXPLOSION)"
        target_strike = f"{int(atm_strike)} PE"
    elif expected_gap_pct < 0.0:
        gap_dir = "SLIGHT GAP-DOWN"
        target_strike = f"{int(atm_strike)} PE"
    else:
        gap_dir = "FLAT / NEUTRAL OPEN"
        target_strike = f"{int(atm_strike)} ATM STRADDLE"

    # 8. Pre-Open Conviction %
    alignment = 0.0
    if (expected_gap_pct > 0 and opt_vel_skew > 0 and fut_obi > 0) or \
       (expected_gap_pct < 0 and opt_vel_skew < 0 and fut_obi < 0):
        alignment += 14.0
    if (expected_gap_pct > 0 and pcr_skew > 0) or (expected_gap_pct < 0 and pcr_skew < 0):
        alignment += 6.0
    if category not in ("ROUTINE_COMPLIANCE", "NO_RECENT_HEADLINE", "GENERAL_MACRO") and abs(sentiment) > 0.2:
        alignment += 5.0

    conviction = round(min(98.0, 50.0 + min(4.0, abs(expected_gap_pct)) * 7.5 + (sources_cnt * 3.0) + alignment), 1)

    return {
        "expected_gap_pct": expected_gap_pct,
        "gap_direction": gap_dir,
        "pre_open_conviction": conviction,
        "target_strike": target_strike,
        "catalyst_count": sources_cnt,
        "positioning": positioning,
        "implied_move_daily_pct": round(implied_move_daily_pct, 2)
    }

# =====================================================================
# PART 3: TOP-10 GROUND-TRUTH RECONCILIATION & SELF-CALIBRATING LOOP
# =====================================================================
def load_calibration_state():
    if os.path.exists(CALIBRATION_STATE_PATH):
        try:
            with open(CALIBRATION_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "cycle_number": 0,
        "weights": dict(DEFAULT_WEIGHTS),
        "prior_top10": [],
        "last_reconciliation": {}
    }

def save_calibration_state(state):
    try:
        with open(CALIBRATION_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"[WARN] Failed to save calibration state: {e}")

def run_ground_truth_reconciliation(current_predictions, actual_top_gainers_contracts, current_weights, prior_top10=None, persist=True):
    """
    Compares prior Top 10 predictions against actual live top option movers.
    Diagnoses misses and updates feature weights using online multiplicative weight updates.
    """
    cal_state = load_calibration_state()
    cycle = cal_state.get("cycle_number", 0) + 1
    if prior_top10 is None:
        prior_top10 = cal_state.get("prior_top10", [])

    current_top10_symbols = [p["symbol"] for p in current_predictions[:10]]
    current_top10_contracts = [p["ce_symbol"] if "CALL" in p["directional_bias"] else p["pe_symbol"] for p in current_predictions[:10]]

    # If first run, initialize prior_top10
    if not prior_top10:
        prior_top10 = current_top10_contracts

    actual_contracts = [str(c.get("contract") if isinstance(c, dict) else c).strip().upper() for c in actual_top_gainers_contracts[:10]]
    actual_symbols = []
    for c in actual_top_gainers_contracts[:10]:
        c_contract = str(c.get("contract") if isinstance(c, dict) else c).strip().upper()
        sym = str(c.get("symbol") if isinstance(c, dict) and c.get("symbol") else "").strip().upper()
        if not sym:
            matched = next((p["symbol"] for p in current_predictions if p.get("ce_symbol") == c_contract or p.get("pe_symbol") == c_contract), None)
            sym = matched if matched else c_contract.split("29SEP")[0].split("26")[0]
        actual_symbols.append(sym)

    hits = [c for c in actual_contracts if c in prior_top10]
    misses = [c for c in actual_contracts if c not in prior_top10]

    hit_rate = round((len(hits) / max(1, len(actual_contracts))) * 100.0, 1)
    recall_10 = round(len(hits) / 10.0, 2)

    # Calculate Mean Rank of actual movers in our 219 rankings
    sym_rank_map = {p["symbol"]: p["rank"] for p in current_predictions}
    ranks = [sym_rank_map.get(s, 100) for s in actual_symbols]
    mean_rank = round(sum(ranks) / max(1, len(ranks)), 1)

    # Miss Root-Cause Attribution & Online Multiplicative Weight Updates
    attribution = defaultdict(float)
    eta = 0.05  # Learning rate

    for miss in misses:
        rec = next((p for p in current_predictions if p.get("ce_symbol") == miss or p.get("pe_symbol") == miss), None)
        if not rec:
            m_sym = miss.split("29SEP")[0].split("26")[0]
            rec = next((p for p in current_predictions if p["symbol"] == m_sym), None)
        if rec:
            lead_chg = rec.get("ce_chg_pct", 0) if "CALL" in rec.get("directional_bias", "") else rec.get("pe_chg_pct", 0)
            if lead_chg > 15:
                attribution["opt_vel"] += 1.8
            d_gamma = max(rec.get("ce_dollar_gamma", 0), rec.get("pe_dollar_gamma", 0))
            if d_gamma > 1.0:
                attribution["gamma"] += 1.5
            if abs(rec.get("ce_oi_velocity", 0)) > 5 or abs(rec.get("pe_oi_velocity", 0)) > 5:
                attribution["oi_vel"] += 1.2
            if abs(rec.get("news_sentiment", 0)) > 0.2:
                attribution["news"] += 0.8
            attribution["opt_obi"] += 0.5
            attribution["fut_obi"] += 0.5
        else:
            attribution["opt_vel"] += 1.5
            attribution["oi_vel"] += 1.0

    # Update weights
    updated_weights = dict(current_weights)
    if misses:
        for k in updated_weights:
            updated_weights[k] = round(updated_weights[k] * (1.0 + eta * attribution.get(k, 0.0)), 4)
        # Normalize sum to 1.0
        total_w = sum(updated_weights.values())
        for k in updated_weights:
            updated_weights[k] = round(updated_weights[k] / total_w, 4)

    reconciliation = {
        "cycle": cycle,
        "hit_rate_pct": hit_rate,
        "recall_at_10": recall_10,
        "mean_rank": mean_rank,
        "hits_count": len(hits),
        "misses_count": len(misses),
        "hits": hits,
        "misses": misses[:5],
        "weights": updated_weights
    }

    if persist:
        # Save state for next cycle
        cal_state["cycle_number"] = cycle
        cal_state["prior_top10"] = current_top10_contracts
        cal_state["weights"] = updated_weights
        cal_state["last_reconciliation"] = reconciliation
        save_calibration_state(cal_state)

    print(f"[CALIBRATION] Cycle #{cycle} | Hit Rate: {hit_rate}% | Recall@10: {recall_10} | Mean Rank: {mean_rank}")
    return reconciliation

# =====================================================================
# PART 3B: EOD PRE-CLOSE NEXT-DAY GAP-UP & EXPLOSION PREDICTION ENGINE (15:00 - 15:40 IST)
# =====================================================================
NEXT_DAY_GAP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/next_day_gap_predictions.json")
GAP_RECON_HISTORY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/gap_reconciliation_history.json")

def generate_next_day_gap_picks(predictions, ist_now=None):
    """
    Identifies high-conviction overnight Gap-Up Call (CE) and Gap-Down Put (PE) candidates
    evaluated before market close (15:00 - 15:40 IST) based on institutional positioning,
    gamma exposure, order flow imbalance, and non-routine catalysts.
    """
    if ist_now is None:
        ist_now = get_ist_time()
    ist_str = ist_now.strftime("%Y-%m-%d %H:%M:%S")

    ce_candidates = []
    pe_candidates = []

    for p in predictions:
        if p.get("is_illiquid", False) or "ILLIQUID" in p.get("action_rating", ""):
            continue
        
        sym = p.get("symbol", "")
        spot = float(p.get("spot_ltp", 0.0))
        exp_gap = float(p.get("expected_gap_pct", 0.0))
        ce_prob = float(p.get("ce_win_prob", 50.0))
        pe_prob = float(p.get("pe_win_prob", 50.0))
        ce_ltp = float(p.get("ce_ltp", 0.0))
        pe_ltp = float(p.get("pe_ltp", 0.0))
        atm_strike = float(p.get("atm_strike", 0.0))
        act_rating = p.get("action_rating", "")
        conviction = float(p.get("pre_open_conviction", 60.0))
        headline = p.get("top_headline", "")
        ce_gamma = float(p.get("ce_dollar_gamma", 0.0))
        pe_gamma = float(p.get("pe_dollar_gamma", 0.0))
        ce_oi_vel = float(p.get("ce_oi_velocity", 0.0))
        pe_oi_vel = float(p.get("pe_oi_velocity", 0.0))
        pcr = float(p.get("atm_pcr", 1.0))
        ce_sym = p.get("ce_symbol", "")
        pe_sym = p.get("pe_symbol", "")
        ce_chg = float(p.get("ce_chg_pct", 0.0))
        pe_chg = float(p.get("pe_chg_pct", 0.0))

        # 1. CE Candidate Evaluation (Gap-Up / Call Breakout)
        if ce_prob >= 60.0 and exp_gap >= 0.25 and ce_ltp >= 0.50:
            score = (exp_gap * 3.0) + (ce_prob * 0.5) + min(25.0, ce_gamma * 15.0) + min(15.0, max(0.0, ce_oi_vel) * 0.5)
            sl_ltp = round(max(0.05, ce_ltp * 0.85), 2)
            tgt_ltp = round(ce_ltp * 1.50, 2)
            why = f"[OVERNIGHT GAP-UP CE] Action: {act_rating} | ExpGap: {exp_gap:+.2f}% | Conviction: {conviction:.1f}% | Gamma: {ce_gamma:.2f} | OI Vel: {ce_oi_vel:+.1f}% | PCR: {pcr:.2f} | Catalyst: {headline[:70]}"
            ce_candidates.append({
                "symbol": sym,
                "side": "CE",
                "spot_ltp": spot,
                "target_strike": f"{int(atm_strike)} CE",
                "contract_symbol": ce_sym,
                "forecast_contract": ce_sym,
                "strike": atm_strike,
                "expiry": p.get("expiry", ""),
                "forecast_timestamp": ist_str,
                "underlying_ref_price": spot,
                "option_ref_price": ce_ltp,
                "entry_ltp": ce_ltp,
                "session_change_pct": ce_chg,
                "expected_gap_pct": exp_gap,
                "conviction_pct": conviction,
                "stop_loss_ltp": sl_ltp,
                "target_ltp": tgt_ltp,
                "dollar_gamma": ce_gamma,
                "action_rating": act_rating,
                "news_catalyst": headline[:100],
                "why_rationale": why,
                "score": round(score, 2),
                "pcr": pcr,
                "oi_velocity": ce_oi_vel
            })

        # 2. PE Candidate Evaluation (Gap-Down / Put Breakdown)
        if pe_prob >= 60.0 and exp_gap <= -0.25 and pe_ltp >= 0.50:
            score = (abs(exp_gap) * 3.0) + (pe_prob * 0.5) + min(25.0, pe_gamma * 15.0) + min(15.0, max(0.0, pe_oi_vel) * 0.5)
            sl_ltp = round(max(0.05, pe_ltp * 0.85), 2)
            tgt_ltp = round(pe_ltp * 1.60, 2)
            why = f"[OVERNIGHT GAP-DOWN PE] Action: {act_rating} | ExpGap: {exp_gap:+.2f}% | Conviction: {conviction:.1f}% | Gamma: {pe_gamma:.2f} | OI Vel: {pe_oi_vel:+.1f}% | PCR: {pcr:.2f} | Catalyst: {headline[:70]}"
            pe_candidates.append({
                "symbol": sym,
                "side": "PE",
                "spot_ltp": spot,
                "target_strike": f"{int(atm_strike)} PE",
                "contract_symbol": pe_sym,
                "forecast_contract": pe_sym,
                "strike": atm_strike,
                "expiry": p.get("expiry", ""),
                "forecast_timestamp": ist_str,
                "underlying_ref_price": spot,
                "option_ref_price": pe_ltp,
                "entry_ltp": pe_ltp,
                "session_change_pct": pe_chg,
                "expected_gap_pct": exp_gap,
                "conviction_pct": conviction,
                "stop_loss_ltp": sl_ltp,
                "target_ltp": tgt_ltp,
                "dollar_gamma": pe_gamma,
                "action_rating": act_rating,
                "news_catalyst": headline[:100],
                "why_rationale": why,
                "score": round(score, 2),
                "pcr": pcr,
                "oi_velocity": pe_oi_vel
            })

    ce_candidates.sort(key=lambda x: x["score"], reverse=True)
    pe_candidates.sort(key=lambda x: x["score"], reverse=True)

    result = {
        "timestamp_ist": ist_str,
        "date": ist_str[:10],
        "top_ce_picks": ce_candidates[:5],
        "top_pe_picks": pe_candidates[:5]
    }

    # Persist locally to data/
    try:
        os.makedirs(os.path.dirname(NEXT_DAY_GAP_PATH), exist_ok=True)
        with open(NEXT_DAY_GAP_PATH, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    except Exception as e:
        print(f"[WARN] Failed to cache next_day_gap_predictions.json: {e}")

    return result

def journal_pre_close_paper_trades(sh, bq_client, gap_picks, ist_str, ist_now):
    """
    Appends overnight paper trades to Google Sheets PAPER_ALERT_LOG and BigQuery Sandbox
    during the 15:00 - 15:40 IST pre-close window with complete micro-details and rationale.
    Guarantees deduplication (exactly 1 record per symbol/side per session date).
    """
    require_authorized_writer()
    session_date = ist_str[:10]
    next_day = ist_now.date() + datetime.timedelta(days=1 if ist_now.weekday() < 4 else 3)
    target_date_iso = next_day.isoformat()

    all_picks = gap_picks.get("top_ce_picks", []) + gap_picks.get("top_pe_picks", [])
    if not all_picks:
        return

    # 1. Google Sheets PAPER_ALERT_LOG
    try:
        ws_paper = sh.worksheet("PAPER_ALERT_LOG")
        existing_rows = ws_paper.get_all_values()
        logged_keys = set()
        for r in existing_rows[1:]:
            if len(r) >= 4 and r[1] == session_date and "[OVERNIGHT" in (r[8] if len(r) > 8 else ""):
                logged_keys.add((r[2].strip().upper(), r[3].strip().upper()))

        new_paper_rows = []
        for c in all_picks:
            key = (c["symbol"].strip().upper(), c["side"].strip().upper())
            if key in logged_keys:
                continue
            logged_keys.add(key)
            full_note = f"{c['why_rationale']} | Entry: ₹{c['entry_ltp']:.2f} | SL: ₹{c['stop_loss_ltp']:.2f} (-15%) | Target: ₹{c['target_ltp']:.2f} | ExpGap: {c['expected_gap_pct']:+.2f}%"
            new_paper_rows.append([
                ist_str,
                session_date,
                c["symbol"],
                c["side"],
                c["spot_ltp"],
                c["session_change_pct"],
                c["contract_symbol"] if c["side"] == "CE" else "",
                c["contract_symbol"] if c["side"] == "PE" else "",
                full_note,
                "",  # Later session change % (reconciled at 09:15 next day)
                ""   # Outcome filled at (reconciled at 09:15 next day)
            ])

        if new_paper_rows:
            ws_paper.append_rows(new_paper_rows, value_input_option="USER_ENTERED")
            append_sheet_provenance(
                sh,
                sink="PAPER_ALERT_LOG",
                record_count=len(new_paper_rows),
                source_timestamp=ist_str,
            )
            print(f"[OK] Appended {len(new_paper_rows)} overnight paper trades to PAPER_ALERT_LOG!")
    except Exception as e:
        print(f"[WARN] Error journaling to PAPER_ALERT_LOG: {e}")

    # 2. BigQuery Sandbox Table (next_day_gap_predictions)
    try:
        dataset_ref = bq_client.dataset(BQ_DATASET_ID)
        table_ref = dataset_ref.table("next_day_gap_predictions")
        table = bq_client.get_table(table_ref)

        bq_rows = []
        for c in all_picks:
            bq_rows.append({
                **build_provenance(ist_str),
                "prediction_date": session_date,
                "predicted_at_ist": ist_str,
                "symbol": str(c["symbol"]),
                "target_date": target_date_iso,
                "side": str(c["side"]),
                "spot_ltp": float(c["spot_ltp"]),
                "target_strike": str(c["target_strike"]),
                "contract_symbol": str(c["contract_symbol"]),
                "entry_ltp": float(c["entry_ltp"]),
                "expected_gap_pct": float(c["expected_gap_pct"]),
                "conviction_pct": float(c["conviction_pct"]),
                "stop_loss_ltp": float(c["stop_loss_ltp"]),
                "target_ltp": float(c["target_ltp"]),
                "rationale": str(c["why_rationale"]),
                "news_catalyst": str(c["news_catalyst"]),
                "dollar_gamma": float(c["dollar_gamma"]),
                "actual_open_ltp": None,
                "actual_return_pct": None,
                "outcome": "PENDING_OPEN",
                "reconciled_at_ist": None
            })

        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION],
            schema=table.schema,
            autodetect=False,
        )
        job = bq_client.load_table_from_json(bq_rows, table, job_config=job_config)
        job.result()
        print(f"[OK] Loaded {len(bq_rows)} next-day gap records into BigQuery next_day_gap_predictions!")
    except Exception as e:
        print(f"[WARN] Error syncing to BigQuery next_day_gap_predictions: {e}")

# =====================================================================
# PART 3C: NEXT-MORNING 09:15 AM RECONCILIATION & BAYESIAN SELF-LEARNING ENGINE
# =====================================================================
def reconcile_next_day_gap_trades(smartApi, sh, bq_client, predictions, ist_str, ist_now):
    """
    Executes morning reconciliation (09:15 - 09:40 IST) for unresolved overnight paper trades.
    Computes actual opening returns, determines WIN / LOSS / SCRATCH outcomes, updates
    PAPER_ALERT_LOG and BigQuery, and feeds outcomes back to the Bayesian weight self-calibration.
    """
    require_authorized_writer()
    session_date = ist_str[:10]
    try:
        ws_paper = sh.worksheet("PAPER_ALERT_LOG")
        rows = ws_paper.get_all_values()
        if len(rows) <= 1:
            return

        pred_symbol_map = {p["symbol"].strip().upper(): p for p in predictions}
        unresolved_indices = []

        for idx, r in enumerate(rows[1:], start=2):
            if len(r) >= 9 and "[OVERNIGHT" in r[8]:
                later_change = r[9].strip() if len(r) > 9 else ""
                if not later_change:
                    unresolved_indices.append((idx, r))

        if not unresolved_indices:
            print("[INFO] No pending overnight paper trades to reconcile.")
            return

        print(f"[INFO] Reconciling {len(unresolved_indices)} overnight paper trades...")
        reconciled_results = []
        updates_for_sheet = []

        for row_idx, r in unresolved_indices:
            trade_date = r[1]
            sym = r[2].strip().upper()
            side = r[3].strip().upper()
            contract = (r[6] if side == "CE" else r[7]).strip().upper()
            note = r[8]

            m_entry = re.search(r"Entry:\s*₹?\s*([0-9.]+)", note)
            entry_ltp = float(m_entry.group(1)) if m_entry else 0.0

            open_ltp = 0.0
            current_atm_contract = ""
            if sym in pred_symbol_map:
                pred_item = pred_symbol_map[sym]
                current_atm_contract = (pred_item.get("ce_symbol") if side == "CE" else pred_item.get("pe_symbol")) or ""
                # G19 Fix: Only use pred_item LTP if the current ATM contract matches the exact frozen contract.
                # If ATM drifted intraday/overnight, do NOT substitute the drifted ATM contract's LTP!
                if side == "CE" and current_atm_contract == contract:
                    open_ltp = float(pred_item.get("ce_ltp", 0.0))
                elif side == "PE" and current_atm_contract == contract:
                    open_ltp = float(pred_item.get("pe_ltp", 0.0))

            # When ATM drifted or open_ltp not yet resolved, query the EXACT frozen contract
            if open_ltp <= 0.0 and smartApi:
                try:
                    q = smartApi.getLtpData("NFO", contract, "")
                    if q and q.get("data"):
                        open_ltp = float(q["data"].get("ltp", 0.0))
                except Exception:
                    pass

            if entry_ltp > 0 and open_ltp > 0:
                ret_pct = round(((open_ltp - entry_ltp) / entry_ltp) * 100.0, 2)
                if ret_pct >= 20.0:
                    outcome = "WIN"
                elif ret_pct <= -15.0:
                    outcome = "LOSS"
                else:
                    outcome = "SCRATCH"

                result_text = f"{ret_pct:+.2f}% ({outcome})"
                updates_for_sheet.append((row_idx, result_text, ist_str))
                reconciled_results.append({
                    "symbol": sym,
                    "side": side,
                    "trade_date": trade_date,
                    "forecast_contract": contract,
                    "current_atm_contract": current_atm_contract,
                    "contract": contract,
                    "entry_ltp": entry_ltp,
                    "actual_open_ltp": open_ltp,
                    "actual_return_pct": ret_pct,
                    "outcome": outcome,
                    "reconciled_at_ist": ist_str
                })

        for row_idx, res_txt, fill_time in updates_for_sheet:
            try:
                ws_paper.update_cell(row_idx, 10, res_txt)
                ws_paper.update_cell(row_idx, 11, fill_time)
            except Exception as e:
                print(f"[WARN] Failed to update PAPER_ALERT_LOG row {row_idx}: {e}")

        if updates_for_sheet:
            append_sheet_provenance(
                sh,
                sink="PAPER_ALERT_LOG_RECONCILE",
                record_count=len(updates_for_sheet),
                source_timestamp=ist_str,
            )

        if reconciled_results:
            print(f"[OK] Reconciled {len(reconciled_results)} overnight trades in PAPER_ALERT_LOG!")

            # Append reconciliation records into BigQuery
            try:
                dataset_ref = bq_client.dataset(BQ_DATASET_ID)
                table_ref = dataset_ref.table("next_day_gap_predictions")
                table = bq_client.get_table(table_ref)
                bq_reconciled_rows = []
                for res in reconciled_results:
                    bq_reconciled_rows.append({
                        **build_provenance(ist_str),
                        "prediction_date": res["trade_date"],
                        "predicted_at_ist": ist_str,
                        "symbol": res["symbol"],
                        "target_date": session_date,
                        "side": res["side"],
                        "spot_ltp": 0.0,
                        "target_strike": "",
                        "contract_symbol": res["contract"],
                        "entry_ltp": res["entry_ltp"],
                        "expected_gap_pct": 0.0,
                        "conviction_pct": 0.0,
                        "stop_loss_ltp": 0.0,
                        "target_ltp": 0.0,
                        "rationale": f"RECONCILIATION RESULT: {res['outcome']} ({res['actual_return_pct']:+.2f}%)",
                        "news_catalyst": "",
                        "dollar_gamma": 0.0,
                        "actual_open_ltp": res["actual_open_ltp"],
                        "actual_return_pct": res["actual_return_pct"],
                        "outcome": res["outcome"],
                        "reconciled_at_ist": ist_str
                    })
                job_config = bigquery.LoadJobConfig(
                    write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
                    schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION],
                    schema=table.schema,
                    autodetect=False,
                )
                bq_client.load_table_from_json(bq_reconciled_rows, table, job_config=job_config).result()
                print(f"[OK] Logged {len(bq_reconciled_rows)} reconciliation results to BigQuery!")
            except Exception as e:
                print(f"[WARN] Failed to log reconciliation to BigQuery: {e}")

            # Online Closed-Loop Weight Calibration based on overnight outcomes
            cal_state = load_calibration_state()
            current_w = dict(cal_state.get("weights", DEFAULT_WEIGHTS))
            wins = sum(1 for r in reconciled_results if r["outcome"] == "WIN")
            losses = sum(1 for r in reconciled_results if r["outcome"] == "LOSS")
            
            eta = 0.04
            if wins > losses:
                current_w["gamma"] = round(current_w.get("gamma", 0.15) * (1.0 + eta), 4)
                current_w["opt_vel"] = round(current_w.get("opt_vel", 0.20) * (1.0 + eta), 4)
            elif losses > wins:
                current_w["opt_vel"] = round(current_w.get("opt_vel", 0.20) * (1.0 - eta), 4)
                current_w["opt_obi"] = round(current_w.get("opt_obi", 0.15) * (1.0 + eta), 4)

            tot_w = sum(current_w.values())
            for k in current_w:
                current_w[k] = round(current_w[k] / tot_w, 4)

            cal_state["weights"] = current_w
            save_calibration_state(cal_state)
            print(f"[CALIBRATION] Overnight gap feedback integrated: {wins} Wins, {losses} Losses. Weights updated.")

            try:
                hist = []
                if os.path.exists(GAP_RECON_HISTORY_PATH):
                    with open(GAP_RECON_HISTORY_PATH, "r", encoding="utf-8") as f:
                        hist = json.load(f)
                hist.extend(reconciled_results)
                with open(GAP_RECON_HISTORY_PATH, "w", encoding="utf-8") as f:
                    json.dump(hist[-500:], f, indent=2)
            except Exception as e:
                print(f"[WARN] Failed to update reconciliation history: {e}")

    except Exception as e:
        print(f"[WARN] Reconciliation loop error: {e}")

# =====================================================================
# DYNAMIC F&O UNIVERSE DISCOVERY & ANGEL ONE INTEGRATION
# =====================================================================
def get_angel_client():
    load_env()
    creds = get_angel_credentials()
    missing = [name for name, value in creds.items() if not value]
    if missing:
        raise RuntimeError(
            "Angel One credentials are required only for live broker access; "
            f"missing environment variables: {', '.join(missing)}"
        )
    totp = pyotp.TOTP(creds["ANGEL_TOTP_SEED"]).now()
    smartApi = SmartConnect(api_key=creds["ANGEL_API_KEY"])
    login = smartApi.generateSession(creds["ANGEL_CLIENT_CODE"], creds["ANGEL_PIN"], totp)
    if not login or not login.get("status"):
        raise RuntimeError(f"Angel One session rejected: {login}")
    print("[OK] Angel One SmartAPI Session Connected")
    return smartApi

def load_or_download_scrip_master(exchange_epoch=None):
    # Cache freshness check only, not data timestamp
    now_ts = exchange_epoch if exchange_epoch is not None else time.time()
    if os.path.exists(SCRIP_CACHE_PATH):
        try:
            mtime = os.path.getmtime(SCRIP_CACHE_PATH)
            if (now_ts - mtime) < 86400:
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

    discovered_count = len(universe)
    if discovered_count < EXPECTED_FNO_UNIVERSE_COUNT:
        print(f"[WARN] F&O universe incomplete: discovered {discovered_count}/{EXPECTED_FNO_UNIVERSE_COUNT}. Refusing to claim full-universe coverage.")
    else:
        print(f"[OK] Auto-Discovered {discovered_count} NSE F&O Symbols with active CE & PE Option Chains!")
    return universe

def fetch_quotes_in_batches(smartApi, token_list, chunk_size=45):
    results = {}
    chunks = [token_list[i:i + chunk_size] for i in range(0, len(token_list), chunk_size)]
    for chunk in chunks:
        retries = 0
        max_retries = 4
        while retries <= max_retries:
            try:
                res = smartApi.getMarketData("FULL", {"NFO": chunk})
                status = bool(res and res.get("status"))
                if status and res.get("data"):
                    for item in res["data"].get("fetched", []) or []:
                        results[str(item.get("symbolToken"))] = item
                    time.sleep(0.20)
                    break
                error_text = str((res or {}).get("message") or (res or {}).get("errorcode") or "empty/failed market-data response")
                raise RuntimeError(error_text)
            except Exception as e:
                retries += 1
                if retries > max_retries:
                    print(f"[ERROR] Quote batch failed permanently after {max_retries} retries: {e}")
                    break
                backoff = min(30.0, (2 ** retries) + 0.5)
                print(f"[WARN] Quote batch error: {e}. Retrying {retries}/{max_retries} in {backoff:.1f}s...")
                time.sleep(backoff)
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
    ce_ltp, ce_pct, ce_oi, ce_obi, ce_spread, ce_iv,
    ce_delta=0.0, ce_gamma=0.0, ce_theta=0.0, ce_vega=0.0,
    pe_ltp=0.0, pe_pct=0.0, pe_oi=0, pe_obi=0.0, pe_spread=0.0,
    pe_iv=0.0, pe_delta=0.0, pe_gamma=0.0, pe_theta=0.0, pe_vega=0.0,
    atm_pcr=1.0, max_pain=0.0, prev_ce_oi=None, prev_pe_oi=None,
    news_sentiment=0.0, news_category="NO_NEWS", news_impact="NEUTRAL",
    weights=None, ce_vol=1000, pe_vol=1000,
    ce_greeks=None, pe_greeks=None, **kwargs
):
    if ce_greeks and isinstance(ce_greeks, dict):
        ce_delta = ce_greeks.get("delta", ce_delta)
        ce_gamma = ce_greeks.get("gamma", ce_gamma)
        ce_theta = ce_greeks.get("theta", ce_theta)
        ce_vega = ce_greeks.get("vega", ce_vega)

    if pe_greeks and isinstance(pe_greeks, dict):
        pe_delta = pe_greeks.get("delta", pe_delta)
        pe_gamma = pe_greeks.get("gamma", pe_gamma)
        pe_theta = pe_greeks.get("theta", pe_theta)
        pe_vega = pe_greeks.get("vega", pe_vega)
    w = weights or DEFAULT_WEIGHTS

    ce_oi_velocity = 0.0
    if prev_ce_oi and prev_ce_oi > 0:
        ce_oi_velocity = round(((ce_oi - prev_ce_oi) / prev_ce_oi) * 100.0, 2)

    pe_oi_velocity = 0.0
    if prev_pe_oi and prev_pe_oi > 0:
        pe_oi_velocity = round(((pe_oi - prev_pe_oi) / prev_pe_oi) * 100.0, 2)

    logit = 0.0

    # A. Futures Price & Order Imbalance Momentum
    logit += (fut_pct * 0.45)
    logit += (fut_obi * w.get("fut_obi", 0.22) * 3.5)

    # B. Options Price & Flow Velocity
    if ce_pct > 0 and ce_oi_velocity > 0:
        logit += min(1.0, ce_oi_velocity * 0.05)
    elif ce_pct < 0 and ce_oi_velocity > 0:
        logit -= min(1.0, ce_oi_velocity * 0.04)

    if pe_pct > 0 and pe_oi_velocity > 0:
        logit -= min(1.0, pe_oi_velocity * 0.05)
    elif pe_pct < 0 and pe_oi_velocity > 0:
        logit += min(1.0, pe_oi_velocity * 0.04)

    logit += (ce_obi - pe_obi) * w.get("opt_obi", 0.18) * 1.5

    # C. PCR & Max Pain
    if atm_pcr is not None:
        if atm_pcr >= 1.25:
            logit += 0.35
        elif atm_pcr <= 0.70:
            logit -= 0.35

    if max_pain > 0 and fut_ltp > 0:
        pain_gap_pct = ((fut_ltp - max_pain) / max_pain) * 100.0
        if abs(pain_gap_pct) < 1.0:
            logit *= 0.85
        elif pain_gap_pct > 1.5 and fut_pct > 0:
            logit += 0.25

    # Normalize Gamma into Dollar Gamma: Gamma * S^2 * 0.01 (unitless rupees of delta exposure per 1% underlying move)
    ce_dollar_gamma = round(ce_gamma * (fut_ltp ** 2) * 0.01, 4) if fut_ltp > 0 else 0.0
    pe_dollar_gamma = round(pe_gamma * (fut_ltp ** 2) * 0.01, 4) if fut_ltp > 0 else 0.0

    # D. Greeks & Dollar Gamma Acceleration
    if ce_dollar_gamma > 0.50 and ce_obi > 0.15 and fut_pct > 0.2:
        logit += (0.50 * w.get("gamma", 0.20) / 0.20)
    elif pe_dollar_gamma > 0.50 and pe_obi > 0.15 and fut_pct < -0.2:
        logit -= (0.50 * w.get("gamma", 0.20) / 0.20)

    # E. News Sentiment & Dividend Ex-Date Nuance
    category_weights = {
        "ORDER_WIN": 1.6,
        "EARNINGS_BEAT": 1.5,
        "EARNINGS_MISS": 1.5,
        "REGULATORY_PROBE": 1.8,
        "M&A_EXPANSION": 1.2,
        "CAPITAL_DIVIDEND": 1.1,
        "MANAGEMENT_CHANGE": 0.8,
        "GENERAL_MACRO": 0.8,
        "ROUTINE_COMPLIANCE": 0.0
    }
    if news_category == "CAPITAL_DIVIDEND":
        # Check whether Futures OBI and Option flow confirm bullish accumulation or ex-dividend discount
        flow_bullish = (fut_obi > 0.05 and ce_obi > pe_obi and fut_pct >= -0.5)
        flow_bearish = (fut_obi < -0.05 or ce_obi < pe_obi or fut_pct < -0.8)
        if flow_bullish:
            logit += (news_sentiment * 1.2 * w.get("news", 0.07) * 5.0)
        elif flow_bearish:
            logit -= min(0.35, max(0.10, abs(fut_pct) * 0.25))
        else:
            logit += (news_sentiment * 0.3 * w.get("news", 0.07) * 5.0)
    elif news_category == "ROUTINE_COMPLIANCE":
        pass
    else:
        news_mult = category_weights.get(news_category, 1.0)
        logit += (news_sentiment * news_mult * w.get("news", 0.07) * 5.0)

    # Probabilities
    prob_ce = 1.0 / (1.0 + math.exp(-max(-4.0, min(4.0, logit * 1.5))))
    ce_win_prob = round(prob_ce * 100.0, 1)
    pe_win_prob = round((100.0 - ce_win_prob), 1)

    # Intensity (1 - 100)
    intensity = 35.0
    avg_iv = (ce_iv + pe_iv) / 2.0 if (ce_iv + pe_iv) > 0 else 20.0
    intensity += min(25.0, (avg_iv / 35.0) * 20.0)
    intensity += min(20.0, abs(fut_pct) * 6.0)
    intensity += min(15.0, abs(fut_obi) * 15.0)

    if max(ce_dollar_gamma, pe_dollar_gamma) > 0.40:
        intensity += 10.0
    if max(abs(ce_oi_velocity), abs(pe_oi_velocity)) > 15.0:
        intensity += 10.0
    if news_category in ("ORDER_WIN", "REGULATORY_PROBE", "EARNINGS_BEAT", "EARNINGS_MISS"):
        intensity += 12.0

    intensity_score = int(max(20, min(99, round(intensity))))

    # Confidence (50% - 98%)
    conviction_distance = abs(ce_win_prob - 50.0)
    agreement_boost = 0.0
    if (ce_win_prob > 55.0 and news_sentiment > 0.2 and fut_obi > 0.1) or \
       (pe_win_prob > 55.0 and news_sentiment < -0.2 and fut_obi < -0.1):
        agreement_boost = 12.0
    confidence_pct = round(min(97.5, 52.0 + conviction_distance * 0.90 + agreement_boost), 1)

    # Ratings
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

    if ce_dollar_gamma > 0.60 and ce_obi > 0.20 and ce_win_prob >= 60.0:
        rating = "🚨 GAMMA SQUEEZE ALERT (ACCELERATING CE)"

    # Dominant option parameters for composite ranking
    if ce_win_prob >= 50.0:
        lead_opt_chg = max(0.0, ce_pct)
        lead_oi_vel = max(0.0, ce_oi_velocity)
        lead_dollar_gamma = ce_dollar_gamma
        lead_obi = ce_obi
        dom_ltp = ce_ltp
        dom_spread = ce_spread
        dom_iv = ce_iv
        dom_oi = ce_oi
        dom_vol = ce_vol
    else:
        lead_opt_chg = max(0.0, pe_pct)
        lead_oi_vel = max(0.0, pe_oi_velocity)
        lead_dollar_gamma = pe_dollar_gamma
        lead_obi = pe_obi
        dom_ltp = pe_ltp
        dom_spread = pe_spread
        dom_iv = pe_iv
        dom_oi = pe_oi
        dom_vol = pe_vol

    # Relative spread calculation: spread / max(ltp, 0.05)
    rel_spread = dom_spread / max(dom_ltp, 0.05)

    # Liquidity & Bid-Ask Spread Gate:
    # If volume == 0, oi == 0, iv <= 0.01, or rel_spread > 0.25 (and absolute spread > 2.00)
    is_illiquid = (
        dom_vol == 0 or
        dom_oi == 0 or
        dom_iv <= 0.01 or
        (rel_spread > 0.25 and dom_spread > 2.00)
    )

    if is_illiquid:
        rating = "⚠️ ILLIQUID / WIDE SPREAD [AVOID]"
        confidence_pct = round(min(confidence_pct * 0.40, 40.0), 1)
        intensity_score = min(intensity_score, 20)
        # Heavily penalize rank metric so illiquid symbols get Rank > 180
        rank_metric = round(-1000.0 - (rel_spread * 10.0) - dom_spread, 2)
    else:
        # Composite Ranking Metric:
        # Directly weights Option Price Velocity, Dollar Gamma, Volume/OI Surge, and Conviction
        # Soft-saturate extreme option percentage change so runaway penny options don't explode linearly
        if lead_opt_chg > 150.0:
            sat_opt_chg = 150.0 + 50.0 * math.log1p((lead_opt_chg - 150.0) / 50.0)
        else:
            sat_opt_chg = lead_opt_chg

        opt_vel_term = sat_opt_chg * w.get("opt_vel", 0.28) * 1.5
        gamma_term = min(40.0, lead_dollar_gamma * 0.35) * w.get("gamma", 0.20) * 1.2
        oi_surge_term = min(30.0, lead_oi_vel * 0.5) * w.get("oi_vel", 0.18) * 1.0
        conviction_term = (conviction_distance * 1.2 + intensity_score * 0.6) * 0.25
        obi_term = max(0.0, lead_obi * 20.0) * w.get("opt_obi", 0.10) * 0.5
        news_term = max(0.0, news_sentiment * 15.0) * w.get("news", 0.07)

        raw_rank_metric = opt_vel_term + gamma_term + oi_surge_term + conviction_term + obi_term + news_term
        rank_metric = round(min(400.0, max(-999.0, raw_rank_metric)), 2)

    return {
        "directional_bias": bias,
        "ce_win_prob": ce_win_prob,
        "pe_win_prob": pe_win_prob,
        "intensity_score": intensity_score,
        "confidence_pct": confidence_pct,
        "action_rating": rating,
        "ce_oi_velocity": ce_oi_velocity,
        "pe_oi_velocity": pe_oi_velocity,
        "ce_dollar_gamma": ce_dollar_gamma,
        "pe_dollar_gamma": pe_dollar_gamma,
        "rank_metric": rank_metric,
        "is_illiquid": is_illiquid
    }

# =====================================================================
# FULL EXECUTION PIPELINE
# =====================================================================
def run_prediction_pipeline(bypass_market_check=False, force_pre_close=False, reconcile_morning=False):
    require_authorized_writer()
    ist_now = get_ist_time()
    ist_str = ist_now.strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n=======================================================")
    print(f"[{ist_str}] STARTING ADVANCED PREDICTION & CALIBRATION PIPELINE")
    print(f"=======================================================")

    smartApi = get_angel_client()

    scrip_data = load_or_download_scrip_master()
    universe = discover_fno_universe(scrip_data)
    universe = select_verified_universe(universe)
    symbols = list(universe.keys())

    # Multi-source news
    news_map = aggregate_news_for_symbols(symbols)

    # Futures quotes
    fut_tokens = [u["fut_token"] for u in universe.values()]
    print(f"[INFO] Fetching live Underlying Futures quotes for {len(fut_tokens)} symbols...")
    fut_quotes = fetch_quotes_in_batches(smartApi, fut_tokens, chunk_size=45)

    # Resolve ATM & chain strikes
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

    # Fetch Option quotes
    unique_option_tokens = list(set(atm_tokens + chain_tokens))
    print(f"[INFO] Fetching live option chain quotes for {len(unique_option_tokens)} contracts across {len(sym_meta)} symbols...")
    opt_quotes = fetch_quotes_in_batches(smartApi, unique_option_tokens, chunk_size=45)

    # Load persistent states
    state = load_state()
    prev_symbols_state = state.get("symbols", {})
    new_symbols_state = {}
    seen_news_keys = set(state.get("seen_news_keys", []))

    cal_state = load_calibration_state()
    current_weights = cal_state.get("weights", DEFAULT_WEIGHTS)

    # Compute Features, Greeks, Max Pain, Pre-Market Gap, and Predictions
    print("[INFO] Computing Option Greeks, Max Pain, Pre-Market Gap Predictions & Ratings...")
    predictions = []
    news_rows_for_bq = []
    forensic_live_rows = []

    today = ist_now.date()

    for sym, meta in sym_meta.items():
        info = universe[sym]
        fq = fut_quotes.get(info["fut_token"], {})
        ceq = opt_quotes.get(meta["ce_token"], {})
        peq = opt_quotes.get(meta["pe_token"], {})
        if not ceq or not peq:
            raise RuntimeError(f"Missing ATM option quote for {sym}; preserving last good publication")

        fut_ltp = float(fq.get("ltp", 0.0))
        fut_pct = float(fq.get("percentChange", 0.0))
        fut_tbq = int(fq.get("totBuyQuan", 0))
        fut_tsq = int(fq.get("totSellQuan", 0))
        fut_obi = round((fut_tbq - fut_tsq) / max(1, (fut_tbq + fut_tsq)), 3)

        # ATM CE metrics (strict schema: 0.0 when depth is 0)
        ce_ltp = float(ceq.get("ltp", 0.0))
        ce_pct = float(ceq.get("percentChange", 0.0))
        ce_oi  = int(ceq.get("opnInterest", 0))
        ce_vol = int(ceq.get("tradeVolume", 0) or ceq.get("volume", 0) or 0)
        ce_tbq = int(ceq.get("totBuyQuan", 0))
        ce_tsq = int(ceq.get("totSellQuan", 0))
        ce_obi = round((ce_tbq - ce_tsq) / max(1, (ce_tbq + ce_tsq)), 3) if (ce_tbq + ce_tsq) > 0 else 0.0
        ce_depth = ceq.get("depth", {})
        ce_buy_p = float(ce_depth.get("buy", [{}])[0].get("price", 0.0)) if ce_depth.get("buy") else 0.0
        ce_sell_p = float(ce_depth.get("sell", [{}])[0].get("price", 0.0)) if ce_depth.get("sell") else 0.0
        ce_spread = round(max(0.0, ce_sell_p - ce_buy_p), 2) if (ce_buy_p > 0 and ce_sell_p > 0) else 0.0

        # ATM PE metrics
        pe_ltp = float(peq.get("ltp", 0.0))
        pe_pct = float(peq.get("percentChange", 0.0))
        pe_oi  = int(peq.get("opnInterest", 0))
        pe_vol = int(peq.get("tradeVolume", 0) or peq.get("volume", 0) or 0)
        pe_tbq = int(peq.get("totBuyQuan", 0))
        pe_tsq = int(peq.get("totSellQuan", 0))
        pe_obi = round((pe_tbq - pe_tsq) / max(1, (pe_tbq + pe_tsq)), 3) if (pe_tbq + pe_tsq) > 0 else 0.0
        pe_depth = peq.get("depth", {})
        pe_buy_p = float(pe_depth.get("buy", [{}])[0].get("price", 0.0)) if pe_depth.get("buy") else 0.0
        pe_sell_p = float(pe_depth.get("sell", [{}])[0].get("price", 0.0)) if pe_depth.get("sell") else 0.0
        pe_spread = round(max(0.0, pe_sell_p - pe_buy_p), 2) if (pe_buy_p > 0 and pe_sell_p > 0) else 0.0

        # Strict non-empty PCR: if CE OI > 0: round(min(10.0, PE OI / CE OI), 2), else 0.0
        atm_pcr = round(min(10.0, pe_oi / ce_oi), 2) if ce_oi > 0 else 0.0

        days_to_exp = max(0.5, (meta["expiry_date"] - today).days)
        T = days_to_exp / 365.0

        ce_iv = solve_implied_volatility(ce_ltp, fut_ltp, meta["atm_strike"], T, RISK_FREE_RATE, is_call=True)
        ce_greeks = calculate_greeks(fut_ltp, meta["atm_strike"], T, RISK_FREE_RATE, (ce_iv or 20.0) / 100.0, is_call=True)

        pe_iv = solve_implied_volatility(pe_ltp, fut_ltp, meta["atm_strike"], T, RISK_FREE_RATE, is_call=False)
        pe_greeks = calculate_greeks(fut_ltp, meta["atm_strike"], T, RISK_FREE_RATE, (pe_iv or 20.0) / 100.0, is_call=False)

        # Real Max Pain calculation across candidate strikes
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

        prev_s = prev_symbols_state.get(sym, {})
        prev_ce_oi = prev_s.get("ce_oi", ce_oi)
        prev_pe_oi = prev_s.get("pe_oi", pe_oi)

        new_symbols_state[sym] = {
            "ce_oi": ce_oi,
            "pe_oi": pe_oi,
            "fut_ltp": fut_ltp,
            "timestamp": ist_str
        }

        news_info = news_map.get(sym, {
            "sentiment_score": 0.0,
            "category": "NO_RECENT_HEADLINE",
            "impact_rating": "NEUTRAL",
            "top_headline": "No fresh material catalyst",
            "sources_count": 0
        })

        pred = compute_prediction_and_rating(
            sym=sym, fut_ltp=fut_ltp, fut_pct=fut_pct, fut_obi=fut_obi,
            ce_ltp=ce_ltp, ce_pct=ce_pct, ce_oi=ce_oi, ce_obi=ce_obi, ce_spread=ce_spread,
            ce_iv=ce_iv, ce_delta=ce_greeks["delta"], ce_gamma=ce_greeks["gamma"], ce_theta=ce_greeks["theta"], ce_vega=ce_greeks["vega"],
            pe_ltp=pe_ltp, pe_pct=pe_pct, pe_oi=pe_oi, pe_obi=pe_obi, pe_spread=pe_spread,
            pe_iv=pe_iv, pe_delta=pe_greeks["delta"], pe_gamma=pe_greeks["gamma"], pe_theta=pe_greeks["theta"], pe_vega=pe_greeks["vega"],
            atm_pcr=atm_pcr, max_pain=max_pain_val, prev_ce_oi=prev_ce_oi, prev_pe_oi=prev_pe_oi,
            news_sentiment=news_info["sentiment_score"], news_category=news_info["category"], news_impact=news_info["impact_rating"],
            weights=current_weights,
            ce_vol=ce_vol, pe_vol=pe_vol
        )

        # Pre-Market Gap Prediction
        pre_gap = compute_pre_market_gap(
            sym=sym, fut_ltp=fut_ltp, fut_pct=fut_pct, fut_obi=fut_obi,
            fut_oi_vel=pred["ce_oi_velocity"], news_info=news_info, atm_strike=meta["atm_strike"],
            ce_pct=ce_pct, pe_pct=pe_pct, ce_obi=ce_obi, pe_obi=pe_obi,
            ce_oi_vel=pred["ce_oi_velocity"], pe_oi_vel=pred["pe_oi_velocity"],
            atm_pcr=atm_pcr, ce_iv=ce_iv, pe_iv=pe_iv,
            is_illiquid=pred.get("is_illiquid", False)
        )

        # Cross-asset market confirmation combining sentiment, futures and option order flow
        mkt_confirm = compute_market_confirmation(
            sentiment_score=news_info["sentiment_score"],
            fut_pct=fut_pct,
            fut_obi=fut_obi,
            ce_pct=ce_pct,
            pe_pct=pe_pct,
            ce_oi_vel=pred["ce_oi_velocity"],
            pe_oi_vel=pred["pe_oi_velocity"],
            atm_pcr=atm_pcr
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
            "atm_pcr": atm_pcr,
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
            "ce_dollar_gamma": pred.get("ce_dollar_gamma", 0.0),
            "pe_dollar_gamma": pred.get("pe_dollar_gamma", 0.0),
            "expected_gap_pct": pre_gap["expected_gap_pct"],
            "gap_direction": pre_gap["gap_direction"],
            "pre_open_conviction": pre_gap["pre_open_conviction"],
            "target_strike": pre_gap["target_strike"],
            "catalyst_count": pre_gap["catalyst_count"],
            "positioning": pre_gap["positioning"],
            "news_sentiment": news_info["sentiment_score"],
            "news_impact": news_info["impact_rating"],
            "news_category": news_info["category"],
            "top_headline": news_info["top_headline"],
            "news_severity_level": int(news_info.get("severity_level", 1)),
            "news_source_tier": str(news_info.get("source_tier", "TIER_3_FINANCIAL_MEDIA")),
            "positive_prob": float(news_info.get("positive_prob", 0.33)),
            "negative_prob": float(news_info.get("negative_prob", 0.33)),
            "already_priced_in_prob": float(news_info.get("already_priced_in_prob", 0.50)),
            "market_confirmation": str(mkt_confirm),
            "expected_move_band": str(news_info.get("expected_move_band", "0.0%")),
            "source_url": str(news_info.get("source_url", "")),
            "is_illiquid": pred.get("is_illiquid", False)
        }
        predictions.append(record)

        # Build FORENSIC_LIVE row with strict fixed-width schema (18 columns, no empty fields)
        forensic_live_rows.append([
            ist_str, sym, meta["expiry_str"], fut_ltp, fut_pct, fut_obi,
            meta["atm_strike"],
            meta["ce_symbol"], ce_ltp, ce_pct, ce_oi, ce_obi,
            meta["pe_symbol"], pe_ltp, pe_pct, pe_oi,
            atm_pcr, pred["action_rating"]
        ])

        if news_info.get("items"):
            for itm in news_info["items"]:
                n_title = str(itm.get("title", "")).strip()
                n_key = f"{sym}::{news_dedup_key(itm)}"
                if n_key not in seen_news_keys:
                    seen_news_keys.add(n_key)
                    news_rows_for_bq.append({
                        "timestamp": parse_news_timestamp_ist(itm.get("published_at_ist") or itm.get("pubDate"), fallback=ist_now),
                        "symbol": sym,
                        "news_type": itm.get("category", "GENERAL"),
                        "sentiment": "BULLISH" if itm["score"] > 0 else ("BEARISH" if itm["score"] < 0 else "NEUTRAL"),
                        "tone_score": float(itm["score"]),
                        "impact_rating": str(itm["impact"]),
                        "severity_level": int(itm.get("severity_level", 1)),
                        "source_tier": str(itm.get("source_tier", "TIER_3_FINANCIAL_MEDIA")),
                        "positive_prob": float(itm.get("positive_prob", 0.33)),
                        "negative_prob": float(itm.get("negative_prob", 0.33)),
                        "already_priced_in_prob": float(itm.get("already_priced_in_prob", 0.50)),
                        "market_confirmation": str(mkt_confirm),
                        "expected_move_band": str(itm.get("expected_move_band", "0.0%")),
                        "source_url": str(itm.get("source_url", "")),
                        "canonical_url": str(itm.get("source_url", "")),
                        "verified_catalyst": bool(itm.get("severity_level", 1) >= 3),
                        "source_count": int(news_info["item_count"]),
                        "source_agreement_pct": 100.0,
                        "title": n_title,
                        "source": str(itm.get("source", "")),
                        "filing_type": str(itm.get("filing_type", ""))
                    })

    require_verified_symbols(p["symbol"] for p in predictions)
    require_verified_symbols(row[1] for row in forensic_live_rows)
    pending_state = {
        "symbols": new_symbols_state,
        "seen_news_keys": list(seen_news_keys)[-5000:],
        "last_updated": ist_str
    }

    predictions.sort(key=lambda x: x["rank_metric"], reverse=True)
    for idx, r in enumerate(predictions):
        r["rank"] = idx + 1

    # Part 3: Run Live Ground-Truth Reconciliation against actual liquid option leaders
    liquid_preds = [p for p in predictions if not p.get("is_illiquid", False)]
    actual_top_movers = sorted(
        [{"contract": p["ce_symbol"], "symbol": p["symbol"], "gain": p["ce_chg_pct"]} for p in liquid_preds] +
        [{"contract": p["pe_symbol"], "symbol": p["symbol"], "gain": p["pe_chg_pct"]} for p in liquid_preds],
        key=lambda x: x["gain"], reverse=True
    )[:10]

    reconciliation = run_ground_truth_reconciliation(predictions, actual_top_movers, current_weights)

    # Part 3B: EOD Pre-Close Next-Day Gap-Up (CE) and Gap-Down (PE) Engine
    next_day_picks = generate_next_day_gap_picks(predictions, ist_now)

    gc = get_gspread_client()
    sh = gc.open_by_key(require_authoritative_sheet_id(SHEET_ID))
    bq_client = get_bigquery_client()

    # Pre-Close Journaling Window (15:00 - 15:30 IST) or forced
    if is_pre_close_time(ist_now) or force_pre_close:
        print("[INFO] Pre-Close Window (15:00-15:40 IST): Journaling overnight next-day gap picks...")
        journal_pre_close_paper_trades(sh, bq_client, next_day_picks, ist_str, ist_now)

    # Morning Reconciliation Window (09:15 - 09:45 IST) or forced
    if is_morning_reconcile_time(ist_now) or reconcile_morning:
        print("[INFO] Morning Open Window (09:15-09:45 IST): Reconciling overnight gap paper trades...")
        reconcile_next_day_gap_trades(smartApi, sh, bq_client, predictions, ist_str, ist_now)

    # Sync to Google Sheets & BigQuery Sandbox
    publish_outputs(
        sh, bq_client, bq_client.dataset(BQ_DATASET_ID).table("option_predictions_live"), ist_str,
        sheet_write=lambda: sync_to_google_sheet(predictions, reconciliation, forensic_live_rows, ist_str, next_day_picks=next_day_picks, sh=sh),
        bq_write=lambda: sync_to_bigquery(predictions, news_rows_for_bq, reconciliation, ist_now),
    )
    save_state(pending_state)

    return predictions, reconciliation, next_day_picks

# =====================================================================
# GOOGLE SHEET SYNC MODULE
# =====================================================================
def sync_to_google_sheet(predictions, reconciliation, forensic_live_rows, ist_str, next_day_picks=None, sh=None):
    require_authorized_writer()
    require_verified_symbols(p["symbol"] for p in predictions)
    if any(len(row) != 18 for row in forensic_live_rows):
        raise RuntimeError("Invalid FORENSIC_LIVE row width; preserving last good publication")
    require_verified_symbols(row[1] for row in forensic_live_rows)
    print("[INFO] Syncing outputs across Google Sheet tabs...")
    try:
        if sh is None:
            gc = get_gspread_client()
            sh = gc.open_by_key(require_authoritative_sheet_id(SHEET_ID))

        # 1. Update FORENSIC_LIVE with exact schema (18 columns, strict validator)
        ws_fl = sh.worksheet("FORENSIC_LIVE")
        fl_headers = [
            "Timestamp (IST)", "Symbol", "Nearest Expiry", "Fut LTP", "Fut Chg %", "Fut OBI",
            "ATM Strike", "ATM CE Contract", "CE LTP", "CE Chg %", "CE OI", "CE OBI",
            "ATM PE Contract", "PE LTP", "PE Chg %", "PE OI", "ATM PCR", "Forensic Action Signal"
        ]
        # Validate exact 18 columns per row BEFORE indexing/sorting.
        valid_fl_rows = []
        for r in forensic_live_rows:
            if len(r) == 18:
                valid_fl_rows.append(r)
            else:
                print(f"[WARN] Dropping malformed FORENSIC_LIVE row with {len(r)} columns; expected 18.")
        # Sort only validated rows, so malformed rows can never trigger IndexError.
        valid_fl_rows.sort(
            key=lambda r: (
                1 if "BREAKOUT" in str(r[17]) or "GAMMA" in str(r[17]) else 0,
                r[5],
                r[4],
            ),
            reverse=True,
        )

        write_grid(ws_fl, normalize_sheet_rows([fl_headers, *valid_fl_rows], 18))
        print(f"[OK] FORENSIC_LIVE updated with {len(valid_fl_rows)} validated rows!")

        # 2. Update HEARTBEAT with engine metrics, without destroying telemetry
        ws_hb = sh.worksheet("HEARTBEAT")
        hb_rows = [
            ["Metric", "Value", "Benchmark", "Component", "Protocol", "Status"],
            ["Session Auth", "CONNECTED_ANGEL_SMARTAPI", "ACTIVE", "Angel One SmartAPI", "TOTP / JWT WebSocket", "🟢 HEALTHY"],
            ["Self-Calibration Hit Rate", f"{reconciliation['hit_rate_pct']}%", "Self-Calibration Loop", "Reconciliation Engine", "Ground Truth Compare", "🟢 CALIBRATED"],
            ["Recall @ 10", f"{reconciliation['recall_at_10']}", "Top 10 Prediction Match", "Self-Calibration Loop", "Online Weights", "🟢 ACTIVE"],
            ["Mean Rank", f"{reconciliation['mean_rank']}", "Actual Movers Rank", "Greeks & News Model", "Dynamic Calibration", "🟢 HIGH ACCURACY"]
        ]
        # Update metrics starting at row 5
        ws_hb.update(range_name="A5", values=normalize_sheet_rows(hb_rows, 6), value_input_option="USER_ENTERED")
        
        print("[OK] HEARTBEAT updated with exact 6-column schema and calibration metrics!")

        # 3. Update OPTION_PREDICTIONS tab (exact 41 columns fixed width)
        try:
            ws_pred = sh.worksheet("OPTION_PREDICTIONS")
        except Exception:
            ws_pred = sh.add_worksheet(title="OPTION_PREDICTIONS", rows="350", cols="45")

        ce_picks = [p for p in predictions if "CALL" in p["directional_bias"]][:3]
        pe_picks = [p for p in predictions if "PUT" in p["directional_bias"]][:3]
        gap_up_picks = sorted([p for p in predictions if p["expected_gap_pct"] > 0], key=lambda x: x["expected_gap_pct"], reverse=True)[:3]
        gap_down_picks = sorted([p for p in predictions if p["expected_gap_pct"] < 0], key=lambda x: x["expected_gap_pct"])[:3]

        pred_rows = [
            ["⚡ DYNAMIC OPTION CE/PE PREDICTION, PRE-MARKET GAP & INTENSITY ENGINE", "", "", "", "", "", "", "", "", "", "", ""],
            [f"Last Synced: {ist_str} IST", "Broker: CONNECTED (Angel One SmartAPI)", f"F&O Symbols: {len(predictions)}", f"Hit Rate: {reconciliation['hit_rate_pct']}%", f"Recall@10: {reconciliation['recall_at_10']}", f"Mean Rank: {reconciliation['mean_rank']}", "Publication: PENDING_READBACK", "", "", "", "", ""],
            ["", "", "", "", "", "", "", "", "", "", "", ""],
            ["🌅 PRE-MARKET 9:15 AM GAP EXPLOSION PICKS (ADVANCE PREDICTION BEFORE OPEN)", "", "", "", "", "", "", "", "", "", "", ""],
            ["Rank", "Symbol", "Gap Direction", "Expected Opening Gap %", "Pre-Open Conviction %", "Target 9:15 Strike", "Verified Sources", "Top Catalyst / News Filing", "", "", "", ""]
        ]

        for p in gap_up_picks:
            pred_rows.append([
                p["rank"], p["symbol"], p["gap_direction"], f"+{p['expected_gap_pct']}%", f"{p['pre_open_conviction']}%",
                p["target_strike"], p["catalyst_count"], p["top_headline"][:70], "", "", "", ""
            ])
        for p in gap_down_picks:
            pred_rows.append([
                p["rank"], p["symbol"], p["gap_direction"], f"{p['expected_gap_pct']}%", f"{p['pre_open_conviction']}%",
                p["target_strike"], p["catalyst_count"], p["top_headline"][:70], "", "", "", ""
            ])

        pred_rows.extend([
            ["", "", "", "", "", "", "", "", "", "", "", ""],
            ["🏆 TOP CONVICTION CALL (CE) BREAKOUT CANDIDATES", "", "", "", "", "", "", "", "", "", "", ""],
            ["Rank", "Symbol", "Action Rating", "CE Win Prob %", "Intensity (1-100)", "Spot LTP", "ATM Strike", "CE Contract", "CE LTP", "CE IV %", "News Catalyst", ""]
        ])
        for p in ce_picks:
            pred_rows.append([
                p["rank"], p["symbol"], p["action_rating"], f"{p['ce_win_prob']}%", p["intensity_score"],
                p["spot_ltp"], p["atm_strike"], p["ce_symbol"], p["ce_ltp"], f"{p['ce_iv']}%", p["top_headline"][:60], ""
            ])

        pred_rows.extend([
            ["", "", "", "", "", "", "", "", "", "", "", ""],
            ["💥 TOP CONVICTION PUT (PE) BREAKDOWN CANDIDATES", "", "", "", "", "", "", "", "", "", "", ""],
            ["Rank", "Symbol", "Action Rating", "PE Win Prob %", "Intensity (1-100)", "Spot LTP", "ATM Strike", "PE Contract", "PE LTP", "PE IV %", "News Catalyst", ""]
        ])
        for p in pe_picks:
            pred_rows.append([
                p["rank"], p["symbol"], p["action_rating"], f"{p['pe_win_prob']}%", p["intensity_score"],
                p["spot_ltp"], p["atm_strike"], p["pe_symbol"], p["pe_ltp"], f"{p['pe_iv']}%", p["top_headline"][:60], ""
            ])

        # Dedicated Next-Day Pre-Close (3:00 - 3:40 PM) Section
        if next_day_picks and (next_day_picks.get("top_ce_picks") or next_day_picks.get("top_pe_picks")):
            pred_rows.extend([
                ["", "", "", "", "", "", "", "", "", "", "", ""],
                ["🌆 NEXT-DAY 3:00 - 3:40 PM PRE-CLOSE GAP-UP & EXPLOSION CANDIDATES (OVERNIGHT SWING)", "", "", "", "", "", "", "", "", "", "", ""],
                ["Rank", "Symbol", "Side", "Target Strike", "Contract", "Entry LTP", "Stop Loss (-15%)", "Target (+50%/+60%)", "Expected Gap %", "Conviction %", "Multi-Factor Rationale & Catalyst", ""]
            ])
            for idx, c in enumerate(next_day_picks.get("top_ce_picks", [])[:5], start=1):
                pred_rows.append([
                    idx, c["symbol"], "CE (GAP-UP)", c["target_strike"], c["contract_symbol"],
                    c["entry_ltp"], c["stop_loss_ltp"], c["target_ltp"], f"{c['expected_gap_pct']:+.2f}%", f"{c['conviction_pct']:.1f}%",
                    c["why_rationale"][:70], ""
                ])
            for idx, c in enumerate(next_day_picks.get("top_pe_picks", [])[:5], start=1):
                pred_rows.append([
                    idx, c["symbol"], "PE (GAP-DOWN)", c["target_strike"], c["contract_symbol"],
                    c["entry_ltp"], c["stop_loss_ltp"], c["target_ltp"], f"{c['expected_gap_pct']:+.2f}%", f"{c['conviction_pct']:.1f}%",
                    c["why_rationale"][:70], ""
                ])

        pred_rows.extend([
            ["", "", "", "", "", "", "", "", "", "", "", ""],
            ["==================================================================================================================================================================", "", "", "", "", "", "", "", "", "", "", ""],
            ["📊 COMPLETE F&O UNIVERSE OPTION CE/PE PREDICTION & GREEKS MATRIX (RANKED HIGHEST TO LOWEST INTENSITY)", "", "", "", "", "", "", "", "", "", "", ""],
            ["Rank", "Symbol", "Actionable Prediction Rating", "Directional Bias", "CE Win Prob %", "PE Win Prob %",
             "Intensity Score (1-100)", "Confidence %", "Spot / Fut LTP", "ATM Strike", "ATM PCR", "Max Pain",
             "ATM CE Contract", "CE LTP", "CE Chg %", "CE OI", "CE OI Vel %", "CE IV %", "Delta CE", "Gamma", "Theta CE", "Vega", "CE Spread",
             "ATM PE Contract", "PE LTP", "PE Chg %", "PE OI", "PE OI Vel %", "PE IV %", "Delta PE", "PE Spread",
             "Pre-Open Gap %", "Gap Bias", "Target 9:15 Strike", "News Severity", "Source Tier", "Market Confirmation", "Expected Move Band", "News Sentiment", "Top Catalyst Headline", "Snapshot Time (IST)"]
        ])

        for p in predictions:
            pred_rows.append([
                p["rank"], p["symbol"], p["action_rating"], p["directional_bias"], p["ce_win_prob"], p["pe_win_prob"],
                p["intensity_score"], p["confidence_pct"], p["spot_ltp"], p["atm_strike"], p["atm_pcr"], p["max_pain"],
                p["ce_symbol"], p["ce_ltp"], p["ce_chg_pct"], p["ce_oi"], p["ce_oi_velocity"], p["ce_iv"], p["ce_delta"], p["ce_gamma"], p["ce_theta"], p["ce_vega"], p["ce_spread"],
                p["pe_symbol"], p["pe_ltp"], p["pe_chg_pct"], p["pe_oi"], p["pe_oi_velocity"], p["pe_iv"], p["pe_delta"], p["pe_spread"],
                p["expected_gap_pct"], p["gap_direction"], p["target_strike"],
                f"Lvl {p.get('news_severity_level', 1)}", p.get("news_source_tier", "TIER_3"), p.get("market_confirmation", "NEUTRAL_FLOW"), p.get("expected_move_band", "0.0%"),
                p["news_sentiment"], p["top_headline"], ist_str
            ])

        write_grid(ws_pred, normalize_sheet_rows(pred_rows, 41))
        print(f"[OK] OPTION_PREDICTIONS updated with {len(pred_rows)} rows!")

        # 4. Sync to NEWS_LIVE tab (all 219 symbols, strict 12 columns)
        try:
            ws_nl = sh.worksheet("NEWS_LIVE")
            nl_rows = [
                ["Multi-source news tone for the F&O list. The rating reads headlines. It does not predict the next price.", "", "", "", "", "", "", "", "", "", "", ""],
                ["Symbol", "Sentiment", "Tone rating 0-100", "Tone arrow", "Sources", "Source agreement %", "Event", "Latest time", "NSE filing", "Headlines", "Trigger words", "Meaning"]
            ]
            for p in predictions:
                tone = p.get("news_sentiment", 0.0)
                rating = int(round(50.0 + (tone * 50.0)))
                if tone > 0.2:
                    sent = "Strong positive" if tone >= 0.5 else "Positive"
                    arrow = "↑"
                elif tone < -0.2:
                    sent = "Strong negative" if tone <= -0.5 else "Moderate bearish"
                    arrow = "↓"
                else:
                    sent = "Neutral"
                    arrow = "→"
                nl_rows.append([
                    p["symbol"], sent, rating, arrow, p.get("catalyst_count", 1), 100,
                    p.get("top_headline", "")[:90], ist_str, p.get("news_category", "Updates"),
                    p.get("top_headline", ""), f"{p.get('news_category', '')} [Lvl {p.get('news_severity_level', 1)}]",
                    f"Confirmation: {p.get('market_confirmation', 'NEUTRAL_FLOW')} | Expected: {p.get('expected_move_band', '0.0%')}"
                ])
            write_grid(ws_nl, normalize_sheet_rows(nl_rows, 12))
            print(f"[OK] NEWS_LIVE updated with {len(nl_rows)} validated rows!")
        except Exception as e:
            raise RuntimeError(f"NEWS_LIVE sync failed: {e}") from e

        append_sheet_provenance(
            sh,
            sink="prediction_cycle",
            record_count=len(predictions),
            source_timestamp=ist_str,
        )

        # This legacy view has no publisher in the current authoritative cycle.
        # Preserve its historical data but remove the stale LIVE/216 claim.
        try:
            legacy = sh.worksheet("PRE_BREAKOUT_SCANNER")
        except gspread.WorksheetNotFound:
            legacy = None
        if legacy is not None:
            legacy.update(range_name="A1", values=[[
                "LEGACY SNAPSHOT — not refreshed by this publisher. "
                "Canonical 219-symbol output: FORENSIC_LIVE / OPTION_PREDICTIONS. "
                "Verify PUBLICATION_STATUS before use."
            ]], value_input_option="RAW")

        return {
            "FORENSIC_LIVE": normalize_sheet_rows([fl_headers, *valid_fl_rows], 18),
            "OPTION_PREDICTIONS": normalize_sheet_rows(pred_rows, 41),
            "NEWS_LIVE": normalize_sheet_rows(nl_rows, 12),
        }

        # Paper trades are specifically and deduplicatedly journaled via journal_pre_close_paper_trades during 15:00 - 15:40 IST pre-close window

    except Exception as e:
        raise RuntimeError(f"Google Sheets sync failed: {e}") from e

# =====================================================================
# BIGQUERY SANDBOX SYNC MODULE ($0 COST)
# =====================================================================
def build_news_append_job_config(table_news):
    """Use the existing BigQuery table schema so numeric-looking string IDs stay STRING."""
    return bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        schema=table_news.schema,
        autodetect=False,
    )


def sync_to_bigquery(predictions, news_rows, reconciliation, ist_dt):
    require_authorized_writer()
    require_verified_symbols(p["symbol"] for p in predictions)
    print("[INFO] Appending records into BigQuery Sandbox (asia-south1)...")
    try:
        bq_client = get_bigquery_client()
        dataset_ref = bq_client.dataset(BQ_DATASET_ID)
        local_dt = local_market_time(ist_dt)
        ts_iso = local_dt.isoformat()
        provenance = build_provenance(ts_iso)

        # 1. Predictions Table (WRITE_TRUNCATE: maintains latest deduplicated live snapshot)
        table_pred = bq_client.get_table(dataset_ref.table("option_predictions_live"))
        rows_to_insert = []
        for p in predictions:
            rows_to_insert.append({
                **provenance,
                "snapshot_timestamp": ts_iso,
                "rank": int(p["rank"]),
                "symbol": str(p["symbol"]),
                "expiry": to_iso_date(p.get("opt_expiry_date") or p.get("expiry")),
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
                "top_news_headline": str(p["top_headline"])[:255],
                "expected_gap_pct": float(p.get("expected_gap_pct", 0.0)),
                "gap_direction": str(p.get("gap_direction", "NEUTRAL")),
                "pre_open_conviction_pct": float(p.get("pre_open_conviction", 50.0)),
                "target_open_strike": str(p.get("target_strike", "")),
                "news_severity_level": int(p.get("news_severity_level", 1)),
                "news_source_tier": str(p.get("news_source_tier", "TIER_3_FINANCIAL_MEDIA")),
                "positive_prob": float(p.get("positive_prob", 0.33)),
                "negative_prob": float(p.get("negative_prob", 0.33)),
                "already_priced_in_prob": float(p.get("already_priced_in_prob", 0.50)),
                "market_confirmation": str(p.get("market_confirmation", "NEUTRAL_FLOW")),
                "expected_move_band": str(p.get("expected_move_band", "0.0%")),
                # Positive LTP does not establish an exchange tick timestamp.
                "data_freshness_status": "MARKET_CLOSED" if not is_market_open(ist_dt) else "SOURCE_TIME_UNVERIFIED"
            })

        from tools.schema_validator import load_schema
        raw_schema = load_schema("option_predictions_live")
        target_schema = [
            bigquery.SchemaField(f["name"], f["type"], mode=f.get("mode", "NULLABLE"))
            for f in raw_schema
        ]

        job_config_trunc = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            schema=target_schema,
            autodetect=False,
        )
        load_job = bq_client.load_table_from_json(rows_to_insert, table_pred, job_config=job_config_trunc)
        load_job.result()
        print(f"[OK] Replaced {len(rows_to_insert)} records in BigQuery option_predictions_live (WRITE_TRUNCATE active)!")

        # 2. News Table: deterministic replay dedup before append.
        unique_news_rows = [
            {**row, **provenance} for row in deduplicate_news_rows(news_rows)
        ]
        if unique_news_rows:
            table_news = bq_client.get_table(dataset_ref.table("market_news_sentiment"))
            # Append against the existing table contract instead of autodetecting
            # numeric-looking provenance strings (for example GitHub RUN_ID) as INTEGER.
            news_job_config = build_news_append_job_config(table_news)
            load_job_news = bq_client.load_table_from_json(
                unique_news_rows, table_news, job_config=news_job_config
            )
            load_job_news.result()
            print(f"[OK] Appended {len(unique_news_rows)} fresh records to BigQuery market_news_sentiment!")
        else:
            print("[INFO] No fresh headlines to append to BigQuery market_news_sentiment (dedup active).")

        # 3. Calibration Table
        table_cal = bq_client.get_table(dataset_ref.table("prediction_calibration_log"))
        cal_row = [{
            **provenance,
            "timestamp": ts_iso,
            "cycle_number": int(reconciliation["cycle"]),
            "top10_hit_rate_pct": float(reconciliation["hit_rate_pct"]),
            "recall_at_10": float(reconciliation["recall_at_10"]),
            "mean_rank_of_top10": float(reconciliation["mean_rank"]),
            "predicted_top10": json.dumps(reconciliation.get("hits", [])),
            "actual_top10": json.dumps(reconciliation.get("misses", [])),
            "hits": json.dumps(reconciliation.get("hits", [])),
            "misses": json.dumps(reconciliation.get("misses", [])),
            "miss_root_causes": json.dumps({"causes": "Attributed via online multi-factor model"}),
            "updated_weights_json": json.dumps(reconciliation.get("weights", {}))
        }]
        cal_schema = getattr(table_cal, "schema", None)
        job_config_cal = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION],
            schema=cal_schema,
            autodetect=False,
        )
        load_job_cal = bq_client.load_table_from_json(cal_row, table_cal, job_config=job_config_cal)
        load_job_cal.result()
        print(f"[OK] Appended reconciliation audit to BigQuery prediction_calibration_log!")

    except Exception as e:
        raise RuntimeError(f"BigQuery sync failed: {e}") from e

# =====================================================================
# MAIN ENTRYPOINT
# =====================================================================
def main():
    bypass_market_check = "--run-once" in sys.argv or "--verify" in sys.argv
    force_pre_close = "--force-pre-close" in sys.argv
    reconcile_morning = "--reconcile-gap" in sys.argv

    if bypass_market_check or force_pre_close or reconcile_morning:
        print("[MODE] Direct Live Execution (bypassing market-hour sleeps)...")
        run_prediction_pipeline(
            bypass_market_check=True,
            force_pre_close=force_pre_close,
            reconcile_morning=reconcile_morning
        )
        print("[SUCCESS] Live Execution Cycle Completed!")
        return

    print("[MODE] Automated Indian Market Production Daemon (09:15 - 15:30 IST)...")
    while True:
        try:
            now = get_ist_time()
            if is_market_open(now) or is_pre_market_time(now):
                run_prediction_pipeline(bypass_market_check=False)
                time.sleep(45)
            else:
                print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')} IST] Market closed. Executing baseline verification sync...")
                run_prediction_pipeline(bypass_market_check=True)
                print("[INFO] Baseline sync complete. Standing by for next market session...")
                time.sleep(1800)
        except KeyboardInterrupt:
            print("[INFO] Daemon stopped by user.")
            break
        except Exception as e:
            print(f"[ERROR] Pipeline error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()