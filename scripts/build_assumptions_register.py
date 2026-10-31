"""
Assumptions register, generated from utilities/*.json.

Writes docs/assumptions_register.csv (one row per input per utility) and
docs/ASSUMPTIONS.md (status counts by utility and layer, then the inputs).
Covers every status-tagged input of the layered model (starting_bill lines,
forward_assumptions: projection, layers, network, capacity_carve_out,
starting_adjustments) and the top-level utility fields of the earlier model,
whose status is given by the `_..._VERIFY` key placed before them.

    python scripts/build_assumptions_register.py           # write both files
    python scripts/build_assumptions_register.py --check   # exit 1 if out of date

tests/test_assumptions_register.py fails if the files are out of date.
"""
import csv
import io
import json
import os
import re
import sys
from collections import Counter, OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UTILITIES = OrderedDict([('ConEd', 'ConEd.json'), ('RGE', 'RGE.json'), ('DomVA', 'Dominion_VA.json'),
                         ('PepcoMD', 'Pepco_MD.json')])
STATUSES = ('sourced', 'derived', '_VERIFY', 'setting')
COLUMNS = ['utility', 'section', 'layer', 'input', 'name', 'value', 'low', 'central', 'high', 'unit', 'status',
           'source', 'source_link', 'as_of', 'notes']
CSV_PATH = os.path.join('docs', 'assumptions_register.csv')
MD_PATH = os.path.join('docs', 'ASSUMPTIONS.md')
URL = re.compile(r'https?://[^\s;,)\]]+|(?<![\w/@.])(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:gov|com|org|net|us)'
                 r'(?:/[^\s;,)\]]*)?', re.I)


def _fmt(v):
    """Compact text for a value: numbers as stored, lists and dicts as JSON, None as blank."""
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (list, dict)):
        return json.dumps(v, separators=(',', ':'))
    return str(v)


def _links(text):
    """URLs and bare web addresses quoted in a source string (blank if none)."""
    seen = []
    for m in URL.findall(text or ''):
        m = m.rstrip('.')
        if m not in seen:
            seen.append(m)
    return '; '.join(seen)


def _spec_row(ukey, section, layer, pname, spec):
    row = dict(utility=ukey, section=section, layer=layer, input=pname, name='')
    if isinstance(spec, dict) and ('central' in spec or 'value' in spec):
        row.update(value=_fmt(spec.get('value')), low=_fmt(spec.get('low')), central=_fmt(spec.get('central')),
                   high=_fmt(spec.get('high')), unit=spec.get('unit', ''), status=spec.get('status', ''),
                   source=spec.get('source', ''), as_of=spec.get('as_of', ''),
                   notes=spec.get('note', spec.get('notes', '')) or '')
    else:                                         # a bare value (no spec)
        row.update(value=_fmt(spec), low='', central='', high='', unit='', status='', source='', as_of='', notes='')
    return row


def utility_rows(ukey, uj):
    """One dict per input for one utility (COLUMNS keys)."""
    rows = []
    sb = uj['starting_bill']
    for ln in sb['lines']:
        rows.append(dict(utility=ukey, section='starting_bill', layer='starting_bill', input=ln['id'],
                         name=ln.get('name', ''), value=_fmt(ln.get('rate')), low='', central='', high='',
                         unit=ln.get('unit', '') + (f" of {ln['applies_to']}" if ln.get('applies_to') else ''),
                         status=ln.get('status', ''), source=ln.get('source', ''), as_of=ln.get('as_of', ''),
                         notes=' '.join(x for x in (ln.get('tariff_detail') or '', ln.get('notes') or '') if x)))
    fa = uj['forward_assumptions']
    for pname, spec in fa['projection'].items():
        rows.append(_spec_row(ukey, 'forward_assumptions', 'projection', pname, spec))
    for lname, layer in fa['layers'].items():
        for pname, spec in layer.get('params', {}).items():
            rows.append(_spec_row(ukey, 'forward_assumptions', lname, pname, spec))
    for pname, spec in fa.get('network', {}).get('params', {}).items():
        rows.append(_spec_row(ukey, 'forward_assumptions', 'network', pname, spec))
    co = fa.get('capacity_carve_out')
    if co:
        rows.append(dict(utility=ukey, section='forward_assumptions', layer='capacity_carve_out',
                         input='capacity_carve_out', name='Capacity carved out of the bill line(s) where it is embedded',
                         value=_fmt({k: v for k, v in co.items() if k not in ('source', 'status', 'as_of', 'method')}),
                         low='', central='', high='', unit='inputs to $/month (see method)', status=co.get('status', ''),
                         source=co.get('source', ''), as_of=co.get('as_of', ''), notes=co.get('method', '')))
    for adj in fa.get('starting_adjustments', []):
        rows.append(dict(utility=ukey, section='forward_assumptions', layer='starting_adjustments', input=adj['id'],
                         name=adj.get('name', ''), value=_fmt(adj.get('month')), low='', central='', high='',
                         unit='$/month', status=adj.get('status', ''), source=adj.get('source', ''),
                         as_of=adj.get('as_of', ''), notes=adj.get('note', '')))
    keys = list(uj.keys())
    for i, k in enumerate(keys):                  # earlier-model top-level fields
        v = uj[k]
        if k.startswith('_') or k in ('starting_bill', 'forward_assumptions') or not isinstance(v, (int, float)) \
                or isinstance(v, bool):
            continue
        prev = keys[i - 1] if i else ''
        note = uj[prev] if prev.endswith(('_note', '_VERIFY')) else ''
        rows.append(dict(utility=ukey, section='utility_data', layer='earlier model', input=k, name='', value=_fmt(v),
                         low='', central='', high='', unit='', status='_VERIFY' if prev.endswith('_VERIFY') else '',
                         source=note if isinstance(note, str) else _fmt(note), as_of='', notes=''))
    for r in rows:
        r['source_link'] = _links(r['source'])
    return rows


def all_rows(root=ROOT):
    rows = []
    for ukey, fn in UTILITIES.items():
        with open(os.path.join(root, 'utilities', fn)) as f:
            rows += utility_rows(ukey, json.load(f))
    return rows


def build_csv(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator='\n')
    w.writeheader()
    for r in rows:
        w.writerow({c: str(r[c]).replace('\r', ' ').replace('\n', ' ') for c in COLUMNS})
    return buf.getvalue()


def _md(s, n=None):
    s = str(s).replace('|', '\\|').replace('\n', ' ')
    return s if n is None or len(s) <= n else s[:n - 1].rstrip() + '…'


def build_md(rows):
    tagged = [r for r in rows if r['section'] != 'utility_data']
    out = ['# Assumptions register', '',
           'Generated by `scripts/build_assumptions_register.py` from `utilities/*.json`; do not edit by hand. '
           'The full register, with sources, as-of dates and notes in full, is '
           '[`assumptions_register.csv`](assumptions_register.csv). '
           '`tests/test_assumptions_register.py` fails if either file is out of date with the JSON.', '',
           'Status: **sourced** = read from a cited document; **derived** = calculated from sourced figures; '
           '**_VERIFY** = estimate, assumption or proxy awaiting confirmation; **setting** = a model switch or mode '
           'choice. Ranges are low / central / high; scenarios and the tornado pick levels (see '
           '[METHODOLOGY.md](METHODOLOGY.md)).', '',
           '## Status counts by utility', '',
           'Status-tagged inputs of the layered model (`starting_bill` and `forward_assumptions`).', '',
           '| Utility | ' + ' | '.join(STATUSES) + ' | Total | _VERIFY share |',
           '|---|' + '---:|' * (len(STATUSES) + 2)]
    for ukey in UTILITIES:
        c = Counter(r['status'] for r in tagged if r['utility'] == ukey)
        tot = sum(c[s] for s in STATUSES)
        out.append(f'| {ukey} | ' + ' | '.join(str(c[s]) for s in STATUSES)
                   + f" | {tot} | {c['_VERIFY'] / tot:.0%} |")
    untagged = [r for r in tagged if r['status'] not in STATUSES]
    if untagged:
        out += ['', f'Inputs without a status: {len(untagged)} (' +
                ', '.join(f"{r['utility']} {r['layer']}.{r['input']}" for r in untagged) + ').']
    out += ['', '## Status counts by layer', '', 'All four utilities together.', '',
            '| Layer | ' + ' | '.join(STATUSES) + ' | Total |', '|---|' + '---:|' * (len(STATUSES) + 1)]
    layers = list(OrderedDict.fromkeys(r['layer'] for r in tagged))
    for l in layers:
        c = Counter(r['status'] for r in tagged if r['layer'] == l)
        out.append(f'| {l} | ' + ' | '.join(str(c[s]) for s in STATUSES) + f' | {sum(c[s] for s in STATUSES)} |')
    out += ['', '## Status counts by utility and layer', '', '_VERIFY / total status-tagged inputs.', '',
            '| Layer | ' + ' | '.join(UTILITIES) + ' |', '|---|' + '---:|' * len(UTILITIES)]
    for l in layers:
        cells = []
        for ukey in UTILITIES:
            rs = [r for r in tagged if r['layer'] == l and r['utility'] == ukey]
            cells.append(f"{sum(r['status'] == '_VERIFY' for r in rs)} / {sum(r['status'] in STATUSES for r in rs)}"
                         if rs else '–')
        out.append(f'| {l} | ' + ' | '.join(cells) + ' |')
    for ukey in UTILITIES:
        out += ['', f'## {ukey}', '',
                'Value is the single value or setting; ranges are low / central / high. Sources are truncated here; '
                'see the CSV for the full text.', '',
                '| Layer | Input | Value | Low | Central | High | Unit | Status | As of | Source |',
                '|---|---|---|---|---|---|---|---|---|---|']
        for r in tagged:
            if r['utility'] != ukey:
                continue
            out.append('| ' + ' | '.join([_md(r['layer']), _md(r['input']), _md(r['value'], 60), _md(r['low']),
                                          _md(r['central']), _md(r['high']), _md(r['unit'], 50), _md(r['status']),
                                          _md(r['as_of']), _md(r['source'], 140)]) + ' |')
        top = [r for r in rows if r['utility'] == ukey and r['section'] == 'utility_data']
        if top:
            out += ['', f'**{ukey}: earlier-model fields** (top level of the JSON; status `_VERIFY` where a '
                    '`_..._VERIFY` note precedes the field, otherwise untagged).', '',
                    '| Field | Value | Status | Note |', '|---|---|---|---|']
            for r in top:
                out.append(f"| {r['input']} | {_md(r['value'])} | {r['status'] or '–'} | {_md(r['source'], 140)} |")
    return '\n'.join(out) + '\n'


def build(root=ROOT):
    """(csv text, markdown text) for the register."""
    rows = all_rows(root)
    return build_csv(rows), build_md(rows)


def main(argv):
    csv_text, md_text = build()
    targets = ((CSV_PATH, csv_text), (MD_PATH, md_text))
    if '--check' in argv:
        stale = []
        for rel, text in targets:
            p = os.path.join(ROOT, rel)
            if not os.path.exists(p) or open(p, encoding='utf-8').read() != text:
                stale.append(rel)
        if stale:
            print('Out of date: ' + ', '.join(stale) + ' (run python scripts/build_assumptions_register.py)')
            return 1
        print('Assumptions register up to date.')
        return 0
    for rel, text in targets:
        with open(os.path.join(ROOT, rel), 'w', encoding='utf-8', newline='') as f:
            f.write(text)
        print(f'Wrote {rel}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
