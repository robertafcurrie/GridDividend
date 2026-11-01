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


def test_placeholder_layers_cannot_be_enabled():
    """Older forward_assumptions carry wholesale_energy and roe as placeholders (hook: true)."""
    uj, p = _utility('ConEd', 'GridDividend_NewYork.ipynb')
    legacy = json.load(open(os.path.join(ROOT, 'tests', 'fixtures', 'layers_1b09e20.json')))['ConEd']
    uj = {**uj, 'forward_assumptions': legacy['forward_assumptions']}
    with pytest.raises(NotImplementedError):
        LY.project_layers(uj, p, enabled={'roe': True})


@pytest.mark.parametrize('key,nb', UTILS)
def test_program_transfer_is_neutral_without_new_resources(key, nb):
    """
    Moving today's core programs from surcharges into rates, with no new MW or EE, leaves bills at BAU.
    Checked with no load waiting (sub-band off): in shared savings core programs are recovered per kWh
    served, so load waiting for an upgrade raises the per-kWh rider slightly, while the BAU surcharge does
    not depend on served kWh.
    """
    uj, p = _utility(key, nb)
    pr = uj['forward_assumptions']['layers']['programs']['params']
    ov = {('programs', 'ee_incremental_savings_pct'): 0.0, ('programs', 'flex_conn_share'): 0.0}
    for k in LY.FLEX_TYPES:
        for y in (2035, 2050):
            ov[('programs', f'mw_{y}_{k}')] = pr[f'mw_start_{k}']['value']
    en = {l: False for l in LY.SAVINGS_LAYERS}
    en['programs'] = True
    r = LY.project_layers(uj, p, overrides=ov, enabled=en, network={'subband_enabled': False})
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
        # only load-enabled headroom connects load sooner (efficiency is not counted)
        assert (s['enabled_mw'] <= s['headroom_enable_mw'] + tol).all()


@pytest.mark.parametrize('key,nb', UTILS)
def test_network_served_never_exceeds_demand_or_capacity(key, nb):
    uj, p = _utility(key, nb)
    r = LY.project_layers(uj, p)
    for case in ('bau', 'ss'):
        d = r[case]
        assert (d['served_mw'] <= d['network_demand_mw'] + 1e-9).all()
        # existing load above the planning limit is served up to the operating limit
        assert (d['served_mw'] <= r['operating_limit'] * d['network_capacity_mw'] + d['headroom_created_mw'] + 1e-9).all()


_FIXTURE = os.path.join(ROOT, 'tests', 'fixtures', 'layers_single_pool_ebb0c04.json')
# Columns renamed since the fixtures were written (values unchanged)
RENAMED = {'waiting_mw': 'upgrade_wait_mw', 'delay_mw_yr_avoided': 'upgrade_delay_mw_yr_avoided'}
# Shared-savings columns the code fixes after 50a3f96 change on purpose (efficiency counted once in
# capacity; MW connected sooner = served above BAU, so efficiency is not counted and flexible
# connections are not credited twice); each fix has its own test below. BAU and every other column
# must still reproduce the fixtures exactly.
FIXED_SS = {'capacity_cost_m', 'avg_bill_total', 'bill_total', 'rr_m', 'shared_savings_earnings_m',
            'connection_cost_avoided_m', 'enabled_mw'}
# Current-JSON data changed after 50a3f96: Pepco's capacity price aligned with its carve-out (moves
# its capacity line in both cases) and Dominion's demand-response path without embedded efficiency
# (moves its whole shared-savings case)
DATA_CHANGED = {'PepcoMD': {'bau': {'capacity_cost_m', 'avg_bill_total', 'bill_total', 'rr_m'}, 'ss': 'all'},
                'DomVA': {'bau': set(), 'ss': 'all'}}


def _compare_fixture(r, ref, name, skip=None):
    skip = skip or {}
    for col, d in ref.items():
        for case in ('bau', 'ss'):
            sk = skip.get(case, set())
            if sk == 'all' or col in sk or (case == 'ss' and col in FIXED_SS):
                continue
            np.testing.assert_array_equal(r[case][RENAMED.get(col, col)].values, np.array(d[case]),
                                          err_msg=f'{name} {col} {case}')


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
        _compare_fixture(r, ref, name)


@pytest.mark.parametrize('key,nb', UTILS)
def test_bands_sum_to_network_totals(key, nb):
    uj, p = _utility(key, nb)
    r = LY.project_layers(uj, p)
    assert len(r['bands']) > 1
    assert sum(b['load_share'] for b in r['bands']) == pytest.approx(1.0)
    for case in ('bau', 'ss'):
        g = r['band_detail'][case].groupby('year')[['demand_mw', 'capacity_mw', 'upgrade_wait_mw', 'headroom_mw']].sum()
        d = r[case].set_index('year')
        np.testing.assert_allclose(g['demand_mw'], d['network_demand_mw'], rtol=1e-12)
        np.testing.assert_allclose(g['capacity_mw'], d['network_capacity_mw'], rtol=1e-12)
        np.testing.assert_allclose(g['upgrade_wait_mw'], d['upgrade_wait_mw'], rtol=1e-9, atol=1e-9)
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
    assert a[f'{LY.UD} avoided (MW-years)'] == 0
    assert a['Connection cost avoided by new customers ($M, undiscounted nominal)'] == 0


# ── Network block: defaults, sub-band, override order ─────────────────────────

_FIXTURE_1B09 = os.path.join(ROOT, 'tests', 'fixtures', 'layers_1b09e20.json')
NEW_LAYERS_OFF = {'wholesale_energy': False, 'transmission': False, 'losses': False, 'roe': False}
MODEL_BAU = {('bau_plan', 'basis'): 'model',          # the BAU basis before published-plan BAU,
             ('bau_plan', 'electrification_pace'): 'state_policy'}   # with uncalibrated load
# Data changed after 7c9b6e6: Con Edison's layered data-centre growth (central 0%, was 6%); the
# pinned-output tests run the current JSON with the earlier value so they still reproduce exactly
# and RG&E's (central = NYISO Gold Book Zone B large loads, was 5%) after 94992aa
DATA_SINCE_7C9B = {'ConEd': {('system_needs', 'dc_growth'): 0.06}, 'RGE': {('system_needs', 'dc_growth'): 0.05}}
PLAN_FIXED = {('bau_plan', 'link_growth_to_load'): False}   # plan capex fixed regardless of load
SUBBAND_ON = {'subband_enabled': True, 'flex_targeting_enabled': True}


@pytest.mark.parametrize('key,nb', UTILS)
@pytest.mark.parametrize('source', ['current_json', 'legacy_json'])
def test_network_defaults_reproduce_1b09e20(key, nb, source):
    """
    The 1b09e20 JSON (no network block) reproduces 1b09e20 exactly, and so does
    the current JSON with the constrained sub-band switched off and the
    value-stream and ROE layers (added since) disabled.
    """
    from engine.report import TIGHT_NETWORK
    fx = json.load(open(_FIXTURE_1B09))[key]
    uj, p = _utility(key, nb)
    if source == 'legacy_json':
        uj = {**uj, 'forward_assumptions': fx['forward_assumptions']}
    for name, ref in fx['runs'].items():
        scn = name.replace('_tight', '')
        cur = source == 'current_json'
        ov = dict(TIGHT_NETWORK) if name.endswith('_tight') else {}
        if cur:
            ov.update(MODEL_BAU)
            ov.update(DATA_SINCE_7C9B.get(key, {}))
        r = LY.project_layers(uj, p, scenario=scn, overrides=ov or None,
                              network={'subband_enabled': False} if cur else None,
                              enabled=NEW_LAYERS_OFF if cur else None)
        _compare_fixture(r, ref, name, DATA_CHANGED.get(key) if cur else None)


@pytest.mark.parametrize('key,nb', UTILS)
@pytest.mark.parametrize('scenario', LY.SCENARIOS)
def test_headroom_used_never_exceeds_created_with_subband(key, nb, scenario):
    uj, p = _utility(key, nb)
    for nw in (SUBBAND_ON, {**SUBBAND_ON, 'subband_load_share': 0.15, 'mean_utilisation': 0.95}):
        s = LY.project_layers(uj, p, scenario=scenario, network=nw)['ss']
        tol = 1e-9
        assert (s['headroom_enable_mw'] + s['headroom_defer_mw'] <= s['headroom_created_mw'] + tol).all()
        assert (s['headroom_used_mw'] <= s['headroom_created_mw'] + tol).all()
        # only load-enabled headroom connects load sooner (efficiency is not counted)
        assert (s['enabled_mw'] <= s['headroom_enable_mw'] + tol).all()


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
            assert b0['upgrade_wait_mw'] > 0


def test_full_utilisation_long_lead_gives_bau_queue():
    # network mechanism under state-policy load growth (the calibrated utility-forecast load is slower)
    uj, p = _utility('DomVA', 'GridDividend_Virginia.ipynb')
    sp = {('bau_plan', 'electrification_pace'): 'state_policy'}
    base = LY.project_layers(uj, p, network={'subband_enabled': False}, overrides=sp)
    assert base['bau']['upgrade_wait_mw'].max() == 0
    r = LY.project_layers(uj, p, network={'subband_enabled': False, 'mean_utilisation': 1.0,
                                          'reinforcement_lead_years': 'high'}, overrides=sp)
    assert r['bau']['upgrade_wait_mw'].max() > 0
    assert all(b['loading0'] == pytest.approx(1.0) for b in r['bands'])


@pytest.mark.parametrize('key,nb', UTILS)
def test_subband_gives_bau_queue_and_keeps_totals(key, nb):
    """Sub-band: load above the planning limit at 2026, new load waits in BAU; total load and capacity unchanged."""
    uj, p = _utility(key, nb)
    off = LY.project_layers(uj, p, network={'subband_enabled': False})
    on = LY.project_layers(uj, p, network={'subband_enabled': True})
    sub = on['bands'][0]
    assert sub['name'] == 'Above planning limit' and sub['load_share'] == pytest.approx(0.043)
    assert sub['loading0'] == pytest.approx(1.125)
    assert sum(b['load_share'] for b in on['bands']) == pytest.approx(1.0)
    assert sum(b['C0'] for b in on['bands']) == pytest.approx(sum(b['C0'] for b in off['bands']))
    assert on['bau']['above_planning_limit_mw'].iloc[0] > 0
    assert on['bau']['upgrade_wait_mw'].max() > 0
    assert LY.access_summary(on)[f'{LY.UD} avoided (MW-years)'] > 0


@pytest.mark.parametrize('mean', [0.6, 0.75, 0.9, 1.0])
def test_mean_utilisation_shift(mean):
    uj, p = _utility('ConEd', 'GridDividend_NewYork.ipynb')
    for mode in ('explicit', 'generated'):
        bands = LY.project_layers(uj, p, network={'mean_utilisation': mean, 'band_mode': mode})['bands']
        cw = sum(b['capacity_share'] * b['loading0'] for b in bands) / sum(b['capacity_share'] for b in bands)
        assert cw == pytest.approx(mean, abs=1e-9)
        assert max(b['loading0'] for b in bands if not b['subband']) <= 1.0 + 1e-12


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
    col = f'{LY.UD} avoided (MW-years)'
    assert len(sw) == 4 * len(LY.DELAY_CASES)
    zero = sw[sw['sub-band share'] == 0]
    assert (zero[col] == 0).all()
    assert (sw[sw['sub-band share'] > 0][col] > 0).all()
    c = sw[(sw['sub-band share'] > 0) & (sw['mean utilisation'] == 0.8)].set_index('delay case')[col]
    assert c['short'] < c['central'] < c['long']


# ── Upgrade Delay for Interconnection ─────────────────────────────────────────

@pytest.mark.parametrize('key,nb', UTILS)
def test_subband_on_in_every_scenario_and_switchable(key, nb):
    import copy
    uj, p = _utility(key, nb)
    for sc in (None,) + LY.SCENARIOS:
        r = LY.project_layers(uj, p, scenario=sc)
        assert any(b['subband'] for b in r['bands'])
        assert r['bau']['upgrade_wait_mw'].max() > 0
    uj2 = copy.deepcopy(uj)
    uj2['forward_assumptions']['scenarios']['Cautious']['network'] = {'subband_enabled': False}
    assert not any(b['subband'] for b in LY.project_layers(uj2, p, scenario='Cautious')['bands'])
    assert any(b['subband'] for b in LY.project_layers(uj2, p, scenario='Central')['bands'])
    assert not any(b['subband'] for b in LY.project_layers(uj, p, network={'subband_enabled': False})['bands'])


@pytest.mark.parametrize('key,nb', UTILS)
def test_upgrade_delay_mw_years_identity(key, nb):
    """MW-years by request year (first in, first out) = sum of MW waiting over the years; avoided = BAU - SS."""
    uj, p = _utility(key, nb)
    for nw in (None, {'subband_load_share': 0.15, 'flex_targeting_enabled': True}):
        r = LY.project_layers(uj, p, network=nw)
        for case in ('bau', 'ss'):
            d = r[case]
            assert d['upgrade_delay_mw_yr'].sum() == pytest.approx(d['upgrade_wait_mw'].sum(), rel=1e-9, abs=1e-6)
        assert r['ss']['upgrade_delay_mw_yr_avoided'].sum() == pytest.approx(
            r['bau']['upgrade_delay_mw_yr'].sum() - r['ss']['upgrade_delay_mw_yr'].sum(), rel=1e-9, abs=1e-6)


def test_upgrade_delay_inputs_drive_the_wait():
    """With the backlog cleared at once, BAU waits never exceed the upgrade delay; longer delays and slower clearance wait longer."""
    uj, p = _utility('DomVA', 'GridDividend_Virginia.ipynb')
    run = lambda **nw: LY.project_layers(uj, p, network=nw)
    r = run(upgrade_delay_ordinary_years=2, upgrade_delay_large_years=2, backlog_clearance_pct=1.0)
    b = r['bau']
    later = b[(b['year'] >= 2028) & (b['year'] <= 2045) & (b['upgrade_delay_mw_affected'] > 0)]
    assert len(later) > 0 and (later['upgrade_delay_yr'] <= 2.0 + 1e-9).all() and (later['upgrade_delay_yr'] > 0).all()
    mwyr = lambda r_: r_['bau']['upgrade_delay_mw_yr'].sum()
    assert mwyr(run(upgrade_delay_ordinary_years='low', upgrade_delay_large_years='low')) < mwyr(run()) < \
        mwyr(run(upgrade_delay_ordinary_years='high', upgrade_delay_large_years='high'))
    above = lambda r_: r_['bau']['above_planning_limit_mw'].sum()
    assert above(run(backlog_clearance_pct='high')) < above(run()) < above(run(backlog_clearance_pct='low'))
    assert mwyr(run(constrained_build_priority=False)) >= mwyr(run()) - 1e-9


@pytest.mark.parametrize('key,nb', UTILS)
@pytest.mark.parametrize('scenario', LY.SCENARIOS)
def test_flexibility_never_lengthens_upgrade_delay(key, nb, scenario):
    uj, p = _utility(key, nb)
    r = LY.project_layers(uj, p, scenario=scenario, network={'subband_enabled': True})
    assert r['ss']['upgrade_delay_mw_yr'].sum() <= r['bau']['upgrade_delay_mw_yr'].sum() + 1e-9
    assert r['ss']['upgrade_delay_mw_affected'].sum() <= r['bau']['upgrade_delay_mw_affected'].sum() + 1e-9


# ── Value-stream and ROE layers ───────────────────────────────────────────────

@pytest.mark.parametrize('key,nb', UTILS)
def test_value_layers_add_savings_and_sum(key, nb):
    """Each value layer adds customer savings; the waterfall and the contributions sum to the full case."""
    uj, p = _utility(key, nb)
    lc = LY.layer_contributions(uj, p)
    for l in LY.VALUE_LAYERS:
        assert lc.loc[l, 'Customer savings ($B, undiscounted nominal)'] > 0
        assert lc.loc[l, 'Monthly bill 2050 ($, nominal)'] < 0
    full = LY.project_layers(uj, p)
    sm = LY.system_summary(full)
    assert lc['Customer savings ($B, undiscounted nominal)'].sum() == pytest.approx(
        sm['Customer savings ($B, undiscounted nominal)'], abs=1e-9)
    assert lc['Shared savings earnings attributable ($B, undiscounted nominal)'].sum() == pytest.approx(
        sm['Shared savings earnings ($B, undiscounted nominal)'], abs=1e-9)
    wf = LY.waterfall(uj, p, years=(2050,)).iloc[0]
    assert wf['BAU'] + wf.drop(['BAU', 'Shared savings']).sum() == pytest.approx(wf['Shared savings'], abs=1e-9)


@pytest.mark.parametrize('key,nb', UTILS)
def test_wholesale_counts_only_load_shifting(key, nb):
    """No incremental flexible MW -> no wholesale value, even with energy efficiency (already counted)."""
    uj, p = _utility(key, nb)
    pr = uj['forward_assumptions']['layers']['programs']['params']
    ov = {('programs', f'mw_{y}_{k}'): pr[f'mw_start_{k}']['value'] for k in LY.FLEX_TYPES for y in (2035, 2050)}
    s = LY.project_layers(uj, p, overrides=ov)['ss']
    assert (s['ee_gwh'] > 0).any() and (s['wholesale_value_m'] == 0).all()


@pytest.mark.parametrize('key,nb', UTILS)
def test_losses_energy_value_only_above_average(key, nb):
    uj, p = _utility(key, nb)
    s = LY.project_layers(uj, p, overrides={('losses', 'marginal_mult_energy'): 1.0})['ss']
    assert (s['losses_energy_value_m'] == 0).all() and (s['losses_peak_value_m'] > 0).any()


@pytest.mark.parametrize('key,nb', UTILS)
def test_roe_lever(key, nb):
    """ROE +delta raises the shared-savings bill and equity return; shared savings earnings unchanged (outside the pool)."""
    uj, p = _utility(key, nb)
    c = LY.project_layers(uj, p)
    hi = LY.project_layers(uj, p, overrides={('roe', 'roe_delta'): 'high'})
    lo = LY.project_layers(uj, p, overrides={('roe', 'roe_delta'): 'low'})
    np.testing.assert_array_equal(c['ss']['avg_bill_total'].values,
                                  LY.project_layers(uj, p, enabled={'roe': False})['ss']['avg_bill_total'].values)
    assert hi['ss']['avg_bill_total'].iloc[-1] > c['ss']['avg_bill_total'].iloc[-1] > lo['ss']['avg_bill_total'].iloc[-1]
    assert hi['ss']['equity_return_m'].sum() > c['ss']['equity_return_m'].sum() > lo['ss']['equity_return_m'].sum()
    np.testing.assert_allclose(hi['ss']['shared_savings_earnings_m'], c['ss']['shared_savings_earnings_m'], atol=1e-9)
    np.testing.assert_array_equal(hi['bau']['avg_bill_total'].values, c['bau']['avg_bill_total'].values)


def test_transmission_bill_basis():
    """New York: avoided transmission lowers the delivery bill; PJM: it lowers the transmission lines."""
    off = {'transmission': False}
    for key, nb, cat in (('ConEd', 'GridDividend_NewYork.ipynb', 'avg_bill_distribution_base'),
                         ('DomVA', 'GridDividend_Virginia.ipynb', 'avg_bill_transmission')):
        uj, p = _utility(key, nb)
        on_, off_ = LY.project_layers(uj, p)['ss'], LY.project_layers(uj, p, enabled=off)['ss']
        assert on_[cat].iloc[-1] < off_[cat].iloc[-1]


# ── Code fixes after 50a3f96 (independent documentation check) ────────────────

@pytest.mark.parametrize('key,nb', UTILS)
def test_efficiency_counted_once_in_capacity(key, nb):
    """Capacity MW = peak - waiting - firm flexible MW - EE MW (layer on); peak - waiting (layer off)."""
    uj, p = _utility(key, nb)
    for on in (True, False):
        s = LY.project_layers(uj, p, enabled={'capacity': on})['ss']
        red = (s['firm_flex_mw'] + s['ee_mw']) if on else 0.0
        mw = s['peak_mw'] - s['upgrade_wait_mw'] - red
        np.testing.assert_allclose(s['capacity_cost_m'], mw * s['capacity_price_m_per_mw_yr'], rtol=1e-9)
        assert (s['ee_mw'] > 0).any()


def test_dominion_demand_response_excludes_efficiency():
    """Dominion's IRP DSM MW (EE + DR) less EE at ee_kw_per_mwh: 341 MW (2025) and 1,076 MW (2030)."""
    uj, _ = _utility('DomVA', 'GridDividend_Virginia.ipynb')
    pr = uj['forward_assumptions']['layers']['programs']['params']
    k = pr['ee_kw_per_mwh']['central']
    assert pr['mw_start_dr']['value'] == pytest.approx(341 - 1462 * k, abs=0.05)
    assert pr['mw_2035_dr']['central'] == pytest.approx(1076 - 3011 * k, abs=0.05)


@pytest.mark.parametrize('key,nb', UTILS)
def test_flexible_connections_counted_once(key, nb):
    """Connection cost avoided credits only MW connected sooner, never flexible-connection MW (already headroom)."""
    uj, p = _utility(key, nb)
    r = LY.project_layers(uj, p)
    s, a = r['ss'], r['assumptions']
    t = s['year'].values - 2026
    new = np.diff(np.maximum.accumulate(s['enabled_mw'].values), prepend=0.0)
    exp = (new * a['system_needs']['dist_upgrade_cost_per_mw'] * a['load_enabled']['customer_funded_share']
           * (1 + a['projection']['inflation_rate']) ** t)
    np.testing.assert_allclose(s['connection_cost_avoided_m'], exp, rtol=1e-9, atol=1e-9)
    off = LY.project_layers(uj, p, enabled={'deferral': False, 'load_enabled': False})['ss']
    assert (off['flex_conn_mw'] > 0).any()
    assert off['connection_cost_avoided_m'].abs().sum() == 0


@pytest.mark.parametrize('key,nb', UTILS)
def test_earnings_attributed_in_proportion_to_pool(key, nb):
    uj, p = _utility(key, nb)
    lc = LY.layer_contributions(uj, p)
    full = LY.project_layers(uj, p)['ss']['shared_savings_earnings_m'].sum() / 1e3
    for basis in ('undiscounted nominal', 'NPV 3%, 2026 $'):
        attr = lc[f'Shared savings earnings attributable ($B, {basis})']
        pool = lc[f'Savings pool contribution ($B, {basis})']
        np.testing.assert_allclose(attr.values, (pool / pool.sum() * attr.sum()).values, rtol=1e-9, atol=1e-12)
    assert lc['Shared savings earnings attributable ($B, undiscounted nominal)'].sum() == pytest.approx(full, rel=1e-9)
    # deferral lowers what customers pay, so it now earns a positive share
    assert lc.loc['deferral', 'Shared savings earnings attributable ($B, undiscounted nominal)'] > 0


@pytest.mark.parametrize('key,nb', UTILS)
def test_efficiency_not_counted_as_connected_sooner(key, nb):
    """With deferral and load enabled off, efficiency connects nobody and is charged no connection cost."""
    uj, p = _utility(key, nb)
    s = LY.project_layers(uj, p, enabled={'deferral': False, 'load_enabled': False})['ss']
    assert (s['ee_mw'] > 0).any()
    for col in ('enabled_mw', 'conn_capex_m', 'connection_cost_avoided_m', 'electrification_gwh_brought_forward'):
        assert s[col].abs().sum() == 0, col


def test_capex_pool_basis_removed():
    uj, p = _utility('ConEd', 'GridDividend_NewYork.ipynb')
    with pytest.raises(TypeError):
        LY.project_layers(uj, p, pool_basis='capex')
    fa = json.loads(json.dumps(uj['forward_assumptions']))
    fa['layers']['mechanism']['params']['pool_basis']['value'] = 'capex'
    with pytest.raises(ValueError):
        LY.project_layers({**uj, 'forward_assumptions': fa}, p)
    assert 'customer_credit_m' not in LY.project_layers(uj, p)['ss'].columns


@pytest.mark.parametrize('key,nb', UTILS)
def test_settings_are_labelled_setting(key, nb):
    """Every forward_assumptions input whose source says it is a setting carries status 'setting'."""
    uj, _ = _utility(key, nb)
    fa = uj['forward_assumptions']
    groups = [fa['projection'], fa['network']['params']] + [l.get('params', {}) for l in fa['layers'].values()]
    wrong = [n for g in groups for n, sp in g.items()
             if isinstance(sp, dict) and str(sp.get('source', '')).startswith('Setting') and sp.get('status') != 'setting']
    assert not wrong, wrong
    for n in ('transition_year', 'existing_capitalised'):
        assert fa['layers']['programs']['params'][n]['status'] == 'setting'


def test_pepco_capacity_prices_aligned():
    """Pepco's carve-out and capacity layer start from the same year-zero price ($/MW-day x 365 / 1e6)."""
    uj, _ = _utility('PepcoMD', 'GridDividend_Maryland.ipynb')
    fa = uj['forward_assumptions']
    layer = fa['layers']['capacity']['params']['price_m_per_mw_yr']['value']
    assert layer == pytest.approx(fa['capacity_carve_out']['price_usd_per_mw_day'] * 365 / 1e6, rel=1e-6)


# ── Published-plan BAU ────────────────────────────────────────────────────────

_FIXTURE_23FE = os.path.join(ROOT, 'tests', 'fixtures', 'layers_23fec60_model_bau.json')


@pytest.mark.parametrize('key,nb', UTILS)
def test_model_bau_basis_reproduces_23fec60(key, nb):
    """With bau_plan.basis = 'model' the current JSON reproduces the layered outputs at 23fec60 exactly."""
    ref = json.load(open(_FIXTURE_23FE))['runs'][key]
    uj, p = _utility(key, nb)
    for sc, cols in ref.items():
        r = LY.project_layers(uj, p, scenario=sc, overrides={**MODEL_BAU, **DATA_SINCE_7C9B.get(key, {})})
        for col, d in cols.items():
            for case in ('bau', 'ss'):
                exp = np.array([np.nan if v is None else v for v in d[case]], float)
                np.testing.assert_array_equal(r[case][col].values, exp, err_msg=f'{sc} {col} {case}')


@pytest.mark.parametrize('key,nb', UTILS)
def test_published_plan_capex_and_beyond_paths(key, nb):
    """BAU capex = the published plan in plan years; beyond it, the three paths behave as specified."""
    uj, p = _utility(key, nb)
    bp = uj['forward_assumptions']['bau_plan']['params']
    yrs, plan = bp['plan_years']['value'], bp['plan_dist_capex_m']['value']
    b = LY.project_layers(uj, p, overrides=PLAN_FIXED)['bau'].set_index('year')
    np.testing.assert_allclose(b.loc[yrs, 'capex_m'].values, plan, rtol=1e-12)
    np.testing.assert_allclose(b.loc[yrs, 'plan_capex_m'].values, plan, rtol=1e-12)
    runs = {path: LY.project_layers(uj, p, overrides={**PLAN_FIXED, ('bau_plan', 'beyond_path'): path})['bau'].set_index('year')
            for path in LY.BEYOND_PATHS}
    g_plan = (bp['plan_cagr_override']['value'] if 'plan_cagr_override' in bp
              else (plan[-1] / plan[0]) ** (1 / (len(plan) - 1)) - 1)
    c = runs['continue']['capex_m']
    np.testing.assert_allclose(c.loc[2050] / c.loc[yrs[-1]], (1 + g_plan) ** (2050 - yrs[-1]), rtol=1e-9)
    # taper: after taper_year capex grows with nominal network peak growth, like the policy path's formula
    infl = uj['forward_assumptions']['projection']['inflation_rate']['value']
    tp, dn = runs['taper'], b['network_demand_mw']
    ty = bp['taper_year']['central']
    sysdf = LY.project_layers(uj, p, overrides=PLAN_FIXED)['system'].set_index('year')['net_peak_mw']
    for y in (ty + 1, 2050):
        assert tp.loc[y, 'capex_m'] / tp.loc[y - 1, 'capex_m'] == pytest.approx(sysdf.loc[y] / sysdf.loc[y - 1] * (1 + infl), rel=1e-9)
    # policy: from the first year after the plan, nominal network peak growth with electrification at high
    run = LY.project_layers(uj, p, overrides=PLAN_FIXED)
    a_hi = {**run['assumptions'], 'system_needs': {**run['assumptions']['system_needs'],
            'electrification_growth': uj['forward_assumptions']['layers']['system_needs']['params']['electrification_growth']['high']}}
    hi = LY.system_path(p, a_hi, True).set_index('year')['net_peak_mw']
    pol = runs['policy']['capex_m']
    for y in (yrs[-1] + 1, 2040, 2050):
        assert pol.loc[y] / pol.loc[y - 1] == pytest.approx(hi.loc[y] / hi.loc[y - 1] * (1 + infl), rel=1e-9)
    # model basis is still selectable and differs
    m = LY.project_layers(uj, p, overrides=MODEL_BAU)['bau'].set_index('year')
    assert m.loc[2026, 'capex_m'] == p['annual_capex_m']


@pytest.mark.parametrize('key,nb', UTILS)
def test_plan_capex_avoidance_by_category(key, nb):
    """SS capex = plan - avoided; growth avoided <= share x cap; replacement and grid mod at their addressable shares."""
    uj, p = _utility(key, nb)
    r = LY.project_layers(uj, p)
    b, s, a = r['bau'].set_index('year'), r['ss'].set_index('year'), r['assumptions']['bau_plan']
    av = b['capex_m'] - s['capex_m']
    np.testing.assert_allclose(b['capex_m'].values, b[[f'plan_{c}_capex_m' for c in LY.PLAN_CATEGORIES]].sum(axis=1).values, rtol=1e-12)
    parts = s[['capex_avoided_growth_m', 'capex_avoided_replacement_m', 'capex_avoided_gridmod_m', 'capex_avoided_other_m']].sum(axis=1)
    np.testing.assert_allclose(av.values, parts.values, rtol=1e-9, atol=1e-9)
    assert (s['capex_avoided_growth_m'] <= b['plan_growth_capex_m'] * a['addressable_growth'] + 1e-9).all()
    full = 2028 + int(a['addressable_ramp_years'])
    np.testing.assert_allclose(s.loc[full:, 'capex_avoided_replacement_m'],
                               b.loc[full:, 'plan_replacement_capex_m'] * a['addressable_replacement'], rtol=1e-9)
    assert (s.loc[:2027, ['capex_avoided_growth_m', 'capex_avoided_replacement_m']].values == 0).all()
    off = LY.project_layers(uj, p, enabled={'deferral': False})
    np.testing.assert_allclose(off['ss']['capex_m'].values, off['bau']['capex_m'].values, rtol=1e-12)


@pytest.mark.parametrize('key,nb', UTILS)
def test_transmission_follows_its_own_plan(key, nb):
    """PJM utilities: the transmission line follows the plan's transmission rate base per MW of peak; New York: no line."""
    uj, p = _utility(key, nb)
    r = LY.project_layers(uj, p)
    bp = uj['forward_assumptions']['bau_plan']['params']
    b = r['bau'].set_index('year')
    if 'transmission_plan_rate_base_m' not in bp:
        assert (b['avg_bill_transmission'] == 0).all()
        return
    yrs, rb = bp['transmission_plan_years']['value'], bp['transmission_plan_rate_base_m']['value']
    pk = r['system'].set_index('year')['peak_mw']
    y = yrs[-1]
    exp = (rb[yrs.index(y)] / pk.loc[y]) / (rb[yrs.index(2026)] / pk.loc[2026])
    assert b.loc[y, 'bill_transmission'] / b.loc[2026, 'bill_transmission'] == pytest.approx(exp, rel=1e-9)


@pytest.mark.parametrize('key,nb', UTILS)
def test_long_run_capacity_price(key, nb):
    """The long-run price path reaches the long-run cost of new entry (inflated) by long_run_year."""
    uj, p = _utility(key, nb)
    cap = uj['forward_assumptions']['layers']['capacity']['params']
    infl = uj['forward_assumptions']['projection']['inflation_rate']['value']
    r = LY.project_layers(uj, p, overrides={('capacity', 'price_path'): 'long_run'})['bau'].set_index('year')
    ly, lr = cap['long_run_year']['value'], cap['long_run_price_m_per_mw_yr']['value']
    exp = lr * (1 + infl) ** (ly - cap['long_run_price_year']['value'])
    assert r.loc[ly, 'capacity_price_m_per_mw_yr'] == pytest.approx(exp, rel=1e-9)
    today = LY.project_layers(uj, p)['bau'].set_index('year')
    assert r.loc[2050, 'capacity_cost_m'] > today.loc[2050, 'capacity_cost_m']


def test_coned_data_centre_growth_matches_forecasts():
    """Con Edison's central data-centre growth is 0% (CECONY forecast 0.7%/yr peak growth; Zone J flat in the Gold Book)."""
    uj, p = _utility('ConEd', 'GridDividend_NewYork.ipynb')
    sn = uj['forward_assumptions']['layers']['system_needs']['params']['dc_growth']
    assert sn['central'] == 0.0 and sn['status'] == 'derived'
    pk = LY.project_layers(uj, p)['system'].set_index('year')['peak_mw']
    # remaining system peak growth comes from baseline growth and electrification, not data centres
    assert (pk[2030] / pk[2026]) ** 0.25 - 1 < 0.015


def test_rge_plan_from_rate_case():
    """RG&E's plan covers 2026-2031 (Case 25-E-0379) and sums to the filed electric total, net of hydro, plus common."""
    uj, _ = _utility('RGE', 'GridDividend_NewYork.ipynb')
    bp = uj['forward_assumptions']['bau_plan']['params']
    assert bp['plan_years']['value'] == list(range(2026, 2032))
    hydro, common = 14735 / 336163, 471.6 * 0.7139
    assert sum(bp['plan_dist_capex_m']['value']) == pytest.approx(5060 * (1 - hydro) + common, abs=0.5)


@pytest.mark.parametrize('key,nb', UTILS)
def test_plan_growth_capex_linked_to_load(key, nb):
    """Linked: plan-year growth capex = plan x growth share x cumulative model growth / cumulative plan growth; other categories on plan."""
    uj, p = _utility(key, nb)
    bp = uj['forward_assumptions']['bau_plan']['params']
    assert bp['link_growth_to_load']['value'] is True
    yrs, plan, g = bp['plan_years']['value'], bp['plan_dist_capex_m']['value'], bp['plan_load_growth']['value']
    sh = dict(zip(LY.PLAN_CATEGORIES, bp['category_shares']['value']))
    r = LY.project_layers(uj, p)
    b, pk = r['bau'].set_index('year'), r['system'].set_index('year')['peak_mw']
    for y, cp in zip(yrs, plan):
        t = y - 2026
        sc = 1.0 if t == 0 else max(0.0, (pk[y] / pk[2026] - 1) / ((1 + g) ** t - 1))
        assert b.loc[y, 'plan_growth_capex_m'] == pytest.approx(cp * sh['growth'] * sc, rel=1e-9)
        for c in ('replacement', 'gridmod', 'other'):
            assert b.loc[y, f'plan_{c}_capex_m'] == pytest.approx(cp * sh[c], rel=1e-12)
    fixed = LY.project_layers(uj, p, overrides=PLAN_FIXED)['bau'].set_index('year')
    np.testing.assert_allclose(fixed.loc[yrs, 'capex_m'].values, plan, rtol=1e-12)
    # more model load growth than the plan assumes -> more growth capex, and vice versa
    if pk[yrs[-1]] / pk[2026] - 1 > (1 + g) ** (yrs[-1] - 2026) - 1:
        assert b.loc[yrs[-1], 'capex_m'] > fixed.loc[yrs[-1], 'capex_m']
    else:
        assert b.loc[yrs[-1], 'capex_m'] <= fixed.loc[yrs[-1], 'capex_m']


def test_rge_data_centres_follow_gold_book_zone_b():
    """RG&E central data-centre load = 300 MW + Gold Book Zone B large-load MW added since 2026 x RG&E share of Zone B; high 5%/yr."""
    uj, p = _utility('RGE', 'GridDividend_NewYork.ipynb')
    sy = LY.project_layers(uj, p)['system'].set_index('year')['dc_mw']
    sh = 1050 / 1828                                  # RG&E share of the Zone B peak
    added = {2026: 0, 2027: 0, 2028: round(150 * sh, 1), 2029: round(280 * sh, 1), 2030: round(400 * sh, 1),
             2040: round(400 * sh, 1), 2050: round(400 * sh, 1)}
    for y, mw in added.items():
        assert sy[y] == pytest.approx(p['dc_load_mw_start'] + mw)
    hi = LY.project_layers(uj, p, overrides={('system_needs', 'dc_growth'): 'high'})['system'].set_index('year')['dc_mw']
    assert hi[2050] == pytest.approx(p['dc_load_mw_start'] * 1.05 ** 24)


@pytest.mark.parametrize('key,nb', UTILS)
def test_utility_forecast_pace_calibrates_load(key, nb):
    """Central pace: system peak growth over the plan years equals the plan's forecast, so the scale factor is 1.0 at plan end."""
    uj, p = _utility(key, nb)
    bp = uj['forward_assumptions']['bau_plan']['params']
    assert bp['electrification_pace']['value'] == 'utility_forecast'
    end, g = bp['plan_years']['value'][-1], bp['plan_load_growth']['value']
    r = LY.project_layers(uj, p)
    pk = r['system'].set_index('year')['peak_mw']
    assert (pk[end] / pk[2026]) ** (1 / (end - 2026)) - 1 == pytest.approx(g, abs=1e-9)
    assert r['bau'].set_index('year').loc[end, 'plan_growth_scale'] == pytest.approx(1.0, abs=1e-6)
    c = r['load_calibration']
    assert c['electrification_multiplier'] >= 0
    sp = LY.project_layers(uj, p, overrides={('bau_plan', 'electrification_pace'): 'state_policy'})
    assert sp['load_calibration']['electrification_multiplier'] == 1.0


def test_electrification_pace_table():
    uj, p = _utility('PepcoMD', 'GridDividend_Maryland.ipynb')
    t = LY.electrification_pace_table(uj, p)
    assert len(t) == 6
    for sc in LY.SCENARIOS:
        u, s = t.loc[(sc, 'utility_forecast')], t.loc[(sc, 'state_policy')]
        assert s['Additional opportunity, customer savings ($B, undiscounted nominal)'] == pytest.approx(
            s['Customer savings ($B, undiscounted nominal)'] - u['Customer savings ($B, undiscounted nominal)'])


# ── Additional savings objective ──────────────────────────────────────────────

@pytest.mark.parametrize('key,nb', UTILS)
def test_objective_zero_is_a_no_op(key, nb):
    """At the default 0% every output equals the run with the objective layer switched off."""
    uj, p = _utility(key, nb)
    assert uj['forward_assumptions']['layers']['objective']['params']['objective_pct']['central'] == 0.0
    a = LY.project_layers(uj, p)
    b = LY.project_layers(uj, p, enabled={'objective': False})
    for case in ('bau', 'ss'):
        for col in b[case].columns:
            np.testing.assert_array_equal(a[case][col].values, b[case][col].values, err_msg=f'{case} {col}')
    assert (a['ss']['objective_saving_m'] == 0).all()


@pytest.mark.parametrize('key,nb', UTILS)
@pytest.mark.parametrize('base', LY.OBJECTIVE_BASES)
def test_objective_savings_rise_with_level(key, nb, base):
    uj, p = _utility(key, nb)
    cs, earn = [], []
    for pct in (0.0, 0.025, 0.05, 0.10):
        r = LY.project_layers(uj, p, overrides={('objective', 'objective_pct'): pct, ('objective', 'objective_base'): base})
        sm = LY.system_summary(r)
        cs.append(sm['Customer savings ($B, undiscounted nominal)'])
        earn.append(sm['Shared savings earnings ($B, undiscounted nominal)'])
        assert (r['bau']['objective_saving_m'] == 0).all()           # BAU is untouched
    assert all(x < y for x, y in zip(cs, cs[1:])), cs
    assert all(x <= y for x, y in zip(earn, earn[1:])), earn


def test_objective_capex_base_flows_through_rate_base():
    uj, p = _utility('ConEd', 'GridDividend_NewYork.ipynb')
    ov = {('objective', 'objective_pct'): 0.05, ('objective', 'objective_base'): 'capex_plan'}
    r, c = LY.project_layers(uj, p, overrides=ov), LY.project_layers(uj, p)
    s, s0 = r['ss'].set_index('year'), c['ss'].set_index('year')
    assert s.loc[2026, 'objective_level'] == 0 and s.loc[2027, 'objective_level'] == pytest.approx(0.05 / 3)
    assert s.loc[2029, 'objective_level'] == pytest.approx(0.05)
    # capex falls by the objective, rate base by its accumulation; the RR saving equals the RR difference
    np.testing.assert_allclose((s0['capex_m'] - s['capex_m']).values, s['objective_gross_m'].values, rtol=1e-9, atol=1e-9)
    assert s.loc[2050, 'wires_rate_base_m'] < s0.loc[2050, 'wires_rate_base_m']
    np.testing.assert_allclose((s0['rr_dist_m'] - s['rr_dist_m']).values, s['objective_saving_m'].values, rtol=1e-7, atol=1e-6)


def test_objective_persistence_fades():
    uj, p = _utility('PepcoMD', 'GridDividend_Maryland.ipynb')
    r = LY.project_layers(uj, p, overrides={('objective', 'objective_pct'): 0.05, ('objective', 'objective_persistence'): 5})
    lv = r['ss'].set_index('year')['objective_level']
    assert lv[2029] == pytest.approx(0.05) and lv[2031] == pytest.approx(0.03) and lv[2034] == 0


# ── Mechanism options: fast start and customer dividend advance ───────────────

NEW_MECH = ('fast_start', 'near_term_ramp_capacity', 'near_term_ramp_programs_mw', 'near_term_ramp_addressable',
            'advance_enabled', 'advance_start_year', 'advance_sizing_fraction', 'advance_sizing_scenario',
            'advance_credit_years', 'advance_financing', 'advance_securitized_rate', 'advance_cap')
ADV = {('mechanism', 'advance_enabled'): True}


@pytest.mark.parametrize('key,nb', UTILS)
def test_mechanism_option_defaults_change_nothing(key, nb):
    """Defaults (fast start off, ramps null, advance off) give exactly the outputs of a JSON without the new inputs."""
    import copy
    uj, p = _utility(key, nb)
    mp = uj['forward_assumptions']['layers']['mechanism']['params']
    assert all(k in mp for k in NEW_MECH) and mp['fast_start']['value'] is False and mp['advance_enabled']['value'] is False
    uj0 = copy.deepcopy(uj)
    for k in NEW_MECH:
        del uj0['forward_assumptions']['layers']['mechanism']['params'][k]
    for sc in LY.SCENARIOS:
        a, b = LY.project_layers(uj, p, scenario=sc), LY.project_layers(uj0, p, scenario=sc)
        for case in ('bau', 'ss'):
            for col in b[case].columns:
                np.testing.assert_array_equal(a[case][col].values, b[case][col].values, err_msg=f'{sc} {case} {col}')
        assert a['advance'] is None and (a['ss']['advance_credit_m'] == 0).all()


@pytest.mark.parametrize('key,nb', UTILS)
def test_fast_start_first_savings_year_2027(key, nb):
    uj, p = _utility(key, nb)
    base = LY.project_layers(uj, p)['ss'].set_index('year')
    fs = LY.project_layers(uj, p, overrides={('mechanism', 'fast_start'): True})
    s, b = fs['ss'].set_index('year'), fs['bau']
    assert base.loc[2027, 'ee_gwh'] == 0 and base.loc[2027, 'new_program_spend_m'] == 0
    assert s.loc[2027, 'ee_gwh'] > 0 and s.loc[2027, 'new_program_spend_m'] > 0 and s.loc[2027, 'savings_pool_m'] != 0
    assert s.loc[2027, 'program_bill_cost_m'] == 0          # core surcharges leave the bill in 2027
    np.testing.assert_array_equal(b['avg_bill_total'].values, LY.project_layers(uj, p)['bau']['avg_bill_total'].values)


def test_near_term_ramps():
    uj, p = _utility('ConEd', 'GridDividend_NewYork.ipynb')
    pr = uj['forward_assumptions']['layers']['programs']['params']
    ov = {('mechanism', 'fast_start'): True, **LY.no_ramp_overrides(),
          ('mechanism', 'near_term_ramp_programs_mw'): {'2027': 0.5}}
    m = LY.project_layers(uj, p, overrides=ov)['mw'].set_index('year')
    st, tg = pr['mw_start_dr']['value'], pr['mw_2035_dr']['central']
    assert m.loc[2027, 'dr_ss_mw'] == pytest.approx(st + 0.5 * (tg - st))
    r = LY.project_layers(uj, p, overrides={('mechanism', 'near_term_ramp_capacity'): {'2028': 0.0}})
    s = r['ss'].set_index('year')
    assert s.loc[2028, 'peak_reduction_mw'] == 0 and s.loc[2029, 'peak_reduction_mw'] > 0
    r = LY.project_layers(uj, p, overrides={('mechanism', 'near_term_ramp_addressable'): {'2028': 1.0}})
    s, b = r['ss'].set_index('year'), r['bau'].set_index('year')
    ad = r['assumptions']['bau_plan']['addressable_replacement']
    assert s.loc[2028, 'capex_avoided_replacement_m'] == pytest.approx(b.loc[2028, 'plan_replacement_capex_m'] * ad)


@pytest.mark.parametrize('key,nb', UTILS)
@pytest.mark.parametrize('fin', ['utility_regulatory_asset', 'securitized'])
def test_advance_npv_equals_recoveries_plus_financing(key, nb, fin):
    """Credits + financing - recoveries = 2050 balance; PV at the financing rate: credits = recoveries + balance."""
    uj, p = _utility(key, nb)
    r = LY.project_layers(uj, p, scenario='Central', overrides={**ADV, ('mechanism', 'advance_financing'): fin})
    s, ad = r['ss'], r['advance']
    c, rec, f, bal = (s[k].values for k in ('advance_credit_m', 'advance_recovery_m', 'advance_financing_m', 'advance_balance_m'))
    assert c.sum() + f.sum() - rec.sum() == pytest.approx(bal[-1], abs=1e-6)
    d = (1 + ad['rate']) ** -np.arange(len(LY.YEARS))
    assert (c * d).sum() == pytest.approx((rec * d).sum() + bal[-1] * d[-1], rel=1e-9, abs=1e-6)
    assert ad['rate'] == (p['wacc'] if fin == 'utility_regulatory_asset' else 0.04)
    if fin == 'utility_regulatory_asset':
        np.testing.assert_allclose(s['advance_return_m'].values, f)
    else:
        assert (s['advance_return_m'] == 0).all()


@pytest.mark.parametrize('key,nb', UTILS)
@pytest.mark.parametrize('src', LY.ADVANCE_SOURCES)
def test_advance_sizing_cap_and_true_up(key, nb, src):
    uj, p = _utility(key, nb)
    r = LY.project_layers(uj, p, scenario='Cautious', overrides={**ADV, ('mechanism', 'advance_recovery_source'): src})
    s, b, ad = r['ss'], r['bau'], r['advance']
    assert ad['financing'] == 'securitized' and ad['rate'] == 0.04 and ad['sizing_basis'] == 'recoverable'
    d = 1.04 ** -np.arange(len(LY.YEARS))
    base = np.array(ad['recoverable_base_m'])
    assert ad['size_m'] == pytest.approx(0.5 * (base * d).sum(), rel=1e-12)
    pc = np.array(ad['planned_credit_m'])
    assert (pc * d).sum() == pytest.approx(ad['size_m'], rel=1e-9)
    assert pc[LY.YEARS.index(2027)] > 0 and pc[LY.YEARS.index(2026)] == 0
    # cap: customers' total net saving is never negative in a recovery year; no residential bill above BAU
    cust = LY._customer_saving_yearly(r)
    assert (cust[s['advance_recovery_m'].values > 0] >= -1e-6).all()
    assert (s['avg_bill_total'].values <= b['avg_bill_total'].values + 1e-9).all()
    # true-up: a planned credit is paid unless last year's balance was above schedule
    sched, bal, cr = s['advance_schedule_m'].values, s['advance_balance_m'].values, s['advance_credit_m'].values
    for t in range(1, len(LY.YEARS)):
        if pc[t] > 0:
            assert (cr[t] == 0) == (bal[t - 1] > sched[t - 1] + 1e-9), LY.YEARS[t]


@pytest.mark.parametrize('key,nb', UTILS)
@pytest.mark.parametrize('src', LY.ADVANCE_SOURCES)
@pytest.mark.parametrize('fin', LY.ADVANCE_FINANCING)
def test_advance_cautious_sized_and_realized_clears(key, nb, src, fin):
    """Sized on Cautious recoverable savings and realized Cautious: no balance left in 2050 (within rounding)."""
    uj, p = _utility(key, nb)
    r = LY.project_layers(uj, p, scenario='Cautious', overrides={**ADV, ('mechanism', 'advance_recovery_source'): src,
                                                                  ('mechanism', 'advance_financing'): fin})
    assert abs(r['ss']['advance_balance_m'].iloc[-1]) < 1e-3
    assert r['ss']['advance_credit_m'].sum() > 0
