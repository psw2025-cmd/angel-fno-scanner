"""Auditable Option DNA flags; no fabricated IV, Greeks, or confirmed turning points."""
import math
def number(value):
    try:
        if value is None or isinstance(value,bool): return None
        x=float(value)
        return x if math.isfinite(x) else None
    except (ValueError,TypeError): return None
def snapshot_dna(quote, *, prior=None):
    depth=quote.get("depth") or {}; buys=depth.get("buy") or []; sells=depth.get("sell") or []
    bid=number(buys[0].get("price")) if buys else None
    ask=number(sells[0].get("price")) if sells else None
    oi=number(quote.get("openInterest") if quote.get("openInterest") is not None else quote.get("opnInterest"))
    volume=number(quote.get("tradeVolume")); flags=[]
    if bid is None or ask is None or bid<=0 or ask<bid: raise ValueError("Invalid broker best bid/ask")
    spread=200*(ask-bid)/(ask+bid)
    if spread>=3: flags.append("WIDE_SPREAD_3PCT")
    if prior:
        old=number(prior.get("spread_pct"))
        if old is not None and old>0 and spread>=2*old and spread-old>=1: flags.append("SPREAD_SHOCK_2X_PRIOR")
    ratio=volume/oi if oi is not None and oi>0 and volume is not None and volume>=0 else None
    if ratio is not None and ratio>=3: flags.append("VOLUME_OI_RATIO_HIGH_3X_NOT_OI_CHANGE")
    if ratio is not None and ratio<=0.05: flags.append("VOLUME_OI_RATIO_LOW_005")
    old_oi=number(prior.get("oi")) if prior else None
    if old_oi is not None and old_oi>0 and oi is not None:
        oi_change=(oi-old_oi)/old_oi
        if volume is not None and volume>=100 and oi_change<=-0.2: flags.append("OI_FALL_20PCT_WITH_VOLUME")
    else: oi_change=None
    return {"spread_pct":round(spread,8),"volume_oi_ratio":round(ratio,8) if ratio is not None else None,
            "oi_change_pct":round(100*oi_change,8) if oi_change is not None else None,
            "iv":None,"theta":None,"iv_theta_status":"UNAVAILABLE_NO_VERIFIED_IV_GREEKS_OR_TIME_SERIES",
            "flags":sorted(set(flags)),"broker_exchange_timestamp":quote.get("exchFeedTime")}
def structure_watch(rows):
    """OI/PCR concentration is a hypothesis, never a confirmed market reversal."""
    grouped={}
    for row in rows: grouped.setdefault((row["symbol"],row["expiry"]),[]).append(row)
    out=[]
    for (symbol,expiry),items in sorted(grouped.items()):
        ce=sum(float(x["oi"]) for x in items if x["option_type"]=="CE")
        pe=sum(float(x["oi"]) for x in items if x["option_type"]=="PE")
        pcr=pe/ce if ce>0 else None; state="INSUFFICIENT_DATA"
        if pcr is not None and ce>0 and pe>0:
            if pcr>=1.5: state="POTENTIAL_BOTTOM_WATCH_OI_IMBALANCE_ONLY"
            elif pcr<=0.67: state="POTENTIAL_TOP_WATCH_OI_IMBALANCE_ONLY"
            else: state="NEUTRAL_OI_IMBALANCE"
        out.append({"underlying":symbol,"expiry":expiry,"selected_contracts":len(items),
                    "selected_ce_oi":ce,"selected_pe_oi":pe,"selected_pcr":round(pcr,8) if pcr is not None else None,
                    "state":state,"confirmed_reversal":False,
                    "limitation":"Selected strike OI only; no price trend, full-chain breadth or backtested turning-point validation"})
    return out
