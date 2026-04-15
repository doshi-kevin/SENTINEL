.PHONY: download download-smoke ingest verify reproduce smoke clean-data help

help:
	@echo "Sentinel-Z make targets:"
	@echo "  make download         — full DARPA TC E5 FiveDirections download (~17 GB, hours)"
	@echo "  make download-smoke   — first 5 chunks per host (~750 MB, ~20 min)"
	@echo "  make ingest           — parse Avro -> graphs + labels at data/auto_processed/"
	@echo "  make verify           — run Phase 4 pipeline; smoke-check outputs"
	@echo "  make reproduce        — full download + ingest + verify"
	@echo "  make smoke            — smoke download + ingest + verify (fast pipeline check)"
	@echo "  make clean-data       — wipe data/auto_processed and data/model_ready"

download:
	python scripts/download_e5.py

download-smoke:
	python scripts/download_e5.py --max-chunks-per-host 5

ingest:
	python scripts/ingest_e5.py

verify:
	python scripts/verify_phase4.py

reproduce: download ingest verify

smoke: download-smoke ingest verify

clean-data:
	rm -rf data/auto_processed data/model_ready
	@echo "data/raw/ NOT removed (manual: rm -rf data/raw)"
