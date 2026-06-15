select
    'mart_airline_reliability' as model_name,
    airline_code as entity_key,
    reliability_score
from {{ ref('mart_airline_reliability') }}
where reliability_score < 0
   or reliability_score > 100

union all

select
    'mart_route_reliability' as model_name,
    route as entity_key,
    reliability_score
from {{ ref('mart_route_reliability') }}
where reliability_score < 0
   or reliability_score > 100
