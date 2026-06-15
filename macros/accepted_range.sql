{% test accepted_range(model, column_name, min_value=none, max_value=none, inclusive=true) %}

select *
from {{ model }}
where
    {% if min_value is not none and max_value is not none %}
        {% if inclusive %}
            {{ column_name }} < {{ min_value }} or {{ column_name }} > {{ max_value }}
        {% else %}
            {{ column_name }} <= {{ min_value }} or {{ column_name }} >= {{ max_value }}
        {% endif %}
    {% elif min_value is not none %}
        {% if inclusive %}
            {{ column_name }} < {{ min_value }}
        {% else %}
            {{ column_name }} <= {{ min_value }}
        {% endif %}
    {% elif max_value is not none %}
        {% if inclusive %}
            {{ column_name }} > {{ max_value }}
        {% else %}
            {{ column_name }} >= {{ max_value }}
        {% endif %}
    {% else %}
        false
    {% endif %}

{% endtest %}
