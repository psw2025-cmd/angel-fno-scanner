"""Load an explicitly approved, versioned trained ranking model; no fallback baseline."""
import hashlib
import json
from pathlib import Path
from phase2.option_stream import enforce_paper_mode

class TrainedRankingModel:
    def __init__(self, artifact_dir):
        enforce_paper_mode()
        root = Path(artifact_dir)
        manifest = json.loads((root / "manifest.json").read_text())
        if manifest.get("approved_for_paper") is not True or not manifest.get("version"):
            raise RuntimeError("Approved trained-model manifest required")
        binary = (root / "model.joblib").read_bytes()
        if hashlib.sha256(binary).hexdigest() != manifest.get("sha256"):
            raise RuntimeError("Trained model artifact SHA-256 mismatch")
        if not manifest.get("feature_columns") or not isinstance(manifest["feature_columns"], list):
            raise RuntimeError("Model feature contract absent")
        import joblib
        self.model = joblib.load(root / "model.joblib")  # only trusted, reviewed artifact
        if not hasattr(self.model, "predict_proba"):
            raise RuntimeError("Trained classifier must expose predict_proba")
        self.version = manifest["version"]
        self.feature_columns = manifest["feature_columns"]

    def predict(self, features):
        enforce_paper_mode()
        if not features:
            raise ValueError("No features")
        rows = [[row[col] for col in self.feature_columns] for row in features]
        probabilities = self.model.predict_proba(rows)
        classes = list(self.model.classes_)
        if 1 not in classes:
            raise RuntimeError("Positive class 1 missing")
        index = classes.index(1)
        output = [{**row, "model_probability": float(p[index])} for row, p in zip(features, probabilities)]
        if len(output) != len(features):
            raise RuntimeError("Prediction count mismatch")
        output.sort(key=lambda r: (-r["model_probability"], r["symbol"], r["expiry"], r["strike"], r["option_type"]))
        return [{**row, "rank": i} for i, row in enumerate(output, 1)]
