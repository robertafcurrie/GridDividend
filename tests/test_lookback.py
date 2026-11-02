# tests/test_lookback.py
# Look-back module (engine/lookback.py, utilities/<utility>_lookback.json): the
# revenue-requirement bridge sums, the bill categories sum to the total, every
# figure carries a source or a status, and the export carries the block.

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from engine import layers as LY    # noqa: E402
from engine import lookback as LB  # noqa: E402
import export_results as E         # noqa: E402

KEYS = list(LB.LOOKBACK_FILES)


@pytest.mark.parametrize('key', KEYS)
def test_bridge_sums_to_change_in_revenue_requirement(key):
    uj, _ = E.load_utility(key)
    lb = LB.load_lookback(key)
    br = LB.rr_bridge(lb, uj)
    assert abs(LB.bridge_check(br)) < 1e-6
    start = br.loc[br['group'] == 'start', 'value_m'].iloc[0]
    mid = br.loc[br['group'] == 'subtotal', 'value_m'].iloc[0]
    end = br.loc[br['group'] == 'end', 'value_m'].iloc[0]
    a, b = LB.functional_year(lb, '2021'), LB.functional_year(lb, '2025')
    assert start == pytest.approx(a['rr'], rel=1e-12) and mid == pytest.approx(b['rr'], rel=1e-12)
    steps = br[~br['group'].isin(['start', 'subtotal', 'end', 'rate_case'])]['value_m'].sum()
    assert start + steps == pytest.approx(mid, rel=1e-12)
    assert end - mid == pytest.approx(lb['rr_bridge']['step_2026']['value'], rel=1e-12)
    # rate base growth at the 2021 WACC equals the change in rate base x that WACC (capital shares sum to 1)
    rbg = br[br['group'] == 'rate_base_growth']['value_m'].sum()
    assert rbg == pytest.approx((b['rate_base'] - a['rate_base']) * a['wacc'], rel=1e-9)
    assert sum(LB.capital_shares(uj).values()) == pytest.approx(1.0, abs=1e-6)
    # each year's revenue requirement goes through the same formula
    for d in (a, b):
        assert d['rr'] == pytest.approx(LB.revenue_requirement(d['rate_base'], d['wacc'], d['depreciation'], d['om'],
                                                               d['taxes_other'], d['income_taxes']), rel=1e-12)


@pytest.mark.parametrize('key', KEYS)
def test_bill_categories_sum_to_total(key):
    uj, _ = E.load_utility(key)
    lb = LB.load_lookback(key)
    bill = LB.bill_comparison(lb, uj)
    cats = list(LY.CATEGORIES)
    # 2026: the starting bill by category sums to its total
    assert bill.loc[cats, '2026'].sum() == pytest.approx(bill.loc['total', '2026'], abs=1e-9)
    assert bill.loc['total', '2026'] == pytest.approx(sum(d['month'] for d in LY.starting_lines(uj)), abs=1e-9)
    # 2021: itemised categories plus the unitemised remainder sum to the total
    known = bill.loc[cats, '2021'].fillna(0).sum()
    unit = bill.loc[[i for i in bill.index if i.startswith('unitemised_')], '2021'].fillna(0).sum()
    assert known + unit == pytest.approx(bill.loc['total', '2021'], abs=0.011)


@pytest.mark.parametrize('key', KEYS)
def test_every_figure_has_source_or_status(key):
    lb = LB.load_lookback(key)
    figs = list(LB.iter_figures(lb))
    assert len(figs) > 50
    for path, spec in figs:
        assert spec.get('status') in LB.STATUSES, path
        assert spec.get('source'), path
        assert spec.get('as_of'), path
        if spec['value'] is None and spec['status'] not in ('_VERIFY', 'setting', 'sourced'):
            pytest.fail(f'{path}: missing value must be _VERIFY')
    # proceedings and class allocation: every figure field is a spec; adjustments carry a source and status
    for p in lb['proceedings']:
        for f in ('filed', 'decided', 'revenue_requested_m', 'revenue_approved_m', 'roe_requested', 'roe_granted'):
            assert isinstance(p[f], dict) and p[f].get('status') in LB.STATUSES, (p['docket'], f)
        assert p['status'] in ('decided', 'pending'), p['docket']
        for adj in p.get('capital_adjustments', []):
            assert adj.get('source') and adj.get('status') in LB.STATUSES, (p['docket'], adj['item'])
        for r in p.get('commission_reasons', []):
            assert r.get('quote') and r.get('source'), p['docket']
    for c in lb['class_allocation']:
        for f in ('residential_share_of_increase', 'residential_share_of_sales', 'customer_charge_before', 'customer_charge_after'):
            assert isinstance(c[f], dict) and c[f].get('status') in LB.STATUSES, (c['docket'], f)
    # RG&E's pending case is marked pending
    if key == 'RGE':
        assert [p['status'] for p in lb['proceedings'] if p['docket'] == 'Case 25-E-0379'] == ['pending']
    assert 'influenced' in lb['supply_side']['influence'].lower() and 'not controlled' in lb['supply_side']['influence']


@pytest.mark.parametrize('key', KEYS)
def test_export_lookback_block(key):
    with open(os.path.join(ROOT, 'exports', f'{key}.json')) as f:
        ex = json.load(f)
    lk = ex['lookback']
    for k in ('bill_comparison', 'rr_bridge', 'supply_side', 'proceedings', 'class_allocation'):
        assert k in lk
    uj, _ = E.load_utility(key)
    br = LB.rr_bridge(LB.load_lookback(key), uj)
    assert [r['value_m'] for r in lk['rr_bridge']['rows']] == pytest.approx(br['value_m'].tolist(), rel=1e-12)
