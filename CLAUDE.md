# GridDividend — CLAUDE.md

## Project purpose

GridDividend is a Jupyter Notebook policy simulation framework modelling shared savings mechanisms for electric distribution utilities. The core question: if Non-Wires Solutions (NWS) — demand response, batteries, managed EV charging — defer traditional CAPEX, how should those savings be split between customers and the utility, and what is the bill impact over a 25-year horizon?

This is an exploratory/educational tool, not a utility planning model or rate-case replica. AI has been used extensively in its creation.

## Repository layout

```
GridDividend_v1.0.ipynb   — entire model (24 cells, self-contained)
requirements.txt          — pandas, numpy, matplotlib (minimum versions)
docs/                     — pre-run chart images for README
README.md
LICENSE                   — MIT
```

No Python modules, tests, or helper scripts exist yet.

## Running the notebook

The kernel name in the notebook metadata is `conda-base-py`. When executing headlessly via nbconvert, override the kernel:

```bash
jupyter nbconvert --to notebook --execute \
  --ExecutePreprocessor.kernel_name=python3 \
  GridDividend_v1.0.ipynb --output GridDividend_executed.ipynb
```

The notebook installs nothing at runtime — all dependencies (pandas, numpy, matplotlib) must be present in the environment beforehand.

## Key domain concepts

| Term | Meaning |
|------|---------|
| NWS | Non-Wires Solution — DER/DR programmes that defer traditional network CAPEX |
| NWA | Non-Wires Alternative — a specific NWS procurement |
| DER | Distributed Energy Resource — rooftop solar, battery, managed EV, demand response |
| Shared savings | Mechanism splitting NWS cost savings between utility (incentive) and customers (bill reduction) |
| BAU | Business As Usual — traditional build-out, no shared savings reform |
| Rate base | Regulated asset value on which the utility earns its allowed ROE |
| WACC | Weighted average cost of capital (equity + debt blend) |
| CLCPA | Climate Leadership and Community Protection Act — NY's 2019 clean energy law |

## Utilities currently modelled

| Key | Name | Rate case source |
|-----|------|-----------------|
| `'ConEd'` | Consolidated Edison (CECONY) | Case 25-E-0072, approved Jan 2026 |
| `'RGE'` | Rochester Gas and Electric | Case 25-E-0379, temp rates Jun 2026; final order pending |

## Notebook structure

| Section | Cell(s) | Content |
|---------|---------|---------|
| 0 | 2 | Imports, matplotlib styling, output directory |
| 1 | 4–6 | All user-adjustable parameters (edit here, re-run all) |
| 2 | 7–8 | Utility starting data from filed rate cases |
| 3 | 9–10 | `project()` model engine: 2026–2050 annual loop |
| 4 | 11–12 | Runs BAU / shared savings × freeze / no-freeze for each utility |
| 5 | 13–14 | Customer bill charts |
| 6 | 15–16 | CAPEX & OPEX spending charts |
| 7 | 17–18 | Utility financial results |
| 8 | 19–20 | Sensitivity analysis |
| 9 | 21–22 | Con Edison vs. RG&E side-by-side comparison |
| 10 | 23 | Model caveats and scope statement |

## Key parameters (Section 1, Cell 4)

Every parameter has a source citation in the comment block immediately below it. The most sensitive parameters:

- `UTILITY_SAVINGS_SHARE` — fraction of savings retained by utility (default 0.30)
- `NWS_AVOIDANCE_OF_ELIGIBLE_MATURE` — avoidance rate at programme maturity (default 0.80)
- `NWS_AVOIDANCE_RAMP_YEARS` — years to reach maturity (default 9)
- `FLEX_LOAD_UTILISATION_SHARE_SS` — utilisation credit for shared savings scenario (default 0.15)
- `utilities_to_run` — list of utility keys to model (`['ConEd']`, `['RGE']`, or both)

## What to be careful about

- **Not a forecast.** Direction and order of magnitude only.
- **Spatially aggregate.** NWS is modelled as a system-wide % of eligible CAPEX; real outcomes depend on feeder-level constraint types and DER siting.
- **RG&E data is provisional.** Update when Case 25-E-0379 issues a final order.
- **Property tax rates are estimates** (~1.6% ConEd, ~1.8% RG&E electric assets only) derived from annual reports, not official filed figures.
- **Do not remove or reorder sections** — downstream cells reference earlier variables by name.

## Coding conventions

- Parameters: `UPPER_SNAKE_CASE`; model functions: `lower_snake_case`
- Every new parameter in Section 1 must include a source citation in the inline comment block
- Keep the notebook self-contained — avoid adding external data file dependencies
- New utility dicts must match the structure of `UTILITIES` in Cell 4, with all fields documented and sourced

## When adding a new utility

Supply a dict matching the `UTILITIES` structure (Cell 4): rate base, annual CAPEX, allowed ROE, equity ratio, customer count, peak demand, delivery/supply tariff rates, and DER starting levels. Document the rate case source inline next to each figure. Also add a matching entry in `UTILITY_BILL_PARAMS` (also Cell 4).
