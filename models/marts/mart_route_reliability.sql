select
    airline_code,
    origin_airport,
    dest_airport,
    route,
    route_market,
    count(*) as scheduled_flights,
    avg(arrival_delay_minutes) as avg_arrival_delay_minutes,
    quantile_cont(arrival_delay_minutes, 0.90) as p90_arrival_delay_minutes,
    sum(arrival_delayed_15) * 1.0 / count(*) as arrival_delay_rate,
    sum(departure_delayed_15) * 1.0 / count(*) as departure_delay_rate,
    sum(cancelled) * 1.0 / count(*) as cancellation_rate,
    sum(diverted) * 1.0 / count(*) as diversion_rate,
    sum(severe_arrival_delay) * 1.0 / count(*) as severe_arrival_delay_rate,
    round(count(*) * (sum(arrival_delayed_15) * 1.0 / count(*)), 0) as estimated_late_arrivals,
    {{ reliability_score('cancelled', 'diverted', 'arrival_delayed_15', 'severe_arrival_delay', 'count(*)') }} as reliability_score
from {{ ref('stg_flights') }}
group by airline_code, origin_airport, dest_airport, route, route_market
having count(*) >= {{ var('minimum_route_flights') }}
