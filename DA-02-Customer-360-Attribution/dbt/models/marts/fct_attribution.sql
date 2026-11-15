-- Multi-touch attribution: one row per (order, touchpoint) with the credit share under six rule-based models.
-- Every model's weights sum to 1 per order, so attributed revenue always reconciles to order revenue.
{% set half_life = var('time_decay_half_life_days') %}
{% set w_first = var('position_based_first_weight') %}
{% set w_last = var('position_based_last_weight') %}
with t as (
    select
        *,
        power(0.5, days_before_conversion / {{ half_life }})  as decay_raw,
        max(case when channel <> 'Direct' then touch_number end)
            over (partition by order_id)                       as last_non_direct_number
    from {{ ref('int_attribution_touchpoints') }}
),
weights as (
    select
        *,
        case when touch_number = 1 then 1.0 else 0.0 end                         as w_first_touch,
        case when touch_number = touch_count then 1.0 else 0.0 end               as w_last_touch,
        case when touch_number = coalesce(last_non_direct_number, touch_count)
             then 1.0 else 0.0 end                                               as w_last_non_direct,
        1.0 / touch_count                                                        as w_linear,
        decay_raw / sum(decay_raw) over (partition by order_id)                  as w_time_decay,
        case
            when touch_count = 1 then 1.0
            when touch_count = 2 then 0.5
            when touch_number = 1 then {{ w_first }}
            when touch_number = touch_count then {{ w_last }}
            else (1.0 - {{ w_first }} - {{ w_last }}) / (touch_count - 2)
        end                                                                      as w_position_based
    from t
)
select
    touchpoint_id, order_id, customer_key, order_ts, net_revenue,
    session_id, touch_ts, channel, platform, campaign, is_synthetic,
    touch_number, touch_count, days_before_conversion,
    w_first_touch, w_last_touch, w_last_non_direct, w_linear, w_time_decay, w_position_based,
    w_first_touch      * net_revenue as rev_first_touch,
    w_last_touch       * net_revenue as rev_last_touch,
    w_last_non_direct  * net_revenue as rev_last_non_direct,
    w_linear           * net_revenue as rev_linear,
    w_time_decay       * net_revenue as rev_time_decay,
    w_position_based   * net_revenue as rev_position_based
from weights
