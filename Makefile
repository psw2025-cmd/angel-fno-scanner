.PHONY: 100-year-check
100-year-check:
	python tools/memory_guard.py
	python tools/chaos_inject.py
	python -m pytest tests/ -q
	@test -n "$(METADATA)" || (echo "METADATA=path/to/real/cycle_metadata.json required; FAIL CLOSED"; exit 1)
	python tools/100_year_guard.py --phase pre --metadata "$(METADATA)"
	@echo "Run authenticated read-only probe separately via workflow_dispatch dry_run=true; postflight requires sink readback."
