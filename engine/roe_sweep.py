# engine/roe_sweep.py
# GridDividend ROE sweep — utility-agnostic
# Tests how lower (market-set) allowed returns on equity interact with the
# shared-savings mechanism. All inputs passed explicitly; no globals are read.
#
# ROE values below the rate-case figure are an "illustrative market-return
# range" only — none is an auction-clearing rate.

import numpy as np
import pandas as pd

from .model import project, run_named_scenario, apply_preset, SAVINGS_POOL_BASES, NWS_COST_TREATMENTS

DEFAULT_SHARES     = (0.10, 0.15, 0.20, 0.25, 0.30)
CORRECTED_SHARES   = tuple(round(0.05 * i, 2) for i in range(11))   # 0%–50%
DEFAULT_ROE_FLOOR  = 0.070
DEFAULT_ROE_STEP   = 0.005
DEFAULT_BILL_YEARS = (2030, 2040, 2050)
DEFAULT_NPV_RATES  = (0.03, 0.07)
BASE_YEAR          = 2026
EARLY_YEARS        = 3
MIN_SHARE_HORIZONS = (10, 25)

# Scenario labels used in the tidy output
BAU, EASE = 'BAU', 'EASE'

_KEEP_COLS = [
    'year', 'avg_monthly_bill', 'avg_annual_bill', 'customers', 'rate_base_m',
    'capex_avoided_m', 'nws_opex_m', 'savings_pool_m', 'customer_savings_m',
    'utility_shared_revenue_m', 'traditional_earnings_m', 'roe_earnings_m',
    'delivery_rr_m', 'total_utility_revenue_m', 'equity_earnings_m', 'incentive_base_m',
    'regulatory_asset_m',
]


def roe_grid(rate_case_roe, floor=DEFAULT_ROE_FLOOR, step=DEFAULT_ROE_STEP):
    """
    Rate-case ROE plus every multiple of `step` from `floor` up to (but not
    including) the rate-case ROE, descending. E.g. 0.094 →
    [0.094, 0.090, 0.085, 0.080, 0.075, 0.070].
    """
    n = int(np.floor((rate_case_roe - floor) / step + 1e-9))
    grid = [round(floor + i * step, 4) for i in range(n + 1)]
    grid = [r for r in grid if r < rate_case_roe - 1e-9]
    return [rate_case_roe] + sorted(grid, reverse=True)


def _tidy(df, **labels):
    out = df[_KEEP_COLS].copy()
    # utility_earnings_m = equity-only earnings (equity return on rate base +
    # shared-savings income), used for all incentive metrics. The WACC-based
    # series (return incl. debt interest + shared income) is kept as
    # total_utility_revenue_m.
    out['utility_earnings_m'] = out['equity_earnings_m']
    for k, v in labels.items():
        out.insert(0, k, v)
    return out


def run_roe_sweep(utility_data, base_config, utilities, scenario_def=None,
                  shares=DEFAULT_SHARES, roe_floor=DEFAULT_ROE_FLOOR,
                  roe_step=DEFAULT_ROE_STEP, pool_bases=SAVINGS_POOL_BASES,
                  variant='default'):
    """
    Run BAU and the EASE Case (BASE scenario) across an ROE × utility-share ×
    savings-pool-basis grid.

    Parameters
    ----------
    utility_data : dict of loaded utility params (from load_utility())
    base_config  : full model config (notebook MODEL_CONFIG)
    utilities    : list of utility keys to run (e.g. utilities_to_run)
    scenario_def : SCENARIO_DEFS entry for the EASE Case; defaults to BASE
                   (no overrides, no freeze)
    shares       : UTILITY_SAVINGS_SHARE values to sweep
    roe_floor, roe_step : ROE grid, see roe_grid()
    pool_bases   : SAVINGS_POOL_BASIS values to run
    variant      : label for this run's config (e.g. 'CORRECTED/expense'),
                   stored in a 'variant' column and used to group metrics

    Capacity pass-through is applied exactly as in notebook Section 4, via
    run_named_scenario() against the BAU run at the same ROE and config.

    Returns
    -------
    Tidy DataFrame, one row per (utility, variant, roe, share, pool_basis,
    scenario, year). All $ columns are nominal $M. BAU does not depend on share or pool basis; its rows are repeated
    for each combination so every slice is self-contained.
    """
    sdef = scenario_def or {'params': {}, 'freeze': False}
    frames = []
    for k in utilities:
        p = utility_data[k]
        for roe in roe_grid(p['roe'], roe_floor, roe_step):
            for basis in pool_bases:
                for share in shares:
                    cfg = {**base_config, 'ROE_OVERRIDE': roe,
                           'SAVINGS_POOL_BASIS': basis,
                           'UTILITY_SAVINGS_SHARE': share}
                    bau = project(p, 'bau', config=cfg)
                    ease = run_named_scenario(k, sdef, utility_data, {k: {'bau': bau}}, cfg)
                    for scen, df in ((BAU, bau), (EASE, ease)):
                        frames.append(_tidy(df, scenario=scen, pool_basis=basis,
                                            share=share, roe=roe,
                                            rate_case_roe=p['roe'], variant=variant,
                                            utility=k))
    return pd.concat(frames, ignore_index=True)


def _npv(values, years, rate):
    years = np.asarray(years)
    return float(np.sum(np.asarray(values) / (1 + rate) ** (years - BASE_YEAR)))


def min_incentive_share(bau, ease, horizon):
    """
    Minimum UTILITY_SAVINGS_SHARE keeping cumulative utility earnings in the
    EASE Case >= BAU over the first `horizon` years (undiscounted nominal).

    Utility earnings are linear in the share: equity return on rate base does
    not depend on it, and shared-savings income is share × incentive base
    (the pool after negative-pool treatment, plus capacity pass-through). So
        s* = (BAU earnings − EASE equity return) / cumulative incentive base
    This holds for every NEGATIVE_POOL_TREATMENT and for share = 0.
    Returns 0.0 if EASE already matches BAU with no incentive, np.inf if no
    non-negative share works (pool ≤ 0 with an earnings gap). Values > 1 mean
    the utility would need more than the whole pool.
    """
    b = bau.iloc[:horizon]; e = ease.iloc[:horizon]
    gap  = b['roe_earnings_m'].sum() - e['roe_earnings_m'].sum()
    pool = e['incentive_base_m'].sum()
    if gap <= 0:
        return 0.0
    if pool <= 0:
        return np.inf
    return gap / pool


def compute_roe_metrics(sweep, bill_years=DEFAULT_BILL_YEARS,
                        npv_rates=DEFAULT_NPV_RATES):
    """
    Summarise run_roe_sweep() output: one row per (utility, variant, roe,
    share, pool_basis). Utility earnings are equity-only (see _tidy).

    Dollar columns are named by basis: '_nominal' = undiscounted nominal sum;
    '_npv3' / '_npv7' = NPV at 3% / 7%, base year 2026. Per-customer figures
    are for the average residential customer (sum of annual bill differences).

    Columns
    -------
    bau_bill_{y}, ease_bill_{y}     monthly bill in year y ($/month, nominal)
    cum_saving_*                    EASE vs BAU at the SAME ROE, $/customer
    bau_vs_sq_* / ease_vs_sq_*      saving vs status quo (rate-case ROE, BAU)
    crossover_year                  first year from which EASE utility earnings
                                    stay below BAU through the horizon end
                                    (NaN = EASE ≥ BAU in the final year;
                                    first model year = never above BAU)
    early_gain_per_deferred_$       first 3 yrs: shared income / avoided CAPEX
    early_loss_per_deferred_$       first 3 yrs: equity-return loss / avoided CAPEX
    early_net_per_deferred_$        gain − loss
    ss_income_share_of_earnings     cumulative shared income / total EASE earnings
    min_share_10y, min_share_25y    see min_incentive_share()
    """
    rows = []
    sq_all = sweep[(sweep['scenario'] == BAU) & (sweep['roe'] == sweep['rate_case_roe'])]
    keys = ['utility', 'variant', 'roe', 'share', 'pool_basis']
    for (k, variant, roe, share, basis), g in sweep.groupby(keys, sort=False):
        bau  = g[g['scenario'] == BAU].sort_values('year').reset_index(drop=True)
        ease = g[g['scenario'] == EASE].sort_values('year').reset_index(drop=True)
        sq = (sq_all[(sq_all['utility'] == k) & (sq_all['variant'] == variant)
                     & (sq_all['share'] == share) & (sq_all['pool_basis'] == basis)]
              .sort_values('year').reset_index(drop=True))
        years = ease['year'].values
        r = dict(utility=k, variant=variant, roe=roe,
                 rate_case_roe=g['rate_case_roe'].iloc[0], share=share, pool_basis=basis)

        for y in bill_years:
            r[f'bau_bill_{y}']  = bau.loc[bau['year'] == y, 'avg_monthly_bill'].iloc[0]
            r[f'ease_bill_{y}'] = ease.loc[ease['year'] == y, 'avg_monthly_bill'].iloc[0]

        for prefix, a, b in (('cum_saving', bau, ease),
                             ('bau_vs_sq', sq, bau),
                             ('ease_vs_sq', sq, ease)):
            diff = (a['avg_annual_bill'] - b['avg_annual_bill']).values
            r[f'{prefix}_nominal'] = float(diff.sum())
            for rate in npv_rates:
                r[f'{prefix}_npv{round(rate * 100)}'] = _npv(diff, years, rate)

        below = ease['utility_earnings_m'].values < bau['utility_earnings_m'].values
        if below[-1]:
            above_idx = np.flatnonzero(~below)
            start = above_idx[-1] + 1 if above_idx.size else 0
            r['crossover_year'] = int(years[start])
        else:
            r['crossover_year'] = np.nan

        e3, b3 = ease.iloc[:EARLY_YEARS], bau.iloc[:EARLY_YEARS]
        deferred = e3['capex_avoided_m'].sum()
        gain = e3['utility_shared_revenue_m'].sum()
        loss = b3['roe_earnings_m'].sum() - e3['roe_earnings_m'].sum()
        r['early_gain_per_deferred_$'] = gain / deferred if deferred else np.nan
        r['early_loss_per_deferred_$'] = loss / deferred if deferred else np.nan
        r['early_net_per_deferred_$']  = (gain - loss) / deferred if deferred else np.nan

        r['ss_income_share_of_earnings'] = (ease['utility_shared_revenue_m'].sum()
                                            / ease['utility_earnings_m'].sum())
        r['cum_wacc_basis_gap_25y_m'] = (ease['total_utility_revenue_m'].sum()
                                         - bau['total_utility_revenue_m'].sum())
        r['cum_earnings_gap_25y_m'] = (ease['utility_earnings_m'].sum()
                                       - bau['utility_earnings_m'].sum())
        for h in MIN_SHARE_HORIZONS:
            r[f'min_share_{h}y'] = min_incentive_share(bau, ease, h)
        rows.append(r)
    return pd.DataFrame(rows)


def quadrant_table(metrics, utility, pool_basis, share=0.30, roe_low=DEFAULT_ROE_FLOOR,
                   column='nominal', variant='default'):
    """
    2×2 table of cumulative saving per customer vs the status quo
    (rate-case ROE, BAU): rows = rate-case ROE / roe_low, columns = BAU / EASE.
    `column` picks the dollar basis: 'nominal', 'npv3' or 'npv7'.
    """
    m = metrics[(metrics['utility'] == utility) & (metrics['pool_basis'] == pool_basis)
                & (metrics['variant'] == variant) & np.isclose(metrics['share'], share)]
    rc = m['rate_case_roe'].iloc[0]
    out = {}
    for label, roe in ((f'Rate-case ROE {rc:.1%}', rc), (f'Illustrative {roe_low:.1%}', roe_low)):
        row = m[np.isclose(m['roe'], roe)].iloc[0]
        out[label] = {BAU: row[f'bau_vs_sq_{column}'], 'EASE Case': row[f'ease_vs_sq_{column}']}
    return pd.DataFrame(out).T


def run_corrected_sweep(utility_data, base_config, utilities, scenario_def=None,
                        treatments=NWS_COST_TREATMENTS, shares=CORRECTED_SHARES,
                        roe_floor=DEFAULT_ROE_FLOOR, roe_step=DEFAULT_ROE_STEP,
                        preset='CORRECTED'):
    """
    ROE sweep under a named preset (default CORRECTED), once per
    NWS_COST_TREATMENT, with utility share 0–50% in 5-point steps. The pool
    basis is whatever the preset sets. Variant labels are '<preset>/<treatment>'.
    """
    cfg0 = apply_preset(base_config, preset)
    frames = []
    for t in treatments:
        cfg = {**cfg0, 'NWS_COST_TREATMENT': t}
        frames.append(run_roe_sweep(utility_data, cfg, utilities, scenario_def=scenario_def,
                                    shares=shares, roe_floor=roe_floor, roe_step=roe_step,
                                    pool_bases=(cfg['SAVINGS_POOL_BASIS'],),
                                    variant=f'{preset}/{t}'))
    return pd.concat(frames, ignore_index=True)


def data_quality_flags(utility_meta, utilities):
    """
    Caveat lines for utilities whose inputs are unverified or provisional,
    derived from the utility JSON: count of '_VERIFY' fields, and a filing
    case marked 'pending'.
    """
    flags = []
    for k in utilities:
        u = utility_meta[k]
        name = u.get('short_name', k)
        n_verify = sum(1 for f in u if f.endswith('_VERIFY'))
        if n_verify:
            flags.append(f"{name}: results are ILLUSTRATIVE — {n_verify} parameters are "
                         f"flagged _VERIFY in the utility JSON.")
        if 'pending' in u.get('filing_case', '').lower():
            flags.append(f"{name}: results are PROVISIONAL — {u['filing_case']}.")
    return flags
