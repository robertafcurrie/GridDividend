# GridDividend

**An open-source policy simulation framework for electric utility shared savings.**

*Dr Robert A. F. Currie, May 2026*

AI has been used extensively in the creation of this tool.

---

## What it does

GridDividend models what happens to customer electricity bills and utility finances when a regulatory framework replaces traditional infrastructure build-out with a **shared savings mechanism**: Non-Wires Solutions (NWS) — batteries, demand response, managed EV charging — defer capital investment, and the resulting savings are split between the utility (as an earnings incentive) and customers (as bill reductions).

Generated per-utility reports call this the **EASE Case** — shorthand for what bills and utility finances would look like if a jurisdiction enacted **The Electricity Affordability, Savings, and Efficiency Act (the "EASE Act")**, the model's working name for legislation enabling this shared-savings mechanism — contrasted against **BAU** (business as usual, no such reform). The EASE Case is a **directional illustration of order of magnitude, not a guarantee of results**: it identifies a direction of travel for the policy, not a prediction, and it does not replace the detailed, state-by-state modelling and legislative design work that actual reform would require.

The model runs **2026–2050** projections across five scenarios per utility, plus a BAU baseline:

| Scenario | Description |
|----------|-------------|
| BAU | Business As Usual — traditional CAPEX build-out, no reform |
| BASE | Standard shared savings programme — NWS avoidance + 30/70 savings split. Reported as the **EASE Case** |
| ACCELERATED | Faster NWS ramp, 2× standard pace — tests aggressive programme delivery |
| FREEZE_PLUS | BASE programme with a 4-year rate freeze — lower early bills, gradual catch-up |
| COMBINED | ACCELERATED programme with a 3-year freeze — maximum near-term customer benefit |
| FRONTLOADED | BASE programme with 3-year full customer passthrough — utility earns 0% in years 1–3 |

`BASE` is the scenario used in generated summary reports; it's what "EASE Case" refers to there. The other named scenarios explore near-term/long-term trade-offs and aren't (yet) surfaced in the per-utility HTML reports.

Currently models three utilities across two states — New York (Con Edison and RG&E) and Virginia (Dominion Energy Virginia): **Con Edison** (Case 25-E-0072, approved Jan 2026), **RG&E** (Case 25-E-0379, temporary rates Jun 2026), and **Dominion Energy Virginia** (SCC Case PUR-2025-00058, rates effective Jan 2026).

---

## Key result

Under shared savings, a typical Con Edison residential customer (600 kWh/month) avoids hundreds of dollars per year in bill increases that BAU regulation would otherwise impose. Cumulative savings reach **$12,907 per customer** by 2050 ($52B aggregate across Con Edison's 3.7M customers).

The rate freeze (FREEZE_PLUS) reshapes the timing of savings — bills are lower in years 1–4, then gradually recover — but converges with BASE by 2034. The 25-year cumulative saving is identical. Structural reform delivers a permanently lower trajectory; a rate freeze is a timing mechanism, not a cost reduction.

**Dominion Energy Virginia** (SCC Case PUR-2025-00058, rates effective January 2026)
- Starting bill: $155/month (1,000 kWh/month Virginia SCC benchmark)
- BAU 2050: $350/month
- Shared savings 2050: $232/month
- Annual saving 2050: $1,410/year
- ⚠️ Five parameters require verification from SCC filing before results should be cited — see `utilities/Dominion_VA.json`

---

## Three mechanisms

Every EASE Case scenario draws savings from three distinct mechanisms. Each mechanism's savings are split the same way — utility retains 30% as an incentive (consistent with NY PSC NWS incentive precedent), 70% passes through to customer bills — via `UTILITY_SAVINGS_SHARE`, not a fourth mechanism of its own.

1. **NWS avoidance** — Flexible DER defers growth-driven infrastructure spending, shrinking the rate base and the return earned on it. Avoidance ramps from ~20% of eligible CAPEX in 2026 to ~80% at programme maturity, consistent with GB flexibility market outcomes (UKPN DSO, 2024/25) and the Brattle Ontario NWS study (2026).

2. **Pass-through savings** — Flexible demand also shaves system-wide peak demand, so the utility buys less capacity in the wholesale capacity market. That saving flows through on the supply portion of the bill.

3. **Utilisation credit** — Managed flexible load uses existing system headroom without triggering proportional new build, spreading fixed costs over more kWh. Source: Brattle/Utilize Coalition, *The Untapped Grid* (2026).

---

## How to use

**Option A — Conda (recommended if you have Anaconda/Miniconda):**
```bash
git clone https://github.com/robertafcurrie/GridDividend.git
cd GridDividend
conda activate base          # or any environment with the packages below
jupyter notebook GridDividend_v1.0.ipynb
```

**Option B — pip:**
```bash
git clone https://github.com/robertafcurrie/GridDividend.git
cd GridDividend
pip install -r requirements.txt
jupyter notebook GridDividend_v1.0.ipynb
```

Then edit any parameter in **Section 1** and choose **Kernel → Restart & Run All**.

The notebook is entirely self-contained — no external data files are required.

Each run also writes a self-contained HTML summary report per utility — `reports/{Utility}_BASE_{years}.html` — an EASE Case vs. BAU one-pager with the bill chart, key tables, and modelling assumptions. Toggle via `GENERATE_SUMMARY_REPORT` / `REPORT_SCENARIOS` in Section 1; see `engine/report.py`.

---

## Model caveats

This is a **strategic policy simulation**, not a utility planning model or rate-case replica. Key limitations:

- **Spatially aggregate.** NWS is modelled as a system-wide percentage of eligible CAPEX. Real outcomes depend on feeder-level constraint types and DER siting. Individual feeders will range from zero NWS benefit (fault-current or asset-condition driven) to near-complete deferral (growth-driven, thermally constrained, demand-coincident).
- **No real grid-utilization data.** NWS-eligible CAPEX share and avoidance rates are estimates from rate-case filings and industry benchmarks, not measured from actual utility hosting-capacity, feeder-loading, or grid-utilization data, for any of the three utilities modelled. Where a utility publishes real grid-utilization data, we'd want to use it in place of these assumptions — see `_grid_utilization_VERIFY` in `utilities/Dominion_VA.json` for where this is flagged most explicitly.
- **Not a forecast.** Results show direction and order of magnitude. Key sensitivities are the NWS avoidance rate at maturity and the electrification ramp — see Section 8 (Sensitivity Analysis).
- **RG&E data is provisional.** The PSC set temporary rates in June 2026; the final order on Case 25-E-0379 is still pending. Parameters should be updated when the order issues.
- **Dominion Energy Virginia** parameters include five values flagged for verification from the SCC rate case filing (total revenue, property tax rate, NWS eligible CAPEX share, grid-utilization data, and distribution upgrade cost per MW). Results for Dominion VA should be treated as illustrative until those parameters are confirmed.

Full caveats are in **Section 10** of the notebook (14 items, including discussion of permanent avoidance vs temporary deferral and the legislative design implications for clawback provisions).

---

## Citation

If you use this work in research or publications, please cite:

> Currie, R. (2026). *GridDividend: Open Source Utility Shared Savings Framework*. GitHub Repository.

---

## License

MIT
