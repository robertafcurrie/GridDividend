# engine/report.py
# Single-scenario-vs-BAU summary report generator — utility-agnostic.
# Never compares named scenarios to each other; one report = one scenario vs BAU.

import base64
import os
import platform
import shutil
import subprocess

import numpy as np

UNIVERSAL_CAVEATS = [
    ("Not a forecast.", "This is a single deterministic model path illustrating "
     "direction and order of magnitude, not a prediction of actual future bills "
     "or revenue."),
    ("Spatially aggregate.", "Non-Wires Solutions are modelled as a system-wide "
     "share of eligible CAPEX, not a feeder-level analysis — real outcomes will "
     "vary by location and constraint type."),
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


def compute_insights(bau_df, scenario_df, scenario_label, years):
    """Deterministic derived facts for one scenario vs BAU. Numbers only — no
    prose. See render_report_html() for the templated sentences built from this.
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
                        generated_at, git_sha):
    """Self-contained HTML string for one utility/scenario. System font stack
    only — no embedded custom font, so this works portably with zero new deps
    and no third-party font redistribution."""
    short_name = utility_json.get('short_name', utility_key)
    milestones = _milestone_years(years)

    ins = insights
    up_or_down = 'higher' if ins['revenue_delta_b'] >= 0 else 'lower'
    sentences = [
        f"By {ins['end_year']}, the typical {short_name} residential customer pays "
        f"{_fmt(ins['scenario_final_bill'])}/month under {scenario_label} versus "
        f"{_fmt(ins['bau_final_bill'])}/month under business-as-usual &mdash; a "
        f"{_fmt(ins['bill_gap_monthly'])}/month ({ins['bill_gap_pct']:.0%}) reduction.",

        f"Cumulative bill savings over {ins['start_year']}&ndash;{ins['end_year']} reach "
        f"{_fmt(ins['cum_bill_savings_b'], 1, suffix='B')}, driven by "
        f"{_fmt(ins['cum_capex_avoided_b'], 1, suffix='B')} of avoided distribution CAPEX "
        f"against {_fmt(ins['cum_opex_b'], 1, suffix='B')} of NWS programme cost.",

        f"Modelled total utility revenue under {scenario_label} is "
        f"{_fmt(abs(ins['revenue_delta_b']), 1, suffix='B')} {up_or_down}, cumulatively, "
        f"than business-as-usual.",
    ]
    threshold_bits = []
    if ins['first_10_year']:
        threshold_bits.append(f"monthly savings first exceed $10 in {ins['first_10_year']}")
    if ins['nws_ceiling_year']:
        threshold_bits.append(
            f"the NWS-eligible CAPEX share reaches its effective ceiling by {ins['nws_ceiling_year']}")
    if threshold_bits:
        sentences.append(("; ".join(threshold_bits) + ".").capitalize())

    def bill_rows():
        out = []
        for yr in milestones:
            b = bau_df[bau_df['year'] == yr].iloc[0]
            s = scenario_df[scenario_df['year'] == yr].iloc[0]
            save_yr = (b['avg_monthly_bill'] - s['avg_monthly_bill']) * 12
            pct = save_yr / b['avg_annual_bill']
            idx = bau_df[bau_df['year'] <= yr].index
            cum = np.sum(
                (bau_df.loc[idx, 'avg_annual_bill'].values - scenario_df.loc[idx, 'avg_annual_bill'].values)
                * scenario_df.loc[idx, 'customers'].values
            ) / 1e9
            out.append(f"<tr><td>{yr}</td><td>{_fmt(b['avg_monthly_bill'],1)}</td>"
                       f"<td>{_fmt(s['avg_monthly_bill'],1)}</td><td>{_fmt(save_yr)}</td>"
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
          <thead><tr><th>Parameter</th><th>Current estimate</th><th style="text-align:left">Verification needed</th></tr></thead>
          <tbody>{"".join(row_html)}</tbody>
        </table>
      </div>
    </section>"""

    caveats_html = "".join(
        f"<li><strong>{title}</strong> {body}</li>" for title, body in UNIVERSAL_CAVEATS
    )

    chart_html = _embed_image(chart_png_path)

    sha_bit = f" &middot; commit {git_sha}" if git_sha else ""

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
.sheet {{ max-width: 760px; margin: 0 auto; background: var(--sheet); border: 1px solid var(--line); padding: 36px 44px; }}
.eyebrow {{ font-family: -apple-system, 'Segoe UI', sans-serif; font-size: 10px; font-weight: 600;
  letter-spacing: 0.13em; text-transform: uppercase; color: var(--copper); margin: 0 0 8px; }}
h1 {{ font-size: 22px; line-height: 1.25; margin: 0 0 6px; }}
.meta {{ font-family: ui-monospace, Menlo, monospace; font-size: 11.5px; color: var(--ink-soft); margin: 0 0 16px; }}
hr {{ border: 0; border-top: 1px solid var(--line-strong); margin: 0 0 16px; }}
.lede {{ font-size: 13px; line-height: 1.5; margin: 0 0 18px; }}
.lede li {{ margin-bottom: 6px; }}
h2 {{ font-size: 14.5px; margin: 0 0 4px; padding-left: 10px; border-left: 3px solid var(--copper); }}
h2.flag {{ border-left-color: var(--flag); }}
.section-intro {{ font-size: 11.5px; color: var(--ink-soft); margin: 4px 0 8px 13px; }}
section {{ margin-bottom: 16px; }}
.chart-img {{ max-width: 100%; height: auto; display: block; margin: 6px 0 12px; border: 1px solid var(--line); }}
table {{ width: 100%; border-collapse: collapse; font-family: ui-monospace, Menlo, monospace; font-size: 10.5px; }}
table.prose td {{ font-family: Georgia, serif; font-size: 11px; white-space: normal; vertical-align: top; }}
th {{ font-family: -apple-system, 'Segoe UI', sans-serif; font-size: 8.5px; font-weight: 600; text-transform: uppercase;
  color: var(--ink-soft); text-align: right; padding: 0 10px 4px 0; border-bottom: 1px solid var(--line-strong); }}
th:first-child, td:first-child {{ text-align: left; }}
td {{ text-align: right; padding: 3px 10px 3px 0; border-bottom: 1px solid var(--line); }}
tr:last-child td {{ border-bottom: 1px solid var(--line-strong); font-weight: 600; }}
.verify-box {{ background: var(--flag-bg); border-left: 3px solid var(--flag); padding: 8px 10px 2px; margin: 5px 0 10px 13px; }}
ul.caveats {{ margin: 5px 0 0 13px; padding-left: 16px; font-size: 11px; line-height: 1.4; }}
footer {{ margin-top: 16px; padding-top: 8px; border-top: 1px solid var(--line);
  font-family: -apple-system, 'Segoe UI', sans-serif; font-size: 9px; color: var(--ink-soft); }}
</style>
</head>
<body>
<div class="sheet">
  <p class="eyebrow">Summary Report &mdash; Single Scenario vs. BAU</p>
  <h1>{short_name}: {scenario_label}, {ins['start_year']}&ndash;{ins['end_year']}</h1>
  <p class="meta">Generated {generated_at}{sha_bit} &middot; GridDividend v1.1</p>
  <hr>
  <ul class="lede">{"".join(f"<li>{s}</li>" for s in sentences)}</ul>

  <section>
    <h2>Customer Bills</h2>
    {chart_html}
    <table>
      <thead><tr><th>Year</th><th>BAU $/mo</th><th>Scenario $/mo</th><th>Saving/yr</th><th>% Saving</th><th>Cum. $B</th></tr></thead>
      <tbody>{bill_rows()}</tbody>
    </table>
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
      <thead><tr><th>Year</th><th>BAU RB $B</th><th>Scen. RB $B</th><th>BAU Earn $M</th><th>Scen. Earn $M</th><th>Incentive $M</th><th>Total Rev $M</th></tr></thead>
      <tbody>{fin_rows()}</tbody>
    </table>
  </section>
  {verify_html}
  <section>
    <h2 class="flag">Model Caveats</h2>
    <ul class="caveats">{caveats_html}</ul>
    <p class="section-intro" style="margin-left:0">See Section 10 of the source notebook for the complete caveats and limitations list.</p>
  </section>

  <footer>
    GridDividend is an open-source policy simulation framework (MIT License) &mdash; not a utility
    planning model or rate-case replica. Auto-generated, single-scenario-vs-BAU only &mdash; not a
    comparison across scenarios.
  </footer>
</div>
</body>
</html>"""


def try_convert_html_to_pdf(html_path, pdf_path, timeout=30):
    """Best-effort HTML->PDF via a local Chrome/Chromium/wkhtmltopdf install.
    Never raises; returns False (and leaves no partial file) if none is found
    or conversion fails."""
    html_abs = os.path.abspath(html_path)
    pdf_abs = os.path.abspath(pdf_path)

    which_names = ['google-chrome-stable', 'google-chrome', 'chromium-browser',
                   'chromium', 'chrome', 'msedge', 'wkhtmltopdf']
    candidates = [shutil.which(name) for name in which_names]

    system = platform.system()
    if system == 'Darwin':
        candidates += [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Chromium.app/Contents/MacOS/Chromium',
            '/opt/homebrew/bin/wkhtmltopdf',
            '/usr/local/bin/wkhtmltopdf',
        ]
    elif system == 'Linux':
        candidates += [
            '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable',
            '/usr/bin/chromium-browser', '/usr/bin/chromium',
            '/snap/bin/chromium', '/usr/bin/wkhtmltopdf',
        ]
    elif system == 'Windows':
        candidates += [
            r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
            r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
        ]

    binary = next((c for c in candidates if c and os.path.exists(c)), None)
    if not binary:
        return False

    is_wkhtmltopdf = 'wkhtmltopdf' in os.path.basename(binary).lower()
    if is_wkhtmltopdf:
        cmd = [binary, html_abs, pdf_abs]
    else:
        cmd = [binary, '--headless=new', '--disable-gpu', '--no-sandbox',
               f'--print-to-pdf={pdf_abs}', html_abs]

    try:
        subprocess.run(cmd, timeout=timeout, capture_output=True)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False

    if os.path.exists(pdf_abs) and os.path.getsize(pdf_abs) > 0:
        return True
    if os.path.exists(pdf_abs):
        os.remove(pdf_abs)
    return False
