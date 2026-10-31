# Pepco Maryland: data notes

*Key `PepcoMD`; notebook `GridDividend_Maryland.ipynb`; data `utilities/Pepco_MD.json`. As of 31 October 2026.*

Every input with its value, source and status is in [../ASSUMPTIONS.md](../ASSUMPTIONS.md); the method is in [../METHODOLOGY.md](../METHODOLOGY.md).

## Starting point

**Rate case.** MD PSC Case No. 9820, Order No. 92607:
- final order 28 August 2026;
- historic test year ending 30 September 2025;
- authorised increase $50.9M of $119.9M requested;
- the White Flint substation ($164.9M) disallowed as imprudent.

**System figures:**

| Field | Value | Notes |
|---|---|---|
| Rate base | $2,995M | Sourced, Order No. 92607 |
| ROE | 9.4% | Sourced |
| Equity ratio | 50.5% | Sourced |
| Annual capex | $275M | `_VERIFY`; Maryland share of Pepco's plan |
| Total revenue | $2,480M | `_VERIFY` |
| Customers | 619,357 | MD PSC Ten-Year Plan |
| Peak | 3,644 MW | MD PSC Ten-Year Plan |
| Energy | 13,280 GWh | MD PSC Ten-Year Plan |
| Property tax | 1.97% | |

The 2026 reconciliation against the case record is in `utilities/calibration/Pepco_MD.csv`.

**Residential bill.** Montgomery County, Schedule R with Standard Offer Service, at 900 kWh/month (Maryland Office of People's Counsel benchmark). The starting bill is $231.63/month:

| Category | $/month | Main lines |
|---|---:|---|
| Distribution base | 67.95 | Customer charge $8.44; distribution 6.17¢/kWh; plus the Order No. 92607 adjustment (+$3.94) |
| Distribution riders | 0.00 | RDM and GRC at zero; BSA not posted |
| Program surcharges | 19.01 | Core: EmPOWER (2.06¢/kWh). Not core: Universal Service, Maryland Environmental Surcharge |
| Supply energy | 88.62 | SOS generation net of the capacity carve-out |
| Capacity | 25.41 | Carved out of SOS generation |
| Transmission | 18.91 | SOS transmission |
| Taxes and fees | 11.73 | Gross receipts tax 2.04%; Montgomery County energy tax |

The base rates in effect at the as-of date are pre-case, so the authorised residential increase is added as a starting adjustment. pepco.com/md-rates returned a bot challenge, so Riders BSA, DT, MCS, MES and AC are derived or left out.

## Key sources

- **Rate case and tariff:** Order No. 92607 and its appendices; the Pepco Maryland tariff (P.S.C. Md. No. 1, August 2026).
- **Load:** the MD PSC Ten-Year Plan (2025–2034). Pepco's own forecast is flat: net sales +0.04% a year, summer peak +0.33% a year to 2034.
- **Efficiency:** the 2026 EmPOWER Standard Report.
  - Pepco saved 252,130 MWh in 2025, which sets the savings rate.
  - The verified kW per MWh ratio is used for all four utilities.
- **Demand response today:** Energy Wise Rewards, 247 MW (EmPOWER report, Table 13).
- **Demand response path:** the DRIVE Act proposal (Case 9761, up to 185 MW of flexible load).
- **Ramp limits:** Energy Wise Rewards additions, 2009–2025. These are used for all four utilities.
- **Capacity price:** PJM PEPCO zone 2026/27 BRA, $329.17/MW-day ($0.12015M per MW-year), the same price as the capacity carve-out. The earlier model reads `PJM.json` (2027/28, $333.44/MW-day, growing at inflation).
- **Avoided transmission:** PJM network service rate, PEPCO zone, $60.49/kW-year.
- **Losses:** 4.92% (EIA-861).
- **Upgrade cost:** $1.74 / 2.2 / 3.08M per MW (White Flint, Order No. 92607).

## Utility-specific vs borrowed

**Utility-specific:**
- the rate case and bill;
- load forecast;
- efficiency savings rate and kW per MWh;
- demand response today and its path;
- storage path;
- capacity zone;
- transmission rate;
- losses;
- upgrade cost;
- ramp limits.

**Borrowed (proxies):**
- **Network bands and sub-band:** Dominion.
- **Upgrade delays:** Con Edison. No Pepco Maryland timeline was found.
- **Wholesale mwh per MW:** NYISO event-hours.
- **Other DER path:** DOE low end.

## Main `_VERIFY` gaps to close

1. **Annual capex and total revenue** for Maryland distribution. These are derived from Pepco DC+MD figures at 46.3%.
2. **Network loading and connection timelines.** The Maryland PSC Electric System Planning report (December 2025) describes PHI's 10-year feeder and substation plans; COMAR 20.50.15 plans would give constrained-area data.
3. **Unposted riders** (BSA, DT, MES) and the Prince George's County energy tax, as an alternative location.
4. **Managed EV and other DER enrolled today.** These are not found and are set to 0 MW.
5. **Capacity carve-out inputs.** The residential share of the obligation is assumed equal to its share of sales.

## Notes

- Section 12 of the Maryland notebook (earlier model) adds Maryland-specific checks: the reconciliation, break-even shares, the flat-load case, the White Flint worked example, and the data-centre and capacity-price sensitivities.
