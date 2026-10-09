import ast

# ====================================================================
# DYNAMIC TELEMETRY GUARDS & LOCAL BACKUP FALLBACKS (SDLC PROTECTION)
# ====================================================================
import json
import uuid
import tempfile
import datetime
from pathlib import Path

def enforce_run_id_string_contract(payload_row):
    """
    Enforces that 'run_id' is strictly a STRING to prevent mismatch with
    the fno_predictions.market_news_sentiment BigQuery schema.
    """
    if not isinstance(payload_row, dict):
        return payload_row

    # Enforce run_id is a STRING if present
    if 'run_id' in payload_row:
        if payload_row['run_id'] is None:
            payload_row['run_id'] = str(uuid.uuid4())
        else:
            payload_row['run_id'] = str(payload_row['run_id'])
    else:
        payload_row['run_id'] = str(uuid.uuid4())

    # Enforce other critical metadata strings
    for key in ['git_sha', 'writer_id', 'cycle_id']:
        if key in payload_row and payload_row[key] is not None:
            payload_row[key] = str(payload_row[key])

    return payload_row

def write_local_backup_buffer(dataset_name, table_name, failed_rows):
    """
    Saves failed transaction records to a local JSON buffer in /tmp/angel_telemetry_backup
    to completely prevent data loss in case of a BQ/Sheets sink crash.
    """
    backup_dir = Path("/tmp/angel_telemetry_backup")
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    backup_file = backup_dir / f"{dataset_name}_{table_name}_fallback_{timestamp_str}_{unique_id}.json"

    try:
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump({
                "dataset": dataset_name,
                "table": table_name,
                "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "rows": failed_rows
            }, f, indent=2, default=str)
        print(f"[BACKUP] Safely buffered {len(failed_rows)} rows to local backup: {backup_file}")
    except Exception as e:
        print(f"[CRITICAL ERROR] Failed to write local backup buffer: {e}")

# ====================================================================

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

from credentials import (
    get_angel_credentials,
    load_env,
    load_service_account as load_sa_credentials,
    require_authoritative_sheet_id,
    validate_angel_credentials,
)
from gainers import (
    contracts_from_forensic,
    market_is_open,
    quote_from_angel,
    render_gainer_sheet,
    strike_window_tokens,
)
from paper_log import alerts_to_append, fill_later_changes, render_production_sheet
from writer_guard import append_sheet_provenance, require_authorized_writer
from sheet_grid import write_grid

load_env()
SHEET_ID = os.getenv("SHEET_ID", "").strip()
MAX_RUNTIME_SECONDS = max(1, int(os.getenv("MAX_RUNTIME_SECONDS", "22500")))
IST = ZoneInfo("Asia/Kolkata")
from universe_contract import EXPECTED_FNO_UNIVERSE_COUNT, select_verified_universe, require_verified_symbols
# Static literal duplicated for infra_readiness.py AST probe (does not import scanner at import time).
# MUST equal universe_contract.EXPECTED_FNO_UNIVERSE_COUNT.
EXPECTED_FNO_UNIVERSE_COUNT = 219
DAEMON_FRESH_SECONDS = 90
PREDICTION_INTERVAL_SECONDS = max(300, int(os.getenv("PREDICTION_INTERVAL_SECONDS", "900")))
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
    return load_sa_credentials()


def worksheet(book, title, rows=400, cols=26):
    try:
        return book.worksheet(title)
    except gspread.WorksheetNotFound:
        return book.add_worksheet(title=title, rows=rows, cols=cols)



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
    for title in ("CE_PE_RANK", "TOP_GAINERS"):
        write_grid(worksheet(book, title, rows=max(200, len(rows) + 10), cols=len(rows[3]) if len(rows) > 3 else 26), rows)
    print(f"[OK] Wrote {max(0, len(rows) - 4)} real gainer rows to CE_PE_RANK and TOP_GAINERS from {source}")
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
        # PAPER_ALERT_LOG is append-only. NEVER call write_grid here —
        # write_grid uses batch_clear and can destroy historical rows.
        # Only update columns J and K in place.
        if len(filled) > 1:
            batch_payload = []
            for idx, r in enumerate(filled[1:], start=2):
                batch_payload.append({
                    "range": f"J{idx}:K{idx}",
                    "values": [[r[9] if len(r) > 9 else "",
                                r[10] if len(r) > 10 else ""]],
                })
            paper.batch_update(batch_payload, value_input_option="RAW")
        values = filled
    fresh = alerts_to_append(values, signals, now, market_is_open(now))
    if fresh:
        paper.append_rows(fresh, value_input_option="RAW")
        print(f"[OK] Logged {len(fresh)} live paper alerts")


def angel_login():
    load_env()
    missing = validate_angel_credentials()
    if missing:
        raise RuntimeError(
            "Angel One credentials are required only when broker access is invoked; "
            f"missing environment variables: {', '.join(missing)}"
        )
    creds = get_angel_credentials()
    totp = pyotp.TOTP(creds["ANGEL_TOTP_SEED"]).now()
    api = SmartConnect(api_key=creds["ANGEL_API_KEY"])
    session = api.generateSession(creds["ANGEL_CLIENT_CODE"], creds["ANGEL_PIN"], totp)
    if not session or not session.get("status"):
        raise RuntimeError(f"Angel login failed: {session}")
    print("[OK] Angel Session Active")
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
    universe = select_verified_universe(universe)
    print(f"[OK] Tracking {len(universe)} symbols")
    return universe


def fetch_chunked(api, tokens, size=45):
    quotes = {}
    failures = 0
    for start in range(0, len(tokens), size):
        chunk = tokens[start:start + size]
        for attempt in range(4):
            try:
                response = api.getMarketData("FULL", {"NFO": chunk})
                if not response or not response.get("status"):
                    raise RuntimeError(f"market data status failed for {len(chunk)} tokens")
                for item in response.get("data", {}).get("fetched", []) or []:
                    if os.getenv("ANGEL_REQUIRE_EXCHANGE_TIME") == "1":
                        from tools.exchange_timestamp import get_exchange_timestamp
                        get_exchange_timestamp(item)
                    quotes[str(item.get("symbolToken"))] = item
                break
            except Exception as exc:
                if attempt == 3:
                    failures += 1
                    print(f"[ERROR] Quote chunk failed permanently after retries: {exc}")
                else:
                    backoff = (2 ** attempt) + 0.5
                    print(f"[WARN] Quote chunk error: {exc}. Retrying in {backoff}s...")
                    time.sleep(backoff)
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


def run_prediction_with_retry(attempts=3, force_pre_close=False):
    from angel_prediction_engine import run_prediction_pipeline

    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            print(f"[INFO] Prediction cycle attempt {attempt}/{attempts}...")
            return run_prediction_pipeline(bypass_market_check=True, force_pre_close=force_pre_close)
        except Exception as exc:
            last_error = exc
            if attempt >= attempts:
                raise
            delay = min(30 * attempt, 90)
            print(f"[WARN] Prediction cycle failed: {exc}. Retrying in {delay}s...")
            time.sleep(delay)
    raise last_error


def run_angel_loop(book, api):
    universe = discover_universe(api)
    each_side = 1 if MAX_RUNTIME_SECONDS <= 120 else int(os.getenv("STRIKE_WINDOW", "6"))
    started = time.time()
    loop = 0
    prediction_ran = False
    last_prediction_epoch = 0.0
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
        if os.getenv("ANGEL_REQUIRE_EXCHANGE_TIME") == "1":
            from tools.cycle_metadata import generate_cycle_metadata
            import json
            import subprocess
            from pathlib import Path
            if len(universe) != 219:
                raise RuntimeError(f"Expected 219 verified futures, got {len(universe)}")
            quote_list = []
            for item in universe.values():
                quote = future_quotes.get(item["token"])
                if not quote:
                    raise RuntimeError("Missing futures quote: exchange freshness unverifiable")
                quote_list.append(quote)
            run_id = os.getenv("GITHUB_RUN_ID") or os.getenv("RUN_ID")
            if not run_id:
                raise RuntimeError("Missing run ID for authoritative provenance")
            git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
            session = os.getenv("ANGEL_MARKET_SESSION", "EOD")
            meta = generate_cycle_metadata(quote_list, run_id, git_sha, session)
            meta_path = Path(os.getenv("ANGEL_CYCLE_METADATA_FILE", "/tmp/cycle_metadata.json"))
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = meta_path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            os.replace(temp_path, meta_path)
            prov_path = Path("scratch") / "provenance" / f"{run_id}.json"
            prov_path.parent.mkdir(parents=True, exist_ok=True)
            prov_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
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
            if not market_is_open(now) or MAX_RUNTIME_SECONDS <= 120 or (now.hour == 15 and now.minute > 40):
                break
            time.sleep(30)
            continue
        api._consecutive_failures = 0
        forensic_rows, signals, latest_changes = build_forensic_rows(universe, future_quotes, option_quotes, stamped)
        chain_quotes = build_chain_quotes(universe, future_quotes, option_quotes, each_side)
        try:
            require_verified_symbols(row[1] for row in forensic_rows)
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
                    "Stream Health": "ðŸŸ¢ HEALTHY" if not outage_duration else "ðŸ”´ OUTAGE RECOVERED",
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

                # Last BigQuery Sync (IST) must be a timestamp or blank - never a row count.
                bq_sync_col = "Last BigQuery Sync (IST)"
                if bq_sync_col in telemetry_header:
                    bq_idx = telemetry_header.index(bq_sync_col)
                    prev = str(current_row[bq_idx]).strip() if current_row[bq_idx] is not None else ""
                    if prev:
                        try:
                            datetime.datetime.strptime(prev[:19], "%Y-%m-%d %H:%M:%S")
                        except Exception:
                            current_row[bq_idx] = ""
                    else:
                        current_row[bq_idx] = ""
                
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
            append_sheet_provenance(
                book,
                sink="scanner_quote_loop",
                record_count=len(forensic_rows),
                source_timestamp=stamped,
            )
            print(
                f"[{stamped}] Forensic {len(forensic_rows)} | Chain quotes {len(chain_quotes)} | "
                f"Quote chunk failures {future_failures + option_failures} | Loop #{loop}"
            )
            if market_is_open(now) and (time.time() - last_prediction_epoch >= PREDICTION_INTERVAL_SECONDS):
                print("[INFO] Running scheduled intraday prediction/readback cycle...")
                run_prediction_with_retry()
                prediction_ran = True
                last_prediction_epoch = time.time()
        except Exception as exc:
            raise RuntimeError("Scanner publication failed; cycle is unverified") from exc
        loop += 1
        if not market_is_open(now) or MAX_RUNTIME_SECONDS <= 120:
            print("[INFO] Single real quote pass complete.")
            break
        remaining = MAX_RUNTIME_SECONDS - (time.time() - started)
        time.sleep(min(30, max(0, remaining)))
    return prediction_ran


def refresh_from_forensic(book, now):
    forensic = worksheet(book, "FORENSIC_LIVE").get_all_values()
    require_verified_symbols(row[1] for row in forensic[1:] if len(row) > 1 and str(row[1]).strip())
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
    append_sheet_provenance(
        book,
        sink="scanner_refresh_from_forensic",
        record_count=len(quotes),
        source_timestamp=now.strftime("%Y-%m-%d %H:%M:%S"),
    )


def main():
    load_env()
    require_authorized_writer()
    sheet_id = require_authoritative_sheet_id(
        os.getenv("SHEET_ID", "").strip() or SHEET_ID
    )
    book = gspread.service_account_from_dict(load_service_account()).open_by_key(sheet_id)
    now = now_ist()
    age = heartbeat_age_seconds(book, now)
    prediction_ran = False
    if age is not None and age <= DAEMON_FRESH_SECONDS:
        print(f"[INFO] HEARTBEAT is {int(age)}s old. Skipping a second Angel login.")
        refresh_from_forensic(book, now)
    else:
        print(f"[INFO] HEARTBEAT age={age}. Opening Angel for a real quote pass.")
        prediction_ran = bool(run_angel_loop(book, angel_login()))
    if not prediction_ran:
        print("[INFO] Invoking Option CE/PE Prediction & Rating Pipeline...")
        from market_calendar import is_trading_day
        _now = now_ist()
        _catchup = is_trading_day(_now) and not market_is_open(_now) and _now.hour >= 15
        if _catchup:
            print(f"[INFO] EOD catch-up mode: forcing pre-close journaling at {_now.strftime('%H:%M IST')}")
        run_prediction_with_retry(force_pre_close=_catchup)


if __name__ == "__main__":
    main()