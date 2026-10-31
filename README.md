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

Figures are Central, with the Cautious–Ambitious range in brackets. All $ are nominal.

| | Con Edison | Dominion VA | Pepco MD | RG&E |
|---|---|---|---|---|
| **Customer savings 2026–2050, $B undiscounted** | **14.4** (4.3–29.8) | **13.4** (3.6–37.8) | **4.0** (1.9–5.6) | **1.1** (0.4–2.6) |
| Customer savings, $B NPV 3% (2026 $) | 8.8 (2.7–18.3) | 8.3 (2.3–23.3) | 2.5 (1.2–3.5) | 0.7 (0.2–1.6) |
| Average residential bill, $/month lower in 2035 | 6.37 (1.73–11.41) | 5.22 (2.21–12.78) | 8.67 (5.22–11.30) | 1.96 (0.78–4.29) |
| Average residential bill, $/month lower in 2050 | 16.63 (3.65–28.26) | 9.89 (3.16–25.61) | 15.88 (5.40–23.31) | 4.44 (1.06–10.84) |
| New flexible MW by 2050 | 3,576 (466–3,729) | 2,547 (181–7,014) | 327 (169–660) | 545 (7–545) |
| Upgrade Delay avoided, MW-years (MW waiting in BAU) | 178 (31–215) of 141 MW | 482 (32–637) of 373 MW | 36 (11–49) of 23 MW | 24 (1–26) of 17 MW |
| Shared savings earnings, $B undiscounted | 2.26 (0.05–4.95) | 1.39 (0.01–6.95) | 0.18 (0.01–0.59) | 0.01 (0.00–0.16) |

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

The largest single driver is a policy choice: how much energy efficiency becomes core utility business.

| Policy levers | External drivers |
|---|---|
| Efficiency ambition (savings rate): top driver for Dominion and RG&E, second for Con Edison (just behind the ROE lever) and Pepco | Load growth, especially data centres |
| Flexible MW targets by resource type, and the ramp to reach them | Capacity, energy and transmission price growth |
| Locational targeting of flexibility and flexible connections | Network upgrade cost per MW |
| Utility share of savings | Efficiency and flexibility costs |
| ROE lever: ±60 bp moves Con Edison's 2050 saving by about ±$4.60/month | Existing network headroom and upgrade delays (see the headroom sweep) |

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
- **Scenarios:** `forward_assumptions['scenarios']` sets the levels for Cautious / Central / Ambitious. Each scenario can also set its own `network` values.
- **Notebook what-ifs:** set `NETWORK_OVERRIDES` at the top of Section 13 to change any network input without editing the JSON, for example `{'subband_enabled': False}` or `{'mean_utilisation': 0.9}`.
- **Override order** (highest wins): notebook override > scenario values > JSON.
- **In code:** `engine.layers.project_layers()` takes `overrides`, `enabled` and `network` arguments.

---

## Caveats

- **Not a forecast.** Results show direction and order of magnitude.
- **About half the inputs are still `_VERIFY`.** By utility: Con Edison 46%, Dominion 43%, Pepco 49%, RG&E 58% of the status-tagged inputs in `starting_bill` and `forward_assumptions` (counts by layer in [ASSUMPTIONS.md](docs/ASSUMPTIONS.md)). Each one carries the reason and what would confirm it.
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
