$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "src"
python -m road_lab.road_check selftest
python -m day11_pipeline.qa_runner
python scripts/verify_all.py
