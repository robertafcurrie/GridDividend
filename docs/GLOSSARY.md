# GridDividend glossary

Plain-language definitions of the terms used in the [README](../README.md), the [methodology](METHODOLOGY.md) and the state notebooks. They are in three groups, as in the web explorer:

1. [Parts of a bill](#1-parts-of-a-bill): the lines on a residential electricity bill.
2. [How rates are set](#2-how-rates-are-set): regulation, rate cases and markets.
3. [Terms in the model](#3-terms-in-the-model): what GridDividend calculates and the names it uses.

Where the model or the data use an internal name, it is shown in `code` after the plain term. Groups 1 and 2 are mostly alphabetical; group 3 is arranged by topic.

---

## 1. Parts of a bill

| Term | Plain meaning |
|---|---|
| **Average residential bill** (`avg_bill_total`) | What a typical household actually pays each month. In the model, energy efficiency lowers the household's usage, so this bill falls with usage as well as with rates. It is the headline bill measure. |
| **Benchmark usage** (`benchmark_kwh_month`) | A fixed monthly usage (600 kWh in New York, 900 kWh for Pepco, 1,000 kWh for Dominion) used to compare bills on the same footing. |
| **Benchmark-usage bill** (`bill_total`) | The bill at the benchmark usage. Because usage is held fixed, it shows only the effect of rate changes. |
| **Bundled service** | The utility supplies both delivery and the electricity itself. Most residential customers are on bundled service. |
| **Capacity** (`capacity`) | The cost of paying power plants and other resources to be available at the hour of peak demand. Bought in PJM's or NYISO's capacity market. It is usually hidden inside the supply or generation line; the model splits it out (see *capacity carve-out*). |
| **Clean Energy Standard (CES) surcharges** (New York) | Charges that pay for renewable energy credits (`cess_rec`), zero-emission credits for nuclear plants (`cess_zec`) and the environmental value of distributed generation (`cess_env`), plus a delivery-side CES charge (`cesd`). |
| **Consumption tax** (Virginia) | A state and local tax per kWh, on the first 2,500 kWh a month. |
| **Customer charge / basic customer charge** (`customer_charge`) | A fixed monthly charge, the same however much electricity you use. It covers metering, billing and part of the wires. |
| **Deferred fuel cost charge** (Dominion) | A charge repaying fuel costs the utility paid but did not collect in 2022–2023, refinanced with low-cost bonds (*securitisation*). |
| **Delivery** | Everything to do with moving electricity to your home: the local wires (distribution), in New York the high-voltage lines (transmission), and the programs recovered alongside them. The utility always provides delivery, even if you buy supply from someone else. |
| **Delivery charge / energy delivery charge / distribution kWh charge** (`energy_delivery`, `delivery_charge`, `distribution_kwh`) | The main per-kWh charge for using the local wires. |
| **Delivery-only service** | You buy delivery from the utility and supply from a retail supplier. EIA reports these customers separately, which lets the model split average bills into delivery and supply. |
| **Distribution base** (`distribution_base`) | Bill category: the delivery charges set in the base rate case (customer charge plus delivery charge). |
| **Distribution riders** (`distribution_rider`) | Bill category: delivery charges collected outside the base rate. Examples are adjustment clauses, decoupling adjustments, Dominion's Rider DIST (undergrounding and grid transformation) and Pepco's Grid Resiliency Charge. |
| **EmPOWER Maryland charge** (Pepco, `empower`) | The surcharge that funds Maryland's energy-efficiency and demand-response programs. |
| **Fuel factor / fuel charge** (Dominion Rider A, `fuel`) | The per-kWh charge recovering the fuel and purchased energy used to make your electricity. It is reset each year. From 2026 it also carries Dominion's purchased capacity. |
| **Generation charge** (Dominion, `generation_kwh`) | The base-rate charge for Dominion's own power plants. |
| **Gross receipts tax (GRT)** | A tax on the utility's revenue, passed through to customers as a percentage of the bill. |
| **Merchant function charge (MFC)** (New York) | Recovers the utility's cost of buying electricity for customers on its supply service (procurement, working capital, bad debt). |
| **Market supply charge (MSC)** (Con Edison) | The supply charge: energy (`msc_energy`) and capacity (`msc_capacity`) bought in NYISO's markets, passed through at cost. |
| **Monthly adjustment clause (MAC)** (Con Edison) | A delivery adjustment that reconciles certain costs and revenues to rate-plan targets. |
| **Non-bypassable** | A charge every customer pays, even those who buy supply from another supplier. |
| **Program surcharge** (`program_surcharge`) | Bill category: charges that fund programs such as energy efficiency, demand response, EV make-ready, clean energy standards and low-income help. Some are *core business* under shared savings (see group 3). |
| **Revenue decoupling adjustment** (`rdm`, Pepco `rider_bsa`) | A small per-kWh adjustment that trues the utility's delivery revenue back to the amount the regulator allowed, so the utility neither gains from higher sales nor loses from lower ones. |
| **Rider** | A separately approved charge, outside base rates, for a specific cost (a power plant, a program, transmission, fuel). Virginia calls them rate adjustment clauses (RACs). |
| **Standard offer service (SOS)** (Maryland) | Pepco's default supply service for customers who do not choose a retail supplier, priced from wholesale auctions (`sos_generation`, `sos_transmission`). |
| **Supply / supply energy** (`supply_energy`) | Bill category: the electricity itself (energy), the fuel factor and supply-side riders. Separate from delivery. |
| **System benefits charge (SBC)** (New York) | Surcharges that fund NYSERDA's clean energy programs and the utilities' energy-efficiency programs. |
| **Taxes and fees** (`taxes_and_fees`) | Bill category: gross receipts, sales and use, consumption and local energy taxes. |
| **Transmission** (`transmission`) | Bill category: the cost of the high-voltage network. A separate line in PJM (Dominion `transmission_kwh` + Rider T1, Pepco `sos_transmission`). Inside the delivery charge in New York. |
| **Universal service charge / PIPP** | Funds bill assistance for low-income customers (Maryland Rider USC, Virginia's Percentage of Income Payment Program). |
| **VDER cost recovery** (Con Edison) | Recovers payments to distributed energy resources under New York's Value of DER tariff. |

## 2. How rates are set

| Term | Plain meaning |
|---|---|
| **Allowed return / ROE** (return on equity) | The profit rate the regulator lets the utility earn on the shareholders' share of its investment (for example 9.4%). It is a ceiling on what rates are designed to deliver, not a guarantee. |
| **ATRR** (annual transmission revenue requirement) | In PJM, the yearly amount a transmission owner may collect for its network, set by a FERC formula rate. |
| **Base rates** | The rates set in a rate case for the utility's own costs, as distinct from riders and pass-through charges. |
| **Biennial / triennial review** (Virginia) | Virginia's periodic base-rate review of Dominion, every two years since 2023 (three before). It sets the allowed return and checks whether Dominion over-earned. |
| **Bridge (revenue-requirement bridge)** | A step-by-step walk from one year's revenue requirement to another's, showing what drove the change. |
| **Capacity market** | A market where the grid operator pays resources to be available at peak. In PJM it is the Base Residual Auction (BRA), priced in $/MW-day; NYISO runs monthly ICAP auctions priced in $/kW-month. |
| **Capital structure / equity ratio** | How the utility's investment is financed: the share from shareholders' equity (for example 48%) against debt. |
| **Class allocation / revenue allocation** | How a rate increase is shared between customer classes (residential, commercial, industrial). |
| **Cost of debt** | The interest rate the utility pays on its borrowing, as allowed in rates. |
| **Cost of service study** | A study that assigns the utility's costs to customer classes. It guides revenue allocation. |
| **Customer class / service class** (for example SC 1, Schedule R) | Customers grouped by type, each with its own rates. SC 1 and Schedule R are residential. |
| **Decoupling** | Separates the utility's revenue from its sales, so energy efficiency doesn't cost it revenue (see *revenue decoupling adjustment* in group 1). |
| **Deferral (regulatory)** | Recording a cost or a credit now and recovering or returning it in later rates. Not the same as the model's deferral of grid upgrades. |
| **Delivery-only revenue** (EIA-861 Part C) | Revenue from customers who buy only delivery from the utility. |
| **Depreciation** | The yearly recovery of the cost of an asset over its life. It is part of the revenue requirement and lowers the rate base as assets age. |
| **Earnings sharing mechanism** | If the utility earns above its allowed return, part of the excess goes back to customers. |
| **EIA-861** | The US Energy Information Administration's annual survey of utility sales, revenue and customers. The model uses it for average bills, sales shares and customer counts. |
| **ELCC** (effective load-carrying capability) | How much a resource counts toward meeting peak demand, as a share of its size. Batteries, demand response and solar each have their own rating. |
| **Embedded cost** | The average cost of the existing system, as opposed to the cost of adding more (*marginal cost*). |
| **Equipment material condition** | PJM's driver for transmission projects that replace ageing equipment, as opposed to load growth. |
| **FERC** | The Federal Energy Regulatory Commission. It regulates transmission rates and returns and wholesale markets; states regulate distribution and retail rates. |
| **FERC Form 1** | The annual financial report every major utility files with FERC: plant, expenses and taxes by function. |
| **Formula rate** | A FERC transmission rate that resets each year from the utility's actual costs. |
| **Fuel factor proceeding** | Virginia's annual case resetting Dominion's fuel charge. |
| **Functional basis** | Costs sorted by function (generation, transmission, distribution, customer service) as in Form 1. |
| **ICAP / UCAP** | Installed and unforced capacity: a resource's rated size, and its size after allowing for outages. Capacity prices are quoted per unit of UCAP. |
| **IRP** (integrated resource plan) | A utility's long-term plan for meeting demand. |
| **Joint proposal** (New York) | A settlement of a rate case negotiated by the utility, Department of Public Service staff and other parties, then adopted (or not) by the Commission. |
| **Jurisdictional share** | The part of a multi-state utility's costs belonging to one state (for example Pepco's Maryland share). |
| **Levelized** | An increase spread evenly across the years of a rate plan, instead of rising in steps. |
| **Load serving entity (LSE)** | A company that buys power for customers in a zone; a zone can have several (for example Dominion and co-operatives in PJM's DOM zone). |
| **Local transmission plan (LTP)** (New York) | Each transmission owner's plan for its local transmission system, filed through NYISO. |
| **LDA / locality / zone** | A part of a market with its own capacity price or rate (PJM zones such as DOM and PEPCO; NYISO's New York City locality). |
| **Marginal cost of service (MCOS)** | The cost of serving one more kW of peak demand on a part of the network. New York utilities publish it in their benefit-cost (BCA) handbooks. |
| **Multi-year rate plan** | A rate case that sets rates for several years at once (rate years 1, 2, 3). |
| **NITS** (network integration transmission service) | PJM's transmission service for serving load. Each zone's NITS rate is its ATRR divided by its network service peak load. |
| **Net CONE** | The net cost of new entry: what a new peaking plant needs from the capacity market to be built. It anchors long-run capacity prices. |
| **Network service peak load (NSPL)** | A customer group's demand at the zone's peak hour. PJM uses it to share transmission costs within a zone. |
| **NWA / NWS** (non-wires alternative / solution) | A program (flexibility, efficiency, storage) used instead of building or upgrading wires. |
| **O&M** (operations and maintenance) | The utility's running costs: staff, repairs, customer service and administration. |
| **Pass-through** | A cost recovered from customers at what the utility paid, with no profit (energy, capacity, fuel). |
| **Performance-based regulation / earnings adjustment mechanism (EAM)** | Rules that tie part of the utility's earnings to outcomes such as reliability, interconnection speed or demand response. Shared savings is one form. |
| **Property tax** | Tax on the utility's plant. It is recovered in rates and grows with the rate base. |
| **Rate base** | The value of the utility's invested assets (plant less depreciation) on which it earns its allowed return. |
| **Rate case** | The proceeding in which the regulator sets base rates: the utility files a request, parties respond and the commission decides. |
| **Rate-case step** | The increase approved for a given year of a rate plan (for example Con Edison's 2026 step of $234M). |
| **Rate design** | How a class's revenue is collected: the fixed customer charge, per-kWh charges and demand charges. |
| **Rate year (RY)** | A year of a rate plan. It may not match the calendar year. |
| **Regulatory asset** | A cost the regulator lets the utility recover over several years, earning a return meanwhile. |
| **Reliability need** | A projected violation of planning standards (an overloaded line or a shortfall at peak) that triggers a transmission project. |
| **Retail choice** | Customers may buy supply from a retail supplier. Maryland and New York have it; Virginia largely does not. |
| **Revenue requirement (RR)** | The total the utility may collect in a year: return on rate base + depreciation + O&M + taxes. |
| **RTEP** (Regional Transmission Expansion Plan) | PJM's annual transmission plan. *Baseline* projects meet reliability criteria (often load growth); *supplemental* projects are proposed by the transmission owner (customer service, equipment condition); *Window* projects are competitively solicited (for example 2024 RTEP Window 1). |
| **Securitisation** | Refinancing a cost with low-interest bonds repaid by a dedicated, non-bypassable charge. |
| **Settlement agreement** | A negotiated outcome of a case, approved by the commission (Virginia's term for a joint proposal). |
| **Shared savings** | A regulatory model in which the utility earns a share of the savings it creates for customers, instead of earning only on the assets it builds. |
| **State commissions** | The New York Public Service Commission (PSC, with its staff, the Department of Public Service, DPS); the Virginia State Corporation Commission (SCC); the Maryland Public Service Commission (MD PSC). |
| **Temporary rates** | Rates set while a case is pending, subject to full reconciliation once the final order is issued (RG&E, May 2026). |
| **Test year** | The 12 months of costs a rate case is based on: historic (past actuals) or forecast. |
| **True-up / reconciliation** | Settling the difference between what was collected and what was actually owed, in later rates. |
| **WACC** (weighted average cost of capital) | The blended return on equity and cost of debt, weighted by the capital structure. Rate base × WACC is the return in the revenue requirement. |
| **State laws and programs** | CLCPA: New York's 2019 climate law. VCEA: the Virginia Clean Economy Act (2020). GTSA: Virginia's Grid Transformation and Security Act (2018). EmPOWER: Maryland's efficiency program. RGGI: the Regional Greenhouse Gas Initiative. |

## 3. Terms in the model

### Structure and cases

| Term | Plain meaning |
|---|---|
| **BAU** (business as usual) | The future without reform: the utility follows its published plan, and programs stay as surcharges. |
| **SS / shared savings case** (`ss`) | The future with the shared-savings reform. It is compared with BAU. |
| **EASE Act / EASE Case** | The proposed Electricity Affordability, Savings, and Efficiency Act that would enact shared savings. "EASE Case" is the modelled outcome if it passed, against BAU. Illustrative only. |
| **Layered model** | The current model (`engine/layers.py`, notebook Section 13). It adds the reform one layer at a time so each layer's effect can be seen. |
| **Earlier model / v1.0 / CORRECTED** | The original model (`engine/model.py`, notebook Sections 1–12, `GridDividend_v1.0.ipynb`), kept so its results reproduce exactly. CORRECTED is a preset of recommended fixes; it is not the default. |
| **Layer** | One part of the reform added in turn: system needs, programs, deferral, load enabled, capacity, wholesale energy, transmission, losses, objective, mechanism, ROE. |
| **Scenario** | Cautious (today's programs, grown modestly), Central (flexibility anchored to state targets and studies) or Ambitious (what supportive policy could unlock). Results are ranges across them, not forecasts. |
| **Electrification pace** (`utility_forecast`, `state_policy`) | Whether BAU load follows the utility's own forecast (central) or the state's electrification policy. |
| **Transition year** (`transition_year`) | The year programs become core utility business (2028), or 2027 with *fast start*. |
| **Starting bill** (`starting_bill`) | Today's residential bill, line by line, with a source for every line. It is year zero of the projection. |
| **Capacity carve-out** (`capacity_carve_out`) | Splitting the capacity cost out of the bill line it is hidden in. The total bill is unchanged. |
| **Starting adjustment** | A known change applied to the starting bill (Pepco's Order No. 92607, +$3.94/month). |

### The layers

| Term | Plain meaning |
|---|---|
| **System needs** (`system_needs`) | Load growth (baseline, electrification, data centres) and the grid it needs. Applies to both BAU and shared savings. |
| **Programs as core business** (`programs`) | Flexibility and efficiency run by the utility as part of its business, instead of as surcharge-funded programs. |
| **Deferral** (`deferral`) | Grid upgrades deferred: flexibility lets the planner order reinforcement later. |
| **Load enabled** (`load_enabled`) | New load connected sooner because flexibility frees up grid space. Its bill bar shows only the effect on residential bills. |
| **Capacity** (`capacity`) | Lower peak demand means less capacity to buy. |
| **Wholesale energy** (`wholesale_energy`) | Energy bought off-peak instead of on-peak (load shifting). |
| **Avoided transmission** (`transmission`) | Lower transmission costs from a lower peak. |
| **Avoided distribution losses** (`losses`) | Less energy lost as heat on the wires. |
| **Additional savings objective** (`objective`) | Extra savings the utility commits to find by any means, net of the cost of finding them. Off by default. |
| **Mechanism** (`mechanism`) | The utility's share of the savings: how the pool is split between the utility and customers. |
| **ROE lever** (`roe`) | A change in the utility's allowed return, outside the pool. A separate policy lever. |
| **Value-stream layers** | Wholesale energy, avoided transmission and avoided losses. |

### Network and access

| Term | Plain meaning |
|---|---|
| **Addressable share** (`addressable_*`) | The part of a capital category that shared savings could defer, avoid or right-size. |
| **Backlog clearance** (`backlog_clearance_pct`) | The share of the existing overload in constrained areas fixed each year. |
| **Band / loading band** (`bands`) | A group of substations at similar loading, standing in for the real network. |
| **Constrained sub-band** (`subband_*`) | The small part of the network already above its planning limit (default 4.3% of load at 112.5%). |
| **Deferrable share** | How much of BAU's reinforcement the network model shows can be avoided. |
| **Firm flexible MW / derate** (`derate_*`) | The part of flexible capacity that can be counted on at peak. |
| **Firm MW** | Firm flexible MW plus efficiency's peak reduction. |
| **Flexible connection** (`flex_conn_*`) | A large load (for example a data centre or EV hub) connected on terms that let the utility curtail it at peak. |
| **Flexible headroom** | Grid space freed by flexibility: firm flexible MW in the right places plus flexible connections. |
| **Headroom sweep** | Results across a grid of network assumptions (starting loading, sub-band size, delay). |
| **Locational match** (`locational_match`) | The share of flexibility located where the network needs it. |
| **MW connected sooner** | New load connected earlier than in BAU. |
| **MW waiting for upgrade** (`upgrade_wait_mw`) | Demand that cannot connect until an upgrade is finished. |
| **Planning limit / operating limit** | The loading planners design to (80% of rating) and the most the equipment can carry. |
| **Plan categories** (growth, replacement, grid modernisation, other) | The published capital plan split by what drives it. |
| **Published-plan BAU** (`bau_plan`) | BAU spending taken from the utility's published capital plan, extended to 2050 (`beyond_path`: continue, taper or policy; `taper_year`). |
| **Link growth to load** (`link_growth_to_load`) | Scales the plan's growth spending up or down with the model's load growth. |
| **Seed pipeline** | Upgrades already under way in 2026. |
| **Upgrade Delay for Interconnection** (`upgrade_delay_*`) | The time a new customer in a constrained area waits for the grid upgrade before connecting. |
| **Access block** | Benefits to customers being connected (sooner connection, delay avoided, connection costs avoided). Reported apart from the bill. |

### Capacity, transmission and other values

| Term | Plain meaning |
|---|---|
| **Accreditation** (`accr_*`) | How much each resource counts toward the capacity requirement (ELCC). |
| **Auction lag** (`auction_lag_years`) | Years before a lower peak shows up in the capacity bought (PJM 3, NYISO 1). |
| **Avoided obligation** (`avoided_obligation`, default) | Capacity formulation: the capacity the utility no longer has to buy, accredited by resource type, coincidence-adjusted and lagged by the auction, at the long-run price. |
| **Embedded** (`embedded`) | The earlier capacity formulation: firm MW × today's bill-line capacity price. Kept as an option. |
| **Coincidence** (`system_coincidence`, `local_coincidence`) | How much a resource's peak reduction lines up with the system's (or the zone's) peak hour. |
| **Price suppression** | A lower requirement lowering the capacity price itself. A sensitivity only, off by default. |
| **Avoidable share** (`avoidable_share`) | In the single transmission formulation (the earlier default, now an option), the share of the transmission cost per kW that a lower peak avoids. |
| **Single / split transmission formulation** (`formulation`) | Split (default): (b) transmission upgrades deferred, counted in savings, and (a) lower share of zonal transmission costs, reported separately. Single (option, the earlier default): one value per kW. |
| **Lower share of zonal transmission costs** (allocation effect, transmission (a); `transmission_allocation_m`) | In PJM each zone's transmission cost for the year is fixed and shared out by each group's demand at the zone's peak hour. When these customers' peak falls, their share of that fixed cost falls. Nothing is avoided: the cost is moved, not saved. It is 0 in New York, where the utility recovers its transmission costs from its own customers. **It is reported separately, as its own line, and is not counted in headline customer savings, the bills or the shared-savings pool, so the utility earns nothing on it.** A switch (`allocation_in_headline`, off by default) adds it to the headline and bills for comparison only; it never enters the pool. |
| **Cost shifted to others in the zone** (`transmission_cost_shifted_m`) | The other side of a lower share of zonal transmission costs. The zone's fixed cost is spread over a smaller peak, so the rate rises and the zone's other customers pay what these customers no longer pay (for Dominion, co-operative and municipal customers in the DOM zone; for Pepco MD, Pepco DC and SMECO customers). It is reported alongside the saving, never netted against it. |
| **Transmission upgrades deferred** (avoided build, transmission (b); `transmission_build_avoided_m`) | Transmission investment that would have served load growth, built later or not at all because planners see a lower peak. It is the load-driven share of the published transmission investment, deferred in proportion to the reduction in planning peak from firm flexibility and flexible connections, after the planning lag, and scaled by the realisation. The avoided investment lowers the transmission revenue requirement over time. In PJM, these customers get their zone share of that saving and the rest of the zone gets the remainder (`transmission_build_other_zone_m`). |
| **Realisation** (`avoided_build_share`) | How much of the possible transmission deferral the transmission planner actually acts on, as a share. It depends on who plans the transmission: for **Dominion and Pepco**, PJM plans regional transmission (the RTEP), so the utility can only offer a lower peak for PJM to count: Cautious 0 / Central 0.5 / Ambitious 1.0 (`_VERIFY`, documented assumptions); for **Con Edison and RG&E**, the utility plans its own local transmission (local transmission plan, rate case) alongside distribution, so it gets the same realisation as the distribution growth-capex addressable share: Cautious 0.5 / Central 0.8 / Ambitious 1.0 (setting). The deferral also waits for the planning lag (7 years; 5–10). |
| **Load-driven share** (`load_driven_share`) | The part of planned transmission investment that serves load growth, rather than retirements, ageing equipment or public policy. |
| **Planning lag** (`planning_lag_years`) | Years between a lower planning peak and the transmission investment it defers (7). |
| **Marginal loss multiplier** | How much more is lost on the wires at the margin, and at peak, than on average. |

### Programs and savings

| Term | Plain meaning |
|---|---|
| **Core business / core program** | A program that moves from a surcharge into the utility's business under shared savings, earning shared savings earnings. |
| **Cost at which flexibility pays for itself** (`flex_pays_cost`) | The flexibility cost per kW-year at which the shared-savings bill equals BAU. |
| **Customer savings** | What all customers save against BAU: revenue requirement net of the utility's earnings, program costs, capacity, efficiency energy and each value stream. |
| **Efficiency energy** | Energy not bought because efficiency lowers usage, valued at today's residential supply rate. |
| **Incremental MW** | Flexible MW above today's programs. |
| **Ramp limit** (`ramp_pct_peak_*`) | The fastest flexible MW can grow each year, as a share of peak. |
| **Savings pool / pool** | The net saving in a year before it is split: BAU minus shared-savings revenue requirement, net of program costs, plus value streams counted in the pool (`in_pool`). |
| **Negative pool, carried forward** | Early years can cost more than they save. The shortfall is netted against later savings. |
| **Shared savings earnings** | The utility's share of the pool: its earnings opportunity. |
| **Utility share** (`utility_share`, earlier model `UTILITY_SAVINGS_SHARE`) | The fraction of the pool the utility keeps (30% central). |
| **Cost to achieve** (`objective_cost_to_achieve_pct`) | The cost of finding the additional savings objective, netted from it. |

### Mechanism options

| Term | Plain meaning |
|---|---|
| **Fast start** (`fast_start`) | Savings start in 2027, with near-term ramps for capacity, program MW and the plan's addressable shares. |
| **Customer dividend advance** (`advance_*`) | An early, level bill credit paid before the savings arrive, financed (securitised, or as a regulatory asset) and recovered later from the savings, with a true-up and a cap that keeps customers' net saving at or above zero. |
| **Recoverable savings** | The savings the advance can be repaid from. |
| **Stress case** | The advance sized on Central but realised on Cautious. |
| **Customer allocation** (`customer_allocation`: `by_sales`, `per_customer`, `custom`) | How customers' share of the pool is split between residential and non-residential customers: by sales (default), equally per customer, or a set share. Costs follow the benefits they buy; only savings are reallocated. |

### Outputs

| Term | Plain meaning |
|---|---|
| **Earnings per rate base** | The utility's earnings per dollar of rate base, BAU against shared savings. |
| **Layer contributions** | Each layer's share of customer savings, pool and earnings. |
| **Sankey / value flows** | A diagram of where the savings come from and who receives them. |
| **Tornado** | Change in the result when one input moves from low to high, the others held at central. |
| **Value stack** | Value per kW-year of flexibility by source (capacity, deferral, load enabled). |
| **Waterfall** | The bill stepping from BAU to shared savings, one layer at a time. |
| **Exports** | JSON results for the web explorer (`exports/<utility>.json`). |

### Data, statuses and money

| Term | Plain meaning |
|---|---|
| **sourced** | Read directly from a cited document. |
| **derived** | Calculated from sourced figures; the method is stated. |
| **`_VERIFY`** | An estimate, assumption or proxy awaiting confirmation. |
| **setting** | A model switch or choice, not a measured value. |
| **Low / central / high** | The range for an input. Scenarios and the tornado pick a level. |
| **Nominal / 2026 $** | Dollars of each year, or adjusted to 2026 purchasing power. |
| **Undiscounted / NPV** | Simply added up, or discounted to a present value (at 3% unless stated). |
| **Proxy** | Another utility's or region's data used where the utility's own is not published. |
| **Assumptions register** | The generated list of every input with its source and status ([ASSUMPTIONS.md](ASSUMPTIONS.md)). |

### Look-back, 2021–2026

| Term | Plain meaning |
|---|---|
| **Look-back** | How each utility reached its 2026 starting point ([METHODOLOGY section 12](METHODOLOGY.md#12-starting-point-20212026)). |
| **Like-for-like bill trend** | The EIA average bill, 2021–2025, at the benchmark usage, measured the same way each year. |
| **Grouped bridge** | The revenue-requirement change grouped into capital-driven, cost of capital, operating and the rate-case step. |
| **Capital-driven** | Change caused by investment: return on new rate base, depreciation, property tax on plant, income tax on the return. |
| **Normalised O&M** | Running costs excluding non-service pension and retiree-benefit costs, which can swing with financial markets. |
| **Non-service pension cost** | The parts of pension and retiree-benefit cost other than benefits earned that year (interest, expected investment returns, amortised gains and losses). |
| **Property tax attributed to plant** | Property tax assigned to the wires in proportion to their book value. |
| **Asked against granted** | The revenue increase a utility requested against what the commission approved. |
| **Rider bridge** (Dominion) | Dominion's bill split into base rates, fuel and riders by group, year by year. |
| **Supply side (influenced, not controlled)** | Costs set by markets or other regulators (capacity, energy, transmission), which the distribution utility can affect but not set. |

### Earlier model (Sections 1–12)

| Term | Plain meaning |
|---|---|
| **BASE, ACCELERATED, COMBINED, FRONTLOADED, FREEZE_PLUS** | Named scenarios: the reform; faster ramp-up; ramp-up plus wider eligibility; customers keep all savings in years 1–3; reform plus a rate freeze. |
| **NWS-eligible share / avoidance** (`NWS_AVOIDANCE_*`) | The share of capital spending non-wires solutions could replace, and how much they actually avoid as programs mature. |
| **NWS OPEX** | The running cost of the non-wires programs. |
| **Utilisation credit** (`FLEX_LOAD_UTILISATION_SHARE_SS`) | The earlier model's credit for using existing grid capacity better. The layered model replaced it. |
| **Deferral fraction** (`DEFERRAL_FRACTION`) | The share of avoided capital that is eventually built anyway. |
| **Savings pool basis** (`capex`, `revenue_requirement`) | Whether the pool is avoided capital spending in the year (earlier default) or the reduction in revenue requirement (CORRECTED). |
| **Capacity pass-through** | Capacity savings from a lower peak, passed to customers' supply charge. |
| **Crossover year** | The year utility earnings under shared savings fall below BAU. |
| **Break-even / minimum utility share** | The smallest utility share at which the utility is no worse off than BAU. Kept for the earlier model only. |
| **ROE sweep** | Results at allowed returns from the rate-case value down to 7%. |
| **$10/month threshold** | The point at which monthly savings become noticeable relief. |
