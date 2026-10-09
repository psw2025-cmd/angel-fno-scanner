"""Offline adversarial tests. Never connect to broker or mutate production."""
import importlib.util
from pathlib import Path
from datetime import datetime, timedelta, timezone
p=Path(__file__).with_name("100_year_guard.py")
spec=importlib.util.spec_from_file_location("autonomy_guard",p)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
now=datetime.now(timezone.utc)
stamp=now.isoformat()
meta={"run_id":"test","git_sha":"test","cycle_id":"test","market_session":"OPEN",
      "source_timestamp":stamp,"data_freshness_status":"EXCHANGE_VERIFIED",
      "verified_count":219,"total":219}
cases=[
    ("partial_218",{"verified_count":218}),
    ("stale_5min",{"source_timestamp":(now-timedelta(minutes=5)).isoformat()}),
    ("future_clock",{"source_timestamp":(now+timedelta(minutes=2)).isoformat()}),
    ("schema_missing",{"data_freshness_status":None}),
    ("universe_220",{"total":220}),
]
for name,changes in cases:
    bad={**meta,**changes}
    try:mod.verify(bad,"pre",now=now)
    except (ValueError,KeyError):print("PASS FAIL-CLOSED",name)
    else:raise AssertionError("unsafe acceptance "+name)
try:mod.verify(meta,"post",now=now)
except ValueError:print("PASS FAIL-CLOSED unverified external sinks")
else:raise AssertionError("post accepted without readback")
print("CHAOS PASS: 6 adversarial scenarios")
