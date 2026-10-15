"""Fail-closed, dependency-injected paper close orchestration."""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from phase2.option_stream import enforce_paper_mode

def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def execute(closing_provider, feature_engine, ranking_model, paper_publisher):
    enforce_paper_mode()
    closing = closing_provider.get_verified_official_close(symbols=("NIFTY", "BANKNIFTY"), timeout_seconds=1200)
    if closing.get("officially_published") is not True or closing.get("quality") != "VALID" or not closing.get("source_timestamp"):
        raise RuntimeError("Verified official close unavailable")
    features = feature_engine.transform(closing)
    if not features:
        raise RuntimeError("No features")
    ranking = ranking_model.predict(features)
    if not ranking or not getattr(ranking_model, "version", None):
        raise RuntimeError("Unversioned or empty ranking")
    prediction = {
        "run_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "PAPER", "live_order_authority": 0,
        "source_timestamp": closing["source_timestamp"],
        "source_hash": canonical_hash(closing),
        "features_hash": canonical_hash(features),
        "model_version": ranking_model.version,
        "ranking": ranking,
    }
    prediction["prediction_hash"] = canonical_hash(prediction)
    enforce_paper_mode()
    receipt = paper_publisher.publish_once(prediction)
    if receipt.get("prediction_hash") != prediction["prediction_hash"]:
        raise RuntimeError("Publication hash mismatch")
    return receipt

if __name__ == "__main__":
    raise SystemExit("No live providers or publisher wired: review-only Phase 2")
