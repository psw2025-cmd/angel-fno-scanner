"""Train a paper-only model from independently labeled historical rows; never synthesize labels."""
import argparse, csv, hashlib, json
from pathlib import Path
from phase2.option_stream import enforce_paper_mode

FEATURES = ["oi", "volume", "spread_pct"]
def train(input_csv, output_dir):
    enforce_paper_mode()
    import joblib
    from sklearn.ensemble import HistGradientBoostingClassifier
    rows = list(csv.DictReader(open(input_csv, newline="", encoding="utf-8")))
    if len(rows) < 200 or any(not all(k in r for k in FEATURES + ["label"]) for r in rows):
        raise ValueError("At least 200 independently labeled historical rows required")
    X = [[float(r[k]) for k in FEATURES] for r in rows]
    y = [int(r["label"]) for r in rows]
    if set(y) != {0, 1}:
        raise ValueError("Both observed outcome classes required")
    model = HistGradientBoostingClassifier(random_state=42).fit(X, y)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "model.joblib"
    joblib.dump(model, path)
    manifest = {"version": "paper-hgb-v1", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "feature_columns": FEATURES, "training_rows": len(rows), "training_input_sha256": hashlib.sha256(Path(input_csv).read_bytes()).hexdigest(), "approved_for_paper": False}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--labeled-csv", required=True)
    p.add_argument("--output-dir", required=True)
    a = p.parse_args()
    print(json.dumps(train(a.labeled_csv, a.output_dir), indent=2))
