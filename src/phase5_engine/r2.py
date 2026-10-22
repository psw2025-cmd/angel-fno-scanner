"""R2 immutable evidence helper. Credentials remain in server-side environment."""
import json
import os
def write_immutable(key,payload):
    import boto3
    required=("R2_ACCOUNT_ID","R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","PHASE5_R2_BUCKET")
    missing=[k for k in required if not os.getenv(k)]
    if missing:raise RuntimeError("Missing R2 configuration: "+", ".join(missing))
    allowed=("predictions/","validation/","models/versions/","raw/","actuals/","metrics/")
    if (not isinstance(key,str) or not key.startswith(allowed)
            or any(part in ("", ".", "..") for part in key.split("/"))
            or any(ord(ch)<32 or ord(ch)==127 or ch=="\\\\" for ch in key)):
        raise ValueError("Invalid evidence key")
    s3=boto3.client("s3",endpoint_url="https://"+os.environ["R2_ACCOUNT_ID"]+".r2.cloudflarestorage.com",aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],region_name="auto")
    body=json.dumps(payload,allow_nan=False,sort_keys=True).encode()
    s3.put_object(Bucket=os.environ["PHASE5_R2_BUCKET"],Key=key,Body=body,ContentType="application/json",IfNoneMatch="*")
    return {"key":key,"bytes":len(body)}
