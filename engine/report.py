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
    """
    Deterministic derived facts for one earlier-model scenario vs BAU. Numbers
    only, no prose; render_report_html() builds the sentences.

    Inputs: bau_df, scenario_df (engine.model.project() / run_named_scenario()
      frames, one row per year); scenario_label; years (list);
      bau_freeze_df / scenario_freeze_df (optional): the rate-freeze overlay pair
      plotted in the Section 5 bill chart (results[k]['bau_freeze'] /
      ['shared_freeze']), not a named freeze scenario. When supplied,
      freeze_insight holds the relief / catch-up / reconverge facts.
    Output: dict: start and final average monthly bills and the final-year gap
      ($/month nominal, and as a share of the BAU annual bill); cumulative
      bill savings, capex avoided, NWS opex, grid spend, utility revenue and
      earnings, and the pool split between customers and utility ($B,
      undiscounted nominal); effective utility share; freeze_insight;
      first_10_year and nws_ceiling_year (years).
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


# Section 1 keys a utility JSON may override (engine: nws_eligible_bounds()).
_JSON_OVERRIDABLE = {'NWS_ELIGIBLE_CAPEX_SHARE_START': 'nws_eligible_capex_share_start',
                     'NWS_ELIGIBLE_CAPEX_SHARE_MAX': 'nws_eligible_capex_share_max'}


def _mechanism_param_rows(model_config, utility_json=None):
    """Mechanism parameters as the engine applies them: a utility JSON value
    for the NWS-eligible share bounds wins unless explicitly overridden."""
    utility_json = utility_json or {}
    overrides = model_config.get('CONFIG_OVERRIDES', ())
    rows = []
    for key, label, fmt, desc in MECHANISM_PARAM_FIELDS:
        val = model_config.get(key)
        jkey = _JSON_OVERRIDABLE.get(key)
        if jkey and key not in overrides and utility_json.get(jkey) is not None:
            val = utility_json[jkey]
        if val is None:
            continue
        rows.append((label, fmt(val), desc))
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


def _state_context_sentence(utility_json):
    """Optional jurisdiction sentence from utility_json['report_context']
    (regulator, case, statutes). Returns None when the JSON has no such block,
    so reports for utilities without it are unchanged."""
    ctx = utility_json.get('report_context')
    if not ctx:
        return None
    bits = []
    if ctx.get('regulator'):
        bits.append(f"Regulator: {ctx['regulator']}")
    if ctx.get('case'):
        bits.append(f"rate case: {ctx['case']}")
    out = "; ".join(bits) + "." if bits else ""
    if ctx.get('statutes'):
        out += " State policy context: " + "; ".join(ctx['statutes']) + "."
    if ctx.get('note'):
        out += " " + ctx['note']
    return out.strip() or None


POOL_BASIS_TEXT = {
    'capex': ("Savings-pool basis: <code>'capex'</code> (avoided CAPEX net of NWS cost, in the "
              "year of avoidance). Customers also benefit from the smaller rate base in later "
              "years, so the same avoided dollar counts twice &mdash; treat these savings as an "
              "<strong>upper bound</strong>."),
    'revenue_requirement': ("Savings-pool basis: <code>'revenue_requirement'</code> (annual "
                            "reduction in delivery revenue requirement vs BAU, net of NWS cost). "
                            "No double count; the utility's share is recovered in rates."),
}


def render_report_html(utility_key, utility_json, utility_params, scenario_label,
                        years, bau_df, scenario_df, insights, chart_png_path,
                        generated_at, git_sha, model_config=None,
                        bau_freeze_df=None, scenario_freeze_df=None,
                        pool_basis_note=False, layered_html=None):
    """
    Self-contained HTML report for one utility and earlier-model scenario.

    Inputs: utility_key; utility_json; utility_params; scenario_label; years;
      bau_df, scenario_df, insights (compute_insights()); chart_png_path (embedded
      as base64); generated_at, git_sha (footer); model_config (Section 1
      parameters); bau_freeze_df / scenario_freeze_df (optional: adds
      BAU+Freeze / EASE+Freeze columns to the near-term bill rows, matching the
      embedded chart); pool_basis_note=True states the SAVINGS_POOL_BASIS in the
      lede and caveats, labelling the default 'capex' basis as an upper bound;
      layered_html (render_layered_section() output, appended).
    utility_json['report_context'] (optional) adds a regulator / case / statute
    sentence. System font stack only, no embedded fonts.
    Output: str, a complete HTML document. Every $ figure states its basis.
    """
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

    state_sentence = _state_context_sentence(utility_json)
    if state_sentence:
        sentences.insert(1, state_sentence)
    pool_text = None
    if pool_basis_note:
        pool_text = POOL_BASIS_TEXT.get(model_config.get('SAVINGS_POOL_BASIS', 'capex'))
        if pool_text:
            sentences.insert(1, pool_text)

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
    param_rows = _mechanism_param_rows(model_config, utility_json)
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

    caveat_items = list(UNIVERSAL_CAVEATS)
    if pool_text:
        caveat_items.append(("Savings-pool basis.", pool_text))
    caveats_html = "".join(
        f"<li><strong>{title}</strong> {body}</li>" for title, body in caveat_items
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
  {layered_html or ''}
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


# ── Layered section (engine/layers.py) ───────────────────────────────────────

TIGHT_NETWORK = {('network', 'planning_headroom'): 'low',
                 ('network', 'reinforcement_lead_years'): 'high',
                 ('network', 'max_build_pct'): 'low'}


# Ordinal blue ramp (light -> dark) for the sub-band shares in the headroom sweep
SWEEP_COLORS = ('#86b6ef', '#5598e7', '#2a78d6', '#1c5cab', '#0d366b')
SWEEP_PANELS = {
    'saving': ('2050 monthly saving ($/month, nominal)', '2050 monthly saving ($, nominal)', '${:,.1f}'),
    'customer_npv': ('Customer savings ($B, NPV 3%, 2026 $)', 'Customer savings ($B, NPV 3%, 2026 $)', '${:,.1f}B'),
    'capex': ('Wires capex avoided or deferred ($B, undiscounted nominal)',
              'Wires capex avoided or deferred ($B, undiscounted nominal)', '${:,.1f}B'),
    'delay': ('Upgrade Delay avoided (MW-years 2026-2050, 80% mean utilisation)',
              'Upgrade Delay for Interconnection avoided (MW-years)', '{:,.0f}'),
}
DELAY_STYLE = {'short': ':', 'central': '-', 'long': '--'}


def headroom_sweep_figure(sw, name, panels=('saving', 'customer_npv', 'capex', 'delay')):
    """
    Matplotlib Figure (no pyplot state) for layers.headroom_sweep().

    Inputs: sw = headroom_sweep() DataFrame; name (utility short name); panels,
      any of 'saving' (2050 monthly saving, $/month nominal), 'customer_npv'
      (customer savings, $B NPV 3%, 2026 $), 'capex' (wires capex avoided, $B
      undiscounted nominal), 'delay' (MW-years of Upgrade Delay avoided).
    Each panel plots its metric against mean starting utilisation, one line per
    sub-band share (ordinal blue ramp, legend), at the central Upgrade Delay case.
    The 'delay' panel plots MW-years avoided against the sub-band share at 80%
    mean utilisation, one line per delay case (short dotted, central solid, long
    dashed). Central scenario.
    Output: matplotlib.figure.Figure.
    """
    from matplotlib.figure import Figure
    from matplotlib.ticker import FuncFormatter
    full = sw
    if 'delay case' in sw.columns:
        sw = sw[sw['delay case'] == 'central']
    shares = sorted(sw['sub-band share'].unique())
    ncol = 2 if len(panels) > 1 else 1
    nrow = (len(panels) + 1) // 2
    fig = Figure(figsize=(6.2 * ncol, 3.9 * nrow + 0.6))
    axes = fig.subplots(nrow, ncol, squeeze=False).ravel()
    for ax, key in zip(axes, panels):
        title, col, fmt = SWEEP_PANELS[key]
        if key == 'delay' and 'delay case' in full.columns:
            m80 = full['mean utilisation'].sub(0.8).abs().min()
            for dc in [d for d in DELAY_STYLE if d in set(full['delay case'])]:
                d = full[(full['delay case'] == dc) & ((full['mean utilisation'] - 0.8).abs() == m80)]
                d = d.sort_values('sub-band share')
                ax.plot(d['sub-band share'], d[col], color=SWEEP_COLORS[2], lw=2, ls=DELAY_STYLE[dc], marker='o', ms=4,
                        label=f'{dc} upgrade delay')
            ax.set_title(title.replace('$', r'\$'), fontsize=10, loc='left')
            ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:.0%}'))
            ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _, f=fmt: f.format(v)))
            ax.grid(axis='y', color='#e6e6e6', lw=0.8)
            ax.spines[['top', 'right']].set_visible(False)
            ax.set_xlabel('Share of load in the constrained sub-band', fontsize=9)
            ax.legend(fontsize=8, frameon=False)
            continue
        for x, c in zip(shares, SWEEP_COLORS[-len(shares):] if len(shares) <= len(SWEEP_COLORS) else SWEEP_COLORS):
            d = sw[sw['sub-band share'] == x].sort_values('mean utilisation')
            ax.plot(d['mean utilisation'], d[col], color=c, lw=2, marker='o', ms=4,
                    label=('no sub-band' if x == 0 else f'{x:.1%} of load above limit'))
        ax.set_title(title.replace('$', r'\$'), fontsize=10, loc='left')
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:.0%}'))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _, f=fmt: f.format(v)))
        ax.grid(axis='y', color='#e6e6e6', lw=0.8)
        ax.spines[['top', 'right']].set_visible(False)
        ax.set_xlabel('Mean starting planning utilisation', fontsize=9)
    for ax in axes[len(panels):]:
        ax.set_visible(False)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc='lower center', ncol=len(shares), fontsize=8, frameon=False)
    fig.suptitle(f'{name}: how the potential depends on existing headroom (Central scenario, central upgrade delay)',
                 fontsize=11, x=0.01,
                 ha='left')
    fig.tight_layout(rect=(0, 0.06, 1, 0.96))
    return fig


def _fig_b64(fig, alt):
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=110, bbox_inches='tight')
    b64 = base64.b64encode(buf.getvalue()).decode('ascii')
    return f'<img src="data:image/png;base64,{b64}" alt="{alt}" class="chart-img">'


def _tbl(header, rows):
    th = ''.join(f'<th>{h}</th>' for h in header)
    body = ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>' for r in rows)
    return f'<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


def render_layered_section(utility_key, utility_json, utility_params):
    """
    HTML block: the layered model (engine/layers.py) for one utility.

    Inputs: utility_key; utility_json (starting_bill, forward_assumptions);
      utility_params (earlier-model utility dict). Runs every scenario; the
      notebook's NETWORK_OVERRIDES apply.
    Output: str, HTML <section>: a methodology note (scenario, dollar basis, pool
      setting, link to docs/METHODOLOGY.md), then the monthly bill difference,
      cumulative and NPV savings, starting bill, scenarios, waterfall,
      system-wide results, layer contributions, ROE lever, value stack, network,
      bands, sub-band, Upgrade Delay, headroom sweep, access, MW paths and
      earnings. Every $ figure is labelled with its basis.
    """
    from . import layers as LY
    uj, p = utility_json, utility_params
    name = uj.get('short_name', utility_key)
    kwh = uj['starting_bill']['benchmark_kwh_month']
    runs = {sc: LY.project_layers(uj, p, scenario=sc) for sc in LY.SCENARIOS}
    c = runs['Central']
    col = 'avg_bill_total'
    # Methodology note: scenario, dollar basis and pool setting used
    a_c = c['assumptions']
    mech = a_c['mechanism']
    in_pool = [lbl for k, lbl in (('wholesale_energy', 'wholesale energy'), ('transmission', 'avoided transmission'),
                                  ('losses', 'avoided distribution losses'))
               if a_c['_enabled'].get(k) and a_c.get(k, {}).get('in_pool', True)]
    roe_c = a_c.get('roe', {})
    bp_c = a_c.get('bau_plan', {})
    if bp_c.get('basis') == 'published_plan':
        yrs_ = bp_c['plan_years']
        bau_note = (f"BAU basis: the utility's published distribution capital plan ({yrs_[0]}&ndash;{yrs_[-1]}"
                    if len(yrs_) > 1 else f"BAU basis: the utility's published distribution capital plan ({yrs_[0]}")
        bau_note += {'taper': f"; beyond it, capex growth tapers to load growth by {int(bp_c['taper_year'])})",
                     'continue': '; beyond it, the plan growth rate continues)',
                     'policy': '; beyond it, load growth with high electrification)'}[bp_c.get('beyond_path', 'taper')]
        bau_note += (f"; shared savings defers up to {bp_c['addressable_growth']:.0%} of growth-driven capex (as the network "
                     f"model finds deferrable) and right-sizes {bp_c['addressable_replacement']:.0%} of asset replacement and "
                     f"{bp_c['addressable_gridmod']:.0%} of grid modernisation. ")
    else:
        bau_note = "BAU basis: capex generated by the network model. "
    ov_note = (' Notebook network overrides in force: ' + ', '.join(f'{k} = {v}' for k, v in LY.NETWORK_OVERRIDES.items())
               + '.') if LY.NETWORK_OVERRIDES else ''
    method = (
        f"<p class=\"section-intro\"><strong>Methodology.</strong> The layered model starts from today's residential "
        f"bill, line by line, and projects each line 2026&ndash;2050 under business as usual (BAU) and under shared "
        f"savings. The difference is built from switchable layers: programs as core business, deferral of network "
        f"reinforcement, load enabled, capacity, wholesale energy, avoided transmission, avoided distribution losses, "
        f"the shared savings mechanism and the ROE lever. The distribution network has explicit capacity in loading "
        f"bands, including a constrained sub-band above the planning limit, and new load in constrained areas waits "
        f"the Upgrade Delay for Interconnection. Full methodology: "
        f"<a href=\"{GITHUB_URL}/blob/main/docs/METHODOLOGY.md\">docs/METHODOLOGY.md</a>; every input with its "
        f"source and status: <a href=\"{GITHUB_URL}/blob/main/docs/ASSUMPTIONS.md\">docs/ASSUMPTIONS.md</a>.</p>"
        f"<p class=\"section-intro\"><strong>Settings used.</strong> Scenario: <strong>Central</strong> for every "
        f"figure unless marked; Cautious and Ambitious give the range. Dollar basis: nominal dollars; cumulative "
        f"figures are undiscounted unless marked NPV, which is in 2026 dollars at 3% (and 7% where shown). Savings "
        f"pool: the reduction in what customers pay versus BAU (distribution revenue requirement, program surcharges "
        f"and capacity cost)"
        + (f", plus {', '.join(in_pool[:-1]) + ' and ' + in_pool[-1] if len(in_pool) > 1 else in_pool[0]}"
           if in_pool else '')
        + f"; the utility's share is {mech['utility_share']:.0%} (its shared savings earnings) and customers keep the "
        f"rest. Negative pools are carried forward against later positive pools. ROE lever: "
        + (f"{roe_c['roe_delta'] * 1e4:+.0f} bp" if roe_c.get('roe_delta') else 'no change in allowed ROE')
        + f" in Central, outside the pool. Programs become core business "
        f"from {int(a_c['programs']['transition_year'])}. {bau_note}{ov_note}</p>")
    at = lambda df, y: float(df.loc[df['year'] == y, col].iloc[0])
    lead = []
    for y in (2035, 2050):
        b, s_ = at(c['bau'], y), at(c['ss'], y)
        lead.append(f"In {y}, the average residential bill is {_fmt(s_, 2)}/month under shared savings versus "
                    f"{_fmt(b, 2)}/month under BAU (Central scenario): {_fmt(b - s_, 2)}/month lower "
                    f"($/month, nominal).")
    cs = LY.cumulative_savings(c)
    lead.append(f"Cumulative saving per residential customer, 2026&ndash;2050 (Central): {_fmt(cs['undiscounted nominal $'])} "
                f"undiscounted nominal; {_fmt(cs['NPV 3% (2026 $)'])} NPV at 3% and {_fmt(cs['NPV 7% (2026 $)'])} NPV at 7% "
                f"(2026 dollars). Range across scenarios: "
                + ', '.join(f"{sc} {_fmt(LY.cumulative_savings(runs[sc])['undiscounted nominal $'])}" for sc in LY.SCENARIOS)
                + ' (undiscounted nominal).')
    # Starting bill by category
    cat0 = LY.by_category(c['starting_lines'])
    start_rows = [(k.replace('_', ' ').capitalize(), _fmt(v, 2)) for k, v in cat0.items() if abs(v) > 0.005]
    start_rows.append(('<strong>Total</strong>', f'<strong>{_fmt(sum(cat0.values()), 2)}</strong>'))
    # Bills by scenario
    bill_rows = []
    for y in (2026, 2035, 2050):
        bill_rows.append([str(y), _fmt(at(c['bau'], y), 2)] + [_fmt(at(runs[sc]['ss'], y), 2) for sc in LY.SCENARIOS])
    # Waterfall 2050
    wf = LY.waterfall(uj, p, years=(2050,)).iloc[0]
    labels = {'BAU': 'BAU bill', 'system_needs': 'System needs (both cases)', 'programs': 'Programs as core business',
              'deferral': 'Deferral',
              'load_enabled': 'Load enabled: residential bill effect only (the benefit of faster connections goes to '
                              'the customers being connected; see Access)',
              'capacity': 'Capacity',
              'wholesale_energy': 'Wholesale energy: flexible load shifted to off-peak hours',
              'transmission': 'Avoided transmission', 'losses': 'Avoided distribution losses',
              'objective': 'Additional savings objective (unspecified means, net of cost to achieve)',
              'mechanism': 'Shared savings earnings', 'roe': 'ROE lever (allowed ROE vs BAU)',
              'Shared savings': 'Shared-savings bill'}
    wf_rows = [(labels[k], (_fmt(v, 2) if k in ('BAU', 'Shared savings') else f"{v:+.2f}")) for k, v in wf.items()]
    # System-wide summary (Central) and each layer's contribution
    sm = LY.system_summary(c)
    def _b(v):
        v = 0.0 if abs(v) < 0.005 else v
        return f"-${-v:,.2f}B" if v < 0 else f"${v:,.2f}B"
    sys_rows = [[k.replace('($B, undiscounted nominal)', '').replace('($B, NPV 3%, 2026 $)', '(NPV 3%, 2026 $)').strip(),
                 _b(v) if '$B' in k else (_fmt(v, 0, suffix='M') if '$M' in k else f"{v:,.2f}" if '(avg yr' in k else f"{v:,.0f}")]
                for k, v in sm.items()]
    lc = LY.layer_contributions(uj, p)
    lc_rows = [[labels.get(l, l).split(':')[0], _b(r['Customer savings ($B, undiscounted nominal)']),
                _b(r['Customer savings ($B, NPV 3%, 2026 $)']), f"{r['Monthly bill 2035 ($, nominal)']:+.2f}",
                f"{r['Monthly bill 2050 ($, nominal)']:+.2f}",
                _b(r['Shared savings earnings attributable ($B, undiscounted nominal)']),
                _b(r['Shared savings earnings attributable ($B, NPV 3%, 2026 $)'])]
               for l, r in lc.iterrows()]
    roe_rows = []
    for lev, lbl in (('low', 'ROE lower'), ('high', 'ROE higher')):
        rr_ = LY.project_layers(uj, p, overrides={('roe', 'roe_delta'): lev})
        d_ = rr_['assumptions']['roe'].get('roe_delta', 0.0)
        smr = LY.system_summary(rr_)
        roe_rows.append([f"{lbl} ({d_ * 1e4:+.0f} bp)", _b(smr['Customer savings ($B, undiscounted nominal)']),
                         f"{at(rr_['bau'], 2050) - at(rr_['ss'], 2050):,.2f}",
                         _b(rr_['ss']['equity_return_m'].sum() / 1e3), _b(rr_['bau']['equity_return_m'].sum() / 1e3)])
    # Value stack
    vs = LY.value_stack(c, p, years=(2035, 2050))
    vs_rows = []
    for y, r in vs.iterrows():
        if r.get('flexible kW (incremental)', 0) <= 0:
            continue
        vs_rows.append([str(y), f"{r['cost $/kW-yr']:,.0f}", f"{r['capacity value $/kW-yr']:,.0f}",
                        f"{r['deferral value $/kW-yr']:,.0f}", f"{r['load-enabled value $/kW-yr']:,.0f}",
                        f"{r['total value $/kW-yr']:,.0f}"])
    pays = []
    for tg, lbl in ((2050, 'average bill equal to BAU in 2050'), ('npv3', 'cumulative 2026-2050 saving zero at 3% NPV')):
        cost, note = LY.flex_pays_cost(uj, p, target=tg)
        pays.append(f"{lbl}: " + (f'${cost:,.0f}/kW-yr' if cost is not None else 'n/a') + f" ({note})")
    # Network
    net_rows = []
    for lbl, ov in (('Central network', {}), ('Tight network', TIGHT_NETWORK)):
        for sc in LY.SCENARIOS:
            r = LY.project_layers(uj, p, scenario=sc, overrides=ov)
            b_, s_ = r['bau'].set_index('year'), r['ss'].set_index('year')
            a_ = LY.access_summary(r)
            net_rows.append([lbl, sc, f"{s_.loc[2035, 'capacity_uplift_pct']:.1%}", f"{s_.loc[2050, 'capacity_uplift_pct']:.1%}",
                             f"{a_['MW connected sooner, peak year']:,.0f}",
                             f"{a_[LY.UD + ', BAU (avg yr per MW affected)']:.2f} &rarr; "
                             f"{a_[LY.UD + ', SS (avg yr per MW affected in BAU)']:.2f}"])
    # Loading bands: MW of load in constrained bands
    con_rows = []
    for lbl, ov in (('Central network', {}), ('Tight network', TIGHT_NETWORK)):
        ct = LY.constrained_table(LY.project_layers(uj, p, overrides=ov), (2030, 2035, 2040, 2050))
        for y, r in ct.iterrows():
            con_rows.append([lbl, str(y), f"{r['BAU MW in constrained bands']:,.0f}", f"{r['SS MW in constrained bands']:,.0f}",
                             f"{r['BAU MW waiting for upgrade']:,.0f}", f"{r['SS MW waiting for upgrade']:,.0f}"])
    nb = c['bands']
    band_desc = '; '.join(f"{b['name']} {b['loading0']:.0%}" for b in nb)
    band_status = LY.network_block(uj['forward_assumptions']).get('bands', {}).get('status', '')
    # Constrained sub-band (load above the planning limit), Central scenario
    nwp = LY.network_block(uj['forward_assumptions'])
    sub_rows = []
    for lbl, nw in (('Central (sub-band on)', {'subband_enabled': True}),
                    ('Central, flexibility targeted', {'subband_enabled': True, 'flex_targeting_enabled': True})):
        r = LY.project_layers(uj, p, network=nw)
        b_, s_ = r['bau'].set_index('year'), r['ss'].set_index('year')
        a_ = LY.access_summary(r)
        for y in (2026, 2028, 2030, 2035):
            sub_rows.append([lbl, str(y), f"{b_.loc[y, 'above_planning_limit_mw']:,.0f}", f"{s_.loc[y, 'above_planning_limit_mw']:,.0f}",
                             f"{b_.loc[y, 'upgrade_wait_mw']:,.0f}", f"{s_.loc[y, 'upgrade_wait_mw']:,.0f}",
                             f"{a_[LY.UD + ' avoided (MW-years)']:,.0f}" if y == 2026 else '',
                             f"{b_.loc[2050, 'avg_bill_total'] - s_.loc[2050, 'avg_bill_total']:,.2f}" if y == 2026 else ''])
    sub_desc = (f"{nwp['subband_load_share']['value']:.1%} of network load at {nwp['subband_utilisation']['value']:.1%} "
                f"planning utilisation (share status {nwp['subband_load_share']['status']}, utilisation status "
                f"{nwp['subband_utilisation']['status']}); operating limit {LY.operating_limit({k: v.get('value') for k, v in nwp.items() if isinstance(v, dict) and 'value' in v}):.2f} x planning capacity")
    # Upgrade Delay for Interconnection by year, Central
    ud_rows = []
    udt = LY.upgrade_delay_table(c, (2028, 2030, 2032, 2035, 2040, 2050))
    for y, r in udt.iterrows():
        ud_rows.append([str(y), f"{r[f'BAU {LY.UD} (yr)']:.2f}", f"{r[f'SS {LY.UD} (yr)']:.2f}",
                        f"{r['BAU MW affected (requested that year)']:,.1f}", f"{r['SS MW affected (requested that year)']:,.1f}",
                        f"{r['BAU MW waiting for upgrade']:,.0f}", f"{r['SS MW waiting for upgrade']:,.0f}",
                        f"{r['MW-years of delay avoided']:,.0f}"])
    ud_in = '; '.join(f"{lab} {nwp[k].get('central')} yr ({nwp[k].get('status')})" for k, lab in
                      (('upgrade_delay_ordinary_years', 'ordinary new load'), ('upgrade_delay_large_years', 'large loads'))
                      if k in nwp)
    if 'backlog_clearance_pct' in nwp:
        ud_in += (f"; backlog cleared {nwp['backlog_clearance_pct']['central']:.0%} a year "
                  f"({nwp['backlog_clearance_pct']['status']}); build-rate priority "
                  f"{'on' if nwp.get('constrained_build_priority', {}).get('value') else 'off'}")
    # Headroom sweep
    sw = LY.headroom_sweep(uj, p)
    sweep_img = _fig_b64(headroom_sweep_figure(sw, name, panels=('saving', 'customer_npv', 'delay')), 'Headroom sweep')
    def _sw(m, x, c, dc='central'):
        return float(sw.loc[(sw['delay case'] == dc) & (sw['mean utilisation'] == m) & (sw['sub-band share'] == x), c].iloc[0])
    sweep_rows = [[f'{m:.0%}', _fmt(_sw(m, 0.043, '2050 monthly saving ($, nominal)'), 2),
                   f"${_sw(m, 0.043, 'Customer savings ($B, undiscounted nominal)'):,.2f}B",
                   f"${_sw(m, 0.043, 'Customer savings ($B, NPV 3%, 2026 $)'):,.2f}B",
                   f"${_sw(m, 0.043, 'Wires capex avoided or deferred ($B, undiscounted nominal)'):,.2f}B",
                   f"{_sw(m, 0.043, 'MW connected sooner (peak year)'):,.0f}",
                   ' / '.join(f"{_sw(m, 0.043, LY.UD + ' avoided (MW-years)', dc):,.0f}" for dc in ('short', 'central', 'long')),
                   _fmt(_sw(m, 0.043, 'Connection cost avoided ($M, undiscounted nominal)'), 0, suffix='M')]
                  for m in (0.6, 0.7, 0.8, 0.9, 1.0)]
    # Access benefits (not on the bill)
    acc_rows = []
    for lbl, ov, nw in (('Central network', {}, None), ('Central network, sub-band on in every scenario', {}, {'subband_enabled': True}),
                        ('Tight network', TIGHT_NETWORK, None)):
        at_ = LY.access_table(uj, p, overrides=ov, network=nw)
        for sc, r in at_.iterrows():
            acc_rows.append([lbl, sc, f"{r['MW affected by upgrade delay, BAU (2026-2050 requests)']:,.0f}",
                             f"{r[LY.UD + ', BAU (avg yr per MW affected)']:.2f} &rarr; "
                             f"{r[LY.UD + ', SS (avg yr per MW affected in BAU)']:.2f}",
                             f"{r[LY.UD + ' avoided (MW-years)']:,.0f}", f"{r['MW connected sooner, peak year']:,.0f}",
                             _fmt(r['Connection cost avoided by new customers ($M, undiscounted nominal)'], 0, suffix='M'),
                             _fmt(r['Connection cost avoided by new customers ($M, NPV 3%, 2026 $)'], 0, suffix='M'),
                             f"{r['Electrification GWh brought forward (cumulative)']:,.0f}"])
    # MW paths, target vs ramp limit
    mp = LY.mw_path_table(uj, p, years=(2030, 2035, 2050))['Total flexible MW']
    ramp_rows = [[str(y), f"{mp.loc[('target path', y)]:,.0f}", f"{mp.loc[('with ramp limit', y)]:,.0f}"]
                 for y in (2030, 2035, 2050)]
    # MW by type
    mt = LY.mw_table(c, (2035, 2050))
    ma = LY.mw_table(runs['Ambitious'], (2050,))
    mw_rows = []
    for k in LY.FLEX_TYPES:
        lab = LY.FLEX_LABEL[k]
        mw_rows.append([lab, f"{mt.loc[2035, f'{lab} MW (today)']:,.0f}", f"{mt.loc[2035, f'{lab} MW (SS)']:,.0f}",
                        f"{mt.loc[2050, f'{lab} MW (SS)']:,.0f}", f"{ma.loc[2050, f'{lab} MW (SS)']:,.0f}"])
    # Earnings
    et = LY.earnings_table(c).sum()
    earn_rows = [('BAU: equity return on rate base', _fmt(et['BAU equity return'], 0, suffix='M')),
                 ('Shared savings: equity return on rate base', _fmt(et['SS equity return'], 0, suffix='M')),
                 ('Shared savings: shared savings earnings (earnings opportunity)', _fmt(et['SS shared savings earnings'], 0, suffix='M')),
                 ('Shared savings: total', _fmt(et['SS total earnings'], 0, suffix='M'))]
    return f"""
  <section class="page-break">
    <h2>Layered Projection: Today's Bill to 2050</h2>
    <p class="section-intro">GridDividend layer engine (engine/layers.py), separate from the projections above. Bills are the
      <strong>average residential bill</strong> ($/month, nominal; energy efficiency lowers usage). Scenarios: Cautious /
      Central / Ambitious (forward_assumptions in the utility data file). Directional illustration, not a forecast.</p>
    {method}
    <ul class="lede">{''.join(f'<li>{x}</li>' for x in lead)}</ul>
    <h2>Starting Bill by Category</h2>
    <p class="section-intro">Today's residential bill at {kwh:,} kWh/month, $/month nominal (starting_bill, with derived
      capacity carve-out and adjustments).</p>
    {_tbl(['Category', '$/month'], start_rows)}
    <h2>Average Residential Bill by Scenario</h2>
    <p class="section-intro">$/month, nominal.</p>
    {_tbl(['Year', 'BAU', 'Cautious', 'Central', 'Ambitious'], bill_rows)}
    <h2>2050 Waterfall, Central</h2>
    <p class="section-intro">BAU to shared-savings average residential bill, $/month nominal, one step per layer.</p>
    {_tbl(['Step', '$/month'], wf_rows)}
    <h2>System-Wide Results, Central</h2>
    <p class="section-intro">BAU minus shared savings, all customers. Customer savings = delivery (net of shared savings
      earnings and any ROE change), program and capacity costs, plus efficiency energy at today's residential supply rate
      (all classes; likely an overstatement for commercial and industrial customers), wholesale energy (flexible load shifted
      to off-peak hours), avoided transmission and avoided marginal distribution losses. Efficiency energy is counted once.
      $B undiscounted nominal unless marked NPV.</p>
    {_tbl(['Measure', 'Value'], sys_rows)}
    <h2>Contribution by Layer, Central</h2>
    <p class="section-intro">Layers added one at a time in waterfall order. Customer savings in $B; monthly bill change in
      $/month nominal (negative = lower bill); shared savings earnings attributable to each layer: total earnings split in
      proportion to each layer's contribution to the savings pool (programs takes a negative share, because its costs
      come before the savings they enable). Not on the bill and reported separately: access benefits (below); next candidates, not yet
      modelled: resilience, capacity price suppression, the economic value of faster connections and emissions.</p>
    {_tbl(['Layer', 'Customer savings ($B undiscounted nominal)', 'Customer savings ($B NPV 3%, 2026 $)', 'Bill 2035',
           'Bill 2050', 'Shared savings earnings ($B undiscounted nominal)', 'Shared savings earnings ($B NPV 3%, 2026 $)'],
          lc_rows)}
    <p class="section-intro">ROE lever (Central is no change in allowed ROE; outside the shared-savings pool, so it moves the
      equity return, not shared savings earnings):</p>
    {_tbl(['Setting', 'Customer savings ($B undiscounted nominal)', '2050 monthly saving ($, nominal)',
           'SS equity return ($B undiscounted nominal)', 'BAU equity return ($B undiscounted nominal)'], roe_rows)}
    <h2>Value Stack for Flexible Resources, Central</h2>
    <p class="section-intro">$ per kW-year of incremental flexible capacity, nominal. Cost at which flexibility pays for
      itself (MW-weighted, 2026 $): {'; '.join(pays)}.</p>
    {_tbl(['Year', 'Cost', 'Capacity value', 'Deferral value', 'Load-enabled value', 'Total value'], vs_rows)}
    <h2>Network Capacity: Effective Uplift and Load Connected Sooner</h2>
    <p class="section-intro">Effective capacity uplift = flexible headroom / network capacity. MW connected sooner (peak year)
      and the average Upgrade Delay for Interconnection, BAU &rarr; shared savings (years per MW that waits under BAU,
      2026&ndash;2050 requests). Tight network = low planning headroom, long lead time, low build rate (sensitivity).</p>
    {_tbl(['Network', 'Scenario', 'Uplift 2035', 'Uplift 2050', 'MW connected sooner (peak year)',
           'Upgrade Delay for Interconnection (yr, BAU &rarr; SS)'], net_rows)}
    <h2>Loading Bands: Load in Constrained Bands</h2>
    <p class="section-intro">The network is split into {len(nb)} bands of substation loading (starting loading: {band_desc};
      status {band_status}). A band is constrained when its load exceeds firm capacity plus counted flexible headroom.
      MW of network load in constrained bands and MW waiting for upgrade, Central scenario.</p>
    {_tbl(['Network', 'Year', 'BAU MW in constrained bands', 'Shared savings MW in constrained bands',
           'BAU MW waiting for upgrade', 'Shared savings MW waiting for upgrade'], con_rows)}
    <h2>Constrained Sub-Band: Load Above the Planning Limit</h2>
    <p class="section-intro">On in every scenario (a scenario's network values or the notebook override can switch it
      off): {sub_desc}. Existing load stays connected up to the operating limit; the backlog above the planning limit is
      cleared at the backlog clearance rate, and new load in the sub-band waits the Upgrade Delay for Interconnection. MW
      above the planning limit and MW waiting for upgrade are separate measures, BAU and shared savings. Flexibility
      targeted = flexible headroom sited first where load is above the planning limit.</p>
    {_tbl(['Setting', 'Year', 'BAU MW above planning limit', 'SS MW above planning limit', 'BAU MW waiting for upgrade',
           'SS MW waiting for upgrade', 'Upgrade Delay avoided (MW-yr, 2026-2050)', '2050 monthly saving ($, nominal)'],
          sub_rows)}
    <h2>Upgrade Delay for Interconnection, Central</h2>
    <p class="section-intro">The time a new customer in a constrained area waits for the grid upgrade before connecting.
      Inputs: {ud_in}. By request year: average years waited by the MW that had to wait (MW affected), BAU and shared
      savings; MW waiting for upgrade and MW-years of delay avoided in that calendar year. Load still waiting in 2050 is
      counted to the end of 2050.</p>
    {_tbl(['Request year', 'BAU delay (yr)', 'SS delay (yr)', 'BAU MW affected', 'SS MW affected', 'BAU MW waiting',
           'SS MW waiting', 'MW-years avoided'], ud_rows)}
    <h2>How the Potential Depends on Existing Headroom</h2>
    <p class="section-intro">Headroom sweep, Central scenario: mean starting planning utilisation from 60% to 100% (bands
      shifted together, each capped at the planning limit) and share of load in the constrained sub-band (0% to 15%;
      system mean held fixed), at the central Upgrade Delay case; the third panel runs the upgrade delays and backlog
      clearance at short (low delays, fast clearance), central and long. Table at a 4.3% sub-band share. Customer savings = delivery, program and capacity costs plus
      efficiency energy at today's residential supply rate (all classes; likely an overstatement for commercial and
      industrial customers).</p>
    {sweep_img}
    {_tbl(['Mean utilisation', '2050 monthly saving ($, nominal)', 'Customer savings ($B undiscounted nominal)',
           'Customer savings ($B NPV 3%, 2026 $)', 'Wires capex avoided ($B undiscounted nominal)',
           'MW connected sooner (peak year)', 'Upgrade Delay avoided (MW-yr; short / central / long)',
           'Connection cost avoided ($M undiscounted nominal)'],
          sweep_rows)}
    <h2>Access: Faster Connections (Not on the Bill)</h2>
    <p class="section-intro">Benefits to the customers being connected, reported separately from the residential bill.
      Upgrade Delay for Interconnection: MW of new load that waits under BAU, the average wait BAU &rarr; shared savings
      (years per MW that waits under BAU) and MW-years avoided. Connection cost avoided = network upgrade cost
      ($/MW at the utility's distribution upgrade cost) for MW connected sooner (flexible connections count once, as network
      headroom, not here): an upper bound,
      since the share paid by new customers through CIAC is tariff-specific. Electrification GWh brought forward = energy
      of the MW connected sooner, electrification share of load growth. Efficiency is not counted as MW connected sooner.</p>
    {_tbl(['Network', 'Scenario', 'MW affected (BAU)', 'Upgrade Delay (yr, BAU &rarr; SS)',
           'Upgrade Delay avoided (MW-yr, 2026-2050)', 'MW connected sooner (peak year)',
           'Connection cost avoided ($M undiscounted nominal)',
           'Connection cost avoided ($M NPV 3%, 2026 $)', 'Electrification GWh brought forward'], acc_rows)}
    <h2>Flexible MW: Target Path vs Ramp Limit</h2>
    <p class="section-intro">Total flexible nameplate MW, Central: the target path, and with the maximum annual growth per
      resource type (observed program ramps).</p>
    {_tbl(['Year', 'Target path', 'With ramp limit'], ramp_rows)}
    <h2>Flexible MW by Resource Type</h2>
    <p class="section-intro">Nameplate MW: today's programs, Central 2035 and 2050, Ambitious 2050.</p>
    {_tbl(['Resource', 'Today', 'Central 2035', 'Central 2050', 'Ambitious 2050'], mw_rows)}
    <h2>Utility Earnings, Central</h2>
    <p class="section-intro">Cumulative 2026&ndash;2050, $M undiscounted nominal. Shared savings earnings are the
      utility's earnings opportunity under the reform.</p>
    {_tbl(['Series', '$M'], earn_rows)}
  </section>"""
