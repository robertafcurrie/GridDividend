"""
Look-back module: the starting point, 2021-2026, for each utility.

Data: utilities/<utility>_lookback.json (every figure with source, as_of and
status). The forward model (engine/layers.py) does not read it; this module only
calls the forward model's starting_lines() / by_category() to price the 2026
starting bill by category.

Blocks:
  bill_comparison()   residential bill at the benchmark usage, 2021 against 2026, by category
  functional_year()   distribution revenue requirement on a FERC Form 1 functional basis
  rr_bridge()         revenue-requirement bridge 2021 -> 2025 (Form 1) -> 2026 (approved rate-case step)
  supply_side()       capacity prices, implied energy supply rate, transmission (influenced, not controlled)
  proceedings_table() rate cases and major riders: asked against granted
  class_allocation_table()
  lookback_export()   the export block for exports/<utility>.json
"""
import json
import os

import pandas as pd

from . import layers as LY

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOOKBACK_FILES = {'ConEd': 'ConEd', 'RGE': 'RGE', 'DomVA': 'Dominion_VA', 'PepcoMD': 'Pepco_MD'}
CAPITAL_CATEGORIES = ('growth', 'replacement', 'grid_modernisation', 'storm_resilience', 'it_other')
STATUSES = ('sourced', 'derived', '_VERIFY', 'setting')
BRIDGE_START, BRIDGE_MID, BRIDGE_END = '2021', '2025', '2026'


def load_lookback(key, root=ROOT):
    """utilities/<utility>_lookback.json for a utility key ('ConEd', 'RGE', 'DomVA', 'PepcoMD')."""
    with open(os.path.join(root, 'utilities', f'{LOOKBACK_FILES[key]}_lookback.json')) as f:
        return json.load(f)


def _v(spec):
    return spec['value'] if isinstance(spec, dict) else spec


def wacc(roe, equity_ratio, cost_of_debt):
    """After-tax weighted average cost of capital, as params['wacc'] in the forward model."""
    return equity_ratio * roe + (1 - equity_ratio) * cost_of_debt


def revenue_requirement(rate_base, wacc_, depreciation, om, taxes_other, income_taxes=0.0):
    """
    Distribution revenue requirement, $M: the forward model's wires revenue
    requirement (layers.project_layers: rr_dist = rate base x WACC + property tax +
    depreciation + O&M), with taxes other than income in place of property tax and
    income taxes added, as Form 1 reports them separately.
    """
    return rate_base * wacc_ + taxes_other + depreciation + om + income_taxes


def functional_year(lb, year):
    """
    Revenue requirement for one year on a Form 1 functional basis, $M nominal.

    Scope: lb['rr_bridge']['scope']['functions'] (distribution; plus transmission in
    New York, where delivery rates recover it). Functional rate base = scope net
    plant + general and intangible plant + working capital and net ADIT, the last
    two allocated by the scope's share of net plant (distribution + transmission +
    production). Depreciation: scope plus allocated general, intangible and common.
    O&M: scope O&M + customer accounts, customer service and sales + A&G allocated
    by the scope's share of direct O&M (production net of purchased power,
    transmission, regional market, distribution). Taxes other than income and
    income taxes: by the net plant share. The jurisdictional share then applies.
    Return = rate base x allowed after-tax WACC (lb['rr_bridge']['allowed_return']).
    """
    br = lb['rr_bridge']
    f1 = {k: (_v(v) or 0.0) for k, v in br['form1'][year].items()}
    g = lambda k: f1.get(k, 0.0)
    scope = br['scope']['functions']
    j = _v(br['scope']['jurisdiction_share'][year])
    np_scope = sum(g(f'np_{f}') for f in scope)
    share_p = np_scope / (g('np_distribution') + g('np_transmission') + g('np_production'))
    gen_int = (g('np_general') + g('np_intangible')) * share_p
    other_rb = (g('net_working_capital') + g('net_adit')) * share_p
    rb = (np_scope + gen_int + other_rb) * j
    dep = (sum(g(f'dep_{f}') for f in scope) + (g('dep_general') + g('dep_intangible') + g('dep_common')) * share_p) * j
    direct_scope = sum(g(f'om_{f}') for f in scope)
    direct_all = (g('om_production') - g('om_purchased_power') + g('om_transmission') + g('om_regional_market')
                  + g('om_distribution'))
    share_om = direct_scope / direct_all
    om = (direct_scope + g('om_customer_accounts') + g('om_customer_service') + g('om_sales')
          + g('om_admin_general') * share_om) * j
    taxes = g('taxes_other_than_income') * share_p * j
    inc = g('income_taxes') * share_p * j
    a = br['allowed_return'][year]
    roe, eq, cod = _v(a['roe']), _v(a['equity_ratio']), _v(a['cost_of_debt'])
    w = wacc(roe, eq, cod)
    return dict(year=int(year), jurisdiction_share=j, plant_share=share_p, om_share=share_om,
                functional_plant=np_scope * j, general_intangible=gen_int * j, other_rate_base=other_rb * j,
                rate_base=rb, roe=roe, equity_ratio=eq, cost_of_debt=cod, wacc=w, return_m=rb * w,
                depreciation=dep, om=om, taxes_other=taxes, income_taxes=inc,
                rr=revenue_requirement(rb, w, dep, om, taxes, inc))


def capital_shares(utility_json):
    """Capital category shares (growth, replacement, grid modernisation, other) from the forward JSON, central level."""
    sh = LY.resolve(utility_json['forward_assumptions'])['bau_plan']['category_shares']
    return dict(zip(('growth', 'replacement', 'gridmod', 'other'), sh))


def rr_bridge(lb, utility_json):
    """
    Revenue-requirement bridge, $M nominal: 2021 (Form 1 functional basis) ->
    rate base growth by capital category, return (ROE, equity ratio, cost of debt),
    depreciation, O&M, taxes -> 2025 (same basis) -> approved 2026 rate-case step
    -> 2026.

    Rate base growth is valued at the 2021 WACC: functional plant growth split by
    the forward model's capital category shares (storm and resilience sit inside
    replacement: Form 1 cannot separate them, so that line is 0); IT and other =
    the "other" share plus general and intangible plant; working capital and ADIT
    are their own line. The return change is the 2025 rate base x the WACC change,
    split exactly into ROE, equity ratio and cost of debt effects.
    Output: DataFrame (group, item, value_m); the items sum from the 2021 revenue
    requirement to the 2026 one.
    """
    a, b = functional_year(lb, BRIDGE_START), functional_year(lb, BRIDGE_MID)
    sh = capital_shares(utility_json)
    d_plant = b['functional_plant'] - a['functional_plant']
    w0 = a['wacc']
    cap = {'growth': d_plant * sh['growth'], 'replacement': d_plant * sh['replacement'],
           'grid_modernisation': d_plant * sh['gridmod'], 'storm_resilience': 0.0,
           'it_other': d_plant * sh['other'] + (b['general_intangible'] - a['general_intangible'])}
    rb1 = b['rate_base']
    step = _v(lb['rr_bridge']['step_2026'])
    rows = [('start', f'Revenue requirement {BRIDGE_START} (Form 1 functional basis)', a['rr'])]
    rows += [('rate_base_growth', c, cap[c] * w0) for c in CAPITAL_CATEGORIES]
    rows += [('rate_base_growth', 'other_rate_base_items', (b['other_rate_base'] - a['other_rate_base']) * w0),
             ('return', 'roe_change', rb1 * a['equity_ratio'] * (b['roe'] - a['roe'])),
             ('return', 'equity_ratio_change', rb1 * (b['equity_ratio'] - a['equity_ratio']) * (b['roe'] - a['cost_of_debt'])),
             ('return', 'cost_of_debt_change', rb1 * (1 - b['equity_ratio']) * (b['cost_of_debt'] - a['cost_of_debt'])),
             ('depreciation', 'depreciation', b['depreciation'] - a['depreciation']),
             ('om', 'om', b['om'] - a['om']),
             ('taxes', 'taxes_other_than_income', b['taxes_other'] - a['taxes_other']),
             ('taxes', 'income_taxes', b['income_taxes'] - a['income_taxes']),
             ('subtotal', f'Revenue requirement {BRIDGE_MID} (Form 1 functional basis)', b['rr']),
             ('rate_case', f'Approved {BRIDGE_END} rate-case step', step),
             ('end', f'Revenue requirement {BRIDGE_END}', b['rr'] + step)]
    return pd.DataFrame(rows, columns=['group', 'item', 'value_m'])


def bridge_check(bridge):
    """Change items (excluding start, subtotal and end) sum to end - start; returns the difference, $M."""
    df = bridge
    change = df[~df['group'].isin(['start', 'subtotal', 'end'])]['value_m'].sum()
    start = df.loc[df['group'] == 'start', 'value_m'].iloc[0]
    end = df.loc[df['group'] == 'end', 'value_m'].iloc[0]
    return end - start - change


def bill_comparison(lb, utility_json):
    """
    Residential bill at the benchmark usage by category, $/month nominal: 2021
    (lb['bill']['2021']; category values where located, otherwise unitemised by
    section) against 2026 (the forward model's starting bill, by category).
    Output: DataFrame indexed by category plus 'unitemised' rows and 'total', with
    columns 2021, 2026, status_2021.
    """
    b21 = lb['bill']['2021']
    lines = LY.starting_lines(utility_json)
    c26 = LY.by_category(lines)
    rows = []
    for c in LY.CATEGORIES:
        s = b21['categories'][c]
        rows.append({'item': c, '2021': _v(s), '2026': c26[c], 'status_2021': s['status']})
    for k, s in b21['unitemised'].items():
        rows.append({'item': f'unitemised_{k}', '2021': _v(s), '2026': None, 'status_2021': s['status']})
    rows.append({'item': 'total', '2021': _v(b21['total']), '2026': sum(c26.values()), 'status_2021': b21['total']['status']})
    return pd.DataFrame(rows).set_index('item')


def supply_side(lb):
    """Capacity prices, implied energy supply rate and transmission series (influenced, not controlled)."""
    return lb['supply_side']


def proceedings_table(lb):
    """Asked against granted for each proceeding: DataFrame of docket, type, dates, revenue and ROE asked / granted."""
    rows = []
    for p in lb['proceedings']:
        rows.append({'docket': p['docket'], 'type': p['type'], 'status': p['status'],
                     'filed': _v(p['filed']), 'decided': _v(p['decided']),
                     'revenue_requested_m': _v(p['revenue_requested_m']), 'revenue_approved_m': _v(p['revenue_approved_m']),
                     'roe_requested': _v(p['roe_requested']), 'roe_granted': _v(p['roe_granted']),
                     'capital_adjustments': len(p.get('capital_adjustments', []))})
    return pd.DataFrame(rows)


def class_allocation_table(lb):
    """Residential share of each approved increase against its share of sales, and the customer charge before / after."""
    rows = []
    for c in lb['class_allocation']:
        rows.append({'docket': c['docket'], **{k: _v(c[k]) for k in ('residential_share_of_increase', 'residential_share_of_sales',
                                                                      'customer_charge_before', 'customer_charge_after')}})
    return pd.DataFrame(rows)


def iter_figures(obj, path=''):
    """Every numeric-or-null figure spec in a look-back JSON: yields (path, spec) for dicts holding 'value'."""
    if isinstance(obj, dict):
        if 'value' in obj and ('status' in obj or 'source' in obj):
            yield path, obj
            return
        for k, v in obj.items():
            yield from iter_figures(v, f'{path}/{k}')
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_figures(v, f'{path}[{i}]')


def lookback_export(key, utility_json, root=ROOT):
    """The lookback block for exports/<utility>.json."""
    lb = load_lookback(key, root)
    bill = bill_comparison(lb, utility_json)
    br = rr_bridge(lb, utility_json)
    yrs = {y: functional_year(lb, y) for y in (BRIDGE_START, BRIDGE_MID)}
    num = lambda x: None if x is None or (isinstance(x, float) and pd.isna(x)) else float(x)
    return {
        'note': lb['_note'], 'period': lb['period'], 'benchmark_kwh_month': lb['benchmark_kwh_month'],
        'bill_comparison': {'basis_2021': lb['bill']['2021']['basis'], 'basis_2026': lb['bill']['2026']['basis'],
                            'rows': [{'item': i, 'usd_month_2021': num(r['2021']), 'usd_month_2026': num(r['2026']),
                                      'status_2021': r['status_2021']} for i, r in bill.iterrows()],
                            'eia_series': lb['bill']['eia_series']},
        'rr_bridge': {'scope': lb['rr_bridge']['scope'], 'note': lb['rr_bridge']['note'],
                      'rows': [{'group': g, 'item': i, 'value_m': float(v)} for g, i, v in br.itertuples(index=False)],
                      'years': {y: {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in d.items()} for y, d in yrs.items()},
                      'step_2026': lb['rr_bridge']['step_2026']},
        'supply_side': supply_side(lb),
        'proceedings': lb['proceedings'],
        'class_allocation': lb['class_allocation']}
