# GridDividend methodology

*The layered model (`engine/layers.py`, Section 13 of each state notebook). As of 2 November 2026: published-plan BAU (2.5, 3.3a), avoided-obligation capacity (3.6a), after the code fixes in the CHANGELOG entry "Code fixes from the independent check".*

This document explains how GridDividend works. It is written for a policy reader who is comfortable with numbers but is not a modeller. Sections marked **Technical detail** give the equations and code-level behaviour; they can be skipped without losing the thread.

Related documents:
- [ASSUMPTIONS.md](ASSUMPTIONS.md): every input, by utility, with its value, source, as-of date and status (generated from the JSON).
- [utilities/](utilities/): data notes for each utility.
- [../README.md](../README.md): headline results.
- [../CHANGELOG.md](../CHANGELOG.md): what changed, and its effect on results.

Notation in the equations: `x` is multiplication, `t` is years since 2026, `^` is a power, and `(1 + g)^t` grows a 2026 value at rate `g` a year. "SS" means the shared savings case.

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
- It defers network reinforcement.
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
- **Shared savings (SS):** from the **transition year** (2028 for all four utilities), core programs leave the surcharges and become utility spending recovered in rates.
  - The utility grows flexible resources and efficiency along a target path.
  - Flexible headroom defers reinforcement or connects waiting load.
  - The resulting savings form a pool. The utility keeps a share as shared savings earnings.

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

System figures (rate base, capex, revenue, ROE, equity ratio, customers, peak, energy) come from each utility's rate case. They are the same figures the earlier model uses.

### 2.3 Projection, 2026–2050

Each bill category is projected on its own driver:

| Category | Driver |
|---|---|
| Distribution base and riders | Wires revenue requirement per kWh delivered |
| Program surcharges | Core surcharges: grow with the surcharge growth rate in BAU, removed in SS from the transition year. Non-core surcharges: grow in both cases |
| Supply energy | Supply energy growth rate; lowered in SS by wholesale-energy and loss-energy savings |
| Capacity | Zonal capacity price x capacity MW, per kWh delivered |
| Transmission | Transmission growth rate; lowered in SS by avoided transmission where transmission is billed separately (PJM) |
| Taxes and fees | Percentage taxes follow their base; fixed fees are held |
| SS only: core programs and shared savings earnings | A per-kWh rider recovering program costs and shared savings earnings |

### 2.4 Scenarios

Each input with uncertainty has a **low / central / high** value. A scenario picks a level for each input.

| Scenario | Programs | Deferral | Load enabled | Everything else |
|---|---|---|---|---|
| Cautious | low | low | low | central |
| Central | central | central | central | central |
| Ambitious | high | high | high | central |

**What "low" and "high" mean.** The levels are labels in the JSON, oriented within each layer:
- In the programs, deferral and load-enabled layers, "low" is the cautious end and "high" the ambitious end. The programs level moves more than MW and cost:
  - fewer MW and higher cost per kW-year;
  - lower derates;
  - higher capitalised shares, so the cost timing changes too;
  - a lower `ee_kw_per_mwh`;
  - a lower efficiency savings rate;
  - fewer flexible connections with more curtailment;
  - tighter ramp limits.

  The deferral level sets the locational match. The load-enabled level sets the enable share, the connection cost and the incremental O&M.
- In the mechanism layer, "low" is a *larger* utility share (40%) and "high" a smaller one (10%).
- In the ROE layer, "low" is −60 basis points and "high" +60.

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
    - Dominion 1.88% (its own 2025 Company Load Forecast for the DOM LSE, which includes Dominion-served data centres);
    - RG&E 3.0% (Gold Book Zone B, proxy).
  - In the plan years, the growth category is scaled by the model's load growth relative to that assumption. Replacement, grid modernisation and other stay on plan.
  - Plan capex fixed regardless of load remains a setting.
- **Electrification pace** (`electrification_pace`, central `utility_forecast`).
  - Central BAU load is calibrated to the forecast behind each utility's plan, so the load link's scale factor is 1.0 at plan end.
  - `state_policy` keeps the model's electrification assumptions (state policy pace). The difference is reported as the additional opportunity if electrification follows state policy (`electrification_pace_table()`).
- **Plan capex is split into categories:** growth-driven, asset replacement, grid modernisation / resilience, and other. The split is sourced for Con Edison and RG&E. **Dominion and Pepco use the New York splits as a proxy** (`_VERIFY`); neither publishes one.
- **Each category has an addressable share:** the part that flexibility, efficiency and better planning could defer, avoid or right-size under shared savings (3.3a).
- **Transmission** follows its own published plan and stays on its bill line, where it is one (Dominion and Pepco). In New York, transmission is recovered in delivery rates and is part of the plan's electric capex.
- **The network model no longer generates BAU capex.** It still models capacity, waiting load and the Upgrade Delay, and it estimates how much of the plan's growth-driven spending is deferrable, and where.
- **Other bill components:**
  - Capacity uses published auction prices where they exist (PJM 2027/28 at $333.44/MW-day).
  - Transmission follows the plans above.
  - Supply energy and program surcharges keep their growth rates (no utility-specific published forecast was found).
  - Shared savings influences these lines (capacity, wholesale energy, transmission and losses) but does not eliminate them.

The earlier, model-derived BAU remains selectable (`basis: 'model'`) and reproduces the earlier results exactly (tested).

> **Technical detail.** `scenario_overrides()` builds `{(layer, param): level}` from `scenarios[name]['levels']`. A key can name a layer (`'programs'`) or one input (`'programs.cost_kw_yr_dr'`), and anything unlisted takes `default_level`. Central returns only its network values. The tornado and `project_layers()` without a scenario use every input at `level` (default central), which equals Central.

---

## 3. The layers

Each layer has its own switch (`enabled`). The waterfall adds them in this order.

| # | Layer | One line |
|---|---|---|
| — | Starting bill | Today's bill, line by line |
| 1 | System needs | Load growth, peak, growth vs asset-condition capex (both cases) |
| — | Network capacity | Loading bands, constrained sub-band, reinforcement, Upgrade Delay for Interconnection (both cases) |
| — | Published-plan BAU | BAU distribution capex from the utility's plan; addressable shares by category (3.3a) |
| 2 | Programs as core business | Surcharges leave the bill; flexible MW and efficiency paid for in rates |
| 3 | Deferral | Flexible headroom counted by the planner, so reinforcement is ordered later |
| 4 | Load enabled | Flexible headroom connects waiting load sooner |
| 5 | Capacity | Firm MW avoided at the zonal capacity price |
| 6 | Wholesale energy | Flexible load shifted from on-peak to off-peak hours |
| 7 | Avoided transmission | Transmission cost avoided by peak reduction |
| 8 | Avoided distribution losses | Marginal losses avoided |
| 8a | Additional savings objective | Savings the utility commits to find by unspecified means (default 0%) |
| 9 | Shared savings mechanism | The utility's share of the pool |
| 10 | ROE lever | Allowed ROE vs BAU, outside the pool |

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

*Capacity carve-out* (RG&E, Dominion, Pepco): where capacity is embedded in a supply line, a capacity line is derived and moved out of the parent line(s). The total bill is unchanged.

```
obligation_kw per customer = peak_mw x residential_share x obligation_scaling / residential_customers x 1000
capacity $/month           = obligation_kw x price ($/MW-day) / 1000 x 365 / 12
```

For Dominion the carved-out amount is split 91.5% from base generation and 8.5% from fuel.

*Starting adjustments* (Pepco): the residential increase authorised by Order No. 92607 (+$3.94/month) is added, because the tariff in effect at the as-of date was pre-case.

**Inputs.** The `starting_bill` lines (rate, unit, category, section, core flag, source, status); `capacity_carve_out`; `starting_adjustments`.

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
> `band_mode: 'generated'` makes `n_bands` equal-capacity bands at `mean + spread x (0.5 - i / (n - 1))`. If `mean_utilisation` is null, `mean` is the capacity-weighted mean of the explicit bands. Each band is capped at 1.0. A non-null `mean_utilisation` shifts every band by one amount (bisection) so the capacity-weighted mean equals it, each band capped at 1.0. The sub-band takes `share x DN0` of load and `share x DN0 / U` of capacity from the most loaded bands in turn, moving their growth and flex shares with the load; capacity shares are then recomputed.
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
  - Exelon-wide growth: Pepco's 2050 BAU bill $443/month, saving $25.79;
  - derived path (central): $419, saving $23.05;
  - no plan (2.5% growth): $401, saving $20.92.

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

**What it represents.** Under shared savings, utility-run programs (demand response, efficiency, electrification, DER and non-wires programs) stop being bill surcharges. They become utility spending recovered in rates: operating cost, plus a capitalised share in a regulatory asset. The utility then grows flexible resources by type, and efficiency, along a target path.

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
program RR_t        = program opex_t + amortisation_t + regulatory asset_t x WACC
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
- `uplift_mode`, `direct_uplift_pct`, `customer_funded_share`.
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
  - PJM: Brattle's 2025 CONE study, indicative Net CONE $528/MW-day UCAP = $192.7/kW-year, 2025 $. PJM's own 2027/28 Net CONE for DOM ($178/MW-day) and PEPCO ($292/MW-day) is below today's capped price.
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
- **(b) Accreditation** by resource type, replacing the programs derates in this formulation.
  - PJM 2028/29 ELCC class ratings: Demand Resource 91%; storage 4-hr 59%, 6-hr 68%, 8-hr 71%, 10-hr 78%; fixed-tilt solar 7%.
  - NYISO 2026-27 capacity accreditation factors (NYC Locality for Con Edison, Rest of State for RG&E; CHPE-In central and high, CHPE-Out low): Special Case Resources 70.2% / 74.2%; 4-hour storage 84.4% / 84.6%; solar 11.2% / 13.9%.
  - Storage is read from `accr_storage_by_duration` at `storage_duration_hr` (4).
  - Managed EV charging has no class in either market and keeps the programs derate (`_VERIFY`).
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

**Results** (utility-forecast pace; 2026–2050; customer savings and the capacity layer are $B undiscounted nominal, with NPV 3% in 2026 $ in brackets; monthly savings are the average residential bill, $/month nominal). The capacity layer is the capacity cost avoided: firm MW x price in the embedded formulation, and the avoided obligation in the default. `engine.layers.capacity_formulation_table()` produces it.

| Utility | Scenario | Formulation | Capacity layer $B (NPV 3%) | Customer savings $B (NPV 3%) | Monthly saving 2035 ($) | Monthly saving 2050 ($) |
|---|---|---|---|---|---|---|
| Con Edison | Cautious | embedded | 1.38 (0.86) | 11.81 (7.08) | 4.75 | 27.74 |
| Con Edison | Cautious | avoided obligation (default) | 2.29 (1.40) | 12.45 (7.46) | 5.05 | 29.02 |
| Con Edison | Central | embedded | 6.82 (4.23) | 37.85 (22.40) | 16.13 | 105.69 |
| Con Edison | Central | avoided obligation (default) | 10.45 (6.37) | 40.39 (23.90) | 17.28 | 111.10 |
| Con Edison | Ambitious | embedded | 9.79 (6.16) | 56.78 (33.94) | 24.52 | 139.53 |
| Con Edison | Ambitious | avoided obligation (default) | 14.61 (9.01) | 60.16 (35.93) | 26.09 | 146.21 |
| RG&E | Cautious | embedded | 0.04 (0.03) | 1.53 (0.95) | 4.46 | 14.17 |
| RG&E | Cautious | avoided obligation (default) | 0.13 (0.08) | 1.59 (0.98) | 4.58 | 14.60 |
| RG&E | Central | embedded | 0.60 (0.37) | 3.80 (2.33) | 10.88 | 37.56 |
| RG&E | Central | avoided obligation (default) | 1.68 (1.02) | 4.56 (2.78) | 12.17 | 43.88 |
| RG&E | Ambitious | embedded | 0.73 (0.46) | 6.17 (3.80) | 16.54 | 55.13 |
| RG&E | Ambitious | avoided obligation (default) | 1.98 (1.20) | 7.04 (4.32) | 18.05 | 62.22 |
| Dominion | Cautious | embedded | 1.27 (0.79) | 6.04 (3.74) | 2.77 | 5.60 |
| Dominion | Cautious | avoided obligation (default) | 1.67 (1.00) | 6.32 (3.88) | 2.75 | 5.78 |
| Dominion | Central | embedded | 6.30 (3.95) | 19.31 (11.76) | 6.64 | 15.79 |
| Dominion | Central | avoided obligation (default) | 7.25 (4.37) | 19.97 (12.06) | 6.44 | 16.32 |
| Dominion | Ambitious | embedded | 18.66 (11.74) | 47.07 (28.74) | 15.54 | 36.69 |
| Dominion | Ambitious | avoided obligation (default) | 20.47 (12.36) | 48.34 (29.18) | 14.82 | 37.94 |
| Pepco MD | Cautious | embedded | 0.59 (0.37) | 2.29 (1.46) | 6.65 | 11.75 |
| Pepco MD | Cautious | avoided obligation (default) | 0.85 (0.51) | 2.48 (1.56) | 6.63 | 12.45 |
| Pepco MD | Central | embedded | 1.09 (0.69) | 4.35 (2.73) | 11.01 | 24.31 |
| Pepco MD | Central | avoided obligation (default) | 1.29 (0.78) | 4.49 (2.79) | 10.80 | 25.10 |
| Pepco MD | Ambitious | embedded | 1.86 (1.18) | 6.07 (3.80) | 14.55 | 33.15 |
| Pepco MD | Ambitious | avoided obligation (default) | 2.10 (1.28) | 6.24 (3.87) | 14.09 | 34.26 |

- **The earnings opportunity grows with the avoided capacity.** The avoided-obligation formulation raises customer savings in every utility and scenario:
  - Con Edison Central: +$2.5B, from $37.8B to $40.4B.
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
  | Con Edison | 3.84 | 2.69 (to $43.08B) |
  | Dominion | 1.35 | 0.95 |
  | Pepco | 0.04 | 0.03 |
  | RG&E | 0.03 | 0.02 |

  For Con Edison it is over a quarter of the capacity layer ($14.3B with suppression), which is why it stays out of every scenario.

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
- The obligation factors are applied to the price inputs as given. The NYISO ICAP-to-UCAP translation is not modelled (`_VERIFY`).
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
- `in_pool`.

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

**Bill effect** (`bill_basis`):
- **'delivery'** (New York, where transmission is recovered in delivery rates): the distribution lines fall by `transmission_t / wires RR`.
- **'transmission_lines'** (PJM): the transmission lines fall by `transmission_t / (peak x cost_kw_yr x 1000 x growth / 1e6)`.

**Inputs.**
- `cost_kw_yr`: Con Edison $40.67 and RG&E $3.25 per kW-year (marginal transmission cost, BCA handbooks); Dominion $85.19 and Pepco $60.49 per kW-year (PJM network service rates, June 2026).
- `avoidable_share`: New York 1.0. PJM 0 / 0.5 / 1.0, because network service rates are average embedded costs: a lower peak shifts cost within the zone in the short run and avoids upgrades in the long run. `_VERIFY`.
- `bill_basis`, `in_pool`.

**Limitations.** PJM avoided transmission is a range, not a point estimate.

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
- **Programs takes a negative share.** Its costs come before the savings they enable, so it lowers the pool. Con Edison Central: programs −$2.00B, deferral +$0.90B, capacity +$2.13B, transmission +$0.72B, losses +$0.33B, wholesale +$0.20B, load enabled −$0.02B; total $2.26B.
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

**Customer dividend advance** (`advance_enabled`, default off). Customers receive part of their expected savings early, as a level annual bill credit, and repay it later through a rider. The defaults below apply once the advance is enabled.

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

**What the utility earns.** Under `utility_regulatory_asset`, the return on the balance (`advance_return_m`) is the utility's, reported separately from shared savings earnings. Under securitisation (the default) it is interest to bondholders. With bill-savings recovery, shared savings earnings are unaffected.

**Identities (tested).**
- Credits + financing − recoveries = the balance left in 2050.
- At the financing rate, the PV of credits = PV of recoveries + PV of that balance.

**What it costs customers.** Customers pay the financing cost of receiving their own savings earlier. Undiscounted customer savings are lower with the advance, although the credits are front-loaded.

**Stress case** (`advance_stress` in the export: sized on Central, realised Cautious). The larger credits run ahead of what Cautious delivers, so the true-up pauses the credits after the first years. That keeps the balance recoverable, and the export reports any balance left in 2050.

**Limitations.**
- The credit term (5 years) is the model's choice.
- The cap applies to all customers together and to the average residential bill, not to each class separately.
- An unrecovered balance is reported, not assigned.

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

  All three hold for the four utilities.
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

- **Results export** (`scripts/export_results.py`, `exports/<utility>.json`): every scenario × electrification pace. The Sankey value flows decompose customer savings exactly as `system_summary()` adds them up:
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

Of the measured inputs (sourced, derived or `_VERIFY`, i.e. excluding settings), about half are `_VERIFY`: Con Edison 48%, Dominion 47%, Pepco 52%, RG&E 64%. As a share of all status-tagged inputs, including the settings that each new feature adds, the figures are 34%, 33%, 37% and 44%. The shares fell when published-plan BAU was added, mostly because its new inputs are settings (basis, paths, addressable shares), and again with the avoided-obligation capacity inputs (3.6a), most of which are sourced from PJM, NYISO and NYSRC publications. [ASSUMPTIONS.md](ASSUMPTIONS.md) has the counts by layer.

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

`python -m pytest tests/` runs the full suite. The layered-model tests (`tests/test_layers.py`) check the following.

| Test | What it guarantees |
|---|---|
| `test_all_layers_off_equals_bau` | With every savings layer off, SS equals BAU |
| `test_starting_total_equals_starting_bill` | Year zero equals the sum of the starting-bill lines (carve-out moves dollars, adds none) |
| `test_pepco_order_adjustment` | The Order No. 92607 adjustment is applied (+$3.94 x (1 + gross receipts tax) on the bill) |
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
| `test_network_defaults_reproduce_1b09e20` | The network block reproduces the pinned 1b09e20 outputs with the sub-band and new layers off and the embedded capacity formulation: BAU exactly; shared savings exactly except the columns the code fixes change, and except where this commit's data changes apply (Dominion's demand-response path, Pepco's capacity price) |
| `test_full_utilisation_long_lead_gives_bau_queue` | A tight network produces waiting load in BAU |
| `test_subband_gives_bau_queue_and_keeps_totals` | The sub-band creates waiting load and keeps totals |
| `test_mean_utilisation_shift` | The mean shift hits its target |
| `test_network_override_order` | JSON < scenario network values < NETWORK_OVERRIDES < per-call `network=` (not `overrides=` or scenario levels) |
| `test_headroom_sweep_grid` | The sweep covers the grid; MW-years avoided rise from short to long delay |
| `test_subband_on_in_every_scenario_and_switchable` | The sub-band is on in every scenario and can be switched off |
| `test_upgrade_delay_mw_years_identity` | Delay MW-years equal the sum of MW waiting |
| `test_upgrade_delay_inputs_drive_the_wait` | With the backlog cleared at once, BAU waits for requests in 2028–2045 never exceed the input delay; BAU MW-years rise from low to central to high delays; slower clearance leaves more MW above the planning limit; no priority never shortens the wait |
| `test_flexibility_never_lengthens_upgrade_delay` | SS total delay MW-years and MW affected ≤ BAU |
| `test_value_layers_add_savings_and_sum` | Each value layer adds savings and lowers the 2050 bill; contributions and the waterfall sum to the full case |
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
| `test_capacity_formulations_reproduce_212efce` | The default reproduces 212efce's avoided-obligation runs exactly, and `'embedded'` reproduces that commit's default runs exactly (fixture `layers_212efce_capacity.json`) |
| `test_capacity_obligation_neutral_settings_reproduce_embedded` | With accreditation = the programs derates, coincidence 1, obligation 1, no lag and the bill-line price, the avoided-obligation results equal the embedded ones |
| `test_capacity_obligation_identities` | BAU unchanged; credit = lagged obligation x obligation factor x long-run avoided price; the long-run price is reached by `long_run_year`; a longer lag or lower coincidence never raises the layer |
| `test_capacity_price_suppression_sensitivity` | Suppression is zero before its start year and from `long_run_year`, never negative, adds savings only when on, and is ignored under `'embedded'` |
| `test_capacity_formulation_table` | Both formulations for every scenario; the default row matches `system_summary()` |

`tests/test_assumptions_register.py` checks two things:
- The assumptions register matches the JSON.
- Every layered input has a valid status.

`tests/test_export.py` checks that the exports balance and match direct runs. `test_program_costs_enter_once` sets every flexible cost per kW-year and the efficiency levelised cost to zero. Customer savings plus shared savings earnings then rise by exactly the original run's `program_costs` flow, and every value source is unchanged, so program costs enter the results once.

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
| **Customer dividend advance** | Level bill credit paid early, sized on recoverable savings, securitised, and recovered through a bill-savings rider (or from the pool), with a true-up and a cap |
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
