# Con Edison (CECONY): data notes

*Key `ConEd`; notebook `GridDividend_NewYork.ipynb`; data `utilities/ConEd.json`. As of 31 October 2026.*

Every input with its value, source and status is in [../ASSUMPTIONS.md](../ASSUMPTIONS.md); the method is in [../METHODOLOGY.md](../METHODOLOGY.md).

## Starting point

**Rate case.** NYPSC Case 25-E-0072 (approved January 2026).

**System figures** (earlier-model fields, also used by the layered model):

| Field | Value |
|---|---|
| Rate base | $32,935M |
| Annual capex | $4,579M |
| Total revenue | $8,400M |
| ROE | 9.4% |
| Equity ratio | 48% |
| Customers | 3.7 million |
| Peak | 11,822 MW |
| Energy | 63,000 GWh |

**Residential bill.** New York City, SC 1 Rate I (full service), at 600 kWh/month. The starting bill is $215.01/month:

| Category | $/month | Main lines |
|---|---:|---|
| Distribution base | 122.28 | Customer charge $21.00; energy delivery 16.88¢/kWh |
| Distribution riders | −1.46 | MAC, RDM credit, delivery revenue surcharge |
| Program surcharges | 11.97 | Core: VDER, company EE/BE, Dynamic Load Management, EV Make Ready. Not core: NYSERDA SBC, CES, AMP |
| Supply energy | 45.38 | MSC energy (residual), Merchant Function Charge |
| Capacity | 28.69 | MSC capacity (separate line, so no carve-out) |
| Transmission | 0.00 | Recovered in delivery rates (no separate line) |
| Taxes and fees | 8.16 | Gross receipts tax: 4.86% delivery, 2.41% commodity |

The published check is Con Edison's 2025 average 600 kWh NYC bill, $218.55/month.

## Key sources

- **Bill lines:** Con Edison PSC No. 10 tariff leaves and monthly statements (MAC, RDM, SBC, DLM, EV Make Ready, CES, MSC, MFC, GRT).
- **Capacity price:** NYISO NYC, $0.12M per MW-year (`shared/capacity_markets/NYISO.json`).
- **Demand response today:** 466.2 MW (DLM program report, Case 14-E-0423).
- **Flexible MW paths, Central:** Brattle, *New York's Grid Flexibility Potential* (January 2025, for NYSERDA and DPS).
- **Upgrade delays:** Con Edison E-Mobility Interconnection Guide (April 2026). Ordinary load 0.5 / 1.5 / 3 years; large loads 2 / 3 / 6 years.
- **Network cost and losses:** marginal transmission cost $40.67/kW-year and average losses 4.24%, both from the Con Edison BCA handbook.
- **Upgrade cost:** $3.0 / 4.0 / 7.1M per MW (notebook Section 1; Idlewild $7.1M/MW).

## Published-plan BAU

- **Distribution capex plan:** CECONY Electric $4,766M (2026), $4,852M, $5,019M, $6,228M, $6,293M (2030).
  - Source: Consolidated Edison 2025 Form 10-K, Capital Requirements estimate.
  - It includes transmission, which Con Edison recovers in delivery rates, and surcharge-recovered programs.
  - It excludes energy-efficiency regulatory-asset spend.
  - The plan's 2026–2030 CAGR is 7.2%.
- **Cross-check:** the Case 25-E-0072 electric average rate base is $32,935M / $35,149M / $39,174M (2026–2028).
- **Category split** (2026 targets, Q1 2026 capital expenditure report to the NYPSC):
  - growth 50.2% (New Business + System Expansion);
  - replacement 21.4% (Replacement + Equipment Purchases);
  - grid modernisation / resilience 23.5% (Risk Reduction + Storm Hardening + Customer Energy Solutions);
  - other 4.9% (Public Improvement, Environmental, Safety).

  The mapping to these four categories is the model's.
- **No separate transmission plan:** transmission has no bill line in New York.
- **Long-run capacity value** (sensitivity): $200/kW-year UCAP, the NYISO market monitor's levelized Net CONE for the 2-hour battery reference unit.

## Utility-specific vs borrowed

**Utility-specific:**
- the bill and tariff lines;
- rate-case system figures;
- capacity zone;
- demand response today;
- Central flexible MW paths (Brattle New York study);
- upgrade delays;
- transmission cost;
- loss rate;
- upgrade cost per MW.

**Borrowed (proxies):**
- **Network loading bands and constrained sub-band:** Dominion's grid utilization filing (PUR-2026-00164).
- **Wholesale on/off-peak spread:** PJM 2025 State of the Market.
- **Capacity derates:** PJM class ratings.
- **Demand response cost per kW-year:** Pepco Rider R-DLC and Brattle.
- **Efficiency peak ratio:** EmPOWER Maryland.
- **Ramp limits:** Pepco direct load control history.

## Main `_VERIFY` gaps to close

1. **Network loading.** Con Edison's own feeder or substation loading distribution would replace Dominion's bands. Its hosting-capacity and load-capacity maps are the starting point.
2. **Efficiency savings rate** (0.5% a year central): New York EE/BE first-year savings for 2024–25.
3. **Managed EV, storage and other DER enrolled today.** These are not found and are set to 0 MW.
4. **Costs and capitalised shares** for managed EV, storage and other DER.
5. **Locational match** (0.4): feeder-level constraint data from the DSIP.
6. **MSC energy line.** It is a residual from the 2025 average bill. **Program recovery ($M a year)** is not filled because the PSC document server refused connections.

## Notes

- The Merchant Function Charge averages February–October 2026; January 2026 is not parsed. The November 2026 link on coned.com serves an Orange & Rockland statement (rechecked 31 October 2026).
- `ConEd.json` has no `property_tax_rate`, so the notebook fallback of 1.6% applies. This is an open item; changing it would change results.
