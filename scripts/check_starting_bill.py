#!/usr/bin/env python
"""
Validate each utility JSON's `starting_bill` section (data only; nothing here
changes the model).

For each utility:
  - prices every included line at the benchmark usage (residential_kwh_month);
  - totals by category and by bill section (delivery / supply / tax);
  - compares the delivery and supply subtotals (and the distribution_base
    lines alone, since some delivery riders sit outside the model's rate
    fields by design) with the model's existing
    tariff fields (basic_charge_month + delivery_rate_kwh x kWh, and
    supply_rate_kwh x kWh) and reports the gap in $/month and %;
  - reports the share of the bill made up by program lines flagged
    core_business_under_shared_savings = true.

Rate fields are read from the utility JSON when present, otherwise from the
notebook's UTILITY_BILL_PARAMS (Con Edison and RG&E live in the New York
notebook). All $ are nominal, per residential customer per month.

Usage:  python scripts/check_starting_bill.py [--json]
"""
import contextlib
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UTILITIES = {  # key -> (json file, notebook holding UTILITY_BILL_PARAMS if not in JSON)
    'ConEd': ('ConEd.json', 'GridDividend_NewYork.ipynb'),
    'RGE': ('RGE.json', 'GridDividend_NewYork.ipynb'),
    'DomVA': ('Dominion_VA.json', 'GridDividend_Virginia.ipynb'),
    'PepcoMD': ('Pepco_MD.json', 'GridDividend_Maryland.ipynb'),
}
CATEGORIES = ('distribution_base', 'distribution_rider', 'program_surcharge', 'supply_energy',
              'capacity', 'transmission', 'taxes_and_fees')
RATE_FIELDS = ('delivery_rate_kwh', 'supply_rate_kwh', 'basic_charge_month')
_NB_CACHE = {}


def _notebook_bill_params(nb_name):
    """UTILITY_BILL_PARAMS from a notebook's Section 0 and 1 cells."""
    if nb_name not in _NB_CACHE:
        sys.path.insert(0, ROOT)
        nb_dir = os.path.join(ROOT, 'notebooks')
        nb = json.load(open(os.path.join(nb_dir, nb_name)))
        src = [''.join(c['source']) for c in nb['cells'] if c['cell_type'] == 'code']
        ns, cwd = {}, os.getcwd()
        os.chdir(nb_dir)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                for tag in ('# SECTION 0: SETUP', '# SECTION 1: USER-ADJUSTABLE'):
                    exec([s for s in src if tag in s.split('\n', 3)[1]][0], ns)
        finally:
            os.chdir(cwd)
        _NB_CACHE[nb_name] = ns['UTILITY_BILL_PARAMS']
    return _NB_CACHE[nb_name]


def rate_fields(key, u):
    json_file, nb = UTILITIES[key]
    if all(f in u for f in RATE_FIELDS):
        return {f: u[f] for f in RATE_FIELDS}, f'utilities/{json_file}'
    p = _notebook_bill_params(nb)[key]
    return {f: p[f] for f in RATE_FIELDS}, f'notebooks/{nb} UTILITY_BILL_PARAMS'


def price_lines(sb):
    """$/month for each included line at the benchmark usage."""
    kwh = sb['benchmark_kwh_month']
    priced, base = [], {'delivery': 0.0, 'supply': 0.0, 'distribution_and_transmission': 0.0}
    pct_lines = []
    for ln in sb['lines']:
        if not ln.get('included_in_benchmark', True) or ln.get('rate') is None:
            priced.append((ln, None))
            continue
        unit = ln['unit']
        if unit == '$/month':
            m = ln['rate']
        elif unit == '$/kWh':
            m = ln['rate'] * kwh
        elif unit == 'pct':
            pct_lines.append(ln)
            continue
        else:
            raise ValueError(f"unknown unit {unit!r} in line {ln['id']}")
        priced.append((ln, m))
        if ln['bill_section'] in ('delivery', 'supply'):
            base[ln['bill_section']] += m
        if ln['category'] in ('distribution_base', 'distribution_rider', 'transmission'):
            base['distribution_and_transmission'] += m
    for ln in pct_lines:
        priced.append((ln, base[ln['applies_to']] * ln['rate'] / 100))
    return priced


def check(key):
    json_file, _ = UTILITIES[key]
    u = json.load(open(os.path.join(ROOT, 'utilities', json_file)))
    sb = u['starting_bill']
    kwh = sb['benchmark_kwh_month']
    priced = price_lines(sb)
    by_cat = {c: 0.0 for c in CATEGORIES}
    by_sec = {'delivery': 0.0, 'supply': 0.0, 'tax': 0.0}
    core = 0.0
    for ln, m in priced:
        if m is None:
            continue
        by_cat[ln['category']] += m
        by_sec[ln['bill_section']] += m
        if ln.get('core_business_under_shared_savings'):
            core += m
    total = sum(by_sec.values())
    fields, fsrc = rate_fields(key, u)
    model_delivery = fields['basic_charge_month'] + fields['delivery_rate_kwh'] * kwh
    model_supply = fields['supply_rate_kwh'] * kwh
    gap = lambda bill, model: (bill - model, (bill - model) / model if model else float('nan'))
    return dict(
        utility=key, short_name=u.get('short_name', key), benchmark_kwh=kwh, as_of=sb.get('as_of'),
        lines=[dict(id=ln['id'], name=ln['name'], category=ln['category'],
                    bill_section=ln['bill_section'], program_type=ln.get('program_type'),
                    core=ln.get('core_business_under_shared_savings'),
                    month=None if m is None else round(m, 2), status=ln['status'])
               for ln, m in priced],
        by_category={c: round(v, 2) for c, v in by_cat.items()},
        by_section={s: round(v, 2) for s, v in by_sec.items()},
        total_month=round(total, 2),
        core_program_month=round(core, 2),
        core_program_share=core / total if total else float('nan'),
        model_fields=fields, model_fields_source=fsrc,
        delivery_gap=gap(by_sec['delivery'], model_delivery),
        base_delivery_gap=gap(by_cat['distribution_base'], model_delivery),
        supply_gap=gap(by_sec['supply'], model_supply),
        model_delivery_month=round(model_delivery, 2), model_supply_month=round(model_supply, 2),
        customer_charge_gap=next(((ln['rate'] - fields['basic_charge_month'])
                                  for ln, _ in priced if ln['unit'] == '$/month'
                                  and ln['category'] == 'distribution_base'), None),
        verify_lines=[ln['id'] for ln, _ in priced if ln['status'] == '_VERIFY'],
        published_check=sb.get('published_check'),
    )


def main():
    results = [check(k) for k in UTILITIES]
    if '--json' in sys.argv:
        print(json.dumps(results, indent=2, default=str))
        return
    for r in results:
        print(f"\n=== {r['short_name']} - {r['benchmark_kwh']} kWh/month, as of {r['as_of']} "
              f"(nominal $ per residential customer per month)")
        for ln in r['lines']:
            m = '   excluded' if ln['month'] is None else f"{ln['month']:>11.2f}"
            core = '' if ln['core'] is None else ('core' if ln['core'] else 'not core')
            print(f"  {m}  {ln['category']:<19} {(ln['program_type'] or ''):<22} {core:<9} "
                  f"{ln['status']:<8} {ln['name'][:60]}")
        print('  By category: ' + ', '.join(f'{c} {v:.2f}' for c, v in r['by_category'].items() if v))
        print(f"  Sections: delivery {r['by_section']['delivery']:.2f}, supply {r['by_section']['supply']:.2f}, "
              f"tax {r['by_section']['tax']:.2f}; total {r['total_month']:.2f}")
        print(f"  Core-business programs: {r['core_program_month']:.2f}/month "
              f"({r['core_program_share']:.1%} of the bill)")
        d, s = r['delivery_gap'], r['supply_gap']
        print(f"  vs model fields ({r['model_fields_source']}): delivery {r['model_delivery_month']:.2f} -> "
              f"gap {d[0]:+.2f} ({d[1]:+.1%}); supply {r['model_supply_month']:.2f} -> gap {s[0]:+.2f} "
              f"({s[1]:+.1%}); customer charge gap {r['customer_charge_gap']:+.2f}")
        b = r['base_delivery_gap']
        print(f"  distribution_base lines only vs model delivery: gap {b[0]:+.2f} ({b[1]:+.1%})")
        if r['published_check']:
            print(f"  Published check: {r['published_check']['description']}")
        if r['verify_lines']:
            print(f"  _VERIFY lines: {', '.join(r['verify_lines'])}")


if __name__ == '__main__':
    main()
