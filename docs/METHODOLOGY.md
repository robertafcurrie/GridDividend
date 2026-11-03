# GridDividend methodology

*The layered model (`engine/layers.py`, Section 13 of each state notebook). As of 2 November 2026: published-plan BAU (business as usual, following the utility's own investment plan; 2.5, 3.3a), avoided-obligation capacity (the capacity the utility no longer has to buy; 3.6a), split transmission (transmission upgrades deferred in savings, the lower share of zonal transmission costs reported separately; 3.8a), customer allocation by sales (3.10b), after the code fixes in the CHANGELOG entry "Code fixes from the independent check".*

This document explains how GridDividend works. It is written for a policy reader who is comfortable with numbers but is not a modeller. Sections marked **Technical detail** give the equations and code-level behaviour; they can be skipped without losing the thread.

**New to the terms?** [GLOSSARY.md](GLOSSARY.md) defines every bill component, ratemaking term and model term in plain language.

Related documents:
- [GLOSSARY.md](GLOSSARY.md): plain-language definitions (parts of a bill, how rates are set, terms in the model).
- [ASSUMPTIONS.md](ASSUMPTIONS.md): every input, by utility, with its value, source, as-of date and status (generated from the JSON).
- [utilities/](utilities/): data notes for each utility.
- [../README.md](../README.md): headline results.
- [../CHANGELOG.md](../CHANGELOG.md): what changed, and its effect on results.

Notation in the equations: `x` is multiplication, MW is megawatts and kWh kilowatt-hours, `t` is years since 2026, `^` is a power, and `(1 + g)^t` grows a 2026 value at rate `g` a year. "SS" means the shared savings case.

---

## Contents

1. [Purpose and framing](#1-purpose-and-framing)
2. [Structure](#2-structure)
3. [The layers](#3-the-layers)
4. [Outputs](#4-outputs)
5. [Dollar bases and discounting](#5-dollar-bases-and-discounting)
6. [Data and status](#6-data-and-status)
7. [Configuration](#7-configuration)
8. [Validation](#8-validation)
9. [Relationship to v1.0 and CORRECTED](#9-relationship-to-v10-and-corrected)
10. [Limitations and open questions](#10-limitations-and-open-questions)
11. [Glossary](#11-glossary)
12. [Starting point: 2021–2026](#12-starting-point-20212026)

---

## 1. Purpose and framing

GridDividend shows the **potential** of shared savings for electric distribution utilities, and the **conditions** that unlock it.

Under shared savings, flexibility becomes core utility business. Here flexibility means:
- demand response;
- managed EV charging;
- distributed storage;
- other distributed energy resources (DER);
- energy efficiency.

Flexibility creates value in five ways:
- It defers network reinforcement (grid upgrades).
- It lowers capacity, wholesale energy, transmission and loss costs.
- It lets new customers connect sooner where the grid is constrained.
- The utility earns a share of the savings it creates. That share is its **shared savings earnings**, the earnings opportunity the reform offers.
- Customers keep the rest.

**Ranges, not forecasts.** Every result comes from three scenarios:
- **Cautious:** today's programs, grown modestly.
- **Central:** flexibility anchored to state targets and studies.
- **Ambitious:** what supportive policy could unlock.

The range shows how much the outcome depends on choices regulators and utilities make, and on external drivers they do not control.

**What the model is:**
- A transparent, reproducible illustration of the mechanism.
- It starts from each utility's actual residential bill and rate-case figures.
- Every input carries a source, an as-of date and a status.

**What the model is not:**
- Not a utility planning model, and not a rate-case replica.
- Not a forecast of bills.
- It does not site individual projects: the network is represented by loading bands, not feeders.
- It does not model customer behaviour beyond the stated program paths.
- It is not a cost-benefit test from any single regulatory perspective.
- GridDividend measures bill impacts, not total resource cost: customer-side DER and efficiency costs beyond the utility incentives recovered through rates are outside the model.

---

## 2. Structure

### 2.1 Two cases: BAU and shared savings

Each run projects two cases, year by year, from 2026 to 2050.

- **Business as usual (BAU):** the utility invests as its published capital plan says (2.5). Program surcharges stay on the bill, and today's flexibility programs continue at their current size.
- **Shared savings (SS):** from the **transition year** (2028 for all six utilities), core programs (programs that become utility business) leave the surcharges and become utility spending recovered in rates.
  - The utility grows flexible resources and efficiency along a target path.
  - Flexible headroom (grid space freed by flexibility) defers reinforcement or connects waiting load.
  - The resulting savings form a pool (the savings pool: the net saving before it is split). The utility keeps a share as shared savings earnings.

Both cases share the same load growth, prices and network. The difference between them is the effect of the reform.

### 2.2 Starting point

Year zero is each utility's **residential bill today**, line by line (`starting_bill` in the utility JSON). Each line is priced at a benchmark monthly usage (600 kWh for Con Edison and RG&E, 1,000 kWh for Dominion, 900 kWh for Pepco). Lines are grouped into seven categories:
- distribution base;
- distribution riders;
- program surcharges;
- supply energy;
- capacity;
- transmission;
- taxes and fees.

Two adjustments are made at year zero (see [3.1](#31-starting-bill)):
- Where capacity is embedded in another line, it is split out.
- Pepco's authorised but not yet billed increase is added.

System figures (rate base (the value of the utility's invested assets), capex (capital spending), revenue, ROE (allowed return on equity), equity ratio (the share financed by shareholders), customers, peak, energy) come from each utility's rate case. They are the same figures the earlier model uses.

### 2.3 Projection, 2026–2050

Each bill category is projected on its own driver:

| Category | Driver |
|---|---|
| Distribution base and riders | Wires revenue requirement (what the utility may collect for the local wires) per kWh delivered |
| Program surcharges | Core surcharges: grow with the surcharge growth rate in BAU, removed in SS from the transition year. Non-core surcharges: grow in both cases |
| Supply energy | Supply energy growth rate; lowered in SS by wholesale-energy and loss-energy savings |
| Capacity | Zonal capacity price x capacity MW, per kWh delivered |
| Transmission | Transmission growth rate; lowered in SS by avoided transmission where transmission is billed separately (PJM) |
| Taxes and fees | Percentage taxes follow their base; fixed fees are held |
| SS only: core programs and shared savings earnings | A per-kWh rider recovering program costs and shared savings earnings |

### 2.4 Scenarios

Each input with uncertainty has a **low / central / high** value. A scenario picks a level for each input.

| Scenario | Programs (flexibility and efficiency as core business) | Deferral (grid upgrades deferred) | Load enabled (new load connected sooner) | Everything else |
|---|---|---|---|---|
| Cautious | low | low | low | central |
| Central | central | central | central | central |
| Ambitious | high | high | high | central |

**What "low" and "high" mean.** The levels are labels in the JSON, oriented within each layer:
- In the programs, deferral and load-enabled layers, "low" is the cautious end and "high" the ambitious end. The programs level moves more than MW and cost:
  - fewer MW and higher cost per kW-year;
  - lower derates (the share of flexible MW counted on at peak);
  - higher capitalised shares, so the cost timing changes too;
  - a lower `ee_kw_per_mwh` (peak kW saved per MWh of efficiency);
  - a lower efficiency savings rate;
  - fewer flexible connections with more curtailment;
  - tighter ramp limits.

  The deferral level sets the locational match (the share of flexibility sited where the grid needs it). The load-enabled level sets the enable share, the connection cost and the incremental O&M.
- In the mechanism layer (the utility's share of the savings), "low" is a *larger* utility share (40%) and "high" a smaller one (10%).
- In the ROE layer (the utility's allowed return on equity), "low" is −60 basis points (−0.6 percentage points) and "high" +60.

**What scenarios hold fixed.** Load growth, prices, network inputs and the utility share stay at central in every scenario. The range therefore isolates program ambition, cost and siting.

Each scenario can also set its own network values. They are empty by default, so every scenario uses the JSON network block, with the constrained sub-band on.

- **Addressable shares.** The published-plan addressable shares (3.3a) follow the scenario too: Cautious at low, Ambitious at high, with growth 50 / 80 / 100%, replacement 10 / 20 / 30% and grid modernisation 0 / 5 / 10%.

### 2.5 BAU basis: the utility's published plan

BAU is what the utility says it will do. By default (`bau_plan.basis: 'published_plan'`) it is built from published sources:
- **Distribution capex** follows each utility's published capital plan for the plan years:
  - Con Edison: 2025 Form 10-K, 2026–2030;
  - RG&E: its Case 25-E-0379 proposal, 2026–2031 (the 2028–2031 years are an equal split of the filed total);
  - Dominion: Q4 2025 investor slides, 2026–2030;
  - Pepco: Exelon Q4 2025 slides, 2026–2029, Maryland share.
- **Beyond the plan,** three selectable paths run to 2050:
  - continue the plan growth rate;
  - **taper** to load growth by a set year (central, 2035);
  - follow policy-driven load growth (high electrification).
- **Growth-driven capex follows load** (`link_growth_to_load`, central on).
  - Each plan records the load growth it assumes:
    - Con Edison 0.7% a year (its 10-K forecast);
    - Pepco 0.33% (its Maryland Ten-Year Plan);
    - Dominion 1.88% (its own 2025 Company Load Forecast for the DOM LSE (Dominion's own load in PJM's DOM zone), which includes Dominion-served data centres);
    - RG&E 3.0% (Gold Book Zone B: NYISO's annual load forecast for the Rochester area; proxy).
  - In the plan years, the growth category is scaled by the model's load growth relative to that assumption. Replacement, grid modernisation and other stay on plan.
  - Plan capex fixed regardless of load remains a setting.
- **Electrification pace** (`electrification_pace`, central `utility_forecast`).
  - Central BAU load is calibrated to the forecast behind each utility's plan, so the load link's scale factor is 1.0 at plan end.
  - `state_policy` keeps the model's electrification assumptions (state policy pace). The difference is reported as the additional opportunity if electrification follows state policy (`electrification_pace_table()`).
- **Plan capex is split into categories:** growth-driven, asset replacement, grid modernisation / resilience, and other. The split is sourced for Con Edison and RG&E. **Dominion and Pepco use the New York splits as a proxy** (`_VERIFY`: an estimate awaiting confirmation); neither publishes one.
- **Each category has an addressable share:** the part that flexibility, efficiency and better planning could defer, avoid or right-size under shared savings (3.3a).
- **Transmission** follows its own published plan and stays on its bill line, where it is one (Dominion and Pepco). In New York, transmission is recovered in delivery rates and is part of the plan's electric capex.
- **The network model no longer generates BAU capex.** It still models capacity, waiting load and the Upgrade Delay (the wait for a grid upgrade before a new customer can connect), and it estimates how much of the plan's growth-driven spending is deferrable, and where.
- **Other bill components:**
  - Capacity uses published auction prices where they exist (PJM 2027/28 at $333.44/MW-day).
  - Transmission follows the plans above.
  - Supply energy and program surcharges keep their growth rates (no utility-specific published forecast was found).
  - Shared savings influences these lines (capacity, wholesale energy, transmission and losses) but does not eliminate them.

The earlier, model-derived BAU remains selectable (`basis: 'model'`: capex generated by the network model) and reproduces the earlier results exactly (tested).

> **Technical detail.** `scenario_overrides()` builds `{(layer, param): level}` from `scenarios[name]['levels']`. A key can name a layer (`'programs'`) or one input (`'programs.cost_kw_yr_dr'`), and anything unlisted takes `default_level`. Central returns only its network values. The tornado (one input moved at a time) and `project_layers()` without a scenario use every input at `level` (default central), which equals Central.

---

## 3. The layers

Each layer has its own switch (`enabled`). The waterfall (the bill stepping from BAU to shared savings one layer at a time) adds them in this order.

| # | Layer | One line |
|---|---|---|
| — | Starting bill | Today's bill, line by line |
| 1 | System needs (load growth and the grid it needs) | Load growth, peak, growth vs asset-condition capex (both cases) |
| — | Network capacity | Loading bands, constrained sub-band, reinforcement, Upgrade Delay for Interconnection (both cases) |
| — | Published-plan BAU (the utility's own investment plan) | BAU distribution capex from the utility's plan; addressable shares by category (3.3a) |
| 2 | Programs as core business (flexibility and efficiency run by the utility) | Surcharges leave the bill; flexible MW and efficiency paid for in rates |
| 3 | Deferral (grid upgrades deferred) | Flexible headroom counted by the planner, so reinforcement is ordered later |
| 4 | Load enabled (new load connected sooner) | Flexible headroom connects waiting load sooner |
| 5 | Capacity (less capacity to buy) | Firm MW avoided at the zonal capacity price |
| 6 | Wholesale energy (energy bought off-peak instead of on-peak) | Flexible load shifted from on-peak to off-peak hours |
| 7 | Avoided transmission (lower transmission costs) | Transmission cost avoided by peak reduction |
| 8 | Avoided distribution losses (less energy lost on the wires) | Marginal losses avoided |
| 8a | Additional savings objective (extra savings the utility commits to find) | Savings the utility commits to find by unspecified means (default 0%) |
| 9 | Mechanism (the utility's share of the savings) | Splits the pool between the utility (shared savings earnings) and customers |
| 10 | ROE lever (the utility's allowed return) | Allowed ROE vs BAU, outside the pool |

Each subsection below covers:
- what the layer represents;
- the calculation;
- its inputs;
- how it interacts with other layers;
- how double counting is prevented;
- known limitations.

### 3.1 Starting bill

**What it represents.** Today's residential bill at benchmark usage, by tariff line. It anchors every projection to what customers actually pay.

**Calculation.**
- A `$/month` line is its rate.
- A `$/kWh` line is rate x benchmark kWh.
- A percentage line is its rate x the subtotal it applies to (`delivery`, `supply` or `distribution_and_transmission`).
- Lines marked `included_in_benchmark: false`, or with no rate, are left out.

*Capacity carve-out* (RG&E, Dominion, Pepco, Eversource CT, United Illuminating): where capacity is embedded in a supply line, a capacity line is derived and moved out of the parent line(s). The total bill is unchanged.

```
obligation_kw per customer = peak_mw x residential_share x obligation_scaling / residential_customers x 1000
capacity $/month           = obligation_kw x price ($/MW-day) / 1000 x 365 / 12
```

For Dominion the carved-out amount is split 91.5% from base generation and 8.5% from fuel. In Connecticut it comes out of the Standard Service Generation Service Charge at the FCA 17 price ($2.59/kW-month = $85.15/MW-day) and the ICR / reference-peak factor 1.151.

*Temporary rates* (`revert` on a starting-bill line; Connecticut): a line whose 2026 rate is known to be temporary returns to a stated rate (2026 $, same unit) from `from_year`, with `first_year_share` of that year at the new rate, then grows like its category. It applies to program surcharge lines. Connecticut's public-benefits charges are a credit from May 2026 (PA 25-173 bonding and the Millstone / Seabrook contracts turning into a net benefit) until at least April 2027. From May 2027 (8/12 of 2027), NBFMCC + SBC move toward 3.3¢/kWh, the pre-credit level of about 4¢ (OCC) less C&LM and renewable energy. How far they move is `projection.public_benefits_revert_share` (a range, so it is in the tornado):
- low 0: the credit persists;
- central: only the PA 25-173 bonded amount returns. OCC puts it at about $10/month, which is 1.43¢/kWh at 700 kWh: 0.262 of the full move for CL&P (5.46¢) and 0.192 for UI (7.44¢). The bonding is confirmed only "through at least next spring" (Governor's office, 8 September 2026); no authorisation past 30 April 2027 was located, so the revert starts in May 2027;
- high 1: full revert to about 3.3¢/kWh. That would assume the bonding, the Millstone / Seabrook net benefit and returned over-collections all end together.

Without the revert, the model would project a temporary credit for 25 years. The share moves BAU and shared-savings bills alike. Lines without `revert` are unchanged (tested: the other utilities' exports are identical).

*Starting adjustments* (Pepco): the residential increase authorised by Order No. 92607 (+$3.94/month) is added, because the tariff in effect at the as-of date was pre-case.

**Inputs.** The `starting_bill` lines (rate, unit, category, section, core flag, source, status); `capacity_carve_out` (capacity split out of the line it is hidden in); `starting_adjustments` (known changes not yet on the bill).

**Interactions.** Every projected line is the starting line x its driver. The core program surcharges set today's program spend (see 3.4). The residential share of that spend sets how the SS rider is allocated.

**Double counting.** The carve-out moves dollars between lines; it never adds them. Validation: `test_starting_total_equals_starting_bill`.

**Limitations.**
- One benchmark customer, not a distribution of customers.
- The carve-out assumes the residential share of the capacity obligation equals its share of sales. Residential load is peakier, so this likely understates it.
- Some lines are `_VERIFY` (see [utilities/](utilities/)).

> **Technical detail.** `starting_lines()` returns the lines with `month` in $/month and `volumetric` (True for $/kWh lines, the carve-out, and starting adjustments unless they set `volumetric: false`). Pepco's +$3.94/month adjustment is therefore treated like a distribution line: it is projected with the distribution driver, scaled by residential usage in the average bill, and grossed up by the gross receipts tax. Percentage lines are filled by `_apply_pct()` after every other line is projected, in each year. The script `scripts/check_starting_bill.py` reconciles the lines with the published delivery and supply rates.

### 3.2 System needs (layer 1)

**What it represents.** How much electricity customers use and how high the peak is, 2026–2050. It covers:
- baseline growth;
- electrification (EVs and buildings);
- data centres.

It also covers how much network capex is driven by growth rather than asset condition. It applies to BAU and SS alike, so its waterfall bar is zero.

**Calculation.**

```
non-DC energy N0          = annual_energy_gwh - DC0 x 8.76 x dc_load_factor
baseline_t                = N0 x (1 + baseline_energy_growth)^t
EV_t                      = N0 x ((1 + g_elec x ev_share)^t - 1)
buildings_t               = N0 x ((1 + g_elec x (1 - ev_share))^t - 1)
DC_t (MW)                 = DC0 x (1 + dc_growth)^t
sales_t (GWh)             = baseline + EV + buildings + DC_t x 8.76 x dc_load_factor
non-DC peak_t             = (P0 - DC0) x (non-DC energy_t / N0)^peak_elasticity
system peak_t             = non-DC peak_t + DC_t
network peak_t            = non-DC peak_t + DC_t x dc_distribution_share
```

The electrification peak is the extra non-data-centre peak from EV and buildings energy; the EV peak is the part from EV energy. These feed the large-load share (3.3) and the electrification brought forward (4.5).

**Inputs.**
- Growth rates: baseline, electrification, data centres.
- `ev_share_of_electrification` (0.8, NREL EFS).
- `dc_load_factor`, `peak_elasticity`.
- `dist_upgrade_cost_per_mw`.
- From the utility data: energy, peak, data-centre MW and its distribution share.

**Interactions.** The network peak drives reinforcement (3.3). The system peak drives capacity cost (3.6). Sales spread fixed wires costs (bills).

`dc_growth` is either a growth rate or an explicit path {year: MW added since 2026}. RG&E uses the path: the NYISO 2026 Gold Book Zone B large-load forecast, allocated by RG&E's share of the zone peak (57%): +86, +161 and +230 MW by 2028, 2029 and 2030, then flat. Con Edison uses 0% a year (Zone J has no large loads in the Gold Book).

With the layer switched off, demand is flat at 2026 levels and capex is held at the rate-case figure without inflation. No reinforcement is ordered, there is no seed pipeline, and the constrained-area delay rule is disabled.

**Limitations.**
- Growth is smooth, with no step loads.
- Peak follows energy through one elasticity.
- Data-centre load is flat at its load factor.

### 3.3 Network capacity, loading bands, constrained sub-band and Upgrade Delay for Interconnection

**What it represents.** The distribution network has a finite amount of firm capacity. It grows only when the utility builds reinforcement, which takes time and is limited by how fast the utility can build. When load grows faster than capacity, new load **waits for the upgrade**. The **Upgrade Delay for Interconnection** is the time a new customer in a constrained area waits for the grid upgrade before connecting.

**Loading bands.** The network is not one pool. It is split into loading bands, groups of substations from most to least loaded. Each band has:
- a share of capacity;
- a starting loading (load / planning capacity).

The default bands come from Dominion's grid utilization filing (SCC PUR-2026-00164): five quintiles at 100%, 88%, 78%, 70% and 63% of planning capacity. Their capacity-weighted mean is 79.8%. The other three utilities use these bands as a `_VERIFY` proxy until their own data is found.

**Planning limit and operating limit.**
- *Planning capacity* is 80% of the equipment rating (`planning_limit_factor`, Dominion Metric iv). A band at loading 1.0 is at its planning limit.
- *Operating limit* is the rating itself: 1 / 0.80 = 1.25 x planning capacity. Existing (2026) load is kept connected up to the operating limit.

**Constrained sub-band.** Dominion reports that 4.3% of feeders are above their planning limit. The model carves a **constrained sub-band** out of the most loaded bands:
- It holds 4.3% of network load at 112.5% of planning capacity.
- Total load and capacity are unchanged, so the system mean is unchanged.
- The sub-band is on in every scenario.

The sub-band is the model's **constrained area**. Load there is above the planning limit, so:
- the existing backlog must be cleared;
- new load waits for an upgrade.

**Reinforcement outside constrained areas (reactive planner).** Each year, in each band:
- The planner orders new capacity when demand x (1 + planning headroom) exceeds capacity in service, plus the pipeline, plus any flexible headroom counted for deferral.
- The order arrives after the lead time (3 years).
- It is capped at the maximum build rate (3.5% of band capacity a year at central).

**Reinforcement in constrained areas (Upgrade Delay inputs).** In the sub-band the delay inputs replace the reactive planner:
- *Backlog clearance:* each year the utility clears `backlog_clearance_pct` (20% central) of the outstanding backlog above the planning limit, in service the following year.
- *New load:* capacity for new load is ordered on request and arrives after the upgrade delay.
  - Ordinary new load (EVs, heat pumps, small business) waits 0.5 / 1.5 / 3 years (low / central / high).
  - Large loads (distribution-connected data centres, fleet hubs) wait 4 / 6 / 7 years for Dominion and 2 / 3 / 6 years for the others.
  - The split between ordinary and large follows that year's large-load share of network growth.
- *Build-rate priority:* with `constrained_build_priority` on (default), constrained-area upgrades are not capped by the maximum build rate. Off, backlog clearance plus new-load upgrades together are capped at it.

**New load waits behind the backlog.** In a constrained area, capacity built for new load does not serve new load until total capacity has passed the existing load. Backlog clearance is geometric (20% of what remains each year), so this rule drives much of the BAU waiting.

**Which bands count as constrained areas.** Only the sub-band uses the delay inputs, and only when all three delay inputs are set and system needs is on. An explicit band with a starting loading above 1.0 still uses the reactive planner.

**Served load and waiting load.** In each band, served load is the smallest of:
- demand;
- capacity (or existing load up to the operating limit, if higher) plus flexible headroom.

The rest is **MW waiting for upgrade**. Waiting MW are turned into energy not sold as `waiting MW x 8.76 x system load factor`, as if they were unserved all year at the system average load factor. The same load factor is used for incremental O&M and for curtailed flexible-connection energy.

**The delay is measured, not assumed.** New load requested each year joins a first-in, first-out queue. It connects as the MW waiting fall. For each request year the model records:
- the MW that waited at least a year (**MW affected**);
- the MW-years they waited.

Load still waiting at the end of 2050 is counted to the end of 2050. The average Upgrade Delay is MW-years / MW affected.

**Inputs** (`forward_assumptions['network']`):
- Bands, or generated bands with a mean utilisation and spread.
- Planning limit factor and operating limit.
- Sub-band switch, share and utilisation.
- Upgrade delays (ordinary and large) and backlog clearance.
- Build-rate priority.
- Planning headroom, lead time, maximum build rate.
- Seed pipeline.
- Constrained-loading threshold.
- Flexibility targeting.

These are all listed in [ASSUMPTIONS.md](ASSUMPTIONS.md); upgrade cost per MW is in system needs.

**Interactions.**
- Reinforcement in service is growth capex, which enters rate base (bills).
- Flexible headroom (3.4) either substitutes for reinforcement (deferral, 3.5) or connects waiting load (load enabled, 3.5).
- Waiting load is not served, so it neither buys capacity nor pays wires costs while it waits.

**Double counting.**
- Bands sum to the network totals (tested).
- The sub-band is carved out with total load and capacity held.
- Each MW of flexible headroom has one use (see 3.5).

**Limitations.**
- Bands approximate the network: they are not feeders, and constraints are thermal only (no voltage, fault level or protection).
- The bands and the sub-band are Dominion's, used as a proxy elsewhere.
- Delays for ordinary load outside Con Edison are proxies, including Dominion's.
- The build rate is per band.

> **Technical detail.**
>
> *Bands.* For each band with capacity share `cs` and starting loading `L`, load share = `cs x L / sum(cs x L)` and planning capacity `C0 = load share x DN0 / L` (DN0 = 2026 network peak). Optional `growth_share` and `flex_share` default to the load share. Band demand:
> ```
> D_b,t = load_share_b x DN_t + (growth_share_b - load_share_b) x (DN_t - DN0) - EE_MW_t x load_share_b
> ```
> `band_mode: 'generated'` (bands generated from a mean and a spread, instead of listed) makes `n_bands` equal-capacity bands at `mean + spread x (0.5 - i / (n - 1))`. If `mean_utilisation` is null, `mean` is the capacity-weighted mean of the explicit bands. Each band is capped at 1.0. A non-null `mean_utilisation` shifts every band by one amount (bisection) so the capacity-weighted mean equals it, each band capped at 1.0. The sub-band takes `share x DN0` of load and `share x DN0 / U` of capacity from the most loaded bands in turn, moving their growth and flex shares with the load; capacity shares are then recomputed.
>
> *Existing load served.* `G_b = min(load_share_b x DN0, operating_limit x C0_b)`.
>
> *Reactive order* (non-constrained bands):
> ```
> order_b,t = min( max(0, D_b,t x (1 + h) - (C_b,t + pipeline_b + h_def_b,t)), max_build_pct x C_b,t )   arrives in t + lead
> ```
> *Seed pipeline.* Projects under way at 2026: for the first `lead` years (or `seed_pipeline_years`), next year's network growth x (1 + h), arriving that year. It is allocated to bands by growth share, so the 2026 growth / asset-condition capex split does not depend on the bands. It can be `'none'` or an explicit list.
>
> *Constrained bands* (sub-band with all three delay inputs set):
> ```
> gap      = max(0, G_b - (C_b - new-load capacity in service) - backlog pipeline)
> use      = min(h_def, gap)                                     deferral headroom used against the backlog
> backlog order = backlog_clearance_pct x (gap - use)            in service next year
> new order     = max(0, (D_b,t - D_b,2026) x (1 + h) - (h_def - use) - new capacity ordered so far)
> ```
> The new order is split by the large-load share `dL / dDN`, where large load = new distribution data-centre MW + `ev_hub_share` x EV peak. Each part arrives after its delay (`_split_delay`: a fractional delay `d` splits the MW between years `floor(d)` and `floor(d) + 1`; a part due in the same year is in service at once). Without priority, `backlog order + new order` is scaled down to `max_build_pct x C_b`.
>
> *Served load* (BAU: `bs = D`; SS: `bs` = BAU served in that band and year):
> ```
> cs = max(C_b, G_b)
> served_b = min( D_b, min( max(C_b + h_def, G_b), max(cs, bs) ) + h_en )
> ```
> So deferral headroom can carry load only up to what BAU serves (it replaces reinforcement), and only load-enabled headroom connects load BAU leaves waiting.
>
> *Constrained count and above-limit measure.* A band is constrained when `D_b > constrained_loading x (C_b + h_en + h_def)`. MW above the planning limit = `max(0, served_b - (C_b + h_en + h_def))`.
>
> *Delay cohorts* (`_delay_cohorts`, per band, then summed). Requests in year t = `max(0, D_t - D_t-1)`, plus the load already waiting in 2026. Each year the queue is reduced by `sum(queue) - waiting_t`, oldest first. When waiting rises by more than that year's requests, the excess joins the queue as a cohort of that year. A cohort still waiting at the end counts `2051 - request year` years. The total MW-years equals the sum of MW waiting over the years (tested).

### 3.3a Published-plan BAU: distribution capex and what shared savings can address

**What it represents.** The utility's published plan says how much it will spend on the distribution network. This section sets out:
- how that plan is extended to 2050;
- what part of it shared savings could defer (growth-driven work) or right-size (replacements and grid modernisation).

**Calculation.**

```
BAU capex_t        = sum over categories of BAU category_c,t
  category_c,t     = plan capex_t x share_c                                      (plan years; growth also x scale_t)
  scale_t          = max(0, (peak_t / peak_2026 - 1) / ((1 + plan_load_growth)^t - 1))   (link on; 1 if off, and in 2026)
  category_c,t     = category_c,t-1 x (1 + g_t)                                 (after the plan, each category)
  g_t, continue    = plan CAGR (RG&E: 0%, its 2028-2031 plan years are flat)
  g_t, taper       = plan CAGR -> nominal network peak growth, linearly, reached by taper_year
  g_t, policy      = nominal network peak growth with electrification at its high level
nominal peak growth = (network peak_t / network peak_t-1) x (1 + inflation) - 1

deferrable share_t = 1 - cumulative SS reinforcement / cumulative BAU reinforcement     (network model, to year t)
avoided growth_t   = BAU growth category_t x min(addressable_growth, deferrable share_t)
avoided repl._t    = BAU replacement category_t x addressable_replacement x ramp_t
avoided grid mod_t = BAU grid-mod category_t x addressable_gridmod x ramp_t
ramp_t             = min(1, (year - transition year + 1) / addressable_ramp_years)
SS capex_t         = BAU capex_t - avoided growth - avoided replacement - avoided grid mod - avoided other
```

- Avoidance applies in shared savings once programs are active and only with the deferral layer on; deferral's waterfall bar therefore carries the capex effect.
- Rate base rolls forward as before: rate base × (1 − 3.5%) + capex + connection capex.
- The 2026 recalibration of other O&M uses the plan's 2026 capex, so 2026 BAU wires RR still equals the rate-case target.

**Category splits:**

| Utility | Growth | Replacement | Grid mod / resilience | Other | Source |
|---|---:|---:|---:|---:|---|
| Con Edison | 50.2% | 21.4% | 23.5% | 4.9% | 2026 targets, Q1 2026 capital expenditure report to the NYPSC (derived; mapping is the model's) |
| RG&E | 25.8% | 53.0% | 8.3% | 12.8% | 2026 Five-Year Plan by category, Q1 2026 capital variance report (derived) |
| Dominion | 50.0% | 21.4% | 23.7% | 4.9% | **New York proxy:** grid transformation share from the Q4 2025 slides; the rest split in Con Edison's proportions (`_VERIFY`) |
| Pepco MD | 25.8% | 53.0% | 8.3% | 12.8% | **New York proxy:** RG&E's split; Order No. 92607 describes mainly reliability work (`_VERIFY`) |

**Load calibration (utility-forecast pace, central).**
- `calibrate_load()` scales electrification growth by a multiplier m ≥ 0 (keeping the EV / buildings split) so that system peak in the last plan year equals peak_2026 × (1 + plan_load_growth)^n.
- If even m = 0 overshoots, baseline growth is lowered by d instead. This stands for the forecast's efficiency and behind-the-meter solar.
- The calibrated rates continue after the plan.

| Utility | Plan's forecast | Calibration | Scale factor in the plan years | State-policy pace: model growth / scale at plan end |
|---|---|---|---|---|
| Con Edison | 0.7%/yr (10-K) | electrification × 0.32 | 1.00 | 1.26%/yr / 1.82 |
| RG&E | 3.0%/yr (Gold Book Zone B, proxy) | electrification 0; baseline −2.2 pt (to −1.7%/yr) | 0–1.36 (1.00 at 2031) | 4.92%/yr / 1.69 |
| Dominion | 1.88%/yr (DOM LSE Company Load Forecast) | electrification × 0.47 | 0.99–1.00 | 2.47%/yr / 1.32 |
| Pepco MD | 0.33%/yr (Ten-Year Plan) | electrification × 0.36 | 1.00 | 0.86%/yr / 2.61 |

The scale factor compares cumulative growth since 2026, rather than single-year growth, to avoid dividing by year-to-year swings, and it equals 1 when the model's load path matches the plan's.
- **RG&E** varies within its plan because the Gold Book's large loads arrive in steps (none in 2027, then +86/161/230 MW), while the plan assumption is a constant rate. Matching the zone total with RG&E's 57% share of those loads needs its other load to fall 1.7% a year.
- **Dominion:** no distribution-level forecast excluding transmission-connected loads was found. Its own LSE forecast includes the data centres it serves and is compared with the model's system peak, which also includes them. It replaces PJM's 5.4% zone forecast, which includes co-operative load growing 7.4% a year.

**Addressable shares** (settings, low / central / high):
- growth-driven: 50 / 80 / 100% (central = the earlier model's mature NWS avoidance, Brattle Ontario);
- asset replacement: 10 / 20 / 30%;
- grid modernisation / resilience: 0 / 5 / 10%;
- other: 0%.

**Transmission** (Dominion and Pepco; PJM network service rates are revenue divided by zonal peak):

```
transmission line_t = transmission line_2026 x (transmission rate base_t / system peak_t) / (rate base_2026 / peak_2026)   (plan years)
```

After the plan, its growth tapers to `transmission_growth` by `taper_year`. Inputs:
- **Dominion:** the transmission rider rate base path from the Q4 2025 slides ($13.5B in 2025 to $23.7B in 2030).
- **Pepco:** derived from Exelon's transmission capex at the model's 3.5% decay. Exelon publishes transmission rate base only company-wide (+15.3% a year, 2025–2029), so the range is shown:
  - Exelon-wide growth: Pepco's 2050 BAU bill $443/month, saving $24.55;
  - derived path (central): $432, saving $23.58;
  - no plan (2.5% growth): $412, saving $21.74.

**Interactions.**
- BAU bills rise with the plan, so the same percentage of avoided spending is worth more than under the model-derived BAU.
- The network model's deferrable share depends on flexible headroom, locational match and the bands (3.3, 3.5).

**Double counting.**
- Growth-driven avoidance is capped by both the addressable share and what the network model finds deferrable.
- Replacement and grid-modernisation right-sizing are separate categories of the same plan, so no dollar is avoided twice.
- Avoided transmission (3.8) values transmission cost; the distribution plan excludes transmission except in New York. There, the transmission layer's value lowers the delivery bill (3.8), and New York's transmission spend sits in the plan categories (mostly substations and system expansion), so the two can overlap slightly.

**Limitations.**
- Plans run 4–6 years; beyond that the path is a choice.
- Central load is calibrated to utility forecasts that run only to the plan horizon; the calibrated rates are extended to 2050.
- RG&E's forecast is a zone proxy. Dominion's includes the data centres it serves.
- Under state-policy pace, the scale factor carries the model's electrification into BAU capex.
- RG&E's plan is the company's rate-case proposal; the final order is pending, and Staff recommended $226M and $246M for 2026–27 against $308M and $421M proposed. Its 2028–2031 years are an equal split of the $5.06B 2026–2031 total.
- Category splits are mapped by the model. **Dominion and Pepco borrow the New York splits.**
- Addressable shares are settings, not measurements.
- Pepco's transmission rate base path is derived.
- Plan capex for Con Edison includes transmission and surcharge-recovered programs, and Dominion's includes North Carolina, consistent with the modelled customer count.

### 3.4 Programs as core business (layer 2)

**What it represents.** Under shared savings, utility-run programs (demand response, efficiency, electrification, DER and non-wires programs) stop being bill surcharges. They become utility spending recovered in rates: operating cost, plus a capitalised share in a regulatory asset (a cost recovered over several years, earning a return meanwhile). The utility then grows flexible resources by type, and efficiency, along a target path.

**Calculation.**

*Today's program spend* (`spend0`, $M/yr) is the system-wide recovery of the core surcharges: `annual_recovery_m` where published. Otherwise it is residential $/kWh rate x total sales, or $/month rate x 12 x customers. Both fallbacks assume the residential rate applies to every class.

*Flexible MW*, by type (demand response, managed EV, storage, other DER):
- BAU holds today's programs (`mw_start`).
- SS follows a target path, linear from today to the 2035 value and on to the 2050 value.
- From the transition year, each type's growth is capped at its ramp limit (a share of 2026 peak a year):
  - Cautious 0.40%: Pepco direct load control, 2009–2025 average.
  - Central 1.37%: its fastest year.
  - Ambitious: no cap.
- Only MW **above today's** count (incremental MW): today's programs are in BAU too.

```
incremental MW_k,t = max(0, SS MW_k,t - BAU MW_k,t)
flexible cost_k,t  = incremental MW_k,t x 1000 x cost_kw_yr_k x (1 + inflation)^t / 1e6     ($M)
firm flexible MW_t = sum_k incremental MW_k,t x derate_k
```

*Efficiency.*
- Each year from the transition year, new savings of `ee_incremental_savings_pct` x that year's BAU sales.
- Each year's savings persist for the measure life.

```
EE GWh_t  = sum of vintages still within measure life
EE cost_t = EE GWh_t x ee_levelised_cost_kwh x (1 + inflation)^t      ($M)
EE MW_t   = EE GWh_t x ee_kw_per_mwh                                   (EmPOWER Maryland 2024 evaluated ratio)
```

*Flexible large-load connections.* New large loads (distribution data centres + EV hub share x EV peak) that accept flexible connection terms add headroom; their curtailed energy is not sold:

```
flexible connection MW  = large load x flex_conn_share x flex_conn_peak_depth
curtailed GWh           = large load x flex_conn_share x 8.76 x system load factor x flex_conn_energy_curtailed
```

*Spending and recovery.*

```
BAU program spend_t = spend0 x (sales_t / sales_2026) x (1 + program_surcharge_growth)^t
SS program spend_t  = BAU program spend_t + flexible cost_t + EE cost_t        (from the transition year)
capitalised_t       = sum_k flexible cost_k x capitalised_k + EE cost x ee_capitalised + BAU spend x existing_capitalised
program opex_t      = SS spend_t - capitalised_t
regulatory asset    = previous + capitalised_t - amortisation_t   (straight line over amortisation_years, from the next year)
program RR_t        = program opex_t + amortisation_t + regulatory asset_t x WACC          (WACC: weighted average cost of capital)
```

**Bill effect.**
- In SS, the core surcharge lines are set to zero from the transition year.
- A rider recovers the program revenue requirement plus shared savings earnings (3.10) per kWh, allocated to residential customers in the same ratio as today's core surcharges:

```
rider $/month     = (program RR + earnings adjustment) / sales x benchmark kWh x residential allocation
residential alloc = (today's residential core surcharge $/kWh) / (spend0 / total sales)
```

Efficiency also lowers usage. The **average residential bill** scales every volumetric line by `(sales - EE GWh) / sales`.

**Inputs.**
- Per type: `mw_start`, `mw_2035`, `mw_2050`, `cost_kw_yr`, `derate`, `capitalised`, `ramp_pct_peak`.
- Efficiency: savings rate, levelised cost, measure life, capitalised share, `ee_kw_per_mwh`.
- Flexible connections: share, peak depth, energy curtailed, EV hub share.
- `transition_year`, `amortisation_years`, `existing_capitalised`.
- Demand-response paths are demand response only. Dominion's IRP reports DSM MW for efficiency and demand response together (341 MW in 2025, 1,076 MW by 2030), so its demand-response inputs remove the efficiency part at `ee_kw_per_mwh` x the IRP's DSM energy savings: 181.2 MW today and 746.9 MW in 2030–2035. Efficiency is modelled only in the efficiency inputs.
- The `split_*` inputs in the JSON are authoring aids, used to divide statewide or DOE totals across types when the MW paths were set. The engine does not read them.

**Interactions.**
- Firm flexible MW and efficiency MW feed every value layer (3.5–3.9).
- Efficiency lowers network demand and sales.
- Program costs are in the savings pool (3.10) as part of what customers pay.

**Double counting.**
- Program spend is counted once: as surcharge in BAU, as rider in SS.
- Moving today's programs into rates with no new resources is bill-neutral (tested, with the sub-band off; see 10.2).

**Limitations.**
- Target paths are anchored to state targets and studies (Central) or DOE's 20% of peak (Ambitious), not to a utility potential study.
- Many MW paths and costs are `_VERIFY`.
- Efficiency cost is levelised, not program-year cash.

**A programme already in BAU policy (`bau_path_<type>`; Connecticut storage).** Connecticut's Energy Storage Solutions (ESS) is run by Eversource and UI under PURA, with a 580 MW target by 2030, and is recovered through the NBFMCC. It is BAU, not shared savings.
- BAU storage follows `bau_path_storage`: today's installed MW to 580 MW × customer share by 2030, flat after.
- The ESS cost stays in the NBFMCC line on the BAU bill, in both cases.
- Shared-savings storage never falls below the BAU path. Only the MW above it are costed (at `cost_kw_yr_storage`) and credited:
  - Cautious: none;
  - Central: 10% of BAU peak × the storage split;
  - Ambitious: 20% of BAU peak × the storage split.
- The ramp limit applies to growth above the BAU path.
- The cost per kW-year comes from the ESS incentives (effective 1 April 2026, Docket 25-08-05). Performance incentives run 10 years; enrolment incentives ($/kWh × 4 hours) are annualised at a 7% capital recovery factor. Levelised: residential $471, C&I $251. Weighted by the ESS target mix (150 MW residential, 430 MW C&I) that gives $308 (Central). Cautious $360, Ambitious $233 (large C&I).
- Other utilities have no BAU path, so their BAU holds today's MW (unchanged).

### 3.5 Deferral (layer 3) and load enabled (layer 4)

**What they represent.** Firm flexible capacity in the right place acts like network headroom. It can be used in one of two ways:
- **Deferral:** the planner counts it, so reinforcement is ordered later or not at all. Customers save the return, tax and depreciation on capex not built.
- **Load enabled:** where BAU leaves load waiting, headroom lets that load connect sooner. The extra kWh help pay fixed wires costs, net of the cost of connecting them.

**Calculation.**

```
headroom created H_t = firm flexible MW_t x locational_match + flexible connection MW_t       ('derived' mode)
                     = direct_uplift_pct x capacity                                           ('direct' what-if mode)
```

- Headroom is allocated to bands by flex share.
- With flexibility targeting on (derived mode only), up to `flex_targeting_share` x H goes first to bands with load above capacity in service, in proportion to that excess `max(0, D_b - C_b)`. The rest is spread by flex share: `H_b = (H - T) x flex_share_b + T x need_b / sum(need)`, where `T = min(share x H, sum(need))`.
- In each band, headroom goes first to load enabled where BAU leaves load waiting: `h_en = min(H_b x enable_share, BAU waiting_b)`. The rest goes to deferral: `h_def = H_b - h_en`.

*Load enabled, costs.*

```
MW connected sooner_t  = sum_b max(0, SS served_b - BAU served_b)
connection capex_t     = newly connected MW x 1000 x connection_cost_kw x (1 + inflation)^t / 1e6   (enters rate base)
incremental O&M_t      = MW connected sooner x 8.76 x load factor x incremental_om_mwh x (1 + inflation)^t / 1000
```

**What counts as newly connected.** MW connected sooner are load actually served above what BAU serves. Efficiency lowers demand but connects nobody, so it is not counted and is charged no connection cost. Connection capex (and connection cost avoided, 4.5) is charged only when MW connected sooner rise above their previous maximum. Incremental O&M is charged on the whole stock.

**Bill effect versus system-wide effect.** The extra kWh enter sales, which lowers distribution cost per kWh. The load-enabled bar on the residential bill is **only the residential bill effect**. System-wide, the layer shows only its costs: connection capex, incremental O&M, and capacity for the extra load served. Its customer savings and its contribution to the pool are therefore slightly negative (Central: Con Edison −$60M, Dominion −$139M, Pepco −$7M, RG&E −$4M, undiscounted nominal). The benefit goes to the customers being connected and is reported in the access block (4.5).

**Inputs.**
- `locational_match`.
- `enable_share`, `connection_cost_kw`, `incremental_om_mwh`.
- `uplift_mode`, `direct_uplift_pct`, `customer_funded_share` (the share of an upgrade new customers would otherwise pay).
- Flexibility targeting (network block).

**Double counting.**
- Each MW of headroom has one use. Headroom used never exceeds headroom created, and MW connected sooner never exceed load-enabled headroom (tested).
- Flexible-connection MW count once, as headroom (deferral or load enabled). They are not credited again as connection cost avoided (4.5).
- Deferral headroom can only carry load BAU would serve anyway.
- The former utilisation layer, a price discount not tied to any cost that overlapped with deferral, has been replaced.

**Limitations.**
- `locational_match` (the share of flexible MW where the network needs it) is `_VERIFY` and among the most influential inputs.
- Headroom is firm in the planning year; dispatch reliability is captured only through derates.

### 3.6 Capacity (layer 5)

*Since 2 November 2026 the default is the avoided-obligation formulation (3.6a). This section describes the earlier formulation, still available as `capacity.formulation: 'embedded'`.*

**What it represents.** Lower peak demand lowers the utility's capacity obligation in the wholesale capacity market. The zones are NYISO NYC, NYISO Rest of State, PJM DOM and PJM PEPCO.

**Calculation.**

```
price_t        = price_m_per_mw_yr x (1 + price_growth)^t          ($M per MW-year)
system peak_t  = peak_t - MW waiting for upgrade_t
peak reduction = min(firm flexible MW + EE MW, system peak)          (SS, capacity layer on; otherwise 0)
capacity cost  = (system peak - peak reduction) x price             ($M)
capacity bill  = starting capacity line x (price_t / price_0) x ((system peak - peak reduction - loss peak MW) / peak_2026) / (sales_t / sales_2026)
```

- Load waiting for an upgrade does not buy capacity.
- Each efficiency MW and each firm flexible MW lowers the obligation once, in this layer. With the capacity layer off, neither earns a capacity credit, so the waterfall books all of efficiency's capacity value here.
- (Before the code fixes, efficiency MW were subtracted three times with the layer on and once with it off.)

**Inputs.** `price_m_per_mw_yr`, `price_growth`; derates by type (3.4).
- The 2026 price matches the capacity carve-out where there is one (Pepco: the 2026/27 BRA price, $329.17/MW-day = $0.12015M per MW-year).
- The New York zones read `shared/capacity_markets/NYISO.json`, and Dominion reads `PJM.json` (DOM, $0.12M per MW-year).
- Under published-plan BAU, `published_prices` set later years where an auction has cleared: PJM 2027/28 at the $333.44/MW-day cap, from 2027, then `price_growth`.
- `price_path: 'long_run'` (sensitivity) ramps the price linearly from 2026 to the long-run cost of new entry by `long_run_year` (2040), then grows it with inflation:
  - PJM: Brattle's 2025 CONE study, indicative Net CONE (net cost of new entry: what a new peaking plant needs from the capacity market) $528/MW-day UCAP (capacity after allowing for outages) = $192.7/kW-year, 2025 $. PJM's own 2027/28 Net CONE for DOM ($178/MW-day) and PEPCO ($292/MW-day) is below today's capped price.
  - New York: $200/kW-year. Brattle's study for NY DPS and NYSERDA (Jan 2025, Case 24-E-0165; reported by Utility Dive, 5 Feb 2025) puts avoided generation capacity cost above $200/kW-year on a fully decarbonized grid in 2040, from NREL data. The NYISO market monitor's levelized Net CONE for the 2-hour battery reference unit is also $200/kW-year UCAP (2025–2029 reset). RG&E uses the same value as a proxy.

**Interactions.** Avoided-loss peak MW (3.9) lower the capacity bill line; their value is booked in the losses layer, not here. Capacity cost is in the savings pool.

**Limitations.**
- One zonal price, with no price suppression (the alternative formulation in 3.6a adds accreditation, coincidence, the auction lag, the long-run price and a price-suppression sensitivity).
- Dominion's layer price ($0.12M per MW-year) is the same 2026/27 BRA price as its carve-out, rounded in `PJM.json` (0.1% lower than $329.17/MW-day x 365).
- RG&E uses NYISO Rest of State in the layered model.

### 3.6a Capacity: avoided-obligation formulation (default)

**What it represents.** The capacity layer valued the way avoided-cost studies value capacity. It has been the default in every utility and scenario since 2 November 2026 (`capacity.formulation = 'avoided_obligation'`). The earlier formulation (3.6) remains available as `'embedded'`. The BAU capacity line is the same in both; only the value credited in shared savings changes. The CHANGELOG records each headline's change when the default switched.

**Calculation** (shared savings, capacity layer on).

```
accredited MW_t  = sum_k incremental MW_k,t x accr_k x coincidence  +  EE MW_t x accr_ee
coincidence      = system_coincidence x ((1 - locational_match) + locational_match x local_coincidence)
                   (locational_match from the deferral layer; 0 with deferral off)
obligation MW_t  = min(accredited MW_(t - auction_lag_years), system peak_t)      (near-term capacity ramp applied before the lag)
avoided price_t  = today's price (and published auction prices) trending linearly to the long-run net CONE by long_run_year, then inflation
capacity avoided = obligation MW_t x (obligation_factor + secondary_obligation_factor x secondary_price_ratio) x avoided price_t
capacity cost    = system peak_t x bill-line price_t - capacity avoided - price suppression
capacity bill    = starting capacity line x ((capacity cost - loss peak MW x price_t) / (peak_2026 x price_0)) / (sales_t / sales_2026)
```

The six elements:

- **(a) Contribution to peak.** The avoided obligation is the reduction in the utility's contribution to the RTO / NYCA peak, times the obligation that peak carries.
  - PJM (Dominion, Pepco): an LSE's UCAP obligation is its Peak Load Contribution (share of the 5 coincident peaks) x the Forecast Pool Requirement. `obligation_factor` 0.926 = (1 + IRM 20.0%) x pool-wide accredited UCAP factor 77.2% (2027/28 BRA planning parameters).
  - Con Edison: the NYC locational requirement, 86.4% of NYC peak (CHPE-in; 82.6% CHPE-out, the low level), at the NYC price. The rest of the NYCA requirement, (1 + 24.5%) - 86.4% = 0.381, is at the Rest of State price (`secondary_*`).
  - RG&E: the NYCA requirement, 124.5% of peak (IRM 24.5%, 2026-27).
  - ISO-NE (Eversource CT, United Illuminating): a load-serving entity's Capacity Load Obligation is its share of the annual system peak × the Installed Capacity Requirement. `obligation_factor` 1.151 = ICR 31,591 MW / reference 50/50 peak 27,440 MW (FCA 18). Net of the Hydro-Québec interconnection capability credits (1,041 MW) it is 1.113; which one load bears is `_VERIFY`. Connecticut has no local sourcing requirement and clears at the Rest-of-Pool price.
- **(b) Accreditation** by resource type, replacing the programs derates in this formulation.
  - PJM 2028/29 ELCC (effective load-carrying capability: how much a resource counts at peak) class ratings: Demand Resource 91%; storage 4-hr 59%, 6-hr 68%, 8-hr 71%, 10-hr 78%; fixed-tilt solar 7%.
  - NYISO 2026-27 capacity accreditation factors (NYC Locality for Con Edison, Rest of State for RG&E; CHPE-In central and high, CHPE-Out low): Special Case Resources 70.2% / 74.2%; 4-hour storage 84.4% / 84.6%; solar 11.2% / 13.9%.
  - Storage is read from `accr_storage_by_duration` at `storage_duration_hr` (4).
  - Managed EV charging has no class in either market and keeps the programs derate (`_VERIFY`).
  - ISO-NE: the PJM class ratings are used as a proxy (`_VERIFY`). ISO-NE moves to marginal-reliability-impact accreditation with the prompt auction (Capacity Auction Reforms; FERC accepted Phase 1 on 30-31 March 2026; seasonal accreditation, Phase 2, to be filed by end-2026). Connecticut class values were not located.
  - Efficiency: `accr_ee` 1.0 of its measured peak kW, because efficiency lowers the load forecast. PJM removed Energy Efficiency Resources from the supply side from the 2026/27 BRA (FERC, ER24-2995) and recognises efficiency in the forecast. `_VERIFY`.
- **(c) Coincidence.** Distribution peak shaving is not automatically credited at system peak.
  - `system_coincidence` is the utility's zone peak at the RTO / NYCA coincident peak per MW of its own peak: Con Edison 0.976 (Zone J NCP/CP 1.0245), RG&E 0.968 (Zone B 1.0336), Dominion 0.975 (DOM 24,569 / 25,193 MW), Pepco 0.963 (PEPCO 5,778 / 6,003 MW).
  - The share of flexible MW dispatched for local relief (the deferral layer's `locational_match`) also carries `local_coincidence` (0.5 / 0.75 / 1.0, `_VERIFY`; low from the ~50% cross-use credit in Brattle's New York study).
  - `local_coincidence` is an external driver in the tornado, from 0.5 (low) to 1.0 (high). The other capacity inputs with a range also enter the tornado as external drivers: the CHPE-out / CHPE-in New York levels and PJM's auction lag. They enter only while the formulation is `'avoided_obligation'`.
  - Efficiency's peak kW are measured on the summer peak-period basis, so efficiency takes accreditation only.
- **(d) Auction lag.** The obligation falls `auction_lag_years` after the load does.
  - PJM: 3 (the BRA runs about three years ahead; high level 1, the year after a lower Peak Load Contribution).
  - NYISO: 1 (each capability year's requirement is set from the previous summer's weather-normalised peak).
- **(e) Long-run price.** The avoided price follows the long-run path whatever `price_path` the bill line uses (`avoided_price_path: 'long_run'`): Net CONE $192.7/kW-yr (PJM, 2025 $) and $200/kW-yr (New York, 2025 $) by 2040, as in 3.6.
- **(f) Price suppression** (`suppression_enabled`, off by default and never in the central case). It is a separate sensitivity:

  ```
  suppression_t = suppression_elasticity x (obligation MW / market_peak_mw) x avoided price_t x fade_t x remaining obligation_t
  fade_t        = linear from 1 at suppression_start_year to 0 at long_run_year (new entry restores the long-run price)
  ```

  - NYISO elasticity = 1 / (zero-crossing point - 1): NYC 5.56 (118%), NYCA 8.33 (112%).
  - PJM 16.7 (`_VERIFY`): the slope of PJM's proposed RTO VRR curve, 0.5 x cap between 101.5% and 104.5% of the requirement. It starts in 2030, after the auctions that cleared at the cap.

**Results** (utility-forecast pace; 2026–2050; customer savings and the capacity layer are $B undiscounted nominal, with NPV 3% (net present value, discounted at 3% a year) in 2026 $ in brackets; monthly savings are the average residential bill, $/month nominal). The capacity layer is the capacity cost avoided: firm MW x price in the embedded formulation, and the avoided obligation in the default. `engine.layers.capacity_formulation_table()` produces it.

| Utility | Scenario | Formulation | Capacity layer $B (NPV 3%) | Customer savings $B (NPV 3%) | Monthly saving 2035 ($) | Monthly saving 2050 ($) |
|---|---|---|---|---|---|---|
| Con Edison | Cautious | embedded | 1.38 (0.86) | 10.34 (6.21) | 4.02 | 23.79 |
| Con Edison | Cautious | avoided obligation (default) | 2.29 (1.40) | 10.98 (6.59) | 4.33 | 25.07 |
| Con Edison | Central | embedded | 6.82 (4.23) | 37.18 (21.88) | 13.48 | 106.69 |
| Con Edison | Central | avoided obligation (default) | 10.45 (6.37) | 39.73 (23.38) | 14.64 | 112.09 |
| Con Edison | Ambitious | embedded | 9.79 (6.16) | 59.52 (35.30) | 21.06 | 151.98 |
| Con Edison | Ambitious | avoided obligation (default) | 14.61 (9.01) | 62.89 (37.30) | 22.63 | 158.67 |
| RG&E | Cautious | embedded | 0.04 (0.03) | 1.53 (0.94) | 4.35 | 15.32 |
| RG&E | Cautious | avoided obligation (default) | 0.13 (0.08) | 1.59 (0.98) | 4.47 | 15.75 |
| RG&E | Central | embedded | 0.60 (0.37) | 4.03 (2.45) | 10.37 | 42.65 |
| RG&E | Central | avoided obligation (default) | 1.68 (1.02) | 4.78 (2.90) | 11.65 | 48.96 |
| RG&E | Ambitious | embedded | 0.73 (0.46) | 6.51 (3.98) | 16.04 | 62.42 |
| RG&E | Ambitious | avoided obligation (default) | 1.98 (1.20) | 7.38 (4.51) | 17.55 | 69.51 |
| Dominion | Cautious | embedded | 1.27 (0.79) | 5.59 (3.46) | 2.61 | 5.28 |
| Dominion | Cautious | avoided obligation (default) | 1.67 (1.00) | 5.87 (3.60) | 2.60 | 5.46 |
| Dominion | Central | embedded | 6.30 (3.95) | 18.23 (11.02) | 5.82 | 15.52 |
| Dominion | Central | avoided obligation (default) | 7.25 (4.37) | 18.90 (11.31) | 5.63 | 16.05 |
| Dominion | Ambitious | embedded | 18.66 (11.74) | 48.16 (28.96) | 13.34 | 40.08 |
| Dominion | Ambitious | avoided obligation (default) | 20.47 (12.36) | 49.43 (29.40) | 12.62 | 41.33 |
| Pepco MD | Cautious | embedded | 0.59 (0.37) | 2.07 (1.32) | 6.20 | 10.42 |
| Pepco MD | Cautious | avoided obligation (default) | 0.85 (0.51) | 2.31 (1.46) | 6.18 | 11.56 |
| Pepco MD | Central | embedded | 1.09 (0.69) | 4.05 (2.54) | 10.17 | 22.79 |
| Pepco MD | Central | avoided obligation (default) | 1.29 (0.78) | 4.19 (2.60) | 9.96 | 23.58 |
| Pepco MD | Ambitious | embedded | 1.86 (1.18) | 5.55 (3.47) | 13.08 | 30.68 |
| Pepco MD | Ambitious | avoided obligation (default) | 2.10 (1.28) | 5.72 (3.54) | 12.63 | 31.78 |

- **The earnings opportunity grows with the avoided capacity.** The avoided-obligation formulation raises customer savings in every utility and scenario:
  - Con Edison Central: +$2.5B, from $37.2B to $39.7B.
  - RG&E Central: +$0.8B.
  - Dominion Central: +$0.7B.
  - Pepco Central: +$0.1B.
  - Shared savings earnings rise too, since capacity is in the pool.
- **Two forces work in opposite directions.**
  - Upward: the long-run price ($200/kW-yr by 2040, against today's NYISO Rest of State $72/kW-yr and the PJM cap of $122/kW-yr) and, in New York, the reserve margin in the obligation.
  - Downward: lower accreditation (NYISO Special Case Resources 70–74% against the 92% PJM proxy), coincidence (0.96–0.98, and 0.75 for locally dispatched MW) and the auction lag.
  - In PJM, the 3-year lag and the 0.926 FPR outweigh the price path until the early 2030s. Dominion's and Pepco's 2035 monthly savings are slightly lower ($0.02–0.72) and their 2050 savings higher. In New York, both years are higher.
- **Price suppression** (Central, sensitivity only; undiscounted nominal):

  | Utility | Price suppression $B | Added to customer savings $B |
  |---|---|---|
  | Con Edison | 3.84 | 2.69 (to $42.42B) |
  | Dominion | 1.35 | 0.95 |
  | Pepco | 0.04 | 0.03 |
  | RG&E | 0.03 | 0.02 |

  For Con Edison it is over a quarter of the capacity layer ($14.3B with suppression), which is why it stays out of every scenario.

**ISO-NE (Connecticut).**
- **Price:** FCA 17 (2026/27) $2.59/kW-month = $0.03108M per MW-year, the bill-line price. FCA 18 (2027/28) $3.58 = $0.04296M is a published price from 2027 (published-plan basis).
- **Long-run price:** FCA 18 Net CONE, $9.078/kW-month = $0.1089M per MW-year (2027/28 $), reached by 2040.
- **Auction lag:** 3 / 1 / 0 years. FCA 17 and 18 fix 2026/27 and 2027/28 forward; prompt annual auctions from 2028/29 react within the year. The engine applies one lag from 2026, so central is 1.
- **Growth:** flat real (inflation). The ISO-NE 2026 CELT has the winter peak growing ~2.9% a year (2026-2035) against ~0.7% for summer. 3% a year real is the high level.
- **Results:** capacity cost avoided, Central, is $0.87B (Eversource CT) and $0.28B (UI), undiscounted nominal. The 2026 price is about a quarter of PJM's, which limits the capacity value until the long-run price is reached.

**Double-count guard: efficiency and demand response that clear in the FCM.** Connecticut's C&LM budget counts ISO-NE Forward Capacity Market revenue (~$15.2M a year statewide in 2025) as a funding source. That revenue comes from today's efficiency and active demand response, which are in BAU in both cases, so it is unchanged. Only efficiency and flexible MW above BAU earn the avoided-obligation value. ISO-NE reconstitutes FCM-cleared efficiency into the load forecast, so each MW either clears as a resource and is paid, or lowers the forecast; it is never both. The program cost per kWh (`ee_levelised_cost_kwh`) is gross: it is not net of any FCM revenue. So the incremental MW's capacity value is counted once. If the utility bid them into the FCM instead, the payment would replace this value rather than add to it.

**Calibration.**

*Brattle, New York's Grid Flexibility Potential (Jan 2025, Vol. I, p.8):*
- Generation capacity is $2,029M a year of avoided cost in 2040 (2024 $), for 8.5 GW of cost-effective potential measured at the NYISO-coincident peak. That is $239/kW-yr per coincident kW.
- At the long-run price, the avoided-obligation formulation gives $213/kW-yr (Con Edison, which buys the Rest of State share at the lower price) and $243/kW-yr (RG&E) per obligation kW in 2040 (2024 $, deflated at 2.5%). Per kW, the two match.
- The difference is in the MW:
  - Brattle's potential is 21% (Con Edison) and 24% (RG&E) of each utility's NYISO-coincident summer peak (p.46).
  - In 2040, Central's accredited obligation is 12.4% of Con Edison's peak and 20.5% of RG&E's (18.3% / 24.9% Ambitious).
  - Combined, Con Edison and RG&E carry 44% of the 2026 NYCA coincident peak, so a pro-rata share of Brattle's $2,029M would be $892M. The model gives $400M Central and $575M Ambitious (45% and 64%).
- Under the embedded formulation the same 2040 figure is $232M Central, at $114/kW-yr (Con Edison) and $69/kW-yr (RG&E): today's price grown with inflation, without the reserve margin.
- The avoided-obligation formulation therefore moves the New York capacity value per kW to Brattle's level. The remaining gap is the MW of flexibility the scenarios assume, not the price.

*Brattle, An Assessment of Electrification Impacts on the Pepco DC Distribution System (Nov 2025):*
- The study is distribution-only. It "does not assess value to the bulk system", so it offers no calibration point for the capacity layer.
- It finds flexibility reduces Pepco DC's 2025–2040 load-growth capex by $58–868M (2025 $; 4–54%), with value concentrated where overloads are short (2–5 hours a day, 1–6 days a year).
- It supports the coincidence adjustment: the system is winter-peaking, while managed EV charging relieves mainly summer-peaking locations, so distribution relief and system-peak relief do not coincide in full.

**Limitations.**
- The obligation factors are applied to the price inputs as given. The NYISO ICAP-to-UCAP (installed to unforced capacity) translation is not modelled (`_VERIFY`).
- Con Edison's Rest of State price is RG&E's 2026 price input (`_VERIFY`), held in a fixed ratio to the NYC price.
- `local_coincidence` is an assumption pending feeder load shapes.
- PJM accreditation is for 2028/29. Ratings change each auction, and most fall as winter risk grows (2029/30: 4-hour storage 57%).
- Price suppression uses a linear demand-curve slope with fixed supply. It ignores the PJM cap and floor beyond 2029 and any supply response before `long_run_year`.

### 3.7 Wholesale energy (layer 6)

**What it represents.** Flexible resources shift energy from expensive on-peak hours to cheaper off-peak hours.

**Calculation.**

```
spread_t       = spread_mwh x (1 + supply_energy_growth)^t
storage value  = spread_t - offpeak_price_t x (1 / storage_rte - 1)        (round-trip losses)
wholesale_t    = sum_k incremental MW_k x mwh_per_mw_k x value_k / 1e6     ($M)
```

The three value layers (3.7–3.9) apply only in shared savings once programs are active (programs layer on, from the transition year). Their firm MW include efficiency MW, whether or not the capacity layer is on.

**Bill effect.** The supply-energy lines fall by `(wholesale + loss energy value) / (supply rate x sales)`.

**Inputs.**
- `spread_mwh`: the PJM 2025 State of the Market on/off-peak spread; New York uses it as a `_VERIFY` proxy.
- `mwh_per_mw_*`: NYISO 2025 demand-response event-hours for demand response and other DER; managed EV and storage are `_VERIFY`.
- `offpeak_price_mwh`, `storage_rte` (0.85).
- `in_pool` (whether the value counts in the shared-savings pool).

**Double counting.**
- Only incremental flexible MW, so the layer is zero without them (tested).
- Efficiency's lower energy purchases are already counted as lower usage (and as the efficiency energy line in 4.2), so they are not added here.

**Limitations.**
- One spread for all hours and years.
- No interaction with capacity dispatch hours.

### 3.8 Avoided transmission (layer 7)

**What it represents.** Lower peak demand lowers transmission cost.

**Calculation.**

```
firm MW_t        = min(firm flexible MW + EE MW, peak)
transmission_t   = firm MW x cost_kw_yr x 1000 x avoidable_share x (1 + transmission_growth)^t / 1e6     ($M)
```

**Bill effect** (`bill_basis`: which bill lines the saving lowers):
- **'delivery'** (New York, where transmission is recovered in delivery rates): the distribution lines fall by `transmission_t / wires RR`.
- **'transmission_lines'** (PJM): the transmission lines fall by `transmission_t / (peak x cost_kw_yr x 1000 x growth / 1e6)`.

**Inputs.**
- `cost_kw_yr`: Con Edison $40.67 and RG&E $3.25 per kW-year (marginal transmission cost, BCA handbooks); Dominion $85.19 and Pepco $60.49 per kW-year (PJM network service rates, June 2026).
  - **RG&E's $3.25 was checked, and is kept and documented.** It is correctly transcribed: the NYSEG/RG&E Electric BCA Handbook v5.0 (June 2025), Table 9-3, still prescribes it (NYSEG $4.18), from the 2015 marginal cost of service studies, "the last accepted MCOS results".
  - **Why it is about one-twelfth of Con Edison's value:** marginal cost studies measure load-related expansion. RG&E's 115 kV system had little load-driven transmission investment in the 2015 study, while Con Edison's serves dense, growing NYC load areas.
  - **Escalation:** Con Edison's value is escalated to 2026 as its handbook directs; RG&E's is not, because its handbook gives no rule.
  - **No update yet:** no 2025 RG&E MCOS update (under the August 2024 PSC order) was located.
- `avoidable_share` (the share of the cost per kW that a lower peak avoids): New York 1.0. PJM 0 / 0.5 / 1.0, because network service rates are average embedded costs: a lower peak shifts cost within the zone in the short run and avoids upgrades in the long run. `_VERIFY`.
- `bill_basis`, `in_pool`.

**Limitations.** PJM avoided transmission is a range, not a point estimate.

This is the `'single'` formulation. It was the default until 2 November 2026 and remains an option (`transmission.formulation = 'single'`). 3.8a describes the default.

### 3.8a Avoided transmission: split formulation (default)

`transmission.formulation = 'split'` (the default since 2 November 2026, with the avoided build on) replaces the single value with two components, reported separately:
- **(b) transmission upgrades deferred** counts in customer savings, the bills and the shared-savings pool.
- **(a) the lower share of zonal transmission costs** is a cost shift. It is reported as its own line and kept out of all three.

`'single'` (3.8) remains an option. v1.0, CORRECTED and the three pins are unchanged. `transmission_formulation_table()` compares single with split, (b) off and on.

**Jurisdiction.** Transmission rates and returns are FERC-jurisdictional:
- **PJM:** network service rates are each zone's annual transmission revenue requirement under FERC formula rates, divided by network service peak load.
- **New York:** the transmission revenue requirement is set in the state rate case, but its return and planning sit within the FERC-approved NYISO tariff.

The state mechanism can therefore **count avoided transmission charges as customer savings** and include them in the shared-savings pool (here, (b) only). It **cannot set the utility's transmission return**, change the zonal revenue requirement or direct the RTO's planning. The ROE lever (3.11) applies to the distribution business only.

**(a) Allocation effect (`allocation_effect`).** A lower peak lowers these customers' share of existing transmission costs.
- **PJM** (`'zonal_share'`): the zone's ATRR (annual transmission revenue requirement) is fixed by formula rate (a FERC rate reset each year from actual costs) and shared by network service peak load. With the utility's share s of the zone peak Pz and a peak reduction d (firm flexible MW + efficiency MW, as in 3.8):

```
saving_t        = ATRR_t x (s - (s x Pz - d) / (Pz - d)) = rate_t x d x (1 - s) x Pz / (Pz - d)      ($M)
cost shifted_t  = saving_t                    (paid by the other customers in the zone through a higher zonal rate)
rate_t          = cost_kw_yr x 1000 x transmission index_t / 1e6;   Pz = peak_t / s
```

  The inputs are derived from PJM's June 2026 ATRR and NITS (network integration transmission service) rate sheet (zone NSPL, network service peak load, = ATRR / rate):
  - DOM: zone NSPL 24,678 MW, with Dominion's share 0.810 (20,000 MW). The rest is co-operative and municipal load.
  - PEPCO: zone NSPL 6,016 MW, with Pepco MD's share 0.606 (3,644 MW). The rest is Pepco DC and SMECO.

  The share is held constant. Only (1 − s) of the gross reduction is a saving to these customers; the rest is recovered from them through the higher rate.

  **Reported separately, outside the pool and the headline.** Nothing is avoided: the fixed zonal cost moves to other customers in the zone. So (a):
  - is reported as its own line, **"lower share of zonal transmission costs"** (`transmission_allocation_m`), with the **cost shifted to other zone customers** (`transmission_cost_shifted_m`) alongside;
  - is **never in the shared-savings pool**, so the utility earns nothing on it;
  - is **not in headline customer savings or the bills**.

  `allocation_in_headline` (setting, off by default) adds it to the bills and headline customer savings, for comparison only. It never enters the pool.
- **New York** (`'none'`): the utility's transmission revenue requirement is recovered from its own delivery customers, so a lower peak reallocates it among them. (a) is 0.
- **ISO-NE** (`'zonal_share'`, New England as the zone; Eversource CT, United Illuminating): Regional Network Service pools every transmission owner's PTF revenue requirement (FERC formula rates) and charges it by monthly network load at the 12 coincident peaks.
  - RNS rate from 1 January 2026: $183.71/kW-year. Regional ATRR $3,331.2M; 2024 12CP load 18,133 MW (`zone_nspl_mw`, reference).
  - Each utility's share: its 2026 peak / the ISO-NE 2026 CELT summer peak (25,228 MW). CL&P 0.183, UI 0.050 (`derived`; a proxy for the 12CP share, which was not located).
  - The same formula as PJM, × `allocation_peak_factor` (ISO-NE only; default 1.0, so PJM is unchanged). RNS is allocated on the 12 monthly coincident peaks, while the engine measures the reduction on the annual peak, and most demand response dispatches only in summer. The factor is the share of the annual-peak reduction that lowers the 12CP basis:
    - low 0.25: summer-only dispatch, 3 of 12 months;
    - central 0.5;
    - high 1.0: storage and managed load across all months.

    It is `_VERIFY`. It applies to the cost-shift line only. (a) is reported only, never in savings or the pool.
  - No engine change was needed: `'zonal_share'` is generic.

**(b) Transmission upgrades deferred (avoided build).** This is the deferral of load-driven transmission investment.
- **Investment base (`transmission_plan_capex()`):**
  - PJM: from the published transmission rate base path (`bau_plan.transmission_plan_rate_base_m`), with investment = RB_t − RB_{t−1} × (1 − 3.5% decay). That gives Dominion about $2.4–2.9B a year (2026–2030) and Pepco $325–400M a year. Beyond the plan it grows at `transmission_growth`.
  - ISO-NE: from the utility's transmission rate base path, as for PJM.
    - Both utilities: customers pay the pooled rate, so each path is scaled to the 2026 RNS forecast ($185.28 2025, $183.71 2026, then ~$186 / $197 / $210 / $220 per kW-year to 2030). Each starts from the utility's own transmission base (CL&P ~$4.6B rate base at YE 2025; UI $1.10B Form 1 net plant) × RNS_t / RNS_2025 × peak growth. After 2030 the line tapers to `transmission_growth` by `taper_year`.
    - The implied investment stands for the utility's share of regional PTF additions. UI's own additions would grow its line ~13% a year.
    - Local network service (CL&P-specific, part of the TAC) is not quantified separately; it moves with the RNS rate.
    - BAU transmission line, average bill $/month: CL&P $35.35 (2026), $42.33 (2030), $72.80 (2050); UI $34.11, $40.84, $69.92.
  - New York (the plan includes transmission): `tx_capex_share_of_plan` × the published electric capital plan. The share is the transmission share of T&D net plant growth 2021–2025 (FERC Form 1: the annual financial report utilities file with FERC): Con Edison 0.304, RG&E 0.205 (derived).
- **Load-driven share (`load_driven_share`, low / central / high).** Retirement, market efficiency, equipment condition and public policy projects are excluded.

| Utility | Low / central / high | Status | Derivation |
|---|---|---|---|
| Dominion | 0.300 / 0.667 / 0.746 | derived | PJM 2024 RTEP (Regional Transmission Expansion Plan) Report (Fig. 1.9, Fig. 3.4): baseline $5.92B (deliverability $5.515B, driven by load growth in the Dominion zone and amplified by >2 GW of deactivations); supplemental $9.07B (customer service $4.49B, equipment condition $3.3B, operational flexibility $0.11B, multi-driver $1.17B). Low = customer service / total; central = (baseline deliverability + customer service) / total; high = also multi-driver. PJM-wide shares, dominated by the DOM zone. |
| Pepco MD | 0 / 0 / 0.300 | derived | 2024 RTEP, Maryland/DC tables: no PEPCO-zone baseline projects, and its supplemental projects are all equipment-condition breaker replacements. High = the PJM-wide customer-service share. |
| Con Edison | 0.25 / 0.5 / 0.75 | derived (count) | 2025 LTP (local transmission plan): NYC needs have four drivers (load, retirements, no new generation, loss-of-generation design basis), so low = 1 of 4. Three of four named projects are load-serving substations (Brooklyn Clean Energy Hub, Eastern Queens, Sunset Park), so high = 3 of 4. No project costs are published, so these are counts, not dollars. |
| Eversource CT, UI | 0 / 0.05 / 0.20 | derived | ISO-NE 2026 RNS Rate Overview and Forecast: 2026 regional PTF additions ~$1,096M = $56M Regional System Plan (reliability), $847M asset condition, $193M other, so at most ~5% is load-driven. High allows for local system plan projects and winter-peak growth. |
| RG&E | 0 / 0.25 / 0.5 | `_VERIFY` | Avangrid 2025 LTP, Rochester: the projects are reliability or CLCPA (New York's 2019 climate law: public policy). None is attributed to load, so the share is not derivable. |

- **Deferral.** In proportion to the planning-peak reduction from the scenario's firm flexibility and flexible large-load connections, lagged by `planning_lag_years` (setting; 7, range 5–10):

```
f_t             = min(1, (firm flexible MW + flexible connection MW)_{t - lag} / (peak_t - peak_2026))
avoided capex_t = avoided_build_share x load_driven_share x investment_t x f_t
avoided RB_t    = avoided RB_{t-1} x (1 - 3.5%) + avoided capex_t
(b)_t           = avoided RB_t x (WACC + property tax) + 3.5% x avoided RB_{t-1}      (the model's carrying cost; x s for PJM)
```

- **Realisation by planner (`avoided_build_share`).** How much of the deferral the transmission planner acts on depends on who plans the transmission:

| Planner | Utilities | Cautious / Central / Ambitious | Status | Why |
|---|---|---|---|---|
| PJM (regional transmission, RTEP) or ISO-NE (Regional System Plan) | Dominion, Pepco, Eversource CT, UI | 0 / 0.5 / 1.0 | `_VERIFY` | The utility can only offer PJM a lower peak to count in its load forecast. Cautious: PJM doesn't count distribution-level flexibility. Central: half is credited (for example firm demand response and flexible connections accepted as load modifiers). Ambitious: fully credited. |
| The utility (local transmission) | Con Edison, RG&E | 0.5 / 0.8 / 1.0 | setting | The utility plans its local transmission itself, in its local transmission plan and rate case, alongside distribution. It gets the same realisation as the distribution growth-capex addressable share (`bau_plan.addressable_growth`) in each scenario. |

- **Planning lag (`planning_lag_years`, setting):** 7 years by default, range 5–10 (in the tornado). This is the time from a lower planning peak (load forecast) to the transmission investment it defers (plan, then in service). It applies to both kinds of planner.
- **Other zone customers (PJM):** they get (1 − s) of the avoided revenue requirement, reported as `transmission_build_other_zone_m`.
- **Context, not calibration:** PJM's 2024 RTEP Window 1 (approved February 2025: $4.65B regional + $1.27B local, driven by 10–15 GW of load growth, mainly data centres) and the Duke Nicholas Institute's *Rethinking Load Growth* (February 2025: about 76–126 GW of new load could connect with 0.25–1% curtailment). Neither sets a parameter.

**New York overlap fixed.** New York's published capital plans include transmission, so the deferral layer could defer the same spend as (b). With (b) on, the load-driven transmission spend (b) counts is taken out of the deferral layer's addressable growth capex before its addressable share applies. No plan dollar is deferred by both layers (tested).

**Bill effect and pool.** `transmission_avoided_m` is the transmission value counted in customer savings. By default it is (b) to these customers; it includes (a) only with `allocation_in_headline`.
- It lowers the transmission lines (PJM) or the delivery bill (New York).
- (b) enters the pool when `in_pool` is on, as in 3.8. (a) never does.
- `system_summary()` and the exports report (a) as "lower share of zonal transmission costs", with "cost shifted to other zone customers" alongside, outside customer savings.
- Export fields: `lower_share_of_zonal_transmission_costs_m` and `cost_shifted_to_other_zone_customers_m` (yearly), and the `_b` versions in each headline.

The outputs are:
- `transmission_allocation_m`, `transmission_cost_shifted_m`;
- `transmission_build_avoided_m`, `transmission_build_other_zone_m`;
- `transmission_avoided_capex_m`, `transmission_deferral_fraction`, `transmission_load_driven_capex_m`.

**Results, Central (default)** (utility-forecast pace; $B undiscounted nominal, NPV 3% in brackets; 2050 monthly saving, $ nominal, average residential bill). (a) is reported separately and is not in customer savings:

| Utility | Customer savings $B (NPV 3%) | of which (b) transmission upgrades deferred $B | Transmission capex avoided $B | (a) lower share of zonal transmission costs $B, reported separately | Cost shifted to other zone customers $B | (b) benefit to others in the zone $B | 2050 monthly saving $ |
|---|---|---|---|---|---|---|---|
| Con Edison | 39.73 (23.38) | 10.62 | 14.32 | 0.00 | 0.00 | 0.00 | 112.09 |
| RG&E | 4.78 (2.90) | 0.61 | 0.73 | 0.00 | 0.00 | 0.00 | 48.96 |
| Dominion VA | 18.90 (11.31) | 1.68 | 2.51 | 1.29 | 1.29 | 0.39 | 16.05 |
| Pepco MD | 4.19 (2.60) | 0.00 | 0.00 | 0.36 | 0.36 | 0.00 | 23.58 |
| Eversource CT | 4.77 (2.94) | 0.01 | – | 0.75 | 0.75 | – | 19.66 |
| United Illuminating | 0.67 (0.42) | 0.00 | – | 0.29 | 0.29 | – | 7.80 |

**All scenarios:** single (the earlier default) against split, (b) off and on (the default):

| Utility | Scenario | Customer savings: single / split, (b) off / split, (b) on (default) | (b) transmission upgrades deferred | Transmission capex avoided | (a) lower share of zonal transmission costs, separate | Cost shifted to other zone customers | 2050 monthly saving: single / (b) off / (b) on |
|---|---|---|---|---|---|---|---|
| Con Edison | Cautious | 12.45 / 12.12 / 10.98 | 0.98 | 1.31 | 0.00 | 0.00 | 29.02 / 28.31 / 25.07 |
| Con Edison | Central | 40.39 / 38.78 / 39.73 | 10.62 | 14.32 | 0.00 | 0.00 | 111.10 / 107.33 / 112.09 |
| Con Edison | Ambitious | 60.16 / 57.84 / 62.89 | 18.00 | 23.35 | 0.00 | 0.00 | 146.21 / 141.26 / 158.67 |
| RG&E | Cautious | 1.59 / 1.59 / 1.59 | 0.05 | 0.14 | 0.00 | 0.00 | 14.60 / 14.58 / 15.75 |
| RG&E | Central | 4.56 / 4.54 / 4.78 | 0.61 | 0.73 | 0.00 | 0.00 | 43.88 / 43.63 / 48.96 |
| RG&E | Ambitious | 7.04 / 7.02 / 7.38 | 0.80 | 0.94 | 0.00 | 0.00 | 62.22 / 61.92 / 69.51 |
| Dominion VA | Cautious | 6.32 / 5.87 / 5.87 | 0.00 | 0.00 | 0.25 | 0.25 | 5.78 / 5.46 / 5.46 |
| Dominion VA | Central | 19.97 / 17.72 / 18.90 | 1.68 | 2.51 | 1.29 | 1.29 | 16.32 / 14.83 / 16.05 |
| Dominion VA | Ambitious | 48.34 / 41.67 / 49.43 | 11.08 | 16.46 | 4.29 | 4.29 | 37.94 / 33.90 / 41.33 |
| Pepco MD | Cautious | 2.48 / 2.31 / 2.31 | 0.00 | 0.00 | 0.19 | 0.19 | 12.45 / 11.56 / 11.56 |
| Pepco MD | Central | 4.49 / 4.19 / 4.19 | 0.00 | 0.00 | 0.36 | 0.36 | 25.10 / 23.58 / 23.58 |
| Pepco MD | Ambitious | 6.24 / 5.72 / 5.72 | 0.00 | 0.00 | 0.64 | 0.64 | 34.26 / 31.78 / 31.78 |
| Eversource CT | Cautious | 2.10 / 1.89 / 1.89 | 0.00 | – | 0.24 | 0.24 | 8.33 / 7.76 / 7.76 |
| Eversource CT | Central | 5.40 / 4.77 / 4.77 | 0.01 | – | 0.75 | 0.75 | 21.24 / 19.62 / 19.66 |
| Eversource CT | Ambitious | 11.79 / 10.01 / 10.06 | 0.07 | – | 2.14 | 2.14 | 42.72 / 38.59 / 38.81 |
| United Illuminating | Cautious | 0.20 / 0.16 / 0.16 | 0.00 | – | 0.04 | 0.04 | 2.39 / 2.00 / 2.00 |
| United Illuminating | Central | 0.89 / 0.67 / 0.67 | 0.00 | – | 0.29 | 0.29 | 9.30 / 7.79 / 7.80 |
| United Illuminating | Ambitious | 2.30 / 1.76 / 1.77 | 0.00 | – | 0.74 | 0.74 | 22.80 / 19.02 / 19.05 |

Reading the results:
- **Con Edison:** (b) realises 0.5 / 0.8 / 1.0, like the distribution growth deferral it replaces in the overlap fix. Central customer savings are $39.73B against $40.39B under single: the overlap fix moves load-driven transmission out of the deferral layer, and (b) adds $10.62B. In Cautious, (b) realises less than the deferral layer did ($10.98B against $12.45B). In Ambitious it realises more ($62.89B against $60.16B).
- **RG&E:** the same mechanism, with a smaller transmission plan. Central $4.78B against $4.56B.
- **Dominion:**
  - (a) is $1.29B in Central, all of it a cost shift to other DOM zone customers, reported separately.
  - (b) adds $1.68B to customer savings, and other zone customers get a further $0.39B.
  - Customer savings are $18.90B against $19.97B under single, whose avoidable share counted part of the cost shift as a saving.
- **Pepco:** (b) is 0 at a load-driven share of 0. The $0.36B of (a) is a cost shift to Pepco DC and SMECO customers, now outside customer savings ($4.19B against $4.49B).
- **Connecticut:** (b) is small at a 5% load-driven share. (a) is the lower share of New England's pooled costs. It is scaled by the 12CP factor (central 0.5): $0.75B for CL&P and $0.29B for UI, against $2.42B and $0.91B on the annual peak. It is reported only. Single counts half its unscaled value as a saving (avoidable share 0.5), so single is above split.
- **Shared savings earnings** fall for Pepco in every scenario, and for Dominion in Cautious and Central, because (a) left the pool. Con Edison's fall in Cautious and Central, where the overlap fix removes more deferral than (b) adds back. They rise where (b) adds more: Con Edison and Dominion Ambitious, and RG&E Central and Ambitious.

### 3.9 Avoided distribution losses (layer 8)

**What it represents.** Losses rise with the square of current, so marginal losses at peak are several times average losses. Efficiency and peak reduction avoid them.

**Calculation.**

```
loss energy value_t = EE GWh x avg_loss_pct x (marginal_mult_energy - 1) x supply rate_t              ($M)
loss peak MW_t      = min(firm MW x avg_loss_pct x marginal_mult_peak, system peak - peak reduction)
loss peak value_t   = loss peak MW x capacity price_t                                                  ($M)
```

**Bill effect.**
- The energy value lowers the supply lines (with the wholesale value).
- The peak MW lower the capacity line.

**Inputs.**
- `avg_loss_pct`: Dominion 3.9% (PUR-2026-00164); Con Edison 4.24% and RG&E 6.93% (BCA handbooks); Pepco 4.92% (EIA-861).
- `marginal_mult_energy` 1.5 and `marginal_mult_peak` 3.0 (RAP 2011).
- `in_pool`.

**Double counting.**
- *Energy value.* Average losses are already in retail rates, and lower usage already avoids them. The energy value counts only the part *above* average, `(multiplier - 1)`, so it is zero at a multiplier of 1 (tested).
- *Peak value.* It uses the full peak multiplier. This is not a double count: capacity is bought per wholesale MW, while peak reduction is credited at the customer meter in the capacity layer, so the marginal losses on that reduction are additional capacity avoided.

**Limitations.** One average loss rate and fixed multipliers.

### 3.9a Additional savings objective (layer 8a)

**What it represents.** A savings commitment by the utility, a share of a stated base, found by means the model does not specify. Examples are procurement, work practices, operations, or planning beyond what the network model captures. A regulator might write it into a performance mechanism. It is off by default (`objective_pct` 0%), so every other result is unchanged.

**Calculation** (shared savings only, against this run's BAU, by default the published-plan BAU):

```
level_t    = objective_pct x min(1, (year - start + 1) / ramp_years) x fade_t      (from objective_start_year)
fade_t     = 1 if persistent; else 1 - (years since the ramp ended) / persistence, floored at 0
gross_t    = level_t x base_t
  base     = BAU distribution revenue requirement (default) | BAU other O&M (dist_opex) | BAU plan capex (capex_plan)
cost_t     = objective_cost_to_achieve_pct x gross_t
dist_revenue_requirement, dist_opex:  SS distribution RR falls by gross_t - cost_t that year
capex_plan:  SS capex falls by gross_t (rate base, depreciation, property tax and return follow, as for
             deferral); cost_t is expensed; the RR saving is tracked exactly on the rate base kept out
```

The net saving lowers what customers pay, so it enters the savings pool through the usual BAU − SS comparison. Earnings attributable to it are proportional to its pool contribution, as for the other layers. It appears as its own waterfall step and as the `additional_objective` source in the export's value flows (carved out of deferral). It is a policy driver in the tornado (low 0%, high 10%), and the export's `objective_sweep` re-runs each scenario at 0 / 2.5 / 5 / 10%.

**Inputs** (all settings): `objective_pct` (low 0 / central 0 / high 10%), `objective_base`, `objective_start_year` (2027), `objective_ramp_years` (3), `objective_persistence` ('persistent' or years), `objective_cost_to_achieve_pct` (20%). Scenarios may set the level through `levels` ('objective.objective_pct').

**Additional by assumption.** The objective is added on top of every other layer. The model cannot test whether it overlaps with them, because it does not say how the savings are found. A utility could meet part of an objective framed on capex with the same deferral the network model already counts, or part of one framed on O&M with work the programs layer already pays for. If so, adding the objective double counts.
- The objective is therefore a statement of what a commitment would be worth if it is genuinely additional, not evidence that it is.
- In regulation, it would need to be measured against the same BAU, with the utility showing that the savings come from something other than the measured layers.

**Why cost to achieve is netted off.** Savings found by unspecified means are not free. They take programmes, systems, staff and change management, and cost-saving commitments in rate plans typically come with costs to achieve. Netting them off before the savings reach the pool keeps the objective on the same footing as the other layers, which are all net of their costs. It also stops the utility earning a share of savings that customers paid to create. The 20% default is a setting, not a measurement.

**Limitations.**
- No behavioural or cost basis for the level.
- No interaction with the other layers (by assumption).
- The fade option is linear.

### 3.10 Shared savings mechanism and the pool (layer 9)

**What it represents.** The savings pool is the year's net saving to customers from the reform. The utility earns `utility_share` of it (30% at Central) as **shared savings earnings**. Customers keep the rest.

**Calculation.** `pool_basis: 'revenue_requirement'` is the only basis. The v1.0-style `'capex'` basis was removed from the layered model because it gave customers the capacity and value streams about 1.7 times over. Any other value raises an error.

```
what customers pay_t = core RR (wires RR + program RR) + program surcharge cost + capacity cost
pool_t = BAU pay_t - SS pay_t                           (excluding any ROE change; see 3.11)
       + wholesale + transmission + loss value           (value layers with in_pool = true)
net_t      = pool_t + carry_t-1
carry_t    = min(0, net_t)                              (negative pools carried forward, no interest)
earnings_t = utility_share x max(0, net_t)
```

**Recovery.**
- Earnings are added to the SS revenue requirement and recovered through the rider (3.4).
- Customers receive their share implicitly: they pay the lower costs and only the utility's share is added back.

**Inputs.** `utility_share` (low 0.40 / central 0.30 / high 0.10), `pool_basis`, each value layer's `in_pool`.

**Interactions.**
- The mechanism comes after the cost layers in the waterfall, so in the sequential pass all earnings fall on its step.
- `layer_contributions()` therefore reports **earnings attributable**: the full case's shared savings earnings split across the layers in proportion to each layer's contribution to the pool.
  - Each contribution is the change in the cumulative pool when the layer is added, which does not depend on the mechanism.
  - The undiscounted column uses undiscounted pool contributions; the NPV column uses NPV contributions.
  - The split sums to total earnings (tested).
- **Programs takes a negative share.** Its costs come before the savings they enable, so it lowers the pool. Con Edison Central: programs −$2.59B, deferral +$12.58B, capacity +$3.14B, transmission +$0.41B, losses +$0.31B, wholesale +$0.20B, load enabled −$0.24B; total $13.82B.
- This replaces an order-dependent split in which carry-forward gave programs, deferral and load enabled zero.

**Value creation is held constant across utility shares.** Changing `utility_share` changes only how the pool is divided. It sets shared savings earnings and the matching per-kWh rider. The flexible MW deployed, the reinforcement deferred, the capacity and energy avoided, the rate base and sales all stay the same. So customer savings plus shared savings earnings is identical at every share (exactly so in every year, since the pool itself does not depend on the share), and the utility-share sweep in the results export (0.20 / 0.30 / 0.40) shows the same value divided differently.

This is a simplification. The point of the mechanism is that the share is an incentive: a larger share should make the utility pursue flexibility, efficiency and right-sizing harder, procure more and site it better, and a smaller share should weaken that effort. Value created would then rise with the share, at least up to a point, so a larger share would not simply transfer value away from customers. The model has no behavioural link from the share to the program and deferral inputs. Those are set by the scenarios instead, so the sweep understates what a stronger incentive could unlock and overstates the customer cost of a larger share. Carry-forward also means earnings start later at every share, because early negative pools must be recovered first.

**Double counting.** Efficiency energy savings are not in the pool; they go wholly to customers. Each value stream enters the pool once.

**Limitations.**
- No performance corridor, cap or floor beyond carry-forward.
- No timing lag between saving and earning.

### 3.10a Mechanism options: fast start and customer dividend advance

Both options are off by default, and with the defaults every output is identical to a run without them (tested).

**Fast start** (`fast_start`). The first savings year becomes 2027 instead of `programs.transition_year` (2028). Programs become core business, flexible MW and efficiency begin, the value streams start, and the plan's right-sizing ramp starts a year earlier. Three optional near-term ramps (2026–2030) let each part be brought forward or held back on its own:
- `near_term_ramp_capacity` {year: fraction}: the share of the capacity credit counted in that year.
- `near_term_ramp_programs_mw` {year: fraction}: flexible MW as that fraction of the way from today's programs to the 2035 target, still subject to the ramp limit.
- `near_term_ramp_addressable` {year: fraction}: replaces the addressable-share ramp in that year and scales the growth cap.

**Customer dividend advance** (`advance_enabled`, default off). *Status: parked. Kept in the code and tested, with blocks in the exports for reference, but not part of the headline results or the explorer guide.* Customers receive part of their expected savings early, as a level annual bill credit, and repay it later through a rider. The defaults below apply once the advance is enabled.

```
base_t      = the sizing scenario's recoverable savings (advance off, every other input as given), from advance_start_year:
              bill_savings source (default): its positive customer saving vs BAU (all customers, after shared savings
              earnings, including efficiency energy and the value streams); pool source: its positive pool after carry-forward
size        = advance_sizing_fraction (0.5) x PV of base at the financing rate            (recoverable basis, default)
            = advance_sizing_fraction x NPV at 3% of the sizing scenario's customer savings (customer_savings basis)
credit_t    = C for advance_credit_years (5) from advance_start_year (2027); PV of credits (at the financing rate) = size
r           = advance_securitized_rate (4%, securitized, default) or the after-tax WACC (utility_regulatory_asset)
k0          = FV of credits / FV of base at r: the share of the recoverable savings scheduled for recovery (0.5 at default)
schedule_t  = schedule_t-1 x (1 + r) + credit actually paid_t - k0 x base_t
balance_t   = balance_t-1 x (1 + r) + credit_t - recovery_t
recovery_t  = min(amount needed to return to schedule, recovery source available that year, cap, balance due)
              bill_savings: a rider withholding part of customers' total saving that year; shared savings earnings unchanged
              pool: taken from the positive pool before sharing, so it also reduces shared savings earnings
cap         = customers' net saving that year (after the recovery and the credit) is never negative, and the
              average residential bill stays at or below BAU (the bill is recomputed to find the headroom)
true-up     = if the year-end balance is above schedule, next year's credit is paused
```

**Sizing on recoverable savings.** Sizing on recoverable savings, discounted at the financing rate, means the scheduled recovery is the fixed share k0 = `advance_sizing_fraction` of what the sizing scenario actually makes available. So the advance clears by 2050 when that scenario comes true (tested). The earlier sizing on the NPV at 3% of customer savings remains an option. It could not be repaid from the pool, for two reasons:
- Customer savings include efficiency energy savings outside the pool.
- The balance accrues at a higher rate than the 3% used for sizing.

**Recovery fix.** The schedule now tracks the credits actually paid. Before, it assumed every planned credit was paid. When the true-up paused a credit, the actual balance fell below the scheduled balance, so "recover what is needed to return to schedule" asked for nothing until interest closed the gap. That is why Con Edison's pool-based run recovered nothing in 2029–2037 while the pool was positive: a $7M shortfall in 2028 (the pool that year was $8M) paused the 2029 credit. It was neither the cap nor carry-forward.

**What the utility earns.** Under `utility_regulatory_asset`, the return on the balance (`advance_return_m`) is the utility's, reported separately from shared savings earnings. Under securitisation (financing with low-cost bonds repaid by a dedicated charge; the default) it is interest to bondholders. With bill-savings recovery, shared savings earnings are unaffected.

**Identities (tested).**
- Credits + financing − recoveries = the balance left in 2050.
- At the financing rate, the PV of credits = PV of recoveries + PV of that balance.

**What it costs customers.** Customers pay the financing cost of receiving their own savings earlier. Undiscounted customer savings are lower with the advance, although the credits are front-loaded.

**Stress case** (`advance_stress` in the export: sized on Central, realised Cautious). The larger credits run ahead of what Cautious delivers, so the true-up pauses the credits after the first years. That keeps the balance recoverable, and the export reports any balance left in 2050.

**Limitations.**
- The credit term (5 years) is the model's choice.
- The cap applies to all customers together and to the average residential bill, not to each class separately.
- An unrecovered balance is reported, not assigned.

### 3.10b Customer allocation of the pool: residential vs non-residential (`customer_allocation`)

**Rule: costs follow the benefits they buy; only savings are reallocated.**

**What it represents.** How the customers' share of the shared savings pool is divided between residential and non-residential customers. How a regulator divides it is a rate-design choice. The model offers three options through `mechanism.customer_allocation`, a setting:
- `'by_sales'` (default; the earlier method): by the residential share of sales (EIA-861 2024: Con Edison 26.0%, RG&E 41.4%, Dominion 30.7%, Pepco 41.0%).
- `'per_customer'`: equal per customer, by EIA-861 2024 class customer counts (`residential_customers`, `nonresidential_customers`). The residential share is Con Edison 84.0%, RG&E 89.6%, Dominion 89.5% and Pepco 91.7%.
- `'custom'`: a residential share between 0 and 1 (`custom_residential_share`; the export uses 0.5).

**What moves and what does not.** Only the savings are reallocated: the network revenue-requirement reduction net of shared savings earnings, in years when it is positive.
- **The network saving** is the distribution reduction plus, in New York (Con Edison, RG&E), the **transmission upgrades deferred** (3.8a). New York transmission is in the utility's own rate base and recovered in its delivery rates, alongside distribution, so the commission sets its class allocation in the same rate case.
- **PJM deferred transmission** (Dominion, Pepco) is recovered through the separate transmission lines (PJM network service rates), so it stays with the load-following savings.

Everything else stays allocated by sales under every option:
- **Program costs:** flexible and efficiency spend, including the amortisation of and return on capitalised amounts. The efficiency energy savings those costs buy are allocated by usage, so the costs are too.
- **Load-following savings:** capacity, PJM transmission, losses, wholesale energy and efficiency energy. They follow load through existing rates (capacity per kW of peak contribution, PJM transmission by network service peak load, supply and losses per kWh). Moving them would mean redesigning those rates, not the shared-savings mechanism.
- **A negative network remainder:** in a year where the network reduction net of earnings is negative, the shortfall is allocated by sales.

The network saving net of the utility's earnings is the part that a shared-savings mechanism returns through delivery rates and riders whose class allocation the commission sets. That is the part it could choose to return differently.

**Calculation.**

```
network net of earnings N_t = (BAU - SS) distribution RR + transmission upgrades deferred (New York only)
                              - shared savings earnings (incl. any dividend advance recovery, a parked option, 3.10a)   ($M)
reallocated P_t             = max(0, N_t)
residential_t               = (customer savings_t - P_t) x sales share + P_t x residential share (option)
non-residential_t           = customer savings_t - residential_t
                              (by_sales: customer savings x sales share and x (1 - sales share), exactly as before)
residential bill (engine)   = + allocation adjustment line (delivery rider category, per kWh):
                              -(residential share / sales share - 1) x P_t / sales_t x benchmark kWh  (x usage on the average bill)
non-residential $/month     = non-residential_t / (non-residential customers x 12)     (counts held at 2024)
```

**The setting drives the engine.**
- The residential bill carries the adjustment line, so the average and benchmark bills, the headline monthly savings and (when the parked dividend advance is switched on, 3.10a) its residential bill cap all use the allocated residential bill.
- The value flows split residential and business by the option.
- Totals, the pool, earnings and every value source are unchanged.
- With `'by_sales'` there is no adjustment line, so every output is identical to before.
- `customer_allocation()` reports a run's split, and `customer_allocation_table()` runs every scenario under each option (notebook Section 13, 3d).
- The export's `allocation_sweep` carries yearly bills, value flows split by class, and headline savings by class for each option.

**Results** (Central, utility-forecast pace; $B undiscounted nominal, NPV 3% in 2026 $ in brackets; $/month nominal; all scenarios in the CHANGELOG):

| Utility | Scenario | Option | Residential share of reallocated savings | Residential $B (NPV 3%) | Non-residential $B (NPV 3%) | Residential bill saving 2035 / 2050 ($/month) | Non-residential saving per customer 2035 / 2050 ($/month) |
|---|---|---|---|---|---|---|---|
| Con Edison | Central | by sales (default) | 0.260 | 10.34 (6.09) | 29.39 (17.30) | 14.64 / 112.09 | 68.80 / 469.64 |
| Con Edison | Central | per customer | 0.840 | 27.00 (15.67) | 12.73 (7.72) | 20.93 / 180.43 | 43.89 / 171.45 |
| Con Edison | Central | custom 0.5 | 0.500 | 17.23 (10.05) | 22.50 (13.34) | 17.24 / 140.34 | 58.51 / 346.38 |
| RG&E | Central | by sales (default) | 0.414 | 1.98 (1.20) | 2.80 (1.70) | 11.65 / 48.96 | 144.93 / 504.88 |
| RG&E | Central | per customer | 0.896 | 3.45 (2.08) | 1.33 (0.82) | 19.27 / 84.59 | 77.27 / 221.53 |
| RG&E | Central | custom 0.5 | 0.500 | 2.24 (1.36) | 2.54 (1.54) | 13.02 / 55.35 | 132.81 / 454.12 |
| Dominion | Central | by sales (default) | 0.307 | 5.81 (3.48) | 13.09 (7.84) | 5.63 / 16.05 | 77.11 / 372.46 |
| Dominion | Central | per customer | 0.895 | 10.20 (6.05) | 8.70 (5.26) | 7.68 / 26.46 | 57.78 / 228.79 |
| Dominion | Central | custom 0.5 | 0.500 | 7.25 (4.32) | 11.65 (6.99) | 6.30 / 19.46 | 70.78 / 325.39 |
| Pepco MD | Central | by sales (default) | 0.410 | 1.72 (1.07) | 2.47 (1.53) | 9.96 / 23.58 | 125.07 / 324.51 |
| Pepco MD | Central | per customer | 0.917 | 2.11 (1.30) | 2.07 (1.30) | 11.34 / 30.13 | 110.93 / 253.08 |
| Pepco MD | Central | custom 0.5 | 0.500 | 1.79 (1.11) | 2.40 (1.49) | 10.20 / 24.74 | 122.56 / 311.87 |

**Reading the results.**
- **Per-customer allocation raises residential savings for every utility.** Residential customers' share of customers exceeds their share of sales, and only positive savings move.
  - Con Edison Central: $10.3B → $27.0B, and the 2050 residential bill saving $112 → $180/month.
  - Dominion: $5.8B → $10.2B.
  - RG&E: $2.0B → $3.5B.
  - Pepco: $1.7B → $2.1B.
- **Counting New York's deferred transmission as network saving** raises Con Edison's Central per-customer residential savings from $20.8B to $27.0B and RG&E's from $3.2B to $3.5B. By-sales results, totals and the PJM utilities are unchanged.
- **Non-residential customers still save in every case.** Their per-customer saving is lower, since they keep their sales share of the load-following savings and pay their sales share of program costs.
- **What moves is the network saving net of earnings,** Central 2026–2050: Con Edison $28.7B (of which $10.6B transmission upgrades deferred), RG&E $3.1B ($0.6B), Dominion $7.5B, Pepco $0.78B. Program costs ($8.6B, $1.1B, $8.6B and $1.5B) stay by sales.
- **No year has a negative network remainder** at Central.

**Limitations.**
- Customer counts are held at EIA-861 2024 levels.
- The bill adjustment converts the reallocated dollars per kWh of sales at average residential usage, as the other delivery lines do.
- The class split of today's rates is otherwise taken as given.

### 3.11 ROE lever (layer 10)

**What it represents.** A regulator could change the allowed return on equity alongside shared savings, for example to reward or penalise performance (Illinois CEJA performance metrics adjust ROE by 20–60 basis points; Ameren Illinois ±24 bp). This is a **separate lever**, outside the pool.

**Calculation.** From the transition year, in SS:

```
WACC_SS        = WACC + equity_ratio x roe_delta
ROE cost_t     = (wires rate base + regulatory asset) x equity_ratio x roe_delta
equity return  = rate base x equity_ratio x ROE + ROE cost
```

It changes the wires and program revenue requirement, the bill and the equity return. Because `roe_in_pool` is false, the ROE cost is added back to the pool, so **shared savings earnings are unchanged** (tested).

**Inputs.** `roe_delta` −0.006 / 0 / +0.006 (Central: no change), `roe_in_pool`.

---

## 4. Outputs

### 4.1 Bill measures

- **Average residential bill** (`avg_bill_total`, the headline): every volumetric line scaled by residential usage, which efficiency lowers. It shows what a typical customer pays.
- **Benchmark-usage bill** (`bill_total`): usage held at the benchmark. It isolates rate changes from usage changes.

Both are $/month per residential customer, nominal. Cumulative saving per customer = sum over years of 12 x (BAU − SS monthly bill), reported undiscounted and as NPV at 3% and 7%.

**How the distribution lines move.**

```
distribution bill_t = starting distribution x (wires RR_t / BAU wires RR_2026) x (sales_2026 / sales_t)
wires RR_t          = rate base x WACC + property tax + depreciation + other O&M
rate base_t         = rate base_t-1 x (1 - 0.035) + capex_t + connection capex_t
capex_t             = growth capex (reinforcement in service x upgrade cost per MW, inflated) + asset-condition capex
property tax_t      = rate base x property_tax_rate x (1 + inflation / 2)^t
depreciation_t      = 0.035 x opening rate base
other O&M_t         = recalibrated O&M x (1 + inflation)^t + incremental O&M
```

- Asset-condition capex is the 2026 rate-case capex minus 2026 growth capex, inflated.
- Other O&M is recalibrated so that 2026 BAU wires RR equals the rate-case delivery revenue requirement (`delivery_rr_reconciliation()`; tested). The match holds when three conditions are met:
  - recalibrated O&M is not negative (it is floored at zero);
  - 2026 growth capex does not exceed rate-case capex (asset-condition capex is floored at zero);
  - `wacc` equals `rate_case_wacc` where the latter is set.

  All three hold for the six utilities. United Illuminating's recalibrated O&M is 59% of its delivery revenue requirement, above the 50% plausibility bound (as for RG&E and Dominion), which suggests its Form 1 rate base is understated relative to rate-case revenue.
- Both cases are indexed to BAU 2026, so first-year differences show.
- Sales are net of efficiency, waiting load and curtailed flexible-connection energy.

### 4.2 System-wide savings

`system_summary()` reports all customers together, BAU minus SS:
- **Customer savings** ($B undiscounted nominal and NPV 3%) are the sum of three parts:
  1. What customers pay for delivery (revenue requirement including shared savings earnings and any ROE change), programs and capacity.
  2. **Efficiency energy:** GWh saved x today's residential supply rate, grown at supply energy growth. It is applied to all classes, so it likely overstates the commercial and industrial share.
  3. Wholesale energy, avoided transmission and avoided losses, each on its own line.

  The ROE change is already inside part 1. It is shown on its own line, as a cost to customers, for information only.
- **Wires capex avoided or deferred:** BAU capex − SS capex − connection capex.
- **Other lines:** reinforcement deferred (MW), capacity cost avoided, shared savings earnings, and the access measures (4.5).

`layer_contributions()` adds layers one at a time and reports each layer's change in customer savings, the 2035 and 2050 bill, shared savings earnings (sequential, and attributable in proportion to the pool), its contribution to the savings pool, and the utility's equity return. Rows sum to the full case (tested).

### 4.3 Value stack and the cost at which flexibility pays for itself

`value_stack()` reports, for incremental flexible resources only, $ per kW-year of nameplate (nominal):
- **cost:** flexible spend / kW.
- **capacity value:** min(firm flexible MW, peak reduction) x capacity price.
- **deferral value:** flexible share of firm MW x (BAU − SS wires rate base) x (WACC + property tax rate + 3.5% depreciation).
- **load-enabled value:** the wires RR carried by the extra kWh, net of incremental O&M and connection capex.
- **total:** capacity + deferral + load-enabled.

The value-stream layers are not in the value stack.

`flex_pays_cost()` finds **the cost at which flexibility pays for itself**:
- It scales every flexible cost per kW-year together, by bisection, until the chosen target is met. The `target` argument picks one of two modes:
  - a year: the SS average bill equals BAU that year;
  - `'npv3'`: the cumulative average-bill saving per residential customer at 3% NPV is zero.
- It reports the MW-weighted flexible cost per kW-year (2026 $) at that point.
- Weights are each type's incremental MW in 2035 on the target path (before the ramp limit).
- Efficiency costs are not scaled.

### 4.4 Utility earnings

`earnings_table()` reports, $M nominal per year:
- BAU equity return (rate base including the program regulatory asset x equity ratio x ROE);
- SS equity return (plus any ROE change);
- SS shared savings earnings;
- SS total.

Shared savings earnings are the utility's earnings opportunity under the reform.

### 4.5 Access block (not on the bill)

Faster connections benefit the customers being connected, so they are reported separately (`access_summary()`):
- **MW connected sooner:** the sum over bands of max(0, SS served − BAU served) (2035, 2050, peak year). Efficiency is not counted (3.5).
- **Upgrade Delay for Interconnection:**
  - BAU average, years per MW affected;
  - SS average per MW affected;
  - SS per MW affected in BAU (like-for-like);
  - MW affected;
  - **MW-years avoided** (BAU − SS MW waiting, summed over years).
- **Connection cost avoided by new customers:** increments of MW connected sooner x upgrade cost per MW x `customer_funded_share` (1.0 = upper bound), undiscounted and NPV 3%. Flexible-connection MW are not credited here: they already count once, as network headroom.
- **Electrification brought forward:** MW connected sooner x 8.76 x system load factor x electrification share of network growth (GWh).

### 4.6 Tornado and headroom sweep

- **Tornado** (`tornado()`): every input with a spread is set to low and then high, one at a time, everything else central. The output is the change in the monthly saving in 2035 and 2050, ranked by the 2050 swing.
- **Headroom sweep** (`headroom_sweep()`): Central, varying three things:
  - mean starting utilisation (60% to 100% in 5-point steps);
  - sub-band share (0, 2, 4.3, 8, 15%);
  - Upgrade Delay case: short (low delays, high clearance), central, or long (high delays, low clearance).

  Each point reports the 2050 saving and every `system_summary()` measure.

- **Published-plan sensitivities** (Central, on published-plan BAU), run separately and combined:
  - capacity at the long-run cost of new entry;
  - asset-replacement addressable share at 10 / 20 / 30%;
  - data-centre flexibility at Ambitious (flexible-connection share and curtailment at their high levels);
  - the three beyond-plan paths.

- **Results export** (`scripts/export_results.py`, `exports/<utility>.json`): every scenario × electrification pace. The Sankey value flows (a diagram of where the savings come from and who receives them) decompose customer savings exactly as `system_summary()` adds them up:
  - **Gross value:** deferral (BAU − SS wires revenue requirement, less the objective's share), capacity, transmission, losses, wholesale, efficiency energy and the additional savings objective (3.9a).
  - **Program costs:** a deduction (BAU surcharges − SS program revenue requirement).
  - **Split of the net value:** residential customers and business customers (by the residential share of sales, EIA-861), and shared savings earnings.

  `tests/test_export.py` checks that the flows balance and match the headline figures.

The notebooks also show the waterfall, MW tables, the MW path vs ramp limit, the band and constrained tables, and the Upgrade Delay table by request year.

---

## 5. Dollar bases and discounting

- **Nominal dollars.** The projection is in nominal dollars. Costs grow with inflation (2.5% a year) or their own growth rates. Bills, $M per year and cumulative sums are nominal unless labelled.
- **Undiscounted cumulative.** Sums of nominal dollars over 2026–2050. These are easy to read, but they weight 2050 dollars the same as 2026 dollars.
- **NPV at 3% and 7%, in 2026 dollars.** Nominal flows discounted to 2026 by `(1 + r)^(year - 2026)`.
  - 3% is close to a social discount rate.
  - 7% is close to a utility or private cost of capital, a conservative view of later savings.
  - Because the flows are nominal, a 3% nominal rate is roughly 0.5% real at 2.5% inflation.
- **2026 dollars for inputs.** Cost inputs such as $/kW-year and $/kWh are 2026 values, inflated in the projection. The cost at which flexibility pays for itself is reported in 2026 $.
- **Real dollars** are not reported separately.

Every figure in the notebooks, reports and README states its basis.

---

## 6. Data and status

Every input has a `source`, an `as_of` date and a `status`:

| Status | Meaning |
|---|---|
| `sourced` | Read directly from a cited document (filing, tariff, order, market report, statistical release) |
| `derived` | Calculated from sourced figures; the derivation is in `source` or `notes` |
| `_VERIFY` | An estimate, assumption or proxy awaiting confirmation; `source` says why and what would confirm it |
| `setting` | A model switch or mode choice, not a measured value |

Of the measured inputs (sourced, derived or `_VERIFY`, i.e. excluding settings), about half are `_VERIFY`: Con Edison 47%, Dominion 46%, Pepco 52%, RG&E 63%. As a share of all status-tagged inputs, including the settings that each new feature adds, the figures are 33%, 32%, 36% and 43%. The shares fell when published-plan BAU was added, mostly because its new inputs are settings (basis, paths, addressable shares), and again with the avoided-obligation capacity inputs (3.6a), most of which are sourced from PJM, NYISO and NYSRC publications. [ASSUMPTIONS.md](ASSUMPTIONS.md) has the counts by layer.

**Proxies used where a utility lacks its own data:**
- **Network loading bands and the constrained sub-band:** Dominion's grid utilization filing, applied to Con Edison, RG&E and Pepco.
- **Upgrade delays:** Con Edison's E-Mobility Interconnection Guide (ordinary 0.5 / 1.5 / 3 years, large 2 / 3 / 6 years), applied to RG&E and Pepco, and to Dominion's ordinary load. Dominion's large-load delays (4 / 6 / 7 years) are its own (PUR-2026-00011).
- **Wholesale spread:** PJM's State of the Market, applied to New York.
- **Efficiency peak ratio:** EmPOWER Maryland, applied to all.
- **Ramp limits:** Pepco's direct load control history, applied to all.
- **Backlog clearance:** the low value is from Dominion's large-load queue; the others are assumptions.

The per-utility notes in [utilities/](utilities/) list what is utility-specific, what is borrowed and the main gaps.

---

## 7. Configuration

**Where inputs live.** `utilities/<utility>.json`:
- `starting_bill`: today's bill, line by line.
- `forward_assumptions`:
  - `projection`: growth rates;
  - `layers`: each with `enabled` and `params`;
  - `network`: every headroom input;
  - `bau_plan`: BAU basis, published plan capex, beyond-plan path and taper year, category shares, addressable shares, transmission plan, `link_growth_to_load` and `plan_load_growth`;
  - `scenarios`: levels and network values;
  - `capacity_carve_out`, `starting_adjustments`.

A spec is either a range `{low, central, high, unit, source, as_of, status}` or a single value `{value, unit, source, as_of, status}`.

**Three ways to change an input:**
1. Edit the JSON (the default for every run).
2. A scenario's `levels` (per layer or per input) and `network` values.
3. In the notebook, `NETWORK_OVERRIDES` at the top of Section 13 sets any network input for every run in that section and the report, for example `{'subband_enabled': False}`.

In code, `project_layers()` also takes `overrides={(layer, param): level or value}`, `enabled={layer: bool}` and `network={param: value}`.

**Override order** (highest wins):

```
per-call network=  >  per-call overrides=  >  NETWORK_OVERRIDES (notebook)  >  scenario network values  >  scenario levels  >  JSON (value or central)
```

---

## 8. Validation

`python -m pytest tests/` runs the full suite. The layered-model tests (`tests/test_layers.py`) check the following. Every test runs for all six utilities, except the fixture tests, which pin outputs at earlier commits and run for the four utilities that existed then (`PINNED_UTILS`). The ramp-limit check applies to growth above a BAU path. Three checks that need a positive pool (deferral earns a positive share; the dividend advance pays a credit when sized on the pool) also accept a pool that is never positive (United Illuminating, Cautious and Central), where there is nothing to attribute or recover.

| Test | What it guarantees |
|---|---|
| `test_all_layers_off_equals_bau` | With every savings layer off, SS equals BAU |
| `test_starting_total_equals_starting_bill` | Year zero equals the sum of the starting-bill lines (carve-out moves dollars, adds none) |
| `test_pepco_order_adjustment` | The Order No. 92607 adjustment is applied (+$3.94 x (1 + gross receipts tax) on the bill) |
| `test_temporary_rate_revert` | Connecticut's public-benefits credit moves toward the pre-credit level from May 2027 (8/12 of 2027) by `public_benefits_revert_share` (low 0 / central / high 1), then grows like any program surcharge |
| `test_bau_storage_path_and_incremental_cost` | Connecticut BAU storage follows the ESS path; shared-savings storage never falls below it, only the MW above it are costed, and Cautious adds none |
| `test_allocation_peak_factor_scales_cost_shift_only` | The 12CP factor scales the transmission cost-shift line only; bills are unchanged |
| `test_bau_year_zero_rr_matches_rate_case_target` | 2026 BAU wires RR equals the rate-case delivery revenue requirement |
| `test_placeholder_layers_cannot_be_enabled` | Older JSON placeholders raise an error if switched on |
| `test_program_transfer_is_neutral_without_new_resources` | Moving today's programs into rates with no new resources leaves the bill unchanged (sub-band off) |
| `test_flex_spend_is_mw_times_cost` | Flexible spend = incremental MW x cost per kW-year |
| `test_energy_efficiency_lowers_sales_and_average_bill` | Efficiency savings are positive, the usage index is below 1, and the SS average bill is below the SS benchmark bill (2035) |
| `test_scenarios_are_ordered` | Cautious < Central < Ambitious cumulative saving per customer |
| `test_headroom_used_never_exceeds_headroom_created` and `test_headroom_used_never_exceeds_created_with_subband` | One use per MW of headroom; MW connected sooner ≤ load-enabled headroom |
| `test_network_served_never_exceeds_demand_or_capacity` | Served load ≤ demand and ≤ operating limit x capacity + headroom |
| `test_served_never_exceeds_operating_limit` | Served load ≤ operating limit + headroom |
| `test_one_band_equals_single_pool_model` | One band reproduces the single-pool model exactly (fixture at ebb0c04), except the shared-savings columns the code fixes change on purpose |
| `test_bands_sum_to_network_totals` | Bands sum to network load and capacity |
| `test_ramp_limit_respected` | MW growth never exceeds the ramp limit |
| `test_access_zero_with_layers_off` | No access benefits without layers |
| `test_network_defaults_reproduce_1b09e20` | The network block reproduces the pinned 1b09e20 outputs with the sub-band and new layers off, the single transmission formulation and the embedded capacity formulation: BAU exactly; shared savings exactly except the columns the code fixes change, and except where this commit's data changes apply (Dominion's demand-response path, Pepco's capacity price) |
| `test_full_utilisation_long_lead_gives_bau_queue` | A tight network produces waiting load in BAU |
| `test_subband_gives_bau_queue_and_keeps_totals` | The sub-band creates waiting load and keeps totals |
| `test_mean_utilisation_shift` | The mean shift hits its target |
| `test_network_override_order` | JSON < scenario network values < NETWORK_OVERRIDES < per-call `network=` (not `overrides=` or scenario levels) |
| `test_headroom_sweep_grid` | The sweep covers the grid; MW-years avoided rise from short to long delay |
| `test_subband_on_in_every_scenario_and_switchable` | The sub-band is on in every scenario and can be switched off |
| `test_upgrade_delay_mw_years_identity` | Delay MW-years equal the sum of MW waiting |
| `test_upgrade_delay_inputs_drive_the_wait` | With the backlog cleared at once, BAU waits for requests in 2028–2045 never exceed the input delay; BAU MW-years rise from low to central to high delays; slower clearance leaves more MW above the planning limit; no priority never shortens the wait |
| `test_flexibility_never_lengthens_upgrade_delay` | SS total delay MW-years and MW affected ≤ BAU |
| `test_value_layers_add_savings_and_sum` | Each value layer adds savings and lowers the 2050 bill (transmission may be 0 where nothing is load-driven, Pepco, since the lower share of zonal transmission costs is outside the headline); contributions and the waterfall sum to the full case |
| `test_wholesale_counts_only_load_shifting` | Wholesale value is zero without incremental flexible MW |
| `test_losses_energy_value_only_above_average` | Loss energy value is zero at a multiplier of 1 |
| `test_roe_lever` | ROE moves the bill and equity return, not shared savings earnings; neutral at 0 |
| `test_transmission_bill_basis` | Avoided transmission lowers delivery in New York and the transmission lines in PJM |
| `test_efficiency_counted_once_in_capacity` | Embedded: capacity MW = peak − waiting − firm flexible MW − EE MW with the layer on, peak − waiting with it off. Avoided obligation: each EE MW enters the obligation once, and capacity MW = peak − waiting with the layer off |
| `test_dominion_demand_response_excludes_efficiency` | Dominion's DR inputs equal the IRP DSM MW less EE at `ee_kw_per_mwh` |
| `test_flexible_connections_counted_once` | Connection cost avoided credits only MW connected sooner; zero with deferral and load enabled off, even with flexible connections |
| `test_earnings_attributed_in_proportion_to_pool` | Attributable earnings are proportional to pool contributions and sum to total earnings |
| `test_efficiency_not_counted_as_connected_sooner` | With deferral and load enabled off, no MW connected sooner, connection capex, connection cost avoided or electrification brought forward |
| `test_capex_pool_basis_removed` | The `pool_basis` argument and the `'capex'` basis are gone |
| `test_settings_are_labelled_setting` | Every input whose source says it is a setting has status `setting` |
| `test_pepco_capacity_prices_aligned` | Pepco's carve-out and capacity layer use the same year-zero price |
| `test_model_bau_basis_reproduces_23fec60` | With `basis: 'model'` (and the embedded capacity formulation), the current JSON reproduces the layered outputs at 23fec60 exactly |
| `test_published_plan_capex_and_beyond_paths` | BAU capex equals the published plan in plan years; continue, taper and policy paths follow their formulas |
| `test_plan_capex_avoidance_by_category` | SS capex = plan − avoided by category; growth avoidance capped; replacement at its share after the ramp; no avoidance with deferral off |
| `test_transmission_follows_its_own_plan` | The PJM transmission line follows the plan's rate base per MW of peak; New York has no line |
| `test_long_run_capacity_price` | The long-run price path reaches the inflated cost of new entry by `long_run_year` |
| `test_coned_data_centre_growth_matches_forecasts`, `test_rge_plan_from_rate_case` | Con Edison's data-centre growth is 0%; RG&E's plan sums to the filed total |
| `test_plan_growth_capex_linked_to_load` | Linked growth capex = plan × share × cumulative model / plan load growth; other categories on plan; link off = fixed plan |
| `test_utility_forecast_pace_calibrates_load` | Central pace: system peak growth over the plan years equals the plan's forecast; scale factor 1.0 at plan end; state policy uncalibrated |
| `test_electrification_pace_table` | Both paces for every scenario; additional opportunity = state policy − utility forecast |
| `test_objective_zero_is_a_no_op` | At the default 0%, every output equals the run with the objective layer off |
| `test_objective_savings_rise_with_level` | For each base, customer savings rise steadily with the objective (0 / 2.5 / 5 / 10%); BAU is untouched |
| `test_objective_capex_base_flows_through_rate_base`, `test_objective_persistence_fades` | The capex base lowers capex and rate base, with the RR saving equal to the RR difference; the fade option works |
| `test_mechanism_option_defaults_change_nothing` | Fast start off, ramps null, advance off: every output identical to a JSON without the new inputs |
| `test_fast_start_first_savings_year_2027`, `test_near_term_ramps` | Fast start makes 2027 the first savings year (BAU unchanged); each near-term ramp acts on its own |
| `test_advance_npv_equals_recoveries_plus_financing` | Credits + financing − recoveries = 2050 balance; PV of credits = PV of recoveries + PV of the balance; return reported only for the regulatory asset |
| `test_advance_sizing_cap_and_true_up` | Both recovery sources: size = 0.5 × PV of the recoverable base at 4%; PV of planned credits = size; customers' net saving never negative in a recovery year; no residential bill above BAU; credits paused exactly when behind schedule |
| `test_advance_cautious_sized_and_realized_clears` | Sized and realised Cautious, both sources and both financing options: no balance left in 2050 |
| `test_rge_data_centres_follow_gold_book_zone_b` | RG&E's data-centre load = 300 MW + Gold Book Zone B increments × its zone share; high = 5%/yr |
| `test_capacity_formulation_default_avoided_obligation` | The default is `'avoided_obligation'` with suppression off; every capacity input has a status; `local_coincidence` (0.5 to 1.0) is in the tornado, and obligation-only inputs leave it under `'embedded'` |
| `test_capacity_formulations_reproduce_212efce` | The default reproduces 212efce's avoided-obligation runs exactly, and `'embedded'` reproduces that commit's default runs exactly (fixture `layers_212efce_capacity.json`) (both with the single transmission formulation of that time) |
| `test_capacity_obligation_neutral_settings_reproduce_embedded` | With accreditation = the programs derates, coincidence 1, obligation 1, no lag and the bill-line price, the avoided-obligation results equal the embedded ones |
| `test_capacity_obligation_identities` | BAU unchanged; credit = lagged obligation x obligation factor x long-run avoided price; the long-run price is reached by `long_run_year`; a longer lag or lower coincidence never raises the layer |
| `test_capacity_price_suppression_sensitivity` | Suppression is zero before its start year and from `long_run_year`, never negative, adds savings only when on, and is ignored under `'embedded'` |
| `test_capacity_formulation_table` | Both formulations for every scenario; the default row matches `system_summary()` |
| `test_transmission_default_split_and_inputs` | The default is `'split'` with the avoided build on and `allocation_in_headline` off; realisation by planner (New York = the growth-capex addressable share, PJM 0 / 0.5 / 1.0); split-only inputs have a status; the tornado excludes `avoidable_share` while split and split-only inputs while single |
| `test_transmission_formulations_reproduce_fe90816` | `'single'` reproduces fe90816's default runs exactly, and the default reproduces the split runs (fixture `layers_fe90816_transmission.json`) |
| `test_transmission_split_identities` | By default only (b) counts; in PJM the cost shifted equals (a), which matches an independent share calculation; (a) is 0 in New York; no avoided build before the transition year plus the lag |
| `test_transmission_allocation_outside_pool_and_headline` | (a) never changes the pool or earnings; the switch adds exactly (a) to headline customer savings and the bills |
| `test_transmission_avoided_build_switch_and_scenarios` | (b) off gives no avoided build; PJM Cautious realisation 0; a longer lag never brings the avoided build forward |
| `test_transmission_new_york_overlap_removed` | No plan dollar is deferred by both the deferral layer and (b) |
| `test_transmission_formulation_table` | Single and split, (b) off and on, for every scenario; the default row matches `system_summary()` |

`tests/test_assumptions_register.py` checks two things:
- The assumptions register matches the JSON.
- Every layered input has a valid status.

`tests/test_export.py` checks that the exports balance and match direct runs. New York's transmission upgrades deferred are in the reallocated network saving and PJM's are not; the engine's reallocated pool equals the export's. The allocation tests check three things: `allocation_sweep` by_sales reproduces the existing export fields exactly; residential + non-residential equal customer savings under every option, with the load-following parts unchanged; the per_customer residential share equals the residential share of EIA-861 customer counts; and where residential customers' share of customers exceeds their share of sales, per_customer residential savings are at least the by_sales ones, for every utility, scenario and pace. `test_customer_allocation_drives_bill_and_advance_cap` (layers) checks four things: the allocation moves only the residential bill; totals, earnings and BAU are unchanged; the adjustment is a credit; and with the advance on, the cap holds on the allocated bill. `test_program_costs_enter_once` sets every flexible cost per kW-year and the efficiency levelised cost to zero. Customer savings plus shared savings earnings then rise by exactly the original run's `program_costs` flow, and every value source is unchanged, so program costs enter the results once.

`tests/test_regression.py` pins the earlier model: the v1.0 BASE results for Con Edison, Dominion and Pepco, plus the correction-flag checks.

**What the tests do not guarantee.** They check internal consistency, conservation and reproducibility. They do not check that inputs are right, or that the model reflects any utility's actual network. Section 10.2 lists a calculation the tests do not catch.

---

## 9. Relationship to v1.0 and CORRECTED

The **earlier model** (`engine/model.py`, Sections 1–12 of each notebook, `GridDividend_v1.0.ipynb`) modelled shared savings differently:
- a system-wide share of eligible capex avoided by NWS;
- a capacity pass-through;
- a utilisation credit.

Its scenarios were BAU, BASE (the "EASE Case" in its reports), ACCELERATED, FREEZE_PLUS, COMBINED and FRONTLOADED. The `CORRECTED` preset switches on the recommended methodology fixes (depreciation, revenue-requirement pool, carry-forward, BAU bill index); it is not the default.

**Why it is kept:**
- Published results must reproduce exactly. Three pinned tests guard the BASE results for Con Edison, Dominion and Pepco.
- The earlier notebooks' rate-freeze and ROE-sweep analysis remains useful context.

**How the layered model differs:**
- It starts from the line-by-line bill.
- It represents the network explicitly.
- It ties program spend to MW delivered.
- It uses the revenue-requirement pool with carry-forward.

New analysis uses the layered model. The two models do not share results.

---

## 10. Limitations and open questions

### 10.1 Limitations of the approach

- **Not a forecast.** Direction and order of magnitude only.
- **Spatially aggregate.** Bands approximate the network. Real outcomes depend on feeder-level constraints and where flexibility is sited.
- **Published plans are short and change.** BAU after the plan horizon is a path choice (central: taper to load growth by 2035). Plans are revised every year, and New York's Chapter 58 of the Laws of 2026 adds uncertainty to Con Edison's forecast (its 10-K says so).
- **Proxies.** About half the inputs are `_VERIFY`, including network loading for three utilities.
- **One benchmark customer.** The average residential bill applies system efficiency to residential usage. No customer classes or low-income detail.
- **Fixed customer charges scale with the wires revenue requirement per kWh**, like the volumetric lines.
- **Efficiency energy** is valued at the residential supply rate for all classes.
- **Not modelled yet:** resilience, capacity price suppression, the economic value of faster connections, emissions. These would be reported separately, not on the bill.
- **Summer peak only.** The network, capacity and deferral layers use the summer peak. Connecticut (and ISO-NE) move toward winter peaks in the 2030s as heat pumps spread: ISO-NE's 2026 CELT has the 90/10 winter peak passing the 50/50 summer peak by 2034. That changes which flexible resources defer which capex (heating load control and storage over air-conditioning demand response). This is a candidate for a seasonal network and capacity layer; the engine is unchanged.
- **No feedback** from bills to demand, and no utility behavioural response beyond the stated paths.

### 10.2 Code issues found and fixed

The independent documentation check found these issues; they are fixed in the commit "Code fixes from the independent check" (see [CHANGELOG.md](../CHANGELOG.md) for before/after figures):
1. **Efficiency peak MW was counted three times in capacity.** Each MW now counts once (3.6). Dominion's demand-response inputs no longer embed efficiency (3.4).
2. **Flexible connections were counted twice.** They were counted as headroom and again as connection cost avoided. Now they count once, as headroom (4.5).
3. **Earnings attributable depended on layer order.** It is now proportional to each layer's contribution to the pool (3.10).
4. **Efficiency counted as MW connected sooner.** It no longer does, and it is charged no connection cost (3.5).
5. **The `'capex'` pool basis** has been removed from the layered model (3.10).
6. **Six inputs mislabelled.** They are now labelled `setting`, as their sources say (6).
7. **Pepco's capacity line and capacity layer** now start from one price (3.6).

**Remaining, by design or not fixed:**
- **Program-transfer neutrality with waiting load.** In SS, core programs are recovered per kWh served. Where load waits for an upgrade, the rider is slightly higher than the BAU surcharge (about $0.003/month at most). This is why the neutrality test runs with the sub-band off.
- **Load enabled shows as a small net cost system-wide** (3.5). Its benefit is in the access block.
- **Upgrade Delay MW-years avoided still include efficiency.** BAU waiting − SS waiting counts demand that efficiency removes from waiting bands as delay avoided: that load no longer needs to wait.

### 10.3 Open housekeeping items that would change results

These need a decision before they are changed:
- **v1.0 notebook sync.** `GridDividend_v1.0.ipynb` carries its own engine copy.
- **Dominion ACCELERATED / COMBINED shares** (earlier model): New York's absolute NWS shares (35% / 55%) instead of Dominion's 22% / 35%.
- **EV territory share** (earlier model): Dominion uses the New York-calibrated `customers / 8,000,000`.
- **New York capacity cost** (earlier model): hard-coded rather than read from `NYISO.json`.
- **New York property tax:** `ConEd.json` and `RGE.json` lack `property_tax_rate`, so the notebook fallback (1.6% / 1.8%) applies.
- **Con Edison Merchant Function Charge:** January 2026 is not parsed. The November 2026 link serves an Orange & Rockland statement.
- **Constrained-area build rate** is per band unless build-rate priority is on.

---

## 11. Glossary

The full plain-language glossary, in three groups (parts of a bill, how rates are set, terms in the model), is [GLOSSARY.md](GLOSSARY.md). The table below keeps the model's network and mechanism terms in short form.

| Term | Meaning |
|---|---|
| **Above planning limit (MW)** | Served load above planning capacity plus counted headroom; Dominion's "constrained" basis |
| **Access block** | Benefits to customers being connected (MW connected sooner, Upgrade Delay avoided, connection cost avoided, electrification brought forward), reported apart from the bill |
| **Average residential bill** | The headline bill: usage lowered by efficiency |
| **Backlog clearance** | Share of the constrained-area backlog above the planning limit cleared each year |
| **BAU** | Business as usual: no reform |
| **Benchmark-usage bill** | Bill at fixed benchmark kWh, isolating rate changes |
| **Build-rate priority** | Whether constrained-area upgrades escape the maximum build rate |
| **Capacity carve-out** | Capacity cost split out of the line where it is embedded; total unchanged |
| **Constrained area** | The constrained sub-band, when the three Upgrade Delay inputs are set (other bands use the reactive planner) |
| **Constrained band** | A band whose load exceeds `constrained_loading` x (capacity + counted headroom) |
| **Constrained sub-band** | Load above the planning limit (default 4.3% at 112.5%), carved from the most loaded bands |
| **Core business** | Programs that move from surcharges into utility rates under shared savings |
| **Cost at which flexibility pays for itself** | Flexible cost per kW-year at which the SS bill equals BAU (or the 3% NPV saving is zero) |
| **Customer savings** | System-wide BAU minus SS cost to all customers, including efficiency energy and the value streams |
| **Deferral** | Flexible headroom counted by the planner, so reinforcement is ordered later |
| **Derate** | Share of nameplate flexible MW counted as firm at peak |
| **Earnings attributable** | Total shared savings earnings split across layers in proportion to each layer's contribution to the pool |
| **Effective capacity uplift** | Flexible headroom / network capacity |
| **Firm MW** | Derated flexible MW plus efficiency peak MW |
| **Flexible connection** | A large load connected on terms that let the utility curtail it at peak |
| **Flexible headroom** | Firm flexible MW x locational match + flexible connection MW |
| **Headroom sweep** | Results across mean utilisation, sub-band share and delay case |
| **Incremental MW** | Flexible MW above today's programs |
| **Load enabled** | Waiting load connected sooner by flexible headroom; its bill bar is the residential effect only |
| **Loading band** | A group of substations at similar loading, with a share of capacity |
| **Locational match** | Share of firm flexible MW located where the network needs it |
| **MW affected** | New load that waited at least a year for an upgrade |
| **MW connected sooner** | Sum over bands of max(0, SS served − BAU served): load connected sooner, excluding efficiency |
| **MW waiting for upgrade** | Demand not served because capacity is not yet in service |
| **MW-years avoided** | BAU minus SS MW waiting, summed over years |
| **Operating limit** | Equipment rating, 1 / planning limit factor x planning capacity; existing load is served up to it |
| **Planning capacity / planning limit** | 80% of rating; loading 1.0 |
| **Planning headroom** | Margin the planner keeps above demand (10%) |
| **Pool (savings pool)** | Net saving to customers in a year, before the utility's share; negative pools are carried forward |
| **Published-plan BAU** | BAU distribution capex from the utility's published capital plan, extended to 2050 by a beyond-plan path |
| **Addressable share** | The part of a plan capex category that shared savings could defer, avoid or right-size |
| **Deferrable share** | The network model's cumulative reinforcement avoided as a share of BAU reinforcement; caps growth-driven avoidance with the addressable share |
| **Electrification pace** | Utility forecast (central: BAU load calibrated to the utility's own forecast) or state policy (the model's electrification assumptions) |
| **Additional savings objective** | Savings the utility commits to find by unspecified means, as a share of a base, net of cost to achieve; additional to the other layers by assumption |
| **Customer dividend advance** | Level bill credit paid early, sized on recoverable savings, securitised, and recovered through a bill-savings rider (or from the pool), with a true-up and a cap. A parked option, off by default and not in the headline results (3.10a) |
| **Fast start** | First savings year 2027 instead of the transition year, with separate near-term ramps for capacity, programs MW and the plan's addressable shares |
| **Load link** | Scaling of the plan's growth-driven capex by the model's load growth relative to the plan's assumed load growth |
| **Taper year** | Year by which BAU capex growth reaches load growth on the taper path |
| **Savings pool contribution** | The change in the cumulative pool when a layer is added in waterfall order |
| **ROE lever** | Change in allowed ROE in SS, outside the pool |
| **Seed pipeline** | Reinforcement already under way at 2026 |
| **Shared savings earnings** | The utility's share of the pool: its earnings opportunity |
| **Transition year** | Year programs become core business (2028) |
| **Upgrade Delay for Interconnection** | Time a new customer in a constrained area waits for the grid upgrade before connecting |
| **Value stack** | Value per kW-year of flexible resources: capacity, deferral, load enabled |
| **Value-stream layers** | Wholesale energy, avoided transmission, avoided distribution losses |
| **_VERIFY** | An input awaiting confirmation |

---

## 12. Starting point: 2021–2026

### 12.1 [Narrative introduction: placeholder]

### 12.2 What the look-back covers

The look-back module (`engine/lookback.py`) describes how each utility arrived at its 2026 starting point. It is separate from the forward model: the forward model does not read the look-back data, and nothing in it changed.

- **Data:** `utilities/<utility>_lookback.json`. Every figure carries a `source`, an `as_of` date and a `status` (`sourced` / `derived` / `_VERIFY` / `setting`), as in the forward model. A figure that could not be located is stored as `null` with status `_VERIFY` and a note saying what is missing.
- **Register:** the figures are in the assumptions register under section `lookback`. They are not counted in the forward model's status shares.
- **Export:** `exports/<utility>.json` carries them under `lookback`.

All dollar figures are nominal and undiscounted.

### 12.3 Residential bill: the like-for-like trend, 2021–2025, and the 2026 tariff bill

**Headline trend (`bill_trend()`).** EIA-861 residential average revenue per kWh for 2021–2025, × the benchmark usage, for the utility's own state (Virginia for Dominion, Maryland for Pepco). Status `derived`.
- **Delivery** = EIA-861 delivery-only (Part C) revenue per kWh × kWh, where EIA reports delivery-only customers (New York, Maryland).
- **Supply** = total − delivery.
- **Virginia** has no delivery-only customers, so EIA cannot split Dominion's bill. The rider bridge in 12.6 gives Dominion's split on the SCC basis.
- **Basis:** these are averages over customers and months, not tariff bills. They are, however, the same measure in every year.

$/month nominal at the benchmark usage:

| Utility | kWh/month | 2021 total (delivery / supply) | 2025 total (delivery / supply) | Change 2021 → 2025 (delivery / supply) |
|---|---|---|---|---|
| Con Edison | 600 | 163.95 (104.06 / 59.89) | 220.41 (145.72 / 74.69) | +56.46 (+41.66 / +14.80) |
| RG&E | 600 | 81.22 (51.24 / 29.98) | 132.04 (80.47 / 51.57) | +50.82 (+29.23 / +21.59) |
| Dominion VA | 1000 | 121.30 (not separable) | 151.97 (not separable) | +30.67 |
| Pepco MD | 900 | 125.85 (64.36 / 61.50) | 195.67 (82.86 / 112.81) | +69.82 (+18.50 / +51.31) |

**The 2026 tariff bill (`bill_2026_tariff()`)** is shown separately. It is the forward model's starting bill at the benchmark usage, by category: `starting_lines()` with the capacity carve-out and the Pepco Order No. 92607 adjustment. Totals, $/month nominal: Con Edison 215.01, RG&E 159.45, Dominion VA 182.80, Pepco MD 231.63, Eversource CT 174.44, United Illuminating 183.88 (both at 700 kWh, with the May 2026 public-benefits credit).

**2021 by category.** No 2021 line-item tariff archive or rate-case bill comparison was located for any of the six utilities (for Connecticut, the OCC 2021-22 consumer alerts were not reached).
- The 2021 levels (`bill_comparison()`; export `bill_levels_by_basis`) keep the EIA-derived 2021 totals.
- The category lines are `null` (`_VERIFY`). The totals reconcile through an explicit unitemised remainder (tested).
- The 2021 EIA averages and the 2026 tariff bill are on different bases, so the difference between them is **not presented as a change**. The like-for-like change is the EIA trend above.

Note: the EIA series was corrected in this revision. It previously carried North Carolina figures for Dominion and DC figures for Pepco. The other jurisdiction is now kept separately as `other_jurisdiction`. The 2021 totals were already on the right state.

### 12.4 Distribution revenue-requirement bridge, 2021 → 2026

The bridge runs 2021 → 2025 on a FERC Form 1 functional basis (costs sorted by function: generation, transmission, distribution), then adds the approved 2026 rate-case step (the increase approved for that year).

**Source data.** FERC Form 1 data for 2021 and 2025, via the Catalyst Cooperative PUDL (Public Utility Data Liberation) tables:
- net plant, working capital and accumulated deferred income taxes by function;
- depreciation by function;
- O&M by function;
- taxes and income taxes.

**Scope.**
- **Con Edison and RG&E:** distribution + transmission, because New York delivery rates recover both. This is the forward model's delivery revenue requirement.
- **Dominion, Pepco, Eversource CT and United Illuminating:** distribution only.

**Allocation.**
- **Common costs:** general, intangible and common plant, working capital and ADIT (accumulated deferred income taxes) are allocated to the scope by its share of net plant. Customer accounts, customer service and sales O&M go to the scope. A&G (administrative and general costs) is allocated by the scope's share of direct O&M.
- **Jurisdiction:**
  - Dominion VA: Virginia share of total retail sales, EIA-861 (95.0% in 2021, 95.8% in 2025; a proxy, `derived`).
  - Pepco MD: Maryland share of Pepco distribution rate base, 46.3%. This is derived for 2025 from Order No. 92607 and Exelon's 2025 rate base. It is held for 2021 (`_VERIFY`).

**Revenue requirement.** The look-back uses the forward model's structure (rate base × after-tax WACC + taxes + depreciation + O&M; `revenue_requirement()`), with income taxes added because Form 1 reports them separately. The allowed returns come from the orders and filings:

| Utility | 2021 ROE / equity / debt | 2025 ROE / equity / debt |
|---|---|---|
| Con Edison | 8.8% / 48% / 4.63% (2022 10-K) | 9.25% / 48% / 4.64% (2022 10-K) |
| RG&E | 8.8% / 48% (Avangrid 2021 10-K) / 5.0% (`_VERIFY`) | 9.2% / 48% (Avangrid 2023 10-K) / 5.0% (`_VERIFY`) |
| Dominion VA | 9.2% (SCC) / 52.8% (Form 1 actual, derived) / 5.0% (`_VERIFY`) | 9.7% / 52.035% (SCC Final Order) / 5.0% (`_VERIFY`) |
| Pepco MD | 9.55% (Order 89868) / 50.1% (Form 1 actual, derived) / 5.0% (`_VERIFY`) | 9.5% / 50.5% / 4.71% (Order 91181, derived) |

**Bridge items.**
- **Rate base growth:** valued at the 2021 WACC.
  - Functional plant growth is split by the forward model's capital category shares: growth, replacement, grid modernisation, other.
  - Storm and resilience spending cannot be separated in Form 1. It sits in replacement, and its line is 0 (`_VERIFY`).
  - IT and other = the "other" share + general and intangible plant.
  - Working capital and ADIT are a separate line.
- **Return change:** the 2025 rate base × the WACC change, split exactly into ROE, equity ratio and cost of debt effects.
- **The rest:** depreciation, O&M, taxes other than income and income taxes are changes in the functional totals.
- **2026 step:** the approved increase that takes effect in 2026:
  - Con Edison: RY1, $234M.
  - RG&E: temporary rates (set while the case is pending, subject to reconciliation), $25.9M (pending the final order).
  - Dominion: the distribution share of the 2026 increase, $341.4M (Final Order attachment).
  - Pepco: Order No. 92607, $50.9M.

The items sum exactly from the 2021 to the 2026 revenue requirement (tested). $M nominal:

| Utility | RR 2021 | Rate base growth | Return (ROE, equity, debt) | Depreciation | O&M | Taxes | RR 2025 | 2026 rate-case step | RR 2026 |
|---|---|---|---|---|---|---|---|---|---|
| Con Edison | 6,593 | +285 | +56 | +320 | -5 | +873 | 8,121 | +234 | 8,355 |
| RG&E | 545 | +43 | +5 | +28 | +96 | +37 | 755 | +26 | 781 |
| Dominion VA | 1,648 | +268 | +26 | +106 | +60 | +84 | 2,192 | +341 | 2,533 |
| Pepco MD | 608 | +59 | -5 | +32 | +19 | +51 | 764 | +51 | 815 |
| Eversource CT | 1,467 | +84 | 0 | +58 | +138 | +79 | 1,826 | 0 | 1,826 |
| United Illuminating | 478 | +4 | -3 | +4 | +114 | +16 | 612 | +68 | 680 |

**Reading the bridge.**
- **Con Edison:** taxes other than income (mostly property taxes) are the largest driver, +$633M, consistent with the Commission's statement that property taxes are about 26% of the 2026 increase. Its reported O&M is flat because A&G fell from $557M to $115M between the two Form 1 years. Pension and retiree-benefit credits drive that fall; normalised O&M rises by $452M (grouped view below).
- **Dominion and Pepco:** rate base growth leads.
- **Form 1 basis vs rate-case rate bases:** the Form 1 functional rate bases sit close to the rate-case figures. Con Edison's is $21.0B against an average rate base of $22.8B in 2021; RG&E's $2.06B against $1.91B; Pepco MD's $3.10B against $2.99B adjusted in Case 9820.

**Grouped view (`rr_bridge_grouped()`).** The same bridge, grouped by what drives it. Its start, 2025 subtotal and end equal the detailed rows, and the groups sum to the change (tested).
- **Capital-driven:**
  - the return on rate-base growth at the 2021 WACC (the sum of the detailed rate-base rows);
  - depreciation;
  - plant-related property tax;
  - income tax on the return (the Form 1 income tax change).
- **Cost of capital:** the ROE, equity ratio and cost of debt changes.
- **Operating:** O&M, normalised to exclude non-service pension and retiree-benefit costs, plus non-plant taxes.
- **Pension and retiree-benefit non-service change:** a reconciling line outside the groups. It is zero where no normalisation applies.
- **Rate-case step:** the approved 2026 increase.

**Property tax attributed to plant** (`derived`). Plant-related property tax = the property tax / net plant ratio × the scope's functional plant (scope net plant plus allocated general and intangible plant, after the jurisdictional share). The ratio is:
- the numerator: property and real estate taxes charged, all departments, from Form 1 page 262 (Taxes Accrued, Prepaid and Charged During Year, via PUDL's raw XBRL table);
- the denominator: net utility plant, all departments, from Form 1 page 200.

Non-plant taxes = the scope's taxes other than income − plant-related property tax: payroll, gross receipts, franchise, sales and use and other taxes. The ratio assumes property tax follows net book value. Assessed values, local rates and special-franchise valuation differ by plant type and locality, so this is an attribution, not a measured split.

| Utility | Property tax / net plant, 2021 | 2025 | Property tax, all departments 2021 → 2025 ($M) |
|---|---|---|---|
| Con Edison | 5.45% | 5.84% | 2,218 → 2,981 |
| RG&E | 3.22% | 2.95% | 121 → 143 |
| Dominion VA | 0.75% | 0.59% | 253 → 303 |
| Pepco MD | 1.07% | 1.04% | 88 → 113 |

**O&M as reported and normalised.** Con Edison's Form 1 administrative and general costs fell from $557M (2021) to $115M (2025). The fall is driven by pension and retiree-benefit credits:
- **Account 926:** employee pensions and benefits, inside A&G. It moves from +$190.8M to −$386.5M, a $577M swing, larger than the whole A&G fall.
- **CECONY's non-service components** (total periodic cost less service cost, pension plus retiree benefits; Con Edison 10-K, Notes E and F) turn from a $128M cost in 2021 to a $733M credit in 2025. Expected returns on plan assets exceed interest cost, and actuarial gains are recognised.
- **Why the 10-K doesn't show it:** GAAP presents these components outside operating income, so CECONY's 10-K O&M rises (electric $1,919M → $2,614M). Form 1 keeps them in account 926.

The normalised O&M:
- **Calculation:** the electric non-service amount is CECONY's non-service components × the electric share of CECONY O&M, `derived`. It is allocated to the scope like the rest of A&G.
- **Result:** the scope's normalised O&M rises from $1,724M to $2,175M (+$452M), against reported O&M of $1,797M → $1,791M. The −$457M non-service change is the reconciling line.
- **What stays in:** the rate-level reconciliation (deferral of the difference from the rate allowance) stays in O&M.

The same check for the other utilities finds no credit-driven fall:
- RG&E: account 926 is $7.5M → $0.1M, against A&G of $29.4M → $39.3M.
- Dominion: $84.1M → $134.5M, against $315.5M → $428.9M.
- Pepco: $14.5M → $22.8M, against $158.4M → $197.1M.

Account 926 stays positive throughout, so their reported and normalised O&M are the same (normalisation `setting` 0).

Grouped bridge, $M nominal:

| Utility | RR 2021 | Capital-driven (rate-base return / depreciation / plant property tax / income tax) | Cost of capital | Operating (normalised O&M / non-plant taxes) | Pension non-service | RR 2025 | 2026 step | RR 2026 |
|---|---|---|---|---|---|---|---|---|
| Con Edison | 6,593 | +1,276 (+285 / +320 / +430 / +241) | +56 | +654 (+452 / +202) | −457 | 8,121 | +234 | 8,355 |
| RG&E | 545 | +102 (+43 / +28 / +16 / +15) | +5 | +102 (+96 / +6) | 0 | 755 | +26 | 781 |
| Dominion VA | 1,648 | +445 (+268 / +106 / +9 / +62) | +26 | +73 (+60 / +13) | 0 | 2,192 | +341 | 2,533 |
| Pepco MD | 608 | +129 (+59 / +32 / +7 / +31) | −5 | +32 (+19 / +13) | 0 | 764 | +51 | 815 |
| Eversource CT | 1,467 | +187 (+84 / +58 / +18 / +27) | 0 | +82 (+48 / +34) | 0 | 1,826 | 0 | 1,826 |
| United Illuminating | 478 | +12 (+4 / +4 / +3 / +2) | −3 | +122 (+111 / +11) | 0 | 612 | +68 | 680 |

Connecticut also has a programme line, `programme_outside_base_rates`: CL&P +91, UI +3. It is the change in Form 1 account 908 (customer assistance), where the utilities book C&LM (recovered through the CAM) and hardship and arrearage programmes (recovered through the SBC). These are not base-rate costs, so "operating" is base-rate O&M (`programme_normalisation`). The other utilities have no such line, and their bridges are unchanged.

Capital is the largest driver for the four utilities above and for Eversource CT; for United Illuminating it is base-rate operating costs.
- **Eversource CT:** no rate-case step in 2026 (base rates have not changed since May 2020; Docket 26-05-10 is pending). Capital drives the bridge: +$187M, of which $84M is the return on rate-base growth. Base-rate operating growth is +$82M. Programme O&M recovered through public-benefits charges adds +$91M: account 908 rose from $164.5M to $255.2M, against EIA-861 2025 efficiency and demand-response costs of $145M.
- **United Illuminating:** capital barely moves (+$12M; UI's distribution net plant grew $205M over four years and it halved its capital budget after 2023). Base-rate operating costs drive the bridge: +$122M, mainly customer accounts ($63M → $140M, with uncollectibles $34M → $63M). Programme O&M adds +$3M. The 24-10-04 step (+$68.0M after reconsideration) follows. The $222.4M of capital excluded from return in 2023 sits inside Form 1 plant and cannot be separated.
- Both have a jurisdictional share of 1.0 (single-state utilities) and the scope is distribution only (transmission is pooled through RNS). Neither shows a credit-driven fall in account 926 (CL&P $18.2M → $9.7M; UI $3.4M → $2.4M), so no normalisation applies.

For Con Edison, normalising for the pension credit moves about $450M from "flat O&M" into operating growth.

### 12.5 Supply-side drivers (influenced, not controlled)

These are set by wholesale markets, FERC formula rates or fuel markets. The distribution utility influences them through its load, its procurement and the resources it connects, but does not control them.

- **Capacity prices:**
  - PJM: Base Residual Auction clearing prices by delivery year, 2021/22–2027/28, for the DOM and PEPCO zones. A zone's price is that of the smallest constrained LDA containing it, from PJM's auction reports. PEPCO: $140.00, $95.79, $49.49, $49.49, $269.92, $329.17, $333.44/MW-day. DOM: $140.00, $50.00, $34.13, $28.92, $444.26, $329.17, $333.44.
  - ISO-NE (Connecticut): FCA clearing prices by capability period, Rest-of-Pool, 2021/22–2027/28: $4.631 (`_VERIFY`), $3.80 (`_VERIFY`), $2.00, $2.61, $2.591, $2.59, $3.58/kW-month.
  - NYISO: average spot prices by capability year, 2021/22–2025/26, from the market monitor's State of the Market reports. NYC: $4.31, $3.34, $15.97, $11.76, $10.98/kW-month. NYCA: $4.18, $3.05, $4.11, $3.47, $4.28.
- **Energy supply:** the implied supply component of the residential average price, EIA-861 2021–2025 (bundled minus delivery-only revenue per kWh; Con Edison, RG&E, Pepco MD; `derived`). For Dominion, the fuel factor and deferred fuel charge by year are in the rider bridge (12.6).
- **Transmission:**
  - New York: recovered in delivery rates, so it is inside the bridge.
  - Pepco MD: $0.02101/kWh in 2026. The 2021 rate is `_VERIFY`.
  - Dominion: the Rider T1 history is in 12.6.
  - Connecticut: the TAC in 2026 (CL&P 5.050¢, UI 4.8722¢/kWh) and the RNS rate ($185.28 → $183.71/kW-year, 2025 → 2026). The 2021 TAC is `_VERIFY`.
- **Connecticut Standard Service and public benefits** (`standard_service_cents_kwh`, `public_benefits_cents_kwh`): CL&P 24.17¢ (Jan-Jun 2023, `_VERIFY`), 9.75¢ (Jul-Dec 2025), 12.64¢ (Jan-Jun 2026), 11.58¢ (Jul-Dec 2026); UI 11.68¢, 13.70¢, 11.95¢. Public benefits were about 4¢/kWh combined before May 2026, then about −1.5¢ (CL&P) and −1.3¢ (UI). The 2023 spike was not retrieved.
- **Connecticut, what moved the bill.** EIA-861 at 700 kWh (nominal $/month):
  - CL&P: $149.08 (2021) → $202.13 (2025). Supply peaked at $130.49 in 2023 and was $71.60 in 2025; delivery (distribution, transmission and public benefits) rose $95.27 → $130.53 while base distribution rates were frozen.
  - UI: $176.36 → $247.82. Supply $62.27 → $106.65; delivery $114.08 → $141.18, including the 2023 and 2025 rate increases.
  - The EIA split is delivery against supply only.
- **Connecticut, by category: January 2022 line items → 2026 tariff bill** (`line_item_bridge()`; export `lookback.bill_bridge_line_items`). OCC, *Electric Bill/Rate Components (effective 1 January 2022)*, at 700 kWh, $/month nominal. Supply includes capacity in both years.

  | Category | CL&P Jan 2022 | CL&P 2026 | Change | UI Jan 2022 | UI 2026 | Change |
  |---|---:|---:|---:|---:|---:|---:|
  | Distribution base (customer charge + distribution) | 50.53 | 50.53 | 0.00 | 74.13 | 92.45 | +18.32 |
  | Distribution riders (ESI, decoupling, CTA) | 4.40 | 17.77 | +13.37 | 0.00 | −2.22 | −2.22 |
  | Transmission | 22.86 | 35.35 | +12.49 | 22.92 | 34.11 | +11.18 |
  | Public benefits (SBC, NBFMCC, RE, C&LM) | 21.85 | −10.25 | −32.10 | 19.36 | −24.10 | −43.46 |
  | Supply (Standard Service, incl. capacity) | 80.39 | 81.04 | +0.65 | 74.71 | 83.65 | +8.94 |
  | Total | 180.02 | 174.43 | −5.59 | 191.13 | 183.88 | −7.25 |

  - **CL&P riders:** ESI +$10.14, CTA +$4.28 (it includes the one-time storm-fund amount), decoupling −$1.06.
  - **UI distribution:** the customer charge +$0.18 and the distribution charge +$18.14 (the 2023 and 2025 cases).
  - **Public benefits excluding C&LM:** CL&P +$18.24 → −$14.45; UI +$16.01 → −$28.30.
  - Base distribution, transmission and the ESI tracker raised CL&P's bill. The May 2026 public-benefits credit more than offset them at the 2026 rates.

### 12.6 Dominion: Virginia riders and the bill bridge

Most of Dominion's bill growth since 2021 is in riders, not base rates. `lb['riders']` lists every Virginia rider in effect 2021–2026 with two series:

- **Residential $/month at 1,000 kWh.** For 2021–2025, from the SCC's annual Status Report on the Virginia Electric Utility Regulation Act (Code § 56-596 B; RD390, RD418, RD572, RD717, RD716). These give the typical residential bill as of 1 July, itemised by recovery mechanism and excluding taxes; the components sum to the SCC totals (tested). For 2026, the tariff lines of the starting bill at 1,000 kWh, before the capacity carve-out; taxes are reported separately.
- **Annual revenue requirement by rate year.** From the riders tables in Dominion Energy's 2021–2025 10-Ks (Note 13), which give each application, approval, rate year and total revenue requirement.
  - Rate years still pending at the 10-K date are kept and marked "Requested".
  - Transmission: the T1 total is split into the base-rate transmission component and Rider T1, per the 10-K footnotes.
  - Fuel: the projected fuel expense and the prior under- or over-recovery for each July rate year (10-K, Virginia Fuel Expenses).
  - `rider_rr_by_year()` gives the requirement in effect on 1 July of each year.
  - Gaps (`_VERIFY`): Riders CERC, SMR, PIPP and VCR. Rider RBB has only the $25M noted in the 2025 10-K.

Riders are grouped as generation (R, W, S, BW, GV, B, US-2/3/4, GEN, SNA, CERC, SMR), clean energy under the VCEA (Virginia Clean Economy Act; CE, RPS, OSW, PPA, RGGI), environmental (E, CCR), transmission (T1), distribution (U, GT, DIST, RBB), energy efficiency (the DSM riders) and other (PIPP, VCR).

**Distribution-related riders** are U (strategic undergrounding), GT (grid transformation), DIST (which replaced both in June 2025) and RBB (rural broadband capacity on distribution plant, proposed for consolidation into DIST).

Bill bridge (`dominion_bill_bridge()`), $/month nominal at 1,000 kWh, excluding taxes:

| Group | 1 Jul 2021 | 2022 | 2023 | 2024 | 2025 | Change 2021 → 2025 | 2026 tariff (separate) |
|---|---|---|---|---|---|---|---|
| Base rates | 71.52 | 70.63 | 70.63 | 70.41 | 70.41 | −1.11 | 81.59 |
| Fuel (fuel factor + deferred fuel charge) | 20.45 | 35.38 | 28.59 | 23.96 | 33.13 | +12.68 | 40.55 |
| Transmission (Rider T1) | 10.59 | 6.90 | 3.21 | 5.88 | 9.69 | −0.90 | 12.73 |
| Generation riders | 13.25 | 13.76 | 9.25 | 7.51 | 8.85 | −4.40 | 10.66 |
| Clean energy riders | 0.19 | 1.50 | 4.89 | 13.37 | 16.99 | +16.80 | 22.94 |
| Environmental riders | 1.67 | 4.20 | 4.91 | 4.41 | 2.53 | +0.86 | 2.39 |
| Distribution riders | 2.14 | 3.69 | 2.44 | 5.63 | 6.77 | +4.63 | 7.68 |
| Energy efficiency riders | 1.47 | 1.31 | 1.60 | 1.84 | 1.55 | +0.08 | 1.78 |
| Other | 0.00 | −0.44 | −0.40 | 0.73 | 0.00 | 0.00 | 0.00 |
| **Total** | 121.28 | 136.93 | 125.12 | 133.74 | 149.92 | +28.64 | 180.31 (+2.49 taxes) |

How to read the table:
- **2021 → 2025 is like for like** (SCC basis, 1 July).
- **2026 is a tariff bill on a different presentation:**
  - Base rates include the generation kWh charge before the capacity carve-out.
  - From 2026, purchased capacity moves into the fuel factor (Final Order, PUR-2025-00058).
  - It is therefore shown beside the trend, not as a step in it.
- **What drove 2021 → 2025:**
  - Base rates were flat. Riders R, W and S were rolled into base rates in July 2023, revenue-neutral.
  - Clean energy riders added $16.80, of which Rider OSW was $8.63 and Rider RPS $4.69 in 2025.
  - Fuel added $12.68.
  - Distribution riders added $4.63.

### 12.7 Asked against granted

Every base rate case filed 2021–2026 is listed, with Pepco's Case 9655 added: it was filed in October 2020 and set rates from 2021. Of the rider proceedings, Dominion's Rider OSW (Coastal Virginia Offshore Wind) is listed individually; every Dominion rider's revenue requirement by rate year is in 12.6.

- New York joint proposals (negotiated settlements adopted by the Commission) are treated as the filed request against the adopted multi-year path.
- RG&E's Case 25-E-0379 is pending: temporary rates were ordered on 14 May 2026.
- Each entry gives the docket, dates, revenue requested and approved, ROE requested and granted, capital disallowed, deferred or reduced, and the Commission's stated reasons quoted briefly. Pepco's Case 9820 reasons are a paraphrase of the order as recorded in `Pepco_MD.json`; the verbatim quote was not retrieved.

| Utility | Docket | Status | Revenue requested ($M) | Revenue approved ($M) | ROE requested → granted |
|---|---|---|---|---|---|
| Con Edison | Case 22-E-0064 | decided | 1,200.0 | 442.0/518.0/382.0 | 10.00% → 9.25% |
| Con Edison | Case 25-E-0072 | decided | 1,611.0/932.0/880.0 | 234.0/409.7/421.1 | 10.10% → 9.40% |
| RG&E | Case 22-E-0319 | decided | 93.8 | 50.9/56.6/65.3 | – → 9.20% |
| RG&E | Case 25-E-0379 | pending | 220.2 | 25.9 (temporary rates) | 10.00% → 9.20% (temporary) |
| Dominion VA | PUR-2021-00058 | decided | 0.0 | -50.0 | 10.80% → 9.35% |
| Dominion VA | PUR-2023-00101 | decided | 0.0 | 0.0 | – → 9.70% |
| Dominion VA | PUR-2025-00058 | decided | 822.0/345.0 | 565.7/209.9 | 10.40% → 9.80% |
| Dominion VA | PUR-2021-00142 | decided | 78.7 | 78.7 | – → – |
| Pepco MD | Case 9655 | decided | 37.4/35.4/31.2 | 20.6/16.3/15.3 | 10.20% → 9.55% |
| Pepco MD | Case 9702 | decided | 117.2/160.5/193.2/213.6 | 44.6 | 10.50% → 9.50% |
| Pepco MD | Case 9820 | decided | 119.9 | 50.9 | 10.50% → 9.40% |
| Eversource CT | Docket 17-10-46 | decided | 255.8/44.7/36.4 | 97.1/32.7/24.7 (`_VERIFY` split) | – → 9.25% |
| Eversource CT | 2021 settlement | decided | – | −75.0 (one-time credits) | – → 9.25% |
| Eversource CT | Docket 25-12-13 (storm costs) | decided | 974.2 (one-time) | 869.4 found prudent | – |
| Eversource CT | Docket 26-05-10 | pending | 451.0 filed (base, excl. storms; 727 with storms) | – | 10.25% → – |
| Eversource CT | Docket 26-05-10 notice of intent (May 2026) | pre-filing estimate | ~503 | – | – |
| United Illuminating | Docket 16-06-04 | decided | not located | not located | – |
| United Illuminating | Docket 22-08-08 | decided | 91.1/20.1/19.5 | 23.0 | 10.20% → 8.63% (9.10% less 47 bp) |
| United Illuminating | Docket 24-10-04 | decided | 105.4 | 68.0 (after reconsideration) | 10.50% → 9.40% (derived) |

**Totals (`asked_granted_totals()`).** Each proceeding carries a `comparison` pair of requested and approved annual amounts, `derived` from its own figures. The basis is usually the first rate year:
- **Con Edison 22-E-0064:** the levelized amount the Commission compared the request with.
- **Pepco Case 9702:** the one year granted.
- **Dominion's 2021 and 2023 reviews:** the base rate change, excluding refunds and one-time credits.

RG&E's $25.9M is **temporary rates**, pending the final order. It is excluded from the decided totals and shown in a second total that includes it. $M a year nominal:

| Utility | Proceedings counted | Requested | Approved | Approved / requested |
|---|---|---|---|---|
| Con Edison | 22-E-0064, 25-E-0072 | 2,811.0 | 691.5 | 24.6% |
| RG&E (decided) | 22-E-0319 | 93.8 | 50.9 | 54.3% |
| RG&E (including temporary rates) | + 25-E-0379 | 314.0 | 76.8 | 24.5% |
| Dominion VA | PUR-2021-00058, PUR-2023-00101, PUR-2025-00058, Rider OSW (PUR-2021-00142) | 900.7 | 594.4 | 66.0% |
| Pepco MD | 9655, 9702, 9820 | 274.5 | 116.2 | 42.3% |
| Eversource CT | 17-10-46 (first rate year; filed 2017, its rates applied throughout 2021-2026) | 255.8 | 97.1 | 38.0% |
| United Illuminating | 22-08-08, 24-10-04 | 196.5 | 90.9 | 46.3% |

Connecticut: the 2021 settlement (bill credits), the storm-cost docket (one-time amounts) and the pending Docket 26-05-10 are listed but not in the totals. The annual RAM dockets (21-01-03 / 21-01-04 to 26-01-03 / 26-01-04) were not reviewed for disallowances (`_VERIFY`).

Dominion's base rate reviews alone: $822.0M requested against $515.7M approved (62.7%). PUR-2023-00101 is now resolved: the February 2024 order approved a settlement that kept base rates unchanged, with $15M of one-time credits and $45M of storm costs recovered through base rates (Dominion 2024 10-K).

### 12.8 Class allocation of increases

For each rate case, the look-back records:
- the residential share of the approved increase;
- the residential share of sales (EIA-861) and, where the source gives it, of delivery revenue;
- the residential customer charge before and after.

| Utility | Docket | Residential share of increase | Residential share of delivery revenue / of sales | Customer charge before → after ($/month) |
|---|---|---|---|---|
| Con Edison | 25-E-0072 | 46.5% of the RY1 T&D increase (JP Appendix 15, Table 2A) | 40.2% / 26.0% | 20.00 → 21.00 (22, 23 in RY2, RY3) |
| Con Edison | 22-E-0064 | 40.8% of the RY1 T&D increase (JP Appendix 16) | 40.0% / 26.5% | 17.00 → 18.00 (19, 20) |
| RG&E | 22-E-0319; 25-E-0379 (temporary) | `_VERIFY` | – / 40.4%; 41.4% | `_VERIFY`; 23.00 → `_VERIFY` |
| Dominion VA | PUR-2025-00058 | `_VERIFY` (Staff apportionment, Ex. 98) | – / 30.7% | 7.58, unchanged |
| Pepco MD | 9655 | `_VERIFY` (Order No. 89868 has no class table) | – / 42.9% | 8.01 → 8.22 (year two) |
| Pepco MD | 9702 | 59.67% Schedule R (68.70% with RTM; Order No. 91181, Table 8) | – / 41.0% | 8.21 → 8.43 |
| Pepco MD | 9820 | `_VERIFY` | – / 41.0% | → 8.44 |
| Eversource CT | 17-10-46; 26-05-10 (proposed) | `_VERIFY` | – / 49.2%; 49.8% | → 9.62; 9.62 → `_VERIFY` |
| United Illuminating | 24-10-04; 22-08-08 | `_VERIFY` | – / 44.0%; 42.7% | → 13.02; `_VERIFY` |

Notes:
- **Con Edison's shares** use the T&D increase (column C1). With the low-income discount and the energy-efficiency transfer to a surcharge, SC 1 takes 33.8% (2026) and 27.7% (2023) of the total delivery change.
- **Residential customers take a larger share of the increase than of sales**, but close to their share of delivery revenue. SC 1 is an average class in Con Edison's 2023 embedded cost of service study.

### 12.9 Limitations

- **2021 bills:** they are EIA averages, not tariff line items. The headline trend is the EIA series, 2021–2025.
- **Bridge basis:**
  - It is functional and allocated, not a rate-case cost-of-service study.
  - Form 1 actual costs are combined with allowed returns.
  - The 2026 step is on a rate-case basis.
- **Attributions:** the property tax split and Con Edison's non-service allocation (electric share of CECONY O&M) are attributions, not measured splits.
- **Remaining `_VERIFY` items:**
  - the cost of debt for RG&E, Dominion and Pepco 2021;
  - Pepco's 2021 jurisdictional share;
  - Dominion's jurisdictional proxy;
  - the residential shares of increases for RG&E, Dominion and Pepco Cases 9655 and 9820;
  - Dominion Riders CERC, SMR, PIPP and VCR revenue requirements.

