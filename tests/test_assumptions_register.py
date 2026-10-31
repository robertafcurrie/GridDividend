# tests/test_assumptions_register.py
# The assumptions register (docs/assumptions_register.csv, docs/ASSUMPTIONS.md)
# is generated from utilities/*.json; it must match the JSON exactly.

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import build_assumptions_register as BAR  # noqa: E402


def test_assumptions_register_up_to_date():
    csv_text, md_text = BAR.build()
    for rel, text in ((BAR.CSV_PATH, csv_text), (BAR.MD_PATH, md_text)):
        with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
            assert f.read() == text, f'{rel} is out of date: run python scripts/build_assumptions_register.py'


def test_every_layered_input_has_a_status():
    rows = [r for r in BAR.all_rows() if r['section'] != 'utility_data']
    missing = [f"{r['utility']} {r['layer']}.{r['input']}" for r in rows if r['status'] not in BAR.STATUSES]
    assert not missing, missing
