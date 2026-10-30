# engine/markets.py
# Loader for shared/capacity_markets/*.json — utility-agnostic.

import json
import os


def load_capacity_market(market, root='..'):
    """Return the parsed shared/capacity_markets/{market}.json dict."""
    path = os.path.join(root, 'shared', 'capacity_markets', f'{market}.json')
    with open(path) as f:
        return json.load(f)


def capacity_growth_for(market, zone, inflation_rate=None):
    """
    Annual capacity-price growth for one zone of a parsed market file.
    A zone may override the market-wide 'capacity_cost_growth_real' with its
    own 'capacity_cost_growth': a number, or the string 'INFLATION_RATE'
    (capacity price flat in real terms; needs inflation_rate). Applied by the
    engine to nominal $ via capacity_cost_in_year().
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
    (capacity_cost_start_m_per_mw_yr, growth) for a utility, looked up from
    its 'capacity_market' / 'capacity_market_zone' fields. Start is nominal $M
    per MW-year at the 2026 anchor, exactly as stored (no rounding); growth as
    resolved by capacity_growth_for().
    """
    m = load_capacity_market(utility_json['capacity_market'], root)
    zone = utility_json['capacity_market_zone']
    return (m['zones'][zone]['capacity_cost_start_m_per_mw_yr'],
            capacity_growth_for(m, zone, inflation_rate))
