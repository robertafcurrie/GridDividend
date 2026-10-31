# engine/layers.py
# GridDividend layer engine — a separate, additive model. It does not change
# project(), run_named_scenario() or any v1.0 / CORRECTED result.
#
# Year zero is each utility's `starting_bill` (utilities/*.json): today's
# residential bill at benchmark usage, by line and category. Each category is
# projected 2026-2050 on its own driver, in two cases: BAU and SHARED SAVINGS.
# The difference between the cases is built up from switchable layers whose
# low / central / high values live in the utility JSON `forward_assumptions`:
#
#   1 system_needs  load growth by segment, peak, forward capex split
#                   (shapes BAU and shared savings alike)
#   2 deferral      avoided / deferred growth-driven capex
#   3 programs      core-business programs leave the bill and become utility
#                   OPEX / CAPEX
#   4 utilisation   more kWh over the same wires
#   5 capacity      MW of peak reduction priced at the zonal capacity price
#   6 mechanism     utility share of the savings pool: shared savings earnings
#   hooks (off):    wholesale_energy, roe
#
# All $ are nominal. Bills are per residential customer at the benchmark usage
# (residential_kwh_month), held constant. System figures are $M per year.

import copy

import numpy as np
import pandas as pd

from .model import RATE_BASE_DECAY, delivery_rr_reconciliation

YEARS = list(range(2026, 2051))
LAYERS = ('system_needs', 'deferral', 'programs', 'utilisation', 'capacity', 'mechanism')
HOOK_LAYERS = ('wholesale_energy', 'roe')
SAVINGS_LAYERS = LAYERS[1:]                     # layers that separate shared savings from BAU
LEVELS = ('low', 'central', 'high')
CATEGORIES = ('distribution_base', 'distribution_rider', 'program_surcharge', 'supply_energy',
              'capacity', 'transmission', 'taxes_and_fees')
DIST_CATS = ('distribution_base', 'distribution_rider')


# ── Year zero ────────────────────────────────────────────────────────────────

def starting_lines(utility_json, carve_out=True, adjustments=True):
    """
    Year-zero bill lines ($/month per residential customer, benchmark usage).

    Returns a list of dicts: id, name, category, bill_section, unit, month
    ($/month for fixed/per-kWh lines), pct and applies_to (percentage lines),
    core (bool), origin ('starting_bill' | 'carve_out' | 'adjustment').

    carve_out: where capacity is embedded in a parent line, a derived capacity
      line is split out of the parent (total unchanged). Method and inputs in
      forward_assumptions['capacity_carve_out'].
    adjustments: add forward_assumptions['starting_adjustments'] lines (e.g.
      Pepco MD Order No. 92607 increase not yet billed).
    """
    sb = utility_json['starting_bill']
    kwh = sb['benchmark_kwh_month']
    fa = utility_json.get('forward_assumptions', {})
    out = []
    for ln in sb['lines']:
        if not ln.get('included_in_benchmark', True) or ln.get('rate') is None:
            continue
        d = dict(id=ln['id'], name=ln['name'], category=ln['category'],
                 bill_section=ln['bill_section'], unit=ln['unit'],
                 core=bool(ln.get('core_business_under_shared_savings')),
                 program_type=ln.get('program_type'), origin='starting_bill')
        if ln['unit'] == 'pct':
            d.update(pct=ln['rate'], applies_to=ln['applies_to'], month=None)
        elif ln['unit'] == '$/kWh':
            d['month'] = ln['rate'] * kwh
        else:
            d['month'] = ln['rate']
        out.append(d)
    if carve_out and fa.get('capacity_carve_out'):
        co = fa['capacity_carve_out']
        m = capacity_carve_out_month(co)
        parent = next(d for d in out if d['id'] == co['parent_line'])
        parent['month'] -= m
        out.append(dict(id='capacity_carved_out', name=f"Capacity (carved out of {parent['name']})",
                        category='capacity', bill_section=parent['bill_section'], unit='$/month',
                        core=False, program_type=None, month=m, origin='carve_out'))
    if adjustments:
        for adj in fa.get('starting_adjustments', []):
            out.append(dict(id=adj['id'], name=adj['name'], category=adj['category'],
                            bill_section=adj['bill_section'], unit='$/month', core=False,
                            program_type=None, month=adj['month'], origin='adjustment'))
    _apply_pct(out)
    return out


def capacity_carve_out_month(co):
    """
    $/month of capacity embedded in a parent line:
      obligation_kw = peak_mw x residential share x scaling / residential customers x 1000
      $/month       = obligation_kw x price ($/MW-day) / 1000 x 365 / 12
    The residential share of the obligation is assumed equal to its share of
    sales (co['residential_share'] source); see forward_assumptions notes.
    """
    kw = (co['peak_mw'] * co['residential_share'] * co.get('obligation_scaling', 1.0)
          / co['residential_customers'] * 1000)
    return kw * co['price_usd_per_mw_day'] / 1000 * 365 / 12


def _apply_pct(lines):
    """Fill month for percentage lines from the subtotals they apply to."""
    base = {'delivery': 0.0, 'supply': 0.0, 'distribution_and_transmission': 0.0}
    for d in lines:
        if d.get('pct') is not None:
            continue
        if d['bill_section'] in ('delivery', 'supply'):
            base[d['bill_section']] += d['month']
        if d['category'] in DIST_CATS + ('transmission',):
            base['distribution_and_transmission'] += d['month']
    for d in lines:
        if d.get('pct') is not None:
            d['month'] = base[d['applies_to']] * d['pct'] / 100


def by_category(lines):
    out = {c: 0.0 for c in CATEGORIES}
    for d in lines:
        out[d['category']] += d['month']
    return out


# ── Assumptions ──────────────────────────────────────────────────────────────

def resolve(fa, level='central', overrides=None, enabled=None):
    """
    Flatten forward_assumptions to {layer: {param: value}} at one level.
    overrides: {(layer, param): level_or_value}; enabled: {layer: bool}.
    Projection (non-layer) params sit under layer key 'projection'.
    """
    overrides = overrides or {}
    out = {'_enabled': {}}
    for lname, layer in list(fa['layers'].items()) + [('projection', {'params': fa['projection'],
                                                                      'enabled': True})]:
        vals = {}
        for pname, spec in layer.get('params', {}).items():
            key = (lname, pname)
            lev = overrides.get(key, level)
            if isinstance(spec, dict) and 'central' in spec:
                vals[pname] = spec[lev] if lev in LEVELS else lev
            else:
                vals[pname] = spec.get('value') if isinstance(spec, dict) else spec
        out[lname] = vals
        on = layer.get('enabled', True)
        if enabled is not None and lname in enabled:
            on = enabled[lname]
        out['_enabled'][lname] = bool(on)
    for h in HOOK_LAYERS:
        if out['_enabled'].get(h):
            raise NotImplementedError(f"layer {h!r} is a hook for a later step; keep it disabled")
    return out


def assumption_keys(fa):
    """(layer, param) for every low/central/high assumption, for tornado runs."""
    keys = []
    for lname, layer in list(fa['layers'].items()) + [('projection', {'params': fa['projection']})]:
        for pname, spec in layer.get('params', {}).items():
            if isinstance(spec, dict) and 'central' in spec and spec['low'] != spec['high']:
                keys.append((lname, pname))
    return keys


# ── Projection ───────────────────────────────────────────────────────────────

def _infl(r, t):
    return (1 + r) ** t


def _ev_count(params, year):
    curve = params['ev_adoption_curve']
    ys = sorted(curve)
    share = params.get('ev_territory_share') or params['electric_customers'] / 8_000_000
    return float(np.interp(year, ys, [curve[y] for y in ys])) * share


def system_path(params, a, on):
    """
    Layer 1. Sales (GWh), peak (MW) and forward capex ($M), BAU, by year.
    Off: sales and peak flat, capex held at the rate-case level.
    """
    s = a['system_needs']
    infl = a['projection']['inflation_rate']
    S0, P0 = params['annual_energy_gwh'], params['peak_demand_mw']
    dc0 = params.get('dc_load_mw_start', 0) or 0
    lf = s['dc_load_factor']
    dce0 = dc0 * 8.76 * lf
    N0 = S0 - dce0
    ev0 = _ev_count(params, YEARS[0])
    rows = []
    for t, y in enumerate(YEARS + [YEARS[-1] + 1]):
        if on:
            base = N0 * (1 + s['baseline_energy_growth']) ** t
            build = N0 * ((1 + s['buildings_electrification_growth']) ** t - 1)
            ev = (_ev_count(params, min(y, YEARS[-1])) - ev0) * s['ev_kwh_per_year'] / 1e6
            dc = dc0 * (1 + s['dc_growth']) ** t
            dce = dc * 8.76 * lf
            non_dc = base + build + ev
            peak = (P0 - dc0) * (non_dc / N0) ** s['peak_elasticity'] + dc
        else:
            base, build, ev, dc, dce, non_dc, peak = N0, 0.0, 0.0, dc0, dce0, N0, P0
        rows.append(dict(year=y, baseline_gwh=base, buildings_gwh=build, ev_gwh=ev, dc_mw=dc,
                         dc_gwh=dce, sales_gwh=non_dc + dce, peak_mw=peak, non_dc_peak=peak - dc))
    df = pd.DataFrame(rows)
    # Growth capex built one year ahead of load: next year's peak increment,
    # data-centre increment counted only through dc_distribution_share.
    dshare = params.get('dc_distribution_share', 0)
    d_non = df['non_dc_peak'].diff().shift(-1).fillna(0).clip(lower=0)
    d_dc = df['dc_mw'].diff().shift(-1).fillna(0).clip(lower=0)
    cost = s['dist_upgrade_cost_per_mw']
    growth = (d_non + d_dc * dshare) * cost * df.index.map(lambda t: _infl(infl, t))
    df = df.iloc[:-1].copy()
    growth = growth.iloc[:-1]
    capex0 = params['annual_capex_m']
    if on:
        cond0 = max(0.0, capex0 - growth.iloc[0])
        df['growth_capex_m'] = growth.values
        df['condition_capex_m'] = [cond0 * _infl(infl, t) for t in range(len(df))]
    else:
        df['growth_capex_m'] = 0.0
        df['condition_capex_m'] = capex0
    df['capex_m'] = df['growth_capex_m'] + df['condition_capex_m']
    return df


def _program_spend0(utility_json, params):
    """
    Today's system-wide spend on core-business program surcharges, $M/yr.
    annual_recovery_m where published; else derived = residential rate x total
    sales (assumes the residential $/kWh rate applies to all classes).
    """
    kwh_month = utility_json['starting_bill']['benchmark_kwh_month']
    total, parts = 0.0, []
    for ln in utility_json['starting_bill']['lines']:
        if not ln.get('core_business_under_shared_savings') or ln.get('rate') is None:
            continue
        if ln.get('annual_recovery_m') is not None:
            v, how = ln['annual_recovery_m'], 'annual_recovery_m'
        elif ln['unit'] == '$/kWh':
            v, how = ln['rate'] * params['annual_energy_gwh'], 'derived: rate x total sales'
        else:
            v, how = ln['rate'] * 12 * params['electric_customers'] / 1e6, 'derived: $/month x 12 x customers'
        total += v
        parts.append((ln['id'], v, how))
    return total, parts


def project_layers(utility_json, params, level='central', overrides=None, enabled=None,
                   pool_basis=None):
    """
    BAU and shared-savings projection with the given layer switches.

    utility_json : utility JSON (with starting_bill and forward_assumptions)
    params       : loaded utility params (notebook load_utility(): wacc, roe,
                   equity_ratio, property_tax_rate, total_revenue_m,
                   delivery_share_rr, ev_adoption_curve, ...)
    level        : 'low' | 'central' | 'high' for every assumption
    overrides    : {(layer, param): level or value}
    enabled      : {layer: bool}; default from the JSON
    pool_basis   : override mechanism pool_basis ('revenue_requirement' | 'capex')

    Returns dict with:
      'bau', 'ss'   : DataFrames by year: bill lines by category ($/month per
                      residential customer), total bill, system RR and costs ($M),
                      rate base, equity return, shared savings earnings
      'system'      : layer-1 sales, peak and capex path
      'assumptions' : resolved values
    """
    fa = utility_json['forward_assumptions']
    a = resolve(fa, level, overrides, enabled)
    on = a['_enabled']
    if pool_basis:
        a['mechanism']['pool_basis'] = pool_basis
    pj = a['projection']
    infl = pj['inflation_rate']
    sysdf = system_path(params, a, on['system_needs'])
    S = sysdf['sales_gwh'].values
    P = sysdf['peak_mw'].values
    S0, P0 = S[0], P[0]

    lines0 = starting_lines(utility_json)
    cat0 = by_category(lines0)
    dist0 = sum(d['month'] for d in lines0 if d['category'] in DIST_CATS)

    # Distribution revenue requirement (reuses the engine's 2026 build-up:
    # return at WACC + property tax + depreciation + recalibrated other O&M).
    rec = delivery_rr_reconciliation(params, {})
    om0 = max(0.0, rec['other_om_recalibrated_m'])
    wacc, ptr = params['wacc'], params['property_tax_rate']
    eq_roe = params['equity_ratio'] * params['roe']

    spend0, spend_parts = _program_spend0(utility_json, params)
    core0 = sum(d['month'] for d in lines0 if d['category'] == 'program_surcharge' and d['core'])

    cap = a['capacity']
    price0 = cap['price_m_per_mw_yr']
    deferral, programs, util, mech = a['deferral'], a['programs'], a['utilisation'], a['mechanism']
    trans_year = int(programs['transition_year'])

    res = {}
    for case in ('bau', 'ss'):
        ss = case == 'ss'
        L2 = ss and on['deferral']
        L3 = ss and on['programs']
        L4 = ss and on['utilisation']
        L5 = ss and on['capacity']
        L6 = ss and on['mechanism']
        rb = params['rate_base_start_m']
        reg_vint, reg_asset = [], 0.0
        deferred = []
        carry = 0.0
        u_idx = 1.0
        rows = []
        for t, y in enumerate(YEARS):
            g_s = S[t] / S[t - 1] - 1 if t else 0.0
            capex = sysdf['capex_m'].iloc[t]
            growth = sysdf['growth_capex_m'].iloc[t]
            # Layer 2: avoided growth capex, part re-entering after the deferral period
            avoided = payback = 0.0
            if L2:
                ramp = min(1.0, t / max(1, deferral['ramp_years']))
                share = deferral['avoidance_start'] + ramp * (deferral['avoidance_mature']
                                                              - deferral['avoidance_start'])
                avoided = growth * share
                deferred.append((y, avoided * deferral['deferral_fraction']))
                payback = sum(v for (yy, v) in deferred if y - yy == int(deferral['deferral_period_years']))
            # Layer 3: programs. BAU: surcharge-funded spend grows with sales and policy.
            bau_spend = spend0 * (S[t] / S0) * _infl(pj['program_surcharge_growth'], t)
            ss_spend = bau_spend * programs['spend_multiple'] if (L3 and y >= trans_year) else 0.0
            in_rr = L3 and y >= trans_year
            prog_opex = prog_amort = 0.0
            if in_rr:
                cap_frac = programs['capitalised_fraction']
                prog_opex = ss_spend * (1 - cap_frac)
                amort_years = int(programs['amortisation_years'])
                prog_amort = sum(v / amort_years for (yy, v) in reg_vint if 0 < y - yy <= amort_years)
                reg_vint.append((y, ss_spend * cap_frac))
                reg_asset = reg_asset - prog_amort + ss_spend * cap_frac
            rb_open = rb
            rb = rb * (1 - RATE_BASE_DECAY) + capex - avoided + payback
            rb_earning = rb + reg_asset
            ret = rb_earning * wacc
            ptax = rb * ptr * (1 + infl * 0.5) ** t
            dep = RATE_BASE_DECAY * rb_open
            om = om0 * _infl(infl, t)
            rr_core = ret + ptax + dep + om + prog_opex + prog_amort
            # Layer 5: capacity. MW of peak reduction = incremental flexible capture of
            # peak growth + MW delivered by the extra program spend.
            price = price0 * _infl(cap['price_growth'], t)
            mw_red = 0.0
            if L5:
                mw_red = cap['flex_capture_incremental'] * max(0.0, P[t] - P0)
                if in_rr:
                    mw_red += max(0.0, ss_spend - bau_spend) / (programs['cost_per_mw_yr'] * _infl(infl, t))
                mw_red = min(mw_red, P[t])
            cap_cost = (P[t] - mw_red) * price
            prog_bill_cost = 0.0 if in_rr else bau_spend   # surcharge collections
            # Layer 6: savings pool and the utility's shared savings earnings
            earnings = credit = 0.0
            pool = np.nan
            if ss:
                if mech['pool_basis'] == 'revenue_requirement':
                    pool = ((res['bau']['rr_core_m'].iloc[t] + res['bau']['program_bill_cost_m'].iloc[t]
                             + res['bau']['capacity_cost_m'].iloc[t])
                            - (rr_core + prog_bill_cost + cap_cost))
                else:   # 'capex': avoided capex net of extra program cost, plus capacity saving
                    pool = (avoided - max(0.0, ss_spend - (0.0 if not in_rr else bau_spend))
                            + (res['bau']['capacity_cost_m'].iloc[t] - cap_cost))
                if L6:
                    net = pool + carry
                    carry = min(0.0, net)
                    base = max(0.0, net)
                    earnings = mech['utility_share'] * base
                    if mech['pool_basis'] == 'capex':
                        credit = (1 - mech['utility_share']) * base   # v1.0-style credit (upper bound)
            rr = rr_core + (earnings if mech['pool_basis'] == 'revenue_requirement' else -credit)
            rr0 = rr if t == 0 and not ss else (res['bau']['rr_m'].iloc[0] if ss else rows[0]['rr_m'])
            # Bills ($/month per residential customer, benchmark usage)
            if L4:
                ramp = min(1.0, max(0.0, t / max(1, util['ramp_years'])))
                uc = util['share'] * (0.30 + 0.70 * ramp)
                u_idx *= (1 - uc * g_s)
            dist_bill = dist0 * (rr / rr0) * (S0 / S[t]) * u_idx
            lines = []
            for d in lines0:
                e = dict(d)
                c = d['category']
                if c in DIST_CATS:
                    e['month'] = dist_bill * d['month'] / dist0 if dist0 else 0.0
                elif c == 'program_surcharge':
                    e['month'] = 0.0 if (d['core'] and in_rr) else d['month'] * _infl(pj['program_surcharge_growth'], t)
                elif c == 'supply_energy':
                    e['month'] = d['month'] * _infl(pj['supply_energy_growth'], t)
                elif c == 'transmission':
                    e['month'] = d['month'] * _infl(pj['transmission_growth'], t)
                elif c == 'capacity':
                    e['month'] = (d['month'] * (price / price0) * (P[t] / P0) / (S[t] / S0)
                                  * (1 - mw_red / P[t]))
                elif c == 'taxes_and_fees' and d.get('pct') is None:
                    e['month'] = d['month']          # per-kWh / fixed taxes held at today's rate
                lines.append(e)
            _apply_pct(lines)
            cats = by_category(lines)
            rows.append(dict(year=y, **{f'bill_{c}': v for c, v in cats.items()},
                             bill_total=sum(cats.values()),
                             sales_gwh=S[t], peak_mw=P[t], capex_m=capex, avoided_capex_m=avoided,
                             deferred_payback_m=payback, rate_base_m=rb_earning,
                             regulatory_asset_m=reg_asset, rr_core_m=rr_core, rr_m=rr,
                             program_spend_m=(ss_spend if in_rr else bau_spend),
                             program_bill_cost_m=prog_bill_cost, peak_reduction_mw=mw_red,
                             capacity_price_m_per_mw_yr=price, capacity_cost_m=cap_cost,
                             savings_pool_m=pool, shared_savings_earnings_m=earnings,
                             customer_credit_m=credit, equity_return_m=rb_earning * eq_roe,
                             utility_earnings_m=rb_earning * eq_roe + earnings,
                             utilisation_index=u_idx))
        res[case] = pd.DataFrame(rows)
    return dict(bau=res['bau'], ss=res['ss'], system=sysdf, assumptions=a,
                program_spend0_m=spend0, program_spend0_parts=spend_parts,
                core_program_bill0=core0, starting_lines=lines0)


# ── Outputs ──────────────────────────────────────────────────────────────────

MILESTONES = (2026, 2030, 2035, 2050)


def _npv(v, years, r):
    return float(np.sum(np.asarray(v) / (1 + r) ** (np.asarray(years) - YEARS[0])))


def bill_table(run, years=MILESTONES):
    """Monthly bill by category, BAU vs shared savings, at milestone years ($/month nominal)."""
    rows = []
    for case, df in (('BAU', run['bau']), ('Shared savings', run['ss'])):
        for y in years:
            r = df[df['year'] == y].iloc[0]
            rows.append({'year': y, 'case': case, **{c: r[f'bill_{c}'] for c in CATEGORIES},
                         'total': r['bill_total']})
    return pd.DataFrame(rows).set_index(['year', 'case'])


def cumulative_savings(run):
    """Cumulative bill saving per residential customer 2026-2050 ($, nominal)."""
    d = (run['bau']['bill_total'] - run['ss']['bill_total']).values * 12
    return {'undiscounted nominal $': float(d.sum()),
            'NPV 3% (2026 $)': _npv(d, YEARS, 0.03), 'NPV 7% (2026 $)': _npv(d, YEARS, 0.07)}


def waterfall(utility_json, params, years=MILESTONES, level='central'):
    """
    BAU -> shared savings bill, one bar per layer, adding layers in order.
    Layer 1 (system needs) applies to both cases, so its bar is zero.
    Returns DataFrame: rows = years; columns BAU, each layer, Shared savings.
    """
    fa = utility_json['forward_assumptions']
    base_on = {l: fa['layers'][l].get('enabled', True) for l in LAYERS}
    state = {**base_on, **{l: False for l in SAVINGS_LAYERS}}
    prev = project_layers(utility_json, params, level, enabled=state)
    out = {y: {'BAU': prev['bau'].loc[prev['bau']['year'] == y, 'bill_total'].iloc[0],
               'system_needs': 0.0} for y in years}
    for l in SAVINGS_LAYERS:
        if not base_on[l]:
            for y in years:
                out[y][l] = 0.0
            continue
        state[l] = True
        cur = project_layers(utility_json, params, level, enabled=dict(state))
        for y in years:
            a = prev['ss'].loc[prev['ss']['year'] == y, 'bill_total'].iloc[0]
            b = cur['ss'].loc[cur['ss']['year'] == y, 'bill_total'].iloc[0]
            out[y][l] = b - a
        prev = cur
    for y in years:
        out[y]['Shared savings'] = prev['ss'].loc[prev['ss']['year'] == y, 'bill_total'].iloc[0]
    return pd.DataFrame(out).T


def ranges(utility_json, params, years=(2035, 2050)):
    """All-low, central, all-high: monthly bill BAU and shared savings, and cumulative saving."""
    rows = []
    for lev in LEVELS:
        r = project_layers(utility_json, params, lev)
        row = {'level': f'all-{lev}' if lev != 'central' else 'central'}
        for y in years:
            row[f'BAU {y}'] = r['bau'].loc[r['bau']['year'] == y, 'bill_total'].iloc[0]
            row[f'Shared savings {y}'] = r['ss'].loc[r['ss']['year'] == y, 'bill_total'].iloc[0]
        row.update({f'cum saving, {k}': v for k, v in cumulative_savings(r).items()})
        rows.append(row)
    return pd.DataFrame(rows).set_index('level')


def tornado(utility_json, params, years=(2035, 2050), measure='ss_bill'):
    """
    One-at-a-time sensitivity: each assumption at low and high, others central.
    measure: 'ss_bill' = shared-savings monthly bill; 'saving' = BAU minus
    shared-savings monthly bill (the reform's effect). Values are changes vs
    central, $/month nominal. Sorted by the swing in the last year.
    """
    def m(run, y):
        s = run['ss'].loc[run['ss']['year'] == y, 'bill_total'].iloc[0]
        if measure == 'ss_bill':
            return s
        return run['bau'].loc[run['bau']['year'] == y, 'bill_total'].iloc[0] - s

    fa = utility_json['forward_assumptions']
    c = project_layers(utility_json, params, 'central')
    cen = {y: m(c, y) for y in years}
    rows = []
    for key in assumption_keys(fa):
        row = {'layer': key[0], 'assumption': key[1]}
        for lev in ('low', 'high'):
            r = project_layers(utility_json, params, 'central', overrides={key: lev})
            for y in years:
                row[f'{lev} {y}'] = m(r, y) - cen[y]
        for y in years:
            row[f'swing {y}'] = abs(row[f'high {y}'] - row[f'low {y}'])
        rows.append(row)
    df = pd.DataFrame(rows)
    return df.sort_values(f'swing {years[-1]}', ascending=False).reset_index(drop=True), cen


def earnings_table(run):
    """Utility earnings ($M nominal): equity return + shared savings earnings, BAU vs shared savings."""
    b, s = run['bau'], run['ss']
    df = pd.DataFrame({'year': b['year'],
                       'BAU equity return': b['equity_return_m'],
                       'SS equity return': s['equity_return_m'],
                       'SS shared savings earnings': s['shared_savings_earnings_m']})
    df['SS total earnings'] = df['SS equity return'] + df['SS shared savings earnings']
    return df
