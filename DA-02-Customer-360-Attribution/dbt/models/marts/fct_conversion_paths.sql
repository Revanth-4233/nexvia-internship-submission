-- One row per customer journey, the input for the data-driven (Markov chain) model in attribution/markov.py.
--   converting journeys: the ordered channels that led to each order (same window as rule-based models)
--   non-converting journeys: sessions that never led to an order (anonymous visitors included)
with converting as (
    select
        order_id                                                                    as journey_id,
        max(customer_key)                                                           as customer_key,
        {{ dbt.listagg('channel', "' > '", 'order by touch_number') }}              as path,
        max(touch_count)                                                            as path_length,
        true                                                                        as converted,
        max(net_revenue)                                                            as revenue
    from {{ ref('int_attribution_touchpoints') }}
    group by order_id
),
used_sessions as (
    select session_id from {{ ref('int_attribution_touchpoints') }} where session_id is not null
),
last_order as (
    select contact_id, max(order_ts) as last_order_ts
    from {{ ref('stg_crm__orders') }} group by contact_id
),
unconverted_sessions as (
    select
        s.customer_key, s.channel, s.session_start_ts,
        row_number() over (partition by s.customer_key order by s.session_start_ts) as touch_number
    from {{ ref('int_sessions') }} s
    left join last_order lo on s.contact_id = lo.contact_id
    where s.session_id not in (select session_id from used_sessions)
      and (lo.last_order_ts is null or s.session_start_ts > lo.last_order_ts)
),
non_converting as (
    select
        'nc_' || customer_key                                                       as journey_id,
        customer_key,
        {{ dbt.listagg('channel', "' > '", 'order by touch_number') }}              as path,
        count(*)                                                                    as path_length,
        false                                                                       as converted,
        cast(0 as {{ dbt.type_float() }})                                           as revenue
    from unconverted_sessions
    group by customer_key
)
select * from converting
union all
select * from non_converting
