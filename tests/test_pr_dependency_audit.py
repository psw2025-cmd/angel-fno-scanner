import io
import json
from unittest.mock import patch
from urllib.request import Request
from urllib.error import HTTPError
import unittest
from urllib.error import URLError
from tools.pr_dependency_audit import AuditError, build_report, fetch_open_prs, _NoRedirectHandler, _safe_open

REPO = "psw2025-cmd/angel-fno-scanner"

def pr(n, head, base="main", *, head_repo=REPO, base_repo=REPO, draft=True):
    return {"number": n, "head": {"repo": {"full_name": head_repo}, "ref": head, "sha": "a" * 40},
            "base": {"repo": {"full_name": base_repo}, "ref": base},
            "draft": draft, "html_url": f"https://github.com/{REPO}/pull/{n}"}

class Response:
    def __init__(self, data, link=""):
        self.status = 200
        self.headers = {"Link": link}
        self.stream = io.BytesIO(json.dumps(data).encode())
    def read(self, *args): return self.stream.read(*args)
    def __enter__(self): return self
    def __exit__(self, *args): pass

class TestDependencyAudit(unittest.TestCase):
    def test_stack_and_unresolved_base_not_misrepresented_as_merged(self):
        report = build_report([pr(1, "parent"), pr(2, "child", "parent"), pr(3, "orphan", "deleted")], REPO)
        rows = {r["number"]: r for r in report["prs"]}
        self.assertEqual(rows[2]["parent_pr"], 1)
        self.assertEqual(rows[2]["classification"], "STACKED")
        self.assertEqual(rows[3]["classification"], "UNRESOLVED_BASE_REQUIRES_REVIEW")
        self.assertTrue(report["not_certification"])
    def test_same_ref_different_forks_are_not_collapsed(self):
        report = build_report([pr(1, "fix", head_repo="one/repo"), pr(2, "fix", head_repo="two/repo")], REPO)
        self.assertEqual(report["open_pr_count"], 2)
    def test_duplicate_head_fail_closed(self):
        with self.assertRaisesRegex(AuditError, "Ambiguous"):
            build_report([pr(1, "fix"), pr(2, "fix")], REPO)
    def test_duplicate_number_fail_closed(self):
        with self.assertRaisesRegex(AuditError, "duplicate PR number"):
            build_report([pr(1, "one"), pr(1, "two")], REPO)
    def test_cycle_fail_closed(self):
        with self.assertRaisesRegex(AuditError, "cycle"):
            build_report([pr(1, "a", "b"), pr(2, "b", "a")], REPO)
    def test_missing_head_identity_fail_closed(self):
        x = pr(1, "a"); x["head"]["repo"] = None
        with self.assertRaisesRegex(AuditError, "head repository"):
            build_report([x], REPO)
    def test_requires_token(self):
        with self.assertRaisesRegex(AuditError, "GITHUB_TOKEN"):
            fetch_open_prs(REPO, "")
    def test_rejects_invalid_repo(self):
        with self.assertRaisesRegex(AuditError, "Invalid repository"):
            fetch_open_prs("../unsafe", "fake")
    def test_pagination_follows_only_api_github(self):
        calls = []
        def opener(req, timeout):
            calls.append(req.full_url)
            if len(calls) == 1:
                return Response([pr(1, "a")], f'<https://api.github.com/repos/{REPO}/pulls?state=open&per_page=100&page=2>; rel="next"')
            return Response([pr(2, "b")])
        self.assertEqual(len(fetch_open_prs(REPO, "fake", opener=opener)), 2)
    def test_external_pagination_host_rejected(self):
        def opener(req, timeout):
            return Response([], '<https://evil.example/leak>; rel="next"')
        with self.assertRaisesRegex(AuditError, "Untrusted pagination"):
            fetch_open_prs(REPO, "fake", opener=opener)
    def test_incomplete_page_bound_rejected(self):
        def opener(req, timeout):
            return Response([], '<https://api.github.com/repos/x/y/pulls?page=2>; rel="next"')
        with self.assertRaisesRegex(AuditError, "pagination bound"):
            fetch_open_prs(REPO, "fake", max_pages=1, opener=opener)
    def test_network_error_fail_closed(self):
        def opener(req, timeout): raise URLError("unavailable")
        with self.assertRaisesRegex(AuditError, "fetch failed"):
            fetch_open_prs(REPO, "fake", opener=opener)

    def test_same_host_different_repository_pagination_rejected(self):
        def opener(req, timeout):
            return Response([pr(1, "a")],
                '<https://api.github.com/repos/another/project/pulls?state=open&per_page=100&page=2>; rel="next"')
        with self.assertRaisesRegex(AuditError, "Untrusted pagination"):
            fetch_open_prs(REPO, "fake", opener=opener)

    def test_same_host_different_endpoint_pagination_rejected(self):
        def opener(req, timeout):
            return Response([pr(1, "a")],
                '<https://api.github.com/user?state=open&per_page=100&page=2>; rel="next"')
        with self.assertRaisesRegex(AuditError, "Untrusted pagination"):
            fetch_open_prs(REPO, "fake", opener=opener)

    def test_closed_state_pagination_rejected(self):
        def opener(req, timeout):
            return Response([pr(1, "a")],
                f'<https://api.github.com/repos/{REPO}/pulls?state=closed&per_page=100&page=2>; rel="next"')
        with self.assertRaisesRegex(AuditError, "Untrusted pagination"):
            fetch_open_prs(REPO, "fake", opener=opener)

    def test_skipped_page_pagination_rejected(self):
        def opener(req, timeout):
            return Response([pr(1, "a")],
                f'<https://api.github.com/repos/{REPO}/pulls?state=open&per_page=100&page=3>; rel="next"')
        with self.assertRaisesRegex(AuditError, "Untrusted pagination"):
            fetch_open_prs(REPO, "fake", opener=opener)

    def test_duplicate_query_parameter_pagination_rejected(self):
        def opener(req, timeout):
            return Response([pr(1, "a")],
                f'<https://api.github.com/repos/{REPO}/pulls?state=open&state=closed&per_page=100&page=2>; rel="next"')
        with self.assertRaisesRegex(AuditError, "Untrusted pagination"):
            fetch_open_prs(REPO, "fake", opener=opener)

    def test_fragment_pagination_rejected(self):
        def opener(req, timeout):
            return Response([pr(1, "a")],
                f'<https://api.github.com/repos/{REPO}/pulls?state=open&per_page=100&page=2#misleading>; rel="next"')
        with self.assertRaisesRegex(AuditError, "Untrusted pagination"):
            fetch_open_prs(REPO, "fake", opener=opener)


    def test_redirect_handler_never_forwards_authorization(self):
        request = Request(
            "https://api.github.com/repos/owner/repo/pulls",
            headers={"Authorization": "Bearer fake-test-token"},
        )
        handler = _NoRedirectHandler()
        for target in (
            "https://untrusted.example/collect",
            "https://api.github.com/another/endpoint",
        ):
            self.assertIsNone(
                handler.redirect_request(request, None, 302, "Found", {}, target)
            )

    def test_safe_opener_installs_no_redirect_handler(self):
        request = Request("https://api.github.com/repos/owner/repo/pulls")
        with patch("tools.pr_dependency_audit.build_opener") as builder:
            _safe_open(request, timeout=7)
            self.assertIsInstance(builder.call_args.args[0], _NoRedirectHandler)
            builder.return_value.open.assert_called_once_with(request, timeout=7)

    def test_default_fetch_fails_closed_on_redirect_response(self):
        with patch("tools.pr_dependency_audit._safe_open") as opener:
            opener.side_effect = HTTPError(
                "https://api.github.com/repos/owner/repo/pulls",
                302, "Redirect refused", {}, None,
            )
            with self.assertRaisesRegex(AuditError, "fetch failed"):
                fetch_open_prs(REPO, "fake-test-token")
            self.assertEqual(opener.call_count, 1)


if __name__ == "__main__": unittest.main()
