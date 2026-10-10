"""Fail-closed row schema validation; rejected rows retain provenance."""
import json
from pathlib import Path

def validate_rows(rows,required,types=None,rejects_path=None):
    types=types or {}
    accepted=[]
    rejected=[]
    for index,row in enumerate(rows):
        errors=[]
        if not isinstance(row,dict):
            errors.append("not a mapping")
        else:
            for key in required:
                if key not in row or row[key] is None or row[key]=="":
                    errors.append("missing "+key)
            for key,kind in types.items():
                if key in row and row[key] is not None and not isinstance(row[key],kind):
                    errors.append("invalid type "+key)
        if errors:
            rejected.append({"index":index,"errors":errors,"row":row})
        else:
            accepted.append(row)
    if rejected and rejects_path:
        path=Path(rejects_path)
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("a",encoding="utf-8") as out:
            for item in rejected:
                out.write(json.dumps(item,default=str)+"\n")
    return accepted,rejected
