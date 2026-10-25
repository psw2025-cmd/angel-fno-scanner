"""Read-only fail-closed GitHub PR dependency inventory; not a merge approval."""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, build_opener
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
class AuditError(RuntimeError):
    pass

class _NoRedirectHandler(HTTPRedirectHandler):
    """Reject redirects before Authorization headers can reach another URL."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def _safe_open(req, timeout):
    return build_opener(_NoRedirectHandler()).open(req, timeout=timeout)

def fetch_open_prs(repo, token, max_pages=20, opener=None):
    if opener is None:
        opener = _safe_open
    if not _REPO.fullmatch(repo) or any(part in (".", "..") or ".." in part for part in repo.split("/")):
        raise AuditError("Invalid repository identity")
    if not token:
        raise AuditError("GITHUB_TOKEN missing; authenticated inventory required")
    if not 1 <= max_pages <= 20:
        raise AuditError("max_pages must be 1..20")
    next_url = f"https://api.github.com/repos/{repo}/pulls?state=open&per_page=100&page=1"
    visited, all_prs = set(), []
    for page in range(1, max_pages + 1):
        if next_url in visited:
            raise AuditError("Pagination loop")
        visited.add(next_url)
        parsed = urlparse(next_url)
        try:
            query = parse_qs(parsed.query, strict_parsing=True, keep_blank_values=True)
        except ValueError as exc:
            raise AuditError("Untrusted pagination query") from exc
        # The Link header is untrusted input. Same-host links can still change
        # repository, endpoint, state, page size or page sequence.
        if (parsed.scheme != "https" or parsed.netloc != "api.github.com"
                or parsed.path != f"/repos/{repo}/pulls"
                or parsed.params or parsed.fragment
                or query != {"state": ["open"], "per_page": ["100"], "page": [str(page)]}):
            raise AuditError("Untrusted pagination URL")
        req = Request(next_url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "angel-fno-pr-dependency-audit",
        })
        try:
            with opener(req, timeout=15) as response:
                if response.status != 200:
                    raise AuditError(f"GitHub API status {response.status}")
                data = json.load(response)
                link = response.headers.get("Link", "")
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise AuditError(f"GitHub PR inventory fetch failed: {type(exc).__name__}") from exc
        if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
            raise AuditError("Invalid GitHub PR payload")
        all_prs.extend(data)
        next_links = [part.split(";", 1)[0].strip().strip("<>")
                      for part in link.split(",") if 'rel="next"' in part]
        if len(next_links) > 1:
            raise AuditError("Ambiguous pagination")
        next_url = next_links[0] if next_links else None
        if not next_url:
            return all_prs
    raise AuditError("Inventory incomplete: pagination bound exceeded")

def _repo_ref(item, side):
    section = item.get(side)
    if not isinstance(section, dict):
        raise AuditError(f"Missing {side} metadata")
    repo = section.get("repo")
    if not isinstance(repo, dict) or not isinstance(repo.get("full_name"), str):
        raise AuditError(f"Missing {side} repository identity")
    ref = section.get("ref")
    if not isinstance(ref, str) or not ref:
        raise AuditError(f"Missing {side} ref")
    return repo["full_name"], ref

def build_report(prs, repo, main_ref="main"):
    if not isinstance(prs, list):
        raise AuditError("PR inventory must be a list")
    indexed, heads = {}, {}
    for pr in prs:
        n = pr.get("number")
        if not isinstance(n, int) or isinstance(n, bool) or n < 1 or n in indexed:
            raise AuditError("Missing or duplicate PR number")
        head, base = _repo_ref(pr, "head"), _repo_ref(pr, "base")
        if head in heads:
            raise AuditError("Ambiguous open PR head identity")
        heads[head] = n
        indexed[n] = {"number": n, "head_repo": head[0], "head_ref": head[1],
                      "base_repo": base[0], "base_ref": base[1],
                      "draft": pr.get("draft") is True,
                      "head_sha": pr.get("head", {}).get("sha"),
                      "html_url": pr.get("html_url"),
                      "parent_pr": None, "classification": None}
    for row in indexed.values():
        if (row["base_repo"], row["base_ref"]) == (repo, main_ref):
            row["classification"] = "DIRECT_MAIN_BASE_NOT_MERGE_APPROVAL"
        else:
            parent = heads.get((row["base_repo"], row["base_ref"]))
            row["parent_pr"] = parent
            row["classification"] = "STACKED" if parent else "UNRESOLVED_BASE_REQUIRES_REVIEW"
    state = {}
    def visit(n):
        if state.get(n) == 1:
            raise AuditError("PR dependency cycle detected")
        if state.get(n) == 2:
            return
        state[n] = 1
        parent = indexed[n]["parent_pr"]
        if parent is not None:
            visit(parent)
        state[n] = 2
    for n in indexed:
        visit(n)
    rows = [indexed[n] for n in sorted(indexed)]
    counts = {key: sum(row["classification"] == key for row in rows)
              for key in ("DIRECT_MAIN_BASE_NOT_MERGE_APPROVAL", "STACKED", "UNRESOLVED_BASE_REQUIRES_REVIEW")}
    return {"schema_version": 1, "repository": repo,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": "authenticated_github_open_pr_api_snapshot",
            "open_pr_count": len(rows), "classification_counts": counts,
            "not_certification": True, "prs": rows}

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-pages", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        report = build_report(fetch_open_prs(args.repo, os.environ.get("GITHUB_TOKEN", ""), args.max_pages), args.repo)
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"PR_DEPENDENCY_INVENTORY_PASS count={report['open_pr_count']} unresolved={report['classification_counts']['UNRESOLVED_BASE_REQUIRES_REVIEW']} (not a merge approval)")
        return 0
    except AuditError as exc:
        print(f"PR_DEPENDENCY_INVENTORY_BLOCKED: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
