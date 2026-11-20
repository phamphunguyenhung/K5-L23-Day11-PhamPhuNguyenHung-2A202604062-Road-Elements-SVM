#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="src"
python3 -m road_lab.road_check selftest
python3 -m day11_pipeline.qa_runner
python3 scripts/verify_all.py
