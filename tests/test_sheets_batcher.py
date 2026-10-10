import pytest
from tools.sheets_batcher import batch_read

class FakeSheet:
    def __init__(self): self.calls=0
    def values_batch_get(self,ranges):
        self.calls+=1
        return {"valueRanges":[{"values":[[str(i)]]} for i in range(len(ranges))]}

def test_one_batch_for_many_ranges():
    sheet=FakeSheet()
    assert batch_read(sheet,["A!A1:B2","B!A1:B2"])=={"A!A1:B2":[["0"]],"B!A1:B2":[["1"]]}
    assert sheet.calls==1

def test_duplicate_ranges_fail_closed():
    with pytest.raises(ValueError):batch_read(FakeSheet(),["A!A1","A!A1"])

def test_429_backoff():
    class Throttle(Exception):
        code=429
    class Flaky(FakeSheet):
        def values_batch_get(self,ranges):
            if self.calls==0:
                self.calls+=1
                raise Throttle("quota")
            return super().values_batch_get(ranges)
    s=Flaky()
    assert batch_read(s,["A!A1"],sleep=lambda _:None,jitter=lambda a,b:0)["A!A1"]==[["0"]]
    assert s.calls==2
