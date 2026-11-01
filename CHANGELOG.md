# Changelog

One entry per commit on `main`, newest first, from the commits pushed on 31 October 2026 onward (`629c355..`). Each entry says what changed and its effect on results.

"Earlier model" means v1.0 and the CORRECTED preset (`engine/model.py`, Sections 1–12, `GridDividend_v1.0.ipynb`). "Layered model" means `engine/layers.py` and Section 13. Unless stated, the three pinned v1.0 BASE results (Con Edison, Dominion, Pepco) are unchanged.

---

## 2026-11-01: Central BAU load follows each utility's forecast; electrification pace (this commit)

**What changed** (layered model only; v1.0, CORRECTED and the three pins unchanged):

1. **Central BAU load is calibrated to the forecast behind each plan.** New setting `bau_plan.electrification_pace`:
   - **`utility_forecast` (central):** electrification growth is scaled by a multiplier of 0 or more (and, if needed, baseline growth is lowered) so that the model's system peak over the plan years equals the plan's forecast (`engine.layers.calibrate_load`).
     - Con Edison 0.7%/yr: electrification × 0.32.
     - Pepco 0.33%/yr: × 0.36.
     - Dominion 1.88%/yr: × 0.47.
     - RG&E 3.03%/yr: electrification 0, baseline −1.7%/yr.
   - **`state_policy`:** the model's earlier electrification assumptions.
2. **Dominion's forecast** is now its own 2025 Company Load Forecast for the DOM LSE (2025 IRP Update, Figure 2.1.9): 18,470 MW (2026) to 19,898 MW (2030), 1.88%/yr.
   - It excludes the co-operative Residual DOM Zone (7.4%/yr), which inflates PJM's 5.4% zone forecast.
   - **Flag:** no distribution-level forecast excluding transmission-connected large loads was found (the grid utilization filing reports current loading only). The LSE forecast includes Dominion-served data centres, so it is compared with the model's system peak, which also includes all data-centre load.
3. **Scale factors.** Before (state-policy load): Con Edison 1.82, RG&E 1.69, Dominion 0.44 (against 5.4%), Pepco 2.61 at plan end. Now:
   - Con Edison and Pepco: 1.00 throughout the plan years.
   - Dominion: 0.99–1.00.
   - RG&E: 0–1.36 within the plan and 1.00 at 2031. The Gold Book large loads arrive in steps, while the plan assumption is a constant rate.
4. **New: `electrification_pace_table()`** runs every scenario under both paces and reports the additional opportunity if electrification follows state policy.
5. **Tests:** two new tests (209 in total). The BAU-queue mechanism test runs at state-policy pace; the pinned-output tests use the state-policy pace.
6. **Updated:** METHODOLOGY (2.5, 3.3a, 8, 10, glossary), README (headline table and the electrification-pace table), the assumptions register, utility notes, CLAUDE.md, notebooks and reports.

**Effect on results** (central = utility-forecast pace, before = 17894ab):

| Utility | Scenario | BAU bill 2035 / 2050, $/month | Customer savings $B undiscounted | 2035 saving $/month | 2050 saving $/month | Shared savings earnings $B |
|---|---|---|---|---|---|---|
| Con Edison | Cautious | 406 / 783 → 358 / 653 | 14.30 → **11.81** | 5.17 → 4.75 | 31.63 → **27.74** | 4.42 → 3.46 |
| Con Edison | Central | 406 / 783 → 358 / 653 | 49.46 → **37.85** | 17.75 → 16.13 | 125.09 → **105.69** | 17.79 → 13.01 |
| Con Edison | Ambitious | 406 / 783 → 358 / 653 | 86.12 → **56.78** | 29.88 → 24.52 | 209.07 → **139.53** | 30.09 → 17.92 |
| Dominion | Cautious | 232 / 317 → 241 / 334 | 5.13 → **6.04** | 2.64 → 2.77 | 4.61 → **5.60** | 0.06 → 0.38 |
| Dominion | Central | 232 / 317 → 241 / 334 | 16.40 → **19.31** | 6.19 → 6.64 | 12.59 → **15.79** | 2.68 → 4.12 |
| Dominion | Ambitious | 232 / 317 → 241 / 334 | 42.81 → **47.07** | 14.70 → 15.54 | 30.45 → **36.69** | 9.10 → 11.35 |
| Pepco | Cautious | 308 / 443 → 303 / 432 | 2.62 → **2.29** | 6.54 → 6.65 | 12.67 → **11.75** | 0.09 → 0.03 |
| Pepco | Central | 308 / 443 → 303 / 432 | 5.04 → **4.35** | 11.09 → 11.01 | 27.26 → **24.31** | 0.64 → 0.43 |
| Pepco | Ambitious | 308 / 443 → 303 / 432 | 7.16 → **6.07** | 14.71 → 14.55 | 39.80 → **33.15** | 1.26 → 0.90 |
| RG&E | Cautious | 287 / 561 → 292 / 580 | 2.07 → **1.53** | 4.06 → 4.46 | 17.00 → **14.17** | 0.65 → 0.46 |
| RG&E | Central | 287 / 561 → 292 / 580 | 6.12 → **3.80** | 10.14 → 10.88 | 61.09 → **37.56** | 2.15 → 1.23 |
| RG&E | Ambitious | 287 / 561 → 292 / 580 | 9.57 → **6.17** | 16.95 → 16.54 | 86.92 → **55.13** | 3.15 → 1.85 |

- **The opportunity on utilities' own forecasts:** Central customer savings $37.8B (Con Edison), $19.3B (Dominion), $4.4B (Pepco), $3.8B (RG&E).
- **Dominion rises,** because its own LSE forecast (1.88%) replaced PJM's zone forecast (5.4%) as the plan's assumption, so its growth capex is no longer scaled down.
- **The others fall from the state-policy figures,** because their own forecasts grow load more slowly.

**Additional opportunity if electrification follows state policy:**

| Utility | Scenario | Customer savings $B: utility forecast / state policy (additional) | NPV 3% $B | 2035 saving $/month | 2050 saving $/month | Shared savings earnings $B |
|---|---|---|---|---|---|---|
| Con Edison | Cautious | 11.81 / 14.30 (**+2.48**) | 7.08 / 8.51 | 4.75 / 5.17 | 27.74 / 31.63 | 3.46 / 4.42 |
| Con Edison | Central | 37.85 / 49.46 (**+11.61**) | 22.40 / 29.10 | 16.13 / 17.75 | 105.69 / 125.09 | 13.01 / 17.79 |
| Con Edison | Ambitious | 56.78 / 86.12 (**+29.34**) | 33.94 / 50.73 | 24.52 / 29.88 | 139.53 / 209.07 | 17.92 / 30.09 |
| Dominion | Cautious | 6.04 / 6.34 (**+0.29**) | 3.74 / 3.91 | 2.77 / 2.71 | 5.60 / 5.46 | 0.38 / 0.41 |
| Dominion | Central | 19.31 / 20.26 (**+0.95**) | 11.76 / 12.31 | 6.64 / 6.49 | 15.79 / 15.53 | 4.12 / 4.33 |
| Dominion | Ambitious | 47.07 / 52.76 (**+5.69**) | 28.74 / 32.01 | 15.54 / 15.46 | 36.69 / 38.35 | 11.35 / 13.37 |
| Pepco | Cautious | 2.29 / 2.62 (**+0.33**) | 1.46 / 1.65 | 6.65 / 6.54 | 11.75 / 12.67 | 0.03 / 0.09 |
| Pepco | Central | 4.35 / 5.04 (**+0.69**) | 2.73 / 3.13 | 11.01 / 11.09 | 24.31 / 27.26 | 0.43 / 0.64 |
| Pepco | Ambitious | 6.07 / 7.16 (**+1.08**) | 3.80 / 4.42 | 14.55 / 14.71 | 33.15 / 39.80 | 0.90 / 1.26 |
| RG&E | Cautious | 1.53 / 2.07 (**+0.53**) | 0.95 / 1.25 | 4.46 / 4.06 | 14.17 / 17.00 | 0.46 / 0.65 |
| RG&E | Central | 3.80 / 6.12 (**+2.32**) | 2.33 / 3.63 | 10.88 / 10.14 | 37.56 / 61.09 | 1.23 / 2.15 |
| RG&E | Ambitious | 6.17 / 9.57 (**+3.40**) | 3.80 / 5.72 | 16.54 / 16.95 | 55.13 / 86.92 | 1.85 / 3.15 |

- **Con Edison has the most to gain:** +$11.6B at Central, +$29.3B at Ambitious.
- **Dominion's 2050 per-customer saving is slightly lower at state-policy pace** ($15.53 vs $15.79), even though total savings rise (+$1.0B): the extra load spreads costs over more kWh.

**Tornado note.** Under the calibrated pace, Con Edison's data-centre high case (6%/yr) tops the tornado (swing $50/month in 2050). In the plan years the calibration offsets it with zero electrification and lower baseline growth, but after 2030 the extra data-centre growth carries on on top of the reduced rates. Read it as "data centres grow while the utility forecast holds".

---

## 2026-11-01: `17894ab` RG&E data centres from the Gold Book; plan growth capex linked to load

**What changed** (layered model only; v1.0, CORRECTED and the three pins unchanged):

1. **RG&E data-centre growth.** Central is now the NYISO 2026 Gold Book view for Zone B (Table I-14 large loads: +150 / 280 / 400 MW by 2028 / 2029 / 2030, then flat), allocated by RG&E's share of the Zone B peak (1,050 / 1,828 MW = 57.4%). That is +86 / 161 / 230 MW on the 300 MW starting estimate.
   - The full-zone increment is an upper bound, because Zone B also covers National Grid's Genesee territory.
   - The unsourced 5% a year is kept as the high case; low is 0%.
   - `dc_growth` can now be a rate or a {year: MW added} path (`engine.layers.dc_path`).
2. **Plan growth capex linked to load.** New setting `bau_plan.link_growth_to_load`, central on.
   - Each plan's assumed load growth is recorded in `plan_load_growth`:
     - Con Edison 0.7% a year: its 10-K forecast, used for capital planning;
     - Pepco 0.33%: Maryland Ten-Year Plan;
     - Dominion 5.4%: PJM 2026 DOM zone forecast (proxy, `_VERIFY`);
     - RG&E 3.03%: Gold Book Zone B 2026–2031 (proxy, `_VERIFY`).
   - In the plan years, the growth-driven category is scaled by (model peak_t / peak_2026 − 1) / ((1 + plan_load_growth)^t − 1). After the plan, each category is carried forward at the path's growth rate. Replacement, grid modernisation and other stay on plan.
   - `false` keeps plan capex fixed regardless of load.
   - Scale factors in the last plan year: Con Edison 1.82, RG&E 1.69, Dominion 0.44, Pepco 2.61.
3. **Tests:** two new tests (204 in total). The pinned-output tests run RG&E at its earlier 5%.
4. **Updated:** METHODOLOGY (2.5, 3.2, 3.3a, 7, 8, glossary), README, the assumptions register (`_VERIFY` shares: Con Edison 41%, Dominion 38%, Pepco 43%, RG&E 54%), utility notes, CLAUDE.md, notebooks and reports.

**RG&E's BAU uses the company's filed proposal in Case 25-E-0379 pending the final order.** Staff recommended $226.3M and $246.1M of electric capital for 2026–27 against $308.4M and $420.6M proposed; the BAU and the savings should be revisited when the order issues.

**Effect on results.** The opportunity grows where the model's load outpaces the utility's own forecast, and shrinks for Dominion:
- **Con Edison:** the model grows peak 1.26% a year against Con Edison's 0.7%, mainly through electrification, so growth-driven plan capex scales up and BAU spends more. Central customer savings $34.9B → $49.5B; 2050 saving $82.01 → $125.09/month.
- **Dominion:** PJM's 5.4% zone forecast includes transmission-connected data centres the distribution model does not carry, so BAU growth capex scales down. $18.8B → $16.4B.
- **Pepco:** $4.6B → $5.0B.
- **RG&E:** the Gold Book data-centre path alone takes it to $4.99B; with the link, $6.12B.

Arrows run before → after; for RG&E, the middle value is the Gold Book data-centre change alone:

| Utility | Scenario | BAU bill 2035 / 2050, $/month | Customer savings $B undiscounted | 2035 saving $/month | 2050 saving $/month | Shared savings earnings $B | BAU capex 2026–2050 $B |
|---|---|---|---|---|---|---|---|
| Con Edison | Cautious | 348 / 620 → 406 / 783 | 10.59 → **14.30** | 4.36 → 5.17 | 21.52 → **31.63** | 2.83 → 4.42 | 230.7 → 323.5 |
| Con Edison | Central | 348 / 620 → 406 / 783 | 34.92 → **49.46** | 14.46 → 17.75 | 82.01 → **125.09** | 11.56 → 17.79 | 230.7 → 323.5 |
| Con Edison | Ambitious | 348 / 620 → 406 / 783 | 62.33 → **86.12** | 24.50 → 29.88 | 136.44 → **209.07** | 19.89 → 30.09 | 230.7 → 323.5 |
| Dominion | Cautious | 238 / 330 → 232 / 317 | 5.94 → **5.13** | 2.69 → 2.64 | 5.18 → **4.61** | 0.23 → 0.06 | 84.9 → 61.7 |
| Dominion | Central | 238 / 330 → 232 / 317 | 18.85 → **16.40** | 6.38 → 6.19 | 14.45 → **12.59** | 3.73 → 2.68 | 84.9 → 61.7 |
| Dominion | Ambitious | 238 / 330 → 232 / 317 | 49.13 → **42.81** | 15.18 → 14.70 | 35.46 → **30.45** | 11.81 → 9.10 | 84.9 → 61.7 |
| Pepco | Cautious | 298 / 419 → 308 / 443 | 2.35 → **2.62** | 6.40 → 6.54 | 10.43 → **12.67** | 0.03 → 0.09 | 8.0 → 11.2 |
| Pepco | Central | 298 / 419 → 308 / 443 | 4.58 → **5.04** | 10.76 → 11.09 | 23.05 → **27.26** | 0.44 → 0.64 | 8.0 → 11.2 |
| Pepco | Ambitious | 298 / 419 → 308 / 443 | 6.47 → **7.16** | 14.23 → 14.71 | 32.87 → **39.80** | 0.97 → 1.26 | 8.0 → 11.2 |
| RG&E | Cautious | 278 / 424 → 267 / 507 → 287 / 561 | 1.97 → 1.86 → **2.07** | 4.18 → 3.95 → 4.06 | 12.48 → 14.71 → **17.00** | 0.60 → 0.56 → 0.65 | 35.9 → 34.0 → 40.0 |
| RG&E | Central | 278 / 424 → 267 / 507 → 287 / 561 | 5.50 → 4.99 → **6.12** | 10.24 → 9.23 → 10.14 | 39.97 → 46.02 → **61.09** | 1.88 → 1.67 → 2.15 | 35.9 → 34.0 → 40.0 |
| RG&E | Ambitious | 278 / 424 → 267 / 507 → 287 / 561 | 8.90 → 8.11 → **9.57** | 16.12 → 15.46 → 16.95 | 62.06 → 68.09 → **86.92** | 2.84 → 2.53 → 3.15 | 35.9 → 34.0 → 40.0 |

**Tornado: data-centre and baseline growth rows** (2050 saving, $/month):

| Utility | Row | Before: low / high change in 2050 saving, $/month (swing) | After: low / high (swing), rank |
|---|---|---|---|
| Con Edison | Data-centre growth | +0.0 / -19.3 (19.3) | +0.0 / +16.7 (16.7), #8 |
| Con Edison | Baseline growth | +16.4 / -11.4 (27.8) | -13.4 / +7.3 (20.7), #7 |
| Dominion | Data-centre growth | +2.9 / -3.2 (6.1) | +1.3 / -2.1 (3.3), #2 |
| Dominion | Baseline growth | +0.7 / -0.6 (1.2) | +0.1 / -0.2 (0.3), #26 |
| Pepco | Data-centre growth | +0.2 / -0.7 (0.9) | +0.0 / -0.6 (0.6), #23 |
| Pepco | Baseline growth | +1.4 / -1.1 (2.5) | -2.4 / +0.8 (3.3), #8 |
| RG&E | Data-centre growth | +21.8 / +0.0 (21.8) | -21.7 / -24.7 (3.0), #15 |
| RG&E | Baseline growth | +2.9 / -2.5 (5.4) | -2.2 / -1.4 (0.8), #33 |

With plan capex fixed, more load lowered the per-customer saving: fixed costs were spread over more kWh. Linked, more load also means more growth spending to defer, so the two effects largely offset, and the rows shrink or change sign.

Top three drivers after: Con Edison: ee_incremental_savings_pct (51.5), locational_match (47.9), reinforcement_lead_years (32.9); Dominion: ee_incremental_savings_pct (14.6), dc_growth (3.3), supply_energy_growth (3.3); Pepco: ee_incremental_savings_pct (10.2), supply_energy_growth (9.1), ee_levelised_cost_kwh (5.4); RG&E: addressable_replacement (23.6), reinforcement_lead_years (20.4), utility_share (18.7). The reinforcement lead time now ranks high for Con Edison and RG&E, because it governs how much of the growth-driven spending the network model finds deferrable.

---

## 2026-10-31: `94992aa` Verification of published-plan BAU inputs

**What changed** (layered model only; v1.0, CORRECTED and the three pins unchanged):

1. **Con Edison data-centre growth corrected:** central 0% (low 0%, high 6%), was 6% a year (unsourced).
   - Con Edison forecasts CECONY peak growth of about 0.7% a year for 2026–2030 and cites data centres only for O&R (2025 Form 10-K).
   - The NYISO 2026 Gold Book update has Zone J essentially flat (10,847 MW vs 10,824 MW); large-load growth is upstate in Zone D (+276 MW).
   - The earlier model's 6% and the 1,500 MW starting estimate are unchanged (pins).
2. **RG&E plan replaced** with its Case 25-E-0379 proposal for 2026–2031:
   - $308.4M (2026) and $420.6M (2027), as cited by Staff;
   - $5.06B 2026–2031 total from the rebuttal testimony, with 2028–2031 as an equal split;
   - net of hydro, plus common capital: $351.0M, $458.3M, then $1,091.4M a year;
   - plan growth rate beyond 2031: 0%.

   This replaces the single 2026 year and the Con Edison 7.2% proxy. Staff recommended $226.3M and $246.1M for 2026–27; the final order is pending.
3. **Pepco transmission:** Exelon publishes transmission rate base only company-wide (+15.3% a year, 2025–2029) and PJM RTEP gives projects, not a rate base path. The derived path stays central, with the range documented (below).
4. **Proxy flag:** README and METHODOLOGY now state that Dominion's and Pepco's capex category splits are New York proxies.
5. **Long-run capacity source added:** Brattle for NY DPS and NYSERDA (Jan 2025, Case 24-E-0165), as reported by Utility Dive (5 Feb 2025): avoided generation capacity cost above $200/kW-year in 2040 from NREL data. It sits alongside the NYISO market monitor and Brattle PJM CONE sources; the value is unchanged.

**Tests:** two new tests (199 in total). The pinned-output tests run Con Edison at its earlier 6% (`DATA_SINCE_7C9B`), so they still reproduce exactly.

**Effect on results** (published-plan BAU):

| Utility | Scenario | Customer savings $B undiscounted | NPV 3% | 2035 bill lower $/mo | 2050 bill lower $/mo | % of BAU delivery bill 2050 | Shared savings earnings $B | BAU bill 2050 $/mo | BAU capex 2026–2050 $B |
|---|---|---|---|---|---|---|---|---|---|
| Con Edison | Cautious | 11.13 → **10.59** | 6.69 → 6.38 | 4.03 → 4.36 | 16.87 → **21.52** | 4.8% → 4.7% | 2.82 → 2.83 | 500 → 620 | 234.6 → 230.7 |
| Con Edison | Central | 36.24 → **34.92** | 21.52 → 20.77 | 13.36 → 14.46 | 62.72 → **82.01** | 18.0% → 17.8% | 11.63 → 11.56 | 500 → 620 | 234.6 → 230.7 |
| Con Edison | Ambitious | 65.94 → **62.33** | 39.21 → 37.14 | 22.99 → 24.50 | 106.23 → **136.44** | 30.5% → 29.7% | 20.46 → 19.89 | 500 → 620 | 234.6 → 230.7 |
| RG&E | Cautious | 1.20 → **1.97** | 0.73 → 1.19 | 2.53 → 4.18 | 7.13 → **12.48** | 4.0% → 4.3% | 0.27 → 0.60 | 308 → 424 | 18.6 → 35.9 |
| RG&E | Central | 3.28 → **5.50** | 1.96 → 3.27 | 6.04 → 10.24 | 22.17 → **39.97** | 12.3% → 13.7% | 0.92 → 1.88 | 308 → 424 | 18.6 → 35.9 |
| RG&E | Ambitious | 5.69 → **8.90** | 3.41 → 5.30 | 10.22 → 16.12 | 36.52 → **62.06** | 20.3% → 21.2% | 1.47 → 2.84 | 308 → 424 | 18.6 → 35.9 |

- **Con Edison's monthly saving rises, while its system-wide savings fall slightly.**
  - With no data-centre growth, there are fewer kWh to spread the plan's fixed capex over, so the BAU bill per residential customer is higher ($620 vs $500 in 2050) and so is the saving.
  - Total avoided dollars are a little lower, because there is less load growth to defer after the taper.
  - On the model basis, Con Edison Central customer savings move from $14.4B to $12.7B.
- **RG&E's opportunity grows with its much larger filed capital programme:** BAU capex 2026–2050 is $35.9B vs $18.6B.

**Con Edison 2050 saving decomposed (Central, $82.01/month):**
- **By layer:** deferral −$83.24, capacity −$9.28, transmission −$3.85, losses −$1.27, wholesale −$0.43; offset by programs +$5.44, the mechanism (shared savings earnings) +$10.09 and load enabled +$0.54.
- **By capex category (2050 avoided capex $3.57B):** growth $2.80B (78%), replacement $0.61B (17%), grid modernisation $0.17B (5%). Cumulative 2026–2050: $32.1B, $9.0B and $2.5B.
- **Why the 2035 → 2050 jump ($14.46 → $82.01):** three effects compound. The network model's deferrable share of growth capex rises from 18% to 39% as flexible MW build up; plan capex grows from $8.1B to $14.2B a year; and avoided capex stays out of rate base, so the rate-base gap grows from $4.1B to $34.3B and the wires revenue-requirement gap from $0.5B to $4.3B a year.
- **Why data centres were the top driver in New York City:** at 6% a year from 1,500 MW, data-centre load reached about 6 GW (30% of peak) and a third of sales by 2050. That spread fixed costs and savings over many more kWh, and it lowered the deferrable share. With the corrected 0%, data-centre growth falls to fifth; the top drivers are efficiency ambition, baseline growth, locational match and electrification.

**Pepco transmission range** (BAU bill / saving in 2050, $/month):

| Path | 2050 BAU bill | 2050 saving |
|---|---:|---:|
| Exelon-wide growth | 443 | 25.79 |
| Derived path (central) | 419 | 23.05 |
| No plan (2.5% growth) | 401 | 20.92 |

**Rate-case context, updated:** Con Edison's 2050 saving is 12.0x its $6.81 increase (2035: 2.1x). RG&E's is 6.3x its approximately $6.38 increase (2035: 1.6x).

**Still to check:** RG&E's layered data-centre growth (5% a year central, unsourced). The 2026 Gold Book has Zone B falling 47 MW, and data-centre growth is RG&E's top tornado driver.

---

## 2026-10-31: `7c9b6e6` Published-plan BAU

**What changed** (layered model only; v1.0, CORRECTED and the three pins unchanged):
- **New selectable BAU basis, `bau_plan.basis`.** The default, `'published_plan'`, takes BAU distribution capex from each utility's published plan:
  - **Con Edison:** 2025 Form 10-K, CECONY electric 2026–2030.
  - **RG&E:** Five-Year Plan 2026, NYSEG/RG&E Q1 2026 capital variance report.
  - **Dominion:** Q4 2025 slides, electric distribution plus grid transformation 2026–2030.
  - **Pepco:** Exelon Q4 2025 8-K, distribution 2026–2029 x the Maryland share.

  `'model'` keeps the network-model BAU, and reproduces 23fec60 exactly (new fixture `tests/fixtures/layers_23fec60_model_bau.json`).
- **Beyond the plan:** `beyond_path` is 'continue' (plan CAGR), 'taper' (central: to load growth by `taper_year`, 2032 / 2035 / 2040) or 'policy' (high electrification).
- **Plan capex is split into categories:** growth, replacement, grid modernisation / resilience, other.
  - Con Edison and RG&E are sourced from their capital reports.
  - Dominion and Pepco are proxies (`_VERIFY`).
- **Addressable shares by category:** growth 50 / 80 / 100%, capped by the network model's deferrable share; replacement 10 / 20 / 30%; grid modernisation 0 / 5 / 10%; other 0. They ramp in over 5 years from the transition year and follow the scenario (Cautious low, Ambitious high).
- **The network model no longer generates BAU capex in this basis.** It estimates how much of the plan's growth-driven spending is deferrable.
- **Transmission:** Dominion and Pepco's transmission bill lines follow their published (Dominion) or derived (Pepco) transmission rate base per MW of peak. New York transmission is in delivery and in the plan.
- **Capacity:** the PJM 2027/28 auction price at the $333.44/MW-day cap, from 2027. A long-run capacity price path (sensitivity) uses Brattle's 2025 PJM CONE ($528/MW-day UCAP Net CONE) and the NYISO monitor's $200/kW-year, reached by 2040.
- **Tests:** five new tests (197 in total). The current-JSON 1b09e20 comparison runs on the model basis.
- **Also updated:** notebooks, reports (the settings note states the BAU basis), the assumptions register (it now includes `bau_plan`), README, METHODOLOGY.md (2.5, 3.3a, 3.6, 4.6, 7, 8, 10, glossary), utility notes and CLAUDE.md.

**Effect on results.** The opportunity is larger on published-plan BAU, because the utilities' plans spend more on the distribution network than the network model generated. Central customer savings:
- Con Edison: $36.2B (was $14.4B on model BAU);
- Dominion: $18.8B ($13.4B);
- Pepco: $4.6B ($4.0B);
- RG&E: $3.3B ($1.1B).

All undiscounted nominal. Two other effects:
- BAU bills are higher, and the 2050 saving is 12–18% of the BAU delivery bill at Central.
- Shared savings earnings rise with the pool: Con Edison $11.6B, Dominion $3.7B.

| Utility | Scenario | BAU bill 2026 → 2035 → 2050, $/month (model / plan) | Customer savings $B undiscounted (model → plan) | NPV 3% (model → plan) | 2035 bill lower, $/month | 2050 bill lower, $/month | 2050 saving, % of BAU delivery bill | Shared savings earnings $B |
|---|---|---|---|---|---|---|---|---|
| Con Edison | Cautious | 215 → 289 → 385 / 215 → 326 → 500 | 4.33 → **11.13** | 2.73 → 6.69 | 1.73 → 4.03 | 3.65 → 16.87 | 1.5% → 4.8% | 0.05 → 2.82 |
| Con Edison | Central | 215 → 289 → 385 / 215 → 326 → 500 | 14.38 → **36.24** | 8.85 → 21.52 | 6.37 → 13.36 | 16.63 → 62.72 | 7.0% → 18.0% | 2.26 → 11.63 |
| Con Edison | Ambitious | 215 → 289 → 385 / 215 → 326 → 500 | 29.75 → **65.94** | 18.27 → 39.21 | 11.41 → 22.99 | 28.26 → 106.23 | 11.8% → 30.5% | 4.95 → 20.46 |
| Dominion | Cautious | 183 → 218 → 295 / 183 → 238 → 330 | 3.58 → **5.94** | 2.30 → 3.68 | 2.21 → 2.69 | 3.16 → 5.18 | 3.1% → 4.2% | 0.01 → 0.23 |
| Dominion | Central | 183 → 218 → 295 / 183 → 238 → 330 | 13.40 → **18.85** | 8.30 → 11.50 | 5.22 → 6.38 | 9.89 → 14.45 | 9.7% → 11.8% | 1.39 → 3.73 |
| Dominion | Ambitious | 183 → 218 → 295 / 183 → 238 → 330 | 37.79 → **49.13** | 23.31 → 29.94 | 12.78 → 15.18 | 25.61 → 35.46 | 25.1% → 29.0% | 6.95 → 11.81 |
| Pepco | Cautious | 232 → 287 → 403 / 232 → 298 → 419 | 1.93 → **2.35** | 1.25 → 1.49 | 5.22 → 6.40 | 5.40 → 10.43 | 3.6% → 7.0% | 0.01 → 0.03 |
| Pepco | Central | 232 → 287 → 403 / 232 → 298 → 419 | 3.98 → **4.58** | 2.51 → 2.86 | 8.67 → 10.76 | 15.88 → 23.05 | 10.6% → 15.6% | 0.18 → 0.44 |
| Pepco | Ambitious | 232 → 287 → 403 / 232 → 298 → 419 | 5.59 → **6.47** | 3.50 → 4.03 | 11.30 → 14.23 | 23.31 → 32.87 | 15.5% → 22.2% | 0.59 → 0.97 |
| RG&E | Cautious | 159 → 191 → 236 / 159 → 220 → 308 | 0.39 → **1.20** | 0.25 → 0.73 | 0.78 → 2.53 | 1.06 → 7.13 | 1.0% → 4.0% | 0.00 → 0.27 |
| RG&E | Central | 159 → 191 → 236 / 159 → 220 → 308 | 1.15 → **3.28** | 0.71 → 1.96 | 1.96 → 6.04 | 4.44 → 22.17 | 4.0% → 12.3% | 0.01 → 0.92 |
| RG&E | Ambitious | 159 → 191 → 236 / 159 → 220 → 308 | 2.63 → **5.69** | 1.61 → 3.41 | 4.29 → 10.22 | 10.84 → 36.52 | 9.8% → 20.3% | 0.16 → 1.47 |

Delivery bill = distribution base, distribution riders and program surcharges (average residential bill).

**Sensitivities** (customer savings $B undiscounted / 2050 saving $/month / shared savings earnings $B):

| Sensitivity (Central, published-plan BAU) | Con Edison | Dominion | Pepco | RG&E |
|---|---|---|---|---|
| Central (published plan) | 36.24 / 62.72 / 11.63 | 18.85 / 14.45 / 3.73 | 4.58 / 23.05 / 0.44 | 3.28 / 22.17 / 0.92 |
| Capacity at long-run cost of new entry | 39.91 / 67.58 / 13.20 | 21.87 / 15.66 / 5.02 | 5.13 / 24.59 / 0.67 | 4.16 / 26.04 / 1.30 |
| Asset-replacement addressable 10% | 33.19 / 57.32 / 10.32 | 17.75 / 13.76 / 3.26 | 4.32 / 21.01 / 0.33 | 2.66 / 17.36 / 0.66 |
| Asset-replacement addressable 20% (central) | 36.24 / 62.72 / 11.63 | 18.85 / 14.45 / 3.73 | 4.58 / 23.05 / 0.44 | 3.28 / 22.17 / 0.92 |
| Asset-replacement addressable 30% | 39.29 / 68.12 / 12.94 | 19.95 / 15.15 / 4.20 | 4.85 / 25.09 / 0.55 | 3.89 / 26.99 / 1.19 |
| Data-centre flexibility at Ambitious | 37.24 / 65.36 / 12.06 | 19.35 / 14.93 / 3.94 | 4.59 / 23.19 / 0.45 | 3.35 / 22.95 / 0.95 |
| Combined (long-run capacity + replacement 30% + data-centre flexibility) | 43.96 / 75.61 / 14.94 | 23.48 / 16.83 / 5.71 | 5.40 / 26.77 / 0.79 | 4.85 / 31.63 / 1.59 |
| Beyond-plan path: continue | 43.51 / 85.39 / 14.75 | 17.31 / 12.94 / 3.07 | 4.26 / 19.64 / 0.30 | 3.98 / 30.67 / 1.22 |
| Beyond-plan path: taper | 36.24 / 62.72 / 11.63 | 18.85 / 14.45 / 3.73 | 4.58 / 23.05 / 0.44 | 3.28 / 22.17 / 0.92 |
| Beyond-plan path: policy | 35.78 / 62.36 / 11.44 | 19.79 / 15.24 / 4.13 | 4.78 / 24.72 / 0.52 | 3.15 / 21.30 / 0.86 |

**In context:** the saving compared with each utility's latest residential rate-case increase. The saving is nominal in its year; each increase is nominal in its rate year.

| Utility | Latest residential rate-case increase | 2035 saving, $/month (multiple) | 2050 saving, $/month (multiple) |
|---|---|---|---|
| Con Edison | $6.81/month, rate year 1 (2026), 600 kWh, Case 25-E-0072 (NYPSC rate case summary, Jan 2026) | 13.36 (2.0x) | 62.72 (9.2x) |
| Dominion | $11.24/month in 2026 (+$2.36 in 2027), 1,000 kWh, SCC PUR-2025-00058 final order (25 Nov 2025; as reported) | 6.38 (0.6x) | 14.45 (1.3x) |
| Pepco | $3.94/month, Order No. 92607 (Case 9820) | 10.76 (2.7x) | 23.05 (5.9x) |
| RG&E | temporary rates +4.0% of electric revenue (Jun 2026, Case 25-E-0379); no residential $ figure published, so 4.0% x the modelled $159.45 starting bill = $6.38/month (approximation). The request was $33.01/month at 600 kWh | 6.04 (0.9x) | 22.17 (3.5x) |

**From v1.0's $12,907 to today (Con Edison):**

| Step | Con Edison cumulative saving per residential customer, 2026–2050, $ undiscounted nominal | Change | Label |
|---|---:|---:|---|
| v1.0 as published (before commit 78f1a4f) | 12,907 | | |
| Segmented load model: data centres grown from their own MW base instead of a blended rate (78f1a4f) | 12,423 | −484 | assumption choice |
| + depreciation in the delivery revenue requirement (avoided depreciation was not counted) | 13,617 | +1,194 | error corrected |
| + revenue-requirement savings pool (v1.0 credited avoided capex and also kept it out of rate base: double count) | 9,339 | −4,278 | error corrected |
| + negative pools carried forward instead of negative utility earnings | 9,398 | +60 | assumption choice |
| + bills indexed to BAU 2026 (each case indexed to its own 2026 RR hid first-year differences) | 9,199 | −199 | error corrected |
| + capacity savings allocated by class sales share (per-customer allocation overstated the residential share) | 8,026 | −1,173 | error corrected |
| + capacity price growth at inflation instead of 3% real | 7,983 | −43 | assumption choice |
| = CORRECTED preset (earlier model) | 7,983 | | |
| Layered model, model-derived BAU, before the code fixes (50a3f96): starts from the actual line-by-line bill; explicit network capacity instead of 80% avoidance of an eligible capex share; programs paid in rates at MW x cost; efficiency; value streams; earnings recovered in rates | 3,002 | −4,981 | assumption choice (model structure) |
| + code fixes from the independent check (efficiency peak counted once in capacity; flexible connections and efficiency not double counted) | 2,544 | −458 | error corrected |
| + published-plan BAU (Con Edison's 2026–2030 capital plan, taper to load growth by 2035; 20% of replacements right-sized) | 7,824 | +5,280 | assumption choice |

The earlier-model steps are BASE vs BAU on the earlier model's 600 kWh bill; the layered steps are the Central average residential bill. NWS cost treatment and the ROE rebase flag in CORRECTED leave the result unchanged.

**Caveats and `_VERIFY` items introduced**
- RG&E publishes one plan year, so it uses Con Edison's CAGR (7.2%) as a proxy (`plan_cagr_override`).
- Dominion's and Pepco's category splits are proxies.
- Pepco's transmission rate base path is derived at the model's 3.5% decay.
- Long-run capacity: RG&E uses the New York battery Net CONE as a proxy.
- Addressable shares, beyond-plan paths and the taper year are settings.
- Con Edison's plan assumes approval of its programs; its 10-K notes that New York's Chapter 58 of 2026 adds uncertainty.

---

## 2026-10-31: `23fec60` Code fixes from the independent check

**What changed** (layered model only; v1.0, CORRECTED and the three pins unchanged):
1. **Capacity counts each efficiency MW once.** Capacity MW are now peak − MW waiting − (firm flexible MW + EE MW) with the capacity layer on, and peak − MW waiting with it off. Before, EE MW were subtracted three times with the layer on and once with it off.
   - **Dominion's demand-response MW no longer embed efficiency.** The IRP's DSM MW combine EE and DR: 341 MW in 2025 and 1,076 MW by 2030. The EE part is removed at `ee_kw_per_mwh` x the IRP's DSM energy savings (1,462 and 3,011 GWh). DR is now 181.2 MW today and 746.9 MW in 2030–2035 (2050: 1,079.3 MW; Cautious 271.8 / 362.4 MW).
   - Neither Dominion's IRP nor the SCC DSM reports give a DR-only MW figure, so the split is derived and stays `_VERIFY`.
2. **Flexible connections count once.** They count as network headroom (deferral or load enabled), and are no longer also credited as connection cost avoided by new customers.
3. **Earnings attributable is proportional to the pool.** `layer_contributions()` splits total shared savings earnings across layers in proportion to each layer's contribution to the savings pool, which is now its own column.
   - Total earnings are unchanged.
   - Programs takes a negative share, because its costs come before the savings they enable.
   - Deferral now earns a positive share (Con Edison Central $0.90B, previously zero).
4. **Efficiency is not counted as MW connected sooner.** MW connected sooner are load served above what BAU serves, per band, so efficiency is neither counted nor charged connection cost. Electrification brought forward is now the energy of the MW connected sooner.
5. **The `'capex'` pool basis is removed from the layered model.** The `pool_basis` argument and the `customer_credit_m` column are gone, and any JSON value other than `'revenue_requirement'` raises an error. The earlier model's `SAVINGS_POOL_BASIS` is unchanged.
6. **Six inputs relabelled `setting`,** as their sources say: `transition_year`, `existing_capitalised`, `uplift_mode`, `customer_funded_share`, `pool_basis`, `enable_share`, in all four utilities. The `_VERIFY` shares are now Con Edison 46%, Dominion 43%, Pepco 49%, RG&E 58%.
7. **Pepco's capacity layer now starts from its carve-out price:** the 2026/27 BRA, $329.17/MW-day = $0.12015M per MW-year (was $0.1217M, 2027/28). `shared/capacity_markets/PJM.json` and the earlier model are unchanged.

**Tests.** Eight new tests, one per fix, plus one for the Dominion DR derivation (177 in total):
- The headroom test is tightened: MW connected sooner ≤ load-enabled headroom.
- The ebb0c04 and 1b09e20 fixture tests now compare BAU exactly, and every shared-savings column except those the fixes change on purpose: capacity, bills, RR, earnings, connection cost avoided, MW connected sooner.
- With the current JSON they also skip Dominion's shared-savings case and Pepco's capacity columns (this commit's data changes).
- The pinned fixture files are unchanged.

**Also updated:** notebooks and reports regenerated; the assumptions register; the README table; METHODOLOGY.md (3.4, 3.5, 3.6, 3.10, 4.5, 6, 8, 10.2, glossary); utility notes; CLAUDE.md.

**Effect on results.** The opportunity remains substantial: Central customer savings of $14.4B (Con Edison), $13.4B (Dominion), $4.0B (Pepco) and $1.1B (RG&E), undiscounted nominal, with Ambitious up to $29.8B, $37.8B, $5.6B and $2.6B. Most of the reduction is the capacity fix.
- **Dominion:** of its −$3.65B Central change, −$3.03B is the engine fixes and −$0.62B the DR data change.
- **Pepco:** the price alignment is −$0.01B; the rest is the engine fixes.
- **Shared savings earnings** fall more in proportion than customer savings: the removed capacity overcount had been inflating the pool, and carry-forward absorbs more of the smaller pool in early years.
- **Unchanged:** wires capex avoided, Upgrade Delay avoided and flexible MW, except at Dominion, where the smaller BAU demand-response base slightly lowers Central and raises Ambitious incremental MW.
- **Access:** connection cost avoided falls by over 90% (flexible connections and efficiency no longer counted there), and MW connected sooner roughly halve.

| Measure (Central; Cautious–Ambitious in brackets) | Con Edison | Dominion | Pepco | RG&E |
|---|---|---|---|---|
| Customer savings, $B undiscounted | 16.58 (5.41–34.49) → **14.38** (4.33–29.75) | 17.05 (5.65–44.24) → **13.40** (3.58–37.79) | 4.67 (2.46–6.46) → **3.98** (1.93–5.59) | 1.27 (0.47–2.89) → **1.15** (0.39–2.63) |
| Customer savings, $B NPV 3% (2026 $) | 10.22 (3.39–21.21) → **8.85** (2.73–18.27) | 10.55 (3.56–27.29) → **8.30** (2.30–23.31) | 2.93 (1.57–4.05) → **2.51** (1.25–3.50) | 0.78 (0.29–1.78) → **0.71** (0.25–1.61) |
| Bill $/month lower, 2035 | 7.71 (2.33–14.31) → **6.37** (1.73–11.41) | 5.96 (2.55–14.04) → **5.22** (2.21–12.78) | 9.52 (5.73–12.37) → **8.67** (5.22–11.30) | 2.22 (0.95–4.85) → **1.96** (0.78–4.29) |
| Bill $/month lower, 2050 | 19.18 (4.84–33.74) → **16.63** (3.65–28.26) | 11.36 (4.09–28.08) → **9.89** (3.16–25.61) | 17.55 (7.35–25.43) → **15.88** (5.40–23.31) | 4.92 (1.39–11.88) → **4.44** (1.06–10.84) |
| Cumulative saving per customer, $ undiscounted | 3,002 (796–5,404) → **2,544** (586–4,421) | 1,992 (784–4,837) → **1,738** (635–4,403) | 3,229 (1,629–4,402) → **2,935** (1,342–4,029) | 797 (268–1,849) → **711** (211–1,663) |
| Shared savings earnings, $B undiscounted | 3.21 (0.37–6.98) → **2.26** (0.05–4.95) | 2.96 (0.17–9.72) → **1.39** (0.01–6.95) | 0.48 (0.07–0.96) → **0.18** (0.01–0.59) | 0.06 (0.00–0.27) → **0.01** (0.00–0.16) |
| Capacity cost avoided, $B undiscounted | 10.22 (2.90–17.13) → **7.07** (1.50–10.36) | 11.46 (3.64–28.35) → **6.38** (1.33–18.98) | 2.10 (1.20–3.16) → **1.12** (0.61–1.91) | 0.80 (0.13–1.15) → **0.62** (0.05–0.76) |
| Wires capex avoided, $B undiscounted | 6.25 (1.59–10.68) → **6.25** (1.59–10.68) | 3.80 (0.97–9.70) → **3.57** (0.93–9.81) | 0.38 (0.17–0.73) → **0.38** (0.17–0.73) | 0.34 (0.05–0.52) → **0.34** (0.05–0.52) |
| New flexible MW, 2050 | 3,576 (466–3,729) → **3,576** (466–3,729) | 2,863 (341–6,854) → **2,547** (181–7,014) | 327 (169–660) → **327** (169–660) | 545 (7–545) → **545** (7–545) |
| Upgrade Delay avoided, MW-years | 178 (31–215) → **178** (31–215) | 501 (41–635) → **482** (32–637) | 36 (11–49) → **36** (11–49) | 24 (1–26) → **24** (1–26) |
| MW connected sooner, peak year | 15.6 (2.0–22.3) → **7.5** (0.2–14.7) | 29.5 (3.1–38.2) → **7.7** (0.1–28.7) | 3.4 (1.1–6.2) → **1.4** (0.1–3.4) | 1.8 (0.1–1.9) → **1.2** (0.0–1.3) |
| Connection cost avoided, $M undiscounted | 705 (9–1,687) → **32** (1–62) | 656 (6–1,562) → **15** (0–55) | 51 (3–121) → **3** (0–8) | 46 (0–110) → **2** (0–2) |

All $ nominal. Bills are the average residential bill, $/month; the Upgrade Delay figures are MW-years 2026–2050.

---

## 2026-10-31: `50a3f96` Documentation and methodology pass

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

**Found, not changed in that commit** (each would change results): fixed in the next commit, "Code fixes from the independent check".

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

**Code looks wrong (documented, not changed in 50a3f96; F1 and F3–F8 fixed in the next commit, F2 kept by design):**

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
