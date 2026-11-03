# tests/test_lookback.py
# Look-back module (engine/lookback.py, utilities/<utility>_lookback.json): the
# revenue-requirement bridge sums (detailed and grouped), the bill categories and
# the EIA trend sum, the Dominion riders reproduce the SCC totals, asked against
# granted totals, every figure carries a source or a status, and the export
# carries the block.

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
def test_grouped_bridge_sums_and_matches_detailed(key):
    uj, _ = E.load_utility(key)
    lb = LB.load_lookback(key)
    det, grp = LB.rr_bridge(lb, uj), LB.rr_bridge_grouped(lb, uj)
    assert abs(LB.bridge_check(grp)) < 1e-6
    for g in ('start', 'subtotal', 'end'):
        assert grp.loc[grp['group'] == g, 'value_m'].iloc[0] == pytest.approx(det.loc[det['group'] == g, 'value_m'].iloc[0], rel=1e-12)
    tot = LB.group_totals(grp)
    present = [g for g in LB.GROUPS if g in set(grp['group'])]
    assert list(tot.index) == present
    assert ('programme_outside_base_rates' in present) == ('programme_normalisation' in lb['rr_bridge'])
    assert tot.sum() == pytest.approx(det.loc[det['group'] == 'end', 'value_m'].iloc[0] - det.loc[det['group'] == 'start', 'value_m'].iloc[0], rel=1e-12)
    # cost of capital and rate-base growth carry the detailed rows unchanged
    assert tot['cost_of_capital'] == pytest.approx(det[det['group'] == 'return']['value_m'].sum(), rel=1e-12)
    assert tot['rate_case'] == pytest.approx(lb['rr_bridge']['step_2026']['value'], rel=1e-12)
    for y in ('2021', '2025'):
        d = LB.functional_year(lb, y)
        # property tax split and O&M normalisation are attributions inside the reported totals
        assert d['plant_property_tax'] + d['non_plant_taxes'] == pytest.approx(d['taxes_other'], rel=1e-12)
        assert d['plant_property_tax'] >= 0 and d['non_plant_taxes'] >= 0
        assert d['om_normalised'] + d['non_service_benefits'] + d.get('programme_om', 0.0) == pytest.approx(d['om'], rel=1e-12)
        r = lb['rr_bridge']['property_tax_attribution']['ratio'][y]
        f1 = lb['rr_bridge']['form1'][y]
        assert r['status'] == 'derived'
        assert r['value'] == pytest.approx(f1['property_tax_total_company']['value'] / f1['net_plant_total_company']['value'], abs=1e-6)


@pytest.mark.parametrize('key', KEYS)
def test_om_normalisation_check(key):
    """Con Edison's A&G fall is driven by pension and retiree-benefit credits (account 926); the others are not."""
    lb = LB.load_lookback(key)
    nz = lb['rr_bridge']['om_normalisation']
    f1 = lb['rr_bridge']['form1']
    a926 = [f1[y]['om_ag_employee_pensions_benefits']['value'] for y in ('2021', '2025')]
    ag = [f1[y]['om_admin_general']['value'] for y in ('2021', '2025')]
    ns = [nz['non_service_benefits_electric'][y]['value'] for y in ('2021', '2025')]
    if key == 'ConEd':
        assert nz['applied'] and a926[1] < 0 < a926[0]
        assert a926[0] - a926[1] > ag[0] - ag[1] > 0       # the 926 swing exceeds the whole A&G fall
        assert ns[1] < 0 < ns[0]
        assert all(nz['non_service_benefits_electric'][y]['status'] == 'derived' for y in ('2021', '2025'))
    else:
        assert not nz['applied'] and ns == [0.0, 0.0]
        assert min(a926) >= 0


@pytest.mark.parametrize('key', KEYS)
def test_bill_trend_like_for_like(key):
    lb = LB.load_lookback(key)
    t = LB.bill_trend(lb)
    assert list(t.index) == [2021, 2022, 2023, 2024, 2025]
    kwh = lb['benchmark_kwh_month']
    for y, d in lb['bill']['eia_series'].items():
        assert t.loc[int(y), 'total'] == pytest.approx(d['bundled_cents_kwh']['value'] * kwh / 100, rel=1e-12)
        # the series is the utility's own state (Virginia for Dominion, Maryland for Pepco, Connecticut)
        st = {'DomVA': 'VA', 'PepcoMD': 'MD', 'EversourceCT': 'CT', 'UI_CT': 'CT'}.get(key, 'NY')
        assert f' {st} part' in d['bundled_cents_kwh']['source']
    if key == 'DomVA':
        assert t['delivery'].isna().all()
    else:
        assert (t['delivery'] + t['supply'] - t['total']).abs().max() < 1e-9
        assert (t['delivery'] > 0).all() and (t['supply'] > 0).all()
    assert 'not presented as a change' in lb['bill']['trend_basis']


def test_dominion_riders_reproduce_scc_bills():
    uj, _ = E.load_utility('DomVA')
    lb = LB.load_lookback('DomVA')
    rd = lb['riders']
    for y, b in rd['residential_bill'].items():
        assert set(b['components']) <= set(rd['definitions']), y
        assert sum(c['value'] for c in b['components'].values()) == pytest.approx(b['total']['value'], abs=0.011), y
    # 2026: the tariff lines of the starting bill (before the capacity carve-out), excluding taxes
    sb = uj['starting_bill']
    raw = sum((l['rate'] * sb['benchmark_kwh_month'] if l['unit'] == '$/kWh' else l['rate']) for l in sb['lines']
              if l['rate'] is not None and l.get('included_in_benchmark', True))
    assert rd['residential_bill']['2026']['total']['value'] + rd['residential_bill']['2026']['taxes']['value'] == pytest.approx(raw, abs=1e-6)
    dist = {k for k, d in rd['definitions'].items() if d['distribution_related']}
    assert dist == {'U', 'GT', 'DIST', 'RBB'}
    for k in ('OSW', 'GEN', 'T1', 'RPS', 'CE', 'DSM', 'E', 'CCR', 'SNA', 'fuel_factor'):
        assert rd['revenue_requirements'][k], k
    bb = LB.dominion_bill_bridge(lb)
    for y in ('2021', '2022', '2023', '2024', '2025'):
        assert bb.loc['total', y] == pytest.approx(rd['residential_bill'][y]['total']['value'], abs=0.011)
        assert bb.loc[list(LB.RIDER_GROUPS), y].sum() == pytest.approx(bb.loc['total', y], abs=1e-9)
    assert bb.loc['distribution_related_riders', '2025'] == pytest.approx(bb.loc['distribution', '2025'], abs=1e-9)
    # T1: base-rate transmission + Rider T1 = the total transmission revenue requirement
    for e in rd['revenue_requirements']['T1']:
        assert e['base_rate_transmission_m']['value'] + e['rider_t1_m']['value'] == e['total_revenue_requirement_m']['value']


@pytest.mark.parametrize('key', KEYS)
def test_asked_granted_totals(key):
    lb = LB.load_lookback(key)
    tot = LB.asked_granted_totals(lb)
    inc = [p for p in lb['proceedings'] if p['comparison']['included_in_totals']]
    assert tot['requested_m'] == pytest.approx(sum(p['comparison']['requested_m']['value'] for p in inc))
    assert tot['approved_m'] == pytest.approx(sum(p['comparison']['approved_m']['value'] for p in inc))
    assert 0 < tot['approved_pct_of_requested'] < 100
    for p in lb['proceedings']:
        assert p['comparison']['requested_m']['status'] in LB.STATUSES and p['comparison']['basis']
        # pending cases never count as decided; temporary rates are labelled
        if p['status'] == 'pending':
            assert not p['comparison']['included_in_totals']
    if key == 'RGE':
        p = next(p for p in lb['proceedings'] if p['docket'] == 'Case 25-E-0379')
        assert p['comparison']['temporary'] and 'temporary' in p['revenue_approved_m']['unit']
        assert p['revenue_approved_m'].get('label') == 'temporary rates'
        assert 'Case 25-E-0379' not in tot['proceedings'] and 'Case 25-E-0379' in LB.asked_granted_totals(lb, True)['proceedings']


@pytest.mark.parametrize('key', KEYS)
def test_export_lookback_block(key):
    with open(os.path.join(ROOT, 'exports', f'{key}.json')) as f:
        ex = json.load(f)
    lk = ex['lookback']
    for k in ('bill_trend', 'bill_2026_tariff', 'bill_levels_by_basis', 'rr_bridge', 'supply_side', 'proceedings',
              'asked_granted_totals', 'class_allocation'):
        assert k in lk
    assert 'bill_comparison' not in lk          # the mixed-basis comparison is not presented as a change
    assert ('riders' in lk) == (key == 'DomVA')
    uj, _ = E.load_utility(key)
    lb = LB.load_lookback(key)
    br, grp = LB.rr_bridge(lb, uj), LB.rr_bridge_grouped(lb, uj)
    assert [r['value_m'] for r in lk['rr_bridge']['rows']] == pytest.approx(br['value_m'].tolist(), rel=1e-12)
    assert [r['value_m'] for r in lk['rr_bridge']['grouped_rows']] == pytest.approx(grp['value_m'].tolist(), rel=1e-12)
    assert [r['total_usd_month'] for r in lk['bill_trend']['rows']] == pytest.approx(LB.bill_trend(lb)['total'].tolist(), rel=1e-12)
