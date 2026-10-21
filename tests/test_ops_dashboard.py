import json
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
import unittest
import zipfile
from unittest.mock import patch

from ops_dashboard import evidence
from ops_dashboard.server import AuthStore, DashboardServer, Handler, same_windows_user_process


class DashboardEvidenceTests(unittest.TestCase):
    def test_sensitive_path_filter_preserves_credential_source_code(self):
        self.assertIsNone(evidence.SENSITIVE_PATH_RE.search("credentials.py"))
        self.assertIsNotNone(evidence.SENSITIVE_PATH_RE.search(".env.production"))
        self.assertIsNotNone(evidence.SENSITIVE_PATH_RE.search("secrets/gcp-service-account.json"))
        self.assertIsNotNone(evidence.SENSITIVE_PATH_RE.search("ops/oauth-private.pem"))

    def test_redactor_removes_tokens_and_sensitive_fields(self):
        value = {"message": "Authorization: Bearer abcdefghijklmnop", "client_email": "private@example.invalid", "status": "FAIL"}
        clean = evidence.sanitize(value)
        text = json.dumps(clean)
        self.assertNotIn("abcdefghijklmnop", text)
        self.assertNotIn("private@example.invalid", text)
        self.assertEqual(clean["status"], "FAIL")

    def test_old_telemetry_is_never_current_healthy(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "telemetry.json"
            path.write_text(json.dumps({"generated_at": "2026-10-10 02:00:00", "nodes": {"sheet": {"status": "HEALTHY", "name": "Sheets", "diagnostics": "old"}}}), encoding="utf-8")
            old = 1_700_000_000
            os.utime(path, (old, old))
            with patch.object(evidence, "TELEMETRY_FILE", path):
                result = evidence.telemetry_observation()
        self.assertEqual(result["freshness"], "STALE")
        self.assertEqual(result["nodes"][0]["reported_health"], "HEALTHY")
        self.assertEqual(result["nodes"][0]["health"], "UNKNOWN")

    def test_missing_telemetry_is_unknown_not_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(evidence, "TELEMETRY_FILE", Path(temp) / "missing.json"):
                result = evidence.telemetry_observation()
        self.assertEqual(result["health"], "UNKNOWN")
        self.assertEqual(result["collection"], "ERROR")

    def test_cookie_is_signed_and_expires(self):
        auth = AuthStore()
        cookie = auth.session_cookie(now=1000)
        self.assertTrue(auth.valid_cookie(cookie, now=1001))
        self.assertFalse(auth.valid_cookie(cookie + "x", now=1001))
        self.assertFalse(auth.valid_cookie(cookie, now=1000 + 12 * 60 * 60 + 1))

    def test_graph_edges_are_labeled_source_derived(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a.py").write_text("import b\ndef run():\n    return helper()\ndef helper():\n    return 1\n", encoding="utf-8")
            (root / "b.py").write_text("VALUE = 1\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "add", "a.py", "b.py"], check=True)
            with patch.object(evidence, "ROOT", root):
                graph = evidence.repository_graph()
        self.assertTrue(graph["edges"])
        self.assertTrue(all(edge["source"] == "SOURCE_DERIVED" for edge in graph["edges"]))

    def test_snapshot_store_persists_compact_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            store = evidence.SnapshotStore(Path(temp))
            store.append({"observed_at": "2026-10-11T00:00:00Z", "repository_tree": {"total_matching": 4, "entries": [{"path": "a.py"}]}, "dependency_graph": {"nodes": [1, 2], "edges": [1]}, "history": {"window_commits": 3}, "incidents": []})
            row = store.recent(1)[0]
        self.assertNotIn("repository_tree", row)
        self.assertNotIn("dependency_graph", row)
        self.assertEqual(row["analysis_summary"]["graph_nodes"], 2)

    def test_issue_export_redacts_and_writes_required_files(self):
        issue = {"issue_id": "TEST-1", "title": "fixture", "severity": "medium", "first_seen": "now", "last_seen": "now", "observation_window": "test", "repository_sha": "abc", "runtime_sha_if_known": None, "affected_entities": ["a.py"], "source_references": ["fixture"], "evidence_references": ["fixture"], "reproduction_status": "SIMULATED", "root_cause_status": "UNKNOWN", "competing_hypotheses": ["none"], "observed_impact": "Bearer abcdefghijklmnop", "suspected_impact": "unknown", "prerequisite_steps": [], "proposed_correction": "none", "verification_tests": [], "rollback": "none", "approval_requirements": "none", "remaining_unknowns": []}
        with tempfile.TemporaryDirectory() as temp:
            export_root = Path(temp) / "exports"
            with patch.object(evidence, "EXPORT_ROOT", export_root):
                exported = evidence.export_issue_package(issue)
                target = export_root / exported["package"]
                names = {p.name for p in target.iterdir()}
                content = (target / "issue.json").read_text(encoding="utf-8")
                archive = target / f"{target.name}.zip"
                with zipfile.ZipFile(archive) as bundle:
                    members = set(bundle.namelist())
                    manifest = json.loads(bundle.read("manifest.sha256.json"))
                    hashes_valid = all(hashlib.sha256(bundle.read(name)).hexdigest() == digest for name, digest in manifest["files"].items())
        self.assertTrue({"issue.json", "evidence_manifest.json", "reproduction.md", "affected_paths.json", "proposed_solution.md", "verification_plan.md", "agent_prompt.txt", "manifest.sha256.json"}.issubset(names))
        self.assertTrue(exported["download_url"].endswith(".zip"))
        self.assertIn("issue.json", members)
        self.assertEqual(set(manifest["files"]), members - {"manifest.sha256.json"})
        self.assertTrue(hashes_valid)
        self.assertNotIn("abcdefghijklmnop", content)

    def test_remote_or_non_windows_peer_is_not_trusted(self):
        with patch.object(evidence.os, "name", "posix"):
            self.assertFalse(same_windows_user_process(12345, 8765))

    def test_loopback_api_rejects_unverified_process_and_bad_origin(self):
        server = DashboardServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()
        port = server.server_address[1]
        try:
            url = f"http://127.0.0.1:{port}/api/v1/overview"
            with patch("ops_dashboard.server.same_windows_user_process", return_value=False):
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    urllib.request.urlopen(url, timeout=3)
                self.assertEqual(denied.exception.code, 401)
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/v1/auth/login",
                data=b"{}",
                headers={"Content-Type": "application/json", "Origin": "https://attacker.invalid"},
                method="POST",
            )
            with patch("ops_dashboard.server.same_windows_user_process", return_value=False):
                with self.assertRaises(urllib.error.HTTPError) as bad_origin:
                    urllib.request.urlopen(request, timeout=3)
                self.assertEqual(bad_origin.exception.code, 400)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
