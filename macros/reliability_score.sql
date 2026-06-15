{% macro reliability_score(cancelled_expr, diverted_expr, arrival_delayed_expr, severe_arrival_delay_expr, denominator_expr) -%}
    greatest(0, least(100,
        100
          - 45 * (sum({{ cancelled_expr }}) * 1.0 / nullif({{ denominator_expr }}, 0))
          - 30 * (sum({{ diverted_expr }}) * 1.0 / nullif({{ denominator_expr }}, 0))
          - 20 * (sum({{ arrival_delayed_expr }}) * 1.0 / nullif({{ denominator_expr }}, 0))
          - 5  * (sum({{ severe_arrival_delay_expr }}) * 1.0 / nullif({{ denominator_expr }}, 0))
    ))
{%- endmacro %}
