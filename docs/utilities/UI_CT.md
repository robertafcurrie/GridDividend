# United Illuminating: data notes

*Key `UI_CT`; notebook `GridDividend_Connecticut.ipynb`; data `utilities/UI_CT.json` and `utilities/UI_CT_lookback.json`. As of 2 November 2026.*

Every input with its value, source and status is in [../ASSUMPTIONS.md](../ASSUMPTIONS.md); the method is in [../METHODOLOGY.md](../METHODOLOGY.md).

## Starting point

**About UI.** UI serves about 347,000 customers in 17 towns in southwestern Connecticut (New Haven, Bridgeport). It is an Avangrid subsidiary (Iberdrola) and a transmission owner as well as a distribution company.

**Rates in force: Docket 24-10-04.**
- **Final decision** (28 October 2025), for the rate year 1 November 2025 - 31 October 2026:
  - UI asked for $490.28M (+$105.42M, 27.4%) on the existing $384.865M, at a 10.5% ROE;
  - PURA approved $450.79M at an allowed 9.45%, cut by 20 bp to 9.25% for performance and management issues;
  - about +$9.99/month at 750 kWh.
- **Reconsideration** (3 March 2026): revenue requirement $452,845,438 (+$67,980,438). It removed two ROE reductions, 10 bp (Inglis / English Station remediation) and 5 bp (DER platform / water-heater rental directives).
- Derived ROE 9.40% (`_VERIFY` against the decision text). Some penalties remain in litigation.

**Previous case: Docket 22-08-08** (25 August 2023):
- asked $91.055M / $20.120M / $19.466M at a 10.20% ROE;
- granted one year, +$22.957M (revenue requirement $384.865M), at 9.10% less 47 bp;
- about $222.4M of capital additions not allowed to earn a return.

UI's appeal failed (March 2025). UI then cut $70M of capital and roughly halved its capital budget.

UI has **no ESI tracker and no CTA rate**.

**System figures:**

| Field | Value | Status / notes |
|---|---|---|
| Rate base | $1,430M | Derived: FERC Form 1 2025 distribution functional rate base |
| ROE / equity | 9.40% / 50% | Derived / `_VERIFY` |
| Annual capex | $69.6M | Derived: Form 1 2025 distribution additions proxy (2022-2025: $155M, $127M, $86M, $70M) |
| Total revenue | $1,105.4M | Derived: EIA-861 2025 retail revenue |
| Delivery share | 0.4097 | Derived: $452.8M / $1,105.4M |
| Customers | 348,263 | EIA-861 2025 (314,909 residential) |
| Peak | 1,272 MW | Derived: UI 2025 Loads and Resources, 1,257 MW (2025) × 1.0117 |
| Energy | 4,875 GWh | EIA-861 2025 retail sales |
| Property tax | 2.05% | Derived: Form 1 2025 |

**Reconciliation flag.** The 2026 reconciliation gives recalibrated other O&M of 59% of the delivery revenue requirement, above the 50% plausibility bound. RG&E and Dominion carry the same flag. The Form 1 rate base is likely understated relative to the rate-case revenue. The decision's rate base would settle it.

**Residential bill.** Rate R with Standard Service at 700 kWh/month. PURA's UI decision quotes 750 kWh; 700 kWh keeps the Connecticut pair comparable. Total $183.88/month (nominal):

| Category | $/month | Main lines |
|---|---:|---|
| Distribution base | 92.45 | Customer charge $13.02; distribution 11.3469¢/kWh |
| Distribution riders | −2.22 | RDM −0.3178¢ |
| Program surcharges | −24.10 | NBFMCC −2.8278¢ and SBC −1.3147¢ (credits); RE investment 0.1¢; **core:** C&LM + CAM 0.6¢ (`_VERIFY`) |
| Supply energy | 78.36 | Generation Service Charge 11.95¢ net of the capacity carve-out |
| Capacity | 5.29 | Carved out: FCA 17 |
| Transmission | 34.11 | TAC 4.8722¢/kWh |
| Taxes and fees | 0.00 | |

**Published check.** OCC (1 May 2026) puts the May 2026 RAM at about −$34.15/month at 700 kWh (−13.8%), and May plus July together at about −$50 (−18%). The OCC's statement that UI's public benefits fall to "about 1.3 cent" a credit does not reconcile with the listed UI lines (−4.04¢ before C&LM), so it is not used as a check. The public-benefits credit returns to 3.3¢ from May 2027, as for CL&P.

## Key sources

- **Bill:** OCC bill page, OCC RAM FAQ and the OCC Standard Service advisory (22 May 2026). uinet.com, which hosts the Rate R tariff, did not respond in this build.
- **Rate cases:** PURA 24-10-04 release (28 October 2025); OCC statement on the reconsideration (3 March 2026); Docket 22-08-08 summary.
- **Finances:** FERC Form 1 2021 and 2025 via PUDL (respondent 299). UI's Q1 2026 unaudited statements: capex $59.8M (Q1 2025 $84.1M).
- **Load:** UI *2025 Report on Loads and Resources* (28 February 2025):
  - normal-weather summer peak 1,257 MW (2025) to 1,395 MW (2034), 1.17% a year (UI states 1.23%);
  - sales 4,923 to 5,873 GWh.

  The growth is from EVs and heat pumps. Peak fell 7.7% over 2015-2024. Large loads are included but not quantified.
- **Efficiency:** EIA-861 2025, 33,200 MWh first-year savings (0.68% of sales), at $0.128 per lifetime kWh (the Cautious level).
- **Demand response today:** 10.1 MW (EIA-861 2025).
- **Programs, Central:**
  - demand response: the C&LM Plan statewide target × 0.21 = 49.4 MW;
  - storage: Energy Storage Solutions × 0.21 = 121.8 MW.
- **Transmission:**
  - UI customers pay the pooled RNS rate, so the transmission path is scaled to the 2026 RNS forecast. UI's own additions ($212M, $164M on a $1.1B base) would grow the line about 13% a year.
  - (a) share 0.050, reported separately.
- **Losses:** 2.86% (requirements 5,068 GWh vs sales 4,923 GWh, 2025).

## Published-plan BAU

- **Distribution capex:** no UI plan was located. The 2025 Form 1 additions proxy ($69.6M), grown at inflation: $71.3M to $78.7M over 2026-2030 (`_VERIFY`). This is a low path, after the capital cut.
- **Category split:** RG&E proxy (also an Avangrid company; `_VERIFY`).
- **Load the plan assumes:** 1.17% a year of peak growth.

## The earnings opportunity at UI

UI's pool is **negative in every year at Central**, so UI earns no shared savings earnings in Cautious or Central. Ambitious gives $0.19B undiscounted ($0.11B NPV 3%). Customers still save at Central: $0.60B undiscounted, $10.46/month in 2050. Most of that saving is efficiency energy and capacity, which sit outside the pool.

Three conditions limit the pool:
- **Little capex to defer.** The plan path is about $70-80M a year, so deferral is worth $0.40B in total.
- **Cheap capacity.** ISO-NE's 2026/27 price ($31,080/MW-yr) is about a quarter of PJM's.
- **Storage costs.** The Central storage path (the ESS share, 122 MW) is costed at the Pepco proxy of $150/kW-yr.

The conditions that would unlock it:
- a lower cost per kW-year for storage (tornado swing $4.27/month);
- a capital plan with more growth-driven work (the 1.17% a year peak growth would need it);
- efficiency delivered at the LBNL cost.

## Utility-specific vs borrowed

As for CL&P (see [Eversource_CT.md](Eversource_CT.md)). UI-specific:
- the bill and rate cases;
- Form 1;
- load;
- efficiency;
- demand response today;
- losses.

UI borrows the Pepco upgrade-cost range and has no large-load segment.

## Main `_VERIFY` gaps to close

The tornado ranks these by how much they move the 2050 saving:
1. **Efficiency savings above BAU** ($11.09/month swing).
2. **Storage cost per kW-year** ($4.27).
3. **Supply, transmission and program-surcharge growth** ($3.81, $1.90, $2.03).
4. **The Docket 24-10-04 rate base and capital structure**, and a UI distribution capital plan.
5. **Network loading and connection timelines:** the UI hosting-capacity map; UI's flexible-interconnection proposal.

## Notes

- **Winter peaking, the temporary public-benefits credit and the PBR framework** apply as for CL&P.
- **Look-back:** the $222.4M of capital excluded from return in 2023 (largely allowed in 2025) sits inside the Form 1 capital-driven bridge. The bridge cannot separate it.
