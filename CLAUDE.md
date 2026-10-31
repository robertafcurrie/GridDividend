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
engine/report.py         — compute_insights(), render_report_html()
utilities/ConEd.json     — Con Edison parameters
utilities/RGE.json       — RG&E parameters
utilities/Dominion_VA.json — Dominion Energy Virginia parameters
utilities/[Utility].json — one file per utility for new states
shared/capacity_markets/ — per-market ICAP/capacity cost data
notebooks/               — state-specific notebooks importing from engine/
reports/                 — per-utility/scenario HTML summary reports (top-level, gitignored, written on notebook run)
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
| EASE Act | The Electricity Affordability, Savings, and Efficiency Act — the (proposed/hypothetical) legislation that would enact the shared-savings mechanism. "EASE Case" in generated reports is the modelled outcome if the EASE Act passed, contrasted against BAU. Directional illustration only — not a guarantee of results, and not a substitute for state-by-state modelling and legislative design work |
| Rate base | Regulated asset value on which the utility earns its allowed ROE |
| WACC | Weighted average cost of capital (equity + debt blend) |
| CLCPA | Climate Leadership and Community Protection Act — NY's 2019 clean energy law |

## Utilities currently modelled

| Key | Name | Rate case source |
|-----|------|-----------------|
| `'ConEd'` | Consolidated Edison (CECONY) | Case 25-E-0072, approved Jan 2026 |
| `'RGE'` | Rochester Gas and Electric | Case 25-E-0379, temp rates Jun 2026; final order pending |
| `'DomVA'` | Dominion Energy Virginia | SCC Case PUR-2025-00058, rates effective Jan 2026 and Jan 2027 |

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
| 10 | 35 | Model caveats and scope statement (14 items) |
| 11 | 36–37 | Summary report generator — single scenario vs. BAU, never a cross-scenario comparison; toggle via `GENERATE_SUMMARY_REPORT` / `REPORT_SCENARIOS`; writes `reports/{Utility}_{Scenario}_{years}.html`; see `engine/report.py` |

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

## Savings pool basis (`SAVINGS_POOL_BASIS`)

`project()` supports two definitions of the annual shared-savings pool:

- `'capex'` (default; reproduces v1.0 results): pool = avoided CAPEX − NWS OPEX in the year of avoidance. The customer 70% is credited against that year's revenue requirement, and the avoided CAPEX also stays out of rate base. Customers therefore benefit from the same avoided dollar twice: once as a credit and again as years of lower return and property tax on a smaller rate base. The utility's 30% is not recovered from anyone. Treat headline savings under this basis as a likely upper bound.
- `'revenue_requirement'`: pool = annual reduction in delivery revenue requirement vs BAU (return + property tax on the avoided rate base) − NWS OPEX, computed from a paired BAU run. Customers receive the reduction through the lower rate base, with no extra credit. The utility's share is recovered in the delivery revenue requirement. The pool is negative in the first year or so (OPEX exceeds the RR reduction), and the split is applied symmetrically.

The ROE sweep (`engine/roe_sweep.py`, notebook Section 8b in the modular notebooks) runs both bases. `ROE_OVERRIDE` sets a per-run ROE and recomputes WACC. By default it also rebases the starting delivery bill (`ROE_OVERRIDE_REBASE_BILL`), because bills are indexed to each run's own first-year revenue requirement. `tests/test_regression.py` pins the default Con Edison BASE result; run it with `python -m pytest tests/`.

## Correction flags and the CORRECTED preset

Each flag defaults to v1.0 behaviour, and the defaults reproduce v1.0 results bit for bit. `engine/model.py` `PRESETS['CORRECTED']` switches on the recommended set together. It is **not** the default: set `MODEL_PRESET = 'CORRECTED'` in Section 1 to apply it to `MODEL_CONFIG`.

| Flag | Default | CORRECTED | Effect |
|------|---------|-----------|--------|
| `INCLUDE_DEPRECIATION_EXPENSE` | `False` | `True` | Adds 3.5% × opening rate base (the model's rate-base decay) to delivery RR. Recalibrates other O&M so 2026 BAU delivery RR equals `total_revenue_m × delivery_share_rr` (see `delivery_rr_reconciliation()`). Avoided depreciation enters the RR pool |
| `SAVINGS_POOL_BASIS` | `'capex'` | `'revenue_requirement'` | See above |
| `NEGATIVE_POOL_TREATMENT` | `'symmetric'` | `'carry_forward'` | `'floor_zero'`: the utility share is never below zero. `'carry_forward'`: negative pools are netted against later positive pools, with no interest. Applies to the NWS pool only; capacity pass-through is added afterwards and is never negative |
| `NWS_COST_TREATMENT` | `'expense'` | `'expense'` | `'capitalise'`: NWS OPEX goes into a regulatory asset in rate base. It earns WACC, carries no property tax or decay, and is amortised straight-line over `NWS_AMORTISATION_YEARS` (10) starting the following year |
| `BILL_INDEX_BASE` | `'own'` | `'bau'` | `'bau'` indexes every scenario's delivery bill to BAU 2026 delivery RR, so first-year differences show in bills |

The engine output also includes `equity_earnings_m`: equity return (rate base × equity ratio × ROE) plus shared income. The older `total_utility_revenue_m` is the WACC-based series: the full return on rate base (including debt interest) plus shared income. Incentive metrics in the ROE sweep use the equity-only series.

**2026 reconciliation caveat:** With depreciation included, recalibrated other O&M is 14% of delivery RR for Con Edison (low), 64% for RG&E and 55% for Dominion VA (high). The high values suggest the back-calculated RG&E and Dominion rate bases are understated relative to rate-case revenue. Without the flag, the v1.0 model's 2026 delivery RR is 13–43% below the rate-case figure (ConEd $4,405M vs $5,040M; RG&E $350M vs $614M; DomVA $2,526M vs $4,050M).

## v1.0 notebook vs engine (reconciliation)

The "$12,907 per customer" Con Edison figure in `README.md` and in a Section 9d code comment is **stale**. It is the output of both code paths **before** commit 78f1a4f (segmented load model, 2026-07-25), which replaced the blended `dc_load_growth_annual` rate with a data-centre segment growing from its own MW base. At every commit since then, `GridDividend_v1.0.ipynb` and `engine/` both give **$12,423** (undiscounted nominal, BASE vs BAU), and the bills are bit-identical. The two paths do still differ, as follows:

| Item | v1.0 notebook | engine / modular notebooks | Effect on results |
|------|---------------|----------------------------|-------------------|
| `project()` | Inline copy (cell 12) | `engine/model.py` | Identical logic at HEAD before the correction flags (whitespace-only diff). v1.0 lacks all flags added since |
| Utility data | Inline `UTILITIES` dict (cell 2) | `utilities/*.json` | Same values. The JSON adds only metadata (`capacity_market*`) and an explicit `residential_kwh_month: 600`, which equals the default |
| Capacity pass-through, Section 4 | Inline loop (cell 14) | `apply_passthrough_savings()` | Identical outputs |
| `run_named_scenario()` pass-through | Adds only the customer bill reduction | Also adds the utility share to `utility_shared_revenue_m` / `total_utility_revenue_m`, and the totals to `savings_pool_m` / `customer_savings_m` (fix in commit 018180d) | Bills identical for BASE, ACCELERATED, FREEZE_PLUS, COMBINED. Utility-side columns differ: ConEd BASE shared income +$2,957M and pool +$9,858M cumulative in the engine; RG&E +$191M / +$635M |
| FRONTLOADED upfront passthrough | Moves only the NWS utility share to customers in years 1–3 | Also moves the pass-through utility share | Engine FRONTLOADED bills are slightly lower (ConEd $5.5, RG&E $3.4 cumulative per customer) |
| `pt_*` columns on scenario frames | Absent | Present | — |

**Proposed change (not applied):** make `GridDividend_v1.0.ipynb` import the engine.
1. Cell 2: add `sys.path.insert(0, '.')` and `from engine import project, run_named_scenario, apply_passthrough_savings`. Keep the inline `UTILITIES` dict, or load `utilities/*.json` as the NY notebook does. Loading the JSON gives a single source of data but gives up the "self-contained" convention, so that is the author's decision.
2. Cell 12: replace the inline helpers and `project()` with a comment pointing to `engine/model.py`. Keep `vlines()`.
3. Cell 14: replace the inline pass-through loop with `results = apply_passthrough_savings(results, k, utility_data, MODEL_CONFIG)`.
4. Cell 15: delete the inline `run_named_scenario()` definition and keep the loop that calls it.
5. Cell 4: add the new Section 1 flags (copy from `notebooks/GridDividend_NewYork.ipynb`).

Expected effect: identical bills. The v1.0 utility-side columns (and anything plotted from them) pick up the pass-through fix, and FRONTLOADED bills shift as in the table. Update `README.md` ($12,907 → $12,423; aggregate $52B needs recomputing) at the same time.

## Starting-point bill (`starting_bill`)

Each utility JSON has a `starting_bill` section describing today's residential bill at `residential_kwh_month`, line by line. It is data only: the engine does not read it yet. It is the first layer of the move to range-based results built up from each utility's starting point.

Top level: `as_of`, `benchmark_kwh_month`, `location`, `notes`, optional `published_check` (a published typical bill to compare against), and `lines`. Each line has:

| Field | Meaning |
|---|---|
| `id`, `name` | Short key; name as on the tariff or bill |
| `rate`, `unit` | `$/month`, `$/kWh`, or `pct` (with `applies_to`: `delivery`, `supply` or `distribution_and_transmission`). `null` when embedded or unknown |
| `category` | `distribution_base`, `distribution_rider`, `program_surcharge`, `supply_energy`, `capacity`, `transmission`, `taxes_and_fees` |
| `bill_section` | `delivery`, `supply` or `tax` |
| `program_type` | Program surcharges only: `demand_response`, `energy_efficiency`, `electrification`, `der_nwa` (core when utility-run); `clean_energy_standard`, `nuclear_or_zec`, `low_income`, `public_purpose_other` (not core) |
| `run_by` | `utility`, `state agency (...)`, or other |
| `core_business_under_shared_savings` | `true` if the program would become core utility business, earning shared savings earnings rather than pass-through recovery |
| `included_in_benchmark` | `false` for embedded, unknown or alternative-location lines |
| `annual_recovery_m`, `spend_capex_m`, `spend_opex_m` | System-wide $M where published or derivable; else `null` |
| `tariff_detail`, `notes` | Derivation and caveats |
| `source`, `as_of`, `status` | Every line: `sourced`, `derived` or `_VERIFY` |

Validate with `python scripts/check_starting_bill.py` (add `--json` for machine output). It prices each line at the benchmark usage, totals by category and section, compares the delivery and supply subtotals with `delivery_rate_kwh`, `supply_rate_kwh` and `basic_charge_month` (from the JSON, or the notebook's `UTILITY_BILL_PARAMS` for Con Edison and RG&E), and reports the core-business program share. It never changes those fields.

## Layer engine (`engine/layers.py`) and `forward_assumptions`

A separate, additive model; v1.0 and CORRECTED do not use it. Year zero is `starting_bill` plus `capacity_carve_out` (where capacity is embedded, a derived capacity line is split out of the parent line(s), total unchanged; Dominion splits 91.5% base generation / 8.5% fuel) and `starting_adjustments` (Pepco MD Order No. 92607 +$3.94/month). Each bill category is projected 2026-2050 in BAU and SHARED SAVINGS. Distribution lines follow the wires revenue requirement per kWh (2026 RR as in `delivery_rr_reconciliation()`, rate base decaying at `RATE_BASE_DECAY`). Core program costs and shared savings earnings are recovered per kWh with today's residential allocation of the core surcharges. Supply, transmission and program surcharges grow at their own rates, capacity follows zonal price x peak, and percentage taxes apply to their base lines.

Layers (each `enabled`, values low / central / high with `source`, `as_of`, `status`):
- `system_needs`: baseline, electrification (split 80% EVs / 20% buildings, NREL EFS), data centres, peak, growth vs asset-condition capex. Applies to both cases.
- `programs`: core-business surcharges leave the bill from `transition_year`. Spend = today's surcharge-funded spend + incremental flexible MW (demand response, managed EV, storage, other DER; share of peak by 2030/2035/2050, DOE VPP Liftoff) x cost per kW-year + energy efficiency (incremental savings x levelised $/kWh, measure life). Capitalised shares go to a regulatory asset.
- `deferral`: new firm MW (derated flex + EE peak) x `locational_match` x $/MW avoid growth capex only.
- `utilisation`: utilisation share = `per_flex_share` x firm flexible MW / peak (capped).
- `capacity`: firm MW at the zonal price (RG&E: NYISO Rest of State in the layer engine only).
- `mechanism`: utility share of the pool = shared savings earnings.
- Hooks `wholesale_energy` and `roe` must stay disabled.

Scenarios Cautious / Central / Ambitious (`forward_assumptions['scenarios']`) set programs, deferral and utilisation together and hold growth and the utility share at central. Two bill measures: `avg_bill_total` (average residential bill; EE lowers usage; headline) and `bill_total` (benchmark usage). Outputs: `bill_table`, `scenario_table`, `waterfall`, `mw_table`, `value_stack`, `flex_pays_cost` (cost at which flexibility pays for itself), `tornado` (on the saving), `cumulative_savings`, `earnings_table`. They feed Section 13 of each state notebook. `tests/test_layers.py` checks: layers off = BAU; year zero = `starting_bill` total; 2026 BAU RR = rate-case target; moving programs into rates with no new resources is bill-neutral; flexible spend = MW x cost; EE lowers sales and the average bill; scenarios are ordered.

## What to be careful about

- **Not a forecast.** Direction and order of magnitude only.
- **Spatially aggregate.** NWS is modelled as a system-wide % of eligible CAPEX; real outcomes depend on feeder-level constraint types and DER siting.
- **No real grid-utilization data.** NWS-eligible CAPEX share and avoidance rates are estimates from rate-case filings and industry benchmarks, not measured from actual utility hosting-capacity, feeder-loading, or grid-utilization data. If a utility publishes real grid-utilization data, prefer it over these assumptions — this applies to every utility modelled, and is flagged explicitly for Dominion VA (`utilities/Dominion_VA.json`, `_grid_utilization_VERIFY`).
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
