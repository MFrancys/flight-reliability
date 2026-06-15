with totals as (
    select
        sum(carrier_delay_minutes)      as carrier,
        sum(weather_delay_minutes)      as weather,
        sum(nas_delay_minutes)          as nas,
        sum(security_delay_minutes)     as security,
        sum(late_aircraft_delay_minutes) as late_aircraft
    from {{ ref('stg_flights') }}
),

unpivoted as (
    unpivot totals
    on carrier, weather, nas, security, late_aircraft
    into name delay_reason value delay_minutes
)

select
    delay_reason,
    delay_minutes,
    delay_minutes / nullif(sum(delay_minutes) over (), 0) as share_of_explained_delay
from unpivoted
