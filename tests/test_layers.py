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


@pytest.mark.parametrize('key,nb', UTILS)
def test_program_transfer_is_neutral_without_new_resources(key, nb):
    """Moving today's core programs from surcharges into rates, with no new MW or EE, leaves bills at BAU."""
    uj, p = _utility(key, nb)
    pr = uj['forward_assumptions']['layers']['programs']['params']
    ov = {('programs', 'ee_incremental_savings_pct'): 0.0, ('programs', 'flex_conn_share'): 0.0}
    for k in LY.FLEX_TYPES:
        for y in (2035, 2050):
            ov[('programs', f'mw_{y}_{k}')] = pr[f'mw_start_{k}']['value']
    en = {l: False for l in LY.SAVINGS_LAYERS}
    en['programs'] = True
    r = LY.project_layers(uj, p, overrides=ov, enabled=en)
    np.testing.assert_allclose(r['ss']['bill_total'], r['bau']['bill_total'], rtol=0, atol=1e-9)


@pytest.mark.parametrize('key,nb', UTILS)
def test_flex_spend_is_mw_times_cost(key, nb):
    uj, p = _utility(key, nb)
    r = LY.project_layers(uj, p)
    pr, infl = r['assumptions']['programs'], r['assumptions']['projection']['inflation_rate']
    for t, (_, m) in enumerate(r['mw'].iterrows()):
        expect = sum(m[f'{k}_incremental_mw'] * 1000 * pr[f'cost_kw_yr_{k}'] for k in LY.FLEX_TYPES) \
            * (1 + infl) ** t / 1e6
        got = r['ss']['flex_spend_m'].iloc[t]
        assert got == pytest.approx(expect if m['year'] >= pr['transition_year'] else 0.0)


@pytest.mark.parametrize('key,nb', UTILS)
def test_energy_efficiency_lowers_sales_and_average_bill(key, nb):
    uj, p = _utility(key, nb)
    r = LY.project_layers(uj, p)
    s = r['ss'].set_index('year')
    assert (s.loc[2035, 'ee_gwh'] > 0) and (s.loc[2035, 'residential_usage_index'] < 1)
    assert s.loc[2035, 'avg_bill_total'] < s.loc[2035, 'bill_total']


@pytest.mark.parametrize('key,nb', UTILS)
def test_scenarios_are_ordered(key, nb):
    uj, p = _utility(key, nb)
    cum = [LY.cumulative_savings(LY.project_layers(uj, p, scenario=sc))['undiscounted nominal $']
           for sc in LY.SCENARIOS]
    assert cum[0] < cum[1] < cum[2]


@pytest.mark.parametrize('key,nb', UTILS)
@pytest.mark.parametrize('scenario', LY.SCENARIOS)
def test_headroom_used_never_exceeds_headroom_created(key, nb, scenario):
    """One use per MW of headroom: load enabled + deferral <= created, and used <= created."""
    uj, p = _utility(key, nb)
    for mode in ('derived', 'direct'):
        s = LY.project_layers(uj, p, scenario=scenario, uplift_mode=mode)['ss']
        tol = 1e-9
        assert (s['headroom_enable_mw'] + s['headroom_defer_mw'] <= s['headroom_created_mw'] + tol).all()
        assert (s['headroom_used_mw'] <= s['headroom_created_mw'] + tol).all()
        assert (s['enabled_mw'] <= s['headroom_enable_mw'] + tol).all()


@pytest.mark.parametrize('key,nb', UTILS)
def test_network_served_never_exceeds_demand_or_capacity(key, nb):
    uj, p = _utility(key, nb)
    r = LY.project_layers(uj, p)
    for case in ('bau', 'ss'):
        d = r[case]
        assert (d['served_mw'] <= d['network_demand_mw'] + 1e-9).all()
        assert (d['served_mw'] <= d['network_capacity_mw'] + d['headroom_created_mw'] + 1e-9).all()


_FIXTURE = os.path.join(ROOT, 'tests', 'fixtures', 'layers_single_pool_ebb0c04.json')


@pytest.mark.parametrize('key,nb', UTILS)
def test_one_band_equals_single_pool_model(key, nb):
    """forward_assumptions as at ebb0c04 (no bands, no ramp limit) reproduce that commit's outputs exactly."""
    from engine.report import TIGHT_NETWORK
    fx = json.load(open(_FIXTURE))[key]
    uj, p = _utility(key, nb)
    uj = {**uj, 'forward_assumptions': fx['forward_assumptions']}
    for name, ref in fx['runs'].items():
        r = LY.project_layers(uj, p, scenario=name.replace('_tight', ''),
                              overrides=TIGHT_NETWORK if name.endswith('_tight') else None)
        for col, d in ref.items():
            for case in ('bau', 'ss'):
                np.testing.assert_array_equal(r[case][col].values, np.array(d[case]), err_msg=f'{name} {col} {case}')


@pytest.mark.parametrize('key,nb', UTILS)
def test_bands_sum_to_network_totals(key, nb):
    uj, p = _utility(key, nb)
    r = LY.project_layers(uj, p)
    assert len(r['bands']) > 1
    assert sum(b['load_share'] for b in r['bands']) == pytest.approx(1.0)
    for case in ('bau', 'ss'):
        g = r['band_detail'][case].groupby('year')[['demand_mw', 'capacity_mw', 'waiting_mw', 'headroom_mw']].sum()
        d = r[case].set_index('year')
        np.testing.assert_allclose(g['demand_mw'], d['network_demand_mw'], rtol=1e-12)
        np.testing.assert_allclose(g['capacity_mw'], d['network_capacity_mw'], rtol=1e-12)
        np.testing.assert_allclose(g['waiting_mw'], d['waiting_mw'], rtol=1e-9, atol=1e-9)
        np.testing.assert_allclose(g['headroom_mw'], d['headroom_created_mw'], rtol=1e-12, atol=1e-12)


@pytest.mark.parametrize('key,nb', UTILS)
def test_ramp_limit_respected(key, nb):
    uj, p = _utility(key, nb)
    r = LY.project_layers(uj, p)
    pr, P0 = r['assumptions']['programs'], p['peak_demand_mw']
    m = r['mw']
    for k in LY.FLEX_TYPES:
        cap = pr[f'ramp_pct_peak_{k}'] * r['system']['peak_mw'].iloc[0]
        assert (np.diff(m[f'{k}_ss_mw'].values) <= cap + 1e-9).all()
    free = LY.project_layers(uj, p, overrides=LY.no_ramp_overrides())['mw']
    for k in LY.FLEX_TYPES:
        assert (m[f'{k}_ss_mw'] <= free[f'{k}_ss_mw'] + 1e-9).all()


@pytest.mark.parametrize('key,nb', UTILS)
def test_access_zero_with_layers_off(key, nb):
    uj, p = _utility(key, nb)
    r = LY.project_layers(uj, p, enabled={l: False for l in LY.SAVINGS_LAYERS})
    a = LY.access_summary(r)
    assert a['Total delay avoided (MW-years)'] == 0
    assert a['Connection cost avoided by new customers ($M, undiscounted nominal)'] == 0


# ── Network block: defaults, sub-band, override order ─────────────────────────

_FIXTURE_1B09 = os.path.join(ROOT, 'tests', 'fixtures', 'layers_1b09e20.json')
SUBBAND_ON = {'subband_enabled': True, 'flex_targeting_enabled': True}


@pytest.mark.parametrize('key,nb', UTILS)
@pytest.mark.parametrize('source', ['current_json', 'legacy_json'])
def test_network_defaults_reproduce_1b09e20(key, nb, source):
    """Network block at its defaults (current JSON), and the 1b09e20 JSON without one, reproduce 1b09e20 exactly."""
    from engine.report import TIGHT_NETWORK
    fx = json.load(open(_FIXTURE_1B09))[key]
    uj, p = _utility(key, nb)
    if source == 'legacy_json':
        uj = {**uj, 'forward_assumptions': fx['forward_assumptions']}
    for name, ref in fx['runs'].items():
        r = LY.project_layers(uj, p, scenario=name.replace('_tight', ''),
                              overrides=TIGHT_NETWORK if name.endswith('_tight') else None)
        for col, d in ref.items():
            for case in ('bau', 'ss'):
                np.testing.assert_array_equal(r[case][col].values, np.array(d[case]), err_msg=f'{name} {col} {case}')


@pytest.mark.parametrize('key,nb', UTILS)
@pytest.mark.parametrize('scenario', LY.SCENARIOS)
def test_headroom_used_never_exceeds_created_with_subband(key, nb, scenario):
    uj, p = _utility(key, nb)
    for nw in (SUBBAND_ON, {**SUBBAND_ON, 'subband_load_share': 0.15, 'mean_utilisation': 0.95}):
        s = LY.project_layers(uj, p, scenario=scenario, network=nw)['ss']
        tol = 1e-9
        assert (s['headroom_enable_mw'] + s['headroom_defer_mw'] <= s['headroom_created_mw'] + tol).all()
        assert (s['headroom_used_mw'] <= s['headroom_created_mw'] + tol).all()
        # where BAU leaves load waiting, efficiency also frees capacity for it
        assert (s['enabled_mw'] <= s['headroom_enable_mw'] + s['ee_mw'] + tol).all()


@pytest.mark.parametrize('key,nb', UTILS)
def test_served_never_exceeds_operating_limit(key, nb):
    uj, p = _utility(key, nb)
    for nw in (SUBBAND_ON, {**SUBBAND_ON, 'subband_load_share': 0.15, 'subband_utilisation': 1.3}):
        r = LY.project_layers(uj, p, network=nw)
        for case in ('bau', 'ss'):
            d = r['band_detail'][case]
            assert (d['served_mw'] <= d['operating_limit_mw'] + d['headroom_mw'] + 1e-9).all()
            assert (d['served_mw'] <= d['demand_mw'] + 1e-9).all()
        # utilisation above the operating limit: existing load is served up to the
        # operating limit on 2026 starting capacity; the excess waits from 2026
        b = r['band_detail']['bau']
        b0 = b[(b['year'] == 2026) & (b['band'] == 'Above planning limit')].iloc[0]
        sub = r['bands'][0]
        if nw.get('subband_utilisation', 1.125) > r['operating_limit']:
            assert b0['served_mw'] == pytest.approx(r['operating_limit'] * sub['C0'])
            assert b0['waiting_mw'] > 0


def test_full_utilisation_long_lead_gives_bau_queue():
    uj, p = _utility('DomVA', 'GridDividend_Virginia.ipynb')
    base = LY.project_layers(uj, p)
    assert base['bau']['waiting_mw'].max() == 0
    r = LY.project_layers(uj, p, network={'mean_utilisation': 1.0, 'reinforcement_lead_years': 'high'})
    assert r['bau']['waiting_mw'].max() > 0
    assert all(b['loading0'] == pytest.approx(1.0) for b in r['bands'])


@pytest.mark.parametrize('key,nb', UTILS)
def test_subband_gives_bau_queue_and_keeps_totals(key, nb):
    """Sub-band: load above the planning limit at 2026, new load waits in BAU; total load and capacity unchanged."""
    uj, p = _utility(key, nb)
    off, on = LY.project_layers(uj, p), LY.project_layers(uj, p, network={'subband_enabled': True})
    sub = on['bands'][0]
    assert sub['name'] == 'Above planning limit' and sub['load_share'] == pytest.approx(0.043)
    assert sub['loading0'] == pytest.approx(1.125)
    assert sum(b['load_share'] for b in on['bands']) == pytest.approx(1.0)
    assert sum(b['C0'] for b in on['bands']) == pytest.approx(sum(b['C0'] for b in off['bands']))
    assert on['bau']['above_planning_limit_mw'].iloc[0] > 0
    assert on['bau']['waiting_mw'].max() > 0
    assert LY.access_summary(on)['Total delay avoided (MW-years)'] > 0


@pytest.mark.parametrize('mean', [0.6, 0.75, 0.9, 1.0])
def test_mean_utilisation_shift(mean):
    uj, p = _utility('ConEd', 'GridDividend_NewYork.ipynb')
    for mode in ('explicit', 'generated'):
        bands = LY.project_layers(uj, p, network={'mean_utilisation': mean, 'band_mode': mode})['bands']
        cw = sum(b['capacity_share'] * b['loading0'] for b in bands) / sum(b['capacity_share'] for b in bands)
        assert cw == pytest.approx(mean, abs=1e-9)
        assert max(b['loading0'] for b in bands) <= 1.0 + 1e-12


def test_network_override_order():
    """JSON < scenario network values < notebook NETWORK_OVERRIDES < per-call network."""
    import copy
    uj, p = _utility('ConEd', 'GridDividend_NewYork.ipynb')
    uj = copy.deepcopy(uj)
    fa = uj['forward_assumptions']
    get = lambda **kw: LY.resolve(fa, **kw)['network']['reinforcement_lead_years']
    assert get() == 3
    fa['scenarios']['Ambitious']['network'] = {'reinforcement_lead_years': 'low'}
    fa['scenarios']['Central']['network'] = {'reinforcement_lead_years': 4}
    assert get(scenario='Ambitious') == 2 and get(scenario='Central') == 4 and get(scenario='Cautious') == 3
    try:
        LY.NETWORK_OVERRIDES.update({'reinforcement_lead_years': 6})
        assert get(scenario='Ambitious') == 6
        assert get(scenario='Ambitious', network={'reinforcement_lead_years': 7}) == 7
    finally:
        LY.NETWORK_OVERRIDES.clear()
    assert get(scenario='Ambitious') == 2


def test_headroom_sweep_grid():
    uj, p = _utility('DomVA', 'GridDividend_Virginia.ipynb')
    sw = LY.headroom_sweep(uj, p, means=(0.7, 0.8), shares=(0.0, 0.043))
    assert len(sw) == 4
    zero = sw[sw['sub-band share'] == 0]
    assert (zero['Delay avoided (MW-years)'] == 0).all()
    assert (sw[sw['sub-band share'] > 0]['Delay avoided (MW-years)'] > 0).all()
