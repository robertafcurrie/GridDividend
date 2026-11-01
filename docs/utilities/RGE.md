# Rochester Gas and Electric (RG&E): data notes

*Key `RGE`; notebook `GridDividend_NewYork.ipynb`; data `utilities/RGE.json`. As of 31 October 2026.*

Every input with its value, source and status is in [../ASSUMPTIONS.md](../ASSUMPTIONS.md); the method is in [../METHODOLOGY.md](../METHODOLOGY.md).

## Starting point

**Rate case.** NYPSC Case 25-E-0379. Temporary rates took effect June 2026 (+4.0% electric revenue); the final order is pending. RG&E data is provisional until it issues.

**System figures:**

| Field | Value |
|---|---|
| Rate base | $1,600M |
| Annual capex | $235M |
| Total revenue | $1,096M |
| ROE | 10.0% |
| Equity ratio | 48% |
| Customers | 383,000 |
| Peak | 1,050 MW |
| Energy | 5,500 GWh |

**Residential bill.** SC 1 residential at 600 kWh/month, from RG&E's own bill explainer flyer (sample bill, March–April 2025) and its April 2025 rate case insert. rge.com timed out, so current statements could not be read, and the June 2026 temporary rates are not reflected. The starting bill is $159.45/month:

| Category | $/month | Main lines |
|---|---:|---|
| Distribution base | 74.22 | Customer charge $23.00; delivery 8.54¢/kWh |
| Distribution riders | 10.53 | Transition charge, RDM, recovery charge |
| Program surcharges | 3.56 | SBC (not core: NYSERDA-run) |
| Supply energy | 60.27 | Supply charge net of the capacity carve-out; Merchant Function Charge |
| Capacity | 7.46 | Carved out of the supply charge |
| Transmission | 0.00 | Recovered in delivery rates |
| Taxes and fees | 3.42 | 3.09% on delivery, 1.01% on supply |

RG&E does not show DLM, EV Make Ready or CES as separate lines. Over half of the transition charge funds state programs, and CES sits in supply. So no RG&E line is marked core business, and today's core program spend is zero.

## Key sources

- **Bill lines:** RG&E bill explainer flyer (June 2025).
- **Demand response today:** 7.4 MW (NYSEG/RG&E 2025 DR annual report, Case 14-E-0423).
- **Flexible MW paths, Central:** Brattle New York flexibility potential study (scaled to RG&E).
- **Capacity price:** NYISO Rest of State, $0.07244M per MW-year (2026 monthly spot prices; `_VERIFY`). The layered model uses this zone; the earlier model uses G-H-I.
- **Network cost and losses:** marginal transmission cost $3.25/kW-year and average losses 6.93%, both from the RG&E BCA handbook.
- **Upgrade cost:** $0.8 / 1.5 / 3.0M per MW (notebook Section 1 notes).

## Published-plan BAU

- **Distribution capex plan:** $385.2M in 2026.
  - Source: the RG&E Five-Year Plan figure of $402.9M with common costs (NYSEG/RG&E Q1 2026 capital variance report), less the hydro generation share.
  - Only 2026 is published: RG&E's parent is privately held and files no 10-K. From 2027 the beyond-plan path applies, using Con Edison's 7.2% CAGR as a proxy (`_VERIFY`).
- **Category split** (2026 plan by category):
  - growth 25.8% (Customer Focus);
  - replacement 53.0% (Asset Condition + Reliability);
  - grid modernisation / resilience 8.3% (Modernization, Resiliency, Innovation, AMI);
  - other 12.8% (Compliance).
- **Gaps to close:** RG&E's multi-year capital forecast (the Case 25-E-0379 filing or joint proposal), which would replace the proxy growth rate; and a Rest of State long-run capacity value (the NYISO monitor's $200/kW-year is used as a proxy).

## Utility-specific vs borrowed

**Utility-specific:**
- the bill;
- rate-case figures (provisional);
- demand response today;
- transmission cost;
- loss rate;
- upgrade cost per MW;
- Central MW paths (scaled from the New York study).

**Borrowed (proxies):**
- **Network bands and sub-band:** Dominion.
- **Upgrade delays:** Con Edison. RG&E publishes no connection timeline for constrained areas.
- **Wholesale spread:** PJM.
- **Derates:** PJM.
- **Efficiency peak ratio and ramp limits:** Pepco / EmPOWER.
- **Efficiency savings rate:** New York assumption.

## Main `_VERIFY` gaps to close

RG&E has the highest `_VERIFY` share of the four (53%).

1. **Final order in Case 25-E-0379:** rate base, revenue, ROE and the delivery rates.
2. **Current tariff statements:** delivery, transition, SBC and supply rates, and the taxes. Six of the twelve bill lines are `_VERIFY`.
3. **Network loading and upgrade delays.** RG&E reports that 45% of substation transformers are heavily loaded (NYSAC presentation, July 2025). A loading distribution and connection timelines would replace the proxies.
4. **Capacity price for Load Zone B.**
5. **Efficiency savings rate and today's flexible enrolments** beyond demand response.

## Notes

- `RGE.json` has no `property_tax_rate`, so the notebook fallback of 1.8% applies. This is an open item.
