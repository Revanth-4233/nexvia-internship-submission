-- Every session that happened within the look-back window before a completed order, for the same customer.
-- Orders with no tracked touch (offline, cross-device we could not stitch) get one synthetic 'Direct' touch,
-- so 100% of revenue is always attributed and totals reconcile with finance.
{% set lookback = var('attribution_lookback_days') %}
with orders as (
    select order_id, contact_id as customer_key, order_ts, net_revenue
    from {{ ref('stg_crm__orders') }}
    where is_completed
),
sessions as (
    select * from {{ ref('int_sessions') }} where is_identified
),
joined as (
    select
        o.order_id,
        o.customer_key,
        o.order_ts,
        o.net_revenue,
        s.session_id,
        s.session_start_ts                                              as touch_ts,
        s.channel,
        s.platform,
        s.campaign,
        {{ seconds_between('s.session_start_ts', 'o.order_ts') }} / 86400.0 as days_before_conversion
    from orders o
    join sessions s
      on s.customer_key = o.customer_key
     and s.session_start_ts <= o.order_ts
),
in_window as (
    select * from joined
    where days_before_conversion between 0 and {{ lookback }}
),
unattributed as (
    select
        o.order_id, o.customer_key, o.order_ts, o.net_revenue,
        cast(null as {{ dbt.type_string() }})   as session_id,
        o.order_ts                               as touch_ts,
        'Direct'                                 as channel,
        cast(null as {{ dbt.type_string() }})   as platform,
        cast(null as {{ dbt.type_string() }})   as campaign,
        cast(0 as {{ dbt.type_float() }})        as days_before_conversion
    from orders o
    where o.order_id not in (select order_id from in_window)
),
all_touches as (
    select *, false as is_synthetic from in_window
    union all
    select *, true from unattributed
)
select
    {{ surrogate_key(['order_id', 'session_id']) }}                                 as touchpoint_id,
    *,
    row_number() over (partition by order_id order by touch_ts, session_id)          as touch_number,
    count(*)     over (partition by order_id)                                        as touch_count
from all_touches
