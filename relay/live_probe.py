"""Live receipt gate: require a real normalized tick; never print credentials."""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
os.environ["PAPER_MODE"]="1"
os.environ["LIVE_ORDER_AUTHORITY"]="0"
os.environ["FEED_MODE"]="live_smartapi"
from app import normalize
from smartapi_adapter import stream_live, config

async def main():
    config()
    receipts=[]
    async def capture(tick):
        receipts.append(tick)
        print("LIVE_TICK_RECEIPT "+json.dumps({"ts":datetime.now(timezone.utc).isoformat(),"token":tick["token"],"bid":tick["bid"],"ask":tick["ask"],"volume":tick["volume"]}),flush=True)
        raise StopAsyncIteration()
    try:
        await asyncio.wait_for(stream_live(capture,normalize),timeout=90)
    except StopAsyncIteration:
        pass
    if not receipts:
        raise RuntimeError("NO_LIVE_TICK_RECEIPT")
    print("LIVE_TICK_GATE_PASS count="+str(len(receipts)),flush=True)

if __name__=="__main__":
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(main())
