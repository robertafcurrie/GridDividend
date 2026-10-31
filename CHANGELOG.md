# Changelog

One entry per commit on `main`, newest first, from the commits pushed on 31 October 2026 onward (`629c355..`). Each entry says what changed and its effect on results.

"Earlier model" means v1.0 and the CORRECTED preset (`engine/model.py`, Sections 1–12, `GridDividend_v1.0.ipynb`). "Layered model" means `engine/layers.py` and Section 13. Unless stated, the three pinned v1.0 BASE results (Con Edison, Dominion, Pepco) are unchanged.

---

## 2026-10-31: Documentation and methodology pass (this commit)

**What changed**
- `docs/METHODOLOGY.md`: the full methodology of the layered model, for policy readers, with technical subsections:
  - purpose and framing;
  - structure and scenarios;
  - each layer (calculation, inputs, interactions, double counting, limitations);
  - outputs;
  - dollar bases;
  - data and status;
  - configuration;
  - validation;
  - the relationship to v1.0 and CORRECTED;
  - limitations and open questions;
  - a glossary.
- **Assumptions register:** `scripts/build_assumptions_register.py` generates `docs/assumptions_register.csv` (one row per input per utility) and `docs/ASSUMPTIONS.md` (status counts by utility and layer, then the inputs). The new `tests/test_assumptions_register.py` fails if either file is out of date with the JSON, or if a layered input lacks a valid status.
- **Per-utility data notes:** `docs/utilities/{ConEd,RGE,Dominion_VA,Pepco_MD}.md`.
- **HTML reports:** the layered section now opens with a methodology note. It links to `docs/METHODOLOGY.md` and `docs/ASSUMPTIONS.md` and states the scenario, dollar basis and savings-pool setting used, plus any notebook network override. A stale sentence saying the sub-band was off in Cautious and Ambitious is corrected. Reports regenerated.
- **Docstrings:** every public function in `engine/layers.py`, `engine/markets.py` and `engine/report.py` now states its inputs, outputs and units. The stale header comment in `engine/layers.py` (wholesale energy and ROE listed as disabled hooks) is updated.
- **Notebooks (text only):**
  - Section 13 text now matches METHODOLOGY.md.
  - The Section 10 caveats are scoped to the earlier model and point to METHODOLOGY.md for the layered model.
  - The time-value caveat now notes that NPVs are reported.
  - The stray "Section 11: Future Work" heading is renamed "Future Work".
  - The verification-count sentences in the Virginia and Maryland title cells no longer quote a stale number.
  - The New York Section 6 cumulative grid-spend figures are corrected to the computed values.
  - The Maryland Section 2 pointer is corrected to Section 12a.
- **README:** links to the new documents. Dominion's `_VERIFY` share is 44%. The register counts the capacity carve-out, which the earlier 43% left out.
- **CHANGELOG.md** (this file).
- **`.gitignore`:** `docs/` is narrowed to `docs/*.png`, so the new documents are tracked. The legacy chart images stay untracked.

**Effect on results:** none. No engine logic, default or input changed. Every test passes, including the three pins, and the regenerated notebooks give identical numeric outputs.

**Found, not changed** (each would change results): see METHODOLOGY.md section 10.2 and the independent check below.

**Independent check.** A separate agent compared METHODOLOGY.md with the code. Its findings, and how each was resolved, are listed under [Independent documentation check](#independent-documentation-check-2026-10-31) at the end of this file.

---

## 2026-10-31: `cf28849` Consolidation: README and CLAUDE.md rewritten; label-only housekeeping

**What changed**
- **README** rewritten around the layered model, opportunity first. Stale $12,907 / $52B figures removed.
- **CLAUDE.md** brought up to date.
- **Virginia notebook:** the verification table and the Section 2, 6, 9 and 9c text now describe Dominion.
- **Chart labels:**
  - Chart 6 threshold computed;
  - Chart 11 per-utility starting bill;
  - Chart 12 shading from FREEZE_PLUS, with a per-utility file name.
- **Con Edison:** the MFC note rechecked.

**Effect on results:** none. Notebook numeric outputs were identical.

## 2026-10-31: `af4583b` Layer engine: sub-band in every scenario; wholesale, transmission, losses and ROE layers

**What changed**
- The constrained sub-band is on in Cautious and Ambitious as well as Central.
- New layers:
  - wholesale energy (load shifting; PJM 2025 spreads, NYISO event-hours);
  - avoided transmission (BCA handbook marginal costs; PJM network service rates);
  - avoided distribution losses (utility loss rates, RAP multipliers);
  - an ROE lever, outside the pool.
- New `system_summary()` lines and `layer_contributions()`.

**Effect on results:** layered-model results rose in every scenario, from the value-stream layers and the sub-band in Cautious and Ambitious. The earlier model and the pins were unchanged. With the sub-band and new layers off, the 1b09e20 fixture still reproduces.

## 2026-10-31: `7fa9e30` Layer engine: sub-band on in Central; Upgrade Delay for Interconnection

**What changed**
- The constrained sub-band is on in Central for all four utilities.
- In constrained areas, the Upgrade Delay for Interconnection replaces the BAU queue:
  - delays for ordinary and large loads (Con Edison E-Mobility Interconnection Guide; Dominion PUR-2026-00011);
  - backlog clearance;
  - build-rate priority.
- The delay is measured per request year. Columns renamed: `waiting_mw` → `upgrade_wait_mw`, `delay_mw_yr_avoided` → `upgrade_delay_mw_yr_avoided`.

**Effect on results:** layered Central results changed (waiting load and the delay now appear in BAU). Cautious and Ambitious were unchanged. The earlier model and the pins were unchanged.

## 2026-10-31: `52f948a` Layer engine: network block, constrained sub-band, headroom sweep

**What changed**
- `forward_assumptions['network']` holds every headroom input, with an override order.
- Constrained sub-band (off by default at this commit); flexibility targeting.
- `headroom_sweep()` and `system_summary()`.

**Effect on results:** none at defaults. The 1b09e20 outputs reproduce exactly (fixture test).

## 2026-10-31: `1b09e20` Layer engine: loading bands, access block, MW ramp limits, efficiency re-sourced

**What changed**
- Network loading bands from Dominion's grid utilization filing (a proxy elsewhere).
- Access block, kept separate from the bill.
- MW ramp limits from Pepco direct load control history.
- Pepco demand response start: 247 MW.
- `ee_kw_per_mwh` from the EmPOWER 2024 evaluation; savings rates re-sourced for Pepco and Dominion.

**Effect on results:** layered-model results changed (bands, ramp limits, efficiency inputs). One band reproduces ebb0c04 exactly. The earlier model and the pins were unchanged.

## 2026-10-31: `ebb0c04` Layer engine: explicit network capacity, load-enabled layer, utility-specific MW, report section

**What changed**
- Explicit firm network capacity with reinforcement lead time and build rate.
- The load-enabled layer replaces the utilisation layer (which double counted with deferral).
- One use per MW of headroom.
- Flexible connections; utility-specific flexible MW paths.
- A layered section in the HTML reports.

**Effect on results:** layered-model results changed. The earlier model and the pins were unchanged.

## 2026-10-31: `1666535` Layer engine: link program spend to MW delivered; add EE, scenarios, value stack

**What changed**
- Program spend is now incremental MW x cost per kW-year plus efficiency, replacing a spend multiple.
- Average residential bill measure; Cautious / Central / Ambitious scenarios.
- Value stack and the cost at which flexibility pays for itself.
- Electrification split 80% EVs / 20% buildings.
- RG&E capacity at NYISO Rest of State (layered model only).

**Effect on results:** layered-model results changed. The earlier model and the pins were unchanged.

## 2026-10-31: `eb2c94d` Add layer engine (engine/layers.py), forward assumptions and Section 13

**What changed**
- New additive layered model.
- `forward_assumptions` added to each utility JSON.
- Section 13 added to each state notebook.

**Effect on results:** new layered results. Existing outputs were unchanged.

## 2026-10-31: `19a6cf7` Add starting-point bill breakdown (data only) and validation script

**What changed**
- `starting_bill` added to each utility JSON.
- `scripts/check_starting_bill.py`.

**Effect on results:** none (data only at this commit).

## 2026-10-31: `2d70a86` Refresh notebook outputs (outputs only, no code changes)

**Effect on results:** none. Saved outputs now match the code at e247fb4.

## 2026-10-30: `e247fb4` Use JSON NWS shares; add class allocation and inflation-linked capacity to CORRECTED

**What changed**
- **Bug fix:** `project()` uses a utility JSON's NWS eligible-capex shares when present.
- `CAPACITY_SAVINGS_ALLOCATION` option.
- CORRECTED adds sales-share allocation and inflation-linked capacity growth.

**Effect on results:**
- Dominion's default BASE saving changed from $12,371 to $11,641 per customer (undiscounted nominal), and its pin was updated to $11,640.53.
- New York and Pepco defaults were unchanged.
- CORRECTED outputs changed.

## 2026-10-30: `8379716` Add Pepco Maryland (Case 9820) via modular engine; PJM capacity file

**What changed**
- Pepco Maryland added: JSON, notebook, calibration worksheet.
- `shared/capacity_markets/PJM.json`.
- Engine options (EV territory share, data-centre step, per-utility capacity growth, pass-through share), all defaulting to existing behaviour.

**Effect on results:**
- New Pepco results, pinned at $1,725.09 per customer.
- New York and Virginia outputs were identical.

## 2026-10-30: `d10f329` Add savings-pool basis, correction flags, CORRECTED preset and ROE sweep

**What changed**
- `SAVINGS_POOL_BASIS`.
- Correction flags and the CORRECTED preset (not the default).
- `ROE_OVERRIDE` and the ROE sweep; `equity_earnings_m`.
- Con Edison BASE pin.

**Effect on results:** none at defaults. Text outputs and reports were identical.

---

## Independent documentation check (2026-10-31)

A separate agent that had not seen this work read `docs/METHODOLOGY.md` alongside `engine/layers.py`, `engine/model.py`, `engine/report.py`, the utility JSON and `tests/test_layers.py`. It found 29 items. It confirmed that the bands, both planners, the served-load rule, the rider, the RR build-up, the ROE lever, the value layers, the scenario levels and every quoted input value match the code.

Every documentation item was fixed in METHODOLOGY.md, without code changes. Items where the code itself looks wrong were documented and left unchanged, because fixing them would change results.

**Code looks wrong (documented, not changed):**

| # | Finding | Resolution |
|---|---|---|
| F1 | "Earnings attributable" depends on layer order. Carry-forward gives programs, deferral and load enabled zero, and Con Edison attributes $1.95B to capacity | METHODOLOGY 3.10 and 10.2, report caption, CLAUDE.md open item |
| F2 | Load enabled is a small net cost system-wide (Central: Con Edison −$65M, Dominion −$156M) | Documented as intended (the benefit is in the access block): METHODOLOGY 3.5 |
| F3 | Flexible-connection MW are deferral headroom and also, in full, connection cost avoided. They are about 90% of that measure ($705M vs $67M without, Con Edison) | METHODOLOGY 4.5 and 10.2, CLAUDE.md open item. Presentation only |
| F4 | Efficiency in waiting bands counts as MW connected sooner and attracts connection capex | METHODOLOGY 3.5, 4.5 and 10.2, CLAUDE.md. Small |
| F5 | The efficiency capacity triple count (found in this pass) also raises the pool, earnings and the capacity bill line. The share is 14–25% of customer savings, not 19–25% (RG&E 14%) | METHODOLOGY 3.6 and 10.2 corrected |
| F6 | The `'capex'` pool basis (unused) gives customers the capacity and value streams about 1.7 times over | METHODOLOGY 3.10 and 10.2 |
| F7 | Six inputs are tagged `sourced` or `_VERIFY` although their sources say "Setting" | METHODOLOGY 10.2, CLAUDE.md. JSON not changed (it would change status counts) |
| F8 | Pepco's carve-out (2026/27) and capacity layer (2027/28) use different year-zero prices | METHODOLOGY 3.6, Pepco note |

**Documentation disagreed with the code (fixed in METHODOLOGY.md):**

| # | Fix |
|---|---|
| F9 | Customer savings has three parts; the ROE change is inside delivery and shown for information (4.2) |
| F10 | MW connected sooner is the sum over bands of max(0, BAU − SS) (4.5, glossary) |
| F11 | Dominion's ordinary-load delay is a proxy too (3.3) |
| F12 | Override order: `network=` > `overrides=` (7) |
| F13 | The `'capex'` formula includes the value streams (3.10) |
| F14 | `flex_pays_cost` targets are alternative modes, on the per-customer average bill (4.3) |
| F15 | A constrained area is the sub-band with the delay inputs set (3.3, glossary) |
| F16 | Seven test descriptions corrected to what each test checks (8) |

**Calculations not documented (now documented in METHODOLOGY.md):**

| # | Now documented |
|---|---|
| F17 | New load in a constrained area waits until capacity passes existing load (3.3) |
| F18 | Waiting MW are converted to unsold GWh at the system load factor (3.3) |
| F19 | Flexibility targeting rule (3.5) |
| F20 | Delay cohort edge cases (3.3) |
| F21 | Connection capex is charged only above the running maximum; O&M on the stock (3.5) |
| F22 | `spend0` for per-month lines (3.4) |
| F23 | Starting adjustments are volumetric by default (3.1) |
| F24 | Generated bands centre on the explicit mean when `mean_utilisation` is null (3.3) |
| F25 | Everything the programs level moves in a scenario (2.4) |
| F26 | Behaviour with system needs off (3.2) |
| F27 | Value layers need programs active; their firm MW include efficiency (3.7) |
| F28 | Why the loss peak value uses the full multiplier (3.9) |
| F29 | Conditions for the 2026 RR match (4.1) |
