# engine/markets.py
# Loader for shared/capacity_markets/*.json — utility-agnostic.

import json
import os


def load_capacity_market(market, root='..'):
    """
    Parsed capacity market file.

    Inputs: market (e.g. 'NYISO', 'PJM'); root = repository root relative to the
      working directory ('..' from notebooks/).
    Output: dict from shared/capacity_markets/{market}.json (zones with
      capacity_cost_start_m_per_mw_yr in $M per MW-year nominal, growth rates,
      sources).
    """
    path = os.path.join(root, 'shared', 'capacity_markets', f'{market}.json')
    with open(path) as f:
        return json.load(f)


def capacity_growth_for(market, zone, inflation_rate=None):
    """
    Annual capacity-price growth for one zone.

    Inputs: market (parsed file); zone; inflation_rate (needed when the zone's
      growth is 'INFLATION_RATE').
    A zone may override the market-wide 'capacity_cost_growth_real' with its own
    'capacity_cost_growth': a number, or the string 'INFLATION_RATE' (capacity
    price flat in real terms). Applied by the engine to nominal $ via
    capacity_cost_in_year().
    Output: float, growth per year (share).
    """
    z = market['zones'][zone]
    g = z.get('capacity_cost_growth', market['capacity_cost_growth_real'])
    if g == 'INFLATION_RATE':
        if inflation_rate is None:
            raise ValueError(f"{zone}: growth is INFLATION_RATE but no inflation_rate given")
        return inflation_rate
    return g


def capacity_cost_for(utility_json, root='..', inflation_rate=None):
    """
    Capacity cost start and growth for a utility.

    Inputs: utility_json (capacity_market, capacity_market_zone); root;
      inflation_rate.
    Output: (capacity_cost_start_m_per_mw_yr, growth): start in nominal $M per
      MW-year at the 2026 anchor, exactly as stored; growth per year as resolved
      by capacity_growth_for().
    """
    m = load_capacity_market(utility_json['capacity_market'], root)
    zone = utility_json['capacity_market_zone']
    return (m['zones'][zone]['capacity_cost_start_m_per_mw_yr'],
            capacity_growth_for(m, zone, inflation_rate))
