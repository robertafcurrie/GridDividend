# Layer engine (engine/layers.py) checks. Run: python -m pytest tests/
import contextlib
import importlib.util
import io
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import layers as LY                       # noqa: E402
from engine import delivery_rr_reconciliation          # noqa: E402

SETUP = ('# ============================================================\n# SECTION 0: SETUP',
         '# ============================================================\n# SECTION 1: USER-ADJUSTABLE',
         '# ============================================================\n# SECTION 1b: NEAR-TERM',
         'def load_utility(key):')
UTILS = [('ConEd', 'GridDividend_NewYork.ipynb'), ('RGE', 'GridDividend_NewYork.ipynb'),
         ('DomVA', 'GridDividend_Virginia.ipynb'), ('PepcoMD', 'GridDividend_Maryland.ipynb')]
_CACHE = {}


def _ns(nb_name):
    if nb_name not in _CACHE:
        nb_dir = os.path.join(ROOT, 'notebooks')
        nb = json.load(open(os.path.join(nb_dir, nb_name)))
        src = [''.join(c['source']) for c in nb['cells'] if c['cell_type'] == 'code']
        ns, cwd = {}, os.getcwd()
        os.chdir(nb_dir)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                for p in SETUP:
                    exec([s for s in src if s.startswith(p)][0], ns)
        finally:
            os.chdir(cwd)
        _CACHE[nb_name] = ns
    return _CACHE[nb_name]


def _utility(key, nb_name):
    ns = _ns(nb_name)
    return ns['UTILITIES'][key], ns['utility_data'][key]


def _check_script():
    spec = importlib.util.spec_from_file_location('check_starting_bill',
                                                  os.path.join(ROOT, 'scripts', 'check_starting_bill.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize('key,nb', UTILS)
def test_all_layers_off_equals_bau(key, nb):
    uj, p = _utility(key, nb)
    for level in LY.LEVELS:
        r = LY.project_layers(uj, p, level, enabled={l: False for l in LY.SAVINGS_LAYERS})
        np.testing.assert_array_equal(r['ss']['bill_total'].values, r['bau']['bill_total'].values)
        np.testing.assert_array_equal(r['ss']['rr_m'].values, r['bau']['rr_m'].values)
        assert (r['ss']['shared_savings_earnings_m'] == 0).all()


@pytest.mark.parametrize('key,nb', UTILS)
def test_starting_total_equals_starting_bill(key, nb):
    uj, _ = _utility(key, nb)
    script_total = _check_script().check(key)['total_month']
    raw = sum(d['month'] for d in LY.starting_lines(uj, carve_out=False, adjustments=False))
    carved = sum(d['month'] for d in LY.starting_lines(uj, carve_out=True, adjustments=False))
    assert raw == pytest.approx(script_total, abs=0.005)
    assert carved == pytest.approx(raw, abs=1e-9)                 # carve-out keeps the total


def test_pepco_order_adjustment():
    uj, _ = _utility('PepcoMD', 'GridDividend_Maryland.ipynb')
    base = sum(d['month'] for d in LY.starting_lines(uj, adjustments=False))
    adj = sum(d['month'] for d in LY.starting_lines(uj, adjustments=True))
    grt = next(l['rate'] for l in uj['starting_bill']['lines'] if l['id'] == 'gross_receipts') / 100
    assert adj - base == pytest.approx(3.94 * (1 + grt))


@pytest.mark.parametrize('key,nb', UTILS)
def test_bau_year_zero_rr_matches_rate_case_target(key, nb):
    uj, p = _utility(key, nb)
    r = LY.project_layers(uj, p)
    target = delivery_rr_reconciliation(p, {})['target_delivery_rr_m']
    assert r['bau']['rr_m'].iloc[0] == pytest.approx(target)
    assert r['bau']['bill_total'].iloc[0] == pytest.approx(
        sum(d['month'] for d in LY.starting_lines(uj)))


def test_hook_layers_cannot_be_enabled():
    uj, p = _utility('ConEd', 'GridDividend_NewYork.ipynb')
    with pytest.raises(NotImplementedError):
        LY.project_layers(uj, p, enabled={'roe': True})
