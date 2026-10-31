# engine/layers.py
# GridDividend layer engine — a separate, additive model. It does not change
# project(), run_named_scenario() or any v1.0 / CORRECTED result.
#
# Year zero is each utility's `starting_bill` (utilities/*.json): today's
# residential bill at benchmark usage, by line and category. Each category is
# projected 2026-2050 on its own driver, in two cases: BAU and SHARED SAVINGS.
# The difference is built from switchable layers whose low / central / high
# values live in the utility JSON `forward_assumptions`:
#
#   system_needs  load by segment, peak, growth vs asset-condition capex
#                 (shapes BAU and shared savings alike)
#   programs      core-business programs leave the bill and become utility
#                 OPEX / CAPEX. Spend = MW of flexible resources x cost per
#                 kW-year (demand response, managed EV charging, distributed
#                 storage, other DER) + energy efficiency (levelised $/kWh);
#                 today's surcharge-funded spend is the starting level.
#   deferral      the same MW (derated, locationally matched) avoid
#                 growth-driven capex
#   utilisation   flexible MW let more kWh flow over the same wires
#   capacity      derated MW (and EE peak) priced at the zonal capacity price
#   mechanism     utility share of the savings pool: shared savings earnings
#   hooks (off):  wholesale_energy, roe
#
# Two bill measures, $/month per residential customer, nominal:
#   bill_total      benchmark usage (residential_kwh_month) held constant
#   avg_bill_total  average residential bill: volumetric lines scaled by
#                   residential usage, which energy efficiency lowers
# System figures are $M per year.

import numpy as np
import pandas as pd

from .model import RATE_BASE_DECAY, delivery_rr_reconciliation

YEARS = list(range(2026, 2051))
LAYERS = ('system_needs', 'programs', 'deferral', 'utilisation', 'capacity', 'mechanism')
HOOK_LAYERS = ('wholesale_energy', 'roe')
SAVINGS_LAYERS = LAYERS[1:]                    # layers that separate shared savings from BAU
LEVELS = ('low', 'central', 'high')
SCENARIOS = ('Cautious', 'Central', 'Ambitious')
CATEGORIES = ('distribution_base', 'distribution_rider', 'program_surcharge', 'supply_energy',
              'capacity', 'transmission', 'taxes_and_fees')
DIST_CATS = ('distribution_base', 'distribution_rider')
FLEX_TYPES = ('dr', 'ev', 'storage', 'der')
FLEX_LABEL = {'dr': 'Demand response', 'ev': 'Managed EV charging', 'storage': 'Distributed storage',
              'der': 'Other DER', 'ee': 'Energy efficiency (peak)'}


# ── Year zero ────────────────────────────────────────────────────────────────

def starting_lines(utility_json, carve_out=True, adjustments=True):
    """
    Year-zero bill lines ($/month per residential customer, benchmark usage).
    carve_out: split a derived capacity line out of the parent line(s) where
      capacity is embedded (forward_assumptions['capacity_carve_out']); the
      total is unchanged.
    adjustments: add forward_assumptions['starting_adjustments'].
    Each line has 'volumetric' (True if it scales with usage).
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
                 program_type=ln.get('program_type'), origin='starting_bill',
                 volumetric=ln['unit'] == '$/kWh')
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
        parents = co.get('parents') or [{'line': co['parent_line'], 'share': 1.0}]
        section = None
        for par in parents:
            line = next(d for d in out if d['id'] == par['line'])
            line['month'] -= m * par['share']
            section = section or line['bill_section']
        out.append(dict(id='capacity_carved_out', name='Capacity (carved out: ' +
                        ', '.join(f"{p['line']} {p['share']:.0%}" for p in parents) + ')',
                        category='capacity', bill_section=section, unit='$/month', core=False,
                        program_type=None, month=m, origin='carve_out', volumetric=True))
    if adjustments:
        for adj in fa.get('starting_adjustments', []):
            out.append(dict(id=adj['id'], name=adj['name'], category=adj['category'],
                            bill_section=adj['bill_section'], unit='$/month', core=False,
                            program_type=None, month=adj['month'], origin='adjustment',
                            volumetric=adj.get('volumetric', True)))
    _apply_pct(out)
    return out


def capacity_carve_out_month(co):
    """
    $/month of capacity embedded in the parent line(s):
      obligation_kw = peak_mw x residential_share x obligation_scaling / residential_customers x 1000
      $/month       = obligation_kw x price ($/MW-day) / 1000 x 365 / 12
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

def _param_items(fa):
    yield 'projection', fa['projection']
    for lname, layer in fa['layers'].items():
        yield lname, layer.get('params', {})


def scenario_overrides(fa, scenario):
    """{(layer, param): level} for a named scenario in forward_assumptions['scenarios']."""
    if scenario in (None, 'Central'):
        return {}
    sc = fa['scenarios'][scenario]
    out = {}
    for lname, items in _param_items(fa):
        for pname, spec in items.items():
            if isinstance(spec, dict) and 'central' in spec:
                lev = sc['levels'].get(f'{lname}.{pname}',
                                       sc['levels'].get(lname, sc.get('default_level', 'central')))
                out[(lname, pname)] = lev
    return out


def resolve(fa, level='central', overrides=None, enabled=None, scenario=None):
    """
    Flatten forward_assumptions to {layer: {param: value}}.
    level applies to every low/central/high assumption; scenario (if given)
    sets levels per assumption; overrides {(layer, param): level or value}
    win over both. enabled {layer: bool} overrides the JSON switches.
    """
    ov = {}
    if scenario:
        ov.update(scenario_overrides(fa, scenario))
    ov.update(overrides or {})
    out = {'_enabled': {}}
    for lname, items in _param_items(fa):
        vals = {}
        for pname, spec in items.items():
            if isinstance(spec, dict) and 'central' in spec:
                lev = ov.get((lname, pname), level)
                vals[pname] = spec[lev] if lev in LEVELS else lev
            elif isinstance(spec, dict) and 'value' in spec:
                vals[pname] = ov.get((lname, pname), spec['value'])
            else:
                vals[pname] = spec
        out[lname] = vals
    for lname, layer in fa['layers'].items():
        on = layer.get('enabled', True)
        if enabled is not None and lname in enabled:
            on = enabled[lname]
        out['_enabled'][lname] = bool(on)
    for h in HOOK_LAYERS:
        if out['_enabled'].get(h):
            raise NotImplementedError(f"layer {h!r} is a hook for a later step; keep it disabled")
    return out


def assumption_keys(fa, layers_only=False):
    """(layer, param) for every low/central/high assumption with a spread."""
    keys = []
    for lname, items in _param_items(fa):
        if layers_only and lname == 'projection':
            continue
        for pname, spec in items.items():
            if isinstance(spec, dict) and 'central' in spec and spec['low'] != spec['high']:
                keys.append((lname, pname))
    return keys


# ── Projection helpers ───────────────────────────────────────────────────────

def _infl(r, t):
    return (1 + r) ** t


def system_path(params, a, on):
    """
    Layer 1. Sales (GWh), peak (MW) and forward capex ($M), BAU, by year.
    Total electrification energy growth is split between EVs and
    buildings/other by ev_share_of_electrification. Off: flat sales and peak,
    capex at the rate-case level.
    """
    s = a['system_needs']
    infl = a['projection']['inflation_rate']
    S0, P0 = params['annual_energy_gwh'], params['peak_demand_mw']
    dc0 = params.get('dc_load_mw_start', 0) or 0
    lf = s['dc_load_factor']
    dce0 = dc0 * 8.76 * lf
    N0 = S0 - dce0
    g_ev = s['electrification_growth'] * s['ev_share_of_electrification']
    g_bld = s['electrification_growth'] * (1 - s['ev_share_of_electrification'])
    rows = []
    for t, y in enumerate(YEARS + [YEARS[-1] + 1]):
        if on:
            base = N0 * (1 + s['baseline_energy_growth']) ** t
            ev = N0 * ((1 + g_ev) ** t - 1)
            build = N0 * ((1 + g_bld) ** t - 1)
            dc = dc0 * (1 + s['dc_growth']) ** t
            dce = dc * 8.76 * lf
            non_dc = base + build + ev
            peak = (P0 - dc0) * (non_dc / N0) ** s['peak_elasticity'] + dc
        else:
            base, build, ev, dc, dce, non_dc, peak = N0, 0.0, 0.0, dc0, dce0, N0, P0
        rows.append(dict(year=y, baseline_gwh=base, buildings_gwh=build, ev_gwh=ev, dc_mw=dc,
                         dc_gwh=dce, sales_gwh=non_dc + dce, peak_mw=peak, non_dc_peak=peak - dc))
    df = pd.DataFrame(rows)
    dshare = params.get('dc_distribution_share', 0)
    d_non = df['non_dc_peak'].diff().shift(-1).fillna(0).clip(lower=0)
    d_dc = df['dc_mw'].diff().shift(-1).fillna(0).clip(lower=0)
    growth = ((d_non + d_dc * dshare) * s['dist_upgrade_cost_per_mw']
              * df.index.map(lambda t: _infl(infl, t)))
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
    Today's system-wide spend on core-business program surcharges, $M/yr:
    annual_recovery_m where published; else derived = residential rate x total
    sales (assumes the residential $/kWh rate applies to all classes).
    """
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


def _share_path(pr, year):
    """Flexible MW as a share of peak: interpolate today (2026) -> 2030 -> 2035 -> 2050."""
    xs = [2026, 2030, 2035, 2050]
    ys = [pr['flex_share_2026'], pr['flex_share_2030'], pr['flex_share_2035'], pr['flex_share_2050']]
    return float(np.interp(year, xs, ys))


def flex_mw(pr, peak, year, active):
    """Nameplate MW by type: BAU holds today's share; shared savings follows the path when active."""
    share = _share_path(pr, year) if active else pr['flex_share_2026']
    return {t: peak * share * pr[f'split_{t}'] for t in FLEX_TYPES}


# ── Projection ───────────────────────────────────────────────────────────────

def project_layers(utility_json, params, level='central', overrides=None, enabled=None,
                   pool_basis=None, scenario=None, flex_cost_scale=1.0):
    """
    BAU and shared-savings projection.

    utility_json : utility JSON (starting_bill, forward_assumptions)
    params       : loaded utility params (notebook load_utility())
    level        : 'low' | 'central' | 'high' for every assumption
    scenario     : 'Cautious' | 'Central' | 'Ambitious' (forward_assumptions['scenarios'])
    overrides    : {(layer, param): level or value}
    enabled      : {layer: bool}; default from the JSON
    pool_basis   : override mechanism pool_basis
    flex_cost_scale : multiplies every flexible-resource cost per kW-year
                   (used to find the cost at which flexibility pays for itself)

    Returns dict: 'bau', 'ss' (yearly DataFrames), 'mw' (MW by resource type),
    'system', 'assumptions', and year-zero details.
    """
    fa = utility_json['forward_assumptions']
    a = resolve(fa, level, overrides, enabled, scenario)
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
    dist0 = sum(d['month'] for d in lines0 if d['category'] in DIST_CATS)

    rec = delivery_rr_reconciliation(params, {})
    om0 = max(0.0, rec['other_om_recalibrated_m'])
    wacc, ptr = params['wacc'], params['property_tax_rate']
    eq_roe = params['equity_ratio'] * params['roe']
    spend0, spend_parts = _program_spend0(utility_json, params)
    # Residential allocation of program costs moved into rates: keep today's
    # class split, i.e. the residential core-surcharge $/kWh relative to the
    # all-class average (spend0 / sales). 1.0 where spend0 was derived from
    # the residential rate.
    kwh_b = utility_json['starting_bill']['benchmark_kwh_month']
    core0 = sum(d['month'] for d in lines0 if d['category'] == 'program_surcharge' and d['core'])
    res_alloc = (core0 / kwh_b) / (spend0 / S0) if spend0 > 0 else 1.0

    pr, dfr, ut, cap, mech = a['programs'], a['deferral'], a['utilisation'], a['capacity'], a['mechanism']
    trans_year = int(pr['transition_year'])
    sys_lf = S0 / (P0 * 8.76)
    ee_kw_per_mwh = pr['ee_peak_coincidence'] / (8.76 * sys_lf)     # kW of peak per MWh/yr saved
    price0 = cap['price_m_per_mw_yr']
    cost_mw = a['system_needs']['dist_upgrade_cost_per_mw']

    res, mw_rows = {}, []
    for case in ('bau', 'ss'):
        ss = case == 'ss'
        Lp = ss and on['programs']
        Ld = ss and on['deferral']
        Lu = ss and on['utilisation']
        Lc = ss and on['capacity']
        Lm = ss and on['mechanism']
        rb = params['rate_base_start_m']
        reg_vint, reg_asset = [], 0.0
        deferred, carry = [], 0.0
        av_stock = 0.0
        ee_vint = []                      # (year, first-year GWh saved)
        u_idx = 1.0
        prev_firm = 0.0
        prev_S_case = None
        rr_ref = res['bau']['rr_m'].iloc[0] if ss else None
        rows = []
        for t, y in enumerate(YEARS):
            active = Lp and y >= trans_year
            # ── Programs: flexible MW and energy efficiency ───────────────────
            mw_b = flex_mw(pr, P[t], y, False)
            mw_s = flex_mw(pr, P[t], y, active)
            inc = {k: max(0.0, mw_s[k] - mw_b[k]) for k in FLEX_TYPES}
            flex_cost = {k: inc[k] * 1000 * pr[f'cost_kw_yr_{k}'] * flex_cost_scale * _infl(infl, t) / 1e6
                         for k in FLEX_TYPES}
            if active:
                ee_vint.append((y, S[t] * pr['ee_incremental_savings_pct']))
            life = int(pr['ee_measure_life'])
            ee_gwh = sum(g for (yy, g) in ee_vint if 0 <= y - yy < life)
            ee_cost = ee_gwh * pr['ee_levelised_cost_kwh'] * _infl(infl, t)       # GWh x $/kWh = $M
            ee_mw = ee_gwh * ee_kw_per_mwh                                       # GWh x kW/MWh = MW
            S_case = S[t] - ee_gwh
            bau_spend = spend0 * (S[t] / S0) * _infl(pj['program_surcharge_growth'], t)
            new_spend = (sum(flex_cost.values()) + ee_cost) if active else 0.0
            ss_spend = bau_spend + new_spend if active else 0.0
            cap_amt = (sum(flex_cost[k] * pr[f'capitalised_{k}'] for k in FLEX_TYPES)
                       + ee_cost * pr['ee_capitalised']
                       + bau_spend * pr['existing_capitalised']) if active else 0.0
            prog_opex = (ss_spend - cap_amt) if active else 0.0
            amort_years = int(pr['amortisation_years'])
            prog_amort = sum(v / amort_years for (yy, v) in reg_vint if 0 < y - yy <= amort_years)
            if active:
                reg_vint.append((y, cap_amt))
            reg_asset = reg_asset - prog_amort + cap_amt
            firm_flex = sum(inc[k] * pr[f'derate_{k}'] for k in FLEX_TYPES)
            firm = firm_flex + ee_mw
            # ── Deferral: firm MW, locationally matched, against growth capex ─
            growth = sysdf['growth_capex_m'].iloc[t]
            capex = sysdf['capex_m'].iloc[t]
            avoided = payback = 0.0
            if Ld:
                new_firm = max(0.0, firm - prev_firm)
                avoided = min(growth, new_firm * dfr['locational_match'] * cost_mw * _infl(infl, t))
                deferred.append((y, avoided * dfr['deferral_fraction']))
                payback = sum(v for (yy, v) in deferred if y - yy == int(dfr['deferral_period_years']))
            prev_firm = firm
            rb_open = rb
            rb = rb * (1 - RATE_BASE_DECAY) + capex - avoided + payback
            av_stock = av_stock * (1 - RATE_BASE_DECAY) + avoided - payback
            rb_earning = rb + reg_asset
            ptax = rb * ptr * (1 + infl * 0.5) ** t
            dep = RATE_BASE_DECAY * rb_open
            om = om0 * _infl(infl, t)
            rr_dist = rb * wacc + ptax + dep + om                 # wires revenue requirement
            prog_rr = prog_opex + prog_amort + reg_asset * wacc   # core programs in rates
            rr_core = rr_dist + prog_rr
            # ── Capacity ─────────────────────────────────────────────────────
            price = price0 * _infl(cap['price_growth'], t)
            mw_red = min(firm, P[t]) if Lc else 0.0
            cap_cost = (P[t] - mw_red) * price
            prog_bill_cost = 0.0 if active else bau_spend
            # ── Mechanism ────────────────────────────────────────────────────
            earnings = credit = 0.0
            pool = np.nan
            if ss:
                if mech['pool_basis'] == 'revenue_requirement':
                    pool = ((res['bau']['rr_core_m'].iloc[t] + res['bau']['program_bill_cost_m'].iloc[t]
                             + res['bau']['capacity_cost_m'].iloc[t])
                            - (rr_core + prog_bill_cost + cap_cost))
                else:   # 'capex': avoided capex net of new program spend, plus capacity saving
                    pool = avoided - new_spend + (res['bau']['capacity_cost_m'].iloc[t] - cap_cost)
                if Lm:
                    net = pool + carry
                    carry = min(0.0, net)
                    base = max(0.0, net)
                    earnings = mech['utility_share'] * base
                    if mech['pool_basis'] == 'capex':
                        credit = (1 - mech['utility_share']) * base
            adj = earnings if mech['pool_basis'] == 'revenue_requirement' else -credit
            rr = rr_core + adj
            if not ss and t == 0:
                rr_ref = rr_dist
            # ── Utilisation ──────────────────────────────────────────────────
            uc = 0.0
            if Lu and prev_S_case:
                g_s = S_case / prev_S_case - 1
                uc = min(ut['max_share'], ut['per_flex_share'] * firm_flex / P[t])
                u_idx *= (1 - uc * max(0.0, g_s))
            prev_S_case = S_case
            # ── Bills ────────────────────────────────────────────────────────
            usage = S_case / S[t]                       # residential usage vs BAU (EE lowers it)
            # Wires: distribution lines indexed to the wires RR per kWh. Core program
            # costs and the utility's shared savings earnings (or the capex-basis
            # customer credit) are recovered per kWh with today's residential
            # allocation of the core surcharges (res_alloc).
            dist_bill = dist0 * (rr_dist / rr_ref) * (S0 / S_case) * u_idx
            rider = dict(id='core_program_and_earnings_recovery',
                         name='Core programs and shared savings earnings (uniform $/kWh)',
                         category='program_surcharge', bill_section='delivery', unit='$/kWh', core=False,
                         program_type=None, origin='projection', volumetric=True,
                         month=(prog_rr + adj) / S_case * kwh_b * res_alloc)
            bench, avg = [], []
            for d in lines0 + [rider]:
                e = dict(d)
                c = d['category']
                if d['origin'] == 'projection':
                    pass
                elif c in DIST_CATS:
                    e['month'] = dist_bill * d['month'] / dist0 if dist0 else 0.0
                elif c == 'program_surcharge':
                    e['month'] = (0.0 if (d['core'] and active)
                                  else d['month'] * _infl(pj['program_surcharge_growth'], t))
                elif c == 'supply_energy':
                    e['month'] = d['month'] * _infl(pj['supply_energy_growth'], t)
                elif c == 'transmission':
                    e['month'] = d['month'] * _infl(pj['transmission_growth'], t)
                elif c == 'capacity':
                    e['month'] = d['month'] * (price / price0) * ((P[t] - mw_red) / P0) / (S_case / S0)
                elif c == 'taxes_and_fees' and d.get('pct') is None:
                    e['month'] = d['month']
                bench.append(e)
                f = dict(e)
                if f.get('pct') is None and d.get('volumetric'):
                    f['month'] = e['month'] * usage
                avg.append(f)
            _apply_pct(bench)
            _apply_pct(avg)
            cb, ca = by_category(bench), by_category(avg)
            rows.append(dict(
                year=y, **{f'bill_{c}': v for c, v in cb.items()}, bill_total=sum(cb.values()),
                **{f'avg_bill_{c}': v for c, v in ca.items()}, avg_bill_total=sum(ca.values()),
                residential_usage_index=usage, sales_gwh=S_case, ee_gwh=ee_gwh, peak_mw=P[t],
                capex_m=capex, growth_capex_m=growth, avoided_capex_m=avoided,
                deferred_payback_m=payback, avoided_rb_stock_m=av_stock,
                rate_base_m=rb_earning, regulatory_asset_m=reg_asset, rr_dist_m=rr_dist,
                program_rr_m=prog_rr, rr_core_m=rr_core, rr_m=rr,
                program_spend_m=(ss_spend if active else bau_spend), new_program_spend_m=new_spend,
                flex_spend_m=sum(flex_cost.values()) if active else 0.0,
                ee_spend_m=ee_cost if active else 0.0,
                program_bill_cost_m=prog_bill_cost, firm_mw=firm, firm_flex_mw=firm_flex, ee_mw=ee_mw,
                flex_mw_incremental=sum(inc.values()), peak_reduction_mw=mw_red,
                capacity_price_m_per_mw_yr=price, capacity_cost_m=cap_cost,
                savings_pool_m=pool, shared_savings_earnings_m=earnings, customer_credit_m=credit,
                equity_return_m=rb_earning * eq_roe, utility_earnings_m=rb_earning * eq_roe + earnings,
                utilisation_share=uc, utilisation_index=u_idx))
            if ss:
                mw_rows.append(dict(year=y, **{f'{k}_bau_mw': mw_b[k] for k in FLEX_TYPES},
                                    **{f'{k}_ss_mw': mw_s[k] for k in FLEX_TYPES},
                                    **{f'{k}_incremental_mw': inc[k] for k in FLEX_TYPES},
                                    ee_peak_mw=ee_mw, ee_gwh=ee_gwh,
                                    flex_share_of_peak_ss=sum(mw_s.values()) / P[t],
                                    firm_mw=firm, peak_mw=P[t]))
        res[case] = pd.DataFrame(rows)
    return dict(bau=res['bau'], ss=res['ss'], mw=pd.DataFrame(mw_rows), system=sysdf, assumptions=a,
                program_spend0_m=spend0, program_spend0_parts=spend_parts, starting_lines=lines0,
                ee_kw_per_mwh=ee_kw_per_mwh, residential_program_allocation=res_alloc)


# ── Outputs ──────────────────────────────────────────────────────────────────

MILESTONES = (2026, 2030, 2035, 2050)
MEASURE_COL = {'average': 'avg_bill_total', 'benchmark': 'bill_total'}


def _at(df, y, col):
    return float(df.loc[df['year'] == y, col].iloc[0])


def _npv(v, years, r):
    return float(np.sum(np.asarray(v) / (1 + r) ** (np.asarray(years) - YEARS[0])))


def bill_table(run, years=MILESTONES, measure='average'):
    """Monthly residential bill by category, BAU vs shared savings ($/month nominal)."""
    pre = 'avg_bill_' if measure == 'average' else 'bill_'
    rows = []
    for case, df in (('BAU', run['bau']), ('Shared savings', run['ss'])):
        for y in years:
            r = df[df['year'] == y].iloc[0]
            rows.append({'year': y, 'case': case, **{c: r[f'{pre}{c}'] for c in CATEGORIES},
                         'total': r[f'{pre}total']})
    return pd.DataFrame(rows).set_index(['year', 'case'])


def cumulative_savings(run, measure='average'):
    """Cumulative bill saving per residential customer 2026-2050 ($, nominal)."""
    col = MEASURE_COL[measure]
    d = (run['bau'][col] - run['ss'][col]).values * 12
    return {'undiscounted nominal $': float(d.sum()),
            'NPV 3% (2026 $)': _npv(d, YEARS, 0.03), 'NPV 7% (2026 $)': _npv(d, YEARS, 0.07)}


def waterfall(utility_json, params, years=MILESTONES, measure='average', scenario=None):
    """
    BAU -> shared-savings bill, one bar per layer, adding layers in LAYERS order.
    System needs applies to both cases, so its bar is zero.
    """
    col = MEASURE_COL[measure]
    fa = utility_json['forward_assumptions']
    base_on = {l: fa['layers'][l].get('enabled', True) for l in LAYERS}
    state = {**base_on, **{l: False for l in SAVINGS_LAYERS}}
    prev = project_layers(utility_json, params, enabled=state, scenario=scenario)
    out = {y: {'BAU': _at(prev['bau'], y, col), 'system_needs': 0.0} for y in years}
    for l in SAVINGS_LAYERS:
        if not base_on[l]:
            for y in years:
                out[y][l] = 0.0
            continue
        state[l] = True
        cur = project_layers(utility_json, params, enabled=dict(state), scenario=scenario)
        for y in years:
            out[y][l] = _at(cur['ss'], y, col) - _at(prev['ss'], y, col)
        prev = cur
    for y in years:
        out[y]['Shared savings'] = _at(prev['ss'], y, col)
    return pd.DataFrame(out).T


def scenario_table(utility_json, params, years=(2035, 2050), measure='average'):
    """Cautious / Central / Ambitious: BAU and shared-savings bills and cumulative saving."""
    col = MEASURE_COL[measure]
    rows = []
    for sc in SCENARIOS:
        r = project_layers(utility_json, params, scenario=sc)
        row = {'scenario': sc}
        for y in years:
            row[f'BAU {y}'] = _at(r['bau'], y, col)
            row[f'Shared savings {y}'] = _at(r['ss'], y, col)
        row.update({f'cum saving, {k}': v for k, v in cumulative_savings(r, measure).items()})
        rows.append(row)
    return pd.DataFrame(rows).set_index('scenario')


def tornado(utility_json, params, years=(2035, 2050), measure='average'):
    """
    One-at-a-time sensitivity on the SAVING (BAU minus shared-savings monthly
    bill): each assumption at low and high, others central. Values are changes
    vs the central saving, $/month nominal. Sorted by the last year's swing.
    """
    col = MEASURE_COL[measure]

    def sav(run, y):
        return _at(run['bau'], y, col) - _at(run['ss'], y, col)

    fa = utility_json['forward_assumptions']
    c = project_layers(utility_json, params)
    cen = {y: sav(c, y) for y in years}
    rows = []
    for key in assumption_keys(fa):
        row = {'layer': key[0], 'assumption': key[1]}
        for lev in ('low', 'high'):
            r = project_layers(utility_json, params, overrides={key: lev})
            for y in years:
                row[f'{lev} {y}'] = sav(r, y) - cen[y]
        for y in years:
            row[f'swing {y}'] = abs(row[f'high {y}'] - row[f'low {y}'])
        rows.append(row)
    df = pd.DataFrame(rows)
    return df.sort_values(f'swing {years[-1]}', ascending=False).reset_index(drop=True), cen


def mw_table(run, years=(2030, 2035, 2050)):
    """MW by resource type (shared savings and incremental over BAU) and share of peak."""
    m = run['mw']
    rows = []
    for y in years:
        r = m[m['year'] == y].iloc[0]
        row = {'year': y}
        for k in FLEX_TYPES:
            row[f'{FLEX_LABEL[k]} MW (SS)'] = r[f'{k}_ss_mw']
            row[f'{FLEX_LABEL[k]} MW (incremental)'] = r[f'{k}_incremental_mw']
        row['EE peak MW'] = r['ee_peak_mw']
        row['Flexible share of peak (SS)'] = r['flex_share_of_peak_ss']
        row['Firm MW (derated flex + EE)'] = r['firm_mw']
        row['Peak MW (BAU)'] = r['peak_mw']
        rows.append(row)
    return pd.DataFrame(rows).set_index('year')


def value_stack(run, params, years=(2030, 2035, 2050)):
    """
    Flexible resources only (DR, managed EV, storage, other DER), per year:
    cost per kW-year (nameplate, nominal) vs value per kW-year:
      capacity    = derated flexible MW x capacity price
      deferral    = flexible share of firm MW x RR value of avoided rate base
                    (avoided stock x [WACC + property tax rate + depreciation rate])
      utilisation = wires revenue requirement x (1 - utilisation index)
    """
    s = run['ss']
    wacc, ptr = params['wacc'], params['property_tax_rate']
    rows = []
    for y in years:
        r = s[s['year'] == y].iloc[0]
        kw = r['flex_mw_incremental'] * 1000
        if kw <= 0:
            rows.append({'year': y, 'flexible kW (incremental)': 0.0})
            continue
        flex_frac = r['firm_flex_mw'] / r['firm_mw'] if r['firm_mw'] > 0 else 0.0
        capv = min(r['firm_flex_mw'], r['peak_reduction_mw']) * r['capacity_price_m_per_mw_yr'] * 1e6
        defv = flex_frac * r['avoided_rb_stock_m'] * (wacc + ptr + RATE_BASE_DECAY) * 1e6
        utilv = r['rr_dist_m'] * (1 - r['utilisation_index']) * 1e6
        cost = r['flex_spend_m'] * 1e6
        rows.append({'year': y, 'flexible kW (incremental)': kw,
                     'cost $/kW-yr': cost / kw, 'capacity value $/kW-yr': capv / kw,
                     'deferral value $/kW-yr': defv / kw, 'utilisation value $/kW-yr': utilv / kw,
                     'total value $/kW-yr': (capv + defv + utilv) / kw})
    return pd.DataFrame(rows).set_index('year')


def weighted_flex_cost(utility_json, scenario=None):
    """MW-weighted flexible cost per kW-year, 2026 $, at the resolved assumptions."""
    pr = resolve(utility_json['forward_assumptions'], scenario=scenario)['programs']
    w = {k: pr[f'split_{k}'] for k in FLEX_TYPES}
    return sum(w[k] * pr[f'cost_kw_yr_{k}'] for k in FLEX_TYPES) / sum(w.values())


def flex_pays_cost(utility_json, params, target='npv3', scenario=None, measure='average',
                   lo=0.0, hi=20.0, tol=1e-3):
    """
    Cost at which flexibility pays for itself: the MW-weighted flexible cost
    per kW-year (2026 $) at which the shared-savings bill equals BAU.
    target: a year (int) -> monthly bill equal in that year; 'npv3' ->
    cumulative 2026-2050 saving at 3% NPV equal to zero. All flexible costs
    are scaled together (bisection). Returns (cost or None, note).
    """
    col = MEASURE_COL[measure]
    base = weighted_flex_cost(utility_json, scenario)

    def gap(k):
        r = project_layers(utility_json, params, scenario=scenario, flex_cost_scale=k)
        if target == 'npv3':
            return cumulative_savings(r, measure)['NPV 3% (2026 $)']
        return _at(r['bau'], target, col) - _at(r['ss'], target, col)

    if gap(lo) < 0:
        return None, 'shared savings costs more than BAU even with free flexibility'
    if gap(hi) > 0:
        return base * hi, f'pays for itself at every cost tested (>= ${base * hi:,.0f}/kW-yr)'
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if gap(mid) > 0:
            lo = mid
        else:
            hi = mid
    return base * (lo + hi) / 2, 'bisection'


def earnings_table(run):
    """Utility earnings ($M nominal): equity return + shared savings earnings, BAU vs shared savings."""
    b, s = run['bau'], run['ss']
    df = pd.DataFrame({'year': b['year'],
                       'BAU equity return': b['equity_return_m'],
                       'SS equity return': s['equity_return_m'],
                       'SS shared savings earnings': s['shared_savings_earnings_m']})
    df['SS total earnings'] = df['SS equity return'] + df['SS shared savings earnings']
    return df
