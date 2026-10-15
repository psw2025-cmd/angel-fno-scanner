"""Auto-discover nearest-expiry Angel NFO index option contracts."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from decimal import Decimal, InvalidOperation

URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
IST = ZoneInfo("Asia/Kolkata")

def discover(path, *, max_per_side=12):
    response = requests.get(URL, timeout=(15, 90))
    response.raise_for_status()
    raw = response.content
    data = response.json()
    if not isinstance(data, list) or not data:
        raise ValueError("Invalid Angel instrument master")
    today = datetime.now(IST).date()
    groups = {}
    diagnostic = {"nfo_optidx": 0, "name_match": 0, "symbol_match": 0, "parsed": 0, "future": 0}
    for x in data:
        if not isinstance(x, dict) or x.get("exch_seg") != "NFO" or x.get("instrumenttype") != "OPTIDX":
            continue
        diagnostic["nfo_optidx"] += 1
        name, symbol = x.get("name"), x.get("symbol", "")
        if name in ("NIFTY", "BANKNIFTY"):
            diagnostic["name_match"] += 1
        if isinstance(symbol, str) and symbol.startswith(("NIFTY", "BANKNIFTY")) and symbol.endswith(("CE", "PE")):
            diagnostic["symbol_match"] += 1
        if name not in ("NIFTY", "BANKNIFTY") or not symbol.startswith(name) or not symbol.endswith(("CE", "PE")):
            continue
        try:
            expiry = datetime.strptime(x["expiry"], "%d%b%Y").date()
            strike = float(Decimal(str(x["strike"])) / Decimal("100"))
            token = str(x["token"])
        except (ValueError, KeyError, TypeError, InvalidOperation):
            continue
        diagnostic["parsed"] += 1
        if expiry < today or strike <= 0 or not token.isdigit():
            continue
        diagnostic["future"] += 1
        side = symbol[-2:]
        groups.setdefault((name, expiry, side), []).append({"underlying": name, "exchange": "NFO", "option_type": side, "tradingsymbol": symbol, "symboltoken": token, "expiry": expiry.isoformat(), "strike": strike})
    output = []
    for name in ("NIFTY", "BANKNIFTY"):
        expiries = sorted({expiry for n, expiry, side in groups if n == name and groups.get((n, expiry, "CE")) and groups.get((n, expiry, "PE"))})
        if not expiries:
            raise RuntimeError("No valid paired future expiry for " + name + "; master diagnostic=" + json.dumps(diagnostic, sort_keys=True) + "; available_group_count=" + str(len(groups)))
        expiry = expiries[0]
        ce = {x["strike"]: x for x in groups[(name, expiry, "CE")]}
        pe = {x["strike"]: x for x in groups[(name, expiry, "PE")]}
        strikes = sorted(ce.keys() & pe.keys())
        if not strikes:
            raise RuntimeError("No paired strikes for " + name)
        center = len(strikes)//2
        chosen = strikes[max(0,center-max_per_side//2):center+max_per_side//2]
        for strike in chosen:
            output.extend((ce[strike], pe[strike]))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output, hashlib.sha256(raw).hexdigest()
