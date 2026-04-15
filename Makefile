.PHONY: download ingest verify reproduce clean-data help

help:
	@echo "Sentinel-Z make targets:"
	@echo "  make download    — download DARPA TC E5 (FiveDirections) into data/raw/e5/"
	@echo "  make ingest      — parse Avro -> graphs + labels at data/auto_processed/"
	@echo "  make verify      — run Phase 4 pipeline; smoke-check outputs"
	@echo "  make reproduce   — download + ingest + verify (the full chain)"
	@echo "  make clean-data  — wipe data/auto_processed and data/model_ready"

download:
	python scripts/download_e5.py

ingest:
	python scripts/ingest_e5.py

verify:
	python scripts/verify_phase4.py

reproduce: download ingest verify

clean-data:
	rm -rf data/auto_processed data/model_ready
	@echo "data/raw/ NOT removed (manual: rm -rf data/raw)"
