"""Worktree retry regression, including an actual Windows open-file handle."""
import os
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "tools"))
from recovery_contract import cleanup_with_retry, review_result

def test_retries_then_success():
    calls=[]
    def remove():
        calls.append(1)
        if len(calls)<3: raise PermissionError("file in use")
    result=cleanup_with_retry(remove,sleep=lambda _:None)
    assert result["status"]=="REMOVED" and result["attempts"]==3

def test_exhausted_cleanup_preserves_evidence():
    result=cleanup_with_retry(lambda: (_ for _ in ()).throw(PermissionError("locked")),sleep=lambda _:None)
    assert result["status"]=="CLEANUP_PENDING" and result["attempts"]==5
    assert len(result["errors"])==5

def test_real_windows_file_lock_injection():
    if os.name!="nt": return
    import msvcrt
    with tempfile.TemporaryDirectory() as folder:
        file=Path(folder)/"locked.txt"
        file.write_bytes(b"abc")
        with file.open("r+b") as handle:
            msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            def lock_attempt():
                with file.open("r+b") as other:
                    msvcrt.locking(other.fileno(),msvcrt.LK_NBLCK,1)
                    msvcrt.locking(other.fileno(),msvcrt.LK_UNLCK,1)
            result=cleanup_with_retry(lock_attempt,sleep=lambda _:None)
            assert result["status"]=="CLEANUP_PENDING"
            msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
        assert cleanup_with_retry(lock_attempt,sleep=lambda _:None)["status"]=="REMOVED"

def test_review_timeout_never_passes():
    assert review_result(0,"REVIEW_PASS",180)["status"]!="REVIEWED"
    assert review_result(0,"REVIEW_PASS",3)["status"]=="REVIEWED"

