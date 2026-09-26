import os, sys, time, datetime, json, urllib.request
from collections import defaultdict
import pyotp, gspread
from SmartApi import SmartConnect

ANGEL_API_KEY     = os.environ["ANGEL_API_KEY"]
ANGEL_CLIENT_CODE = os.environ["ANGEL_CLIENT_CODE"]
ANGEL_PIN         = os.environ["ANGEL_PIN"]
ANGEL_TOTP_SEED   = os.environ["ANGEL_TOTP_SEED"]
SHEET_ID          = "1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs"

def get_ist():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(hours=5, minutes=30)

def parse_exp(s):
    try:
        return datetime.datetime.strptime(s.strip().upper(), "%d%b%Y").date()
    except:
        return None

# Authenticate Google Sheet using the secret key JSON
with open("key.json", "w") as f:
    f.write(os.environ["SHEETS_KEY_JSON"])
gc = gspread.service_account(filename="key.json")
sh = gc.open_by_key(SHEET_ID)

ws_live = sh.worksheet("FORENSIC_LIVE")
ws_hb = sh.worksheet("HEARTBEAT")

# Authenticate Angel One
totp = pyotp.TOTP(ANGEL_TOTP_SEED).now()
api = SmartConnect(api_key=ANGEL_API_KEY)
api.generateSession(ANGEL_CLIENT_CODE, ANGEL_PIN, totp)
print(f"[OK] Angel Session Active for {ANGEL_CLIENT_CODE}")

# Download Scrip Master & Discover all symbols with CE & PE
print("[INFO] Discovering symbols...")
req = urllib.request.urlopen("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json", timeout=25)
scrip_master = json.loads(req.read().decode("utf-8"))

today = get_ist().date()
opts = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
futs = defaultdict(list)

for c in scrip_master:
    if c.get("exch_seg") != "NFO": continue
    name, inst, tsym = c.get("name","").strip().upper(), c.get("instrumenttype","").strip().upper(), c.get("symbol","").strip().upper()
    exp = parse_exp(c.get("expiry",""))
    if not name or not exp or exp < today: continue

    if inst in ("OPTSTK", "OPTIDX"):
        stk = float(c.get("strike", 0.0)) / 100.0
        if stk <= 0: continue
        if tsym.endswith("CE"): opts[name][exp][stk]["CE"] = c
        elif tsym.endswith("PE"): opts[name][exp][stk]["PE"] = c
    elif inst in ("FUTSTK", "FUTIDX"):
        c["_exp"] = exp
        futs[name].append(c)

universe = {}
for sym, exp_map in opts.items():
    if sym not in futs: continue
    min_exp = min(exp_map.keys())
    stks = {k: v for k, v in exp_map[min_exp].items() if "CE" in v and "PE" in v}
    if not stks: continue
    nf = sorted(futs[sym], key=lambda x: x["_exp"])[0]
    universe[sym] = {"token": str(nf["token"]), "exp": min_exp.strftime("%d-%b-%Y"), "strikes": stks}

print(f"[OK] Tracking {len(universe)} symbols!")

def fetch_chunked(tokens, size=45):
    res = {}
    for i in range(0, len(tokens), size):
        try:
            r = api.getMarketData("FULL", {"NFO": tokens[i:i+size]})
            for itm in r.get("data", {}).get("fetched", []):
                res[str(itm.get("symbolToken"))] = itm
            time.sleep(0.25)
        except: pass
    return res

fut_tokens = [u["token"] for u in universe.values()]

# Run sync loop for 5 hours (entire trading session)
start_time = time.time()
loop = 0
while time.time() - start_time < 19800:
    now = get_ist()
    if now.hour == 15 and now.minute > 35:
        print("[INFO] Market closed. Finishing run.")
        break

    f_quotes = fetch_chunked(fut_tokens)
    opt_tokens, sym_map = [], {}

    for sym, u in universe.items():
        fq = f_quotes.get(u["token"])
        if not fq: continue
        ltp = float(fq.get("ltp", 0.0))
        if ltp <= 0: continue
        atm_stk = min(list(u["strikes"].keys()), key=lambda s: abs(s - ltp))
        ce_tok = str(u["strikes"][atm_stk]["CE"]["token"])
        pe_tok = str(u["strikes"][atm_stk]["PE"]["token"])
        opt_tokens.extend([ce_tok, pe_tok])
        sym_map[sym] = {"stk": atm_stk, "ce_tok": ce_tok, "pe_tok": pe_tok,
                        "ce_sym": u["strikes"][atm_stk]["CE"]["symbol"],
                        "pe_sym": u["strikes"][atm_stk]["PE"]["symbol"]}

    o_quotes = fetch_chunked(opt_tokens)
    rows = []
    ist_str = now.strftime("%Y-%m-%d %H:%M:%S")

    for sym, m in sym_map.items():
        fq = f_quotes.get(universe[sym]["token"], {})
        cq, pq = o_quotes.get(m["ce_tok"], {}), o_quotes.get(m["pe_tok"], {})

        fltp, fpct = float(fq.get("ltp", 0)), float(fq.get("percentChange", 0))
        ftbq, ftsq = int(fq.get("totBuyQuan", 0)), int(fq.get("totSellQuan", 0))
        fobi = round((ftbq - ftsq) / max(1, ftbq + ftsq), 3)

        cltp, cpct = float(cq.get("ltp", 0)), float(cq.get("percentChange", 0))
        coi, ctbq, ctsq = int(cq.get("opnInterest", 0)), int(cq.get("totBuyQuan", 0)), int(cq.get("totSellQuan", 0))
        cobi = round((ctbq - ctsq) / max(1, ctbq + ctsq), 3)

        pltp, ppct = float(pq.get("ltp", 0)), float(pq.get("percentChange", 0))
        poi = int(pq.get("opnInterest", 0))
        pcr = round(poi / max(1, coi), 2)

        if fpct >= 0.4 and fobi >= 0.12: sig = "PRE-BREAKOUT CALL ACCUMULATION"
        elif fpct <= -0.4 and fobi <= -0.12: sig = "BEARISH BREAKDOWN ACCUMULATION"
        else: sig = "NEUTRAL / CONSOLIDATION"

        rows.append([ist_str, sym, universe[sym]["exp"], fltp, fpct, fobi, m["stk"],
                     m["ce_sym"], cltp, cpct, coi, cobi, m["pe_sym"], pltp, ppct, poi, pcr, sig])

    rows.sort(key=lambda x: (1 if "PRE-BREAKOUT" in x[17] else 0, x[5]), reverse=True)
    header = [["Timestamp (IST)", "Symbol", "Nearest Expiry", "Fut LTP", "Fut Chg %", "Fut OBI", "ATM Strike",
               "ATM CE Contract", "CE LTP", "CE Chg %", "CE OI", "CE OBI", "ATM PE Contract", "PE LTP", "PE Chg %", "PE OI", "ATM PCR", "Forensic Action Signal"]]

    try:
        ws_live.clear()
        ws_live.update(range_name="A1", values=header + rows)
        ws_hb.update(range_name="A2", values=[[ist_str, "CONNECTED_GITHUB_ACTIONS", len(rows), f"Loop #{loop} OK"]])
        print(f"[{ist_str}] Synced {len(rows)} symbols to Google Sheet | Loop #{loop}")
    except Exception as e:
        print(f"[WARN] Sheet update: {e}")

    loop += 1
    time.sleep(5)
