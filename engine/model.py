# engine/model.py
# GridDividend model engine — utility-agnostic
# All parameters passed explicitly via config dict.
# No globals are read from the calling notebook's namespace.

import pandas as pd
import numpy as np

# ── Helper functions ──────────────────────────────────────────────────────────

def get_elec_ramp(year, config):
    for (y0, y1), r in config['ELECTRIFICATION_RAMP'].items():
        if y0 <= year <= y1: return r
    return 0.005

def get_nws_eligible_share(cum_elec_load, config):
    """NWS-eligible CAPEX grows with cumulative electrification load."""
    share_start = config['NWS_ELIGIBLE_CAPEX_SHARE_START']
    share_max   = config['NWS_ELIGIBLE_CAPEX_SHARE_MAX']
    sensitivity = config['NWS_ELIGIBLE_CAPEX_LOAD_SENSITIVITY']
    gap = share_max - share_start
    return share_start + gap * min(1.0, cum_elec_load * sensitivity)

def get_nws_avoidance_of_eligible(year, config):
    """NWS avoidance ramps from START to MATURE over ramp years."""
    start       = config['NWS_AVOIDANCE_OF_ELIGIBLE_START']
    mature      = config['NWS_AVOIDANCE_OF_ELIGIBLE_MATURE']
    ramp_years  = config['NWS_AVOIDANCE_RAMP_YEARS']
    if year <= 2026: return start
    if year >= 2026 + ramp_years: return mature
    t = (year - 2026) / ramp_years
    return start + t * (mature - start)

def get_utilisation_credit(year, scenario, config):
    """
    Utilisation credit — Brattle Untapped Grid mechanism.
    Flexible load uses existing system headroom without triggering proportional
    CAPEX, spreading fixed costs over more kWh and reducing delivery cost/kWh.
    Ramps with DER maturity: 30% of full credit in 2026, 100% by 2035.
    Zero in BAU: no intentional utilisation optimisation.
    """
    share_ss   = config['FLEX_LOAD_UTILISATION_SHARE_SS']
    share_bau  = config['FLEX_LOAD_UTILISATION_SHARE_BAU']
    ramp_years = config['NWS_AVOIDANCE_RAMP_YEARS']
    if scenario == 'bau': return share_bau
    t = min(1.0, max(0.0, (year - 2026) / ramp_years))
    return share_ss * (0.30 + 0.70 * t)

def get_storage_mw(params, year, scenario, peak_mw, config):
    """Battery storage grows logistically toward STORAGE_MAX_PCT_OF_PEAK."""
    max_pct         = config['STORAGE_MAX_PCT_OF_PEAK']
    growth_bau      = config['STORAGE_GROWTH_BAU']
    growth_shared   = config['STORAGE_GROWTH_SHARED']
    lead_years      = config['DER_ADOPTION_LEAD_YEARS']
    base = params['der_storage_mw_start']
    cap  = peak_mw * max_pct
    rate = growth_shared if scenario == 'shared' else growth_bau
    eff_yrs = max(0, year - 2026 + (lead_years if scenario == 'shared' else 0))
    k = (cap - base) / base if base > 0 else 0
    if k <= 0: return min(base, cap)
    return min(cap / (1 + k * np.exp(-rate * eff_yrs)), cap)

def get_territory_ev(params, year, scenario, config):
    """Territory EV count apportioned by customer share; managed fraction applied."""
    ev_managed_shared = config['EV_MANAGED_CHARGING_SHARED']
    ev_adoption_curve = config['EV_ADOPTION_CURVE']
    ev_peak_kw        = config['EV_PEAK_KW']
    # Territory share of the EV_ADOPTION_CURVE. Default (v1.0): customers / 8M,
    # an NY-calibrated constant. A utility JSON may set 'ev_territory_share'
    # directly (e.g. its share of statewide EV registrations) when the curve is
    # a statewide count for a state of different size.
    share = params.get('ev_territory_share', params['electric_customers'] / 8_000_000)
    c2 = ev_adoption_curve
    ys2 = sorted(c2); vs = [c2[y] for y in ys2]
    base_ev = int(np.interp(2026, ys2, vs)) * share
    eff_year = min(2050, 2026 + (year - 2026) * 1.25) if scenario == 'shared' else year
    total_ev = max(int(np.interp(eff_year, ys2, vs)) * share, base_ev)
    mev = params['ev_managed_charging_pct_bau'] if scenario == 'bau' else ev_managed_shared
    return total_ev, total_ev * mev * ev_peak_kw / 1000


SAVINGS_POOL_BASES       = ('capex', 'revenue_requirement')
NEGATIVE_POOL_TREATMENTS = ('symmetric', 'floor_zero', 'carry_forward')
NWS_COST_TREATMENTS      = ('expense', 'capitalise')
BILL_INDEX_BASES         = ('own', 'bau')

# Annual rate-base decay used in project(): rb = rb * (1 - RATE_BASE_DECAY) + ...
RATE_BASE_DECAY = 0.035

# Other O&M as a share of 2026 delivery RR below which the depreciation
# recalibration is flagged as implausibly low (distribution utilities typically
# run roughly 25-45% O&M excluding depreciation and taxes; model judgement).
OTHER_OM_LOW_SHARE  = 0.15
OTHER_OM_HIGH_SHARE = 0.50   # above this, rate base (or revenue) inputs look inconsistent

# Named config presets. Not applied unless the caller asks (apply_preset()).
PRESETS = {
    # Recommended corrections, switched on together:
    #  - depreciation expense in delivery RR, other O&M recalibrated to the
    #    rate-case delivery RR
    #  - savings pool measured as the delivery RR reduction vs BAU
    #  - negative early-year pools carried forward, not charged to the utility
    #  - all scenarios' bills indexed to the BAU 2026 revenue requirement
    #  - capacity pass-through credited to residential bills by class sales
    #    share (CAPACITY_SAVINGS_ALLOCATION = 'sales_share')
    #  - capacity prices grow at INFLATION_RATE (flat in real terms) in every
    #    market
    'CORRECTED': {
        'INCLUDE_DEPRECIATION_EXPENSE': True,
        'SAVINGS_POOL_BASIS':           'revenue_requirement',
        'NEGATIVE_POOL_TREATMENT':      'carry_forward',
        'BILL_INDEX_BASE':              'bau',
        'NWS_COST_TREATMENT':           'expense',
        'ROE_OVERRIDE_REBASE_BILL':     True,
        'CAPACITY_SAVINGS_ALLOCATION':  'sales_share',
        'CAPACITY_COST_GROWTH':         'INFLATION_RATE',
    },
}
# Named sensitivity: CORRECTED, but capacity prices keep each notebook's
# default growth (NYISO 3%/yr, PJM 5%/yr; PEPCO's zone override still applies).
PRESETS['CORRECTED_MARKET_CAPACITY_GROWTH'] = {
    k: v for k, v in PRESETS['CORRECTED'].items() if k != 'CAPACITY_COST_GROWTH'}

CAPACITY_SAVINGS_ALLOCATIONS = ('per_customer', 'sales_share')


def apply_preset(config, name):
    """
    Return a copy of config with the named PRESETS entry applied. A preset
    value of 'INFLATION_RATE' is resolved to config['INFLATION_RATE'].
    """
    if name not in PRESETS:
        raise ValueError(f"Unknown preset {name!r}; choose from {list(PRESETS)}")
    vals = {k: (config['INFLATION_RATE'] if v == 'INFLATION_RATE' else v)
            for k, v in PRESETS[name].items()}
    return {**config, **vals, 'MODEL_PRESET': name}


def config_with(config, **overrides):
    """
    Copy of config with explicit overrides, recorded in CONFIG_OVERRIDES so
    they take precedence over utility-JSON values (see nws_eligible_bounds()).
    Use for sensitivities that vary a parameter a utility JSON may also set.
    """
    prev = tuple(config.get('CONFIG_OVERRIDES', ()))
    return {**config, **overrides,
            'CONFIG_OVERRIDES': tuple(dict.fromkeys(prev + tuple(overrides)))}


def nws_eligible_bounds(params, config):
    """
    (start, max) NWS-eligible CAPEX share for a utility. Precedence:
    explicit override (CONFIG_OVERRIDES, e.g. a named scenario) > utility JSON
    (nws_eligible_capex_share_start / _max) > config (notebook Section 1).
    """
    ovr = config.get('CONFIG_OVERRIDES', ())
    out = []
    for ckey, jkey in (('NWS_ELIGIBLE_CAPEX_SHARE_START', 'nws_eligible_capex_share_start'),
                       ('NWS_ELIGIBLE_CAPEX_SHARE_MAX', 'nws_eligible_capex_share_max')):
        if ckey not in ovr and params.get(jkey) is not None:
            out.append(params[jkey])
        else:
            out.append(config[ckey])
    return tuple(out)


def capacity_allocation_factor(params, config):
    """
    Multiplier on the per-head residential capacity credit.
    'per_customer' (default, v1.0): 1.0 — the customer share is spread
      equally over ALL customers and credited to the residential bill.
    'sales_share': residential share of sales / residential share of
      customers (utility JSON, EIA-861), so the residential class receives its
      sales share; outputs are then per RESIDENTIAL customer.
    """
    mode = config.get('CAPACITY_SAVINGS_ALLOCATION', 'per_customer')
    if mode not in CAPACITY_SAVINGS_ALLOCATIONS:
        raise ValueError(f"CAPACITY_SAVINGS_ALLOCATION must be one of "
                         f"{CAPACITY_SAVINGS_ALLOCATIONS}, got {mode!r}")
    if mode == 'per_customer':
        return 1.0
    try:
        return params['residential_sales_share'] / params['residential_customer_share']
    except KeyError as e:
        raise KeyError(f"{params.get('key', '?')}: {e.args[0]} missing from utility JSON "
                       "(needed for CAPACITY_SAVINGS_ALLOCATION='sales_share')") from None


def per_customer_label(config):
    """'per residential customer' under sales_share allocation, else 'per customer'."""
    return ('per residential customer'
            if config.get('CAPACITY_SAVINGS_ALLOCATION', 'per_customer') == 'sales_share'
            else 'per customer')


def capacity_cost_in_year(config, utility_key, year):
    """
    Capacity cost ($M per MW-year, nominal) for one utility in one year:
    CAPACITY_COST_START × (1 + CAPACITY_COST_GROWTH) ** (year − 2026).
    Either config value may be a scalar or a dict keyed by utility, so a
    market or zone can carry its own growth rate (e.g. PEPCO at inflation)
    without changing other utilities.
    """
    start = config['CAPACITY_COST_START']
    growth = config['CAPACITY_COST_GROWTH']
    start = start[utility_key] if isinstance(start, dict) else start
    growth = growth[utility_key] if isinstance(growth, dict) else growth
    return start * (1 + growth) ** (year - 2026)


def passthrough_utility_share(config):
    """
    (utility share of capacity pass-through, whether it follows the pool).
    PASSTHROUGH_UTILITY_SHARE = None (default) → UTILITY_SAVINGS_SHARE, and the
    pass-through saving counts in incentive_base_m (v1.0 behaviour). A number
    fixes the utility's pass-through share (0 = customers keep 100%); the
    pass-through is then excluded from incentive_base_m and its utility income
    is reported in fixed_shared_income_m.
    """
    s = config.get('PASSTHROUGH_UTILITY_SHARE')
    if s is None:
        return config['UTILITY_SAVINGS_SHARE'], True
    return s, False


def _check_option(cfg, key, default, allowed):
    val = cfg.get(key, default)
    if val not in allowed:
        raise ValueError(f"{key} must be one of {allowed}, got {val!r}")
    return val


def delivery_rr_reconciliation(params, config):
    """
    2026 delivery revenue requirement build-up (BAU, nominal $M) at the
    rate-case WACC, against the rate-case delivery RR
    (total_revenue_m × delivery_share_rr).

    Returns a dict with the target, return, property tax, depreciation
    (RATE_BASE_DECAY × opening rate base), other O&M under the v1.0 rule
    (35% of delivery RR less property tax) and the recalibrated other O&M
    used when INCLUDE_DEPRECIATION_EXPENSE is on
    (= target − return − property tax − depreciation), plus warnings.
    """
    wacc   = params.get('rate_case_wacc', params['wacc'])
    rb0    = params['rate_base_start_m']
    rb26   = rb0 * 0.965 + params['annual_capex_m']          # first-year BAU rate base
    target = params['total_revenue_m'] * params['delivery_share_rr']
    ret    = rb26 * wacc
    ptax   = rb26 * params['property_tax_rate']
    dep    = RATE_BASE_DECAY * rb0
    om_v10 = max(0, target * 0.35 - rb0 * params['property_tax_rate'])
    om_cal = target - ret - ptax - dep
    warnings = []
    if om_cal < 0:
        warnings.append(f"recalibrated other O&M is NEGATIVE ({om_cal:,.0f} $M); floored at 0")
    elif om_cal < OTHER_OM_LOW_SHARE * target:
        warnings.append(f"recalibrated other O&M is only {om_cal / target:.0%} of delivery RR "
                        f"(< {OTHER_OM_LOW_SHARE:.0%}) — implausibly low")
    elif om_cal > OTHER_OM_HIGH_SHARE * target:
        warnings.append(f"recalibrated other O&M is {om_cal / target:.0%} of delivery RR "
                        f"(> {OTHER_OM_HIGH_SHARE:.0%}) — implausibly high; rate base may be "
                        f"understated relative to rate-case revenue")
    return dict(target_delivery_rr_m=target, return_m=ret, property_tax_m=ptax,
                depreciation_m=dep, other_om_v10_m=om_v10,
                v10_delivery_rr_m=ret + ptax + om_v10,
                other_om_recalibrated_m=om_cal,
                other_om_recalibrated_share=om_cal / target if target else float('nan'),
                warnings=warnings)


def apply_roe_override(params, roe, config):
    """
    Return a copy of params with the allowed ROE replaced by `roe`.

    WACC is recomputed exactly as load_utility() does:
        wacc = roe * equity_ratio + COST_OF_DEBT * (1 - equity_ratio)

    If config['ROE_OVERRIDE_REBASE_BILL'] is True (the default), the starting
    delivery bill is also rescaled by the ratio of the first-year BAU delivery
    revenue requirement at `roe` to that at the rate-case ROE. project() indexes
    each year's delivery bill to its own first-year revenue requirement, so
    without this rebase a different ROE would change bill growth but not the
    starting tariff level, which was set at the rate-case ROE.
    """
    p = dict(params)
    p['rate_case_wacc'] = params.get('rate_case_wacc', params['wacc'])
    p['roe']  = roe
    p['wacc'] = roe * p['equity_ratio'] + config['COST_OF_DEBT'] * (1 - p['equity_ratio'])
    if config.get('ROE_OVERRIDE_REBASE_BILL', True) and roe != params['roe']:
        base_cfg = {**config, 'ROE_OVERRIDE': None}
        rr_rate_case = project(params, 'bau', config=base_cfg)['delivery_rr_m'].iloc[0]
        rr_override  = project(p,      'bau', config=base_cfg)['delivery_rr_m'].iloc[0]
        p['start_delivery_bill_monthly'] = (params['start_delivery_bill_monthly']
                                            * rr_override / rr_rate_case)
        p['start_monthly_bill'] = (p['start_delivery_bill_monthly']
                                   + p['start_supply_bill_monthly'])
    return p


# ── Core projection function ───────────────────────────────────────────────────

def project(params, scenario='bau', apply_freeze=False, config=None, bau_ref=None):
    """
    Project utility financials and residential customer bills 2026–2050.

    Parameters
    ----------
    params       : dict from load_utility()
    scenario     : 'bau' or 'shared'
    apply_freeze : bool — apply two-year rate freeze overlay
    config       : dict of all Section 1 model parameters (see notebook
                   MODEL_CONFIG). Required — no values are read from globals.
                   Optional keys (defaults reproduce v1.0 results):
                     SAVINGS_POOL_BASIS  'capex' (default) or
                                         'revenue_requirement' — see below
                     ROE_OVERRIDE        None (default) or an ROE to use in
                                         place of params['roe']; see
                                         apply_roe_override()
                     INCLUDE_DEPRECIATION_EXPENSE  False (default). True adds
                                         RATE_BASE_DECAY × opening rate base
                                         to delivery RR and recalibrates other
                                         O&M so 2026 BAU delivery RR equals the
                                         rate-case figure (see
                                         delivery_rr_reconciliation())
                     NEGATIVE_POOL_TREATMENT 'symmetric' (default: utility
                                         shares negative pools), 'floor_zero'
                                         (utility share never below zero) or
                                         'carry_forward' (negative pools netted
                                         against later positive pools, no
                                         interest)
                     NWS_COST_TREATMENT  'expense' (default) or 'capitalise':
                                         NWS OPEX goes into a regulatory asset
                                         in rate base, earning WACC and
                                         amortised straight-line over
                                         NWS_AMORTISATION_YEARS (default 10)
                     BILL_INDEX_BASE     'own' (default: each scenario's bill
                                         indexed to its own 2026 delivery RR)
                                         or 'bau' (indexed to BAU 2026
                                         delivery RR, so year-one differences
                                         show in bills)
    bau_ref      : optional BAU DataFrame from project(..., 'bau', ...) at the
                   same config. Only used when scenario='shared' and either
                   SAVINGS_POOL_BASIS='revenue_requirement' or
                   BILL_INDEX_BASE='bau'; computed here if not supplied.

    Savings pool basis
    ------------------
    'capex': pool = avoided CAPEX − NWS OPEX in the year of avoidance. The
        customer share is credited against that year's revenue requirement
        while the avoided CAPEX also stays out of rate base, so customers
        benefit twice from the same avoided dollar (v1.0 behaviour).
    'revenue_requirement': pool = reduction in delivery revenue requirement
        vs BAU (return + property tax on the avoided rate base) − NWS OPEX.
        Customers already receive the whole reduction through the lower rate
        base, so no separate customer credit is applied; the utility's share
        is recovered in the delivery revenue requirement. The pool is split
        symmetrically — in early years NWS OPEX can exceed the RR reduction,
        making the pool (and the utility's share) negative.

    Returns
    -------
    pd.DataFrame, one row per year, all financial metrics and bill components
    """
    cfg = config or {}
    POOL_BASIS  = _check_option(cfg, 'SAVINGS_POOL_BASIS', 'capex', SAVINGS_POOL_BASES)
    NEG_POOL    = _check_option(cfg, 'NEGATIVE_POOL_TREATMENT', 'symmetric',
                                NEGATIVE_POOL_TREATMENTS)
    COST_TREAT  = _check_option(cfg, 'NWS_COST_TREATMENT', 'expense', NWS_COST_TREATMENTS)
    INDEX_BASE  = _check_option(cfg, 'BILL_INDEX_BASE', 'own', BILL_INDEX_BASES)
    INCLUDE_DEP = bool(cfg.get('INCLUDE_DEPRECIATION_EXPENSE', False))
    AMORT_YEARS = cfg.get('NWS_AMORTISATION_YEARS', 10)
    if scenario == 'shared' and (POOL_BASIS == 'revenue_requirement' or INDEX_BASE == 'bau'):
        if bau_ref is None:
            # Paired run: BAU at the same config (and ROE override, if any)
            bau_ref = project(params, 'bau', apply_freeze=False, config=cfg)
        bau_core = bau_ref['traditional_earnings_m'] + bau_ref['property_tax_m']
        if INCLUDE_DEP:
            bau_core = bau_core + bau_ref['depreciation_m']
        bau_rr_by_year = dict(zip(bau_ref['year'], bau_core))
        bau_first_delivery_rr = bau_ref['delivery_rr_m'].iloc[0]
    if cfg.get('ROE_OVERRIDE') is not None:
        params = apply_roe_override(params, cfg['ROE_OVERRIDE'], cfg)
    # Pull all scalar params referenced directly in this function's body from
    # cfg once, up front, so the rest of the body reads local variables.
    # (Params only needed by the helper functions above are NOT pulled here —
    # they're passed straight through via cfg to those functions instead.)
    YEARS                           = cfg['YEARS']
    DIST_UPGRADE_COST_PER_MW        = cfg['DIST_UPGRADE_COST_PER_MW']
    RATE_FREEZE_YEARS               = cfg['RATE_FREEZE_YEARS']
    RATE_FREEZE_RECOVERY_YEARS      = cfg['RATE_FREEZE_RECOVERY_YEARS']
    BASELINE_LOAD_GROWTH            = cfg['BASELINE_LOAD_GROWTH']
    FLEX_LOAD_CAPTURE_BAU           = cfg['FLEX_LOAD_CAPTURE_BAU']
    FLEX_LOAD_CAPTURE_SHARED        = cfg['FLEX_LOAD_CAPTURE_SHARED']
    STORAGE_PEAK_OFFSET_KW_PER_MWH  = cfg['STORAGE_PEAK_OFFSET_KW_PER_MWH']
    NWS_DISPATCH_EFFICIENCY         = cfg['NWS_DISPATCH_EFFICIENCY']
    CAPEX_SPENT_FLOOR_GROWTH        = cfg['CAPEX_SPENT_FLOOR_GROWTH']
    OPEX_RATIO                      = cfg['OPEX_RATIO']
    DEFERRAL_FRACTION               = cfg['DEFERRAL_FRACTION']
    DEFERRAL_PERIOD_YEARS           = cfg['DEFERRAL_PERIOD_YEARS']
    INFLATION_RATE                  = cfg['INFLATION_RATE']
    UTILITY_SAVINGS_SHARE           = cfg['UTILITY_SAVINGS_SHARE']

    # Resolve per-utility upgrade cost (supports dict or scalar)
    _cost_per_mw = (DIST_UPGRADE_COST_PER_MW.get(params['key'], 2.0)
                    if isinstance(DIST_UPGRADE_COST_PER_MW, dict)
                    else DIST_UPGRADE_COST_PER_MW)
    rows = []
    rb   = params['rate_base_start_m']
    rr   = params['total_revenue_m']
    cust = params['electric_customers']
    egwh = params['annual_energy_gwh']
    pk   = params['peak_demand_mw']
    capex0   = params['annual_capex_m']
    ptbase   = rr * (1 - params['delivery_share_rr'])   # supply/pass-through base
    prop_tax_base = rb * params['property_tax_rate']
    other_om_base = max(0, rr * params['delivery_share_rr'] * 0.35 - prop_tax_base)
    if INCLUDE_DEP:
        other_om_base = max(0, delivery_rr_reconciliation(params, cfg)['other_om_recalibrated_m'])
    reg_vintages = []        # (year, amount) NWS OPEX capitalised into regulatory asset
    reg_asset = 0.0
    pool_carry = 0.0         # cumulative negative pool carried forward (≤ 0)

    cum_load = 1.0; cum_elec_load = 0.0
    deferred_pool = []       # list of (year, amount) tuples for deferral payback
    freeze_deferred_m = 0.0  # deferred bill amount during rate freeze
    freeze_yr_end  = 2026 + RATE_FREEZE_YEARS
    catchup_yr_end = freeze_yr_end + RATE_FREEZE_RECOVERY_YEARS

    # Bill components (tariff-anchored, tracked separately)
    delivery_bill = params['start_delivery_bill_monthly']
    supply_bill   = params['start_supply_bill_monthly']
    prev_delivery_rr = None
    if scenario == 'shared' and INDEX_BASE == 'bau':
        prev_delivery_rr = bau_first_delivery_rr   # first-year ratio = SS / BAU
    prev_capex_spent = None
    # NWS-eligible share bounds: utility JSON values when present (unless
    # explicitly overridden), else Section 1 config. See nws_eligible_bounds().
    _nws0, _nws1 = nws_eligible_bounds(params, cfg)
    nws_cfg = (cfg if (_nws0, _nws1) == (cfg['NWS_ELIGIBLE_CAPEX_SHARE_START'],
                                         cfg['NWS_ELIGIBLE_CAPEX_SHARE_MAX'])
               else {**cfg, 'NWS_ELIGIBLE_CAPEX_SHARE_START': _nws0,
                     'NWS_ELIGIBLE_CAPEX_SHARE_MAX': _nws1})
    dc_step_mw   = params.get('dc_load_step_mw', 0) or 0
    dc_step_year = params.get('dc_load_step_year', 9999)

    for year in YEARS:
        elr = get_elec_ramp(year, cfg)

        # Segmented load model — data centres grow independently from their
        # own starting MW at their own rate, instead of a blended rate applied
        # to the entire load base (the old dc_load_growth_annual approach
        # overstated dc-driven growth by ~4-5x for utilities where dc load is
        # a large share of total peak, e.g. Virginia).
        dc_mw_start = params.get('dc_load_mw_start', 0)
        dc_rate     = params.get('dc_load_growth_rate', params.get('dc_load_growth_annual', 0))
        base_growth = BASELINE_LOAD_GROWTH + elr

        dc_load_year = dc_mw_start * (1 + dc_rate) ** (year - 2026)
        base_pk      = (params['peak_demand_mw'] - dc_mw_start) * (1 + base_growth) ** (year - 2026)

        prior_dc     = dc_mw_start * (1 + dc_rate) ** (year - 2026 - 1)
        # Optional one-off data-centre step (e.g. a single large campus):
        # dc_load_step_mw added to the dc segment from dc_load_step_year on.
        # It raises peak in full but distribution capex only through
        # dc_distribution_share (see tlg_capex below).
        # Absent / 0 (default) leaves every existing utility unchanged.
        if dc_step_mw:
            if year >= dc_step_year:
                dc_load_year += dc_step_mw
            if year - 1 >= dc_step_year:
                prior_dc += dc_step_mw
        pk_natural   = base_pk + dc_load_year   # organic total peak, before flex-load capture
        prior_base   = (params['peak_demand_mw'] - dc_mw_start) * (1 + base_growth) ** (year - 2026 - 1)
        prior_pk     = prior_base + prior_dc

        # tlg is the effective blended total-load growth rate this year, derived
        # from the segmented model rather than assumed as a fixed sum of rates.
        # It still drives revenue requirement, supply revenue, and utilisation
        # credit calculations below, unchanged. The existing scenario-dependent
        # flex-load-capture dampening (pk update at the end of the loop) is
        # applied to this rate exactly as before — the segmented model only
        # changes how the *natural* (pre-capture) growth rate is derived.
        tlg = (pk_natural / prior_pk) - 1 if prior_pk > 0 else base_growth
        # dcr = the data-centre segment's marginal contribution to tlg this
        # year (replaces the old fixed dc_load_growth_annual input — correctly
        # weighted by the dc segment's actual share of total load, rather than
        # applied uniformly to the whole load base). Retained under the same
        # name because it still feeds cum_elec_load and dc_fl below.
        dcr = tlg - base_growth

        # Capex-relevant growth. For the optional dc step, only the share
        # connected at distribution voltage (dc_distribution_share) drives
        # utility-funded distribution capex and NWS eligibility; the rest is
        # assumed transmission-connected or CIAC/customer-funded (large-load
        # tariffs). The full step still counts in peak (tlg), so capacity and
        # supply effects are unchanged. Without a step these equal tlg / dcr.
        if dc_step_mw:
            ext = dc_step_mw * (1 - params.get('dc_distribution_share', 0))
            pk_capex    = pk_natural - (ext if year >= dc_step_year else 0.0)
            prior_capex = prior_pk - (ext if year - 1 >= dc_step_year else 0.0)
            tlg_capex = (pk_capex / prior_capex) - 1 if prior_capex > 0 else base_growth
            dcr_capex = tlg_capex - base_growth
        else:
            tlg_capex, dcr_capex = tlg, dcr

        cum_elec_load += (elr + dcr_capex)
        annual_capex   = capex0 * cum_load
        eligible_share = get_nws_eligible_share(cum_elec_load, nws_cfg)
        eligible_capex = annual_capex * eligible_share

        smw = get_storage_mw(params, year, scenario, pk, cfg)
        _, ev_nws_mw = get_territory_ev(params, year, scenario, cfg)
        flc = FLEX_LOAD_CAPTURE_BAU if scenario == 'bau' else FLEX_LOAD_CAPTURE_SHARED

        # NWS physical capability (Option C: MW × cost/MW cross-check)
        st_off  = smw * STORAGE_PEAK_OFFSET_KW_PER_MWH
        dc_fl   = pk * dcr * params['dc_distribution_share'] * params['dc_flexibility_share']
        nws_mw  = (ev_nws_mw + st_off + dc_fl) * NWS_DISPATCH_EFFICIENCY
        nws_val = nws_mw * _cost_per_mw

        # ── Mechanism 1: NWS CAPEX avoidance ─────────────────────────────────
        if scenario == 'bau':
            capex_spent = annual_capex
            nws_opex = av = ea = 0.0
            floor_binding = False
        else:
            aoe = get_nws_avoidance_of_eligible(year, cfg)
            # Avoided CAPEX: min of policy ceiling and physical NWS capability
            av = min(min(eligible_capex * aoe, nws_val), eligible_capex)
            capex_spent_raw = annual_capex - av
            floor_binding = False
            # Floor: CAPEX spent must grow by at least 0.5%/yr
            # (NWS defers future projects, not current commitments)
            if prev_capex_spent is not None:
                floor = prev_capex_spent * (1 + CAPEX_SPENT_FLOOR_GROWTH)
                if capex_spent_raw < floor:
                    capex_spent_raw = floor
                    av = max(0, annual_capex - capex_spent_raw)
                    floor_binding = True
            capex_spent = capex_spent_raw
            ea = av / max(1, annual_capex)
            nws_opex = av * OPEX_RATIO
        prev_capex_spent = capex_spent

        # ── Revenue requirement ───────────────────────────────────────────────
        # ── Rate base update with deferral payback ────────────────────────────────────────────
        # Deferred CAPEX (avoided × DEFERRAL_FRACTION) re-enters rate base after
        # DEFERRAL_PERIOD_YEARS. DEFERRAL_FRACTION = 0.0 reproduces prior results.
        if scenario == 'shared' and DEFERRAL_FRACTION > 0:
            deferred_this_year = av * DEFERRAL_FRACTION
            deferred_pool.append((year, deferred_this_year))
        else:
            deferred_this_year = 0.0

        payback_this_year = sum(
            amt for (yr, amt) in deferred_pool
            if year - yr >= DEFERRAL_PERIOD_YEARS
        )
        deferred_pool = [
            (yr, amt) for (yr, amt) in deferred_pool
            if year - yr < DEFERRAL_PERIOD_YEARS
        ]
        rb_open = rb
        rb = rb * 0.965 + capex_spent + payback_this_year
        # NWS cost treatment. 'capitalise': this year's NWS OPEX joins a
        # regulatory asset (in rate base, earning WACC, no property tax or
        # decay), amortised straight-line from the following year.
        if COST_TREAT == 'capitalise' and scenario == 'shared':
            nws_amort = sum(amt / AMORT_YEARS for (yr, amt) in reg_vintages
                            if 0 < year - yr <= AMORT_YEARS)
            reg_vintages.append((year, nws_opex))
            reg_asset = reg_asset - nws_amort + nws_opex
            rb_earning  = rb + reg_asset
            nws_rr_cost = nws_amort
        else:
            nws_amort   = 0.0
            rb_earning  = rb
            nws_rr_cost = nws_opex
        te = rb_earning * params['wacc']
        prop_tax  = rb * params['property_tax_rate'] * (1 + INFLATION_RATE * 0.5) ** (year - 2026)
        other_om  = other_om_base * (1 + INFLATION_RATE) ** (year - 2026)
        dep = RATE_BASE_DECAY * rb_open if INCLUDE_DEP else 0.0
        delivery_rr = te + prop_tax + other_om + nws_rr_cost
        if INCLUDE_DEP:
            delivery_rr += dep

        # ── Supply revenue requirement ────────────────────────────────────────
        # Supply/pass-through grows with load in both scenarios.
        # Pass-through capacity savings are computed EXTERNALLY after both
        # scenarios run (see Section 4), as:
        #   saving = (peak_bau - peak_ss) × capacity_cost_per_mw_year
        # They are then applied to adjust bills and savings pool retrospectively.
        supply_rr = ptbase * (1 + tlg) ** (year - 2026)
        rrc = delivery_rr + supply_rr

        if scenario == 'bau':
            usr = cs = sp = incentive_base = 0.0
        else:
            if POOL_BASIS == 'capex':
                # Savings pool: NWS CAPEX avoidance net of OPEX only
                # (capacity market pass-through savings added in Section 4)
                sp = av - nws_opex
            else:
                # Savings pool: delivery RR reduction vs BAU (return + property
                # tax [+ depreciation]) net of NWS cost recovered in RR
                # (OPEX if expensed, amortisation if capitalised).
                ss_core = te + prop_tax
                if INCLUDE_DEP:
                    ss_core = ss_core + dep
                sp = bau_rr_by_year[year] - ss_core - nws_rr_cost
            # Amount the utility share applies to, after negative-pool treatment
            if NEG_POOL == 'symmetric':
                incentive_base = sp
            elif NEG_POOL == 'floor_zero':
                incentive_base = max(0.0, sp)
            else:   # carry_forward
                net = sp + pool_carry
                pool_carry = min(0.0, net)
                incentive_base = max(0.0, net)
            usr = incentive_base * UTILITY_SAVINGS_SHARE
            cs  = (sp * (1 - UTILITY_SAVINGS_SHARE) if NEG_POOL == 'symmetric'
                   else sp - usr)
            if POOL_BASIS == 'capex':
                rrc -= cs
                delivery_rr -= cs * params['delivery_share_rr']
            else:
                # Customer share is already in the lower rate base (no extra
                # credit); the utility share is collected through delivery RR.
                rrc += usr
                delivery_rr += usr

        # ── Bill calculation: Mechanisms 1, 2, and 3 ─────────────────────────
        # Mechanism 1 tracked: delivery_rr changes → delivery_bill index
        if prev_delivery_rr is not None and prev_delivery_rr > 0:
            drr_ratio = delivery_rr / prev_delivery_rr
        else:
            drr_ratio = 1.0

        # Mechanism 3: utilisation credit
        # Flexible load uses spare capacity → delivery cost grows more slowly
        # than energy sold → existing fixed costs diluted over more kWh
        uc = get_utilisation_credit(year, scenario, cfg)
        delivery_bill *= drr_ratio * (1.0 - uc * tlg)

        # Mechanism 2 tracked: supply grows at (tlg - passthrough_savings)
        supply_growth = (1 + tlg)  # same in both scenarios; pass-through applied in Section 4
        supply_bill  *= supply_growth
        prev_delivery_rr = delivery_rr

        # ── Rate freeze overlay ───────────────────────────────────────────────
        # Evaluated AFTER the bill update so natural_bill reflects the current
        # year's fully-computed delivery+supply bill. Prior placement compared
        # pre-update (i.e. prior year) values, rendering the freeze inactive.
        # Fix: moved this block after delivery_bill and supply_bill are updated.
        freeze_active = catchup_active = False
        freeze_bill_adj = 0.0
        if apply_freeze:
            prev_bill = (rows[-1]['avg_monthly_bill'] if rows
                         else params['start_monthly_bill'])
            natural_bill = delivery_bill + supply_bill
            if year <= 2026 + RATE_FREEZE_YEARS - 1:
                if natural_bill > prev_bill:
                    deferred = natural_bill - prev_bill
                    freeze_deferred_m += deferred
                    freeze_bill_adj = -deferred
                freeze_active = True
            elif year <= catchup_yr_end:
                years_left = catchup_yr_end - year + 1
                catchup_m = freeze_deferred_m / max(1, years_left)
                freeze_bill_adj = catchup_m
                freeze_deferred_m = max(0, freeze_deferred_m - catchup_m)
                catchup_active = True

        monthly_bill = delivery_bill + supply_bill + freeze_bill_adj

        # Update system state
        cum_load *= (1 + tlg_capex); egwh *= (1 + tlg)
        pk = pk * (1 + tlg * (1 - flc)) if scenario == 'shared' else pk * (1 + tlg)
        cust *= 1.005

        rows.append(dict(
            year=year, scenario=scenario, freeze=apply_freeze,
            # CAPEX breakdown
            capex_total_programme_m=annual_capex,
            capex_eligible_m=eligible_capex,
            capex_ineligible_m=annual_capex * (1 - eligible_share),
            capex_spent_m=capex_spent,
            capex_avoided_m=av,
            deferred_capex_added_back_m=payback_this_year,
            capex_avoidance_pct_of_total=ea * 100,
            capex_avoidance_pct_of_eligible=(get_nws_avoidance_of_eligible(year, cfg) * 100
                                             if scenario == 'shared' else 0.0),
            nws_eligible_share_pct=eligible_share * 100,
            nws_opex_m=nws_opex,
            floor_binding=floor_binding,
            total_grid_spend_m=capex_spent + nws_opex,
            # Revenue requirement
            delivery_rr_m=delivery_rr, supply_rr_m=supply_rr,
            revenue_req_m=rrc, traditional_earnings_m=te,
            property_tax_m=prop_tax, other_om_m=other_om,
            # Utility financials
            utility_shared_revenue_m=usr,
            total_utility_revenue_m=te + usr,
            roe_earnings_m=rb_earning * params['equity_ratio'] * params['roe'],
            customer_savings_m=cs, savings_pool_m=sp,
            rate_base_m=rb_earning,
            # DER stack
            nws_capable_mw=nws_mw, storage_mw=smw,
            ev_count=get_territory_ev(params, year, scenario, cfg)[0],
            # Customer bill (three mechanisms combined)
            avg_monthly_bill=monthly_bill,
            avg_annual_bill=monthly_bill * 12,
            delivery_bill_monthly=delivery_bill,
            supply_bill_monthly=supply_bill,
            utilisation_credit_pct=uc * 100,
            freeze_bill_adj_monthly=freeze_bill_adj,
            # System metrics
            customers=cust, energy_gwh=egwh, peak_mw=pk,
            freeze_active=freeze_active, catchup_active=catchup_active,
            cost_per_mwh=(rrc * 1e3) / max(1, egwh),
            peak_per_ratebase=pk / max(1, rb),
            # Added with the correction flags (appended; zero / unchanged
            # under defaults). All nominal $M.
            depreciation_m=dep,
            regulatory_asset_m=reg_asset,
            nws_amortisation_m=nws_amort,
            incentive_base_m=incentive_base,      # pool the utility share applies to
            pool_carry_forward_m=pool_carry,
            # Equity-only earnings: equity return on rate base + shared income.
            # (total_utility_revenue_m above is the WACC-based series: full
            # return on rate base, debt interest included, + shared income.)
            equity_earnings_m=rb_earning * params['equity_ratio'] * params['roe'] + usr,
        ))
    return pd.DataFrame(rows)


# ── Named scenario runner ───────────────────────────────────────────────────

def run_named_scenario(utility_key, sdef, utility_data, results, base_config):
    """
    Run shared savings under a named scenario's parameter overrides.

    Parameters
    ----------
    utility_key  : str key into utility_data
    sdef         : scenario definition dict from SCENARIO_DEFS
    utility_data : dict of loaded utility params
    results      : existing results dict (BAU must already be present, for
                   the base-case BAU peak demand reference)
    base_config  : the full config dict from the notebook (MODEL_CONFIG)

    Builds a modified config for this scenario by merging sdef['params']
    overrides on top of base_config, calls project() with it (apply_freeze
    =False), then applies two post-processing steps using the same merged
    config:

    1. Rate freeze (if sdef['freeze'] is True): the built-in apply_freeze
       mechanism in project() compares pre-update bill values and therefore
       never fires. This function applies the freeze correctly to the
       fully-computed annual bill series, capping year-on-year increases
       during the freeze period and recovering deferred costs over
       RATE_FREEZE_RECOVERY_YEARS thereafter.

    2. Capacity market pass-through: uses base case BAU peak demand as the
       reference (BAU peak is unaffected by NWS programme parameters).
    """
    param_overrides = sdef.get('params', {})
    cfg = config_with(base_config, **param_overrides) if param_overrides else {**base_config}

    freeze_years = param_overrides.get('RATE_FREEZE_YEARS', base_config['RATE_FREEZE_YEARS'])

    p  = utility_data[utility_key]
    sh = project(p, scenario='shared', apply_freeze=False, config=cfg)   # freeze handled below

    # ── Step 1: rate freeze post-processing ──────────────────────────────────
    if sdef['freeze'] and freeze_years > 0:
        sh = sh.copy().sort_values('year').reset_index(drop=True)
        deferred     = 0.0
        freeze_end   = 2026 + freeze_years          # first year after freeze period
        catchup_end  = freeze_end + cfg['RATE_FREEZE_RECOVERY_YEARS']
        p_util       = utility_data[utility_key]
        prev_bill    = p_util['start_monthly_bill']  # 2025 baseline (pre-reform start)
        for i in range(len(sh)):
            yr  = sh.at[i, 'year']
            nat = sh.at[i, 'avg_monthly_bill']
            if yr < freeze_end:                       # freeze years
                if nat > prev_bill:
                    deferred += nat - prev_bill
                    sh.at[i, 'avg_monthly_bill'] = prev_bill
                else:
                    prev_bill = nat                   # allow bill to fall
            elif yr <= catchup_end:                   # catch-up years
                yrs_left = catchup_end - yr + 1
                catchup  = deferred / max(1, yrs_left)
                deferred = max(0, deferred - catchup)
                sh.at[i, 'avg_monthly_bill'] = nat + catchup
                prev_bill = sh.at[i, 'avg_monthly_bill']
            else:
                prev_bill = nat
        sh['avg_annual_bill'] = sh['avg_monthly_bill'] * 12

    # ── Step 2: capacity market pass-through ─────────────────────────────────
    # Mirrors apply_passthrough_savings(): customer share reduces the bill,
    # utility share adds to shared savings income (utility_shared_revenue_m /
    # total_utility_revenue_m) so scenario_results[k][sname] stays consistent
    # with results[k]['shared'] for the same utility.
    bau_df = results[utility_key]['bau']
    pt_share, pt_in_pool = passthrough_utility_share(cfg)
    alloc = capacity_allocation_factor(p, cfg)

    pt_total, pt_customer, pt_utility, pt_monthly = [], [], [], []
    for yr in cfg['YEARS']:
        b_row        = bau_df[bau_df['year'] == yr].iloc[0]
        s_row        = sh[sh['year'] == yr].iloc[0]
        peak_red     = max(0.0, b_row['peak_mw'] - s_row['peak_mw'])
        cap_cost     = capacity_cost_in_year(cfg, utility_key, yr)
        saving_m     = peak_red * cap_cost
        cust_share_m = saving_m * (1 - pt_share)
        util_share_m = saving_m * pt_share
        monthly_red  = (cust_share_m * 1e6) / (s_row['customers'] * 12)
        if alloc != 1.0:
            monthly_red *= alloc
        pt_total.append(saving_m)
        pt_customer.append(cust_share_m)
        pt_utility.append(util_share_m)
        pt_monthly.append(monthly_red)

    pt_df = pd.DataFrame({
        'year': cfg['YEARS'],
        'pt_total_savings_m': pt_total,
        'pt_customer_m': pt_customer,
        'pt_utility_m': pt_utility,
        'pt_monthly_bill_reduction': pt_monthly,
    })
    sh = sh.merge(pt_df, on='year', how='left')
    sh['avg_monthly_bill'] -= sh['pt_monthly_bill_reduction']
    sh['avg_annual_bill']  = sh['avg_monthly_bill'] * 12
    sh['utility_shared_revenue_m'] = sh['utility_shared_revenue_m'] + sh['pt_utility_m']
    sh['total_utility_revenue_m']  = sh['traditional_earnings_m']   + sh['utility_shared_revenue_m']
    sh['savings_pool_m'] = sh['savings_pool_m'] + sh['pt_total_savings_m']
    sh['customer_savings_m'] = sh['customer_savings_m'] + sh['pt_customer_m']
    if pt_in_pool:
        sh['incentive_base_m']  = sh['incentive_base_m'] + sh['pt_total_savings_m']
    else:
        sh['fixed_shared_income_m'] = sh['pt_utility_m']
    sh['equity_earnings_m'] = sh['roe_earnings_m'] + sh['utility_shared_revenue_m']

    # ── Upfront customer passthrough ────────────────────────────────────────────
    # During UPFRONT_PASSTHROUGH_YEARS, 100% of shared savings goes to customers.
    # Utility share is zero during this window; standard split resumes after.
    upy = sdef.get('upfront_passthrough_years', cfg['UPFRONT_PASSTHROUGH_YEARS'])
    if upy > 0:
        sh = sh.copy().reset_index(drop=True)
        for i in range(len(sh)):
            row_year = sh.at[i, 'year']
            if row_year <= 2025 + upy:
                # Move utility share to customer share
                util_share = sh.at[i, 'utility_shared_revenue_m']
                monthly_uplift = (util_share * 1e6) / (sh.at[i, 'customers'] * 12)
                sh.at[i, 'avg_monthly_bill']         -= monthly_uplift
                sh.at[i, 'avg_annual_bill']          -= monthly_uplift * 12
                sh.at[i, 'customer_savings_m']       += util_share
                sh.at[i, 'utility_shared_revenue_m'] = 0.0
                sh.at[i, 'total_utility_revenue_m']  = (
                    sh.at[i, 'traditional_earnings_m']
                )
                sh.at[i, 'equity_earnings_m'] = sh.at[i, 'roe_earnings_m']

    return sh


# ── Capacity market pass-through post-processing ────────────────────────────

def apply_passthrough_savings(results, utility_key, utility_data, config):
    """
    Apply capacity market pass-through savings for a single utility.

    Pass-through saving in year N = (peak_bau - peak_ss) × capacity_cost_year_N
    This is computed here, after both scenarios run, so we can take the actual
    peak demand difference rather than approximating from a fixed rate.
    The saving is split 70/30 between customers and utility (same as NWS savings).
    Customer share reduces supply bills; utility share adds to shared savings income.
    """
    k = utility_key
    p_util = utility_data[k]
    pt_share, pt_in_pool = passthrough_utility_share(config)
    alloc = capacity_allocation_factor(p_util, config)
    bau_df = results[k]['bau'].copy()
    sh_df  = results[k]['shared'].copy()

    pt_savings_m = []      # $M/yr — total capacity market saving
    pt_customer_m = []     # $M/yr — customer share (70%)
    pt_utility_m  = []     # $M/yr — utility share (30%)
    pt_monthly_bill = []   # $/month — customer bill reduction

    for yr in config['YEARS']:
        b_row = bau_df[bau_df['year'] == yr].iloc[0]
        s_row = sh_df[sh_df['year'] == yr].iloc[0]
        peak_reduction_mw = b_row['peak_mw'] - s_row['peak_mw']
        peak_reduction_mw = max(0.0, peak_reduction_mw)  # floor at zero
        cap_cost = capacity_cost_in_year(config, k, yr)
        saving_m = peak_reduction_mw * cap_cost   # $M in that year
        cust_share_m = saving_m * (1 - pt_share)
        util_share_m = saving_m * pt_share
        # Convert customer share to monthly bill reduction
        cust_count = s_row['customers']
        monthly_reduction = (cust_share_m * 1e6) / (cust_count * 12)
        if alloc != 1.0:
            monthly_reduction *= alloc
        pt_savings_m.append(saving_m)
        pt_customer_m.append(cust_share_m)
        pt_utility_m.append(util_share_m)
        pt_monthly_bill.append(monthly_reduction)

    # Apply pass-through savings to shared savings dataframes (not BAU)
    pt_df = pd.DataFrame({
        'year': config['YEARS'],
        'pt_total_savings_m': pt_savings_m,
        'pt_customer_m': pt_customer_m,
        'pt_utility_m': pt_utility_m,
        'pt_monthly_bill_reduction': pt_monthly_bill,
    })

    for key in ['shared', 'shared_freeze']:
        df = results[k][key].copy()
        df = df.merge(pt_df, on='year', how='left')
        # Reduce supply bill by customer pass-through share
        df['supply_bill_monthly'] = df['supply_bill_monthly'] - df['pt_monthly_bill_reduction']
        df['avg_monthly_bill']    = df['avg_monthly_bill']    - df['pt_monthly_bill_reduction']
        df['avg_annual_bill']     = df['avg_monthly_bill'] * 12
        # Add utility pass-through earnings to shared savings income
        df['utility_shared_revenue_m'] = df['utility_shared_revenue_m'] + df['pt_utility_m']
        df['total_utility_revenue_m']  = df['traditional_earnings_m']   + df['utility_shared_revenue_m']
        # Add to savings pool
        df['savings_pool_m'] = df['savings_pool_m'] + df['pt_total_savings_m']
        df['customer_savings_m'] = df['customer_savings_m'] + df['pt_customer_m']
        if pt_in_pool:
            df['incentive_base_m']  = df['incentive_base_m'] + df['pt_total_savings_m']
        else:
            df['fixed_shared_income_m'] = df['pt_utility_m']
        df['equity_earnings_m'] = df['roe_earnings_m'] + df['utility_shared_revenue_m']
        results[k][key] = df

    # Store pass-through data for reference
    results[k]['_passthrough'] = pt_df

    return results
