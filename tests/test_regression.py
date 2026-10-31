# Regression tests: default settings must reproduce v1.0 results exactly.
# Run from the repo root:  python -m pytest tests/
import contextlib
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

from engine import project, run_named_scenario, apply_roe_override   # noqa: E402
from engine.roe_sweep import run_roe_sweep, compute_roe_metrics      # noqa: E402

# Con Edison BASE (EASE Case) cumulative bill saving per customer vs BAU,
# 2026–2050, undiscounted nominal — recorded from v1.0 before the
# SAVINGS_POOL_BASIS / ROE_OVERRIDE changes.
CONED_BASE_CUM_SAVING_PER_CUSTOMER = 12422.99623773428

# Setup cells of the New York notebook, identified by their opening lines so
# the test survives cells being added elsewhere.
SETUP_CELL_PREFIXES = (
    '# ============================================================\n# SECTION 0: SETUP',
    '# ============================================================\n# SECTION 1: USER-ADJUSTABLE',
    '# ============================================================\n# SECTION 1b: NEAR-TERM',
    'def load_utility(key):',
)


@pytest.fixture(scope='module')
def ny():
    """Namespace after running the NY notebook's Section 0, 1, 1b and 2 cells."""
    nb_dir = os.path.join(ROOT, 'notebooks')
    nb = json.load(open(os.path.join(nb_dir, 'GridDividend_NewYork.ipynb')))
    sources = [''.join(c['source']) for c in nb['cells'] if c['cell_type'] == 'code']
    ns, cwd = {}, os.getcwd()
    os.chdir(nb_dir)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            for prefix in SETUP_CELL_PREFIXES:
                matches = [s for s in sources if s.startswith(prefix)]
                assert len(matches) == 1, f'setup cell not found: {prefix!r}'
                exec(matches[0], ns)
    finally:
        os.chdir(cwd)
    return ns


def _base_run(ns, config):
    k = 'ConEd'
    bau = project(ns['utility_data'][k], 'bau', config=config)
    base = run_named_scenario(k, ns['SCENARIO_DEFS']['BASE'], ns['utility_data'],
                              {k: {'bau': bau}}, config)
    return bau, base


def _cum_saving(bau, base):
    return float((bau['avg_annual_bill'] - base['avg_annual_bill']).sum())


def test_coned_base_cumulative_saving_unchanged(ny):
    bau, base = _base_run(ny, ny['MODEL_CONFIG'])
    assert _cum_saving(bau, base) == pytest.approx(CONED_BASE_CUM_SAVING_PER_CUSTOMER,
                                                   rel=1e-12)


def test_explicit_defaults_match_implicit(ny):
    cfg = {**ny['MODEL_CONFIG'], 'SAVINGS_POOL_BASIS': 'capex', 'ROE_OVERRIDE': None}
    bau, base = _base_run(ny, cfg)
    assert _cum_saving(bau, base) == pytest.approx(CONED_BASE_CUM_SAVING_PER_CUSTOMER,
                                                   rel=1e-12)


def test_roe_override_at_rate_case_is_identity(ny):
    rc = ny['utility_data']['ConEd']['roe']
    bau, base = _base_run(ny, {**ny['MODEL_CONFIG'], 'ROE_OVERRIDE': rc})
    assert _cum_saving(bau, base) == pytest.approx(CONED_BASE_CUM_SAVING_PER_CUSTOMER,
                                                   rel=1e-12)


def test_roe_override_recomputes_wacc(ny):
    p = ny['utility_data']['ConEd']
    q = apply_roe_override(p, 0.07, ny['MODEL_CONFIG'])
    cod = ny['MODEL_CONFIG']['COST_OF_DEBT']
    assert q['wacc'] == pytest.approx(0.07 * p['equity_ratio'] + cod * (1 - p['equity_ratio']))
    assert p['roe'] != 0.07   # original params untouched


def test_revenue_requirement_pool_definition(ny):
    cfg = {**ny['MODEL_CONFIG'], 'SAVINGS_POOL_BASIS': 'revenue_requirement'}
    p = ny['utility_data']['ConEd']
    bau = project(p, 'bau', config=cfg)
    sh = project(p, 'shared', config=cfg)
    rr_cut = ((bau['traditional_earnings_m'] + bau['property_tax_m'])
              - (sh['traditional_earnings_m'] + sh['property_tax_m']))
    np.testing.assert_allclose(sh['savings_pool_m'], rr_cut - sh['nws_opex_m'])
    share = cfg['UTILITY_SAVINGS_SHARE']
    np.testing.assert_allclose(sh['utility_shared_revenue_m'], sh['savings_pool_m'] * share)


def test_min_share_is_break_even(ny):
    """Re-running at the computed minimum share closes the 25-year earnings gap."""
    kw = dict(utilities=['ConEd'], scenario_def=ny['SCENARIO_DEFS']['BASE'])
    m = compute_roe_metrics(run_roe_sweep(ny['utility_data'], ny['MODEL_CONFIG'],
                                          shares=(0.30,), roe_floor=0.094, **kw))
    for _, row in m.iterrows():
        s_star = row['min_share_25y']
        m2 = compute_roe_metrics(run_roe_sweep(
            ny['utility_data'], {**ny['MODEL_CONFIG'], 'SAVINGS_POOL_BASIS': row['pool_basis']},
            shares=(s_star,), roe_floor=0.094, pool_bases=(row['pool_basis'],), **kw))
        assert m2['cum_earnings_gap_25y_m'].iloc[0] == pytest.approx(0.0, abs=1e-6)


# ── Correction flags (off by default) ─────────────────────────────────────────

from engine import apply_preset, delivery_rr_reconciliation, PRESETS   # noqa: E402


def test_corrected_preset_is_not_default(ny):
    cfg = ny['MODEL_CONFIG']
    for key, val in PRESETS['CORRECTED'].items():
        if key in ('NWS_COST_TREATMENT', 'ROE_OVERRIDE_REBASE_BILL'):
            continue    # CORRECTED keeps these at their defaults
        assert cfg.get(key) != val, key


def test_depreciation_recalibration_matches_rate_case(ny):
    cfg = {**ny['MODEL_CONFIG'], 'INCLUDE_DEPRECIATION_EXPENSE': True}
    for k, p in ny['utility_data'].items():
        r = delivery_rr_reconciliation(p, cfg)
        bau = project(p, 'bau', config=cfg)
        assert bau['delivery_rr_m'].iloc[0] == pytest.approx(r['target_delivery_rr_m'])
        assert bau['depreciation_m'].iloc[0] == pytest.approx(0.035 * p['rate_base_start_m'])


def test_carry_forward_nets_negative_pools(ny):
    cfg = {**ny['MODEL_CONFIG'], 'SAVINGS_POOL_BASIS': 'revenue_requirement',
           'NEGATIVE_POOL_TREATMENT': 'carry_forward'}
    sh = project(ny['utility_data']['ConEd'], 'shared', config=cfg)
    assert (sh['incentive_base_m'] >= 0).all()
    assert sh['savings_pool_m'].iloc[0] < 0      # the case being tested
    # Paid-out base + carry balance still owed = cumulative pool
    np.testing.assert_allclose(sh['incentive_base_m'].cumsum() + sh['pool_carry_forward_m'],
                               sh['savings_pool_m'].cumsum())


def test_capitalised_nws_fully_amortised(ny):
    cfg = {**ny['MODEL_CONFIG'], 'NWS_COST_TREATMENT': 'capitalise', 'NWS_AMORTISATION_YEARS': 10}
    sh = project(ny['utility_data']['ConEd'], 'shared', config=cfg)
    np.testing.assert_allclose(sh['regulatory_asset_m'],
                               sh['nws_opex_m'].cumsum() - sh['nws_amortisation_m'].cumsum())
    first = sh['nws_opex_m'].iloc[0]
    assert sh['nws_amortisation_m'].iloc[1] == pytest.approx(first / 10)


def test_bill_index_bau_shows_year_one_difference(ny):
    p = ny['utility_data']['ConEd']
    own = project(p, 'shared', config=ny['MODEL_CONFIG'])
    idx = project(p, 'shared', config={**ny['MODEL_CONFIG'], 'BILL_INDEX_BASE': 'bau'})
    bau = project(p, 'bau', config=ny['MODEL_CONFIG'])
    # 'own': 2026 delivery bill ignores the SS/BAU revenue-requirement gap;
    # 'bau': it is scaled by SS 2026 delivery RR / BAU 2026 delivery RR.
    ratio = idx['delivery_rr_m'].iloc[0] / bau['delivery_rr_m'].iloc[0]
    assert ratio < 1
    assert (idx['delivery_bill_monthly'].iloc[0]
            == pytest.approx(own['delivery_bill_monthly'].iloc[0] * ratio))


def test_min_share_break_even_under_corrected_from_zero_share(ny):
    """Break-even share computed from a 0% run closes the gap when re-run."""
    cfg = apply_preset(ny['MODEL_CONFIG'], 'CORRECTED')
    kw = dict(utilities=['ConEd'], scenario_def=ny['SCENARIO_DEFS']['BASE'], roe_floor=0.094,
              pool_bases=('revenue_requirement',))
    m = compute_roe_metrics(run_roe_sweep(ny['utility_data'], cfg, shares=(0.0,), **kw))
    s_star = m['min_share_25y'].iloc[0]
    m2 = compute_roe_metrics(run_roe_sweep(ny['utility_data'], cfg, shares=(s_star,), **kw))
    assert m2['cum_earnings_gap_25y_m'].iloc[0] == pytest.approx(0.0, abs=1e-6)


# ── Pepco MD (Maryland notebook) ─────────────────────────────────────────────

# Pepco MD BASE (EASE Case) cumulative bill saving per customer vs BAU,
# 2026–2050, undiscounted nominal — default settings ('capex' pool, an upper
# bound; PEPCO capacity price growth = INFLATION_RATE), recorded from
# notebooks/GridDividend_Maryland.ipynb Section 12g and confirmed by the author.
PEPCO_MD_BASE_CUM_SAVING_PER_CUSTOMER = 1725.0941982988775


@pytest.fixture(scope='module')
def md():
    """Namespace after running the MD notebook's Section 0, 1, 1b and 2 cells."""
    nb_dir = os.path.join(ROOT, 'notebooks')
    nb = json.load(open(os.path.join(nb_dir, 'GridDividend_Maryland.ipynb')))
    sources = [''.join(c['source']) for c in nb['cells'] if c['cell_type'] == 'code']
    ns, cwd = {}, os.getcwd()
    os.chdir(nb_dir)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            for prefix in SETUP_CELL_PREFIXES:
                matches = [s for s in sources if s.startswith(prefix)]
                assert len(matches) == 1, f'setup cell not found: {prefix!r}'
                exec(matches[0], ns)
    finally:
        os.chdir(cwd)
    return ns


def test_pepco_md_base_cumulative_saving_unchanged(md):
    k = 'PepcoMD'
    bau = project(md['utility_data'][k], 'bau', config=md['MODEL_CONFIG'])
    base = run_named_scenario(k, md['SCENARIO_DEFS']['BASE'], md['utility_data'],
                              {k: {'bau': bau}}, md['MODEL_CONFIG'])
    assert _cum_saving(bau, base) == pytest.approx(PEPCO_MD_BASE_CUM_SAVING_PER_CUSTOMER,
                                                   rel=1e-12)


# ── Dominion VA (Virginia notebook) ──────────────────────────────────────────

# Dominion VA BASE (EASE Case) cumulative bill saving per customer vs BAU,
# 2026–2050, undiscounted nominal — default settings, with the engine using
# Dominion_VA.json's NWS-eligible shares (22% / 35%) rather than Section 1's
# 30% / 50% (bug fix on branch corrections-2).
DOMVA_BASE_CUM_SAVING_PER_CUSTOMER = 11640.525549731597


def _load_setup(nb_name):
    nb_dir = os.path.join(ROOT, 'notebooks')
    nb = json.load(open(os.path.join(nb_dir, nb_name)))
    sources = [''.join(c['source']) for c in nb['cells'] if c['cell_type'] == 'code']
    ns, cwd = {}, os.getcwd()
    os.chdir(nb_dir)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            for prefix in SETUP_CELL_PREFIXES:
                matches = [s for s in sources if s.startswith(prefix)]
                assert len(matches) == 1, f'setup cell not found: {prefix!r}'
                exec(matches[0], ns)
    finally:
        os.chdir(cwd)
    return ns


@pytest.fixture(scope='module')
def va():
    """Namespace after running the VA notebook's Section 0, 1, 1b and 2 cells."""
    return _load_setup('GridDividend_Virginia.ipynb')


def test_domva_base_cumulative_saving_unchanged(va):
    k = 'DomVA'
    bau = project(va['utility_data'][k], 'bau', config=va['MODEL_CONFIG'])
    base = run_named_scenario(k, va['SCENARIO_DEFS']['BASE'], va['utility_data'],
                              {k: {'bau': bau}}, va['MODEL_CONFIG'])
    assert _cum_saving(bau, base) == pytest.approx(DOMVA_BASE_CUM_SAVING_PER_CUSTOMER, rel=1e-12)


# ── corrections-2 options ─────────────────────────────────────────────────────

from engine import (nws_eligible_bounds, config_with, capacity_allocation_factor,   # noqa: E402
                    capacity_cost_in_year)


def test_nws_bounds_precedence(va, ny):
    cfg = va['MODEL_CONFIG']
    p = va['utility_data']['DomVA']
    assert nws_eligible_bounds(p, cfg) == (0.22, 0.35)                     # JSON wins
    assert nws_eligible_bounds(p, config_with(cfg, NWS_ELIGIBLE_CAPEX_SHARE_START=0.4))[0] == 0.4
    ny_cfg = ny['MODEL_CONFIG']                                             # NY JSON lacks fields
    assert nws_eligible_bounds(ny['utility_data']['ConEd'], ny_cfg) == (
        ny_cfg['NWS_ELIGIBLE_CAPEX_SHARE_START'], ny_cfg['NWS_ELIGIBLE_CAPEX_SHARE_MAX'])


def test_capacity_allocation_sales_share(ny):
    p = ny['utility_data']['ConEd']
    cfg = ny['MODEL_CONFIG']
    assert capacity_allocation_factor(p, cfg) == 1.0
    f = capacity_allocation_factor(p, {**cfg, 'CAPACITY_SAVINGS_ALLOCATION': 'sales_share'})
    assert f == pytest.approx(p['residential_sales_share'] / p['residential_customer_share'])
    k = 'ConEd'
    bau = project(p, 'bau', config=cfg)
    per_head = run_named_scenario(k, ny['SCENARIO_DEFS']['BASE'], ny['utility_data'], {k: {'bau': bau}}, cfg)
    by_class = run_named_scenario(k, ny['SCENARIO_DEFS']['BASE'], ny['utility_data'], {k: {'bau': bau}},
                                  {**cfg, 'CAPACITY_SAVINGS_ALLOCATION': 'sales_share'})
    np.testing.assert_allclose(by_class['pt_monthly_bill_reduction'],
                               per_head['pt_monthly_bill_reduction'] * f)


def test_corrected_capacity_growth_is_inflation(ny):
    cfg = ny['MODEL_CONFIG']
    corr = apply_preset(cfg, 'CORRECTED')
    assert corr['CAPACITY_COST_GROWTH'] == cfg['INFLATION_RATE']
    assert corr['CAPACITY_SAVINGS_ALLOCATION'] == 'sales_share'
    sens = apply_preset(cfg, 'CORRECTED_MARKET_CAPACITY_GROWTH')
    assert sens['CAPACITY_COST_GROWTH'] == cfg['CAPACITY_COST_GROWTH']      # 3% default kept
    assert capacity_cost_in_year(corr, 'ConEd', 2027) == pytest.approx(
        cfg['CAPACITY_COST_START']['ConEd'] * (1 + cfg['INFLATION_RATE']))
