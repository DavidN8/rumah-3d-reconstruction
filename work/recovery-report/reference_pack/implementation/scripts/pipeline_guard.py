"""Prevent historical temporal-zone commands from replacing component outputs."""
import json
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]

def reject_retired_temporal_pipeline():
    record=BASE/'analysis/active-pipeline.json'
    if record.exists() and json.loads(record.read_text(encoding='utf-8')).get('legacy_temporal_pipeline_retired'):
        raise RuntimeError('The three temporal zones are retired. Use scripts/20_component_recovery.py and 21_recovery_pilot.py (plus the full-coverage run in 26_all_usable_coverage.py). Historical datasets/checkpoints are preserved; do not retrain or merge them into the active delivery.')
