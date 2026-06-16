select
    airline_code,
    {{ flight_reliability_metrics() }}
from {{ ref('stg_flights') }}
group by 1
