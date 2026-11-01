# tests/test_export.py
# The web-explorer exports (exports/<utility>.json, scripts/export_results.py):
# value flows balance, and totals match the headline figures the model reports now.

import json
import os
import sys

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
