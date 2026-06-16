select
    airline_code,
    origin_airport,
    dest_airport,
    route,
    route_market,
    {{ flight_reliability_metrics() }},
    round(count(*) * (sum(arrival_delayed_15) * 1.0 / count(*)), 0) as estimated_late_arrivals
from {{ ref('stg_flights') }}
group by airline_code, origin_airport, dest_airport, route, route_market
having count(*) >= {{ var('minimum_route_flights') }}
