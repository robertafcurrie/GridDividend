"""
Results export for the web explorer.

Writes exports/<utility>.json for the four utilities: every scenario (Cautious /
Central / Ambitious) x electrification pace (utility forecast / state policy),
from the layered model as it stands (no model changes here):
  - yearly 2026-2050: BAU and shared-savings average residential bill by bill
    category ($/month nominal), customer savings ($M nominal), rate base
    (wires + program regulatory asset, $M), equity return and shared savings
    earnings ($M nominal);
  - waterfall by layer, 2035 and 2050 ($/month nominal, average residential bill);
  - Sankey value flows, cumulative 2026-2050 ($M undiscounted nominal and NPV 3%,
    2026 $): gross value by source, program costs as a deduction, and the split to
    residential customers, business customers and shared savings earnings;
  - share_sweep per scenario and pace: utility_share 0.20 / 0.30 / 0.40, every
    other input fixed (customer savings, earnings, 2035 / 2050 monthly saving,
    and yearly customer savings, earnings and pool);
  - objective_sweep per scenario and pace: additional savings objective 0 / 2.5 /
    5 / 10%, same fields, plus the full chart data for each level under 'run'
    (yearly, waterfall_usd_month, value_flows_m);
  - advance per scenario and pace (customer dividend advance on, default sizing) and
    advance_stress per pace (sized on Central, realized Cautious): yearly bills,
    earnings and pool with the advance, and the worst year against BAU;
  - tornado rows per pace (Central, 2035 and 2050 monthly saving);
  - metadata: source commit, date, dollar basis, pool setting.

    python scripts/export_results.py            # all four utilities
    python scripts/export_results.py ConEd      # one utility

tests/test_export.py checks that each export's flows balance and its totals
match the headline figures (system_summary(), bill differences).
"""
import contextlib
import copy
import io
import json
import os
import subprocess
import sys
from datetime import date

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import layers as LY  # noqa: E402

OUT_DIR = os.path.join(ROOT, 'exports')
UTILITIES = {'ConEd': 'GridDividend_NewYork.ipynb', 'RGE': 'GridDividend_NewYork.ipynb',
             'DomVA': 'GridDividend_Virginia.ipynb', 'PepcoMD': 'GridDividend_Maryland.ipynb'}
SETUP = ('# ============================================================\n# SECTION 0: SETUP',
         '# ============================================================\n# SECTION 1: USER-ADJUSTABLE',
         '# ============================================================\n# SECTION 1b: NEAR-TERM',
         'def load_utility(key):')
YEARS = LY.YEARS
WATERFALL_YEARS = (2035, 2050)
SHARE_SWEEP = (0.20, 0.30, 0.40)                 # utility share of the savings pool (default 0.30)
OBJECTIVE_SWEEP = (0.0, 0.025, 0.05, 0.10)       # additional savings objective (default 0%)
# Tornado driver type: a choice regulators or utilities make (policy) or a condition they do not control (external)
POLICY_LAYERS = {'programs', 'deferral', 'load_enabled', 'mechanism', 'roe', 'objective'}
POLICY_PARAMS = {('bau_plan', 'addressable_growth'), ('bau_plan', 'addressable_replacement'),
                 ('bau_plan', 'addressable_gridmod'), ('network', 'flex_targeting_share')}
FLOW_SOURCES = ('deferral', 'capacity', 'transmission', 'losses', 'wholesale', 'efficiency_energy',
                'additional_objective')
_NS = {}


def load_utility(key):
    """(utility_json, params) as the state notebook builds them (Sections 0, 1, 1b, 2 setup cells)."""
    nb_name = UTILITIES[key]
    if nb_name not in _NS:
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
        _NS[nb_name] = ns
    ns = _NS[nb_name]
    return ns['UTILITIES'][key], ns['utility_data'][key]


def with_objective(utility_json, pct):
    """Copy of utility_json with the additional savings objective set to pct at every level (waterfall sees it too)."""
    uj = copy.deepcopy(utility_json)
    spec = uj['forward_assumptions']['layers']['objective']['params']['objective_pct']
    for lev in LY.LEVELS:
        spec[lev] = pct
    return uj


def with_pace(utility_json, pace):
    """Copy of utility_json with bau_plan.electrification_pace set (so every engine function sees it)."""
    uj = copy.deepcopy(utility_json)
    uj['forward_assumptions']['bau_plan']['params']['electrification_pace']['value'] = pace
    return uj


def _npv(v):
    return float(np.sum(np.asarray(v) / 1.03 ** (np.asarray(YEARS) - YEARS[0])))


def value_flows(run, params):
    """
    Customer savings decomposed by source, $M nominal per year (arrays), exactly as
    system_summary() adds them up:
      deferral          = BAU - SS wires revenue requirement (deferral, load enabled,
                          connection capex, any ROE change on wires), less the
                          additional objective's share
      additional_objective = the objective's net reduction in the wires revenue
                          requirement (objective_saving_m)
      capacity          = BAU - SS capacity cost
      transmission, losses, wholesale = the value-stream layers
      efficiency_energy = efficiency GWh x today's residential supply rate, grown
      program_costs     = BAU program surcharges - SS program revenue requirement (a deduction)
      earnings          = shared savings earnings (recovered in rates)
    customers = sum of sources + program_costs - earnings = customer savings;
    residential / business split by the residential share of sales (EIA-861).
    """
    b, s = run['bau'], run['ss']
    t = np.arange(len(YEARS))
    g = run['assumptions']['projection']['supply_energy_growth']
    col = lambda d, c: d[c].values if c in d.columns else np.zeros(len(d))
    obj = col(s, 'objective_saving_m')
    f = {'deferral': (b['rr_dist_m'] - s['rr_dist_m']).values - obj,
         'additional_objective': obj,
         'capacity': (b['capacity_cost_m'] - s['capacity_cost_m']).values,
         'transmission': col(s, 'transmission_avoided_m'),
         'losses': col(s, 'losses_energy_value_m') + col(s, 'losses_peak_value_m'),
         'wholesale': col(s, 'wholesale_value_m'),
         'efficiency_energy': s['ee_gwh'].values * LY.supply_rate_kwh(run) * (1 + g) ** t,
         'program_costs': ((b['program_rr_m'] + b['program_bill_cost_m']) - (s['program_rr_m'] + s['program_bill_cost_m'])).values,
         'earnings': (s['rr_m'] - s['rr_core_m']).values - (b['rr_m'] - b['rr_core_m']).values}
    f['customers'] = sum(f[k] for k in FLOW_SOURCES) + f['program_costs'] - f['earnings']
    rs = params['residential_sales_share']
    f['residential'] = f['customers'] * rs
    f['business'] = f['customers'] * (1 - rs)
    return f


def sankey(flows):
    """Cumulative flows ($M) for a Sankey, undiscounted nominal and NPV 3% (2026 $); they balance."""
    out = {}
    for basis, agg in (('undiscounted_nominal', lambda v: float(np.sum(v))), ('npv3_2026', _npv)):
        src = {k: agg(flows[k]) for k in FLOW_SOURCES}
        prog = agg(flows['program_costs'])
        net = sum(src.values()) + prog
        out[basis] = {'sources': src, 'program_costs': prog, 'net_value': net,
                      'to': {'residential_customers': agg(flows['residential']),
                             'business_customers': agg(flows['business']),
                             'shared_savings_earnings': agg(flows['earnings'])},
                      'links': ([{'source': k, 'target': 'net_value', 'value': v} for k, v in src.items()]
                                + [{'source': 'net_value', 'target': 'program_costs', 'value': -prog}]
                                + [{'source': 'net_value', 'target': k, 'value': agg(flows[kk])}
                                   for k, kk in (('residential_customers', 'residential'),
                                                 ('business_customers', 'business'),
                                                 ('shared_savings_earnings', 'earnings'))])}
    return out


def _r(v, n=4):
    return [round(float(x), n) for x in v]


def _sweep(uj, params, scenario, key, values, label, fmt):
    """The scenario re-run at each value of one input, every other input fixed."""
    out = {}
    for sh in values:
        run = LY.project_layers(uj, params, scenario=scenario, overrides={key: sh})
        sm = LY.system_summary(run)
        b, s = run['bau'].set_index('year'), run['ss'].set_index('year')
        flows = value_flows(run, params)
        out[fmt.format(sh)] = {
            label: sh,
            'customer_savings_b_undiscounted': sm['Customer savings ($B, undiscounted nominal)'],
            'customer_savings_b_npv3': sm['Customer savings ($B, NPV 3%, 2026 $)'],
            'shared_savings_earnings_b': sm['Shared savings earnings ($B, undiscounted nominal)'],
            'shared_savings_earnings_b_npv3': sm['Shared savings earnings ($B, NPV 3%, 2026 $)'],
            'monthly_saving_2035': float(b.loc[2035, 'avg_bill_total'] - s.loc[2035, 'avg_bill_total']),
            'monthly_saving_2050': float(b.loc[2050, 'avg_bill_total'] - s.loc[2050, 'avg_bill_total']),
            'yearly': {'customer_savings_m': _r(flows['customers']),
                       'shared_savings_earnings_m': _r(run['ss']['shared_savings_earnings_m']),
                       'savings_pool_m': _r(np.nan_to_num(run['ss']['savings_pool_m'].values))}}
    return out


def share_sweep(uj, params, scenario, shares=SHARE_SWEEP):
    """
    The scenario re-run at each utility share of the savings pool, every other input
    fixed. The pool (value created) does not depend on the share, so customer savings
    + shared savings earnings is the same at every share; the share only moves value
    between them (see METHODOLOGY 3.10).
    """
    return _sweep(uj, params, scenario, ('mechanism', 'utility_share'), shares, 'utility_share', '{:.2f}')


def objective_sweep(uj, params, scenario, levels=OBJECTIVE_SWEEP):
    """
    The scenario re-run at each additional savings objective (share of its base),
    every other input fixed. Each entry also carries the full chart data for that
    level under 'run' (yearly, waterfall_usd_month, value_flows_m), built exactly as
    the top-level run block, so the explorer can redraw every chart at each level.
    """
    out = _sweep(uj, params, scenario, ('objective', 'objective_pct'), levels, 'objective_pct', '{:.3f}')
    for pct in levels:
        out[f'{pct:.3f}']['run'] = run_block(with_objective(uj, pct), params, scenario)
    return out


def run_block(uj, params, scenario, run=None):
    """The chart data for one run: yearly series, waterfalls and Sankey value flows."""
    run = run or LY.project_layers(uj, params, scenario=scenario)
    b, s = run['bau'], run['ss']
    flows = value_flows(run, params)
    bills = {case: {c: _r(d[f'avg_bill_{c}']) for c in LY.CATEGORIES} | {'total': _r(d['avg_bill_total'])}
             for case, d in (('bau', b), ('shared_savings', s))}
    wf = LY.waterfall(uj, params, years=WATERFALL_YEARS, scenario=scenario)
    return {
        'yearly': {'year': YEARS, 'avg_residential_bill_usd_month': bills,
                   'customer_savings_m': _r(flows['customers']),
                   'rate_base_m': {'bau': _r(b['rate_base_m'], 1), 'shared_savings': _r(s['rate_base_m'], 1)},
                   'equity_return_m': {'bau': _r(b['equity_return_m'], 2), 'shared_savings': _r(s['equity_return_m'], 2)},
                   'shared_savings_earnings_m': _r(s['shared_savings_earnings_m'], 3),
                   'earnings_total_m': {'bau': _r(b['utility_earnings_m'], 2), 'shared_savings': _r(s['utility_earnings_m'], 2)},
                   'earnings_per_rate_base': {'bau': _r(b['utility_earnings_m'] / b['rate_base_m'], 6),
                                              'shared_savings': _r(s['utility_earnings_m'] / s['rate_base_m'], 6)}},
        'waterfall_usd_month': {str(y): {k: round(float(v), 4) for k, v in wf.loc[y].items()} for y in WATERFALL_YEARS},
        'value_flows_m': sankey(flows)}


def run_export(uj, params, scenario):
    run = LY.project_layers(uj, params, scenario=scenario)
    b, s = run['bau'], run['ss']
    sm = LY.system_summary(run)
    by = b.set_index('year'); sy = s.set_index('year')
    return {
        **run_block(uj, params, scenario, run),
        'headline': {'customer_savings_b_undiscounted': sm['Customer savings ($B, undiscounted nominal)'],
                     'customer_savings_b_npv3': sm['Customer savings ($B, NPV 3%, 2026 $)'],
                     'shared_savings_earnings_b': sm['Shared savings earnings ($B, undiscounted nominal)'],
                     'monthly_saving_2035': float(by.loc[2035, 'avg_bill_total'] - sy.loc[2035, 'avg_bill_total']),
                     'monthly_saving_2050': float(by.loc[2050, 'avg_bill_total'] - sy.loc[2050, 'avg_bill_total']),
                     'bau_bill_2050': float(by.loc[2050, 'avg_bill_total'])},
        'load_calibration': {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in run['load_calibration'].items()},
        'share_sweep': share_sweep(uj, params, scenario),
        'objective_sweep': objective_sweep(uj, params, scenario),
        'advance': advance_block(uj, params, scenario),
    }


ADVANCE_ON = {('mechanism', 'advance_enabled'): True}


def advance_block(uj, params, scenario, sizing=None):
    """
    The scenario run with the customer dividend advance on (default sizing: 1.0 x the
    Cautious customer-savings NPV; or sizing = 'Central' for the stress case), with
    yearly bills, earnings, pool and the advance's credit, recovery, financing and
    balance, and a summary including the worst year against BAU.
    """
    ov = dict(ADVANCE_ON)
    if sizing:
        ov[('mechanism', 'advance_sizing_scenario')] = sizing
    run = LY.project_layers(uj, params, scenario=scenario, overrides=ov)
    b, s = run['bau'], run['ss']
    gap = (s['avg_bill_total'] - b['avg_bill_total']).values
    i = int(np.argmax(gap))
    ad0 = run['advance']
    k0 = YEARS.index(ad0['start_year'])
    j = k0 + int(np.argmax(gap[k0:]))              # smallest saving (largest gap) from the advance start
    sm = LY.system_summary(run)
    ad = run['advance']
    yrs = np.array(YEARS)
    disc = (1 + ad['rate']) ** -(yrs - YEARS[0])
    return {
        'yearly': {'year': YEARS,
                   'avg_residential_bill_usd_month': {'bau': _r(b['avg_bill_total']), 'shared_savings': _r(s['avg_bill_total'])},
                   'shared_savings_earnings_m': _r(s['shared_savings_earnings_m'], 3),
                   'advance_return_m': _r(s['advance_return_m'], 3),
                   'earnings_total_m': {'bau': _r(b['utility_earnings_m'], 2),
                                        'shared_savings': _r(s['utility_earnings_m'] + s['advance_return_m'], 2)},
                   'savings_pool_m': _r(np.nan_to_num(s['savings_pool_m'].values)),
                   'advance_credit_m': _r(s['advance_credit_m'], 3), 'advance_recovery_m': _r(s['advance_recovery_m'], 3),
                   'advance_financing_m': _r(s['advance_financing_m'], 3), 'advance_balance_m': _r(s['advance_balance_m'], 3)},
        'summary': {'sizing_scenario': ad['sizing_scenario'], 'realized_scenario': scenario,
                    'advance_size_m_pv3_2026': ad['size_m'], 'planned_credit_per_year_m': ad['credit_per_year_m'],
                    'credit_years': ad['credit_years'], 'start_year': ad['start_year'],
                    'financing': ad['financing'], 'financing_rate': ad['rate'],
                    'schedule_share_of_sizing_pool': ad['schedule_share_of_pool'],
                    'credits_paid_m': float(s['advance_credit_m'].sum()),
                    'recoveries_m': float(s['advance_recovery_m'].sum()),
                    'financing_cost_m': float(s['advance_financing_m'].sum()),
                    'balance_2050_m': float(s['advance_balance_m'].iloc[-1]),
                    'credits_pv_at_financing_rate_m': float(np.sum(s['advance_credit_m'].values * disc)),
                    'recoveries_pv_at_financing_rate_m': float(np.sum(s['advance_recovery_m'].values * disc)),
                    'years_credit_paused': [y for y, c, pl in zip(YEARS, s['advance_credit_m'], (YEARS[j] in range(ad['start_year'], ad['start_year'] + ad['credit_years']) for j in range(len(YEARS)))) if pl and c == 0],
                    'customer_savings_b_undiscounted': sm['Customer savings ($B, undiscounted nominal)'],
                    'customer_savings_b_npv3': sm['Customer savings ($B, NPV 3%, 2026 $)'],
                    'shared_savings_earnings_b': sm['Shared savings earnings ($B, undiscounted nominal)'],
                    'advance_return_b': float(s['advance_return_m'].sum()) / 1e3,
                    'customer_savings_less_unrecovered_balance_b': (sm['Customer savings ($B, undiscounted nominal)']
                                                                    - float(s['advance_balance_m'].iloc[-1]) / 1e3),
                    'customer_savings_less_unrecovered_balance_b_npv3': (
                        sm['Customer savings ($B, NPV 3%, 2026 $)']
                        - float(s['advance_balance_m'].iloc[-1]) / 1.03 ** (YEARS[-1] - YEARS[0]) / 1e3),
                    'worst_year_vs_bau': {'year': YEARS[i], 'shared_savings_minus_bau_usd_month': float(gap[i]),
                                          'exceeds_bau': bool(gap[i] > 1e-9)},
                    'smallest_saving_from_start': {'year': YEARS[j], 'bau_minus_shared_savings_usd_month': float(-gap[j])}}}


def tornado_rows(uj, params):
    tor, cen = LY.tornado(uj, params)
    rows = []
    for _, r in tor.iterrows():
        key = (r['layer'], r['assumption'])
        rows.append({'driver': f"{r['layer']}.{r['assumption']}", 'layer': r['layer'], 'assumption': r['assumption'],
                     'type': 'policy' if (r['layer'] in POLICY_LAYERS or key in POLICY_PARAMS) else 'external',
                     **{f'{lev}_{y}': round(float(r[f'{lev} {y}']), 4) for lev in ('low', 'high') for y in (2035, 2050)},
                     'swing_2050': round(float(r['swing 2050']), 4)})
    return {'central_saving_usd_month': {str(y): round(float(v), 4) for y, v in cen.items()}, 'rows': rows}


def source_commit():
    try:
        h = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain', '--', 'engine', 'utilities', 'scripts'],
                                             cwd=ROOT, text=True).strip())
        return h, dirty
    except Exception:
        return None, None


def build_export(key):
    uj0, params = load_utility(key)
    h, dirty = source_commit()
    mech = LY.resolve(uj0['forward_assumptions'])['mechanism']
    out = {'metadata': {'utility': key, 'name': uj0.get('name'), 'short_name': uj0.get('short_name'),
                        'source_commit': h, 'source_modified_since_commit': dirty, 'generated': date.today().isoformat(),
                        'dollar_basis': 'Nominal dollars. Cumulative figures undiscounted unless labelled npv3_2026 (NPV at 3%, 2026 dollars). Bills are the average residential bill, $/month.',
                        'pool_setting': {'pool_basis': mech.get('pool_basis', 'revenue_requirement'),
                                         'utility_share_central': mech['utility_share'],
                                         'negative_pools': 'carried forward', 'roe_in_pool': False},
                        'bau_basis': 'published_plan',
                        'residential_sales_share': params['residential_sales_share'],
                        'flows_note': 'Customer savings split residential / business by the residential share of sales (EIA-861, 2024).',
                        'share_sweep_note': 'Each scenario and pace re-run at utility_share 0.20 / 0.30 / 0.40 with every other input fixed (default 0.30). Value creation is held constant across shares: the share moves value between customers and the utility; it does not change what flexibility delivers.',
                        'objective_sweep_note': 'Each scenario and pace re-run with an additional savings objective of 0 / 2.5 / 5 / 10% of its base (default 0%, base dist_revenue_requirement, net of 20% cost to achieve), every other input fixed. The objective is additional to the other layers by assumption.',
                        'objective_sweep_run_note': 'Each objective_sweep level carries its full chart data under run (yearly, waterfall_usd_month, value_flows_m), built exactly as the top-level run block.',
                        'earnings_note': 'earnings_total_m = equity return on rate base + shared savings earnings; earnings_per_rate_base = earnings_total_m / rate base (wires + program regulatory asset).',
                        'advance_note': 'advance: each scenario with the customer dividend advance on (default off in the model): level bill credit for advance_credit_years from 2027 sized at 1.0 x the NPV (3%, 2026 $) of Cautious customer savings, financed at the after-tax WACC as a utility regulatory asset, recovered from the positive pool before sharing on a schedule that follows the sizing scenario pool; true-up pauses credits when behind schedule; recoveries capped so customers net saving is never negative. advance_stress: sized on Central, realized Cautious. worst_year_vs_bau = the largest shared-savings minus BAU average residential bill.',
                        'tornado_note': 'Tornado at Central (every input at central; low and high one at a time), per pace; change in the average residential monthly saving vs Central.',
                        'scenarios': list(LY.SCENARIOS), 'paces': list(LY.PACES), 'years': YEARS},
           'runs': {}, 'tornado': {}}
    for pace in LY.PACES:
        uj = with_pace(uj0, pace)
        out['runs'][pace] = {sc: run_export(uj, params, sc) for sc in LY.SCENARIOS}
        out['tornado'][pace] = tornado_rows(uj, params)
        out.setdefault('advance_stress', {})[pace] = advance_block(uj, params, 'Cautious', sizing='Central')
    return out


def main(argv):
    keys = argv or list(UTILITIES)
    os.makedirs(OUT_DIR, exist_ok=True)
    for k in keys:
        data = build_export(k)
        path = os.path.join(OUT_DIR, f'{k}.json')
        with open(path, 'w') as f:
            json.dump(data, f, indent=1)
        print(f'Wrote exports/{k}.json')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
