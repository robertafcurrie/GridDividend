# engine/layers.py
# GridDividend layer engine — a separate, additive model. It does not change
# project(), run_named_scenario() or any v1.0 / CORRECTED result.
#
# The distribution network has explicit firm capacity: it grows only through
# reinforcement (lead time, maximum build rate); load above capacity waits for
# the upgrade (the Upgrade Delay for Interconnection: the time a new customer in
# a constrained area waits for the grid upgrade before connecting).
# The network is split into loading bands (groups of substations from most to
# least loaded, `network.bands`); constraints, upgrade delay, deferral and
# load enabled are computed per band and summed. No bands = one band at the
# planning target (the single-pool model). Every headroom input lives in the
# `network` block of forward_assumptions (bands, planning limit, constrained
# sub-band, upgrade delays and backlog clearance, lead time, build rate, seed
# pipeline, flexibility targeting), set
# at three levels, highest wins: notebook override (NETWORK_OVERRIDES) >
# scenario `network` values > the utility JSON.
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
#   deferral      flexible headroom (firm MW x locational match) counted by
#                 the network planner, so reinforcement is ordered later
#   load_enabled  flexible headroom lets load waiting for network capacity
#                 connect sooner, spreading fixed wires costs over more kWh
#                 (each MW of headroom has one use: deferral OR load enabled)
#   capacity      derated MW (and EE peak) priced at the zonal capacity price
#   wholesale_energy  flexible load shifted from on-peak to off-peak hours
#   transmission  transmission cost avoided by peak reduction
#   losses        marginal distribution losses avoided (energy and peak)
#   mechanism     utility share of the savings pool: shared savings earnings
#   roe           allowed ROE vs BAU (a separate lever, outside the pool)
#
# The full methodology is in docs/METHODOLOGY.md.
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
LAYERS = ('system_needs', 'programs', 'deferral', 'load_enabled', 'capacity', 'wholesale_energy', 'transmission',
          'losses', 'mechanism', 'roe')
VALUE_LAYERS = ('wholesale_energy', 'transmission', 'losses')     # value streams added in the shared-savings pool
SAVINGS_LAYERS = LAYERS[1:]                    # layers that separate shared savings from BAU
LEVELS = ('low', 'central', 'high')
SCENARIOS = ('Cautious', 'Central', 'Ambitious')
CATEGORIES = ('distribution_base', 'distribution_rider', 'program_surcharge', 'supply_energy',
              'capacity', 'transmission', 'taxes_and_fees')
DIST_CATS = ('distribution_base', 'distribution_rider')
FLEX_TYPES = ('dr', 'ev', 'storage', 'der')
UD = 'Upgrade Delay for Interconnection'
# Network inputs formerly in system_needs (older forward_assumptions without a
# `network` block are read from there; network_bands -> bands)
_LEGACY_NETWORK = {'planning_headroom': 'planning_headroom', 'reinforcement_lead_years': 'reinforcement_lead_years',
                   'max_build_pct': 'max_build_pct', 'constrained_loading': 'constrained_loading',
                   'network_bands': 'bands'}
# Notebook-level network override {param: value or level}: wins over the
# scenario `network` values and the JSON. Set from the notebook's layer section.
NETWORK_OVERRIDES = {}
FLEX_LABEL = {'dr': 'Demand response', 'ev': 'Managed EV charging', 'storage': 'Distributed storage',
              'der': 'Other DER', 'ee': 'Energy efficiency (peak)'}


# ── Year zero ────────────────────────────────────────────────────────────────

def starting_lines(utility_json, carve_out=True, adjustments=True):
    """
    Year-zero bill lines for one utility.

    Inputs: utility_json (parsed utilities/*.json; reads starting_bill and
      forward_assumptions); carve_out: split a derived capacity line out of the
      parent line(s) where capacity is embedded (forward_assumptions
      ['capacity_carve_out']; the total is unchanged); adjustments: add
      forward_assumptions['starting_adjustments'].
    Output: list of dicts, one per line included in the benchmark, with id, name,
      category, bill_section, unit, core (core business under shared savings),
      program_type, origin ('starting_bill' / 'carve_out' / 'adjustment'),
      volumetric (True if it scales with usage) and month ($/month per
      residential customer at benchmark usage, nominal 2026 $). Percentage lines
      also carry pct and applies_to; their month is filled from the subtotal.
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
    $/month of capacity embedded in the parent line(s), per residential customer.

    Input: co = forward_assumptions['capacity_carve_out'] (peak_mw, MW;
      residential_share, share; obligation_scaling, factor; residential_customers;
      price_usd_per_mw_day, $/MW-day).
    Output: float, $/month (2026 $):
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
    """
    Sum bill lines by category.

    Input: lines, as returned by starting_lines() (each with category and month).
    Output: {category: $/month} for every category in CATEGORIES (zero if absent).
    """
    out = {c: 0.0 for c in CATEGORIES}
    for d in lines:
        out[d['category']] += d['month']
    return out


# ── Assumptions ──────────────────────────────────────────────────────────────

def network_block(fa):
    """
    The network inputs of forward_assumptions.

    Input: fa = utility_json['forward_assumptions'].
    Output: {param: spec} from fa['network']['params']; for older JSON without a
      network block, the network inputs read from layers.system_needs
      (network_bands -> bands). Specs are unresolved (see resolve()).
    """
    if 'network' in fa:
        return fa['network'].get('params', {})
    sn = fa['layers'].get('system_needs', {}).get('params', {})
    return {new: sn[old] for old, new in _LEGACY_NETWORK.items() if old in sn}


def _param_items(fa):
    yield 'projection', fa['projection']
    legacy = 'network' not in fa
    for lname, layer in fa['layers'].items():
        items = layer.get('params', {})
        if legacy and lname == 'system_needs':
            items = {k: v for k, v in items.items() if k not in _LEGACY_NETWORK}
        yield lname, items
    yield 'network', network_block(fa)
    if 'bau_plan' in fa:
        yield 'bau_plan', fa['bau_plan'].get('params', {})


def scenario_overrides(fa, scenario):
    """
    Overrides that define a named scenario.

    Inputs: fa = forward_assumptions; scenario = 'Cautious' / 'Central' /
      'Ambitious' (or None).
    Output: {(layer, param): level} for every low/central/high assumption, from
      the scenario's levels (per 'layer.param', then per layer, then
      default_level), plus {('network', param): value or level} from the
      scenario's own network values. Central returns only its network values.
    """
    if scenario is None:
        return {}
    sc = fa['scenarios'][scenario]
    net = {('network', k): v for k, v in sc.get('network', {}).items() if not k.startswith('_')}
    if scenario == 'Central':
        return net
    out = {}
    for lname, items in _param_items(fa):
        for pname, spec in items.items():
            if isinstance(spec, dict) and 'central' in spec:
                lev = sc['levels'].get(f'{lname}.{pname}',
                                       sc['levels'].get(lname, sc.get('default_level', 'central')))
                out[(lname, pname)] = lev
    out.update(net)
    return out


def resolve(fa, level='central', overrides=None, enabled=None, scenario=None, network=None):
    """
    Flatten forward_assumptions to the values used in one run.

    Inputs: fa = forward_assumptions; level = 'low' / 'central' / 'high' for every
      range; scenario (see scenario_overrides()); overrides {(layer, param):
      level or value}; network {param: level or value} (per call, e.g. the
      headroom sweep); enabled {layer: bool} overrides the JSON switches.
    Precedence, lowest to highest: level < scenario levels and network values <
      NETWORK_OVERRIDES (notebook) < overrides < network.
    Output: {layer: {param: value}} with network inputs under 'network', the
      projection under 'projection', and '_enabled': {layer: bool}. Units are
      those of each spec. Raises NotImplementedError if a placeholder (hook)
      layer is enabled.
    """
    ov = {}
    if scenario:
        ov.update(scenario_overrides(fa, scenario))
    ov.update({('network', k): v for k, v in NETWORK_OVERRIDES.items()})
    ov.update(overrides or {})
    ov.update({('network', k): v for k, v in (network or {}).items()})
    out = {'_enabled': {}}
    for lname, items in _param_items(fa):
        vals = {}
        for pname, spec in items.items():
            if isinstance(spec, dict) and 'central' in spec:
                lev = ov.get((lname, pname), level)
                vals[pname] = spec[lev] if (isinstance(lev, str) and lev in LEVELS) else lev
            elif isinstance(spec, dict) and 'value' in spec:
                vals[pname] = ov.get((lname, pname), spec['value'])
            else:
                vals[pname] = spec
        for (l2, p2), v in ov.items():           # overrides of inputs the JSON leaves out
            if l2 == lname and p2 not in items and lname == 'network':
                vals[p2] = v
        out[lname] = vals
    for lname, layer in fa['layers'].items():
        on = layer.get('enabled', True)
        if enabled is not None and lname in enabled:
            on = enabled[lname]
        out['_enabled'][lname] = bool(on)
    for lname, layer in fa['layers'].items():
        if layer.get('hook') and out['_enabled'].get(lname):
            raise NotImplementedError(f"layer {lname!r} is a placeholder in this forward_assumptions; keep it disabled")
    return out


def assumption_keys(fa, layers_only=False):
    """
    The assumptions the tornado varies.

    Inputs: fa = forward_assumptions; layers_only: drop the projection block.
    Output: list of (layer, param) for every low/central/high spec whose low and
      high differ.
    """
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
    Layer 1 (system needs): BAU demand path by year, 2026-2050.

    Inputs: params (earlier-model utility dict: annual_energy_gwh, GWh;
      peak_demand_mw, MW; dc_load_mw_start, MW; dc_distribution_share, share);
      a = resolve() output (system_needs growth rates per year, shares,
      dc_load_factor, peak_elasticity); on: layer switch (off = flat demand).
    Output: DataFrame, one row per year: baseline_gwh, buildings_gwh, ev_gwh,
      dc_gwh, sales_gwh (GWh); dc_mw; peak_mw (system peak, MW, for capacity
      markets); net_peak_mw (distribution-network peak, MW: non-data-centre peak +
      the distribution-connected share of data-centre load); ev_peak_mw,
      elec_peak_mw (peak added by EVs / all electrification, MW); dc_dist_new_mw
      (new distribution-connected data-centre MW). Electrification energy growth
      is split between EVs and buildings by ev_share_of_electrification; non-data-
      centre peak = (P0 - DC0) x (energy / energy0) ^ peak_elasticity.
    """
    s = a['system_needs']
    S0, P0 = params['annual_energy_gwh'], params['peak_demand_mw']
    dc0 = params.get('dc_load_mw_start', 0) or 0
    dshare = params.get('dc_distribution_share', 0)
    lf = s['dc_load_factor']
    N0 = S0 - dc0 * 8.76 * lf
    g_ev = s['electrification_growth'] * s['ev_share_of_electrification']
    g_bld = s['electrification_growth'] * (1 - s['ev_share_of_electrification'])
    e = s['peak_elasticity']
    rows = []
    for t, y in enumerate(YEARS):
        if on:
            base = N0 * (1 + s['baseline_energy_growth']) ** t
            ev = N0 * ((1 + g_ev) ** t - 1)
            build = N0 * ((1 + g_bld) ** t - 1)
            dc = dc0 * (1 + s['dc_growth']) ** t
        else:
            base, build, ev, dc = N0, 0.0, 0.0, dc0
        non_dc_e = base + build + ev
        non_dc_pk = (P0 - dc0) * (non_dc_e / N0) ** e
        ev_pk = non_dc_pk - (P0 - dc0) * ((base + build) / N0) ** e
        elec_pk = non_dc_pk - (P0 - dc0) * (base / N0) ** e
        rows.append(dict(year=y, baseline_gwh=base, buildings_gwh=build, ev_gwh=ev, dc_mw=dc,
                         dc_gwh=dc * 8.76 * lf, sales_gwh=non_dc_e + dc * 8.76 * lf,
                         peak_mw=non_dc_pk + dc, net_peak_mw=non_dc_pk + dc * dshare,
                         ev_peak_mw=ev_pk, elec_peak_mw=elec_pk,
                         dc_dist_new_mw=max(0.0, dc - dc0) * dshare))
    return pd.DataFrame(rows)


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


def flex_mw(pr, year, active):
    """
    Nameplate flexible MW by resource type in one year.

    Inputs: pr = resolved programs params (mw_start_*, mw_2035_*, mw_2050_*, MW);
      year; active: shared savings with programs in force.
    Output: {type: MW} for FLEX_TYPES (dr, ev, storage, der). BAU (not active)
      holds today's programs; active interpolates linearly 2026 -> 2035 -> 2050.
      The ramp limit is applied in project_layers().
    """
    out = {}
    for k in FLEX_TYPES:
        start = pr[f'mw_start_{k}']
        out[k] = (float(np.interp(year, [2026, 2035, 2050], [start, pr[f'mw_2035_{k}'], pr[f'mw_2050_{k}']]))
                  if active else start)
    return out


def _seed_pipeline(D, h, lead):
    """Projects already under way at 2026: the next `lead` years of growth, keeping headroom."""
    return [(YEARS[i], max(0.0, (D[i + 1] - D[i]) * (1 + h))) for i in range(min(lead, len(D) - 1))]


def _seed_from(nw, DN, h, lead):
    """Seed pipeline: 'derived' (the next `lead` years of growth with headroom), 'none', or [{year, mw}]."""
    sp = nw.get('seed_pipeline', 'derived')
    if sp is None or (isinstance(sp, str) and sp == 'derived'):
        yrs = nw.get('seed_pipeline_years')
        return _seed_pipeline(DN, h, lead if yrs is None else int(round(yrs)))
    if isinstance(sp, str) and sp == 'none':
        return []
    return [(int(d['year']), float(d['mw'])) for d in sp]


def operating_limit(nw):
    """
    Operating limit as a multiple of planning capacity.

    Input: nw = resolved network inputs.
    Output: float: nw['operating_limit'] if set, else 1 / planning_limit_factor
      (1.25 at 0.80), else 1.0. Existing load is served up to this multiple.
    """
    if nw.get('operating_limit') is not None:
        return float(nw['operating_limit'])
    return 1 / nw['planning_limit_factor'] if nw.get('planning_limit_factor') else 1.0


def _split_delay(y, mw, d):
    """Capacity ordered in year y arriving after d years (fractional d split between the two whole years)."""
    k = int(np.floor(d))
    f = d - k
    return [(y + k + j, m) for j, m in ((0, mw * (1 - f)), (1, mw * f)) if m > 0]


def _delay_cohorts(D, W):
    """
    Upgrade Delay for Interconnection by request year (first in, first out).
    New load requested in year t = demand growth (load already waiting at the
    start counts as requested in 2026); it connects as the MW waiting falls.
    Returns MW-years waited, MW affected (waited at least one year) and MW still
    waiting in 2050 (censored: their wait is counted to the end of 2050), each
    by request year. Total MW-years equals the sum of MW waiting over the years.
    """
    n = len(D)
    mwyr, aff, cens = np.zeros(n), np.zeros(n), np.zeros(n)
    q = []
    for t in range(n):
        A = W[0] if t == 0 else max(0.0, D[t] - D[t - 1])
        if A > 1e-12:
            q.append([t, A])
        excess = sum(m for _, m in q) - W[t]
        if excess < -1e-9:                      # waiting rose without new requests
            q.append([t, -excess])
            excess = 0.0
        while excess > 1e-12 and q:
            y0, m = q[0]
            take = min(m, excess)
            if t > y0:
                mwyr[y0] += (t - y0) * take
                aff[y0] += take
            excess -= take
            if take >= m - 1e-12:
                q.pop(0)
            else:
                q[0][1] = m - take
    for y0, m in q:
        mwyr[y0] += (n - y0) * m
        aff[y0] += m
        cens[y0] += m
    return mwyr, aff, cens


def _band_spec(nw, h):
    """
    Band list before the sub-band: explicit (`bands`) or generated (`n_bands`
    equal-capacity bands, loadings spread linearly by `utilisation_spread`
    around `mean_utilisation`). If `mean_utilisation` is set, loadings are
    shifted by one amount so the capacity-weighted mean equals it, each band
    capped at the planning limit (loading 1.0); load above the planning limit
    belongs in the constrained sub-band.
    """
    tgt = 1 / (1 + h)
    mean = nw.get('mean_utilisation')
    spec = nw.get('bands') or [{'name': 'All', 'capacity_share': 1.0, 'loading': None}]
    if nw.get('band_mode', 'explicit') == 'generated':
        n, spr = int(nw['n_bands']), nw['utilisation_spread']
        if mean is None:            # centre on the explicit bands' capacity-weighted mean
            mean = (sum(b['capacity_share'] * (b['loading'] if b.get('loading') is not None else tgt) for b in spec)
                    / sum(b['capacity_share'] for b in spec))
        spec = [{'name': f'Band {i + 1}', 'capacity_share': 1 / n,
                 'loading': (mean + spr * (0.5 - i / (n - 1)) if n > 1 else mean)} for i in range(n)]
    if mean is None:
        return spec
    if not 0 < mean <= 1.0:
        raise ValueError(f'mean_utilisation {mean} must be in (0, 1]: load above the planning limit goes in the sub-band')
    L = np.array([b['loading'] if b.get('loading') is not None else tgt for b in spec], float)
    cs = np.array([b['capacity_share'] for b in spec], float)
    f = lambda d: float(np.sum(cs * np.minimum(L + d, 1.0)) / cs.sum())
    lo, hi = -L.max(), 1.0 - L.min()
    for _ in range(200):                                    # bisection on the shift
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) < mean else (lo, mid)
    d = (lo + hi) / 2
    if (L + d).min() <= 0:
        raise ValueError(f'mean_utilisation {mean} gives a band with zero or negative loading')
    return [{**b, 'loading': float(min(Li + d, 1.0))} for b, Li in zip(spec, L)]


def network_bands(nw, DN0, h):
    """
    Loading bands for the network at 2026.

    Inputs: nw = resolved network inputs (bands or generated bands,
      mean_utilisation, sub-band settings); DN0 = 2026 network peak, MW;
      h = planning_headroom (share).
    Each band has a share of network capacity and a starting loading (network
    peak / planning capacity; null = at the planning target 1 / (1 + h)). Load
    shares follow from both. Optional growth_share and flex_share allocate load
    growth and flexible MW; default pro rata to load. No bands -> one band at the
    planning target.

    Constrained sub-band (subband_enabled): subband_load_share of network load at
    subband_utilisation (above the planning limit), carved out of the most loaded
    bands with total load and capacity unchanged (their growth and flex shares
    move with the load). Existing load in every band is served up to the
    operating limit (see project_layers()).

    Output: list of dicts: name, capacity_share, load_share, loading0, growth_share,
      flex_share, C0 (planning capacity, MW), subband (bool). Raises ValueError
      for inconsistent sub-band or mean-utilisation inputs.
    """
    spec = _band_spec(nw, h)
    tgt = 1 / (1 + h)
    w = [b['capacity_share'] * (b['loading'] if b.get('loading') is not None else tgt) for b in spec]
    out = []
    for b, wi in zip(spec, w):
        ls = wi / sum(w)
        C0 = (ls * DN0 * (1 + h)) if b.get('loading') is None else ls * DN0 / b['loading']
        out.append(dict(name=b.get('name', ''), capacity_share=b['capacity_share'], load_share=ls,
                        loading0=b.get('loading') if b.get('loading') is not None else tgt,
                        growth_share=b.get('growth_share', ls), flex_share=b.get('flex_share', ls), C0=C0,
                        subband=False))
    x = nw.get('subband_load_share') or 0.0
    if nw.get('subband_enabled') and x > 0:
        Ls = nw['subband_utilisation']
        if x >= 1:
            raise ValueError('subband_load_share must be below 1')
        rem, g, fl = x, 0.0, 0.0
        for bd in sorted(out, key=lambda b: -b['loading0']):
            take = min(rem, bd['load_share'])
            if take <= 0:
                break
            frac = take / bd['load_share']
            cut = take * DN0 / Ls
            if cut >= bd['C0'] and take < bd['load_share']:
                raise ValueError('subband_utilisation is below the loading of the band it is carved from')
            g += bd['growth_share'] * frac
            fl += bd['flex_share'] * frac
            bd['growth_share'] *= 1 - frac
            bd['flex_share'] *= 1 - frac
            bd['load_share'] -= take
            bd['C0'] = max(0.0, bd['C0'] - cut)
            bd['loading0'] = bd['load_share'] * DN0 / bd['C0'] if bd['C0'] > 0 else 0.0
            rem -= take
        out = [bd for bd in out if bd['load_share'] > 1e-12]
        out.insert(0, dict(name='Above planning limit', capacity_share=0.0, load_share=x, loading0=Ls,
                           growth_share=g, flex_share=fl, C0=x * DN0 / Ls, subband=True))
        tot = sum(bd['C0'] for bd in out)
        for bd in out:
            bd['capacity_share'] = bd['C0'] / tot
    return out


# ── Published-plan BAU ───────────────────────────────────────────────────────

PLAN_CATEGORIES = ('growth', 'replacement', 'gridmod', 'other')
BEYOND_PATHS = ('continue', 'taper', 'policy')


def _taper(g_from, g_to, y, y_end, taper_year):
    """Growth rate tapering linearly from g_from (plan horizon) to g_to (reached in taper_year)."""
    if taper_year <= y_end:
        return g_to
    w = min(1.0, max(0.0, (y - y_end) / (taper_year - y_end)))
    return g_from + (g_to - g_from) * w


def plan_paths(params, a, fa, sysdf, infl):
    """
    Published-plan BAU paths, 2026-2050 (forward_assumptions['bau_plan']).

    Inputs: params (earlier-model utility dict); a = resolve() output (bau_plan,
      system_needs, projection); fa = forward_assumptions (for the high
      electrification level of the policy path); sysdf = system_path() (BAU
      network and system peak); infl = inflation rate.
    Distribution capex follows the published plan for the plan years. Beyond the
    plan, `beyond_path`:
      'continue'  the plan CAGR (or `plan_cagr_override` for a one-year plan);
      'taper'     the growth rate tapers linearly from the plan CAGR to load growth
                  (network peak growth, nominal) by `taper_year`;
      'policy'    nominal network peak growth with electrification at its high
                  level (state electrification and clean energy plans).
    Transmission (PJM utilities with `transmission_plan_rate_base_m`): the
    transmission bill line follows the plan's transmission rate base per MW of
    system peak (network service rates are revenue over zonal peak) for the plan
    years, then its growth tapers to projection.transmission_growth by
    `taper_year`.
    Output: dict: capex ($M nominal per year, 25 values), shares {category:
      share}, addressable {category: share}, ramp_years, tx_index (transmission
      line index, 2026 = 1, or None), plan_end (last plan year), plan_cagr.
    """
    bp = a['bau_plan']
    yrs, capex_plan = list(bp['plan_years']), list(bp['plan_dist_capex_m'])
    y_end = yrs[-1]
    g_plan = (bp['plan_cagr_override'] if bp.get('plan_cagr_override') is not None
              else (capex_plan[-1] / capex_plan[0]) ** (1 / (len(capex_plan) - 1)) - 1)
    path, ty = bp.get('beyond_path', 'taper'), int(round(bp.get('taper_year', 2035)))
    if path not in BEYOND_PATHS:
        raise ValueError(f'beyond_path {path!r} must be one of {BEYOND_PATHS}')
    DN = sysdf['net_peak_mw'].values
    if path == 'policy':
        hi = fa['layers']['system_needs']['params']['electrification_growth']['high']
        a_hi = {**a, 'system_needs': {**a['system_needs'], 'electrification_growth': hi}}
        DN = system_path(params, a_hi, True)['net_peak_mw'].values
    capex = np.zeros(len(YEARS))
    for t, y in enumerate(YEARS):
        if y in yrs:
            capex[t] = capex_plan[yrs.index(y)]
            continue
        g_load = (DN[t] / DN[t - 1]) * (1 + infl) - 1
        g = {'continue': g_plan, 'policy': g_load}.get(path) if path != 'taper' else _taper(g_plan, g_load, y, y_end, ty)
        capex[t] = capex[t - 1] * (1 + g)
    shares = dict(zip(PLAN_CATEGORIES, bp['category_shares']))
    if abs(sum(shares.values()) - 1) > 1e-6:
        raise ValueError('bau_plan category_shares must sum to 1')
    addr = {c: bp.get(f'addressable_{c}', 0.0) or 0.0 for c in PLAN_CATEGORIES}
    tx_index = None
    if bp.get('transmission_plan_rate_base_m'):
        P = sysdf['peak_mw'].values
        tyrs, trb = list(bp['transmission_plan_years']), list(bp['transmission_plan_rate_base_m'])
        gt_end = None
        tx_index = np.ones(len(YEARS))
        base = trb[tyrs.index(2026)] / P[0]
        for t, y in enumerate(YEARS):
            if y in tyrs:
                tx_index[t] = (trb[tyrs.index(y)] / P[t]) / base
            elif t > 0:
                if gt_end is None:
                    gt_end = tx_index[t - 1] / tx_index[t - 2] - 1
                g = _taper(gt_end, a['projection']['transmission_growth'], y, tyrs[-1], ty)
                tx_index[t] = tx_index[t - 1] * (1 + g)
    return dict(capex=capex, shares=shares, addressable=addr, ramp_years=bp.get('addressable_ramp_years', 5) or 5,
                tx_index=tx_index, plan_end=y_end, plan_cagr=g_plan, path=path, taper_year=ty)


def _capacity_price(cap, t, y, infl, plan_on):
    """
    Capacity price, $M per MW-year nominal: the 2026 price grown at price_growth,
    with published auction prices for later years where given (published-plan
    BAU only, `published_prices` {year: price}); 'long_run' price_path ramps
    linearly to the long-run cost of new entry (long_run_price_m_per_mw_yr, in
    long_run_price_year $) by long_run_year, then grows with inflation.
    """
    p0 = cap['price_m_per_mw_yr']
    pub = {int(k): v for k, v in (cap.get('published_prices') or {}).items()} if plan_on else {}
    last = max([yy for yy in pub if yy <= y], default=None)
    if last is not None:
        base = pub[last] * (1 + cap['price_growth']) ** (y - last)
    else:
        base = p0 * (1 + cap['price_growth']) ** t
    if cap.get('price_path', 'today') != 'long_run':
        return base
    ly = int(cap['long_run_year'])
    lr = cap['long_run_price_m_per_mw_yr'] * (1 + infl) ** (y - int(cap.get('long_run_price_year', 2025)))
    if y >= ly:
        return lr
    w = (y - YEARS[0]) / (ly - YEARS[0])
    return max(base, p0 + (cap['long_run_price_m_per_mw_yr'] * (1 + infl) ** (ly - int(cap.get('long_run_price_year', 2025))) - p0) * w)


# ── Projection ───────────────────────────────────────────────────────────────

def project_layers(utility_json, params, level='central', overrides=None, enabled=None,
                   scenario=None, flex_cost_scale=1.0, uplift_mode=None, network=None):
    """
    BAU and shared-savings projection, 2026-2050, with an explicit distribution-
    network capacity constraint.

    Inputs: utility_json (starting_bill, forward_assumptions); params
      (earlier-model utility dict: rate base, capex, WACC, ROE, equity ratio,
      property tax, energy, peak, customers); level, scenario, overrides, enabled,
      network: see resolve();
      flex_cost_scale multiplies every flexible cost per kW-year (used by
      flex_pays_cost()); uplift_mode 'derived' / 'direct' overrides
      load_enabled.uplift_mode.

    Network: firm capacity starts at network peak x (1 + planning headroom) and
    grows only through reinforcement, ordered when demand x (1 + headroom)
    exceeds capacity in service + pipeline (+ headroom counted for deferral),
    arriving after the lead time, capped at a maximum build rate. Served load
    = min(demand, capacity [+ flexible headroom]); the rest waits for the
    upgrade. Existing load (2026) is served up to the operating limit (planning
    capacity / planning_limit_factor). In constrained areas (bands that start
    above the planning limit: the sub-band) the Upgrade Delay for
    Interconnection inputs replace the reactive planner: the backlog above the
    planning limit is cleared at backlog_clearance_pct a year, and capacity for
    new load arrives after the upgrade delay (ordinary / large loads), with or
    without build-rate priority. Without those inputs the reactive planner
    applies there too. The delay itself is measured per request year, first in
    first out (columns upgrade_delay_*).

    Flexible headroom (shared savings) = firm flexible MW x locational match
    + flexible large-load connections ('derived' mode), or an assumed % of
    capacity ('direct' mode). Each year it is split, never double-used:
    load enabled (waiting load connects sooner, up to enable_share of the
    headroom) first where BAU leaves load waiting, the rest to deferral
    (counted by the planner, so reinforcement is ordered later). With
    flexibility targeting on, up to flex_targeting_share of the headroom goes
    first to bands above their planning limit (in proportion to the load
    above it), the rest pro rata.

    Output: dict with 'bau' and 'ss' (DataFrames, one row per year: bills in
      $/month nominal per residential customer, bill_<category> at benchmark
      usage and avg_bill_<category> for the average residential bill; system
      figures in $M nominal per year (_m), MW, GWh; Upgrade Delay columns in
      years, MW and MW-years), 'mw' (MW by type), 'system' (system_path()),
      'assumptions' (resolve()), 'bands', 'band_detail' {'bau', 'ss'}
      (per-band rows), year-zero details (starting_lines, program_spend0_m
      $M/yr, program_spend0_parts, residential_program_allocation), ee_kw_per_mwh
      (kW per MWh of first-year savings), uplift_mode, benchmark_kwh and
      operating_limit.
    """
    fa = utility_json['forward_assumptions']
    a = resolve(fa, level, overrides, enabled, scenario, network)
    on = a['_enabled']
    if a['mechanism'].get('pool_basis', 'revenue_requirement') != 'revenue_requirement':
        raise ValueError("the layer engine has one savings-pool basis, 'revenue_requirement' "
                         f"(got {a['mechanism']['pool_basis']!r})")
    pj = a['projection']
    infl = pj['inflation_rate']
    sn, pr, dfr, le, cap, mech = (a['system_needs'], a['programs'], a['deferral'], a['load_enabled'],
                                  a['capacity'], a['mechanism'])
    nw = a['network']
    mode = uplift_mode or le['uplift_mode']
    sysdf = system_path(params, a, on['system_needs'])
    S = sysdf['sales_gwh'].values
    P = sysdf['peak_mw'].values
    DN = sysdf['net_peak_mw'].values
    S0, P0 = S[0], P[0]
    lf_new = S0 / (P0 * 8.76)                        # load factor of new load (system average)
    h = nw['planning_headroom']
    lead = int(round(nw['reinforcement_lead_years']))
    cost_mw = sn['dist_upgrade_cost_per_mw']

    lines0 = starting_lines(utility_json)
    dist0 = sum(d['month'] for d in lines0 if d['category'] in DIST_CATS)
    # BAU basis: 'published_plan' (distribution capex from the utility's plan; the
    # network model only estimates how much of the growth-driven part is
    # deferrable) or 'model' (capex generated by the network model)
    bp = a.get('bau_plan', {})
    plan_on = bp.get('basis', 'model') == 'published_plan' and on['system_needs']
    if bp.get('basis', 'model') not in ('model', 'published_plan'):
        raise ValueError(f"bau_plan basis {bp['basis']!r} must be 'model' or 'published_plan'")
    plan = plan_paths(params, a, fa, sysdf, infl) if plan_on else None
    # 2026 BAU wires RR = rate-case target in both bases (the plan's 2026 capex enters the rate base)
    rec = delivery_rr_reconciliation({**params, 'annual_capex_m': plan['capex'][0]} if plan_on else params, {})
    om0 = max(0.0, rec['other_om_recalibrated_m'])
    wacc, ptr = params['wacc'], params['property_tax_rate']
    eq_roe = params['equity_ratio'] * params['roe']
    spend0, spend_parts = _program_spend0(utility_json, params)
    kwh_b = utility_json['starting_bill']['benchmark_kwh_month']
    core0 = sum(d['month'] for d in lines0 if d['category'] == 'program_surcharge' and d['core'])
    res_alloc = (core0 / kwh_b) / (spend0 / S0) if spend0 > 0 else 1.0
    trans_year = int(pr['transition_year'])
    ee_kw_per_mwh = (pr['ee_kw_per_mwh'] if pr.get('ee_kw_per_mwh') is not None
                     else pr['ee_peak_coincidence'] / (8.76 * lf_new))
    price0 = cap['price_m_per_mw_yr']
    # Value-stream layers (absent in older forward_assumptions = off)
    we, tx, lo, ro = (a.get(k, {}) for k in ('wholesale_energy', 'transmission', 'losses', 'roe'))
    sup0_kwh = sum(d['month'] for d in lines0 if d['category'] == 'supply_energy') / kwh_b
    tx_on_lines = tx.get('bill_basis', 'transmission_lines') == 'transmission_lines'
    tx_plan = plan['tx_index'] if plan_on else None
    tx_idx = (lambda t: tx_plan[t]) if tx_plan is not None else (lambda t: _infl(pj['transmission_growth'], t))
    bands = network_bands(nw, DN[0], h)
    NB = range(len(bands))
    op_x = operating_limit(nw)
    # Existing load served at the start: up to the operating limit
    G = [min(bd['load_share'] * DN[0], op_x * bd['C0']) for bd in bands]
    tgt_on = bool(nw.get('flex_targeting_enabled'))
    tgt_share = nw.get('flex_targeting_share', 0.0) or 0.0
    DNb = [[bd['load_share'] * DN[t] + (bd['growth_share'] - bd['load_share']) * (DN[t] - DN[0])
            for t in range(len(YEARS))] for bd in bands]
    # Projects under way at 2026 were planned system-wide: the single-pool seed,
    # allocated to bands by growth share (keeps the 2026 growth / asset-condition
    # capex split independent of the band assumptions)
    seed = _seed_from(nw, DN, h, lead) if on['system_needs'] else []
    seeds = [[(yy, m * bd['growth_share']) for (yy, m) in seed] for bd in bands]
    thr = nw.get('constrained_loading', 1.0)
    # Constrained areas (bands that start above their planning limit: the
    # sub-band). Upgrade Delay for Interconnection inputs replace the reactive
    # planner there: capacity for new load is ordered on request and in service
    # after the upgrade delay (ordinary / large loads, weighted by the large-load
    # share of network growth that year); the existing overload is cleared at
    # backlog_clearance_pct of the outstanding backlog per year (in service the
    # next year); without build-rate priority both are capped at max_build_pct.
    ud_in = (nw.get('upgrade_delay_ordinary_years'), nw.get('upgrade_delay_large_years'),
             nw.get('backlog_clearance_pct'))
    ud_on = all(v is not None for v in ud_in) and on['system_needs']
    d_ord, d_lrg, clear_pct = ud_in
    prio = bool(nw.get('constrained_build_priority', True))
    con_area = [bool(bd.get('subband')) and ud_on for bd in bands]
    lrg = sysdf['dc_dist_new_mw'].values + pr['ev_hub_share'] * sysdf['ev_peak_mw'].values
    dDN, dL = np.diff(DN, prepend=DN[0]), np.diff(lrg, prepend=lrg[0])
    large_sh = np.clip(np.where(dDN > 1e-9, dL / np.maximum(dDN, 1e-12), 0.0), 0.0, 1.0)
    ramp = {k: pr.get(f'ramp_pct_peak_{k}') for k in FLEX_TYPES}
    cf_share = le.get('customer_funded_share', 0.0) or 0.0
    elec_share = np.clip(np.where(DN > DN[0], sysdf['elec_peak_mw'].values / np.maximum(DN - DN[0], 1e-12), 0.0),
                         0.0, 1.0)
    cond0 = None

    res, mw_rows, bau_band_t = {}, [], []
    for case in ('bau', 'ss'):
        ss = case == 'ss'
        Lp = ss and on['programs']
        Ld = ss and on['deferral']
        Le = ss and on['load_enabled']
        Lc = ss and on['capacity']
        Lm = ss and on['mechanism']
        Lw, Lt, Ll, Lr = (ss and on.get(k, False) for k in ('wholesale_energy', 'transmission', 'losses', 'roe'))
        rb = params['rate_base_start_m']
        reg_vint, reg_asset = [], 0.0
        carry = 0.0
        ee_vint = []
        Cb = [bd['C0'] for bd in bands]
        pipes = [list(sd) for sd in seeds]
        pipes_new = [[] for _ in NB]                 # new-load upgrades in constrained areas
        Nin, Nord = [0.0 for _ in NB], [0.0 for _ in NB]
        prev_enabled = 0.0
        model_growth_cum = 0.0
        prev_mw = None
        band_rows = []
        rr_ref = res['bau']['rr_dist_m'].iloc[0] if ss else None
        rows = []
        for t, y in enumerate(YEARS):
            active = Lp and y >= trans_year
            # ── Programs: flexible MW, EE, flexible connections ──────────────
            mw_b, mw_s = flex_mw(pr, y, False), flex_mw(pr, y, active)
            if active:      # maximum annual growth per type (share of 2026 peak per year)
                base_prev = prev_mw or mw_b
                mw_s = {k: (min(mw_s[k], max(base_prev[k], mw_b[k]) + ramp[k] * P0) if ramp[k] is not None
                            else mw_s[k]) for k in FLEX_TYPES}
            prev_mw = mw_s
            inc = {k: max(0.0, mw_s[k] - mw_b[k]) for k in FLEX_TYPES}
            flex_cost = {k: inc[k] * 1000 * pr[f'cost_kw_yr_{k}'] * flex_cost_scale * _infl(infl, t) / 1e6
                         for k in FLEX_TYPES}
            if active:
                ee_vint.append((y, S[t] * pr['ee_incremental_savings_pct']))
            ee_gwh = sum(g for (yy, g) in ee_vint if 0 <= y - yy < int(pr['ee_measure_life']))
            ee_cost = ee_gwh * pr['ee_levelised_cost_kwh'] * _infl(infl, t)
            ee_mw = ee_gwh * ee_kw_per_mwh
            large_new = sysdf['dc_dist_new_mw'].iloc[t] + pr['ev_hub_share'] * sysdf['ev_peak_mw'].iloc[t]
            fc_mw = (large_new * pr['flex_conn_share'] * pr['flex_conn_peak_depth']) if active else 0.0
            fc_gwh = (large_new * pr['flex_conn_share'] * 8.76 * lf_new * pr['flex_conn_energy_curtailed']) if active else 0.0
            bau_spend = spend0 * (S[t] / S0) * _infl(pj['program_surcharge_growth'], t)
            new_spend = (sum(flex_cost.values()) + ee_cost) if active else 0.0
            ss_spend = bau_spend + new_spend if active else 0.0
            cap_amt = (sum(flex_cost[k] * pr[f'capitalised_{k}'] for k in FLEX_TYPES)
                       + ee_cost * pr['ee_capitalised'] + bau_spend * pr['existing_capitalised']) if active else 0.0
            prog_opex = (ss_spend - cap_amt) if active else 0.0
            amort_years = int(pr['amortisation_years'])
            prog_amort = sum(v / amort_years for (yy, v) in reg_vint if 0 < y - yy <= amort_years)
            if active:
                reg_vint.append((y, cap_amt))
            reg_asset = reg_asset - prog_amort + cap_amt
            firm_flex = sum(inc[k] * pr[f'derate_{k}'] for k in FLEX_TYPES)
            # ── Network capacity, per loading band ───────────────────────────
            ee_red = ee_mw if active else 0.0
            D = DN[t] - ee_red                                       # network demand
            Db = [DNb[i][t] - ee_red * bands[i]['load_share'] for i in NB]
            arr_b = []
            for i in NB:
                a_i = sum(m for (yy, m) in pipes[i] if yy == y)
                pipes[i] = [(yy, m) for (yy, m) in pipes[i] if yy != y]
                Cb[i] += a_i
                if con_area[i]:
                    a_n = sum(m for (yy, m) in pipes_new[i] if yy == y)
                    pipes_new[i] = [(yy, m) for (yy, m) in pipes_new[i] if yy != y]
                    Cb[i] += a_n
                    Nin[i] += a_n
                    a_i += a_n
                arr_b.append(a_i)
            C = sum(Cb)
            if ss and (Ld or Le) and active:
                if mode == 'derived':
                    H = firm_flex * dfr['locational_match'] + fc_mw
                    Hb = [H * bands[i]['flex_share'] for i in NB]
                    if tgt_on:      # targeting: headroom first to bands above their planning limit
                        need = [max(0.0, Db[i] - Cb[i]) for i in NB]
                        T = min(tgt_share * H, sum(need))
                        if T > 0:
                            Hb = [(H - T) * bands[i]['flex_share'] + T * need[i] / sum(need) for i in NB]
                else:
                    Hb = [le['direct_uplift_pct'] * Cb[i] for i in NB]
                    H = sum(Hb)
            else:
                H, Hb = 0.0, [0.0 for _ in NB]
            Hen_b, Hdef_b, srv_b, wait_b, used_b, ord_b, con_b, abv_b = [], [], [], [], [], [], [], []
            for i in NB:
                # Priority to load enabled only where BAU leaves load waiting
                wb = res['bau_bands'][i]['upgrade_wait_mw'][t] if ss else 0.0
                h_en = min(Hb[i] * le['enable_share'], wb) if (Le and wb > 0) else 0.0
                h_def = (Hb[i] - h_en) if Ld else 0.0
                if con_area[i]:
                    # Constrained area: existing overload cleared at the backlog
                    # clearance rate; new load waits the upgrade delay
                    gap = max(0.0, G[i] - (Cb[i] - Nin[i]) - sum(m for (_, m) in pipes[i]))
                    use = min(h_def, gap)
                    o_bl = clear_pct * (gap - use)
                    o_new = max(0.0, (Db[i] - DNb[i][0]) * (1 + h) - (h_def - use) - Nord[i])
                    if not prio and o_bl + o_new > nw['max_build_pct'] * Cb[i]:
                        sc_ = nw['max_build_pct'] * Cb[i] / (o_bl + o_new)
                        o_bl, o_new = o_bl * sc_, o_new * sc_
                    if o_bl > 0:
                        pipes[i].append((y + 1, o_bl))
                    Nord[i] += o_new
                    for (yy, m) in (_split_delay(y, o_new * (1 - large_sh[t]), d_ord)
                                    + _split_delay(y, o_new * large_sh[t], d_lrg)):
                        if yy == y:                          # upgrade within the year
                            Cb[i] += m
                            Nin[i] += m
                            arr_b[i] += m
                        else:
                            pipes_new[i].append((yy, m))
                # Deferral headroom only carries load BAU would serve anyway (it
                # substitutes for reinforcement); only load-enabled headroom can
                # connect load that BAU leaves waiting. One use per MW.
                # Existing load G[i] stays served up to the operating limit
                # (equals the planning-capacity rule when the band starts at or
                # below its planning limit, G[i] <= Cb[i]).
                bs = res['bau_bands'][i]['served_mw'][t] if ss else Db[i]
                cs_i = max(Cb[i], G[i])
                sv = min(Db[i], min(max(Cb[i] + h_def, G[i]), max(cs_i, bs)) + h_en)
                used_b.append(min(max(0.0, sv - cs_i), h_en + h_def))
                # Reinforcement ordering (reactive), capped at the maximum build rate
                if con_area[i]:
                    o = o_bl + o_new
                else:
                    view = Cb[i] + sum(m for (_, m) in pipes[i]) + h_def
                    o = (min(max(0.0, Db[i] * (1 + h) - view), nw['max_build_pct'] * Cb[i])
                         if on['system_needs'] else 0.0)
                    if o > 0:
                        pipes[i].append((y + lead, o))
                eff = Cb[i] + h_en + h_def
                con_b.append(Db[i] > thr * eff + 1e-9)
                abv_b.append(max(0.0, sv - eff))                    # served above the planning limit
                Hen_b.append(h_en); Hdef_b.append(h_def); srv_b.append(sv); wait_b.append(Db[i] - sv); ord_b.append(o)
                band_rows.append(dict(year=y, band=bands[i]['name'], demand_mw=Db[i], capacity_mw=Cb[i],
                                      operating_limit_mw=op_x * Cb[i], headroom_mw=Hb[i], served_mw=sv,
                                      upgrade_wait_mw=Db[i] - sv, above_planning_limit_mw=abv_b[-1],
                                      loading=Db[i] / eff if eff else 0.0, constrained=con_b[-1]))
            H_en, H_def = sum(Hen_b), sum(Hdef_b)
            arriving = sum(arr_b)
            C = sum(Cb)
            served, used, order = sum(srv_b), sum(used_b), sum(ord_b)
            waiting = sum(wait_b)
            if not ss:
                bau_band_t.append((srv_b, wait_b))
            constrained_mw = sum(Db[i] for i in NB if con_b[i])
            growth = arriving * cost_mw * _infl(infl, t)
            if cond0 is None:
                cond0 = max(0.0, params['annual_capex_m'] - growth)
            capex = growth + cond0 * _infl(infl, t) if on['system_needs'] else params['annual_capex_m']
            model_growth = growth
            av_g = av_r = av_m = av_o = 0.0
            deferrable = 0.0
            if plan_on:
                # BAU capex = the published plan. In shared savings the network model gives
                # the deferrable share of growth-driven spending (cumulative reinforcement
                # avoided vs BAU, capped at the addressable share); replacement, grid
                # modernisation and other spending are right-sized at their addressable
                # shares, ramping in over addressable_ramp_years from the transition year
                capex_bau = plan['capex'][t]
                sh, ad = plan['shares'], plan['addressable']
                if ss and Ld and active:
                    cb = float(np.sum(res['bau']['model_growth_capex_m'].values[:t + 1]))
                    deferrable = (min(1.0, max(0.0, 1 - (model_growth_cum + growth) / cb)) if cb > 1e-9 else 0.0)
                    ramp_p = min(1.0, (y - trans_year + 1) / plan['ramp_years'])
                    av_g = capex_bau * sh['growth'] * min(ad['growth'], deferrable)
                    av_r = capex_bau * sh['replacement'] * ad['replacement'] * ramp_p
                    av_m = capex_bau * sh['gridmod'] * ad['gridmod'] * ramp_p
                    av_o = capex_bau * sh['other'] * ad['other'] * ramp_p
                capex = capex_bau - (av_g + av_r + av_m + av_o)
                growth = capex_bau * sh['growth'] - av_g
            model_growth_cum += model_growth
            # Connected sooner = load served above what BAU serves in each band (efficiency
            # lowers demand but connects nobody, so it is not counted)
            enabled_mw = (sum(max(0.0, srv_b[i] - res['bau_bands'][i]['served_mw'][t]) for i in NB)
                          if ss else 0.0)
            new_enabled = max(0.0, enabled_mw - prev_enabled)
            prev_enabled = max(prev_enabled, enabled_mw)
            # Load enabled: incremental cost of serving the newly connected load
            conn_capex = new_enabled * 1000 * le['connection_cost_kw'] * _infl(infl, t) / 1e6 if Le else 0.0
            served_gwh_loss = waiting * 8.76 * lf_new
            # Access (not on the bill): connection costs avoided by new customers. Flexible
            # connections already count once, as headroom (deferral or load enabled), so
            # only MW actually connected sooner are credited here
            ciac_avoided = (new_enabled * cost_mw * cf_share * _infl(infl, t)) if ss else 0.0
            delay_avoided = (res['bau']['upgrade_wait_mw'].iloc[t] - waiting) if ss else 0.0
            elec_fwd = (enabled_mw * 8.76 * lf_new * elec_share[t]) if ss else 0.0
            S_case = S[t] - (ee_gwh if active else 0.0) - served_gwh_loss - fc_gwh
            inc_om = (max(0.0, enabled_mw) * 8.76 * lf_new * le['incremental_om_mwh'] * _infl(infl, t) / 1000
                      if Le else 0.0)
            # ── Revenue requirement ──────────────────────────────────────────
            rb_open = rb
            rb = rb * (1 - RATE_BASE_DECAY) + capex + conn_capex
            rb_earning = rb + reg_asset
            ptax = rb * ptr * (1 + infl * 0.5) ** t
            dep = RATE_BASE_DECAY * rb_open
            om = om0 * _infl(infl, t) + inc_om
            # ROE layer: allowed ROE in shared savings = BAU ROE + roe_delta from the transition year
            roe_d = ro['roe_delta'] if (Lr and y >= trans_year) else 0.0
            wacc_c = wacc + params['equity_ratio'] * roe_d if roe_d else wacc
            rr_dist = rb * wacc_c + ptax + dep + om
            prog_rr = prog_opex + prog_amort + reg_asset * wacc_c
            roe_cost = rb_earning * params['equity_ratio'] * roe_d
            rr_core = rr_dist + prog_rr
            # ── Capacity (bulk system): all firm MW at peak, derated by type ─
            price = _capacity_price(cap, t, y, infl, plan_on)
            # Load waiting for an upgrade buys no capacity. Efficiency and firm flexible
            # MW lower the obligation once each, in the capacity layer (off: no credit)
            sys_peak = P[t] - (D - served)
            mw_red = min(firm_flex + (ee_mw if active else 0.0), sys_peak) if Lc else 0.0
            cap_cost = (sys_peak - mw_red) * price
            prog_bill_cost = 0.0 if active else bau_spend
            # ── Value streams (shared savings, once programs are active) ─────
            mw_firm = min(firm_flex + ee_mw, P[t]) if active else 0.0
            sup_kwh = sup0_kwh * _infl(pj['supply_energy_growth'], t)            # $/kWh
            whl = tx_av = loss_e = loss_p = mw_loss = 0.0
            if Lw and active:      # load shifted from on-peak to off-peak hours
                spread = we['spread_mwh'] * _infl(pj['supply_energy_growth'], t)
                off = we['offpeak_price_mwh'] * _infl(pj['supply_energy_growth'], t)
                per = {k: spread for k in FLEX_TYPES}
                per['storage'] = spread - off * (1 / we['storage_rte'] - 1)      # round-trip losses
                whl = sum(inc[k] * we[f'mwh_per_mw_{k}'] * per[k] for k in FLEX_TYPES) / 1e6
            if Lt and active:      # transmission cost avoided by peak reduction
                tx_av = (mw_firm * tx['cost_kw_yr'] * 1000 * tx['avoidable_share']
                         * tx_idx(t) / 1e6)
            if Ll and active:      # marginal distribution losses avoided (above the average in retail rates)
                loss_e = (ee_gwh * lo['avg_loss_pct'] * (lo['marginal_mult_energy'] - 1)) * sup_kwh
                mw_loss = min(mw_firm * lo['avg_loss_pct'] * lo['marginal_mult_peak'], max(0.0, sys_peak - mw_red))
                loss_p = mw_loss * price
            vpool = (whl * bool(we.get('in_pool', True)) + tx_av * bool(tx.get('in_pool', True))
                     + (loss_e + loss_p) * bool(lo.get('in_pool', True)))
            # ── Mechanism ────────────────────────────────────────────────────
            # Pool = reduction in what customers pay vs BAU (+ value streams in the pool);
            # the utility's share is recovered in the revenue requirement
            earnings = 0.0
            pool = np.nan
            if ss:
                b = res['bau']
                pool = ((b['rr_core_m'].iloc[t] + b['program_bill_cost_m'].iloc[t] + b['capacity_cost_m'].iloc[t])
                        - (rr_core + prog_bill_cost + cap_cost))
                if roe_cost and not ro.get('roe_in_pool', False):
                    pool += roe_cost                     # the ROE lever sits outside the pool
                if vpool:
                    pool += vpool
                if Lm:
                    net = pool + carry
                    carry = min(0.0, net)
                    earnings = mech['utility_share'] * max(0.0, net)
            adj = earnings
            rr = rr_core + adj
            if not ss and t == 0:
                rr_ref = rr_dist
            # ── Bills ────────────────────────────────────────────────────────
            usage = (S[t] - (ee_gwh if active else 0.0)) / S[t]
            dist_bill = dist0 * (rr_dist / rr_ref) * (S0 / S_case)
            if tx_av and not tx_on_lines:          # transmission recovered in delivery rates (New York)
                dist_bill *= 1 - tx_av / rr_dist
            f_sup = (whl + loss_e) / (sup_kwh * S_case) if (whl or loss_e) and sup_kwh > 0 else 0.0
            f_tx = (tx_av / (P[t] * tx['cost_kw_yr'] * 1000 * tx_idx(t) / 1e6)
                    if tx_av and tx_on_lines else 0.0)
            rider = dict(id='core_program_and_earnings_recovery',
                         name='Core programs and shared savings earnings (per kWh)',
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
                    if f_sup:
                        e['month'] *= 1 - f_sup
                elif c == 'transmission':
                    e['month'] = d['month'] * tx_idx(t)
                    if f_tx:
                        e['month'] *= 1 - f_tx
                elif c == 'capacity':
                    e['month'] = d['month'] * (price / price0) * ((sys_peak - mw_red - mw_loss) / P0) / (S_case / S0)
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
                residential_usage_index=usage, sales_gwh=S_case, ee_gwh=ee_gwh if active else 0.0,
                peak_mw=P[t], network_demand_mw=D, network_capacity_mw=C, headroom_created_mw=H,
                headroom_enable_mw=H_en, headroom_defer_mw=H_def, headroom_used_mw=used,
                served_mw=served, upgrade_wait_mw=waiting, mwh_not_served_gwh=served_gwh_loss,
                load_in_constrained_bands_mw=constrained_mw, constrained_bands=sum(con_b),
                above_planning_limit_mw=sum(abv_b),
                upgrade_delay_mw_yr_avoided=delay_avoided, connection_cost_avoided_m=ciac_avoided,
                electrification_gwh_brought_forward=elec_fwd,
                enabled_mw=enabled_mw, reinforcement_ordered_mw=order, reinforcement_in_service_mw=arriving,
                capacity_uplift_pct=(H / C if C else 0.0), flex_conn_mw=fc_mw,
                capex_m=capex, growth_capex_m=growth, conn_capex_m=conn_capex, incremental_om_m=inc_om,
                model_growth_capex_m=model_growth, plan_capex_m=(plan['capex'][t] if plan_on else np.nan),
                capex_avoided_growth_m=av_g, capex_avoided_replacement_m=av_r, capex_avoided_gridmod_m=av_m,
                capex_avoided_other_m=av_o, deferrable_growth_share=deferrable,
                rate_base_m=rb_earning, wires_rate_base_m=rb, regulatory_asset_m=reg_asset, rr_dist_m=rr_dist,
                program_rr_m=prog_rr, rr_core_m=rr_core, rr_m=rr,
                program_spend_m=(ss_spend if active else bau_spend), new_program_spend_m=new_spend,
                flex_spend_m=sum(flex_cost.values()) if active else 0.0, ee_spend_m=ee_cost if active else 0.0,
                program_bill_cost_m=prog_bill_cost, firm_flex_mw=firm_flex, ee_mw=ee_mw if active else 0.0,
                firm_mw=firm_flex + (ee_mw if active else 0.0), flex_mw_incremental=sum(inc.values()),
                peak_reduction_mw=mw_red, capacity_price_m_per_mw_yr=price, capacity_cost_m=cap_cost,
                savings_pool_m=pool, shared_savings_earnings_m=earnings,
                wholesale_value_m=whl, transmission_avoided_m=tx_av, losses_energy_value_m=loss_e,
                losses_peak_value_m=loss_p, roe_delta=roe_d, roe_cost_m=roe_cost,
                equity_return_m=rb_earning * eq_roe + roe_cost,
                utility_earnings_m=rb_earning * eq_roe + roe_cost + earnings))
            if ss:
                mw_rows.append(dict(year=y, **{f'{k}_bau_mw': mw_b[k] for k in FLEX_TYPES},
                                    **{f'{k}_ss_mw': mw_s[k] for k in FLEX_TYPES},
                                    **{f'{k}_incremental_mw': inc[k] for k in FLEX_TYPES},
                                    ee_peak_mw=ee_mw if active else 0.0, flex_conn_mw=fc_mw,
                                    flex_share_of_peak_ss=sum(mw_s.values()) / P[t],
                                    firm_mw=firm_flex + (ee_mw if active else 0.0), peak_mw=P[t]))
        res[case] = pd.DataFrame(rows)
        res[f'{case}_band_df'] = pd.DataFrame(band_rows)
        # Upgrade Delay for Interconnection, by request year (all bands)
        bdf = res[f'{case}_band_df']
        mwyr, aff, cens = np.zeros(len(YEARS)), np.zeros(len(YEARS)), np.zeros(len(YEARS))
        for bn in [bd['name'] for bd in bands]:
            g_ = bdf[bdf['band'] == bn]
            m_, a_, c_ = _delay_cohorts(g_['demand_mw'].values, g_['upgrade_wait_mw'].values)
            mwyr, aff, cens = mwyr + m_, aff + a_, cens + c_
        res[case]['upgrade_delay_yr'] = np.where(aff > 1e-9, mwyr / np.maximum(aff, 1e-12), 0.0)
        res[case]['upgrade_delay_mw_affected'] = aff
        res[case]['upgrade_delay_mw_yr'] = mwyr
        res[case]['upgrade_delay_mw_still_waiting_2050'] = cens
        if not ss:
            res['bau_bands'] = [{'served_mw': [bt[0][i] for bt in bau_band_t],
                                 'upgrade_wait_mw': [bt[1][i] for bt in bau_band_t]} for i in NB]
    return dict(bau=res['bau'], ss=res['ss'], mw=pd.DataFrame(mw_rows), system=sysdf, assumptions=a,
                bands=bands, band_detail={'bau': res['bau_band_df'], 'ss': res['ss_band_df']},
                program_spend0_m=spend0, program_spend0_parts=spend_parts, starting_lines=lines0,
                ee_kw_per_mwh=ee_kw_per_mwh, residential_program_allocation=res_alloc, uplift_mode=mode,
                benchmark_kwh=kwh_b, operating_limit=op_x)


# ── Outputs ──────────────────────────────────────────────────────────────────

MILESTONES = (2026, 2030, 2035, 2050)
MEASURE_COL = {'average': 'avg_bill_total', 'benchmark': 'bill_total'}


def _at(df, y, col):
    return float(df.loc[df['year'] == y, col].iloc[0])


def _npv(v, years, r):
    return float(np.sum(np.asarray(v) / (1 + r) ** (np.asarray(years) - YEARS[0])))


def bill_table(run, years=MILESTONES, measure='average'):
    """
    Monthly residential bill by category, BAU vs shared savings.

    Inputs: run = project_layers() output; years; measure 'average' (average
      residential bill, usage lowered by efficiency) or 'benchmark' (benchmark
      usage).
    Output: DataFrame indexed by (year, case), one column per category plus
      total, $/month nominal.
    """
    pre = 'avg_bill_' if measure == 'average' else 'bill_'
    rows = []
    for case, df in (('BAU', run['bau']), ('Shared savings', run['ss'])):
        for y in years:
            r = df[df['year'] == y].iloc[0]
            rows.append({'year': y, 'case': case, **{c: r[f'{pre}{c}'] for c in CATEGORIES},
                         'total': r[f'{pre}total']})
    return pd.DataFrame(rows).set_index(['year', 'case'])


def cumulative_savings(run, measure='average'):
    """
    Cumulative bill saving per residential customer, 2026-2050.

    Inputs: run = project_layers() output; measure 'average' or 'benchmark'.
    Output: {'undiscounted nominal $', 'NPV 3% (2026 $)', 'NPV 7% (2026 $)'}:
      sum over years of 12 x (BAU - shared-savings monthly bill), $ per customer;
      NPVs discount year y by (1 + r) ^ (y - 2026).
    """
    col = MEASURE_COL[measure]
    d = (run['bau'][col] - run['ss'][col]).values * 12
    return {'undiscounted nominal $': float(d.sum()),
            'NPV 3% (2026 $)': _npv(d, YEARS, 0.03), 'NPV 7% (2026 $)': _npv(d, YEARS, 0.07)}


def waterfall(utility_json, params, years=MILESTONES, measure='average', scenario=None):
    """
    BAU to shared-savings bill, one step per layer.

    Inputs: utility_json, params; years; measure; scenario. Layers are switched on
      one at a time in LAYERS order (layers disabled in the JSON stay off).
    Output: DataFrame indexed by year: 'BAU' ($/month nominal), one column per
      layer (change in the shared-savings bill when that layer is added,
      $/month; system_needs is zero because it applies to both cases), and
      'Shared savings' ($/month). The steps sum to Shared savings - BAU.
    """
    col = MEASURE_COL[measure]
    fa = utility_json['forward_assumptions']
    base_on = {l: bool(fa['layers'].get(l, {}).get('enabled', False)) and not fa['layers'].get(l, {}).get('hook')
               for l in LAYERS}
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


def scenario_table(utility_json, params, years=(2026, 2035, 2050), measure='average'):
    """
    Cautious / Central / Ambitious summary.

    Inputs: utility_json, params; years; measure.
    Output: DataFrame indexed by scenario: 'BAU <year>' and 'Shared savings
      <year>' ($/month nominal) and the cumulative_savings() measures ($ per
      residential customer).
    """
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
    One-at-a-time sensitivity of the saving (BAU minus shared-savings bill).

    Inputs: utility_json, params; years; measure. Every assumption_keys() entry is
      set to low and to high in turn, everything else central (no scenario).
    Output: (DataFrame, central) where the DataFrame has layer, assumption,
      'low <year>' and 'high <year>' (change in the monthly saving vs central,
      $/month nominal) and 'swing <year>' (|high - low|), sorted by the last
      year's swing; central = {year: central saving, $/month}.
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
    """
    MW by resource type.

    Inputs: run = project_layers() output; years.
    Output: DataFrame indexed by year: nameplate MW today and in shared savings
      per type, EE peak MW, flexible connections MW, flexible share of peak
      (shared savings, share), firm MW (derated flexible + EE) and BAU peak MW.
    """
    m = run['mw']
    rows = []
    for y in years:
        r = m[m['year'] == y].iloc[0]
        row = {'year': y}
        for k in FLEX_TYPES:
            row[f'{FLEX_LABEL[k]} MW (today)'] = r[f'{k}_bau_mw']
            row[f'{FLEX_LABEL[k]} MW (SS)'] = r[f'{k}_ss_mw']
        row['EE peak MW'] = r['ee_peak_mw']
        row['Flexible connections MW'] = r['flex_conn_mw']
        row['Flexible share of peak (SS)'] = r['flex_share_of_peak_ss']
        row['Firm MW (derated flex + EE)'] = r['firm_mw']
        row['Peak MW (BAU)'] = r['peak_mw']
        rows.append(row)
    return pd.DataFrame(rows).set_index('year')


def connection_table(run, years=(2030, 2035, 2050)):
    """
    Network capacity outcomes, BAU vs shared savings.

    Inputs: run = project_layers() output; years.
    Output: DataFrame indexed by year: MW waiting for upgrade, MW connected
      sooner, Upgrade Delay for Interconnection (years, load requested that
      year), GWh not served on time, effective capacity uplift (share),
      headroom created and its split to load enabled / deferral (MW), and
      cumulative reinforcement deferred (MW).
    """
    b, s = run['bau'].set_index('year'), run['ss'].set_index('year')
    rows = []
    for y in years:
        rows.append({'year': y,
                     'BAU MW waiting for upgrade': b.loc[y, 'upgrade_wait_mw'],
                     'SS MW waiting for upgrade': s.loc[y, 'upgrade_wait_mw'],
                     'MW connected sooner (SS)': s.loc[y, 'enabled_mw'],
                     f'BAU {UD} (yr, load requested that year)': b.loc[y, 'upgrade_delay_yr'],
                     f'SS {UD} (yr, load requested that year)': s.loc[y, 'upgrade_delay_yr'],
                     'BAU GWh not served on time': b.loc[y, 'mwh_not_served_gwh'],
                     'SS GWh not served on time': s.loc[y, 'mwh_not_served_gwh'],
                     'Effective capacity uplift %': s.loc[y, 'capacity_uplift_pct'],
                     'Headroom created MW': s.loc[y, 'headroom_created_mw'],
                     'to load enabled MW': s.loc[y, 'headroom_enable_mw'],
                     'to deferral MW': s.loc[y, 'headroom_defer_mw'],
                     'Reinforcement deferred MW (cum.)': (b.loc[:y, 'reinforcement_in_service_mw'].sum()
                                                          - s.loc[:y, 'reinforcement_in_service_mw'].sum())})
    return pd.DataFrame(rows).set_index('year')


def value_stack(run, params, years=(2030, 2035, 2050)):
    """
    Value stack of flexible resources (DR, managed EV, storage, other DER).

    Inputs: run = project_layers() output; params (wacc, property_tax_rate); years.
    Output: DataFrame indexed by year, $ per kW-year of incremental nameplate,
      nominal:
      cost         = flexible spend / kW
      capacity     = min(derated flexible MW, peak reduction) x capacity price
      deferral     = flexible share of firm MW x (BAU - SS wires rate base)
                     x (WACC + property tax + depreciation rate)
      load enabled = wires RR carried by the extra kWh served (BAU-unserved load
                     connected sooner), net of incremental O&M and connection capex
      total        = capacity + deferral + load enabled
      The value-stream layers (wholesale, transmission, losses) are not included.
    """
    s, b = run['ss'], run['bau']
    wacc, ptr = params['wacc'], params['property_tax_rate']
    rows = []
    for y in years:
        r = s[s['year'] == y].iloc[0]
        rb_ = b[b['year'] == y].iloc[0]
        kw = r['flex_mw_incremental'] * 1000
        if kw <= 0:
            rows.append({'year': y, 'flexible kW (incremental)': 0.0})
            continue
        flex_frac = r['firm_flex_mw'] / r['firm_mw'] if r['firm_mw'] > 0 else 0.0
        capv = min(r['firm_flex_mw'], r['peak_reduction_mw']) * r['capacity_price_m_per_mw_yr'] * 1e6
        avoided_rb = max(0.0, rb_['wires_rate_base_m'] - r['wires_rate_base_m'])
        defv = flex_frac * avoided_rb * (wacc + ptr + RATE_BASE_DECAY) * 1e6
        extra_gwh = max(0.0, r['sales_gwh'] - rb_['sales_gwh'] + r['ee_gwh'])
        lev = ((r['rr_dist_m'] * extra_gwh / r['sales_gwh'] if r['sales_gwh'] else 0.0)
               - r['incremental_om_m'] - r['conn_capex_m']) * 1e6
        cost = r['flex_spend_m'] * 1e6
        rows.append({'year': y, 'flexible kW (incremental)': kw,
                     'cost $/kW-yr': cost / kw, 'capacity value $/kW-yr': capv / kw,
                     'deferral value $/kW-yr': defv / kw, 'load-enabled value $/kW-yr': lev / kw,
                     'total value $/kW-yr': (capv + defv + lev) / kw})
    return pd.DataFrame(rows).set_index('year')


def weighted_flex_cost(utility_json, scenario=None, year=2035):
    """
    Incremental-MW-weighted flexible cost per kW-year.

    Inputs: utility_json; scenario; year (weights = shared-savings MW above
      today's in that year, on the target path).
    Output: float, $/kW-year in 2026 $ (NaN if there are no incremental MW).
    """
    pr = resolve(utility_json['forward_assumptions'], scenario=scenario)['programs']
    w = {k: max(0.0, float(np.interp(year, [2026, 2035, 2050],
                                     [pr[f'mw_start_{k}'], pr[f'mw_2035_{k}'], pr[f'mw_2050_{k}']]))
                - pr[f'mw_start_{k}']) for k in FLEX_TYPES}
    tot = sum(w.values())
    if tot <= 0:
        return float('nan')
    return sum(w[k] * pr[f'cost_kw_yr_{k}'] for k in FLEX_TYPES) / tot


def flex_pays_cost(utility_json, params, target='npv3', scenario=None, measure='average',
                   lo=0.0, hi=20.0, tol=1e-3):
    """
    Cost at which flexibility pays for itself.

    Inputs: utility_json, params; target = a year (the shared-savings bill equals
      BAU that year) or 'npv3' (cumulative 2026-2050 saving at 3% NPV equal to
      zero); scenario; measure; lo, hi = bracket of flex_cost_scale; tol.
    All flexible costs per kW-year are scaled together and the scale found by
    bisection; efficiency costs are unchanged.
    Output: (cost, note): cost = the MW-weighted flexible cost per kW-year
      (2026 $) at that scale, or None; note explains edge cases ('bisection',
      free flexibility still costs more, or pays at every cost tested).
    """
    col = MEASURE_COL[measure]
    base = weighted_flex_cost(utility_json, scenario)

    def gap(k):
        r = project_layers(utility_json, params, scenario=scenario, flex_cost_scale=k)
        if target == 'npv3':
            return cumulative_savings(r, measure)['NPV 3% (2026 $)']
        return _at(r['bau'], target, col) - _at(r['ss'], target, col)

    if not np.isfinite(base):
        return None, 'no incremental flexible MW'
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
    """
    Utility earnings, BAU vs shared savings.

    Input: run = project_layers() output.
    Output: DataFrame by year, $M nominal: BAU equity return, SS equity return
      (rate base incl. program regulatory asset x equity ratio x ROE, plus any ROE
      change), SS shared savings earnings, SS total earnings.
    """
    b, s = run['bau'], run['ss']
    df = pd.DataFrame({'year': b['year'],
                       'BAU equity return': b['equity_return_m'],
                       'SS equity return': s['equity_return_m'],
                       'SS shared savings earnings': s['shared_savings_earnings_m']})
    df['SS total earnings'] = df['SS equity return'] + df['SS shared savings earnings']
    return df


# ── Loading bands, access and ramps ──────────────────────────────────────────

def constrained_table(run, years=(2026, 2030, 2035, 2040, 2050)):
    """
    Load in constrained bands, BAU vs shared savings.

    Inputs: run = project_layers() output; years.
    Output: DataFrame indexed by year: MW of network load in constrained bands
      (load above constrained_loading x (capacity + counted headroom)), number of
      constrained bands, MW waiting for upgrade and MW served above the planning
      limit, BAU and shared savings.
    """
    b, s = run['bau'].set_index('year'), run['ss'].set_index('year')
    rows = []
    for y in years:
        rows.append({'year': y,
                     'BAU MW in constrained bands': b.loc[y, 'load_in_constrained_bands_mw'],
                     'SS MW in constrained bands': s.loc[y, 'load_in_constrained_bands_mw'],
                     'BAU constrained bands': int(b.loc[y, 'constrained_bands']),
                     'SS constrained bands': int(s.loc[y, 'constrained_bands']),
                     'BAU MW waiting for upgrade': b.loc[y, 'upgrade_wait_mw'],
                     'SS MW waiting for upgrade': s.loc[y, 'upgrade_wait_mw'],
                     'BAU MW above planning limit': b.loc[y, 'above_planning_limit_mw'],
                     'SS MW above planning limit': s.loc[y, 'above_planning_limit_mw']})
    return pd.DataFrame(rows).set_index('year')


def band_table(run, years=(2026, 2035, 2050)):
    """
    Per-band detail.

    Inputs: run = project_layers() output; years.
    Output: DataFrame indexed by (year, case, band): demand_mw, capacity_mw,
      operating_limit_mw, headroom_mw, served_mw, upgrade_wait_mw,
      above_planning_limit_mw (MW), loading (share) and constrained (bool).
    """
    out = []
    for case, lbl in (('bau', 'BAU'), ('ss', 'Shared savings')):
        d = run['band_detail'][case]
        out.append(d[d['year'].isin(years)].assign(case=lbl))
    return pd.concat(out).set_index(['year', 'case', 'band'])


def _avg_delay(df):
    aff = df['upgrade_delay_mw_affected'].sum()
    return float(df['upgrade_delay_mw_yr'].sum() / aff) if aff > 1e-9 else 0.0


def access_summary(run):
    """
    Access benefits of shared savings, reported separately from the bill: they
    go to the customers being connected, not to existing residential customers.

    Input: run = project_layers() output.
    Output: dict: MW connected sooner (2035, 2050, peak year; MW); Upgrade Delay
      for Interconnection, BAU and SS (average years per MW affected, i.e. MW
      that waited at least a year; load still waiting in 2050 is counted to the
      end of 2050) and SS per MW affected in BAU (like-for-like); MW affected,
      BAU and SS; MW-years avoided; connection cost avoided by new customers
      ($M undiscounted nominal and NPV 3%, 2026 $); electrification GWh brought
      forward (cumulative); flexible connections MW in 2050.
    """
    b, s = run['bau'], run['ss']
    yrs = s['year'].values
    return {'MW connected sooner, 2035': float(s.loc[s['year'] == 2035, 'enabled_mw'].iloc[0]),
            'MW connected sooner, 2050': float(s.loc[s['year'] == 2050, 'enabled_mw'].iloc[0]),
            'MW connected sooner, peak year': float(s['enabled_mw'].max()),
            f'{UD}, BAU (avg yr per MW affected)': _avg_delay(b),
            f'{UD}, SS (avg yr per MW affected)': _avg_delay(s),
            f'{UD}, SS (avg yr per MW affected in BAU)': (
                float(s['upgrade_delay_mw_yr'].sum() / b['upgrade_delay_mw_affected'].sum())
                if b['upgrade_delay_mw_affected'].sum() > 1e-9 else 0.0),
            'MW affected by upgrade delay, BAU (2026-2050 requests)': float(b['upgrade_delay_mw_affected'].sum()),
            'MW affected by upgrade delay, SS (2026-2050 requests)': float(s['upgrade_delay_mw_affected'].sum()),
            f'{UD} avoided (MW-years)': float(s['upgrade_delay_mw_yr_avoided'].sum()),
            'Connection cost avoided by new customers ($M, undiscounted nominal)':
                float(s['connection_cost_avoided_m'].sum()),
            'Connection cost avoided by new customers ($M, NPV 3%, 2026 $)':
                _npv(s['connection_cost_avoided_m'].values, yrs, 0.03),
            'Electrification GWh brought forward (cumulative)': float(s['electrification_gwh_brought_forward'].sum()),
            'Flexible connections MW, 2050': float(s['flex_conn_mw'].iloc[-1])}


def upgrade_delay_table(run, years=(2026, 2028, 2030, 2032, 2035, 2040, 2050)):
    """
    Upgrade Delay for Interconnection by year, BAU vs shared savings.

    Inputs: run = project_layers() output; years.
    Output: DataFrame indexed by year: average years waited by load requested
      that year (MW affected only), MW affected (requested that year), MW
      waiting for upgrade, and MW-years of delay avoided (that calendar year).
    """
    b, s = run['bau'].set_index('year'), run['ss'].set_index('year')
    rows = []
    for y in years:
        rows.append({'year': y,
                     f'BAU {UD} (yr)': b.loc[y, 'upgrade_delay_yr'], f'SS {UD} (yr)': s.loc[y, 'upgrade_delay_yr'],
                     'BAU MW affected (requested that year)': b.loc[y, 'upgrade_delay_mw_affected'],
                     'SS MW affected (requested that year)': s.loc[y, 'upgrade_delay_mw_affected'],
                     'BAU MW waiting for upgrade': b.loc[y, 'upgrade_wait_mw'],
                     'SS MW waiting for upgrade': s.loc[y, 'upgrade_wait_mw'],
                     'MW-years of delay avoided': s.loc[y, 'upgrade_delay_mw_yr_avoided']})
    return pd.DataFrame(rows).set_index('year')


def access_table(utility_json, params, overrides=None, scenarios=SCENARIOS, network=None):
    """
    access_summary() for each scenario.

    Inputs: utility_json, params; overrides; scenarios; network {param: value}
      applied to every scenario.
    Output: DataFrame, one row per scenario, access_summary() columns.
    """
    return pd.DataFrame({sc: access_summary(project_layers(utility_json, params, scenario=sc, overrides=overrides,
                                                           network=network))
                         for sc in scenarios}).T


def no_ramp_overrides():
    """
    Overrides that remove the maximum annual MW growth for every resource type.

    Output: {('programs', 'ramp_pct_peak_<type>'): None} for FLEX_TYPES.
    """
    return {('programs', f'ramp_pct_peak_{k}'): None for k in FLEX_TYPES}


def mw_path_table(utility_json, params, scenario='Central', years=(2030, 2035, 2040, 2050)):
    """
    Shared-savings flexible MW, target path vs with the ramp limit.

    Inputs: utility_json, params; scenario; years.
    Output: DataFrame indexed by (path, year): nameplate MW per type and total.
    """
    runs = {'target path': project_layers(utility_json, params, scenario=scenario, overrides=no_ramp_overrides()),
            'with ramp limit': project_layers(utility_json, params, scenario=scenario)}
    rows = []
    for lbl, r in runs.items():
        m = r['mw'].set_index('year')
        for y in years:
            row = {'path': lbl, 'year': y, **{FLEX_LABEL[k]: m.loc[y, f'{k}_ss_mw'] for k in FLEX_TYPES}}
            row['Total flexible MW'] = sum(m.loc[y, f'{k}_ss_mw'] for k in FLEX_TYPES)
            rows.append(row)
    return pd.DataFrame(rows).set_index(['path', 'year'])


# ── System-wide savings and the headroom sweep ───────────────────────────────

def supply_rate_kwh(run):
    """
    Today's residential supply energy rate.

    Input: run = project_layers() output.
    Output: float, $/kWh (supply_energy lines at benchmark usage / benchmark kWh, 2026 $).
    """
    sup = sum(d['month'] for d in run['starting_lines'] if d['category'] == 'supply_energy')
    return sup / run['benchmark_kwh']


def system_summary(run):
    """
    System-wide results, BAU minus shared savings, all customers.

    Input: run = project_layers() output.
    Customer savings = what all customers pay for delivery (revenue requirement,
    net of shared savings earnings and including any ROE change) + program
    surcharges + capacity, plus the energy no longer bought because of
    efficiency, valued at today's residential supply rate grown at
    supply_energy_growth (applied to every class, so it likely overstates the
    commercial and industrial share), plus the value-stream layers: wholesale
    energy (load shifted to off-peak hours), avoided transmission and avoided
    marginal distribution losses. Efficiency energy is counted once (the
    wholesale layer values only load shifting). Wires capex avoided = BAU capex
    - SS capex - connection capex.
    Output: dict of labelled measures; each key states its unit and basis ($B
      undiscounted nominal or NPV 3% in 2026 $, $M, MW, MW-years, years).
    """
    b, s = run['bau'], run['ss']
    yrs = s['year'].values
    t = yrs - yrs[0]
    pay = lambda d: d['rr_m'] + d['program_bill_cost_m'] + d['capacity_cost_m']
    delivery = (pay(b) - pay(s)).values
    g = run['assumptions']['projection']['supply_energy_growth']
    ee_energy = s['ee_gwh'].values * supply_rate_kwh(run) * (1 + g) ** t
    col = lambda c: s[c].values if c in s.columns else np.zeros(len(s))
    whl, txa = col('wholesale_value_m'), col('transmission_avoided_m')
    loss = col('losses_energy_value_m') + col('losses_peak_value_m')
    roe = col('roe_cost_m')
    total = delivery + ee_energy + whl + txa + loss
    capex = (b['capex_m'] - s['capex_m'] - s['conn_capex_m']).values
    capc = (b['capacity_cost_m'] - s['capacity_cost_m']).values
    earn = s['shared_savings_earnings_m'].values
    acc = access_summary(run)
    return {
        'Customer savings ($B, undiscounted nominal)': total.sum() / 1e3,
        'Customer savings ($B, NPV 3%, 2026 $)': _npv(total, yrs, 0.03) / 1e3,
        'of which efficiency energy ($B, undiscounted nominal)': ee_energy.sum() / 1e3,
        'of which wholesale energy, load shifted ($B, undiscounted nominal)': whl.sum() / 1e3,
        'of which avoided transmission ($B, undiscounted nominal)': txa.sum() / 1e3,
        'of which avoided distribution losses ($B, undiscounted nominal)': loss.sum() / 1e3,
        'of which ROE change, cost to customers ($B, undiscounted nominal)': -roe.sum() / 1e3,
        'Wires capex avoided or deferred ($B, undiscounted nominal)': capex.sum() / 1e3,
        'Wires capex avoided or deferred ($B, NPV 3%, 2026 $)': _npv(capex, yrs, 0.03) / 1e3,
        'Reinforcement deferred (MW)': float(b['reinforcement_in_service_mw'].sum() - s['reinforcement_in_service_mw'].sum()),
        'Capacity cost avoided ($B, undiscounted nominal)': capc.sum() / 1e3,
        'Shared savings earnings ($B, undiscounted nominal)': earn.sum() / 1e3,
        'Shared savings earnings ($B, NPV 3%, 2026 $)': _npv(earn, yrs, 0.03) / 1e3,
        'MW connected sooner (peak year)': acc['MW connected sooner, peak year'],
        f'{UD} avoided (MW-years)': acc[f'{UD} avoided (MW-years)'],
        f'{UD}, BAU (avg yr)': acc[f'{UD}, BAU (avg yr per MW affected)'],
        f'{UD}, SS (avg yr)': acc[f'{UD}, SS (avg yr per MW affected)'],
        f'{UD}, SS (avg yr per MW affected in BAU)': acc[f'{UD}, SS (avg yr per MW affected in BAU)'],
        'MW affected by upgrade delay, BAU': acc['MW affected by upgrade delay, BAU (2026-2050 requests)'],
        'Connection cost avoided ($M, undiscounted nominal)':
            acc['Connection cost avoided by new customers ($M, undiscounted nominal)'],
        'BAU MW waiting for upgrade, peak': float(b['upgrade_wait_mw'].max()),
        'BAU MW above planning limit, 2026': float(b['above_planning_limit_mw'].iloc[0]),
    }


SWEEP_MEANS = tuple(round(0.60 + 0.05 * i, 2) for i in range(9))       # 60% to 100%
SWEEP_SUBBAND = (0.0, 0.02, 0.043, 0.08, 0.15)
# Upgrade Delay for Interconnection cases: short = low delays + high clearance; long = the reverse
DELAY_CASES = {'short': {'upgrade_delay_ordinary_years': 'low', 'upgrade_delay_large_years': 'low',
                         'backlog_clearance_pct': 'high'},
               'central': {},
               'long': {'upgrade_delay_ordinary_years': 'high', 'upgrade_delay_large_years': 'high',
                        'backlog_clearance_pct': 'low'}}


def headroom_sweep(utility_json, params, means=SWEEP_MEANS, shares=SWEEP_SUBBAND, delay_cases=tuple(DELAY_CASES),
                   scenario='Central', network=None, measure='average'):
    """
    Headroom sweep.

    Inputs: utility_json, params; means (mean starting planning utilisation,
      shares); shares (share of network load in the constrained sub-band; 0 =
      no sub-band); delay_cases (keys of DELAY_CASES: short / central / long =
      upgrade delays and backlog clearance at low / central / high); scenario;
      network {param: value} adds fixed inputs (e.g. flex_targeting_enabled);
      measure.
    Output: DataFrame, one row per (delay case, mean, share): '2050 monthly
      saving ($, nominal)' plus every system_summary() measure.
    """
    col = MEASURE_COL[measure]
    rows = []
    for dc in delay_cases:
        for m in means:
            for x in shares:
                nw = {**(network or {}), **DELAY_CASES[dc], 'mean_utilisation': m, 'subband_enabled': x > 0,
                      'subband_load_share': x}
                r = project_layers(utility_json, params, scenario=scenario, network=nw)
                row = {'delay case': dc, 'mean utilisation': m, 'sub-band share': x,
                       '2050 monthly saving ($, nominal)': _at(r['bau'], 2050, col) - _at(r['ss'], 2050, col)}
                row.update(system_summary(r))
                rows.append(row)
    return pd.DataFrame(rows)


def layer_contributions(utility_json, params, scenario=None, years=(2035, 2050), measure='average'):
    """
    Each savings layer's contribution to the full shared-savings case.

    Inputs: utility_json, params; scenario; years; measure. Layers are added one
      at a time in LAYERS order (the waterfall order).
    Output: DataFrame indexed by layer: customer savings ($B, undiscounted nominal
      and NPV 3%, 2026 $), the change in the monthly bill in each year ($/month
      nominal, negative = lower bill), shared savings earnings ($B), the
      utility's equity return on rate base ($B, undiscounted nominal), and the
      layer's contribution to the savings pool ($B, undiscounted nominal and
      NPV 3%). Rows sum to the full case.
    In that order all earnings fall on the mechanism step, so 'earnings
    attributable' splits the full case's shared savings earnings across the
    layers in proportion to each layer's contribution to the pool (undiscounted
    for the undiscounted column, NPV 3% for the NPV column). A layer that lowers
    the pool (e.g. programs, whose costs come before the savings they enable)
    takes a negative share. The pool does not depend on the mechanism, so the
    contributions come from the same sequential pass; the split sums to the
    full case's earnings.
    """
    col = MEASURE_COL[measure]
    fa = utility_json['forward_assumptions']
    base_on = {l: bool(fa['layers'].get(l, {}).get('enabled', False)) and not fa['layers'].get(l, {}).get('hook')
               for l in LAYERS}
    state = {**base_on, **{l: False for l in SAVINGS_LAYERS}}

    def stats(r):
        sm = system_summary(r)
        yrs = r['ss']['year'].values
        pool = np.nan_to_num(r['ss']['savings_pool_m'].values)
        return {'cs': sm['Customer savings ($B, undiscounted nominal)'], 'cs3': sm['Customer savings ($B, NPV 3%, 2026 $)'],
                **{y: _at(r['ss'], y, col) for y in years},
                'earn': r['ss']['shared_savings_earnings_m'].sum() / 1e3,
                'earn3': _npv(r['ss']['shared_savings_earnings_m'].values, yrs, 0.03) / 1e3,
                'eq': r['ss']['equity_return_m'].sum() / 1e3,
                'pool': pool.sum() / 1e3, 'pool3': _npv(pool, yrs, 0.03) / 1e3}

    prev = stats(project_layers(utility_json, params, enabled=state, scenario=scenario))
    rows = []
    for l in SAVINGS_LAYERS:
        if base_on[l]:
            state[l] = True
            cur = stats(project_layers(utility_json, params, enabled=dict(state), scenario=scenario))
        else:
            cur = prev
        rows.append({'layer': l,
                     'Customer savings ($B, undiscounted nominal)': cur['cs'] - prev['cs'],
                     'Customer savings ($B, NPV 3%, 2026 $)': cur['cs3'] - prev['cs3'],
                     **{f'Monthly bill {y} ($, nominal)': cur[y] - prev[y] for y in years},
                     'Shared savings earnings ($B, undiscounted nominal)': cur['earn'] - prev['earn'],
                     'Shared savings earnings ($B, NPV 3%, 2026 $)': cur['earn3'] - prev['earn3'],
                     'Utility equity return ($B, undiscounted nominal)': cur['eq'] - prev['eq'],
                     'Savings pool contribution ($B, undiscounted nominal)': cur['pool'] - prev['pool'],
                     'Savings pool contribution ($B, NPV 3%, 2026 $)': cur['pool3'] - prev['pool3']})
        prev = cur
    out = pd.DataFrame(rows).set_index('layer')
    for basis, key in (('undiscounted nominal', 'earn'), ('NPV 3%, 2026 $', 'earn3')):
        c = out[f'Savings pool contribution ($B, {basis})']
        tot = c.sum()
        out[f'Shared savings earnings attributable ($B, {basis})'] = (c / tot * prev[key]) if abs(tot) > 1e-12 else 0.0
    return out
