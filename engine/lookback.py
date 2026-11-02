"""
Look-back module: the starting point, 2021-2026, for each utility.

Data: utilities/<utility>_lookback.json (every figure with source, as_of and
status). The forward model (engine/layers.py) does not read it; this module only
calls the forward model's starting_lines() / by_category() to price the 2026
starting bill by category.

Blocks:
  bill_trend()        headline like-for-like trend: EIA-861 2021-2025 at the benchmark usage, delivery and supply
  bill_comparison()   bill levels by category: 2021 (EIA-861 averages) and 2026 (tariff); different bases, not a change
  functional_year()   distribution revenue requirement on a FERC Form 1 functional basis
  rr_bridge()         revenue-requirement bridge 2021 -> 2025 (Form 1) -> 2026 (approved rate-case step), detailed rows
  rr_bridge_grouped() the same bridge grouped: capital-driven, cost of capital, operating (normalised O&M), rate-case step
  supply_side()       capacity prices, implied energy supply rate, transmission (influenced, not controlled)
  rider_table(), dominion_bill_bridge()   Dominion: every Virginia rider, residential $/month and revenue requirement
  proceedings_table() rate cases and major riders: asked against granted; asked_granted_totals()
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

    Also: plant_property_tax = the company property tax / net plant ratio x (scope net plant
    + allocated general and intangible plant) x jurisdictional share, non_plant_taxes = taxes
    other than income - plant_property_tax (lb['rr_bridge']['property_tax_attribution']);
    om_normalised = O&M - non-service pension and retiree-benefit costs, allocated like A&G
    (lb['rr_bridge']['om_normalisation']).
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
    # property tax attributed to the scope's plant at the company property tax / net plant ratio (page 262 / page 200)
    ptax = _v(br['property_tax_attribution']['ratio'][year]) * (np_scope + gen_int) * j
    # non-service pension and retiree-benefit costs in A&G (account 926), allocated like the rest of A&G
    ns = _v(br['om_normalisation']['non_service_benefits_electric'][year]) * share_om * j
    a = br['allowed_return'][year]
    roe, eq, cod = _v(a['roe']), _v(a['equity_ratio']), _v(a['cost_of_debt'])
    w = wacc(roe, eq, cod)
    return dict(year=int(year), jurisdiction_share=j, plant_share=share_p, om_share=share_om,
                functional_plant=np_scope * j, general_intangible=gen_int * j, other_rate_base=other_rb * j,
                rate_base=rb, roe=roe, equity_ratio=eq, cost_of_debt=cod, wacc=w, return_m=rb * w,
                depreciation=dep, om=om, taxes_other=taxes, income_taxes=inc,
                plant_property_tax=ptax, non_plant_taxes=taxes - ptax, non_service_benefits=ns, om_normalised=om - ns,
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


GROUPS = ('capital_driven', 'cost_of_capital', 'operating', 'pension_non_service', 'rate_case')


def rr_bridge_grouped(lb, utility_json):
    """
    The revenue-requirement bridge grouped, $M nominal:
      capital_driven: return on rate-base growth (at the 2021 WACC), depreciation,
                      plant-related property tax, income tax on the return (Form 1 income taxes)
      cost_of_capital: ROE, equity ratio and cost of debt changes
      operating: O&M normalised (excluding non-service pension and retiree-benefit costs)
                 and non-plant taxes
      pension_non_service: the change in non-service pension and retiree-benefit costs,
                 outside the groups (zero where no normalisation applies)
      rate_case: the approved 2026 step.
    Start, 2025 subtotal and end equal the detailed bridge (rr_bridge()).
    """
    det = rr_bridge(lb, utility_json)
    a, b = functional_year(lb, BRIDGE_START), functional_year(lb, BRIDGE_MID)
    val = lambda item: det.loc[det['item'] == item, 'value_m'].iloc[0]
    rbg = det.loc[det['group'] == 'rate_base_growth', 'value_m'].sum()
    rows = [('start', det['item'].iloc[0], det['value_m'].iloc[0]),
            ('capital_driven', 'return_on_rate_base_growth', rbg),
            ('capital_driven', 'depreciation', b['depreciation'] - a['depreciation']),
            ('capital_driven', 'plant_property_tax', b['plant_property_tax'] - a['plant_property_tax']),
            ('capital_driven', 'income_tax_on_return', b['income_taxes'] - a['income_taxes']),
            ('cost_of_capital', 'roe_change', val('roe_change')),
            ('cost_of_capital', 'equity_ratio_change', val('equity_ratio_change')),
            ('cost_of_capital', 'cost_of_debt_change', val('cost_of_debt_change')),
            ('operating', 'om_normalised', b['om_normalised'] - a['om_normalised']),
            ('operating', 'non_plant_taxes', b['non_plant_taxes'] - a['non_plant_taxes']),
            ('pension_non_service', 'non_service_pension_and_retiree_benefits', b['non_service_benefits'] - a['non_service_benefits']),
            ('subtotal', det.loc[det['group'] == 'subtotal', 'item'].iloc[0], b['rr']),
            ('rate_case', f'Approved {BRIDGE_END} rate-case step', _v(lb['rr_bridge']['step_2026'])),
            ('end', det['item'].iloc[-1], det['value_m'].iloc[-1])]
    return pd.DataFrame(rows, columns=['group', 'item', 'value_m'])


def group_totals(grouped):
    """Total change by group, $M (the groups sum to end - start)."""
    return grouped[grouped['group'].isin(GROUPS)].groupby('group', sort=False)['value_m'].sum()


def bill_trend(lb):
    """
    Headline like-for-like bill trend, $/month nominal: EIA-861 residential average revenue
    per kWh, 2021-2025, x the benchmark usage (the utility's own state: Virginia for
    Dominion, Maryland for Pepco). Delivery = delivery-only (Part C) revenue per kWh x
    benchmark where EIA reports it (New York, Maryland); supply = total - delivery. Averages
    over customers and months, not tariff bills.
    Output: DataFrame indexed by year: total, delivery, supply (None where EIA has no split).
    """
    kwh = lb['benchmark_kwh_month']
    rows = []
    for y, d in sorted(lb['bill']['eia_series'].items()):
        tot = _v(d['bundled_cents_kwh']) * kwh / 100
        dl = _v(d['delivery_only_cents_kwh']) * kwh / 100 if 'delivery_only_cents_kwh' in d else None
        rows.append({'year': int(y), 'total': tot, 'delivery': dl, 'supply': None if dl is None else tot - dl})
    return pd.DataFrame(rows).set_index('year')


def bill_2026_tariff(utility_json):
    """The 2026 tariff bill at the benchmark usage by category, $/month nominal (the forward model's starting bill)."""
    c26 = LY.by_category(LY.starting_lines(utility_json))
    return pd.Series({**c26, 'total': sum(c26.values())})


def bill_comparison(lb, utility_json):
    """
    Residential bill levels at the benchmark usage by category, $/month nominal: 2021
    (lb['bill']['2021']; category values where located, otherwise unitemised by
    section) and 2026 (the forward model's starting bill, by category). The 2021
    figures are EIA-861 averages and the 2026 ones a tariff bill: different bases, so
    the difference is not a change (bill_trend() is the like-for-like trend).
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
                     'requested_comparable_m': _v(p['comparison']['requested_m']), 'approved_comparable_m': _v(p['comparison']['approved_m']),
                     'temporary': p['comparison']['temporary'],
                     'roe_requested': _v(p['roe_requested']), 'roe_granted': _v(p['roe_granted']),
                     'capital_adjustments': len(p.get('capital_adjustments', []))})
    return pd.DataFrame(rows)


def class_allocation_table(lb):
    """Residential share of each approved increase against its share of sales, and the customer charge before / after."""
    rows = []
    for c in lb['class_allocation']:
        rows.append({'docket': c['docket'], **{k: _v(c[k]) for k in ('residential_share_of_increase', 'residential_share_of_sales',
                                                                      'customer_charge_before', 'customer_charge_after')},
                     'residential_share_of_delivery_revenue': _v(c['residential_share_of_delivery_revenue'])
                     if 'residential_share_of_delivery_revenue' in c else None})
    return pd.DataFrame(rows)


RIDER_GROUPS = ('base_rates', 'fuel', 'transmission', 'generation', 'clean_energy', 'environmental', 'distribution',
                'energy_efficiency', 'other')


def rider_table(lb):
    """
    Dominion: every Virginia rider, residential $/month at 1,000 kWh by year (SCC, as of
    1 July 2021-2025; 2026 tariff) with its group and distribution flag. Riders not in
    effect in a year are NaN. Output: DataFrame indexed by rider id.
    """
    rd = lb['riders']
    yrs = sorted(rd['residential_bill'])
    rows = []
    for k, d in rd['definitions'].items():
        row = {'rider': k, 'name': d['name'], 'group': d['group'], 'distribution_related': d['distribution_related']}
        for y in yrs:
            c = rd['residential_bill'][y]['components'].get(k)
            row[y] = _v(c) if c else float('nan')
        rows.append(row)
    return pd.DataFrame(rows).set_index('rider')


def rider_rr_by_year(lb, month='07'):
    """
    Dominion: each rider's annual revenue requirement in effect on 1 July of each year
    2021-2026 ($M nominal): the latest approved rate year beginning on or before that date.
    """
    out = {}
    for k, entries in lb['riders']['revenue_requirements'].items():
        rec = {}
        for y in range(2021, 2027):
            ok = [e for e in entries if e['rate_year_beginning'] and e.get('approval') != 'Pending'
                  and str(e['rate_year_beginning']) <= f'{y}-{month}' and 'total_revenue_requirement_m' in e]
            rec[y] = _v(max(ok, key=lambda e: str(e['rate_year_beginning']))['total_revenue_requirement_m']) if ok else None
        out[k] = rec
    return pd.DataFrame(out).T


def dominion_bill_bridge(lb):
    """
    Dominion residential bill bridge, $/month nominal at 1,000 kWh: base rates, fuel and
    riders by group, 2021-2025 on the SCC basis (as of 1 July, excluding taxes), the
    change 2021 -> 2025 (like for like), and the 2026 tariff separately (with its taxes).
    Also the distribution-related riders. Output: DataFrame indexed by group.
    """
    t = rider_table(lb)
    yrs = [c for c in t.columns if c.isdigit()]
    g = t.groupby('group')[yrs].sum(min_count=1).reindex(list(RIDER_GROUPS)).fillna(0.0)
    g.loc['total'] = g.sum()
    g.loc['distribution_related_riders'] = t[t['distribution_related']][yrs].sum().fillna(0.0)
    g['change_2021_2025'] = g['2025'] - g['2021']
    return g


def asked_granted_totals(lb, include_temporary=False):
    """
    Asked against granted over 2021-2026, $M a year nominal: the sum of each proceeding's
    comparable requested and approved amounts (p['comparison'], usually the first rate
    year), cumulative and as a percentage. Pending proceedings with temporary rates count
    only with include_temporary=True. Output: dict.
    """
    ps = [p for p in lb['proceedings'] if p['comparison']['included_in_totals']
          or (include_temporary and p['comparison']['temporary'])]
    req = sum(_v(p['comparison']['requested_m']) for p in ps)
    app = sum(_v(p['comparison']['approved_m']) for p in ps)
    return {'proceedings': [p['docket'] for p in ps], 'requested_m': req, 'approved_m': app,
            'approved_pct_of_requested': 100 * app / req if req else None, 'include_temporary': include_temporary}


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
    grp = rr_bridge_grouped(lb, utility_json)
    trend = bill_trend(lb)
    yrs = {y: functional_year(lb, y) for y in (BRIDGE_START, BRIDGE_MID)}
    num = lambda x: None if x is None or (isinstance(x, float) and pd.isna(x)) else float(x)
    rows = lambda df: [{'group': g, 'item': i, 'value_m': float(v)} for g, i, v in df.itertuples(index=False)]
    out = {
        'note': lb['_note'], 'period': lb['period'], 'benchmark_kwh_month': lb['benchmark_kwh_month'],
        'bill_trend': {'basis': lb['bill']['trend_basis'],
                       'rows': [{'year': int(y), 'total_usd_month': num(r['total']), 'delivery_usd_month': num(r['delivery']),
                                 'supply_usd_month': num(r['supply'])} for y, r in trend.iterrows()],
                       'change_2021_2025_usd_month': {c: num(trend.loc[2025, c] - trend.loc[2021, c]) if trend[c].notna().all() else None
                                                      for c in ('total', 'delivery', 'supply')},
                       'eia_series': lb['bill']['eia_series']},
        'bill_2026_tariff': {'basis': lb['bill']['2026']['basis'],
                             'rows': [{'item': i, 'usd_month': float(v)} for i, v in bill_2026_tariff(utility_json).items()]},
        'bill_levels_by_basis': {'note': 'Bill levels on different bases (2021: EIA-861 averages at the benchmark usage; 2026: tariff bill). Not a change; bill_trend is the like-for-like trend.',
                                 'basis_2021': lb['bill']['2021']['basis'], 'basis_2026': lb['bill']['2026']['basis'],
                                 'rows': [{'item': i, 'usd_month_2021': num(r['2021']), 'usd_month_2026': num(r['2026']),
                                           'status_2021': r['status_2021']} for i, r in bill.iterrows()]},
        'rr_bridge': {'scope': lb['rr_bridge']['scope'], 'note': lb['rr_bridge']['note'],
                      'rows': rows(br),
                      'grouped_rows': rows(grp),
                      'group_totals': {g: float(v) for g, v in group_totals(grp).items()},
                      'property_tax_attribution': lb['rr_bridge']['property_tax_attribution'],
                      'om_normalisation': lb['rr_bridge']['om_normalisation'],
                      'years': {y: {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in d.items()} for y, d in yrs.items()},
                      'step_2026': lb['rr_bridge']['step_2026']},
        'supply_side': supply_side(lb),
        'proceedings': lb['proceedings'],
        'asked_granted_totals': {'decided': asked_granted_totals(lb), 'including_temporary': asked_granted_totals(lb, True)},
        'class_allocation': lb['class_allocation']}
    if 'riders' in lb:
        bb = dominion_bill_bridge(lb)
        rr = rider_rr_by_year(lb)
        out['riders'] = {'note': lb['riders']['_note'], 'definitions': lb['riders']['definitions'],
                         'residential_bill': lb['riders']['residential_bill'],
                         'revenue_requirements': lb['riders']['revenue_requirements'],
                         'revenue_requirement_in_effect_1_july': {k: {str(y): num(v) for y, v in r.items()} for k, r in rr.iterrows()},
                         'bill_bridge': {'basis': '2021-2025: SCC typical residential bill at 1,000 kWh as of 1 July, excluding taxes (like for like); 2026: tariff in effect, excluding taxes (shown separately)',
                                         'rows': [{'group': g, **{c: num(v) for c, v in r.items()}} for g, r in bb.iterrows()],
                                         'taxes_2026_usd_month': _v(lb['riders']['residential_bill']['2026']['taxes'])}}
    return out
