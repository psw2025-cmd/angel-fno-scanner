# 100-Year Autonomy Architecture Makefile
.PHONY: 100-year-check test audit recovery-test reconciliation

100-year-check:
	python tools/memory_guard.py
	python tools/verify_sheets_bq_reconciliation.py
	pytest tests/
	python tools/pre_post_matrix.py
	python tools/crash_safe_test.py
	python tools/test_recovery.py
	python tools/self_learner.py --check

test:
	pytest tests/

reconciliation:
	python tools/verify_sheets_bq_reconciliation.py

recovery-test:
	python tools/test_recovery.py
