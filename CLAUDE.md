# GridDividend — CLAUDE.md

## Project purpose

GridDividend is a policy simulation of shared savings for electric distribution utilities. It shows the potential of shared savings and the conditions that unlock it. Flexibility (demand response, managed EV charging, distributed storage, other DER) and energy efficiency become core utility business. They defer network investment, lower capacity, energy, transmission and loss costs, and connect new customers sooner. The utility earns a share of the savings (its **shared savings earnings**, its earnings opportunity); customers keep the rest. Results are ranges across Cautious / Central / Ambitious scenarios, not forecasts.

The **layered model** (`engine/layers.py`, Section 13 of each state notebook) is the current model. The **earlier model** (v1.0 and the CORRECTED preset: `engine/model.py`, Sections 1-12, `GridDividend_v1.0.ipynb`) is kept so its results reproduce exactly. This is an exploratory/educational tool, not a utility planning model or rate-case replica. AI has been used extensively in its creation.

## Working rules

- Do not change any default: v1.0 results, the CORRECTED preset and the pinned tests must reproduce exactly.
- Never invent values. Every number carries a `source`, an `as_of` date and a `status` (see below).
- Framing: the utility's share of savings is its **shared savings earnings** or **earnings opportunity**. Lead with the opportunity, then conditions, then caveats. Don't add break-even analysis to anything new (existing break-even code stays). The cost-recovery value test is "the cost at which flexibility pays for itself".
- Label every dollar figure: nominal or 2026 $; undiscounted or NPV (and the rate).
- Do not mention any private consulting work in comments or docs.
- Work on `main`; commit only when asked; don't push unless asked.
- Keep the documentation in step with the code: update `docs/METHODOLOGY.md` when a calculation changes, rerun `scripts/build_assumptions_register.py` after any JSON change, and add a `CHANGELOG.md` entry (what changed, effect on results) for each commit.

## Status values

Every input in `starting_bill` and `forward_assumptions` has a `status`:

| Status | Meaning |
|---|---|
| `sourced` | Read directly from a cited document (filing, tariff, order, market report, statistical release) |
| `derived` | Calculated from sourced figures; the derivation is in `source` or `notes` |
| `_VERIFY` | An estimate, assumption or proxy (often another utility's data) awaiting confirmation; `source` gives the rationale and what would confirm it |
| `setting` | A model switch or mode choice (e.g. `subband_enabled`, `band_mode`, `in_pool`), not a measured value |

Top-level utility fields use `_..._note` / `_..._VERIFY` keys beside the value instead.

## Repository layout

```
engine/
  layers.py            layered model: project_layers(), outputs, sweeps (current model)
  model.py             earlier model: project(), run_named_scenario(), apply_passthrough_savings(), PRESETS
  report.py            HTML reports: render_report_html() (earlier model), render_layered_section(),
                       headroom_sweep_figure(), TIGHT_NETWORK
  roe_sweep.py         ROE sweep for the earlier model (Section 8b)
  markets.py           loader for shared/capacity_markets/*.json
utilities/
  ConEd.json, RGE.json, Dominion_VA.json, Pepco_MD.json   one file per utility
  TEMPLATE.json        structure for a new utility (earlier-model fields only)
  calibration/Pepco_MD.csv   2026 reconciliation against Pepco's Case 9820 record
shared/capacity_markets/NYISO.json, PJM.json   capacity prices and sources
notebooks/
  GridDividend_NewYork.ipynb    Con Edison and RG&E
  GridDividend_Virginia.ipynb   Dominion Energy Virginia
  GridDividend_Maryland.ipynb   Pepco MD (adds Section 12, Maryland-specific checks)
GridDividend_v1.0.ipynb  self-contained earlier model (inline engine; kept for compatibility)
scripts/check_starting_bill.py   validates starting_bill (python scripts/check_starting_bill.py [--json])
scripts/build_assumptions_register.py   writes docs/assumptions_register.csv and docs/ASSUMPTIONS.md from the JSON
scripts/export_results.py  writes exports/<utility>.json for the web explorer (scenario x electrification pace: yearly bills by category, customer savings, rate base, earnings; waterfalls; Sankey value flows; tornado; metadata)
tests/test_regression.py   earlier model: pins and correction-flag checks
tests/test_layers.py       layered model
tests/test_assumptions_register.py   the assumptions register matches the JSON; every layered input has a status
tests/test_export.py       exports balance and match the headline figures (regenerate exports after any model or JSON change)
tests/fixtures/            layers_single_pool_ebb0c04.json, layers_1b09e20.json, layers_23fec60_model_bau.json (pinned layer outputs)
reports/                   HTML reports (gitignored; written by Section 11 of each state notebook)
charts/, charts_article/   charts written on notebook runs (notebooks/charts/, notebooks/charts_article/)
docs/METHODOLOGY.md        full methodology of the layered model (policy reader; technical subsections; glossary)
docs/ASSUMPTIONS.md, docs/assumptions_register.csv   generated assumptions register (do not edit by hand)
docs/utilities/*.md        per-utility data notes (starting point, sources, proxies, _VERIFY gaps)
docs/*.png                 legacy chart images
CHANGELOG.md               dated entry per commit and its effect on results
exports/                   generated JSON for the web explorer (do not edit by hand)
```

## Running and testing

```bash
python -m pytest tests/                       # full suite (209 tests)
python scripts/build_assumptions_register.py  # after any JSON change (the test fails otherwise)
python scripts/export_results.py              # after any model or JSON change (test_export checks the totals)
cd notebooks && jupyter nbconvert --to notebook --execute --inplace \
  --ExecutePreprocessor.kernel_name=python3 --ExecutePreprocessor.timeout=1800 GridDividend_Virginia.ipynb
```

The notebook kernel in the metadata is `conda-base-py`; override it as above when running headlessly. Nothing is installed at runtime (pandas, numpy, matplotlib; pytest for tests). Notebooks run from `notebooks/` and load `../utilities/*.json`. Re-executing a notebook regenerates its HTML reports in `reports/`.

**Pinned tests.** The three pins are `test_coned_base_cumulative_saving_unchanged`, `test_domva_base_cumulative_saving_unchanged` and `test_pepco_md_base_cumulative_saving_unchanged` (earlier model, BASE vs BAU). The layer fixtures pin the layered model at ebb0c04 (single pool) and 1b09e20 (bands, before the network block). The fixture tests compare BAU exactly and the shared-savings columns not changed on purpose by the code fixes after 50a3f96 (`FIXED_SS` in `tests/test_layers.py`: capacity, bills, RR, earnings, connection cost avoided, MW connected sooner); with the current JSON they also skip Dominion's shared-savings case (demand-response path without embedded efficiency) and Pepco's capacity columns (capacity price aligned with the carve-out) (`DATA_CHANGED`). The current JSON otherwise reproduces 1b09e20 with the sub-band off and the value-stream and ROE layers disabled.

## State notebooks

Sections 0-11 are the earlier model; Section 13 is the layered model. Do not remove or reorder sections: later cells use earlier variables by name.

| Section | Content |
|---|---|
| 0 | Setup; `load_utility()` reads `utilities/*.json` |
| 1, 1b | Earlier-model parameters (`MODEL_PRESET`, correction flags) and named scenarios (`SCENARIO_DEFS`) |
| 2-8 | Starting data, engine note, scenario runs, bills, capex, financials, sensitivity |
| 8b | ROE sweep (`engine/roe_sweep.py`), both pool bases and CORRECTED |
| 9-9d | Comparison (New York only), near-term vs long-term trade-off, article charts 1-12 |
| 10 | Caveats and sources |
| 11 | HTML report per utility and scenario (`reports/`), plus the layered section |
| 12 | Maryland only: reconciliation, break-even shares, sensitivities, regression pin |
| 13 | Layered model: `NETWORK_OVERRIDES`; bills by category; scenarios; waterfall; system-wide results and layer contributions (3b); network, bands, access, MW paths (4a-4e); constrained sub-band and Upgrade Delay (4f); headroom sweep (4g); value stack; tornado; earnings |

## Utilities modelled

| Key | Name | Rate case | Capacity market |
|-----|------|-----------|-----------------|
| `'ConEd'` | Consolidated Edison (CECONY) | NYPSC Case 25-E-0072, approved Jan 2026 | NYISO NYC |
| `'RGE'` | Rochester Gas and Electric | NYPSC Case 25-E-0379, temporary rates Jun 2026; final order pending | NYISO (Rest of State in the layered model) |
| `'DomVA'` | Dominion Energy Virginia | SCC Case PUR-2025-00058, rates effective Jan 2026 and Jan 2027 | PJM DOM |
| `'PepcoMD'` | Potomac Electric Power Co, Maryland | MD PSC Case 9820, Order No. 92607 (Aug 2026) | PJM PEPCO |

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

## Layered model (`engine/layers.py`)

A separate, additive model; v1.0 and CORRECTED do not use it. Year zero is `starting_bill` plus `capacity_carve_out` (where capacity is embedded, a derived capacity line is split out of the parent line(s), total unchanged; Dominion splits 91.5% base generation / 8.5% fuel) and `starting_adjustments` (Pepco MD Order No. 92607 +$3.94/month). The distribution network has explicit firm capacity (network peak x (1 + planning headroom)) that grows only through reinforcement, ordered reactively with a lead time and a maximum build rate; load above capacity waits for the upgrade (MW waiting for upgrade, Upgrade Delay for Interconnection, GWh not served on time). The network is split into loading bands (share of firm capacity and starting loading per band; optional `growth_share` / `flex_share`, default pro rata to load). Constraints, delay, deferral and load enabled are computed per band and summed; projects under way at 2026 are the single-pool seed allocated by growth share, so the 2026 growth / asset-condition capex split does not depend on the bands. No bands = one band at the planning target = the single-pool model. A band is constrained when load exceeds `constrained_loading` x (firm capacity + counted flexible headroom); the default 1.0 follows Dominion's grid utilization filing (SCC PUR-2026-00164). That filing's measured distribution (79.8% mean planning utilisation, 4.3% of feeders above 100%) sets the bands for Dominion and, as a `_VERIFY` proxy, for the other utilities.

**Published-plan BAU (`forward_assumptions['bau_plan']['params']`, default).** BAU distribution capex follows the utility's published capital plan (`plan_years`, `plan_dist_capex_m`: Con Edison 10-K 2026-2030; RG&E Case 25-E-0379 proposal 2026-2031 (2028-31 equal split of the $5.06B total); Dominion Q4 2025 slides; Pepco Exelon Q4 2025 slides x 46.3% MD share). Beyond the plan, `beyond_path` 'continue' (plan CAGR; RG&E `plan_cagr_override` 0%, its 2028-31 years are flat), 'taper' (central: to nominal network peak growth by `taper_year`, 2032 / 2035 / 2040) or 'policy' (high electrification). `category_shares` growth / replacement / gridmod / other; `addressable_*` shares (growth 0.5/0.8/1.0 capped by the network model's deferrable share; replacement 0.10/0.20/0.30; gridmod 0/0.05/0.10; other 0; ramp over `addressable_ramp_years` from the transition year; scenario levels Cautious low, Ambitious high); applied only with deferral on. PJM transmission line follows `transmission_plan_rate_base_m` per MW of peak, then tapers to `transmission_growth`. The network model no longer generates BAU capex in this basis; `basis: 'model'` restores it and reproduces 23fec60 exactly (`tests/fixtures/layers_23fec60_model_bau.json`, with Con Edison's and RG&E's data-centre growth at their earlier 6% and 5%, and electrification pace 'state_policy': `DATA_SINCE_7C9B`, `MODEL_BAU` in the tests). Con Edison's layered `system_needs.dc_growth` is 0 / 0 / 6% (CECONY 0.7%/yr peak forecast; Zone J flat in the Gold Book); the earlier model's 6% is unchanged. Dominion and Pepco category splits are New York proxies. 2026 RR is recalibrated with the plan's 2026 capex. `link_growth_to_load` (setting, central true) scales plan-year growth capex by (model peak_t/peak_2026 - 1) / ((1 + `plan_load_growth`)^t - 1) (Con Edison 0.7% 10-K; Pepco 0.33% Ten-Year Plan; Dominion 1.88% DOM LSE Company Load Forecast, 2025 IRP Update; RG&E 3.03% Gold Book Zone B, proxy). `electrification_pace` 'utility_forecast' (central) calibrates BAU load to `plan_load_growth` over the plan years (`calibrate_load()`: electrification multiplier >= 0, then baseline), so the scale factor is 1.0 at plan end; 'state_policy' = the model's electrification. `electrification_pace_table()` reports both and the additional opportunity; categories carried forward separately after the plan; false = plan fixed. `system_needs.dc_growth` may be a rate or {year: MW added since 2026} (RG&E: Gold Book Zone B large loads x 57% zone share). Capacity: `published_prices` (PJM 2027/28 cap) in plan basis; `price_path` 'long_run' sensitivity to the long-run Net CONE by `long_run_year` 2040. `engine.layers.plan_paths()`.

**Network block (`forward_assumptions['network']['params']`).** Every existing-headroom input, each with `source`, `as_of`, `status` (`sourced` / `derived` / `_VERIFY`; on/off switches and mode choices are `setting`):

| Input | Default | Meaning |
|---|---|---|
| `band_mode` | `'explicit'` | `'explicit'` = `bands`; `'generated'` = `n_bands` equal-capacity bands spread linearly by `utilisation_spread` around `mean_utilisation` |
| `bands`, `n_bands`, `utilisation_spread` | Dominion quintiles; 5; 0.37 | Band definition |
| `mean_utilisation` | `null` | Capacity-weighted mean starting planning utilisation. `null` = bands as given; a number shifts every band by one amount to that mean, each capped at 1.0 |
| `planning_limit_factor`, `operating_limit` | 0.80; `null` | Planning capacity = 0.80 x rating (Dominion Metric iv). Operating limit = 1 / factor (1.25) unless set; existing load is served up to it |
| `subband_enabled`, `subband_load_share`, `subband_utilisation` | `true`; 0.043; 1.125 | Constrained sub-band (below). Per-utility switch, on in every scenario; a scenario's `network` values or `NETWORK_OVERRIDES` can switch it off |
| `upgrade_delay_ordinary_years`, `upgrade_delay_large_years` | 0.5 / 1.5 / 3.0; Con Edison 2 / 3 / 6, Dominion 4 / 6 / 7 (low / central / high) | Upgrade Delay for Interconnection in constrained areas, years from request to connection: ordinary new load (EVs, heat pumps, small business) and large loads (distribution-connected data centres, fleet hubs). Con Edison E-Mobility Interconnection Guide (Apr 2026); Dominion large-load queue application (PUR-2026-00011). Others `_VERIFY` (proxy) |
| `backlog_clearance_pct` | 0.06 / 0.20 / 0.33 | Share of the outstanding constrained backlog cleared per year (`_VERIFY`; low from Dominion's large-load queue) |
| `constrained_build_priority` | `true` | Constrained-area upgrades are not capped by `max_build_pct`; `false` caps backlog clearance plus new-load upgrades together |
| `planning_headroom`, `reinforcement_lead_years`, `max_build_pct` | 0.10; 3; 3.5% (low/central/high) | Planning target, lead time, maximum build rate per band per year |
| `seed_pipeline`, `seed_pipeline_years` | `'derived'`; `null` | Projects under way at 2026: the next lead-time years of growth with headroom (`seed_pipeline_years` overrides the years), `'none'`, or `[{year, mw}]` |
| `constrained_loading` | 1.0 | Threshold for the constrained-band count |
| `flex_targeting_enabled`, `flex_targeting_share` | `false`; 1.0 | Site flexible headroom first in bands above their planning limit, up to this share of headroom and never more than the load above the limit (derived mode) |

Older forward_assumptions without a `network` block are read from `system_needs` (`network_bands` -> `bands`). The `('system_needs', ...)` override keys for these inputs are now `('network', ...)` (e.g. `engine.report.TIGHT_NETWORK`).

**Override order** (highest wins): per-call arguments (`project_layers(..., network={...})`, used by the headroom sweep; `overrides={('network', p): ...}`, used by the tornado) > the notebook override `NETWORK_OVERRIDES` at the top of Section 13 (copied into `engine.layers.NETWORK_OVERRIDES`, so it applies to every run in that section and to the layered report section) > `scenarios[name]['network']` (value or low/central/high level; empty by default) > the JSON network block.

**Constrained sub-band.** On in every scenario. `subband_load_share` of network load at `subband_utilisation` is carved out of the most loaded bands; total load and capacity stay the same, so the system mean is unchanged. Existing (2026) load in every band is served up to the operating limit. Outputs: `above_planning_limit_mw` (served load above planning capacity plus counted headroom; Dominion's "constrained" basis) and `upgrade_wait_mw` (MW waiting for upgrade), reported separately (`constrained_table`). Bands that start at or below their planning limit follow the earlier rule exactly, so with the sub-band off every run reproduces 1b09e20.

**Upgrade Delay for Interconnection** (formerly the BAU queue and its clearance): the time a new customer in a constrained area waits for the grid upgrade before connecting. In constrained areas (bands that start above their planning limit, i.e. the sub-band) the delay inputs replace the reactive planner:
- The backlog above the planning limit is cleared at `backlog_clearance_pct` of the outstanding backlog per year, in service the following year.
- Capacity for new load is ordered on request and arrives after the upgrade delay. It is split between ordinary and large loads by the large-load share of network growth that year (distribution data-centre growth + `ev_hub_share` x EV peak); fractional years are split between the two whole years.
- With `constrained_build_priority` off, both are capped at `max_build_pct` x band capacity.
- New load in a constrained area also waits while the backlog there is not cleared.
- Without the three delay inputs the reactive planner applies there too.

The delay is measured, not assumed: by request year, first in first out across all bands. Columns `upgrade_delay_yr` (average years waited by the MW that waited, per request year), `upgrade_delay_mw_affected`, `upgrade_delay_mw_yr`, `upgrade_delay_mw_still_waiting_2050` (counted to the end of 2050), and `upgrade_delay_mw_yr_avoided` (BAU minus shared savings, per calendar year). The total MW-years equal the sum of MW waiting. `upgrade_delay_table()` gives them by year. `access_summary()` reports the BAU average per MW affected, the shared-savings average per MW affected and per MW affected in BAU (like-for-like), MW affected, and MW-years avoided. Renamed: `waiting_mw` -> `upgrade_wait_mw`, `delay_mw_yr_avoided` -> `upgrade_delay_mw_yr_avoided`; `avg_connection_delay_yr` is replaced by the `upgrade_delay_*` columns.

**Headroom sweep.** `headroom_sweep(uj, p)` runs Central with the mean starting utilisation at 60-100% in 5-point steps x sub-band share 0 / 2 / 4.3 / 8 / 15% x Upgrade Delay case (`DELAY_CASES`: short = low delays and high clearance, central, long = high delays and low clearance). It reports, per point: 2050 monthly saving; customer savings ($B, undiscounted and NPV 3%); wires capex deferred; MW connected sooner (peak year); Upgrade Delay for Interconnection (BAU and SS average, MW affected, MW-years avoided); connection cost avoided (`system_summary()` definitions). Customer savings = BAU minus shared savings of revenue requirement (net of shared savings earnings, including any ROE change) + program bill cost + capacity cost, plus efficiency energy at today's residential supply rate (applied to all classes, so it likely overstates the C&I value), plus the value-stream layers (wholesale energy, avoided transmission, avoided distribution losses), each reported as its own line. Efficiency energy is counted once. `engine.report.headroom_sweep_figure()` draws it in notebook Section 13 (4g, with the full table) and in the layered report section (2050 saving and customer savings against mean utilisation at the central delay case, plus MW-years of Upgrade Delay avoided against sub-band share for each delay case; table at a 4.3% sub-band share).

**Bills.** Each bill category is projected 2026-2050 in BAU and SHARED SAVINGS. Distribution lines follow the wires revenue requirement per kWh (2026 RR as in `delivery_rr_reconciliation()`, rate base decaying at `RATE_BASE_DECAY`). Core program costs and shared savings earnings are recovered per kWh with today's residential allocation of the core surcharges. Supply, transmission and program surcharges grow at their own rates, capacity follows zonal price x peak, and percentage taxes apply to their base lines.

Layers (each `enabled`, values low / central / high with `source`, `as_of`, `status`):
- `system_needs`: baseline, electrification (split 80% EVs / 20% buildings, NREL EFS), data centres, peak, growth vs asset-condition capex. Applies to both cases.
- `programs`: core-business surcharges leave the bill from `transition_year`. Flexible MW follow the target path, limited to a maximum annual growth per type (`ramp_pct_peak_*`, share of 2026 peak per year: Cautious 0.40% = Pepco direct load control 2009-2025 average, Central 1.37% = its fastest year, Ambitious no cap). Energy efficiency peak MW = first-year MWh x `ee_kw_per_mwh` (EmPOWER Maryland 2024 evaluated ratio; replaces `ee_peak_coincidence`, which the engine still reads if `ee_kw_per_mwh` is absent). Spend = today's surcharge-funded spend + incremental flexible MW by type (demand response, managed EV, storage, other DER: `mw_start_*` from each utility's programs, Central `mw_2035_*` / `mw_2050_*` anchored to state targets or studies, Ambitious = DOE 20% of peak) x cost per kW-year + energy efficiency. Flexible large-load connections (`flex_conn_*`, Duke Nicholas Institute) add headroom.
- `deferral`: flexible headroom (firm flexible MW x `locational_match` + flexible connections) counted by the network planner, so reinforcement is ordered later.
- `load_enabled`: where BAU leaves load waiting, headroom (up to `enable_share`) connects it sooner; extra kWh spread fixed wires costs, net of connection cost not covered by CIAC and incremental O&M. Its bill bar is the residential bill effect only: the benefit of faster connections goes to the customers being connected and is reported in the access block (MW connected sooner, Upgrade Delay for Interconnection BAU vs shared savings, MW affected and MW-years avoided, connection cost avoided by new customers at `customer_funded_share` x upgrade cost (upper bound 1.0), electrification GWh brought forward). MW connected sooner = load served above BAU served per band, so efficiency is not counted. Each MW of headroom has one use (deferral or load enabled); flexible-connection MW count once, as headroom, and are not credited as connection cost avoided. `uplift_mode` 'derived' or 'direct' (% what-if). Replaces the former utilisation layer, which double-counted with deferral (near-additive price discount not tied to any cost).
- `capacity`: capacity MW = peak − MW waiting − (firm flexible MW + EE MW, capacity layer on), at the zonal price; each EE MW counts once (RG&E: NYISO Rest of State in the layer engine only; Pepco's 2026 price equals its carve-out price).
- `wholesale_energy`: incremental flexible MW x MWh shifted per MW a year by type (`mwh_per_mw_*`: demand response and other DER = NYISO 2025 event-hours; managed EV and storage `_VERIFY`) x the on/off-peak spread (`spread_mwh`, PJM 2025 State of the Market; New York uses it as a `_VERIFY` proxy). Storage is net of round-trip losses (`storage_rte` 0.85, `offpeak_price_mwh`). Lowers the supply lines. Efficiency's lower energy purchases are already counted (lower usage; the efficiency energy line in `system_summary`), so they are not added here.
- `transmission`: firm flexible + efficiency peak MW x `cost_kw_yr` x `avoidable_share`: Con Edison and RG&E marginal transmission cost (BCA handbooks), Dominion and Pepco PJM NITS rates (June 2026; average embedded, so the avoidable share is 0 / 0.5 / 1.0, `_VERIFY`). `bill_basis` 'delivery' (New York: transmission is recovered in delivery rates) or 'transmission_lines'.
- `losses`: `avg_loss_pct` (Dominion 3.9% PUR-2026-00164; Con Edison 4.24% and RG&E 6.93% from their BCA handbooks; Pepco 4.92% EIA-861) x marginal multipliers (RAP 2011: energy 1.5, peak 3.0). The energy value counts only the part above the average losses already in retail rates (efficiency GWh x average loss x (multiplier - 1) at the supply rate). The peak value is MW x average loss x peak multiplier at the capacity price, which lowers the capacity line.
- Value layers have `in_pool` (setting, default true): their savings enter the shared-savings pool, like capacity.
- `mechanism`: utility share of the pool = shared savings earnings. One pool basis, `'revenue_requirement'` (the `'capex'` basis was removed; any other value raises an error).
- `roe`: allowed ROE in shared savings = BAU ROE + `roe_delta` from the transition year (low / central / high -60 / 0 / +60 basis points; Illinois CEJA performance metrics +/- 20 to 60 bp; Ameren Illinois +/- 24 bp). Changes the wires and program regulatory-asset return, the bill and `equity_return_m`. It stays outside the pool (`roe_in_pool` false), so shared savings earnings are unchanged. A separate lever.
- Older forward_assumptions carry `wholesale_energy` and `roe` as placeholders (`hook: true`); enabling those raises an error, and missing layers are off.
- Next candidates, not built and not on the bill when they are (report separately, like access): resilience, capacity price suppression, the economic value of faster connections, emissions.

Scenarios Cautious / Central / Ambitious (`forward_assumptions['scenarios']`) set programs, deferral and load_enabled together and hold growth and the utility share at central. Two bill measures: `avg_bill_total` (average residential bill; EE lowers usage; headline) and `bill_total` (benchmark usage). Outputs: `bill_table`, `scenario_table`, `waterfall`, `mw_table`, `mw_path_table` (target path vs ramp limit), `connection_table`, `constrained_table` (MW in constrained bands), `band_table`, `access_table`, `upgrade_delay_table`, `value_stack`, `flex_pays_cost` (cost at which flexibility pays for itself), `tornado` (on the saving), `cumulative_savings`, `earnings_table`, `system_summary` (system-wide customer savings with one line per value stream, capex, capacity, earnings, access), `layer_contributions` (each layer's customer savings $B undiscounted and NPV 3%, 2035 / 2050 bill, pool contribution, shared savings earnings attributable in proportion to pool contribution, equity return), `headroom_sweep`. They feed Section 13 of each state notebook and, via `engine.report.render_layered_section()`, a layered section in each HTML report. `tests/test_layers.py` checks: layers off = BAU; year zero = `starting_bill` total; 2026 BAU RR = rate-case target; moving programs into rates with no new resources is bill-neutral; flexible spend = MW x cost; EE lowers sales and the average bill; scenarios are ordered; headroom used never exceeds headroom created (one use per MW) and MW connected sooner never exceed load-enabled headroom; served load never exceeds demand or capacity plus headroom; with one band the engine reproduces the single-pool model exactly (`tests/fixtures/layers_single_pool_ebb0c04.json`: forward assumptions and outputs at commit ebb0c04); bands sum to the network totals; the ramp limit holds; access is zero with layers off. Network-block tests: the 1b09e20 JSON without a network block reproduces 1b09e20 exactly (`tests/fixtures/layers_1b09e20.json`), and so does the current JSON with the sub-band switched off and the value-stream and ROE layers disabled; the program-transfer neutrality test runs with the sub-band off (core programs are recovered per kWh served, so load waiting for an upgrade raises the shared-savings rider slightly); headroom used never exceeds headroom created with the sub-band and targeting on; served load never exceeds the operating limit plus headroom; Dominion at 100% starting utilisation with a 5-year lead gives a non-zero BAU queue; the sub-band gives MW waiting for upgrade in BAU and keeps total load and capacity; the sub-band is on in every scenario and a scenario's network values can switch it off; the mean shift hits its target; the override order; the sweep grid (MW-years avoided rise from short to long delay); the Upgrade Delay MW-years identity; with the backlog cleared at once BAU waits never exceed the input delay, and longer delays, slower clearance or no build-rate priority never shorten them; flexibility never lengthens the delay. Value-stream tests: each value layer adds customer savings and lowers the 2050 bill; layer contributions and the waterfall sum to the full case; the wholesale layer is zero without incremental flexible MW (efficiency is not double counted); the loss energy value is zero at a marginal multiplier of 1; the ROE lever moves the bill and equity return but not shared savings earnings, and is neutral at 0; avoided transmission lowers the delivery bill in New York and the transmission lines in PJM; placeholder layers in older JSON cannot be enabled. Fix tests: each EE MW counted once in capacity; Dominion DR excludes efficiency; flexible connections counted once; earnings attributed in proportion to the pool; efficiency not counted as connected sooner; the `'capex'` basis removed; settings labelled `setting`; Pepco's capacity prices aligned. Fixture columns renamed since they were written are mapped in the tests (`RENAMED`); the stored values are unchanged.

## `forward_assumptions` schema

```
forward_assumptions
  _note, as_of
  scenarios: {Cautious | Central | Ambitious:
      description, default_level, levels: {layer or 'layer.param': 'low'|'central'|'high'},
      network: {param: value or level}}             # scenario network values (empty = network block)
  projection: {inflation_rate, supply_energy_growth, transmission_growth, program_surcharge_growth}
  layers: {system_needs, programs, deferral, load_enabled, capacity, wholesale_energy, transmission,
           losses, mechanism, roe:
      enabled, label, _note, params: {name: spec}}
  network: {label, _note, params: {name: spec}}      # every existing-headroom input
  bau_plan: {label, _note, params: {name: spec}}     # published-plan BAU (basis, plan capex, paths, categories, addressable shares, transmission plan)
  capacity_carve_out                                  # where capacity is embedded in another bill line
  starting_adjustments                                # Pepco: Order No. 92607 +$3.94/month
```

A `spec` is either `{low, central, high, unit, source, as_of, status}` (a range; scenarios and the tornado pick levels) or `{value, unit, source, as_of, status}` (a single value or setting). `resolve()` flattens it to `{layer: {param: value}}` (network inputs under `'network'`). Older forward_assumptions without a `network` block are read from `system_needs`; older ones carry `wholesale_energy` and `roe` as placeholders (`hook: true`), which cannot be enabled; missing layers are off.

**Override order** (highest wins): per-call arguments (`network=`, `overrides=`) > notebook `NETWORK_OVERRIDES` (Section 13) > `scenarios[name]['network']` > scenario `levels` > the JSON value or central level.

## Starting-point bill (`starting_bill`) schema

Each utility JSON has a `starting_bill` section describing today's residential bill at `residential_kwh_month`, line by line. It is year zero of the layered model: `engine.layers.starting_lines()` reads it, applies `capacity_carve_out` and `starting_adjustments`, and projects each line. The earlier model does not read it.

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

## Earlier model (v1.0 and CORRECTED)

`engine/model.py` and Sections 1-12 of each state notebook; `GridDividend_v1.0.ipynb` is the self-contained original. Kept for reproducibility; new analysis uses the layered model.

### Key v1.0 parameters (Section 1)

Every parameter has a source citation in the comment block immediately below it. The most sensitive parameters:

- `UTILITY_SAVINGS_SHARE` — fraction of savings retained by utility (default 0.30)
- `NWS_AVOIDANCE_OF_ELIGIBLE_MATURE` — avoidance rate at programme maturity (default 0.80)
- `NWS_AVOIDANCE_RAMP_YEARS` — years to reach maturity (default 9)
- `FLEX_LOAD_UTILISATION_SHARE_SS` — utilisation credit for shared savings scenario (default 0.15)
- `DEFERRAL_FRACTION` — share of avoided CAPEX that eventually re-enters rate base (default 0.0 = permanent avoidance); 0.40–0.60 more realistic for dense urban networks long-term
- `DEFERRAL_PERIOD_YEARS` — years before deferred CAPEX re-enters rate base (default 10)
- `UPFRONT_PASSTHROUGH_YEARS` — years of 100% customer passthrough before standard split applies (default 0); set to 3 in the FRONTLOADED scenario
- `utilities_to_run` — list of utility keys to model (e.g. `['ConEd', 'RGE']` in the New York notebook)

### Savings pool basis (`SAVINGS_POOL_BASIS`)

`project()` supports two definitions of the annual shared-savings pool:

- `'capex'` (default; reproduces v1.0 results): pool = avoided CAPEX − NWS OPEX in the year of avoidance. The customer 70% is credited against that year's revenue requirement, and the avoided CAPEX also stays out of rate base. Customers therefore benefit from the same avoided dollar twice: once as a credit and again as years of lower return and property tax on a smaller rate base. The utility's 30% is not recovered from anyone. Treat headline savings under this basis as a likely upper bound.
- `'revenue_requirement'`: pool = annual reduction in delivery revenue requirement vs BAU (return + property tax on the avoided rate base) − NWS OPEX, computed from a paired BAU run. Customers receive the reduction through the lower rate base, with no extra credit. The utility's share is recovered in the delivery revenue requirement. The pool is negative in the first year or so (OPEX exceeds the RR reduction), and the split is applied symmetrically.

The ROE sweep (`engine/roe_sweep.py`, notebook Section 8b in the modular notebooks) runs both bases. `ROE_OVERRIDE` sets a per-run ROE and recomputes WACC. By default it also rebases the starting delivery bill (`ROE_OVERRIDE_REBASE_BILL`), because bills are indexed to each run's own first-year revenue requirement. `tests/test_regression.py` pins the default Con Edison BASE result; run it with `python -m pytest tests/`.

### Correction flags and the CORRECTED preset

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

### v1.0 notebook vs engine (reconciliation)

The "$12,907 per customer" Con Edison figure, formerly in `README.md` and a Section 9d code comment (both removed), was **stale**. It is the output of both code paths **before** commit 78f1a4f (segmented load model, 2026-07-25), which replaced the blended `dc_load_growth_annual` rate with a data-centre segment growing from its own MW base. At every commit since then, `GridDividend_v1.0.ipynb` and `engine/` both give **$12,423** (undiscounted nominal, BASE vs BAU), and the bills are bit-identical. The two paths do still differ, as follows:

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

Expected effect: identical bills. The v1.0 utility-side columns (and anything plotted from them) pick up the pass-through fix, and FRONTLOADED bills shift as in the table.

### `GridDividend_v1.0.ipynb` cell map

The self-contained v1.0 notebook (36 cells). Cell indices are 0-based (matching `nb['cells'][n]` in Python).

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

## What to be careful about

- **Not a forecast.** Direction and order of magnitude only.
- **About half the layered inputs are `_VERIFY`** (Con Edison 41%, Dominion 38%, Pepco 43%, RG&E 54% of status-tagged inputs; `docs/ASSUMPTIONS.md` has the counts). Network loading, upgrade delays for ordinary load and most MW paths use proxies for the utilities without their own data.
- **Spatially aggregate.** Loading bands approximate the network; real outcomes depend on feeder-level constraints and where flexibility is sited. Prefer published grid-utilization data wherever it exists (`_grid_utilization_VERIFY`).
- **Avoided transmission is a range** (PJM NITS is an average embedded cost), and **ROE is a separate lever** outside the pool.
- **RG&E data is provisional** until the final order in Case 25-E-0379. **Property tax rates are estimates.**
- **FRONTLOADED** (earlier model) is a timing mechanism: the utility earns 0% in years 1-3 and the 25-year outcome equals BASE.

## Coding conventions

- Earlier-model notebook parameters: `UPPER_SNAKE_CASE`, each with a source citation in the comment block below it. Engine functions: `lower_snake_case`.
- Utility data lives in `utilities/*.json`, not in notebook cells. Write JSON by replacing only the `forward_assumptions` block, so formatting and blank lines are kept.
- Match the surrounding code's comment density and idiom. New layered outputs go in `engine/layers.py` and are shown in Section 13 and `render_layered_section()`.

## Adding a utility

1. Create `utilities/[Name].json` from `TEMPLATE.json` (earlier-model fields). Add `starting_bill` and `forward_assumptions` following `Dominion_VA.json` or `Pepco_MD.json`, with a source, as-of date and status on every value.
2. Add `shared/capacity_markets/[MARKET].json` if the market is new.
3. Copy a state notebook, load the JSON in Section 0 and set `utilities_to_run`.
4. Run `python scripts/check_starting_bill.py`, then `python -m pytest tests/` (add the utility to `UTILS` in `tests/test_layers.py`). Add a regression pin once the results are reviewed.

## Open housekeeping items

These would change results, so they need a decision first:

- **v1.0 notebook sync.** `GridDividend_v1.0.ipynb` carries its own engine copy (proposal under "v1.0 notebook vs engine").
- **Dominion ACCELERATED / COMBINED shares.** These scenarios set absolute NWS eligibility (35% / 55%) calibrated to New York, above Dominion's 22% / 35%.
- **EV territory share.** Dominion uses the New York-calibrated `customers / 8,000,000`; Pepco sets `ev_territory_share`.
- **New York capacity cost.** The New York notebook hard-codes `CAPACITY_COST_START` instead of reading `shared/capacity_markets/NYISO.json`.
- **New York property tax.** `ConEd.json` and `RGE.json` lack `property_tax_rate`, so the notebook fallback (1.6% / 1.8%) applies.
- **Con Edison MFC.** The Merchant Function Charge averages Feb-Oct 2026. January 2026 is not parsed. Con Edison's November 2026 link still serves an Orange & Rockland statement (checked 31 Oct 2026).
- **Program-transfer neutrality with waiting load.** In shared savings, core programs are recovered per kWh served. Where load waits for an upgrade, the rider is slightly higher than the BAU surcharge (about $0.003/month at most).
- **Constrained-area build rate.** It is per band (3.5% of band capacity) unless `constrained_build_priority` is on.
