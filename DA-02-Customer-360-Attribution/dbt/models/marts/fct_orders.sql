with orders as (
    select * from {{ ref('stg_crm__orders') }}
),
touch_summary as (
    select
        order_id,
        max(touch_count)                                              as touches_before_order,
        max(case when touch_number = 1 then channel end)              as first_touch_channel,
        max(case when touch_number = touch_count then channel end)    as last_touch_channel,
        max(days_before_conversion)                                   as days_from_first_touch,
        max(case when is_synthetic then 1 else 0 end) = 1             as is_unattributed
    from {{ ref('int_attribution_touchpoints') }}
    group by order_id
),
sequence as (
    select
        order_id,
        row_number() over (partition by contact_id order by order_ts) as customer_order_number
    from orders
    where is_completed
)
select
    o.order_id,
    o.contact_id                         as customer_key,
    o.order_ts,
    cast(o.order_ts as date)             as order_date,
    o.order_platform,
    o.gross_revenue, o.discount, o.net_revenue, o.currency,
    o.status, o.is_completed,
    s.customer_order_number,
    s.customer_order_number = 1          as is_first_order,
    t.touches_before_order,
    t.first_touch_channel,
    t.last_touch_channel,
    t.days_from_first_touch,
    t.is_unattributed
from orders o
left join touch_summary t on o.order_id = t.order_id
left join sequence s      on o.order_id = s.order_id
