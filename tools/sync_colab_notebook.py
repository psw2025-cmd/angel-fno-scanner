#!/usr/bin/env python3
"""
tools/sync_colab_notebook.py

Synchronizes and patches the Angel F&O Colab Notebook between:
1. Canonical Repository: notebooks/ANGEL_FNO_COLAB_RUNNER.ipynb
2. Google Drive: G:\\My Drive\\Colab Notebooks\\ANGEL_FNO_COLAB_RUNNER.ipynb
3. Active Colab Tab: G:\\My Drive\\Colab Notebooks\\Untitled73.ipynb
"""

import json
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOKS_DIR = REPO_ROOT / "notebooks"
NOTEBOOKS_DIR.mkdir(parents=True, exist_ok=True)

REPO_NOTEBOOK = NOTEBOOKS_DIR / "ANGEL_FNO_COLAB_RUNNER.ipynb"
GDRIVE_DIR = Path(r"G:\My Drive\Colab Notebooks")
GDRIVE_MASTER = GDRIVE_DIR / "ANGEL_FNO_COLAB_RUNNER.ipynb"
GDRIVE_UNTITLED = GDRIVE_DIR / "Untitled73.ipynb"


def patch_and_sync():
    src_path = GDRIVE_UNTITLED if GDRIVE_UNTITLED.exists() else GDRIVE_MASTER
    if not src_path.exists():
        print(f"Source notebook not found at {src_path}")
        return 1

    print(f"Loading source notebook: {src_path}")
    with open(src_path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    # Patch cell QWoGYYdhDrHI
    patched = False
    for cell in nb.get("cells", []):
        cid = cell.get("metadata", {}).get("id", "")
        if cid == "QWoGYYdhDrHI":
            cell["source"] = [
                "import json\n",
                "import datetime\n",
                "import os\n",
                "from google.cloud import bigquery\n",
                "\n",
                "# 1. Resilient Authentication (Interactive or ADC fallback)\n",
                "try:\n",
                "    from google.colab import auth\n",
                "    auth.authenticate_user()\n",
                "    print('User authentication completed.')\n",
                "except Exception as e:\n",
                "    print(f'User auth prompt skipped or using environment ADC: {e}')\n",
                "\n",
                "# 2. Initialize BigQuery Client\n",
                "project_id = os.environ.get('BQ_PROJECT_ID', 'fno-angel-prod-1790444589')\n",
                "try:\n",
                "    client = bigquery.Client(project=project_id)\n",
                "except Exception as ex:\n",
                "    sa_key = '/content/angel-fno-scanner/secrets/gcp-service-account.json'\n",
                "    if os.path.exists(sa_key):\n",
                "        client = bigquery.Client.from_service_account_json(sa_key, project=project_id)\n",
                "    else:\n",
                "        raise ex\n",
                "\n",
                "# 3. Query Active BigQuery Tables\n",
                "query = '''\n",
                "    SELECT table_name\n",
                "    FROM `fno-angel-prod-1790444589.fno_predictions.INFORMATION_SCHEMA.TABLES`\n",
                "'''\n",
                "tables = [row.table_name for row in client.query(query)]\n",
                "\n",
                "colab_telemetry = {\n",
                "    'colab_timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),\n",
                "    'gcp_project': project_id,\n",
                "    'active_bigquery_tables': tables,\n",
                "    'colab_status': 'ONLINE_AND_SYNCHRONIZED'\n",
                "}\n",
                "\n",
                "print(json.dumps(colab_telemetry, indent=2))\n",
            ]
            cell["outputs"] = []
            cell["execution_count"] = None
            patched = True
            break

    print(f"Patched cell QWoGYYdhDrHI: {patched}")

    # 1. Save to Repository
    with open(REPO_NOTEBOOK, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    print(f"[OK] Saved to Repo: {REPO_NOTEBOOK}")

    # 2. Save to Google Drive Master
    if GDRIVE_DIR.exists():
        with open(GDRIVE_MASTER, "w", encoding="utf-8") as f:
            json.dump(nb, f, indent=1, ensure_ascii=False)
        print(f"[OK] Saved to Google Drive Master: {GDRIVE_MASTER}")

        # 3. Update Untitled73 in Drive so user's active session is updated
        with open(GDRIVE_UNTITLED, "w", encoding="utf-8") as f:
            json.dump(nb, f, indent=1, ensure_ascii=False)
        print(f"[OK] Updated active Google Drive session: {GDRIVE_UNTITLED}")
    else:
        print("[WARN] Google Drive G: mount not detected.")

    return 0


if __name__ == "__main__":
    sys.exit(patch_and_sync())
