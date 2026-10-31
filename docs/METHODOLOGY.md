# GridDividend methodology

*The layered model (`engine/layers.py`, Section 13 of each state notebook). As of 31 October 2026.*

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

---

## 2. Structure

### 2.1 Two cases: BAU and shared savings

Each run projects two cases, year by year, from 2026 to 2050.

- **Business as usual (BAU):** the utility builds network capacity as load grows. Program surcharges stay on the bill, and today's flexibility programs continue at their current size.
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

> **Technical detail.** `scenario_overrides()` builds `{(layer, param): level}` from `scenarios[name]['levels']`. A key can name a layer (`'programs'`) or one input (`'programs.cost_kw_yr_dr'`), and anything unlisted takes `default_level`. Central returns only its network values. The tornado and `project_layers()` without a scenario use every input at `level` (default central), which equals Central.

---

## 3. The layers

Each layer has its own switch (`enabled`). The waterfall adds them in this order.

| # | Layer | One line |
|---|---|---|
| — | Starting bill | Today's bill, line by line |
| 1 | System needs | Load growth, peak, growth vs asset-condition capex (both cases) |
| — | Network capacity | Loading bands, constrained sub-band, reinforcement, Upgrade Delay for Interconnection (both cases) |
| 2 | Programs as core business | Surcharges leave the bill; flexible MW and efficiency paid for in rates |
| 3 | Deferral | Flexible headroom counted by the planner, so reinforcement is ordered later |
| 4 | Load enabled | Flexible headroom connects waiting load sooner |
| 5 | Capacity | Firm MW avoided at the zonal capacity price |
| 6 | Wholesale energy | Flexible load shifted from on-peak to off-peak hours |
| 7 | Avoided transmission | Transmission cost avoided by peak reduction |
| 8 | Avoided distribution losses | Marginal losses avoided |
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
MW connected sooner_t  = sum_b max(0, BAU waiting_b - SS waiting_b)
connection capex_t     = newly connected MW x 1000 x connection_cost_kw x (1 + inflation)^t / 1e6   (enters rate base)
incremental O&M_t      = MW connected sooner x 8.76 x load factor x incremental_om_mwh x (1 + inflation)^t / 1000
```

**What counts as newly connected.** Connection capex (and connection cost avoided, 4.5) is charged only when MW connected sooner rise above their previous maximum. Incremental O&M is charged on the whole stock.

**Efficiency also counts.** SS demand is net of efficiency, so efficiency that lowers demand in a waiting band also counts as MW connected sooner and attracts these costs. The effect is small: with deferral and load enabled both off, Con Edison still shows 3.1 MW connected sooner at peak, Dominion 5.0 MW.

**Bill effect versus system-wide effect.** The extra kWh enter sales, which lowers distribution cost per kWh. The load-enabled bar on the residential bill is **only the residential bill effect**. System-wide, the layer shows only its costs: connection capex, incremental O&M, and capacity for the extra load served. Its customer savings and its contribution to the pool are therefore slightly negative (Central: Con Edison −$65M, Dominion −$156M, Pepco −$8M, RG&E −$5M, undiscounted nominal). The benefit goes to the customers being connected and is reported in the access block (4.5).

**Inputs.**
- `locational_match`.
- `enable_share`, `connection_cost_kw`, `incremental_om_mwh`.
- `uplift_mode`, `direct_uplift_pct`, `customer_funded_share`.
- Flexibility targeting (network block).

**Double counting.**
- Each MW of headroom has one use. Headroom used never exceeds headroom created (tested).
- Deferral headroom can only carry load BAU would serve anyway.
- The former utilisation layer, a price discount not tied to any cost that overlapped with deferral, has been replaced.

**Limitations.**
- `locational_match` (the share of flexible MW where the network needs it) is `_VERIFY` and among the most influential inputs.
- Headroom is firm in the planning year; dispatch reliability is captured only through derates.

### 3.6 Capacity (layer 5)

**What it represents.** Lower peak demand lowers the utility's capacity obligation in the wholesale capacity market. The zones are NYISO NYC, NYISO Rest of State, PJM DOM and PJM PEPCO.

**Calculation** (as implemented):

```
price_t        = price_m_per_mw_yr x (1 + price_growth)^t          ($M per MW-year)
system peak_t  = peak_t - (network demand before efficiency - served load) - EE MW_t (SS, programs active)
peak reduction = min(firm flexible MW + EE MW, system peak)          (capacity layer on)
capacity cost  = (system peak - peak reduction) x price             ($M)
capacity bill  = starting capacity line x (price_t / price_0) x ((system peak - peak reduction - loss peak MW) / peak_2026) / (sales_t / sales_2026)
```

Load waiting for an upgrade does not buy capacity.

> **Code issue under review (not changed in this pass).** In the shared savings case, `(network demand before efficiency - served load)` already includes efficiency MW, the formula then subtracts efficiency MW again, and the peak reduction subtracts it a third time. Capacity MW billed are therefore `peak - waiting - firm flexible MW - 3 x EE MW` when the capacity layer is on. With the capacity layer off and programs active, the code adds one EE MW back, which leaves efficiency subtracted once. A first-order estimate of the extra capacity value is 2 x EE MW x price, summed 2026–2050 (Central, undiscounted nominal): Con Edison $3.2B, Dominion $4.3B, Pepco $1.0B, RG&E $0.2B. That is 14–25% of the customer savings reported (RG&E 14%, Con Edison 19%, Pepco 21%, Dominion 25%). The extra capacity cost also enters the pool, so about 30% of it appears as shared savings earnings, and the capacity bill line is lowered too. A fix would change results, so it needs the author's decision. See section 10.2.

**Inputs.** `price_m_per_mw_yr` (from `shared/capacity_markets/`), `price_growth`; derates by type (3.4).

**Interactions.** Avoided-loss peak MW (3.9) lower the capacity bill line; their value is booked in the losses layer, not here. Capacity cost is in the savings pool.

**Limitations.**
- One zonal price, with no price suppression.
- Pepco's capacity carve-out uses the 2026/27 price ($329.17/MW-day), but the capacity layer uses 2027/28 ($333.44/MW-day, $0.1217M per MW-year). The bill line scales with price_t / price_0, so bills are consistent; the pool's capacity cost and the bill line start from slightly different year-zero prices.
- RG&E uses NYISO Rest of State in the layered model.

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

### 3.10 Shared savings mechanism and the pool (layer 9)

**What it represents.** The savings pool is the year's net saving to customers from the reform. The utility earns `utility_share` of it (30% at Central) as **shared savings earnings**. Customers keep the rest.

**Calculation** (`pool_basis: 'revenue_requirement'`, the setting for all four utilities):

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

*Alternative basis* `'capex'` (available, not used):
- pool = avoided capex − new program spend + capacity cost avoided + value streams in the pool.
- Customers receive `(1 - utility_share)` of the pool as an explicit credit, through the rider.
- Earnings are not recovered from anyone, as in v1.0.
- Because the supply, transmission and capacity lines already fall by the full value, customers then receive the capacity and value streams about 1.7 times over.

Treat this basis as an upper bound.

**Inputs.** `utility_share` (low 0.40 / central 0.30 / high 0.10), `pool_basis`, each value layer's `in_pool`.

**Interactions.**
- The mechanism comes after the cost layers in the waterfall, so in the sequential pass all earnings fall on its step.
- `layer_contributions()` therefore also reports earnings attributable to each layer, adding layers in waterfall order with the mechanism on throughout.
- **That split depends on the order.** Programs alone make the pool negative, and carry-forward absorbs the next layers' savings. In Central, programs, deferral and load enabled are attributed zero earnings, and all earnings fall on capacity and the value layers. Con Edison, for example, attributes $1.95B to capacity, even though deferral adds $3.0B of customer savings. Read the column as "earnings in this order", not as each layer's earning power.

**Double counting.** Efficiency energy savings are not in the pool; they go wholly to customers. Each value stream enters the pool once.

**Limitations.**
- No performance corridor, cap or floor beyond carry-forward.
- No timing lag between saving and earning.

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

`layer_contributions()` adds layers one at a time and reports each layer's change in customer savings, the 2035 and 2050 bill, shared savings earnings (sequential and attributable) and the utility's equity return. Rows sum to the full case (tested).

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
- **MW connected sooner:** the sum over bands of max(0, BAU waiting − SS waiting) (2035, 2050, peak year). It includes efficiency that removes demand in waiting bands (3.5).
- **Upgrade Delay for Interconnection:**
  - BAU average, years per MW affected;
  - SS average per MW affected;
  - SS per MW affected in BAU (like-for-like);
  - MW affected;
  - **MW-years avoided** (BAU − SS MW waiting, summed over years).
- **Connection cost avoided by new customers:** increments of MW connected sooner and of flexible-connection MW x upgrade cost per MW x `customer_funded_share` (1.0 = upper bound), undiscounted and NPV 3%.
  - Flexible-connection MW also count as deferral headroom, which lowers utility reinforcement for all customers. Crediting them here as well counts the same avoided upgrade twice.
  - The access block is not added to customer savings, so the double count affects only this measure.
  - It is large: flexible connections are about 90% of the measure (Con Edison Central $705M, or $67M without flexible connections).
  - See 10.2.
- **Electrification brought forward:** GWh served sooner x electrification share of network growth.

### 4.6 Tornado and headroom sweep

- **Tornado** (`tornado()`): every input with a spread is set to low and then high, one at a time, everything else central. The output is the change in the monthly saving in 2035 and 2050, ranked by the 2050 swing.
- **Headroom sweep** (`headroom_sweep()`): Central, varying three things:
  - mean starting utilisation (60% to 100% in 5-point steps);
  - sub-band share (0, 2, 4.3, 8, 15%);
  - Upgrade Delay case: short (low delays, high clearance), central, or long (high delays, low clearance).

  Each point reports the 2050 saving and every `system_summary()` measure.

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

Roughly half of the status-tagged inputs are `_VERIFY`: Con Edison 47%, Dominion 44%, Pepco 50%, RG&E 59%. [ASSUMPTIONS.md](ASSUMPTIONS.md) has the counts by layer.

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
| `test_headroom_used_never_exceeds_headroom_created` and `test_headroom_used_never_exceeds_created_with_subband` | One use per MW of headroom; MW connected sooner ≤ load-enabled headroom + efficiency MW |
| `test_network_served_never_exceeds_demand_or_capacity` | Served load ≤ demand and ≤ operating limit x capacity + headroom |
| `test_served_never_exceeds_operating_limit` | Served load ≤ operating limit + headroom |
| `test_one_band_equals_single_pool_model` | One band reproduces the single-pool model exactly (fixture at ebb0c04) |
| `test_bands_sum_to_network_totals` | Bands sum to network load and capacity |
| `test_ramp_limit_respected` | MW growth never exceeds the ramp limit |
| `test_access_zero_with_layers_off` | No access benefits without layers |
| `test_network_defaults_reproduce_1b09e20` | The network block reproduces the pinned 1b09e20 outputs with the sub-band and new layers off |
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

`tests/test_assumptions_register.py` checks two things:
- The assumptions register matches the JSON.
- Every layered input has a valid status.

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
- **Proxies.** About half the inputs are `_VERIFY`, including network loading for three utilities.
- **One benchmark customer.** The average residential bill applies system efficiency to residential usage. No customer classes or low-income detail.
- **Fixed customer charges scale with the wires revenue requirement per kWh**, like the volumetric lines.
- **Efficiency energy** is valued at the residential supply rate for all classes.
- **Not modelled yet:** resilience, capacity price suppression, the economic value of faster connections, emissions. These would be reported separately, not on the bill.
- **No feedback** from bills to demand, and no utility behavioural response beyond the stated paths.

### 10.2 Code issues found in the documentation pass (not changed)

1. **Efficiency peak MW counted more than once in capacity** (3.6). Billed capacity MW subtract efficiency MW three times with the capacity layer on, and once with it off. The first-order effect is 2 x EE MW x capacity price a year, 14–25% of reported customer savings. Shared savings earnings and the capacity bill line are affected too. A fix would change results.
2. **Program-transfer neutrality with waiting load.** In SS, core programs are recovered per kWh served. Where load waits for an upgrade, the rider is slightly higher than the BAU surcharge (about $0.003/month at most). This is why the neutrality test runs with the sub-band off.

3. **Flexible connections counted twice** (4.5). The same MW are deferral headroom and are credited in full as connection cost avoided by new customers. This affects only the access measure, which they make up about 90% of.
4. **Earnings attributable depends on layer order** (3.10). Carry-forward assigns zero to programs, deferral and load enabled.
5. **Efficiency counts as MW connected sooner** (3.5), and attracts connection capex and O&M. The effect is small.
6. **The `'capex'` pool basis** (not used by any utility) gives customers the capacity and value streams about 1.7 times over (3.10).
7. **Status labels.** In all four JSONs, `transition_year`, `existing_capitalised`, `uplift_mode`, `customer_funded_share` and `pool_basis` are tagged `sourced`, and `enable_share` `_VERIFY`, although each source says "Setting". Relabelling them `setting` would change the status counts, not results.

Load enabled shows as a small net cost system-wide (3.5). This is the intended design, because its benefit is in the access block. The independent documentation check that found items 3–7 is recorded in [CHANGELOG.md](../CHANGELOG.md).

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
| **Earnings attributable** | Each layer's change in shared savings earnings with the mechanism on throughout |
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
| **MW connected sooner** | Sum over bands of max(0, BAU waiting − SS waiting) |
| **MW waiting for upgrade** | Demand not served because capacity is not yet in service |
| **MW-years avoided** | BAU minus SS MW waiting, summed over years |
| **Operating limit** | Equipment rating, 1 / planning limit factor x planning capacity; existing load is served up to it |
| **Planning capacity / planning limit** | 80% of rating; loading 1.0 |
| **Planning headroom** | Margin the planner keeps above demand (10%) |
| **Pool (savings pool)** | Net saving to customers in a year, before the utility's share; negative pools are carried forward |
| **ROE lever** | Change in allowed ROE in SS, outside the pool |
| **Seed pipeline** | Reinforcement already under way at 2026 |
| **Shared savings earnings** | The utility's share of the pool: its earnings opportunity |
| **Transition year** | Year programs become core business (2028) |
| **Upgrade Delay for Interconnection** | Time a new customer in a constrained area waits for the grid upgrade before connecting |
| **Value stack** | Value per kW-year of flexible resources: capacity, deferral, load enabled |
| **Value-stream layers** | Wholesale energy, avoided transmission, avoided distribution losses |
| **_VERIFY** | An input awaiting confirmation |
