# Error register

## angel-market-scan-job-rc4bz

Created `2026-10-13T11:37:33.855955Z`. Completed `2026-10-13T11:43:14.910280Z`. Exit code 1.

```
File "/app/scanner.py", line 420, in run_angel_loop
    from tools.cycle_metadata import generate_cycle_metadata
ModuleNotFoundError: No module named 'tools.cycle_metadata'
```

## angel-market-scan-job-2g9xq

Created `2026-10-13T11:48:32.266616Z`. Completed `2026-10-13T11:55:00.549816Z`. Exit code 1.

```
File "/app/scanner.py", line 435, in run_angel_loop
    git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
subprocess.CalledProcessError: Command '['git', 'rev-parse', 'HEAD']' returned non-zero exit status 128.
```

## angel-market-scan-job-t9j8j

Completed successfully in 9m48.85s at `2026-10-13T12:09:41.608646Z`. No application error traceback was returned. The job env still carried `GIT_SHA=cloudrun-image-v1`, so that success did not prove a source commit.

## Scheduler

- `2026-10-13T03:45:03.600836876Z` severity ERROR (09:15 IST on 13 Oct). Text payload was empty in the log read.
- `2026-10-13T22:15:07.060268381Z` severity ERROR (03:45 IST on 14 Oct). Text payload was empty in the log read.
- Neither timestamp has a matching Cloud Run execution. The only executions are `rc4bz`, `2g9xq`, and `t9j8j`, all between 17:07 and 17:39 IST on 13 Oct.

## GitHub run 38441552721

```
remote: error: GH006: Protected branch update failed for refs/heads/main.
! [remote rejected] HEAD -> main (protected branch hook declined)
##[error]Snapshot push failed after 5 attempts; publication is NOT complete
```

The commit subject was `chore(data): auto-update daily prediction snapshots [skip ci]`.

## Sheet revisions

`WinError 2` while resolving `gcloud` from the virtualenv Python. Revision ids were not saved.
