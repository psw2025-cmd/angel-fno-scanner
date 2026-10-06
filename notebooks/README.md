# 📓 Angel F&O Master Colab & Cloud Analyzer

> **Authoritative Owner Directory:** `notebooks/`  
> **Master Colab Notebook:** [`notebooks/ANGEL_FNO_COLAB_RUNNER.ipynb`](file:///C:/AngelFNO_Workstation/repos/angel-fno-scanner/notebooks/ANGEL_FNO_COLAB_RUNNER.ipynb)  
> **Repository:** `psw2025-cmd/angel-fno-scanner`  
> **Google Drive Mirror:** `G:\My Drive\Colab Notebooks\ANGEL_FNO_COLAB_RUNNER.ipynb`

---

## 🌐 3-Way Universal Synchronization (GitHub ↔ Google Drive ↔ Local Repo)

This notebook is configured for seamless editing and execution across all three environments:

### 1. Open Directly in Google Colab via GitHub (1-Click)
Anyone can open and run this notebook directly in Google Colab from our public GitHub repository:
👉 **[Open `ANGEL_FNO_COLAB_RUNNER.ipynb` in Google Colab](https://colab.research.google.com/github/psw2025-cmd/angel-fno-scanner/blob/main/notebooks/ANGEL_FNO_COLAB_RUNNER.ipynb)**

- **To save edits back to GitHub from Colab:**  
  Click **File → Save a copy in GitHub** → Select repository `psw2025-cmd/angel-fno-scanner` → Branch `main`.

### 2. Open via Google Drive (Live Auto-Sync)
Because your workstation mounts Google Drive at `G:\`:
- The notebook is mirrored directly at:  
  `G:\My Drive\Colab Notebooks\ANGEL_FNO_COLAB_RUNNER.ipynb`
- Any edits made in Google Colab are saved directly to Google Drive.
- Run `python tools/sync_colab_notebook.py` at any time to pull or push updates between Google Drive and the Git repository.

### 3. Run Locally in VS Code / Cursor / CLI
You can also run or debug this notebook locally on your workstation using the local `.venv` environment:
```powershell
.\.venv\Scripts\python.exe -m jupyter lab notebooks/ANGEL_FNO_COLAB_RUNNER.ipynb
```

---

## 🛠️ Synchronization Tool

To synchronize changes between Google Drive and the repository, run:
```powershell
python tools/sync_colab_notebook.py
```
This automatically updates:
- `notebooks/ANGEL_FNO_COLAB_RUNNER.ipynb` (Local Git)
- `G:\My Drive\Colab Notebooks\ANGEL_FNO_COLAB_RUNNER.ipynb` (Google Drive Cloud)
- Active Colab working sessions.
