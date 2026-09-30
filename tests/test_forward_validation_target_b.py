import json
from scripts import forward_validation as fv

def test_target_b_ce_pe_top_ranks_and_no_fake_volume(monkeypatch,tmp_path):
    data=[
      {'symbol':'AAA','ce_ltp':10,'ce_chg_pct':30,'ce_oi':100,'ce_bid_ask_spread':0.2,'ce_volume':500,'pe_ltp':8,'pe_chg_pct':5,'pe_oi':90,'pe_bid_ask_spread':0.3},
      {'symbol':'BBB','ce_ltp':11,'ce_chg_pct':20,'ce_oi':110,'ce_bid_ask_spread':0.2,'pe_ltp':9,'pe_chg_pct':25,'pe_oi':95,'pe_bid_ask_spread':0.4},
      {'symbol':'CCC','ce_ltp':12,'ce_chg_pct':10,'ce_oi':120,'ce_bid_ask_spread':0.3,'pe_ltp':7,'pe_chg_pct':15,'pe_oi':85,'pe_bid_ask_spread':0.5},
      {'symbol':'DDD','ce_ltp':13,'ce_chg_pct':5,'ce_oi':130,'ce_bid_ask_spread':0.4,'pe_ltp':6,'pe_chg_pct':10,'pe_oi':80,'pe_bid_ask_spread':0.6},
      {'symbol':'EEE','ce_ltp':14,'ce_chg_pct':1,'ce_oi':140,'ce_bid_ask_spread':0.5,'pe_ltp':5,'pe_chg_pct':1,'pe_oi':70,'pe_bid_ask_spread':0.7},
    ]
    data_dir=tmp_path/'data'; report_dir=tmp_path/'reports'; data_dir.mkdir()
    src=data_dir/'latest_predictions.json'; src.write_text(json.dumps(data),encoding='utf-8')
    monkeypatch.setattr(fv,'DATA',data_dir); monkeypatch.setattr(fv,'REPORTS',report_dir)
    fv.snapshot_target_b()
    out=list(report_dir.glob('TargetB_SNAPSHOT_*.json')); assert len(out)==1
    x=json.loads(out[0].read_text(encoding='utf-8'))
    assert [r['symbol'] for r in x['CE']['top3']]==['AAA','BBB','CCC']
    assert [r['symbol'] for r in x['PE']['top3']]==['BBB','CCC','DDD']
    assert len(x['CE']['top5'])==5 and len(x['PE']['top5'])==5
    assert x['CE']['top1'][0]['volume']==500
    assert x['PE']['top1'][0]['volume'] is None

def test_target_b_output_is_timestamped(monkeypatch,tmp_path):
    data_dir=tmp_path/'data'; report_dir=tmp_path/'reports'; data_dir.mkdir()
    (data_dir/'latest_predictions.json').write_text(json.dumps([{'symbol':'AAA','ce_ltp':1,'ce_chg_pct':2,'ce_oi':3,'pe_ltp':1,'pe_chg_pct':2,'pe_oi':3}]),encoding='utf-8')
    monkeypatch.setattr(fv,'DATA',data_dir); monkeypatch.setattr(fv,'REPORTS',report_dir)
    fv.snapshot_target_b(); fv.snapshot_target_b()
    assert len(list(report_dir.glob('TargetB_SNAPSHOT_*.json')))==2
