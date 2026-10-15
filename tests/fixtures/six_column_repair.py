"""Pure local schema repair: never connects to BigQuery."""
REPAIR = {"cycle_id":"STRING","data_freshness_status":"STRING","git_sha":"STRING","run_id":"STRING","source_timestamp":"TIMESTAMP","writer_id":"STRING"}
def repair(fields):
    result = [dict(f) for f in fields]
    names = [f["name"] for f in result]
    if len(names) != len(set(names)):
        raise ValueError("duplicate field")
    existing = {f["name"]:f for f in result}
    for name, kind in REPAIR.items():
        if name in existing:
            if existing[name]["type"].upper() != kind or existing[name].get("mode","NULLABLE") != "NULLABLE":
                raise ValueError("incompatible existing field: "+name)
        else:
            result.append({"name":name,"type":kind,"mode":"NULLABLE"})
    return result
