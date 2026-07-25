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
    share = params['electric_customers'] / 8_000_000
    c2 = ev_adoption_curve
    ys2 = sorted(c2); vs = [c2[y] for y in ys2]
    base_ev = int(np.interp(2026, ys2, vs)) * share
    eff_year = min(2050, 2026 + (year - 2026) * 1.25) if scenario == 'shared' else year
    total_ev = max(int(np.interp(eff_year, ys2, vs)) * share, base_ev)
    mev = params['ev_managed_charging_pct_bau'] if scenario == 'bau' else ev_managed_shared
    return total_ev, total_ev * mev * ev_peak_kw / 1000


# ── Core projection function ───────────────────────────────────────────────────

def project(params, scenario='bau', apply_freeze=False, config=None):
    """
    Project utility financials and residential customer bills 2026–2050.

    Parameters
    ----------
    params       : dict from load_utility()
    scenario     : 'bau' or 'shared'
    apply_freeze : bool — apply two-year rate freeze overlay
    config       : dict of all Section 1 model parameters (see notebook
                   MODEL_CONFIG). Required — no values are read from globals.

    Returns
    -------
    pd.DataFrame, one row per year, all financial metrics and bill components
    """
    cfg = config or {}
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

    cum_load = 1.0; cum_elec_load = 0.0
    deferred_pool = []       # list of (year, amount) tuples for deferral payback
    freeze_deferred_m = 0.0  # deferred bill amount during rate freeze
    freeze_yr_end  = 2026 + RATE_FREEZE_YEARS
    catchup_yr_end = freeze_yr_end + RATE_FREEZE_RECOVERY_YEARS

    # Bill components (tariff-anchored, tracked separately)
    delivery_bill = params['start_delivery_bill_monthly']
    supply_bill   = params['start_supply_bill_monthly']
    prev_delivery_rr = None
    prev_capex_spent = None

    for year in YEARS:
        elr = get_elec_ramp(year, cfg)
        dcr = params['dc_load_growth_annual']
        tlg = BASELINE_LOAD_GROWTH + elr + dcr

        cum_elec_load += (elr + dcr)
        annual_capex   = capex0 * cum_load
        eligible_share = get_nws_eligible_share(cum_elec_load, cfg)
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
        rb = rb * 0.965 + capex_spent + payback_this_year
        te = rb * params['wacc']
        prop_tax  = rb * params['property_tax_rate'] * (1 + INFLATION_RATE * 0.5) ** (year - 2026)
        other_om  = other_om_base * (1 + INFLATION_RATE) ** (year - 2026)
        delivery_rr = te + prop_tax + other_om + nws_opex

        # ── Supply revenue requirement ────────────────────────────────────────
        # Supply/pass-through grows with load in both scenarios.
        # Pass-through capacity savings are computed EXTERNALLY after both
        # scenarios run (see Section 4), as:
        #   saving = (peak_bau - peak_ss) × capacity_cost_per_mw_year
        # They are then applied to adjust bills and savings pool retrospectively.
        supply_rr = ptbase * (1 + tlg) ** (year - 2026)
        rrc = delivery_rr + supply_rr

        if scenario == 'bau':
            usr = cs = sp = 0.0
        else:
            # Savings pool: NWS CAPEX avoidance net of OPEX only
            # (capacity market pass-through savings added in Section 4)
            sp  = av - nws_opex
            usr = sp * UTILITY_SAVINGS_SHARE
            cs  = sp * (1 - UTILITY_SAVINGS_SHARE)
            rrc -= cs
            delivery_rr -= cs * params['delivery_share_rr']

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
        cum_load *= (1 + tlg); egwh *= (1 + tlg)
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
            roe_earnings_m=rb * params['equity_ratio'] * params['roe'],
            customer_savings_m=cs, savings_pool_m=sp,
            rate_base_m=rb,
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
    cfg = {**base_config}
    for pname, val in param_overrides.items():
        cfg[pname] = val

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
    bau_df = results[utility_key]['bau']
    cap_cost_start = (cfg['CAPACITY_COST_START'][utility_key]
                      if isinstance(cfg['CAPACITY_COST_START'], dict) else cfg['CAPACITY_COST_START'])

    pt_monthly = []
    for yr in cfg['YEARS']:
        b_row        = bau_df[bau_df['year'] == yr].iloc[0]
        s_row        = sh[sh['year'] == yr].iloc[0]
        peak_red     = max(0.0, b_row['peak_mw'] - s_row['peak_mw'])
        cap_cost     = cap_cost_start * (1 + cfg['CAPACITY_COST_GROWTH']) ** (yr - 2026)
        saving_m     = peak_red * cap_cost
        cust_share_m = saving_m * (1 - cfg['UTILITY_SAVINGS_SHARE'])
        monthly_red  = (cust_share_m * 1e6) / (s_row['customers'] * 12)
        pt_monthly.append(monthly_red)

    pt_df = pd.DataFrame({'year': cfg['YEARS'], 'pt_monthly_bill_reduction': pt_monthly})
    sh = sh.merge(pt_df, on='year', how='left')
    sh['avg_monthly_bill'] -= sh['pt_monthly_bill_reduction']
    sh['avg_annual_bill']  = sh['avg_monthly_bill'] * 12

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
    cap_cost_start = (config['CAPACITY_COST_START'][k]
                      if isinstance(config['CAPACITY_COST_START'], dict)
                      else config['CAPACITY_COST_START'])
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
        cap_cost = cap_cost_start * (1 + config['CAPACITY_COST_GROWTH']) ** (yr - 2026)
        saving_m = peak_reduction_mw * cap_cost   # $M in that year
        cust_share_m = saving_m * (1 - config['UTILITY_SAVINGS_SHARE'])
        util_share_m = saving_m * config['UTILITY_SAVINGS_SHARE']
        # Convert customer share to monthly bill reduction
        cust_count = s_row['customers']
        monthly_reduction = (cust_share_m * 1e6) / (cust_count * 12)
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
        results[k][key] = df

    # Store pass-through data for reference
    results[k]['_passthrough'] = pt_df

    return results
