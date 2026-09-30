import ast
import datetime
import json
import os
import re
import time
import urllib.request
from collections import defaultdict
from zoneinfo import ZoneInfo

import gspread
import pyotp
from SmartApi import SmartConnect

from gainers import (
    contracts_from_forensic,
    market_is_open,
    quote_from_angel,
    render_gainer_sheet,
    strike_window_tokens,
)
from paper_log import alerts_to_append, fill_later_changes, render_production_sheet

SHEET_ID = os.getenv("SHEET_ID", "1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs")
MAX_RUNTIME_SECONDS = max(1, int(os.getenv("MAX_RUNTIME_SECONDS", "22500")))
IST = ZoneInfo("Asia/Kolkata")
DAEMON_FRESH_SECONDS = 90
FORENSIC_HEADER = [
    "Timestamp (IST)", "Symbol", "Nearest Expiry", "Fut LTP", "Fut Chg %", "Fut OBI",
    "ATM Strike", "ATM CE Contract", "CE LTP", "CE Chg %", "CE OI", "CE OBI",
    "ATM PE Contract", "PE LTP", "PE Chg %", "PE OI", "ATM PCR", "Forensic Action Signal",
]


def now_ist():
    return datetime.datetime.now(IST).replace(tzinfo=None)


def parse_exp(value):
    try:
        return datetime.datetime.strptime(str(value).strip().upper(), "%d%b%Y").date()
    except (TypeError, ValueError):
        return None


def load_service_account():
    # Accept normal JSON plus common GitHub-secret copy/paste forms with one or
    # multiple backslashes before JSON quotes. Do not alter \\n in private_key.
    raw_sheet_secret = os.environ["SHEETS_KEY_JSON"].strip()
    candidates = [raw_sheet_secret]
    normalized_quotes = re.sub(r'\\+"', '"', raw_sheet_secret)
    if normalized_quotes not in candidates:
        candidates.append(normalized_quotes)

    if len(raw_sheet_secret) >= 2 and raw_sheet_secret[0] == raw_sheet_secret[-1] and raw_sheet_secret[0] in ("'", '"'):
        inner = raw_sheet_secret[1:-1]
        candidates.append(inner)
        candidates.append(re.sub(r'\\+"', '"', inner))

    sheet_info = None
    json_error = "unparsed"
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
            if isinstance(parsed, dict):
                sheet_info = parsed
                break
        except (json.JSONDecodeError, TypeError) as exc:
            json_error = str(exc)

    if sheet_info is None:
        try:
            parsed = ast.literal_eval(raw_sheet_secret)
            if isinstance(parsed, dict):
                sheet_info = parsed
        except (ValueError, SyntaxError):
            pass

    if not isinstance(sheet_info, dict) or sheet_info.get("type") != "service_account":
        structural = {
            "length": len(raw_sheet_secret),
            "starts_lbrace": raw_sheet_secret.startswith("{"),
            "ends_rbrace": raw_sheet_secret.endswith("}"),
            "double_quotes": raw_sheet_secret.count('"'),
            "single_quotes": raw_sheet_secret.count("'"),
            "backslashes": raw_sheet_secret.count("\\"),
            "newlines": raw_sheet_secret.count("\n"),
        }
        raise RuntimeError(
            "SHEETS_KEY_JSON is not valid Google service-account JSON; "
            f"json_error={json_error}; safe_format_stats={structural}"
        )
    return sheet_info


def worksheet(book, title, rows=400, cols=26):
    try:
        return book.worksheet(title)
    except gspread.WorksheetNotFound:
        return book.add_worksheet(title=title, rows=rows, cols=cols)


def write_grid(ws, rows):
    ws.clear()
    if rows:
        ws.update(range_name="A1", values=rows, value_input_option="RAW")


def heartbeat_age_seconds(book, now):
    try:
        stamped = book.worksheet("HEARTBEAT").acell("A2").value
    except gspread.WorksheetNotFound:
        return None
    if not stamped:
        return None
    try:
        wrote = datetime.datetime.strptime(str(stamped).strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return max(0, (now - wrote).total_seconds())


def publish_gainers(book, quotes, now, source):
    rows = render_gainer_sheet(quotes, now, source)
    for title in ("Sheet1", "TOP_GAINERS"):
        write_grid(worksheet(book, title, rows=max(200, len(rows) + 10), cols=len(rows[3]) if len(rows) > 3 else 26), rows)
    print(f"[OK] Wrote {max(0, len(rows) - 4)} real gainer rows to Sheet1 and TOP_GAINERS from {source}")
    return rows


def publish_production(book, now):
    paper = worksheet(book, "PAPER_ALERT_LOG")
    values = paper.get_all_values()
    write_grid(worksheet(book, "PRODUCTION_APPROVED"), render_production_sheet(values, now))


def sync_paper(book, signals, latest_changes, now):
    paper = worksheet(book, "PAPER_ALERT_LOG")
    values = paper.get_all_values()
    if not values:
        values = [[
            "Logged at IST", "Session date", "Symbol", "Side", "Fut LTP", "Session change %",
            "CE contract", "PE contract", "Note", "Later session change %", "Outcome filled at",
        ]]
        write_grid(paper, values)
    filled = fill_later_changes(values, latest_changes, now)
    if filled is not None:
        write_grid(paper, filled)
        values = filled
    fresh = alerts_to_append(values, signals, now, market_is_open(now))
    if fresh:
        paper.append_rows(fresh, value_input_option="RAW")
        print(f"[OK] Logged {len(fresh)} live paper alerts")


def angel_login():
    client_code = os.environ["ANGEL_CLIENT_CODE"]
    totp = pyotp.TOTP(os.environ["ANGEL_TOTP_SEED"]).now()
    api = SmartConnect(api_key=os.environ["ANGEL_API_KEY"])
    session = api.generateSession(client_code, os.environ["ANGEL_PIN"], totp)
    if not session or not session.get("status"):
        raise RuntimeError(f"Angel login failed: {session}")
    print(f"[OK] Angel Session Active for {client_code}")
    return api


def discover_universe(api):
    print("[INFO] Discovering symbols...")
    with urllib.request.urlopen(
        "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json",
        timeout=25,
    ) as response:
        scrip_master = json.loads(response.read().decode("utf-8"))

    today = now_ist().date()
    options = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    futures = defaultdict(list)
    for contract in scrip_master:
        if contract.get("exch_seg") != "NFO":
            continue
        name = str(contract.get("name", "")).strip().upper()
        instrument = str(contract.get("instrumenttype", "")).strip().upper()
        trading_symbol = str(contract.get("symbol", "")).strip().upper()
        expiry = parse_exp(contract.get("expiry", ""))
        if not name or expiry is None or expiry < today:
            continue
        if instrument in ("OPTSTK", "OPTIDX"):
            strike = float(contract.get("strike", 0.0) or 0.0) / 100.0
            if strike <= 0:
                continue
            side = "CE" if trading_symbol.endswith("CE") else "PE" if trading_symbol.endswith("PE") else ""
            if not side:
                continue
            options[name][expiry][strike][side] = {
                "token": str(contract.get("token")),
                "symbol": trading_symbol,
                "name": name,
                "expiry": expiry,
            }
        elif instrument in ("FUTSTK", "FUTIDX"):
            futures[name].append({"token": str(contract.get("token")), "expiry": expiry})

    universe = {}
    for symbol, expiry_map in options.items():
        if symbol not in futures:
            continue
        nearest = min(expiry_map)
        both = {strike: sides for strike, sides in expiry_map[nearest].items() if "CE" in sides and "PE" in sides}
        if not both:
            continue
        future = sorted(futures[symbol], key=lambda item: item["expiry"])[0]
        universe[symbol] = {
            "token": future["token"],
            "expiry": nearest,
            "strikes": both,
        }
    print(f"[OK] Tracking {len(universe)} symbols")
    return universe


def fetch_chunked(api, tokens, size=45):
    quotes = {}
    failures = 0
    for start in range(0, len(tokens), size):
        chunk = tokens[start:start + size]
        for attempt in range(3):
            try:
                response = api.getMarketData("FULL", {"NFO": chunk})
                if not response or not response.get("status"):
                    raise RuntimeError(f"market data status failed for {len(chunk)} tokens")
                for item in response.get("data", {}).get("fetched", []) or []:
                    quotes[str(item.get("symbolToken"))] = item
                break
            except Exception as exc:
                if attempt == 2:
                    failures += 1
                    print(f"[WARN] Quote chunk failed after retries: {exc}")
                else:
                    time.sleep(0.6 * (attempt + 1))
        time.sleep(0.35)
    return quotes, failures


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_forensic_rows(universe, future_quotes, option_quotes, stamped):
    rows = []
    latest_changes = {}
    signals = []
    for symbol, meta in universe.items():
        future = future_quotes.get(meta["token"])
        if not future:
            continue
        future_ltp = _number(future.get("ltp"))
        if future_ltp <= 0:
            continue
        strike = min(meta["strikes"], key=lambda item: abs(item - future_ltp))
        call = meta["strikes"][strike]["CE"]
        put = meta["strikes"][strike]["PE"]
        if call["token"] not in option_quotes or put["token"] not in option_quotes:
            continue
        call_quote = option_quotes[call["token"]]
        put_quote = option_quotes[put["token"]]
        future_change = _number(future.get("percentChange"))
        buy_qty = int(_number(future.get("totBuyQuan")))
        sell_qty = int(_number(future.get("totSellQuan")))
        future_obi = round((buy_qty - sell_qty) / max(1, buy_qty + sell_qty), 3)
        call_ltp = _number(call_quote.get("ltp"))
        call_change = _number(call_quote.get("percentChange"))
        call_oi = int(_number(call_quote.get("opnInterest")))
        call_buy = int(_number(call_quote.get("totBuyQuan")))
        call_sell = int(_number(call_quote.get("totSellQuan")))
        call_obi = round((call_buy - call_sell) / max(1, call_buy + call_sell), 3)
        put_ltp = _number(put_quote.get("ltp"))
        put_change = _number(put_quote.get("percentChange"))
        put_oi = int(_number(put_quote.get("opnInterest")))
        pcr = "" if call_oi <= 0 else round(put_oi / call_oi, 2)
        if future_change >= 0.4 and future_obi >= 0.12 and call_ltp > 0:
            signal = "PRE-BREAKOUT CALL ACCUMULATION"
            side = "CE"
        elif future_change <= -0.4 and future_obi <= -0.12 and put_ltp > 0:
            signal = "BEARISH BREAKDOWN ACCUMULATION"
            side = "PE"
        else:
            signal = "NEUTRAL / CONSOLIDATION"
            side = ""
        rows.append([
            stamped, symbol, meta["expiry"].strftime("%d-%b-%Y"), future_ltp, future_change, future_obi, strike,
            call["symbol"], call_ltp, call_change, call_oi, call_obi,
            put["symbol"], put_ltp, put_change, put_oi, pcr, signal,
        ])
        latest_changes[symbol] = future_change
        if side:
            signals.append({
                "symbol": symbol,
                "side": side,
                "fut_ltp": future_ltp,
                "session_change": future_change,
                "ce_contract": call["symbol"],
                "pe_contract": put["symbol"],
            })
    rows.sort(key=lambda row: (1 if "PRE-BREAKOUT" in str(row[17]) else 0, row[5]), reverse=True)
    return rows, signals, latest_changes


def build_chain_quotes(universe, future_quotes, option_quotes, each_side):
    quotes = []
    for symbol, meta in universe.items():
        future = future_quotes.get(meta["token"])
        if not future:
            continue
        future_ltp = _number(future.get("ltp"))
        if future_ltp <= 0:
            continue
        for token, quote_meta in strike_window_tokens(meta["strikes"], future_ltp, each_side):
            raw = option_quotes.get(token)
            if not raw:
                continue
            quote_meta = dict(quote_meta)
            quote_meta["future_ltp"] = future_ltp
            quote_meta["expiry"] = meta["expiry"]
            built = quote_from_angel(raw, quote_meta)
            if built is not None:
                quotes.append(built)
    return quotes


def run_angel_loop(book, api):
    universe = discover_universe(api)
    each_side = 1 if MAX_RUNTIME_SECONDS <= 120 else int(os.getenv("STRIKE_WINDOW", "6"))
    started = time.time()
    loop = 0
    while time.time() - started < MAX_RUNTIME_SECONDS:
        now = now_ist()
        stamped = now.strftime("%Y-%m-%d %H:%M:%S")
        future_quotes, future_failures = fetch_chunked(api, [meta["token"] for meta in universe.values()])
        tokens = []
        for meta in universe.values():
            future = future_quotes.get(meta["token"])
            future_ltp = _number(future.get("ltp")) if future else 0
            if future_ltp <= 0:
                continue
            tokens.extend(token for token, _meta in strike_window_tokens(meta["strikes"], future_ltp, each_side))
        option_quotes, option_failures = fetch_chunked(api, tokens)
        is_api_failure = (tokens and not option_quotes) or (not future_quotes and len(universe) > 0)
        if is_api_failure:
            print("[WARN] Option quote feed returned nothing. Existing sheets were left unchanged.")
            consecutive_failures = getattr(api, '_consecutive_failures', 0) + 1
            api._consecutive_failures = consecutive_failures
            if consecutive_failures >= 3:
                print(f"[WARN] {consecutive_failures} consecutive failures. Attempting re-login.")
                import random
                sleep_time = min((2 ** (consecutive_failures - 3)) + random.uniform(0, 1), 60)
                time.sleep(sleep_time)
                try:
                    api = angel_login()
                    universe = discover_universe(api)
                    api._consecutive_failures = 0
                except Exception as e:
                    print(f"[ERROR] Re-login failed: {e}")
                continue
            
            loop += 1
            if not market_is_open(now) or MAX_RUNTIME_SECONDS <= 120 or (now.hour == 15 and now.minute > 35):
                break
            time.sleep(30)
            continue
        api._consecutive_failures = 0
        forensic_rows, signals, latest_changes = build_forensic_rows(universe, future_quotes, option_quotes, stamped)
        chain_quotes = build_chain_quotes(universe, future_quotes, option_quotes, each_side)
        try:
            if forensic_rows:
                live = worksheet(book, "FORENSIC_LIVE", rows=max(300, len(forensic_rows) + 5), cols=18)
                write_grid(live, [FORENSIC_HEADER, *forensic_rows])
                heartbeat = worksheet(book, "HEARTBEAT")
                telemetry_header = [
                    "Last Data Fetch (IST)", 
                    "Angel Broker Connection Status", 
                    "Last BigQuery Sync (IST)", 
                    "Stream Health", 
                    "Outage Start (IST)", 
                    "Outage End (IST)", 
                    "Outage Duration (s)", 
                    "Data Missed Estimate (Rows)"
                ]
                
                try:
                    existing_header = heartbeat.row_values(1)
                except Exception:
                    existing_header = []
                    
                if existing_header != telemetry_header:
                    heartbeat.update(range_name="A1", values=[telemetry_header], value_input_option="RAW")
                    existing_header = telemetry_header
                
                try:
                    last_fetch_str = heartbeat.acell("A2").value
                except Exception:
                    last_fetch_str = None
                
                outage_start = ""
                outage_end = ""
                outage_duration = ""
                data_missed = ""
                
                if last_fetch_str:
                    try:
                        last_time = datetime.datetime.strptime(str(last_fetch_str).strip(), "%Y-%m-%d %H:%M:%S")
                        gap = (now - last_time).total_seconds()
                        if gap > 300 and market_is_open(last_time) and market_is_open(now):
                            outage_start = str(last_time.strftime("%Y-%m-%d %H:%M:%S"))
                            outage_end = stamped
                            outage_duration = str(int(gap))
                            data_missed = str(int(gap / 30) * max(1, len(forensic_rows)))
                    except Exception:
                        pass
                
                row_data = {
                    "Last Data Fetch (IST)": stamped,
                    "Angel Broker Connection Status": "CONNECTED_ANGEL_SMARTAPI",
                    "Stream Health": "🟢 HEALTHY" if not outage_duration else "🔴 OUTAGE RECOVERED",
                }
                
                if outage_duration:
                    row_data["Outage Start (IST)"] = outage_start
                    row_data["Outage End (IST)"] = outage_end
                    row_data["Outage Duration (s)"] = outage_duration
                    row_data["Data Missed Estimate (Rows)"] = data_missed
                
                try:
                    current_row = heartbeat.row_values(2)
                except Exception:
                    current_row = []
                    
                current_row = (current_row + [""] * len(telemetry_header))[:len(telemetry_header)]
                
                for i, col in enumerate(telemetry_header):
                    if col in row_data:
                        current_row[i] = row_data[col]
                        
                heartbeat.update(range_name="A2", values=[current_row], value_input_option="RAW")
            else:
                print("[WARN] Angel returned no futures quotes. FORENSIC_LIVE was left unchanged.")
            if chain_quotes:
                publish_gainers(book, chain_quotes, now, "Angel One SmartAPI FULL")
            else:
                print("[WARN] Angel returned no option quotes. Gainers sheet was left unchanged.")
            sync_paper(book, signals, latest_changes, now)
            publish_production(book, now)
            print(
                f"[{stamped}] Forensic {len(forensic_rows)} | Chain quotes {len(chain_quotes)} | "
                f"Quote chunk failures {future_failures + option_failures} | Loop #{loop}"
            )
        except Exception as exc:
            print(f"[WARN] Sheet update failed: {exc}")
        loop += 1
        if not market_is_open(now) or MAX_RUNTIME_SECONDS <= 120:
            print("[INFO] Single real quote pass complete.")
            break
        remaining = MAX_RUNTIME_SECONDS - (time.time() - started)
        time.sleep(min(30, max(0, remaining)))


def refresh_from_forensic(book, now):
    forensic = worksheet(book, "FORENSIC_LIVE").get_all_values()
    quotes = contracts_from_forensic(forensic)
    if not quotes:
        raise RuntimeError("FORENSIC_LIVE has no priced contracts to publish")
    publish_gainers(book, quotes, now, "FORENSIC_LIVE")
    latest = {}
    header = forensic[0]
    try:
        symbol_at = [str(cell).strip().lower() for cell in header].index("symbol")
        change_at = [str(cell).strip().lower() for cell in header].index("fut chg %")
    except ValueError:
        symbol_at = change_at = None
    if symbol_at is not None:
        for row in forensic[1:]:
            if symbol_at < len(row) and change_at < len(row) and str(row[symbol_at]).strip():
                try:
                    latest[str(row[symbol_at]).strip().upper()] = float(row[change_at])
                except ValueError:
                    continue
    sync_paper(book, [], latest, now)
    publish_production(book, now)


def main():
    book = gspread.service_account_from_dict(load_service_account()).open_by_key(SHEET_ID)
    now = now_ist()
    age = heartbeat_age_seconds(book, now)
    if age is not None and age <= DAEMON_FRESH_SECONDS:
        print(f"[INFO] HEARTBEAT is {int(age)}s old. Skipping a second Angel login.")
        refresh_from_forensic(book, now)
        return
    print(f"[INFO] HEARTBEAT age={age}. Opening Angel for a real quote pass.")
    run_angel_loop(book, angel_login())
    try:
        from angel_prediction_engine import run_prediction_pipeline
        print("[INFO] Invoking Option CE/PE Prediction & Rating Pipeline...")
        run_prediction_pipeline(bypass_market_check=True)
    except Exception as exc:
        print(f"[WARN] Prediction engine run notice: {exc}")


if __name__ == "__main__":
    main()
