with source as (
    select *
    from {{ source('lakehouse', 'fact_flight_performance') }}
),

typed as (
    select
        cast(year as integer) as year,
        cast(month as integer) as month,
        cast(flight_date as date) as flight_date,
        cast(day_of_week as integer) as day_of_week,
        airline_code,
        cast(flight_number as varchar) as flight_number,
        tail_number,
        origin_airport,
        origin_city,
        dest_airport,
        dest_city,
        cast(scheduled_dep_time as integer) as scheduled_dep_time,
        -- Floor-divide (not float division + round, which pushes e.g. 2359 -> 24);
        -- % 24 folds the 2400 midnight code back to hour 0.
        (cast(scheduled_dep_time as integer) // 100) % 24 as scheduled_departure_hour,
        cast(departure_delay_minutes as double) as departure_delay_minutes,
        cast(arrival_delay_minutes as double) as arrival_delay_minutes,
        coalesce(cast(departure_delayed_15 as integer), 0) as departure_delayed_15,
        coalesce(cast(arrival_delayed_15 as integer), 0) as arrival_delayed_15,
        coalesce(cast(cancelled as integer), 0) as cancelled,
        cancellation_code,
        coalesce(cast(diverted as integer), 0) as diverted,
        cast(distance_miles as double) as distance_miles,
        coalesce(cast(carrier_delay_minutes as double), 0) as carrier_delay_minutes,
        coalesce(cast(weather_delay_minutes as double), 0) as weather_delay_minutes,
        coalesce(cast(nas_delay_minutes as double), 0) as nas_delay_minutes,
        coalesce(cast(security_delay_minutes as double), 0) as security_delay_minutes,
        coalesce(cast(late_aircraft_delay_minutes as double), 0) as late_aircraft_delay_minutes
    from source
)

select
    *,
    case when arrival_delay_minutes >= 60 then 1 else 0 end as severe_arrival_delay,
    origin_airport || '-' || dest_airport as route,
    origin_city || ' to ' || dest_city as route_market
from typed
