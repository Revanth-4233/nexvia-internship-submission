-- Long format of fct_attribution (one row per touchpoint per model) - the shape Tableau filters on.
{% set models = ['first_touch', 'last_touch', 'last_non_direct', 'linear', 'time_decay', 'position_based'] %}
{% for m in models %}
select
    touchpoint_id, order_id, customer_key, order_ts, channel, platform, campaign,
    '{{ m }}'          as attribution_model,
    w_{{ m }}          as credit,
    rev_{{ m }}        as attributed_revenue
from {{ ref('fct_attribution') }}
{% if not loop.last %}union all{% endif %}
{% endfor %}
