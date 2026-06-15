select
    airline_code,
    route,
    route_market,
    scheduled_flights,
    arrival_delay_rate,
    estimated_late_arrivals,
    reliability_score
from {{ ref('mart_route_reliability') }}
order by estimated_late_arrivals desc, arrival_delay_rate desc
limit 25
