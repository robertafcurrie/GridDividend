# tests/test_export.py
# The web-explorer exports (exports/<utility>.json, scripts/export_results.py):
# value flows balance, and totals match the headline figures the model reports now.

import json
import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, ROOT)

import export_results as E          # noqa: E402
from engine import layers as LY     # noqa: E402


def _export(key):
    path = os.path.join(ROOT, 'exports', f'{key}.json')
    assert os.path.exists(path), f'missing {path}: run python scripts/export_results.py'
    return json.load(open(path))


@pytest.mark.parametrize('key', list(E.UTILITIES))
def test_export_flows_balance(key):
    ex = _export(key)
    for pace in LY.PACES:
        for sc in LY.SCENARIOS:
            r = ex['runs'][pace][sc]
            for basis, f in r['value_flows_m'].items():
                net = sum(f['sources'].values()) + f['program_costs']
                assert f['net_value'] == pytest.approx(net, rel=1e-9, abs=1e-6), (pace, sc, basis)
                assert sum(f['to'].values()) == pytest.approx(net, rel=1e-9, abs=1e-6), (pace, sc, basis)
                ins = sum(l['value'] for l in f['links'] if l['target'] == 'net_value')
                outs = sum(l['value'] for l in f['links'] if l['source'] == 'net_value')
                assert ins == pytest.approx(outs, rel=1e-9, abs=1e-6), (pace, sc, basis)
            for y, w in r['waterfall_usd_month'].items():
                steps = sum(v for k, v in w.items() if k not in ('BAU', 'Shared savings'))
                assert w['Shared savings'] - w['BAU'] == pytest.approx(steps, abs=1e-3), (pace, sc, y)
            yr = r['yearly']
            assert len(yr['year']) == len(LY.YEARS) == len(yr['customer_savings_m'])
            assert set(yr['avg_residential_bill_usd_month']['bau']) == set(LY.CATEGORIES) | {'total'}


@pytest.mark.parametrize('key', list(E.UTILITIES))
def test_export_totals_match_headline(key):
    ex = _export(key)
    uj0, p = E.load_utility(key)
    for pace in LY.PACES:
        uj = E.with_pace(uj0, pace)
        for sc in LY.SCENARIOS:
            r = ex['runs'][pace][sc]
            run = LY.project_layers(uj, p, scenario=sc)
            sm = LY.system_summary(run)
            b, s = run['bau'].set_index('year'), run['ss'].set_index('year')
            f = r['value_flows_m']['undiscounted_nominal']
            cs = f['to']['residential_customers'] + f['to']['business_customers']
            assert cs / 1e3 == pytest.approx(sm['Customer savings ($B, undiscounted nominal)'], rel=1e-9)
            assert sum(r['yearly']['customer_savings_m']) / 1e3 == pytest.approx(sm['Customer savings ($B, undiscounted nominal)'], rel=1e-5)
            f3 = r['value_flows_m']['npv3_2026']
            assert (f3['to']['residential_customers'] + f3['to']['business_customers']) / 1e3 == pytest.approx(
                sm['Customer savings ($B, NPV 3%, 2026 $)'], rel=1e-9)
            assert f['to']['shared_savings_earnings'] / 1e3 == pytest.approx(sm['Shared savings earnings ($B, undiscounted nominal)'], rel=1e-9)
            for y in (2035, 2050):
                sav = b.loc[y, 'avg_bill_total'] - s.loc[y, 'avg_bill_total']
                assert r['headline'][f'monthly_saving_{y}'] == pytest.approx(sav, rel=1e-9)
                w = r['waterfall_usd_month'][str(y)]
                assert w['BAU'] - w['Shared savings'] == pytest.approx(sav, abs=1e-3)
    assert {row['type'] for row in ex['tornado']['utility_forecast']['rows']} <= {'policy', 'external'}


@pytest.mark.parametrize('key', list(E.UTILITIES))
def test_export_share_sweep(key):
    """0.30 matches the headline; customer savings + earnings is the same at every share where the pool is positive."""
    ex = _export(key)
    for pace in LY.PACES:
        for sc in LY.SCENARIOS:
            r = ex['runs'][pace][sc]
            sw, h = r['share_sweep'], r['headline']
            assert set(sw) == {f'{x:.2f}' for x in E.SHARE_SWEEP}
            base = sw['0.30']
            assert base['customer_savings_b_undiscounted'] == pytest.approx(h['customer_savings_b_undiscounted'], rel=1e-12)
            assert base['customer_savings_b_npv3'] == pytest.approx(h['customer_savings_b_npv3'], rel=1e-12)
            assert base['shared_savings_earnings_b'] == pytest.approx(h['shared_savings_earnings_b'], rel=1e-12)
            assert base['monthly_saving_2035'] == pytest.approx(h['monthly_saving_2035'], rel=1e-12)
            assert base['monthly_saving_2050'] == pytest.approx(h['monthly_saving_2050'], rel=1e-12)
            pool = base['yearly']['savings_pool_m']
            total = {k: [c + e for c, e in zip(v['yearly']['customer_savings_m'], v['yearly']['shared_savings_earnings_m'])]
                     for k, v in sw.items()}
            for i, pv in enumerate(pool):
                if pv > 0:
                    for k in sw:
                        assert total[k][i] == pytest.approx(total['0.30'][i], abs=2e-3), (pace, sc, k, i)
            # earnings rise and customer savings fall with the share
            e = [sw[f'{x:.2f}']['shared_savings_earnings_b'] for x in E.SHARE_SWEEP]
            c = [sw[f'{x:.2f}']['customer_savings_b_undiscounted'] for x in E.SHARE_SWEEP]
            assert e == sorted(e) and c == sorted(c, reverse=True)


@pytest.mark.parametrize('key', list(E.UTILITIES))
def test_export_objective(key):
    """Objective sweep: 0% matches the headline exactly, savings rise with the objective; earnings fields consistent."""
    ex = _export(key)
    for pace in LY.PACES:
        for sc in LY.SCENARIOS:
            r = ex['runs'][pace][sc]
            sw, h = r['objective_sweep'], r['headline']
            assert set(sw) == {f'{x:.3f}' for x in E.OBJECTIVE_SWEEP}
            z = sw['0.000']
            for k in ('customer_savings_b_undiscounted', 'customer_savings_b_npv3', 'shared_savings_earnings_b',
                      'monthly_saving_2035', 'monthly_saving_2050'):
                assert z[k] == h[k], (pace, sc, k)
            cs = [sw[f'{x:.3f}']['customer_savings_b_undiscounted'] for x in E.OBJECTIVE_SWEEP]
            assert all(a < b for a, b in zip(cs, cs[1:])), (pace, sc, cs)
            for basis in r['value_flows_m']:
                assert r['value_flows_m'][basis]['sources']['additional_objective'] == 0.0
            y = r['yearly']
            for case in ('bau', 'shared_savings'):
                for et, rb, epr in zip(y['earnings_total_m'][case], y['rate_base_m'][case], y['earnings_per_rate_base'][case]):
                    assert epr == pytest.approx(et / rb, rel=1e-3)


def test_export_flows_balance_with_objective():
    """With a non-zero objective the new additional_objective source is positive and the flows still balance."""
    uj, p = E.load_utility('DomVA')
    for base in LY.OBJECTIVE_BASES:
        run = LY.project_layers(uj, p, overrides={('objective', 'objective_pct'): 0.05, ('objective', 'objective_base'): base})
        f = E.sankey(E.value_flows(run, p))
        for basis, v in f.items():
            assert v['sources']['additional_objective'] > 0
            assert sum(v['to'].values()) == pytest.approx(v['net_value'], rel=1e-9)
            cs = v['to']['residential_customers'] + v['to']['business_customers']
        sm = LY.system_summary(run)
        assert cs / 1e3 == pytest.approx(sm['Customer savings ($B, NPV 3%, 2026 $)'], rel=1e-9)


@pytest.mark.parametrize('key', list(E.UTILITIES))
def test_export_objective_run_blocks(key):
    """Each objective level carries a full run block: 0% equals the top-level block; flows balance; totals match the level."""
    ex = _export(key)
    for pace in LY.PACES:
        for sc in LY.SCENARIOS:
            r = ex['runs'][pace][sc]
            for lvl, e in r['objective_sweep'].items():
                blk = e['run']
                assert set(blk) == {'yearly', 'waterfall_usd_month', 'value_flows_m'}
                if lvl == '0.000':
                    for k in blk:
                        assert blk[k] == r[k], (pace, sc, k)
                for basis, f in blk['value_flows_m'].items():
                    net = sum(f['sources'].values()) + f['program_costs']
                    assert f['net_value'] == pytest.approx(net, rel=1e-9, abs=1e-6)
                    assert sum(f['to'].values()) == pytest.approx(net, rel=1e-9, abs=1e-6)
                    assert (f['sources']['additional_objective'] > 0) == (e['objective_pct'] > 0), (pace, sc, lvl, basis)
                u = blk['value_flows_m']['undiscounted_nominal']
                cs = u['to']['residential_customers'] + u['to']['business_customers']
                assert cs / 1e3 == pytest.approx(e['customer_savings_b_undiscounted'], rel=1e-9)
                assert u['to']['shared_savings_earnings'] / 1e3 == pytest.approx(e['shared_savings_earnings_b'], rel=1e-9)
                assert blk['yearly']['customer_savings_m'] == e['yearly']['customer_savings_m']
                for y in (2035, 2050):
                    w = blk['waterfall_usd_month'][str(y)]
                    assert w['BAU'] - w['Shared savings'] == pytest.approx(e[f'monthly_saving_{y}'], abs=1e-3)
                    steps = sum(v for k, v in w.items() if k not in ('BAU', 'Shared savings'))
                    assert w['Shared savings'] - w['BAU'] == pytest.approx(steps, abs=1e-3)
                    if e['objective_pct'] > 0:
                        assert w['objective'] < 0                 # the objective lowers the bill


@pytest.mark.parametrize('key', list(E.UTILITIES))
def test_export_advance(key):
    """Advance blocks: identities hold, worst year is consistent with the yearly bills, stress = Central-sized, Cautious-realized."""
    ex = _export(key)
    blocks = [(ex['runs'][pace][sc]['advance'], sc, 'Cautious') for pace in LY.PACES for sc in LY.SCENARIOS]
    blocks += [(ex['advance_stress'][pace], 'Cautious', 'Central') for pace in LY.PACES]
    for blk, realized, sizing in blocks:
        sm, y = blk['summary'], blk['yearly']
        assert sm['realized_scenario'] == realized and sm['sizing_scenario'] == sizing
        assert sm['credits_paid_m'] + sm['financing_cost_m'] - sm['recoveries_m'] == pytest.approx(sm['balance_2050_m'], abs=1e-3)
        assert sum(y['advance_credit_m']) == pytest.approx(sm['credits_paid_m'], abs=1e-2)
        gap = [s - b for s, b in zip(y['avg_residential_bill_usd_month']['shared_savings'], y['avg_residential_bill_usd_month']['bau'])]
        w = sm['worst_year_vs_bau']
        assert w['shared_savings_minus_bau_usd_month'] == pytest.approx(max(gap), abs=1e-3)
        assert w['exceeds_bau'] is False                  # the cap keeps every year at or below BAU
        assert sm['customer_savings_less_unrecovered_balance_b'] == pytest.approx(
            sm['customer_savings_b_undiscounted'] - sm['balance_2050_m'] / 1e3, rel=1e-9)
    # the default model is untouched: the advance blocks do not change the headline
    for pace in LY.PACES:
        for sc in LY.SCENARIOS:
            assert ex['runs'][pace][sc]['share_sweep']['0.30']['customer_savings_b_undiscounted'] == \
                ex['runs'][pace][sc]['headline']['customer_savings_b_undiscounted']


@pytest.mark.parametrize('key', list(E.UTILITIES))
def test_export_advance_defaults(key):
    """Enabled defaults: bill-savings recovery, recoverable sizing, securitized 4%; Cautious sized and realized clears."""
    ex = _export(key)
    for pace in LY.PACES:
        sm = ex['runs'][pace]['Cautious']['advance']['summary']
        assert (sm['recovery_source'], sm['sizing_basis'], sm['financing'], sm['financing_rate']) == \
            ('bill_savings', 'recoverable', 'securitized', 0.04)
        assert abs(sm['balance_2050_m']) < 1e-3
        mc = sm['monthly_credit_2027_2031_usd']
        assert set(mc) == {str(y) for y in range(2027, 2032)} and mc['2027'] > 0


FS = {('mechanism', 'fast_start'): True}


@pytest.mark.parametrize('key', list(E.UTILITIES))
def test_export_fast_start_matches_direct_runs(key):
    """fast_start blocks equal direct runs with fast_start on; flows balance; the waterfall matches the saving."""
    ex = _export(key)
    uj0, p = E.load_utility(key)
    for pace in LY.PACES:
        uj = E.with_pace(uj0, pace)
        for sc in LY.SCENARIOS:
            blk = ex['runs'][pace][sc]['fast_start']
            run = LY.project_layers(uj, p, scenario=sc, overrides=FS)
            sm = LY.system_summary(run)
            b, s = run['bau'], run['ss']
            h = blk['headline']
            assert h['customer_savings_b_undiscounted'] == pytest.approx(sm['Customer savings ($B, undiscounted nominal)'], rel=1e-12)
            assert h['customer_savings_b_npv3'] == pytest.approx(sm['Customer savings ($B, NPV 3%, 2026 $)'], rel=1e-12)
            assert h['shared_savings_earnings_b'] == pytest.approx(sm['Shared savings earnings ($B, undiscounted nominal)'], rel=1e-12)
            for y in (2035, 2050):
                sav = float(b.loc[b['year'] == y, 'avg_bill_total'].iloc[0] - s.loc[s['year'] == y, 'avg_bill_total'].iloc[0])
                assert h[f'monthly_saving_{y}'] == pytest.approx(sav, rel=1e-12)
                w = blk['waterfall_usd_month'][str(y)]
                assert w['BAU'] - w['Shared savings'] == pytest.approx(sav, abs=1e-3)
            yb = blk['yearly']['avg_residential_bill_usd_month']['shared_savings']['total']
            np.testing.assert_allclose(yb, s['avg_bill_total'].values, atol=1e-4)
            assert yb[1] < ex['runs'][pace][sc]['yearly']['avg_residential_bill_usd_month']['shared_savings']['total'][1] + 1e-9
            f = blk['value_flows_m']['undiscounted_nominal']
            assert sum(f['to'].values()) == pytest.approx(sum(f['sources'].values()) + f['program_costs'], rel=1e-9, abs=1e-6)
            assert (f['to']['residential_customers'] + f['to']['business_customers']) / 1e3 == pytest.approx(
                sm['Customer savings ($B, undiscounted nominal)'], rel=1e-9)


@pytest.mark.parametrize('key', list(E.UTILITIES))
def test_export_advance_fast_start_matches_direct_runs(key):
    ex = _export(key)
    uj0, p = E.load_utility(key)
    adv = {**FS, ('mechanism', 'advance_enabled'): True}
    for pace in LY.PACES:
        uj = E.with_pace(uj0, pace)
        cases = [(ex['runs'][pace][sc]['advance_fast_start'], sc, {}) for sc in LY.SCENARIOS]
        cases.append((ex['advance_fast_start_stress'][pace], 'Cautious', {('mechanism', 'advance_sizing_scenario'): 'Central'}))
        for blk, sc, extra in cases:
            run = LY.project_layers(uj, p, scenario=sc, overrides={**adv, **extra})
            s, sm = run['ss'], blk['summary']
            assert sm['advance_size_m_pv3_2026'] == pytest.approx(run['advance']['size_m'], rel=1e-12)
            assert sm['credits_paid_m'] == pytest.approx(s['advance_credit_m'].sum(), rel=1e-12, abs=1e-9)
            assert sm['recoveries_m'] == pytest.approx(s['advance_recovery_m'].sum(), rel=1e-12, abs=1e-9)
            assert sm['balance_2050_m'] == pytest.approx(s['advance_balance_m'].iloc[-1], rel=1e-12, abs=1e-9)
            assert sm['customer_savings_b_undiscounted'] == pytest.approx(
                LY.system_summary(run)['Customer savings ($B, undiscounted nominal)'], rel=1e-12)
            assert sm['worst_year_vs_bau']['exceeds_bau'] is False
            assert sm['credits_paid_m'] + sm['financing_cost_m'] - sm['recoveries_m'] == pytest.approx(sm['balance_2050_m'], abs=1e-3)


@pytest.mark.parametrize('key', list(E.UTILITIES))
def test_program_costs_enter_once(key):
    """With every flexible cost per kW-year and the efficiency levelised cost at zero, customer savings plus
    shared savings earnings rise by exactly the original run's program_costs flow, and every value source
    is unchanged (program costs enter the results once, as the program_costs deduction)."""
    uj0, p = E.load_utility(key)
    zero = {('programs', f'cost_kw_yr_{k}'): 0.0 for k in LY.FLEX_TYPES}
    zero[('programs', 'ee_levelised_cost_kwh')] = 0.0
    for pace in LY.PACES:
        uj = E.with_pace(uj0, pace)
        for sc in LY.SCENARIOS:
            r0 = LY.project_layers(uj, p, scenario=sc)
            r1 = LY.project_layers(uj, p, scenario=sc, overrides=zero)
            f0, f1 = E.value_flows(r0, p), E.value_flows(r1, p)
            for src in E.FLOW_SOURCES:
                np.testing.assert_array_equal(f1[src], f0[src], err_msg=f'{pace} {sc} {src}')
            assert np.abs(f1['program_costs']).max() < 1e-9
            prog0 = f0['program_costs'].sum()
            assert prog0 < 0
            s0, s1 = LY.system_summary(r0), LY.system_summary(r1)
            tot = lambda sm: (sm['Customer savings ($B, undiscounted nominal)']
                              + sm['Shared savings earnings ($B, undiscounted nominal)'])
            assert (tot(s1) - tot(s0)) * 1e3 == pytest.approx(-prog0, rel=1e-9, abs=1e-6)
            assert ((f1['customers'] + f1['earnings']) - (f0['customers'] + f0['earnings'])).sum() == pytest.approx(
                -prog0, rel=1e-12, abs=1e-6)


@pytest.mark.parametrize('key', list(E.UTILITIES))
def test_allocation_sweep_by_sales_matches_export(key):
    """by_sales reproduces the existing export fields exactly (bills, residential / business flows, customer savings)."""
    ex = _export(key)
    for pace in LY.PACES:
        for sc in LY.SCENARIOS:
            blk = ex['runs'][pace][sc]
            al = blk['allocation_sweep']['by_sales']
            y = blk['yearly']['avg_residential_bill_usd_month']
            assert al['yearly']['avg_residential_bill_usd_month']['bau'] == y['bau']['total']
            assert al['yearly']['avg_residential_bill_usd_month']['shared_savings'] == y['shared_savings']['total']
            for basis in ('undiscounted_nominal', 'npv3_2026'):
                to = blk['value_flows_m'][basis]['to']
                assert al['value_flows_m'][basis]['residential']['total'] == to['residential_customers']
                assert al['value_flows_m'][basis]['non_residential']['total'] == to['business_customers']
            assert al['residential_pool_share'] == al['residential_sales_share'] == ex['metadata']['residential_sales_share']
            h = blk['headline']
            assert al['headline']['residential_bill_saving_2035'] == pytest.approx(h['monthly_saving_2035'], abs=1e-12)
            assert al['headline']['residential_bill_saving_2050'] == pytest.approx(h['monthly_saving_2050'], abs=1e-12)
            assert al['headline']['customer_savings_b_undiscounted'] == pytest.approx(h['customer_savings_b_undiscounted'], rel=1e-9)


@pytest.mark.parametrize('key', list(E.UTILITIES))
def test_allocation_totals_same_under_every_option(key):
    """Residential + non-residential = customer savings under every option; load-following parts never move."""
    ex = _export(key)
    for pace in LY.PACES:
        for sc in LY.SCENARIOS:
            sw = ex['runs'][pace][sc]['allocation_sweep']
            cust = np.array(ex['runs'][pace][sc]['yearly']['customer_savings_m'])
            tot = {}
            for opt, al in sw.items():
                yl = al['yearly']
                np.testing.assert_allclose(np.array(yl['residential_savings_m']) + np.array(yl['non_residential_savings_m']),
                                           cust, atol=2e-4, err_msg=f'{pace} {sc} {opt}')
                h = al['headline']
                tot[opt] = h['residential_savings_b_undiscounted'] + h['non_residential_savings_b_undiscounted']
                assert tot[opt] == pytest.approx(h['customer_savings_b_undiscounted'], rel=1e-12)
                for basis, f in al['value_flows_m'].items():
                    t = sum(sum(f[c][g].values()) for c in ('residential', 'non_residential')
                            for g in ('load_following', 'pool_customer_share'))
                    assert t == pytest.approx(f['residential']['total'] + f['non_residential']['total'], rel=1e-9, abs=1e-6)
                    for k, v in f['residential']['load_following'].items():
                        assert v == pytest.approx(sw['by_sales']['value_flows_m'][basis]['residential']['load_following'][k],
                                                  rel=1e-12)
            assert len(set(round(v, 9) for v in tot.values())) == 1
            assert sw['custom']['residential_pool_share'] == 0.5


@pytest.mark.parametrize('key', list(E.UTILITIES))
def test_per_customer_share_equals_customer_counts(key):
    """per_customer: the residential share of the pool equals the residential share of EIA-861 customer counts."""
    uj, p = E.load_utility(key)
    mech = LY.resolve(uj['forward_assumptions'])['mechanism']
    n_r, n_n = mech['residential_customers'], mech['nonresidential_customers']
    share = n_r / (n_r + n_n)
    assert share == pytest.approx(p['residential_customer_share'], abs=5e-5)   # the EIA-861 class shares note
    assert mech['customer_allocation'] == 'by_sales'
    ex = _export(key)
    for pace in LY.PACES:
        for sc in LY.SCENARIOS:
            al = ex['runs'][pace][sc]['allocation_sweep']['per_customer']
            assert al['residential_pool_share'] == share
            f = al['value_flows_m']['undiscounted_nominal']
            for k in E.POOL_PARTS:
                r, n = f['residential']['pool_customer_share'][k], f['non_residential']['pool_customer_share'][k]
                if abs(r + n) > 1e-6:
                    assert r / (r + n) == pytest.approx(share, rel=1e-9)
    run = LY.project_layers(uj, p, scenario='Central')
    with pytest.raises(ValueError):
        LY.customer_allocation(run, p, 'custom', 1.5)
    with pytest.raises(ValueError):
        LY.customer_allocation(run, p, 'other')
    # the engine table: totals equal across options
    t = LY.customer_allocation_table(uj, p, scenarios=('Central',))
    tot = t['Residential ($B, undiscounted nominal)'] + t['Non-residential ($B, undiscounted nominal)']
    assert tot.max() - tot.min() < 1e-9
