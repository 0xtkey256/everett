PY := .venv/bin/python
.PHONY: test fake snapshot fix serve web cleanup
test:
	cd orchestrator && ../$(PY) -m pytest -q
	node --test web/js/reducer.test.mjs
fake:
	cd orchestrator && ../$(PY) -m everett.fake --seed 7
snapshot:
	$(PY) scripts/build_snapshot.py --class container
fix:
	cd orchestrator && ../$(PY) -m everett.cli slugify/L1-word-boundary --save live
serve:
	cd orchestrator && ../$(PY) -m uvicorn everett.server:app --host 0.0.0.0 --port 8000
web:
	cd web && python3 -m http.server 8790
cleanup:
	$(PY) scripts/cleanup.py
