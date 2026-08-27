# engine/report.py
# Single-scenario-vs-BAU summary report generator — utility-agnostic.
# Never compares named scenarios to each other; one report = one scenario vs BAU.

import base64

import numpy as np

GITHUB_URL = "https://github.com/robertafcurrie/GridDividend"

MECHANISMS = [
    ("NWS avoidance", "Flexible demand (DERs, managed EV charging, demand "
     "response) reduces peak load on constrained circuits, letting the "
     "utility defer or avoid distribution CAPEX it would otherwise spend. "
     "That avoided spending shrinks the rate base and the return earned "
     "on it."),
    ("Pass-through savings", "The same flexible demand also shaves "
     "system-wide peak demand, so the utility buys less capacity in the "
     "wholesale capacity market. This saving flows through on the supply "
     "portion of the bill."),
    ("Utilisation credit", "Flexible demand fills existing spare grid "
     "capacity instead of forcing new capacity to be built, spreading "
     "fixed delivery costs over more kWh sold and slowing delivery-rate "
     "growth directly."),
]
MECHANISMS_NOTE = ("Each mechanism's savings are split between customers "
    "and the utility ({utility_share:.0%} to the utility as an incentive, "
    "the rest to customer bills) &mdash; see Section 1 of the source "
    "notebook (<code>UTILITY_SAVINGS_SHARE</code>) for the split and "
    "Section 3 (<code>engine/model.py</code>) for the calculations.")

# (utility_json key, display label, value formatter) — pulled straight from
# the utility's own JSON, with a source citation looked up via _note_for().
STARTING_DATA_FIELDS = [
    ('rate_base_start_m', 'Rate base', lambda v: f"${v:,.0f}M"),
    ('annual_capex_m', 'Annual CAPEX', lambda v: f"${v:,.0f}M"),
    ('roe', 'Allowed ROE', lambda v: f"{v:.1%}"),
    ('equity_ratio', 'Equity ratio', lambda v: f"{v:.0%}"),
    ('electric_customers', 'Customers', lambda v: f"{v:,.0f}"),
    ('peak_demand_mw', 'Peak demand', lambda v: f"{v:,.0f} MW"),
    ('residential_kwh_month', 'Residential usage benchmark', lambda v: f"{v:,.0f} kWh/month"),
]

# (MODEL_CONFIG key, display label, value formatter, plain-English description)
MECHANISM_PARAM_FIELDS = [
    ('UTILITY_SAVINGS_SHARE', 'Utility savings share', lambda v: f"{v:.0%}",
     "Share of every mechanism's savings retained by the utility as an incentive."),
    ('NWS_ELIGIBLE_CAPEX_SHARE_START', 'NWS-eligible CAPEX (start)', lambda v: f"{v:.0%}",
     "Fraction of annual CAPEX addressable by non-wires solutions in year 1."),
    ('NWS_ELIGIBLE_CAPEX_SHARE_MAX', 'NWS-eligible CAPEX (ceiling)', lambda v: f"{v:.0%}",
     "Ceiling on that eligible share as electrification grows."),
    ('NWS_AVOIDANCE_OF_ELIGIBLE_START', 'NWS avoidance (start)', lambda v: f"{v:.0%}",
     "Fraction of eligible CAPEX actually deferred in year 1."),
    ('NWS_AVOIDANCE_OF_ELIGIBLE_MATURE', 'NWS avoidance (mature)', lambda v: f"{v:.0%}",
     "Fraction of eligible CAPEX deferred once the programme matures."),
    ('NWS_AVOIDANCE_RAMP_YEARS', 'Avoidance ramp', lambda v: f"{v:.0f} yr",
     "Years to go from start to mature avoidance."),
    ('DEFERRAL_FRACTION', 'Deferral fraction', lambda v: f"{v:.0%}",
     "Share of avoided CAPEX that eventually re-enters the rate base (0% = permanent avoidance)."),
    ('DEFERRAL_PERIOD_YEARS', 'Deferral period', lambda v: f"{v:.0f} yr",
     "Years before deferred CAPEX re-enters the rate base."),
    ('UPFRONT_PASSTHROUGH_YEARS', 'Upfront pass-through', lambda v: f"{v:.0f} yr",
     "Years of 100% customer pass-through before the standard split applies."),
    ('FLEX_LOAD_UTILISATION_SHARE_SS', 'Utilisation credit', lambda v: f"{v:.0%}",
     "Share of the delivery-cost utilisation credit applied under this scenario."),
]

UNIVERSAL_CAVEATS = [
    ("Not a forecast.", "This is a single deterministic model path illustrating "
     "direction and order of magnitude, not a prediction of actual future bills "
     "or revenue."),
    ("Spatially aggregate.", "Non-Wires Solutions are modelled as a system-wide "
     "share of eligible CAPEX, not a feeder-level analysis — real outcomes will "
     "vary by location and constraint type."),
    ("No real grid-utilization data.", "NWS-eligible CAPEX share and avoidance "
     "assumptions are estimates, not derived from actual utility hosting-capacity, "
     "feeder-loading, or grid-utilization data. Where a utility publishes real "
     "grid-utilization data, it should replace these assumptions."),
    ("Bill scope is partial.", "Savings cover delivery and supply (capacity) "
     "costs only. Wholesale energy prices, transmission investment, and other "
     "rider-based surcharges continue on their baseline trajectory."),
    ("Undiscounted nominal dollars.", "All cumulative figures are simple sums, "
     "not present-valued. Near-term savings are worth more than late ones."),
]


def _milestone_years(years):
    """Natural checkpoint years (every 5th year) plus the horizon's endpoints."""
    ys = [y for y in years if y % 5 == 0]
    if years[0] not in ys:
        ys = [years[0]] + ys
    if years[-1] not in ys:
        ys = ys + [years[-1]]
    return ys


def _bill_milestone_years(years, dense_until=2035, sparse_step=5):
    """Denser checkpoints through `dense_until` (every year — this is where
    the report's own near-term threshold claims, e.g. first year savings
    exceed $10/mo, actually live), every `sparse_step`th year after."""
    dense = [y for y in years if y <= dense_until]
    last_dense = dense[-1] if dense else years[0]
    sparse = [y for y in years if y > last_dense and y % sparse_step == 0]
    out = dense + sparse
    if years[-1] not in out:
        out.append(years[-1])
    return out


def compute_insights(bau_df, scenario_df, scenario_label, years,
                      bau_freeze_df=None, scenario_freeze_df=None):
    """Deterministic derived facts for one scenario vs BAU. Numbers only — no
    prose. See render_report_html() for the templated sentences built from this.

    bau_freeze_df / scenario_freeze_df are optional: the same rate-freeze
    overlay pair already plotted in the Section 5 bill chart (results[k]
    ['bau_freeze'] / ['shared_freeze']), not a named freeze scenario. When
    supplied, freeze_insight is populated with the relief/catch-up/reconverge
    facts shown in that chart's near-term panel.
    """
    b_final = bau_df[bau_df['year'] == years[-1]].iloc[0]
    s_final = scenario_df[scenario_df['year'] == years[-1]].iloc[0]

    bill_gap_monthly = b_final['avg_monthly_bill'] - s_final['avg_monthly_bill']
    bill_gap_pct = (bill_gap_monthly * 12) / b_final['avg_annual_bill']

    cum_bill_savings_b = np.sum(
        (bau_df['avg_annual_bill'].values - scenario_df['avg_annual_bill'].values)
        * scenario_df['customers'].values
    ) / 1e9

    cum_capex_avoided_b = scenario_df['capex_avoided_m'].sum() / 1000
    cum_opex_b = scenario_df['nws_opex_m'].sum() / 1000
    cum_grid_spend_b = scenario_df['total_grid_spend_m'].sum() / 1000
    cum_bau_capex_b = bau_df['capex_spent_m'].sum() / 1000

    cum_total_utility_revenue_b = scenario_df['total_utility_revenue_m'].sum() / 1000
    cum_bau_earnings_b = bau_df['traditional_earnings_m'].sum() / 1000
    revenue_delta_b = cum_total_utility_revenue_b - cum_bau_earnings_b

    # ── Savings-pool decomposition ────────────────────────────────────────
    # The pool (mechanism 1 NWS avoidance + mechanism 2 capacity pass-through,
    # net of NWS OPEX) is split UTILITY_SAVINGS_SHARE/rest between the
    # utility's shared-savings incentive and customer bill credits — see
    # engine/model.py run_named_scenario()/apply_passthrough_savings().
    # Mechanism 3 (utilisation credit) is NOT part of this pool: it lowers
    # delivery cost per kWh directly and doesn't touch the utility's revenue
    # requirement, so it never appears as a split dollar figure — it's
    # captured below only as the residual against actual bill savings.
    cum_pool_customer_b = scenario_df['customer_savings_m'].sum() / 1000
    cum_pool_utility_b = scenario_df['utility_shared_revenue_m'].sum() / 1000
    cum_pool_total_b = cum_pool_customer_b + cum_pool_utility_b
    cum_mech1_net_b = cum_capex_avoided_b - cum_opex_b
    cum_mech2_total_b = (scenario_df['pt_total_savings_m'].sum() / 1000
                          if 'pt_total_savings_m' in scenario_df.columns else 0.0)
    # Residual: actual observed bill savings minus the pool's customer share.
    # Positive because mechanism 1's pool share is a same-year dollar figure
    # while its actual bill effect compounds through the delivery-rate index
    # over 25 years, and mechanism 3 adds further savings outside the pool
    # entirely — the two are not separable from the model's own bookkeeping.
    cum_uc_savings_b = cum_bill_savings_b - cum_pool_customer_b
    effective_utility_share = (cum_pool_utility_b / cum_pool_total_b
                                if cum_pool_total_b else 0.0)

    # ── Utility revenue-delta decomposition ──────────────────────────────
    # revenue_delta_b nets two very differently-shaped effects: the flow of
    # shared-savings incentive income (cum_pool_utility_b, a fixed share of
    # each year's newly avoided CAPEX) against te_delta_b, the change in
    # traditional rate-base earnings (a stock effect — avoided CAPEX that
    # never enters the rate base keeps earning nothing every subsequent
    # year). The two need not be anywhere close in size.
    te_delta_b = (scenario_df['traditional_earnings_m'].sum()
                  - bau_df['traditional_earnings_m'].sum()) / 1000

    freeze_insight = None
    if bau_freeze_df is not None and scenario_freeze_df is not None:
        rel = (scenario_df['avg_monthly_bill'].values
               - scenario_freeze_df['avg_monthly_bill'].values)
        max_i, min_i = int(np.argmax(rel)), int(np.argmin(rel))
        converge_year = None
        for i, yr in enumerate(years):
            if yr > years[max_i] and abs(rel[i]) < 0.05:
                converge_year = int(yr)
                break
        freeze_insight = dict(
            max_relief=float(rel[max_i]), max_relief_year=int(years[max_i]),
            max_catchup=float(-rel[min_i]), max_catchup_year=int(years[min_i]),
            converge_year=converge_year,
        )

    first_10_year = None
    for _, row in bau_df.iterrows():
        yr = row['year']
        s_row = scenario_df[scenario_df['year'] == yr]
        if s_row.empty:
            continue
        if row['avg_monthly_bill'] - s_row.iloc[0]['avg_monthly_bill'] > 10:
            first_10_year = int(yr)
            break

    nws_ceiling_year = None
    final_share = scenario_df['nws_eligible_share_pct'].iloc[-1]
    if final_share > 0:
        threshold = 0.995 * final_share
        hit = scenario_df[scenario_df['nws_eligible_share_pct'] >= threshold]
        if not hit.empty:
            nws_ceiling_year = int(hit.iloc[0]['year'])

    return dict(
        scenario_label=scenario_label,
        start_year=years[0], end_year=years[-1],
        start_bill=bau_df.iloc[0]['avg_monthly_bill'],
        bau_final_bill=b_final['avg_monthly_bill'],
        scenario_final_bill=s_final['avg_monthly_bill'],
        bill_gap_monthly=bill_gap_monthly,
        bill_gap_pct=bill_gap_pct,
        cum_bill_savings_b=cum_bill_savings_b,
        cum_capex_avoided_b=cum_capex_avoided_b,
        cum_opex_b=cum_opex_b,
        cum_grid_spend_b=cum_grid_spend_b,
        cum_bau_capex_b=cum_bau_capex_b,
        cum_total_utility_revenue_b=cum_total_utility_revenue_b,
        cum_bau_earnings_b=cum_bau_earnings_b,
        revenue_delta_b=revenue_delta_b,
        te_delta_b=te_delta_b,
        cum_pool_customer_b=cum_pool_customer_b,
        cum_pool_utility_b=cum_pool_utility_b,
        cum_pool_total_b=cum_pool_total_b,
        cum_mech1_net_b=cum_mech1_net_b,
        cum_mech2_total_b=cum_mech2_total_b,
        cum_uc_savings_b=cum_uc_savings_b,
        effective_utility_share=effective_utility_share,
        freeze_insight=freeze_insight,
        first_10_year=first_10_year,
        nws_ceiling_year=nws_ceiling_year,
    )


def _verify_rows(utility_json):
    """Pairs each '..._VERIFY' note key with the data key that immediately
    follows it in the JSON's own key order (the file's existing authoring
    convention — see _rate_base_note/_capex_note for the same pattern)."""
    keys = list(utility_json.keys())
    rows = []
    for i, key in enumerate(keys):
        if not key.endswith('_VERIFY'):
            continue
        note = utility_json[key]
        data_key, data_val = None, None
        if i + 1 < len(keys):
            candidate = keys[i + 1]
            candidate_val = utility_json[candidate]
            if isinstance(candidate_val, (int, float, str)):
                data_key, data_val = candidate, candidate_val
        rows.append((data_key, data_val, note))
    return rows


def _note_for(utility_json, data_key):
    """Citation text for a starting-data field, if the JSON's authoring
    convention placed a '_..._note' or '_..._VERIFY' key immediately before
    it (see _verify_rows for the same convention)."""
    keys = list(utility_json.keys())
    if data_key not in keys:
        return None
    idx = keys.index(data_key)
    if idx == 0:
        return None
    prev = keys[idx - 1]
    if prev.endswith('_note') or prev.endswith('_VERIFY'):
        return utility_json[prev]
    return None


def _starting_data_rows(utility_json):
    rows = []
    for key, label, fmt in STARTING_DATA_FIELDS:
        if key not in utility_json or utility_json[key] is None:
            continue
        value = fmt(utility_json[key])
        note = _note_for(utility_json, key) or '&mdash;'
        rows.append((label, value, note))
    return rows


def _mechanism_param_rows(model_config):
    rows = []
    for key, label, fmt, desc in MECHANISM_PARAM_FIELDS:
        if key not in model_config or model_config[key] is None:
            continue
        rows.append((label, fmt(model_config[key]), desc))
    return rows


def _embed_image(path):
    try:
        with open(path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('ascii')
        return f'<img src="data:image/png;base64,{b64}" alt="Bill chart" class="chart-img">'
    except (FileNotFoundError, OSError):
        return ''


def _fmt(x, decimals=0, prefix='$', suffix=''):
    return f"{prefix}{x:,.{decimals}f}{suffix}"


def render_report_html(utility_key, utility_json, utility_params, scenario_label,
                        years, bau_df, scenario_df, insights, chart_png_path,
                        generated_at, git_sha, model_config=None,
                        bau_freeze_df=None, scenario_freeze_df=None):
    """Self-contained HTML string for one utility/scenario. System font stack
    only — no embedded custom font, so this works portably with zero new deps
    and no third-party font redistribution.

    bau_freeze_df / scenario_freeze_df are optional: the same rate-freeze
    overlay pair already drawn in the embedded Section 5 chart. When given,
    the Customer Bills table gains BAU+Freeze/EASE+Freeze columns for the
    near-term rows, matching what the chart already shows."""
    short_name = utility_json.get('short_name', utility_key)
    milestones = _milestone_years(years)
    bill_milestones = _bill_milestone_years(years)
    have_freeze = bau_freeze_df is not None and scenario_freeze_df is not None

    ins = insights
    model_config = model_config or {}
    utility_share = model_config.get('UTILITY_SAVINGS_SHARE', 0.30)
    eff_share = ins.get('effective_utility_share', utility_share)
    inflation_rate = model_config.get('INFLATION_RATE')
    up_or_down = 'higher' if ins['revenue_delta_b'] >= 0 else 'lower'

    inflation_note = (
        f" (Includes assumed {inflation_rate:.1%}/yr inflation &mdash; not adjusted back to "
        f"{ins['start_year']} dollars.)" if inflation_rate else ""
    )

    sentences = [
        f"This report models {short_name}, {ins['start_year']}&ndash;{ins['end_year']}, under "
        f"<strong>{scenario_label}</strong> (Non-Wires Solutions savings shared between "
        f"customers and the utility) versus <strong>BAU</strong> (business-as-usual, no "
        f"reform). Produced with <a href=\"{GITHUB_URL}\">GridDividend</a>, an open-source "
        f"policy simulation framework &mdash; a directional illustration of order of magnitude, "
        f"not a guarantee of results or a substitute for detailed, state-by-state modelling and "
        f"legislative design work (see Model Caveats).",

        f"By {ins['end_year']}, the typical {short_name} residential customer pays "
        f"{_fmt(ins['bau_final_bill'])}/month under business-as-usual versus "
        f"{_fmt(ins['scenario_final_bill'])}/month under {scenario_label} &mdash; a "
        f"{_fmt(ins['bill_gap_monthly'])}/month ({ins['bill_gap_pct']:.0%}) reduction."
        f"{inflation_note}",

        (
            f"From {ins['start_year']} to {ins['end_year']}, the model projects a total savings "
            f"of {_fmt(ins['cum_pool_total_b'], 1, suffix='B')} under {scenario_label}, split "
            f"{eff_share:.0%}/{1 - eff_share:.0%} between the utility "
            f"({_fmt(ins['cum_pool_utility_b'], 1, suffix='B')} as an earnings incentive; "
            + (
                f"less {_fmt(abs(ins['te_delta_b']), 1, suffix='B')} in foregone traditional "
                f"rate-base earnings on CAPEX that was never built &mdash; netting "
                f"{_fmt(abs(ins['revenue_delta_b']), 1, suffix='B')} {up_or_down} revenue vs. "
                f"business-as-usual"
                if ins['te_delta_b'] < -0.05 else
                f"plus {_fmt(ins['te_delta_b'], 1, suffix='B')} in additional traditional "
                f"rate-base earnings as deferred CAPEX re-enters the rate base &mdash; netting "
                f"{_fmt(abs(ins['revenue_delta_b']), 1, suffix='B')} {up_or_down} revenue vs. "
                f"business-as-usual"
                if ins['te_delta_b'] > 0.05 else
                f"netting {_fmt(abs(ins['revenue_delta_b']), 1, suffix='B')} {up_or_down} revenue "
                f"vs. business-as-usual, with little change in traditional rate-base earnings"
            )
            + f") and customers ({_fmt(ins['cum_pool_customer_b'], 1, suffix='B')} credited "
            f"directly to bills), per the UTILITY_SAVINGS_SHARE parameter ({utility_share:.0%})."
        ),

        f"That savings comes from two mechanisms: {_fmt(ins['cum_mech1_net_b'], 1, suffix='B')} "
        f"from NWS CAPEX avoidance ({_fmt(ins['cum_capex_avoided_b'], 1, suffix='B')} of avoided "
        f"distribution CAPEX net of {_fmt(ins['cum_opex_b'], 1, suffix='B')} of NWS programme cost) "
        f"and {_fmt(ins['cum_mech2_total_b'], 1, suffix='B')} from capacity-market pass-through "
        f"savings on reduced system peak demand.",

        f"Actual cumulative bill savings for customers total "
        f"{_fmt(ins['cum_bill_savings_b'], 1, suffix='B')} &mdash; "
        f"{_fmt(ins['cum_pool_customer_b'], 1, suffix='B')} of that is the customer share "
        f"described above, plus a further {_fmt(ins['cum_uc_savings_b'], 1, suffix='B')} from the "
        f"utilisation credit mechanism: flexible demand fills spare grid capacity instead of "
        f"forcing new capacity to be built, spreading the same fixed delivery costs over more "
        f"electricity sold and lowering the delivery rate directly. That "
        f"{_fmt(ins['cum_uc_savings_b'], 1, suffix='B')} doesn't touch the utility's revenue "
        f"requirement, so it isn't part of the {eff_share:.0%}/{1 - eff_share:.0%} split above "
        f"&mdash; it's savings customers get on top of it.",
    ]

    threshold_bits = []
    if ins['first_10_year']:
        threshold_bits.append(f"monthly savings first exceed $10 in {ins['first_10_year']}")
    if ins['nws_ceiling_year']:
        threshold_bits.append(
            f"the NWS-eligible CAPEX share reaches its effective ceiling by {ins['nws_ceiling_year']}")
    if threshold_bits:
        sentences.append(("; ".join(threshold_bits) + ".").capitalize())

    fi = ins.get('freeze_insight')
    if fi:
        freeze_years = model_config.get('RATE_FREEZE_YEARS')
        yr_phrase = f"a {freeze_years:.0f}-year rate freeze" if freeze_years else "a rate freeze"
        freeze_bits = [
            f"{yr_phrase} (shown in the accompanying chart) would add up to "
            f"{_fmt(fi['max_relief'])}/month of relief by {fi['max_relief_year']}"
        ]
        if fi['max_catchup'] > 0.05:
            freeze_bits.append(
                f"recovered through up to {_fmt(fi['max_catchup'])}/month in higher catch-up "
                f"bills around {fi['max_catchup_year']}")
        if fi['converge_year']:
            freeze_bits.append(
                f"before reconverging with the unfrozen {scenario_label} path by "
                f"{fi['converge_year']}")
        sentences.append(
            f"Separate from the EASE Case mechanics above, rate freezes are a well-established "
            f"regulatory tool that could be paired with {scenario_label} to accelerate near-term "
            f"customer relief while the reform is pursued: "
            + (", ".join(freeze_bits) + ".")
        )

    def bill_rows():
        out = []
        for yr in bill_milestones:
            b = bau_df[bau_df['year'] == yr].iloc[0]
            s = scenario_df[scenario_df['year'] == yr].iloc[0]
            save_yr = (b['avg_monthly_bill'] - s['avg_monthly_bill']) * 12
            pct = save_yr / b['avg_annual_bill']
            idx = bau_df[bau_df['year'] <= yr].index
            cum = np.sum(
                (bau_df.loc[idx, 'avg_annual_bill'].values - scenario_df.loc[idx, 'avg_annual_bill'].values)
                * scenario_df.loc[idx, 'customers'].values
            ) / 1e9
            freeze_cells = ''
            if have_freeze:
                bf = bau_freeze_df[bau_freeze_df['year'] == yr].iloc[0]
                sf = scenario_freeze_df[scenario_freeze_df['year'] == yr].iloc[0]
                freeze_cells = (f"<td>{_fmt(bf['avg_monthly_bill'],1)}</td>"
                                 f"<td>{_fmt(sf['avg_monthly_bill'],1)}</td>")
            out.append(f"<tr><td>{yr}</td><td>{_fmt(b['avg_monthly_bill'],1)}</td>"
                       f"<td>{_fmt(s['avg_monthly_bill'],1)}</td>{freeze_cells}"
                       f"<td>{_fmt(save_yr)}</td>"
                       f"<td>{pct:.1%}</td><td>{_fmt(cum,1,suffix='B')}</td></tr>")
        return "\n".join(out)

    def capex_rows():
        out = []
        for yr in milestones:
            b = bau_df[bau_df['year'] == yr].iloc[0]
            s = scenario_df[scenario_df['year'] == yr].iloc[0]
            out.append(f"<tr><td>{yr}</td><td>{_fmt(b['capex_spent_m'])}</td>"
                       f"<td>{s['nws_eligible_share_pct']:.1f}%</td>"
                       f"<td>{_fmt(s['capex_avoided_m'])}</td><td>{_fmt(s['capex_spent_m'])}</td>"
                       f"<td>{_fmt(s['nws_opex_m'])}</td>"
                       f"<td>{s['capex_avoidance_pct_of_total']:.1f}%</td></tr>")
        return "\n".join(out)

    def fin_rows():
        out = []
        for yr in milestones:
            b = bau_df[bau_df['year'] == yr].iloc[0]
            s = scenario_df[scenario_df['year'] == yr].iloc[0]
            out.append(f"<tr><td>{yr}</td><td>{_fmt(b['rate_base_m']/1000,1,suffix='B')}</td>"
                       f"<td>{_fmt(s['rate_base_m']/1000,1,suffix='B')}</td>"
                       f"<td>{_fmt(b['traditional_earnings_m'])}</td>"
                       f"<td>{_fmt(s['traditional_earnings_m'])}</td>"
                       f"<td>{_fmt(s['utility_shared_revenue_m'])}</td>"
                       f"<td>{_fmt(s['total_utility_revenue_m'])}</td></tr>")
        return "\n".join(out)

    model_config = model_config or {}
    utility_share = model_config.get('UTILITY_SAVINGS_SHARE', 0.30)
    mechanisms_html = "".join(
        f"<li><strong>{name}.</strong> {desc}</li>" for name, desc in MECHANISMS
    )

    starting_rows = _starting_data_rows(utility_json)
    starting_html = "".join(
        f"<tr><td>{label}</td><td>{value}</td><td>{note}</td></tr>"
        for label, value, note in starting_rows
    )
    param_rows = _mechanism_param_rows(model_config)
    param_html = "".join(
        f"<tr><td>{label}</td><td>{value}</td><td>{desc}</td></tr>"
        for label, value, desc in param_rows
    )
    filing_case = utility_json.get('filing_case', '')
    assumptions_html = f"""
  <section class="page-break">
    <h2>Modeling Assumptions &amp; Starting Data</h2>
    <p class="section-intro">{short_name} starting data, sourced from {filing_case}.</p>
    <div class="verify-box">
      <table class="prose">
        <thead><tr><th>Parameter</th><th>Value</th><th>Source</th></tr></thead>
        <tbody>{starting_html}</tbody>
      </table>
    </div>
    <p class="section-intro">Shared-savings mechanism parameters (Section 1 of the source
      notebook), common across all utilities modelled.</p>
    <div class="verify-box">
      <table class="prose">
        <thead><tr><th>Parameter</th><th>Value</th><th>What it controls</th></tr></thead>
        <tbody>{param_html}</tbody>
      </table>
    </div>
  </section>"""

    verify_rows = _verify_rows(utility_json)
    verify_html = ''
    if verify_rows:
        row_html = []
        for data_key, data_val, note in verify_rows:
            label = f"<code>{data_key}</code>" if data_key else "&mdash;"
            value = data_val if data_val is not None else "(see note)"
            row_html.append(f"<tr><td>{label}</td><td>{value}</td><td>{note}</td></tr>")
        verify_html = f"""
    <section>
      <h2 class="flag">Parameters Requiring Verification</h2>
      <p class="section-intro">{len(verify_rows)} parameter(s) in this utility's data file are
      estimates flagged for confirmation against source filings. The directional conclusion is
      robust to reasonable variation in these; the specific magnitudes above are not.</p>
      <div class="verify-box">
        <table class="prose">
          <thead><tr><th>Parameter</th><th>Current estimate</th><th>Verification needed</th></tr></thead>
          <tbody>{"".join(row_html)}</tbody>
        </table>
      </div>
    </section>"""

    caveats_html = "".join(
        f"<li><strong>{title}</strong> {body}</li>" for title, body in UNIVERSAL_CAVEATS
    )

    chart_html = _embed_image(chart_png_path)

    sha_bit = f" &middot; commit {git_sha}" if git_sha else ""

    footer_html = """
  <footer>
    GridDividend is an open-source policy simulation framework (MIT License) &mdash; not a utility
    planning model or rate-case replica. Auto-generated, single EASE scenario vs BAU scenario.
  </footer>"""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{short_name} &mdash; {scenario_label} Summary Report</title>
<style>
:root {{
  --paper: #eef0ea; --sheet: #fbfbf9; --ink: #1a1e1f; --ink-soft: #565c53;
  --line: #cdd1c9; --line-strong: #9aa093; --copper: #b5620f; --teal: #0f7a5c;
  --flag: #8a3324; --flag-bg: #f1e4dc;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --paper: #0c0e0d; --sheet: #171a1b; --ink: #e7e8e2; --ink-soft: #a8ada2;
    --line: #33372f; --line-strong: #4b5147; --copper: #c67a34; --teal: #2f9670;
    --flag: #d97a63; --flag-bg: #2b211d;
  }}
}}
* {{ box-sizing: border-box; }}
body {{
  background: var(--paper); color: var(--ink); margin: 0; padding: 28px 16px 40px;
  font-family: Georgia, 'Iowan Old Style', 'Palatino Linotype', serif;
}}
.sheet {{ max-width: 760px; margin: 0 auto; background: var(--sheet); border: 1px solid var(--line); padding: 30px 44px 46px; }}
.eyebrow {{ font-family: -apple-system, 'Segoe UI', sans-serif; font-size: 10px; font-weight: 600;
  letter-spacing: 0.13em; text-transform: uppercase; color: var(--copper); margin: 0 0 8px; }}
h1 {{ font-size: 22px; line-height: 1.25; margin: 0 0 6px; }}
.meta {{ font-family: ui-monospace, Menlo, monospace; font-size: 11.5px; color: var(--ink-soft); margin: 0 0 12px; }}
hr {{ border: 0; border-top: 1px solid var(--line-strong); margin: 0 0 12px; }}
.lede {{ font-size: 13px; line-height: 1.45; margin: 0 0 12px; }}
.lede li {{ margin-bottom: 5px; }}
a {{ color: var(--teal); }}
h2 {{ font-size: 14.5px; margin: 0 0 4px; padding-left: 10px; border-left: 3px solid var(--copper);
  page-break-after: avoid; break-after: avoid-page; }}
h2.flag {{ border-left-color: var(--flag); }}
.section-intro {{ font-size: 11.5px; color: var(--ink-soft); margin: 3px 0 6px 13px; }}
section {{ margin-bottom: 11px; }}
section.page-break {{ page-break-before: always; break-before: page; }}
ul.mechanisms {{ margin: 5px 0 0 13px; padding-left: 16px; font-size: 13px; line-height: 1.45; }}
ul.mechanisms li {{ margin-bottom: 5px; }}
.chart-wrap {{ page-break-inside: avoid; break-inside: avoid-page; }}
.chart-img {{ max-width: 92%; height: auto; display: block; margin: 6px auto 10px; border: 1px solid var(--line); }}
table {{ width: 100%; border-collapse: collapse; font-family: ui-monospace, Menlo, monospace; font-size: 10.5px;
  page-break-inside: avoid; break-inside: avoid; }}
table.prose td {{ font-family: Georgia, serif; font-size: 11px; white-space: normal; vertical-align: top; }}
th {{ font-family: -apple-system, 'Segoe UI', sans-serif; font-size: 8.5px; font-weight: 600; text-transform: uppercase;
  color: var(--ink-soft); text-align: right; padding: 0 10px 4px 0; border-bottom: 1px solid var(--line-strong); }}
th:first-child, td:first-child {{ text-align: left; }}
td {{ text-align: right; padding: 3px 10px 3px 0; border-bottom: 1px solid var(--line); }}
tr:last-child td {{ border-bottom: 1px solid var(--line-strong); font-weight: 600; }}
.verify-box {{ background: var(--flag-bg); border-left: 3px solid var(--flag); padding: 8px 10px 2px; margin: 5px 0 10px 13px; }}
.verify-box table th, .verify-box table td {{
  font-family: Georgia, serif; font-size: 11px; text-transform: none; text-align: left;
  padding: 4px 8px; border-bottom: 1px solid var(--line); border-right: 1px solid var(--line);
}}
.verify-box table th {{ font-weight: 600; color: var(--ink); }}
.verify-box table th:last-child, .verify-box table td:last-child {{ border-right: none; }}
.verify-box table tr:last-child td {{ font-weight: 400; border-bottom: 1px solid var(--line); }}
.verify-box table code {{ font-size: 11px; }}
ul.caveats {{ margin: 5px 0 0 13px; padding-left: 16px; font-size: 11px; line-height: 1.3;
  page-break-inside: avoid; break-inside: avoid; }}
footer {{ position: fixed; left: 0; right: 0; bottom: 8px; margin: 0 auto; max-width: 760px;
  padding: 6px 44px 0; border-top: 1px solid var(--line); background: var(--sheet);
  font-family: -apple-system, 'Segoe UI', sans-serif; font-size: 9px; color: var(--ink-soft); }}
</style>
</head>
<body>
<div class="sheet">
  <p class="eyebrow">Summary Report &mdash; Single Scenario vs. BAU</p>
  <h1>{short_name}: EASE vs BAU Modeling, {ins['start_year']}&ndash;{ins['end_year']}</h1>
  <p class="meta">Generated {generated_at}{sha_bit} &middot; GridDividend v1.1</p>
  <hr>
  <ul class="lede">{"".join(f"<li>{s}</li>" for s in sentences)}</ul>

  <section>
    <h2>How These Savings Are Achieved</h2>
    <ul class="mechanisms">{mechanisms_html}</ul>
    <p class="section-intro">{MECHANISMS_NOTE.format(utility_share=utility_share)}</p>
  </section>

  <section class="page-break">
    <h2>Customer Bills</h2>
    <div class="chart-wrap">{chart_html}</div>
    <table>
      <thead><tr><th>Year</th><th>BAU $/mo</th><th>EASE $/mo</th>{'<th>BAU+Freeze $/mo</th><th>EASE+Freeze $/mo</th>' if have_freeze else ''}<th>Saving/yr</th><th>% Saving</th><th>Cum. $B</th></tr></thead>
      <tbody>{bill_rows()}</tbody>
    </table>
    {'<p class="section-intro">Freeze columns show the same 2-year rate-freeze overlay plotted in the chart above &mdash; a legislative timing choice layered on top of ' + scenario_label + ', not a separate named scenario.</p>' if have_freeze else ''}
  </section>

  <section>
    <h2>Grid Investment &mdash; CAPEX &amp; OPEX</h2>
    <table>
      <thead><tr><th>Year</th><th>BAU CAPEX $M</th><th>NWS Elig. %</th><th>Avoided $M</th><th>Spent $M</th><th>NWS OPEX $M</th><th>Eff. Avoid %</th></tr></thead>
      <tbody>{capex_rows()}</tbody>
    </table>
  </section>

  <section>
    <h2>Utility Financial Position</h2>
    <table>
      <thead><tr><th>Year</th><th>BAU RB $B</th><th>EASE RB $B</th><th>BAU RB Earn $M</th><th>EASE RB Earn $M</th><th>EASE Incentive $M</th><th>Total EASE Rev $M</th></tr></thead>
      <tbody>{fin_rows()}</tbody>
    </table>
  </section>
  {verify_html}
  <section>
    <h2 class="flag">Model Caveats</h2>
    <ul class="caveats">{caveats_html}</ul>
    <p class="section-intro" style="margin-left:0">See Section 10 of the source notebook for the complete caveats and limitations list.</p>
  </section>
  {assumptions_html}

  {footer_html}
</div>
</body>
</html>"""
