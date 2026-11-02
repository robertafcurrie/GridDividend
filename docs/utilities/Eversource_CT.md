# Eversource Connecticut (CL&P): data notes

*Key `EversourceCT`; notebook `GridDividend_Connecticut.ipynb`; data `utilities/Eversource_CT.json` and `utilities/Eversource_CT_lookback.json`. As of 2 November 2026.*

Every input with its value, source and status is in [../ASSUMPTIONS.md](../ASSUMPTIONS.md); the method is in [../METHODOLOGY.md](../METHODOLOGY.md).

## Starting point

**Rates in force.** Base distribution rates come from the 2018 settlement (PURA Docket 17-10-46):
- filed 22 November 2017 and approved 18 April 2018;
- three-year request $255.8M / $44.7M / $36.4M ($336.9M), settled at about $154.5M (OCC);
- ROE 9.25% and 53% equity (Eversource 2018 10-K);
- the 2021 settlement froze base rates to at least 1 January 2024 and left the ROE unchanged.

**Pending rate case: Docket 26-05-10** (filed 14 July 2026), the first general rate case since 2017. Figures from the brief, `_VERIFY` against the filing:
- deficiency $451M base, $727M with storm costs (the May 2026 notice of intent said about $503M);
- ROE 10.25%, equity about 54%;
- a four-year **Performance-Based Multi-Year Rate Plan (PBMRP)** with annual formula adjustments;
- AMI (about $1B capital and $300M O&M);
- a ~$4/month, 20-year securitisation charge;
- decision expected mid-2027.

It is not added to the starting bill.

**System figures:**

| Field | Value | Status / notes |
|---|---|---|
| Rate base | $6,174M | Derived: FERC Form 1 2025 distribution functional rate base (net plant + allocated general plant, working capital and ADIT). Not from a rate order |
| ROE / equity | 9.25% / 53% | Sourced (Docket 17-10-46) |
| Annual capex | $549.1M | `_VERIFY`: 2025 distribution capex as reported (Form 1 additions proxy $621M) |
| Total revenue | $4,155.4M | Sourced: 2025 retail revenue (supply $1,050.0M, local delivery $1,425.1M, public benefits $959.3M, transmission $721.0M) |
| Delivery share | 0.343 | Derived: local delivery / retail revenue |
| Customers | 1,309,946 | EIA-861 2025 (1,193,581 residential) |
| Peak | 4,619 MW | Eversource 2025 FLR, 2026 forecast (50/50) |
| Energy | 20,351 GWh | EIA-861 2025 retail sales |
| Property tax | 1.80% | Derived: Form 1 2025 property tax / net plant |

The 2026 reconciliation (`delivery_rr_reconciliation`) gives recalibrated other O&M of 44% of the delivery revenue requirement, inside the plausible range.

**Residential bill.** Rate 1 with Standard Service at 700 kWh/month (OCC and PURA benchmark), rates of 1 May 2026 (RAM) and 1 July 2026 (supply). Total $174.44/month (nominal):

| Category | $/month | Main lines |
|---|---:|---|
| Distribution base | 50.53 | Customer charge $9.62; distribution 5.844¢/kWh |
| Distribution riders | 17.77 | ESI 2.031¢; CTA 0.496¢ (includes a one-time $100M storm-fund contribution, ~$3.50/month); RDM 0.011¢ (`_VERIFY` unit) |
| Program surcharges | −10.25 | NBFMCC −2.061¢ and SBC −0.103¢ (credits); RE investment 0.1¢; **core:** C&LM + CAM 0.6¢ (`_VERIFY`) |
| Supply energy | 75.29 | Generation Service Charge 11.577¢ net of the capacity carve-out |
| Capacity | 5.75 | Carved out of the GSC: FCA 17 $2.59/kW-month |
| Transmission | 35.35 | TAC 5.050¢/kWh |
| Taxes and fees | 0.00 | No sales tax on residential electricity; gross earnings tax embedded |

**Published check.** No published total typical bill was located. OCC (1 May 2026) puts the May 2026 RAM at about −$31/month at 700 kWh (about −15%), and May plus July together at about −$38 (−18%).

**Public benefits are a temporary credit.** The credit comes from PA 25-173 bonding ($145M for 2026-27) and the Millstone / Seabrook contracts turning into a net benefit. Before May 2026, public benefits were about 4¢/kWh combined. The projection returns NBFMCC + SBC to 3.3¢/kWh (4¢ less C&LM and RE investment) from May 2027 (`revert`, METHODOLOGY 3.1). Effect: the 2035 BAU average bill is $286.76 with the revert and $238.99 without, and the 2035 Central saving is $7.96 and $6.08 respectively. The split between NBFMCC and SBC before May 2026 was not located; the whole 3.3¢ sits on the NBFMCC line.

## Key sources

- **Bill:** OCC, *Understand your electric bill*; OCC FAQ on the 2026 RAM decision (1 May 2026); OCC consumer advisory on Standard Service (22 May 2026). The Eversource Rate 1 tariff sheets were not re-read (`_VERIFY`).
- **Finances:** Eversource 2025 Annual Report (CL&P); FERC Form 1 2021 and 2025 via PUDL (respondent 243).
- **Load:** Eversource *2025 Forecast of Loads and Resources* (CT Siting Council, 26 February 2025):
  - summer peak 4,563 MW (2025) to 4,856 MW (2034), 0.69% a year (`plan_load_growth`);
  - energy +0.59% a year, of which EVs and heat pumps add about 1.5% a year of 2025 energy;
  - large customer additions 58 MW rising to 103 MW from 2027 (`dc_growth`; not data centres).

  The 2026 FLR was not located.
- **Efficiency:** EIA-861 2025, 125,243 MWh first-year savings (0.62% of sales), at $0.109 per lifetime kWh (the Cautious cost level).
- **Demand response today:** 118.3 MW (EIA-861 2025, potential peak savings; ConnectedSolutions).
- **Demand response path:** 2025-2027 C&LM Plan statewide active DR target, 235.4 MW, × the 0.79 customer share = 186.0 MW (Central 2035). The FLR plans 192 MW in Eversource's territory 2025-27, which is a consistent check.
- **Storage:** Energy Storage Solutions target of 580 MW × 0.79 = 458 MW (Central 2035). Today 15 MW (statewide installed ESS + ConnectedSolutions batteries × 0.79).
- **Capacity** (`shared/capacity_markets/ISONE.json`, zone CT):
  - prices: FCA 17 $2.59/kW-month (2026/27); FCA 18 $3.58 (2027/28);
  - long-run price: FCA 18 Net CONE, $9.078/kW-month;
  - obligation factor: ICR / reference peak = 1.151;
  - auction lag 3 / 1 / 0 (forward auctions, then the prompt auction from 2028/29).
- **Transmission** (split formulation):
  - (b) transmission upgrades deferred:
    - load-driven share 0 / 0.05 / 0.20 (2026 regional PTF additions: $56M RSP reliability of $1,096M);
    - realisation 0 / 0.5 / 1.0;
    - CL&P's transmission rate base, ~$4.6B at YE 2025, rolled forward at $398.6M a year of capex.
  - (a) lower share of regional transmission costs:
    - New England is the zone (RNS 12CP pooling);
    - CL&P's share is 0.183, its peak / ISO-NE peak, a proxy for its 12CP share;
    - reported separately (Central $2.42B undiscounted). It is overstated, because it is measured on the annual peak against the 12CP average.
  - Cross-check: the derived path grows the TAC line about 4.6% a year to 2030, in line with the 2026 RNS forecast ($184 / $186 / $197 / $210 / $220 per kW-year).
- **Losses:** 2.86%, UI's figure as a proxy (`_VERIFY`). EIA-861's CL&P losses exclude wheeled load.

## Published-plan BAU

- **Distribution capex:** linear from the 2025 actual ($549.1M) to $800M in 2029, then flat in 2030:
  - $611.9M / $674.6M / $737.3M / $800.0M / $800.0M (`_VERIFY`);
  - Eversource says annual Connecticut electric investment will exceed $800M by 2029; the scope may include transmission;
  - the Docket 26-05-10 capital budget by year and driver would replace this.
- **Investment context:**
  - more than $3.3B invested since 2018;
  - a $500M five-year cut announced in 2024;
  - the CEO's "shut the faucet off" remark (late September 2026).

  Recent capex may understate the forward run-rate. None of this is built into BAU beyond the plan.
- **ESI ends at the next rate case.** By statute the tracker ends after Docket 26-05-10. The BAU path assumes the same capital is recovered in base rates.
- **Category split:** RG&E proxy (`_VERIFY`). AMI (if approved) and storm resilience would move spending into grid modernisation, which is not addressable.

## Utility-specific vs borrowed

**Utility-specific:**
- the bill;
- finances (Form 1);
- load forecast and large customer additions;
- efficiency savings and cost;
- demand response today and its path;
- storage path;
- capacity zone and prices;
- RNS rate;
- transmission rate base.

**Borrowed (proxies):**
- network bands and sub-band: Dominion;
- upgrade delays: Con Edison;
- ramp limits and cost per kW-year: Pepco;
- accreditation: PJM ELCC (ISO-NE MRI values not located);
- `system_coincidence`: Pepco;
- wholesale spread: PJM;
- losses: UI;
- upgrade cost: placeholder $2.0M/MW;
- `ee_kw_per_mwh`: EmPOWER.

## Main `_VERIFY` gaps to close

The tornado ranks these by how much they move the 2050 saving:
1. **Efficiency savings above BAU** (`ee_incremental_savings_pct`, swing $15.77/month). Connecticut has no statutory percentage-of-sales target.
2. **Supply, program-surcharge and transmission growth** (projection; $4.41, $2.57, $2.34).
3. **Storage cost per kW-year** ($3.18; Pepco proxy).
4. **Locational match** ($2.01) and **reinforcement lead time** ($1.96). Hosting-capacity data and the IDSP filings (Docket 21-05-15RE03) would inform both.
5. **The Docket 26-05-10 schedules:** rate base, capital budget by driver, class allocation.

## Notes

- **The PBMRP is the natural vehicle** for a shared-savings mechanism. PURA's PBR framework (Docket 21-05-15) has Phase 2 reopeners RE01-RE03 (revenue adjustment, performance mechanisms, integrated distribution system planning). Draft decisions were issued in summer 2025; no final decision was located.
- **Winter peaking.** CL&P peaks in July today; the FLR's heat pumps add no summer peak. ISO-NE's 2026 CELT has the winter 90/10 peak passing the summer 50/50 peak by 2034. Which resources defer which capex will shift. The model is summer-peak based; this is listed as a candidate.
- **Non-wires.** PURA completed the first non-wires solutions cycle (Docket 25-08-08). The Eversource CT NWS Program Manual (with a BCA reference manual) is in force, and no open solicitations are listed. Context only.
- **Storm costs** (Docket 25-12-13, 29 July 2026): $974.2M requested, $869.4M found prudent, $667.9M to be securitised. Kept outside the distribution rate base.
- **Partial direct wholesale procurement** (~20% of Standard Service load) was approved in October 2026, with effects from mid-2027 or 2028. Not modelled.
- **Double-count guard on capacity:** see METHODOLOGY 3.6a. The C&LM budget's FCM revenue is in BAU in both cases.
