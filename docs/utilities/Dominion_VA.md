# Dominion Energy Virginia: data notes

*Key `DomVA`; notebook `GridDividend_Virginia.ipynb`; data `utilities/Dominion_VA.json`. As of 31 October 2026.*

Every input with its value, source and status is in [../ASSUMPTIONS.md](../ASSUMPTIONS.md); the method is in [../METHODOLOGY.md](../METHODOLOGY.md).

## Starting point

**Rate case.** SCC Case PUR-2025-00058, the biennial review. The final order was issued in November 2025; rates take effect January 2026 and January 2027.

**System figures:**

| Field | Value | Status |
|---|---|---|
| Rate base | $13,800M | `_VERIFY` (investor materials) |
| Annual capex | $1,600M | `_VERIFY` |
| Total revenue | $9,000M | `_VERIFY` |
| ROE | 9.8% | Sourced |
| Equity ratio | 48% | Sourced |
| Customers | 2.8 million | |
| Peak | 20,000 MW | |
| Energy | 87,000 GWh | |
| Property tax | 1.7% | `_VERIFY` |

**Residential bill.** Schedule 1 residential at 1,000 kWh/month, bundled (vertically integrated) service, from the filed tariff. The starting bill is $182.80/month:

| Category | $/month | Main lines |
|---|---:|---|
| Distribution base | 40.85 | Basic customer charge $7.58; distribution 3.33¢/kWh |
| Distribution riders | 7.68 | Rider DIST |
| Program surcharges | 24.71 | Core: Riders C1A (peak shaving) and C4A (efficiency). Not core: CE, OSW, RPS, PIPP |
| Supply energy | 61.42 | Base generation and fuel net of the capacity carve-out; GEN, SNA, CERC, E, SMR, CCR, deferred fuel |
| Capacity | 23.21 | Carved out of base generation (91.5%) and fuel (8.5%) |
| Transmission | 22.43 | Transmission kWh charge, Rider T1 |
| Taxes and fees | 2.49 | Consumption tax, sales and use surcharge |

The local consumer utility tax varies by locality and is excluded. The published check is Dominion's typical 1,000 kWh bill of 1 July 2026, $180.79 excluding taxes; several riders changed on 1 September 2026.

## Key sources

- **Bill lines:** Dominion's filed tariff, Schedule 1 and the riders.
- **Network loading:** the Grid Utilization Metrics Proposal (SCC PUR-2026-00164, filed 15 October 2026). It is the source of:
  - the loading bands (mean planning utilisation 79.8%);
  - the planning limit factor (0.80, Metric iv);
  - the constrained sub-band (82 of about 1,900 feeders, 4.3%, above 100%);
  - distribution losses (3.9%, Metric iii).
- **Large-load upgrade delay:** 4 / 6 / 7 years, from the large-load queue application (SCC PUR-2026-00011). The same filing sets the low backlog clearance rate.
- **Capacity price:** PJM DOM 2026/27 BRA, $329.17/MW-day ($0.12M per MW-year).
- **Avoided transmission:** PJM network service rate, DOM zone, $85.19/kW-year (June 2026).
- **Efficiency:** SCC 2025 DSM report (VCEA savings targets).
- **Flexible MW paths:**
  - Demand response: Dominion 2025 IRP Update, DSM 341 MW in 2025 and 1,076 MW by 2030 (efficiency and demand response together), less the efficiency part (the IRP's DSM energy savings, 1,462 GWh and 3,011 GWh, x `ee_kw_per_mwh`): 181.2 MW today and 746.9 MW in 2030–2035.
  - Storage: VCEA (2,700 MW by 2035, of which at least 10% behind the meter = 270 MW).
  - Managed EV and other DER: DOE low end.
  - Ambitious: DOE's VPP Liftoff range.

## Published-plan BAU

- **Distribution capex plan:** Electric distribution plus grid transformation, $2.3B / $2.4B / $2.3B / $2.3B / $2.4B (2026–2030).
  - Source: Dominion Energy Q4 2025 earnings slides (23 Feb 2026), Dominion Energy Virginia 5-year capital summary.
  - DEV includes North Carolina, consistent with the modelled customer count.
- **Category split:**
  - grid modernisation 23.7% (grid transformation's share), sourced;
  - the rest split in Con Edison's proportions (`_VERIFY`; Dominion publishes no driver split).
- **Transmission:** the bill line follows the electric transmission rider rate base, $13.5B (2025), $15.4B, $17.3B, $19.4B, $21.6B, $23.7B (2030) (same slides), per MW of system peak. After 2030 its growth tapers to the transmission growth rate by 2035.
- **Capacity:** the PJM 2027/28 auction cleared at the $333.44/MW-day cap, applied from 2027.
- **Long-run capacity value** (sensitivity): Brattle's 2025 CONE study for PJM, $528/MW-day UCAP Net CONE (about $193/kW-year). PJM's 2027/28 Net CONE for DOM is $178/MW-day, below today's cap.
- **Gap to close:** Dominion's distribution capex by driver (growth, replacement), which would replace the proxy split.

## Utility-specific vs borrowed

Dominion has the most utility-specific network data of the four, and its filing is the proxy for the others.

**Utility-specific:**
- the bill;
- ROE and equity ratio;
- network bands, planning limit, sub-band and losses;
- large-load delay;
- capacity zone;
- transmission rate;
- efficiency savings rate;
- demand response and storage anchors.

**Borrowed (proxies):**
- **Ordinary-load upgrade delay:** Con Edison.
- **Wholesale mwh per MW:** NYISO event-hours.
- **Efficiency peak ratio and ramp limits:** EmPOWER / Pepco.
- **Demand response cost per kW-year:** Pepco and Brattle.

## Main `_VERIFY` gaps to close

1. **Rate base, capex and total revenue**, distribution-only, from PUR-2025-00058. The 2026 reconciliation implies other O&M at 55% of the delivery revenue requirement, which suggests the rate base is understated.
2. **Demand response today and its path.** The IRP does not split DSM MW between efficiency and demand response. The efficiency part is now removed using the EmPOWER kW per MWh ratio, a proxy. Dominion's own DR program MW (Smart Thermostat DR, Non-Residential Curtailment and Distributed Generation, Peak Time Rebate) would replace the derivation.
3. **Ordinary-load upgrade delay** in constrained areas. The grid utilization filing reports constrained feeders but no connection timeline.
4. **Upgrade cost per MW:** $1.0 / 1.8 / 3.5M (suburban and rural vs Northern Virginia).
5. **The shape of the loading distribution.** The filing gives the mean and the count above 100%; the band spread and the sub-band loading (112.5%) are assumed.
6. **Program recovery ($M a year) for C1A and C4A.** The SCC rider orders were not read.

## Notes

- **Earlier model:** the ACCELERATED and COMBINED scenarios use New York's absolute NWS shares (35% / 55%) rather than Dominion's 22% / 35%, and the EV territory share uses `customers / 8,000,000`. Both are open items.
