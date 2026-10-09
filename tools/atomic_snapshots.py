"""Stage a complete snapshot bundle before publishing. Roll back files on failure."""
from pathlib import Path
import os
import shutil
import uuid

def publish_bundle(staging, target, names, *, replace=os.replace):
    staging, target = Path(staging), Path(target)
    names = tuple(names)
    if not names or any(Path(n).name != n or not (staging / n).is_file() for n in names):
        raise ValueError("incomplete or unsafe snapshot bundle")
    target.mkdir(parents=True, exist_ok=True)
    backup = staging.parent / ("backup_" + uuid.uuid4().hex)
    backup.mkdir(parents=True)
    installed = []
    try:
        for name in names:
            original = target / name
            if original.exists():
                shutil.copy2(original, backup / name)
            replace(staging / name, original)
            installed.append(name)
    except Exception:
        for name in reversed(installed):
            original, old = target / name, backup / name
            if old.exists():
                os.replace(old, original)
            elif original.exists():
                original.unlink()
        raise
    finally:
        shutil.rmtree(backup, ignore_errors=True)
        shutil.rmtree(staging, ignore_errors=True)
