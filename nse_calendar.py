"""Fail-closed IST NSE equity-derivatives trading calendar, not settlement calendar."""
import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

CALENDAR=Path(__file__).resolve().parent/"nse_holidays.json"
IST=ZoneInfo("Asia/Kolkata")
def load_calendar():
    data=json.loads(CALENDAR.read_text(encoding="utf-8"))
    if data.get("year")!=2026 or data.get("timezone")!="Asia/Kolkata" or not isinstance(data.get("holidays"),dict):
        raise RuntimeError("NSE holiday calendar invalid")
    for day in data["holidays"]:
        if date.fromisoformat(day).year!=2026: raise RuntimeError("Holiday year mismatch")
    return data
def trading_status(day=None):
    day=day or datetime.now(IST).date()
    data=load_calendar()
    if day.year!=data["year"]: raise RuntimeError("NSE holiday calendar does not cover "+str(day.year)+"; refusing unverified market run")
    reason=data["holidays"].get(day.isoformat())
    if day.weekday()>=5: reason=reason or "Weekend; exceptional Muhurat session requires separate authorization"
    return {"date_ist":day.isoformat(),"market_closed":bool(reason),"reason":reason or "Regular trading day per configured calendar"}
def previous_trading_day(day):
    cursor=day-timedelta(days=1)
    while True:
        status=trading_status(cursor)
        if not status["market_closed"]: return cursor
        cursor-=timedelta(days=1)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--date",help="Test-only YYYY-MM-DD override; do not use in production workflow")
    args=ap.parse_args()
    result=trading_status(date.fromisoformat(args.date) if args.date else None)
    print(("MARKET_CLOSED" if result["market_closed"] else "MARKET_OPEN"),result["date_ist"],result["reason"])
    if __import__("os").environ.get("GITHUB_OUTPUT"):
        with open(__import__("os").environ["GITHUB_OUTPUT"],"a",encoding="utf-8") as out:
            out.write("market_closed="+str(result["market_closed"]).lower()+"\n")
            out.write("market_date_ist="+result["date_ist"]+"\n")
if __name__=="__main__": main()
