# GridDividend

**An open-source policy simulation of shared savings for electric distribution utilities.**

*Dr Robert A. F. Currie, October 2026*

AI has been used extensively in the creation of this tool.

---

## What it does

GridDividend shows the **potential of shared savings** and the **conditions that unlock it**. Under shared savings, flexibility and efficiency become core utility business. Demand response, managed EV charging, distributed storage, other DER and energy efficiency then defer network investment, lower capacity and energy costs, and connect new customers sooner. The utility earns a share of the savings it creates (its **shared savings earnings**); customers keep the rest.

Each utility starts from today's residential bill, line by line. The model then projects it 2026–2050 under business as usual (BAU) and under shared savings, one layer at a time. Results are **ranges** across three scenarios, not forecasts:

- **Cautious:** today's programs, grown modestly.
- **Central:** flexibility anchored to state targets and studies.
- **Ambitious:** what supportive policy could unlock (DOE's national range, lower costs, more flexible connections).

Four utilities are modelled: **Con Edison** and **RG&E** (New York), **Dominion Energy Virginia**, and **Pepco** (Maryland).

## Documentation

- [**Methodology**](docs/METHODOLOGY.md): how the model works, layer by layer, for policy readers (technical detail in marked subsections), with outputs, dollar bases, validation, limitations and a glossary.
- [**Assumptions register**](docs/ASSUMPTIONS.md): every input for every utility, with value or low / central / high, units, status, source and as-of date (also as [CSV](docs/assumptions_register.csv)). It is generated from the utility JSON by `scripts/build_assumptions_register.py`, and a test keeps it in sync.
- **Utility data notes:** [Con Edison](docs/utilities/ConEd.md), [RG&E](docs/utilities/RGE.md), [Dominion Energy Virginia](docs/utilities/Dominion_VA.md), [Pepco Maryland](docs/utilities/Pepco_MD.md). Each covers the starting point, key sources, proxies and the main gaps to close.
- [**Changelog**](CHANGELOG.md): what changed in each commit, and its effect on results.

---

## The layers

Each layer has its own switch and low / central / high inputs, each with a source, an as-of date and a status.

1. **System needs:** load growth (baseline, electrification, data centres), peak, and growth vs asset-condition capex. Applies to both cases.
2. **Programs as core business:** program surcharges leave the bill; flexible MW by type and energy efficiency are paid for in rates.
3. **Deferral:** flexible headroom counted by the network planner, so reinforcement is ordered later.
4. **Load enabled:** headroom lets load waiting for the network connect sooner (residential bill effect only).
5. **Capacity:** firm MW avoided at the zonal capacity price.
6. **Wholesale energy:** flexible load shifted from on-peak to off-peak hours.
7. **Avoided transmission:** transmission cost avoided by peak reduction.
8. **Avoided distribution losses:** marginal losses avoided by efficiency and peak reduction.
9. **Shared savings mechanism:** the utility's share of the savings pool.
10. **ROE lever:** the allowed return in shared savings relative to BAU, a separate lever outside the pool.

**The network.** The distribution network has explicit capacity in loading bands, including a constrained sub-band of load above the planning limit (from Dominion's grid-utilization filing).

**Upgrade Delay for Interconnection.** This is the time a new customer in a constrained area waits for the grid upgrade before connecting, measured in BAU and in shared savings.

**Access benefits.** These go to the customers being connected and are reported separately from the bill:
- MW connected sooner.
- MW-years of Upgrade Delay avoided.
- Connection cost avoided.
- Electrification brought forward.

---

## The opportunity

Figures are Central, with the Cautious–Ambitious range in brackets, on **published-plan BAU** (each utility's published capital plan, with its growth-driven part scaled to the model's load growth, then capex growth tapering to load growth by 2035). All $ are nominal. Dominion's and Pepco's capex category splits are New York proxies (see Caveats).

| | Con Edison | Dominion VA | Pepco MD | RG&E |
|---|---|---|---|---|
| **Customer savings 2026–2050, $B undiscounted** | **49.5** (14.3–86.1) | **16.4** (5.1–42.8) | **5.0** (2.6–7.2) | **6.1** (2.1–9.6) |
| Customer savings, $B NPV 3% (2026 $) | 29.1 (8.5–50.7) | 10.1 (3.2–26.3) | 3.1 (1.6–4.4) | 3.6 (1.2–5.7) |
| Average residential bill, $/month lower in 2035 | 17.75 (5.17–29.88) | 6.19 (2.64–14.70) | 11.09 (6.54–14.71) | 10.14 (4.06–16.95) |
| Average residential bill, $/month lower in 2050 | 125.09 (31.63–209.07) | 12.59 (4.61–30.45) | 27.26 (12.67–39.80) | 61.09 (17.00–86.92) |
| 2050 saving as % of the BAU delivery bill | 20% (5%–34%) | 12% (4%–28%) | 16% (7%–23%) | 14% (4%–20%) |
| New flexible MW by 2050 | 3,576 (466–3,729) | 2,547 (181–7,014) | 327 (169–660) | 545 (7–545) |
| Upgrade Delay avoided, MW-years (MW waiting in BAU) | 178 (31–215) of 141 MW | 482 (32–637) of 373 MW | 36 (11–49) of 23 MW | 24 (1–26) of 17 MW |
| Shared savings earnings, $B undiscounted | 17.79 (4.42–30.09) | 2.68 (0.06–9.10) | 0.64 (0.09–1.26) | 2.15 (0.65–3.15) |

**Published-plan vs model-derived BAU (Central).** The published plans call for more distribution spending than the network model generated, so there is more to defer and right-size. The model-derived BAU remains selectable (`bau_plan.basis: 'model'`).

| Central | Con Edison | Dominion VA | Pepco MD | RG&E |
|---|---|---|---|---|
| BAU average bill 2050, $/month: model → plan | 468 → 783 | 295 → 317 | 403 → 443 | 274 → 561 |
| BAU distribution capex 2026–2050, $B: model → plan | 147 → 324 | 49 → 62 | 8 → 11 | 8 → 40 |
| Customer savings, $B undiscounted: model → plan | 12.8 → 49.5 | 13.4 → 16.4 | 4.0 → 5.0 | 1.1 → 6.1 |
| 2050 bill $/month lower: model → plan | 19.10 → 125.09 | 9.89 → 12.59 | 15.88 → 27.26 | 3.57 → 61.09 |
| Shared savings earnings, $B: model → plan | 2.06 → 17.79 | 1.39 → 2.68 | 0.18 → 0.64 | 0.00 → 2.15 |

**In context.** The 2050 monthly saving (Central) is about 18 times Con Edison's latest residential rate-case increase ($6.81/month, rate year 1 at 600 kWh, Case 25-E-0072), 10 times RG&E's temporary-rate increase (+4.0% of electric revenue, about $6.38/month on the modelled bill), 7 times Pepco's ($3.94/month, Order No. 92607) and 1.1 times Dominion's ($11.24/month in 2026 at 1,000 kWh, PUR-2025-00058). The saving is in 2050 dollars and the increases in their rate years; see the CHANGELOG for 2035 multiples.

**What customer savings include.** They count what all customers pay for delivery (net of shared savings earnings), programs and capacity. On top of that they add:
- The energy efficiency saves, valued at today's residential supply rate.
- Wholesale energy, avoided transmission and avoided losses.

Each component is reported separately in `system_summary()`.

**Upgrade Delay.** Flexibility shortens the average delay:
- Dominion: from 1.75 years to 0.45 at Central.
- Con Edison: from 1.59 years to 0.32.

In Ambitious it removes almost all of it.

The notebooks and reports also show:
- The waterfall by layer.
- Each layer's contribution to savings, bills and earnings.
- The value stack per kW-year, and the cost at which flexibility pays for itself.
- A headroom sweep: how the potential depends on existing network headroom and on upgrade delays.

---

## What drives the range

Under published-plan BAU, the largest drivers are a policy choice (how much energy efficiency becomes core utility business), where flexibility is sited (locational match), and network inputs such as the reinforcement lead time. Because growth-driven plan capex now follows the model's load relative to the load the plan assumes, more load growth means more spending to defer, which offsets the thinner spread of fixed costs over more kWh. Data-centre and baseline growth have dropped down the tornado, except for Dominion, where data-centre growth is still second.

| Policy levers | External drivers |
|---|---|
| Efficiency ambition (savings rate): top driver for Con Edison, Dominion and Pepco | Load growth relative to the plan's own forecast (Con Edison 0.7%/yr, Dominion's PJM zone 5.4%/yr, Pepco 0.33%/yr, RG&E's Gold Book zone 3.0%/yr) |
| Flexible MW targets by resource type, and the ramp to reach them | Capacity, energy and transmission price growth |
| Locational targeting of flexibility and flexible connections | Network upgrade cost per MW |
| Utility share of savings; addressable shares of the plan (asset-replacement right-sizing is RG&E's second driver) | Efficiency and flexibility costs; the utility's capital plan and its path after the plan horizon |
| ROE lever: ±60 bp moves Con Edison's 2050 saving by about ±$10.77/month | Existing network headroom and upgrade delays (see the headroom sweep) |

---

## How to run it

```bash
git clone https://github.com/robertafcurrie/GridDividend.git
cd GridDividend
pip install -r requirements.txt          # pandas, numpy, matplotlib
jupyter notebook notebooks/GridDividend_Virginia.ipynb   # or _NewYork, _Maryland
pip install pytest && python -m pytest tests/            # full suite
```

The layered model is **Section 13** of each state notebook. Each run also writes HTML reports to `reports/`. To run the notebooks headlessly:

```bash
cd notebooks
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=python3 GridDividend_Virginia.ipynb
```

### Configuring it

- **Utility data:** `utilities/*.json`.
  - `starting_bill`: today's bill, line by line.
  - `forward_assumptions`: layers, scenarios and the `network` block.
  - Every input has `source`, `as_of` and `status`.
- **BAU basis:** `forward_assumptions['bau_plan']`: `basis` (`'published_plan'` or `'model'`), the plan capex and sources, `beyond_path` and `taper_year`, category and addressable shares, and the transmission plan.
- **Scenarios:** `forward_assumptions['scenarios']` sets the levels for Cautious / Central / Ambitious. Each scenario can also set its own `network` values.
- **Notebook what-ifs:** set `NETWORK_OVERRIDES` at the top of Section 13 to change any network input without editing the JSON, for example `{'subband_enabled': False}` or `{'mean_utilisation': 0.9}`.
- **Override order** (highest wins): notebook override > scenario values > JSON.
- **In code:** `engine.layers.project_layers()` takes `overrides`, `enabled` and `network` arguments.

---

## Caveats

- **Not a forecast.** Results show direction and order of magnitude.
- **BAU follows published plans, which are short and change.**
  - Distribution capex follows each utility's published plan: Con Edison 2026–2030, Dominion 2026–2030, Pepco 2026–2029, RG&E 2026–2031 (rate-case proposal).
  - After the plan, the central path tapers capex growth to load growth by 2035; continuing the plan's growth rate or following high electrification are the alternatives.
  - The split of plan capex into growth, replacement, grid modernisation and other is sourced for Con Edison and RG&E. **Dominion and Pepco use these New York splits as a proxy**: Dominion takes Con Edison's proportions for everything outside grid transformation, and Pepco takes RG&E's.
  - RG&E's plan is the company's Case 25-E-0379 proposal for 2026–2031 (final order pending; Staff recommended less for 2026–27), with 2028–2031 as an equal split of the filed total.
  - **Growth-driven plan capex is scaled to load:** by the model's cumulative peak growth relative to the plan's assumed load growth (`link_growth_to_load`; turn it off to keep plan capex fixed).
    - The model grows load faster than Con Edison's own 0.7% forecast (electrification), which raises its BAU capex.
    - It grows load slower than PJM's 5.4% for Dominion's zone, which lowers Dominion's.
    - Dominion's and RG&E's assumed load growth are zone forecasts used as proxies.
  - **RG&E's data centres** follow the NYISO 2026 Gold Book Zone B large-load forecast, allocated by RG&E's share of the zone's peak (57%).
  - The addressable shares (how much shared savings can defer or right-size) are settings.
- **Two-fifths to a half of the inputs are still `_VERIFY`.** By utility: Con Edison 41%, Dominion 38%, Pepco 43%, RG&E 54% of the status-tagged inputs in `starting_bill` and `forward_assumptions` (counts by layer in [ASSUMPTIONS.md](docs/ASSUMPTIONS.md)). Each one carries the reason and what would confirm it.
- **Proxies.** Con Edison, RG&E and Pepco use Dominion's measured network loading as a `_VERIFY` proxy until their own feeder data is found. New York uses PJM's price spreads for wholesale energy, and the other utilities use Con Edison's connection timelines for ordinary load.
- **Avoided transmission is a range.** PJM's network service rates are average costs: a lower peak shifts cost within the zone in the short run and avoids upgrades in the long run, so the avoidable share runs from 0 to 1.
- **ROE is a separate lever.** Central assumes no change in allowed ROE. Changing it moves bills and the utility's equity return, not shared savings earnings.
- **Spatially aggregate.** Loading bands approximate the network; real outcomes depend on feeder-level constraints and where flexibility is sited.
- **RG&E data is provisional** until the final order in Case 25-E-0379.
- **Dollar bases.** Every $ figure is labelled: nominal or 2026 $, undiscounted or NPV (3%, sometimes 7%). Customer savings include efficiency energy valued at the residential supply rate for all customer classes, which likely overstates the commercial and industrial share.

---

## The earlier model (v1.0 and CORRECTED)

Sections 1–12 of each notebook and `GridDividend_v1.0.ipynb` hold the earlier model, kept so its results reproduce exactly. It modelled shared savings as a system-wide share of eligible capex avoided by NWS, plus a capacity pass-through and a utilisation credit. Its scenarios were BAU, BASE (the "EASE Case" in its reports), ACCELERATED, FREEZE_PLUS, COMBINED and FRONTLOADED.

The `CORRECTED` preset switches on the recommended methodology fixes; it is not the default. Pinned tests check the v1.0 results for Con Edison, Dominion and Pepco. New analysis uses the layered model.

---

## Citation

If you use this work in research or publications, please cite:

> Currie, R. (2026). *GridDividend: Open Source Utility Shared Savings Framework*. GitHub Repository.

---

## License

MIT
