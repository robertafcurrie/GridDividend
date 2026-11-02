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
- **Network cost and losses:** average losses 4.24% (Con Edison BCA handbook). Avoided transmission (split formulation, the default; METHODOLOGY 3.8a): transmission upgrades deferred = the load-driven share (0.25 / 0.5 / 0.75, from the 2025 local transmission plan) of the transmission share of the capital plan (0.304, Form 1), realisation 0.5 / 0.8 / 1.0 (Con Edison plans its own local transmission); no zonal allocation effect in New York. The single formulation (option) uses the handbook's marginal transmission cost, $40.67/kW-year.
- **Upgrade cost:** $3.0 / 4.0 / 7.1M per MW (notebook Section 1; Idlewild $7.1M/MW).

## Data-centre growth (layered model)

The layered model's central data-centre growth is **0%** (low 0% / high 6%, the earlier assumption). It was 6% a year from 1,500 MW, unsourced.
- **Con Edison:** forecasts CECONY peak demand growth of about 0.7% a year (2026–2030, design conditions, 12,690 MW in 2026) and cites data centres only for O&R (2025 Form 10-K).
- **NYISO 2026 Gold Book update:** Zone J is essentially flat (10,847 MW vs 10,824 MW), with large-load growth upstate in Zone D.
- **Not changed:** the earlier model keeps its 6% (pins) and the 1,500 MW starting estimate, which the layered model also reads. With zero growth, that starting figure only splits today's energy between data-centre and other load.

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
- **Long-run capacity value** (sensitivity): $200/kW-year. Brattle for NY DPS and NYSERDA (Jan 2025, via Utility Dive): avoided generation capacity cost above $200/kW-year in 2040. The NYISO market monitor's 2-hour battery Net CONE is also $200/kW-year.
- **Load the plan assumes:** 0.7% a year of CECONY peak growth (10-K; the forecast Con Edison uses for capital planning). The model grows peak 1.26% a year (2026–2030), mainly through electrification, so the load link scales plan-year growth capex by 1.82.
- **Electrification pace:** under the central utility-forecast pace, electrification is scaled to 0.32 of the state-policy rate (0.31% a year) so that peak grows 0.7% a year to 2030; the scale factor is then 1.0. At state-policy pace, customer savings are $49.5B rather than $37.8B (Central).

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
