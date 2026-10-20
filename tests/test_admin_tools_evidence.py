"""Exercise actual admin functions without importing Windows/runtime integrations."""
import ast
from pathlib import Path
import ssl
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch, MagicMock

tree = ast.parse((Path(__file__).resolve().parents[1] / 'admin_tools.py').read_text(encoding='utf-8'))
names = {'probe_http', 'check_brokers', 'summarize_acceptance'}
namespace = {'ssl': ssl, 'time': time, 'urllib': urllib}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[]), 'admin_tools.py', 'exec'), namespace)


class AdminEvidenceTests(unittest.TestCase):
    def test_http_errors_never_pass(self):
        for code in (401, 403, 404, 500):
            with self.subTest(code=code), patch('urllib.request.urlopen', side_effect=urllib.error.HTTPError('https://example.invalid', code, 'error', {}, None)):
                self.assertEqual(namespace['probe_http']('https://example.invalid')['status'], 'FAIL')

    def test_public_200_is_not_account_authentication(self):
        response = MagicMock()
        response.__enter__.return_value.status = 200
        with patch('urllib.request.urlopen', return_value=response):
            result = namespace['probe_http']('https://example.invalid')
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertFalse(result['authenticated'])
        self.assertEqual(result['transport'], 'REACHABLE')

    def test_timeout_keeps_unknown_and_redacts_message(self):
        with patch('urllib.request.urlopen', side_effect=TimeoutError('sensitive request context')):
            result = namespace['probe_http']('https://example.invalid')
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertNotIn('sensitive', str(result))

    def test_broker_summary_does_not_upgrade_public_reads(self):
        with patch.dict(namespace, probe_http=lambda url: {'status': 'UNKNOWN'}):
            self.assertEqual(namespace['check_brokers']()['status'], 'UNKNOWN')

    def test_every_mandatory_status_required(self):
        passed = {'status': 'PASS'}
        cloud = {'bigquery': passed, 'sheets_ssot': passed}
        safe = {'status': 'PASS', 'runtime_enforcement_verified': True}
        status, checks = namespace['summarize_acceptance'](passed, safe, {'status': 'OPEN'}, passed, cloud, passed)
        self.assertEqual(status, 'PASS')
        for component in ('host', 'calendar', 'runtime_safety', 'github'):
            with self.subTest(component=component):
                status, _ = namespace['summarize_acceptance'](
                    {} if component == 'host' else passed,
                    passed if component == 'runtime_safety' else safe,
                    {'status': 'UNKNOWN' if component == 'calendar' else 'HOLIDAY'},
                    passed, cloud, {} if component == 'github' else passed)
                self.assertEqual(status, 'UNKNOWN')

    def test_failure_overrides_other_successes(self):
        p = {'status': 'PASS'}
        status, _ = namespace['summarize_acceptance'](p, {'status': 'FAIL'}, {'status': 'HOLIDAY'}, p, {'bigquery': p, 'sheets_ssot': p}, p)
        self.assertEqual(status, 'FAIL')


if __name__ == '__main__':
    unittest.main()
