select
    scheduled_departure_hour,
    count(*) as scheduled_flights,
    sum(arrival_delayed_15) * 1.0 / count(*) as arrival_delay_rate,
    sum(severe_arrival_delay) * 1.0 / count(*) as severe_arrival_delay_rate,
    {{ reliability_score('cancelled', 'diverted', 'arrival_delayed_15', 'severe_arrival_delay', 'count(*)') }} as reliability_score
from {{ ref('stg_flights') }}
group by 1
