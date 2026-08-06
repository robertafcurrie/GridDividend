# GridDividend — CLAUDE.md

## Project purpose

GridDividend is a Jupyter Notebook policy simulation framework modelling shared savings mechanisms for electric distribution utilities. The core question: if Non-Wires Solutions (NWS) — demand response, batteries, managed EV charging — defer traditional CAPEX, how should those savings be split between customers and the utility, and what is the bill impact over a 25-year horizon?

This is an exploratory/educational tool, not a utility planning model or rate-case replica. AI has been used extensively in its creation.

## Repository layout

```
GridDividend_v1.0.ipynb   — entire model (36 cells, self-contained)
requirements.txt          — pandas, numpy, matplotlib (minimum versions)
charts_article/           — 12 publication-quality charts (300 dpi PNG, written on notebook run)
docs/                     — original pre-run chart images (legacy README references)
README.md
LICENSE                   — MIT
```

No Python modules, tests, or helper scripts exist yet.

## Repository Architecture (v1.1+)

The codebase uses a modular structure separating engine from data:

```
engine/model.py          — project(), run_named_scenario(), apply_passthrough_savings()
engine/report.py         — compute_insights(), render_report_html(), try_convert_html_to_pdf()
utilities/ConEd.json     — Con Edison parameters
utilities/RGE.json       — RG&E parameters
utilities/[Utility].json — one file per utility for new states
shared/capacity_markets/ — per-market ICAP/capacity cost data
notebooks/               — state-specific notebooks importing from engine/
notebooks/reports/       — per-utility/scenario HTML + best-effort PDF summary reports (gitignored, written on notebook run)
GridDividend_v1.0.ipynb  — self-contained notebook (kept for compatibility)
```

To add a new utility:
1. Create `utilities/[Name].json` following the `ConEd.json` structure
2. Create `shared/capacity_markets/[MARKET].json` if market not already defined
3. Copy `notebooks/GridDividend_NewYork.ipynb` as a template
4. Load the new utility JSON in Section 0 and add to `utilities_to_run`
5. Run through Section 6 and verify results are plausible

## Running the notebook

The kernel name in the notebook metadata is `conda-base-py`. When executing headlessly via nbconvert, override the kernel:

```bash
jupyter nbconvert --to notebook --execute \
  --ExecutePreprocessor.kernel_name=python3 \
  GridDividend_v1.0.ipynb --output GridDividend_executed.ipynb
```

The notebook installs nothing at runtime — all dependencies (pandas, numpy, matplotlib) must be present in the environment beforehand.

## Key domain concepts

| Term | Meaning |
|------|---------|
| NWS | Non-Wires Solution — DER/DR programmes that defer traditional network CAPEX |
| NWA | Non-Wires Alternative — a specific NWS procurement |
| DER | Distributed Energy Resource — rooftop solar, battery, managed EV, demand response |
| Shared savings | Mechanism splitting NWS cost savings between utility (incentive) and customers (bill reduction) |
| BAU | Business As Usual — traditional build-out, no shared savings reform |
| Rate base | Regulated asset value on which the utility earns its allowed ROE |
| WACC | Weighted average cost of capital (equity + debt blend) |
| CLCPA | Climate Leadership and Community Protection Act — NY's 2019 clean energy law |

## Utilities currently modelled

| Key | Name | Rate case source |
|-----|------|-----------------|
| `'ConEd'` | Consolidated Edison (CECONY) | Case 25-E-0072, approved Jan 2026 |
| `'RGE'` | Rochester Gas and Electric | Case 25-E-0379, temp rates Jun 2026; final order pending |

## Notebook structure

Cell indices are 0-based (matching `nb['cells'][n]` in Python).

| Section | Cell(s) | Content |
|---------|---------|---------|
| Title | 0 | Notebook introduction and scope statement |
| 0 | 1–2 | Imports, matplotlib styling, output directory |
| 1 | 3–4 | All user-adjustable parameters (edit here, re-run all) |
| 1b | 5–8 | Scenario definitions (`SCENARIO_DEFS`) and parameter guidance |
| 2 | 9–10 | Utility starting data from filed rate cases |
| 3 | 11–12 | `project()` model engine: 2026–2050 annual loop |
| 4 | 13–15 | Runs BAU / all named scenarios; `run_named_scenario()` |
| 5 | 16–17 | Customer bill charts |
| 6 | 18–19 | CAPEX & OPEX spending charts |
| 7 | 20–21 | Utility financial results |
| 8 | 22–23 | Sensitivity analysis |
| 9 | 24–25 | Con Edison vs. RG&E side-by-side comparison |
| 9b | 26–29 | Near-term vs long-term trade-off (5 scenarios) |
| 9c | 30–31 | Article charts (Charts 1–6, saved to `charts_article/`) |
| 9d | 32–34 | Deferral sensitivity (Chart 7) + long-term case (Charts 8–12) |
| 10 | 35 | Model caveats and scope statement (13 items) |
| 11 | 36–37 | Summary report generator — single scenario vs. BAU, never a cross-scenario comparison; toggle via `GENERATE_SUMMARY_REPORT` / `REPORT_SCENARIOS`; writes `reports/{Utility}_{Scenario}_{years}.html` (+ `.pdf` best-effort); see `engine/report.py` |

## Key parameters (Section 1, Cell 4)

Every parameter has a source citation in the comment block immediately below it. The most sensitive parameters:

- `UTILITY_SAVINGS_SHARE` — fraction of savings retained by utility (default 0.30)
- `NWS_AVOIDANCE_OF_ELIGIBLE_MATURE` — avoidance rate at programme maturity (default 0.80)
- `NWS_AVOIDANCE_RAMP_YEARS` — years to reach maturity (default 9)
- `FLEX_LOAD_UTILISATION_SHARE_SS` — utilisation credit for shared savings scenario (default 0.15)
- `DEFERRAL_FRACTION` — share of avoided CAPEX that eventually re-enters rate base (default 0.0 = permanent avoidance); 0.40–0.60 more realistic for dense urban networks long-term
- `DEFERRAL_PERIOD_YEARS` — years before deferred CAPEX re-enters rate base (default 10)
- `UPFRONT_PASSTHROUGH_YEARS` — years of 100% customer passthrough before standard split applies (default 0); set to 3 in the FRONTLOADED scenario
- `utilities_to_run` — list of utility keys to model (`['ConEd']`, `['RGE']`, or both)

## What to be careful about

- **Not a forecast.** Direction and order of magnitude only.
- **Spatially aggregate.** NWS is modelled as a system-wide % of eligible CAPEX; real outcomes depend on feeder-level constraint types and DER siting.
- **RG&E data is provisional.** Update when Case 25-E-0379 issues a final order.
- **Property tax rates are estimates** (~1.6% ConEd, ~1.8% RG&E electric assets only) derived from annual reports, not official filed figures.
- **FRONTLOADED scenario** uses `upfront_passthrough_years=3`; utility earns 0% of shared savings in years 1–3. The 25-year cumulative outcome is the same as BASE — it is a timing mechanism.
- **Do not remove or reorder sections** — downstream cells reference earlier variables by name.

## Coding conventions

- Parameters: `UPPER_SNAKE_CASE`; model functions: `lower_snake_case`
- Every new parameter in Section 1 must include a source citation in the inline comment block
- Keep the notebook self-contained — avoid adding external data file dependencies
- New utility dicts must match the structure of `UTILITIES` in Cell 4, with all fields documented and sourced

## When adding a new utility

Supply a dict matching the `UTILITIES` structure (Cell 4): rate base, annual CAPEX, allowed ROE, equity ratio, customer count, peak demand, delivery/supply tariff rates, and DER starting levels. Document the rate case source inline next to each figure. Also add a matching entry in `UTILITY_BILL_PARAMS` (also Cell 4).
