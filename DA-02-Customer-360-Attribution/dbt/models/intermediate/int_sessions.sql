-- Unified web + app sessions with marketing channel and resolved customer.
{% set timeout = var('session_timeout_minutes') %}
with web_events as (
    select
        device_id, ga_session_id, event_ts, event_name, source, medium, campaign, device_category,
        transaction_id, purchase_revenue,
        row_number() over (partition by device_id, ga_session_id order by event_ts) as event_seq
    from {{ ref('stg_ga4__events') }}
),
web_sessions as (
    select
        'web'                                                        as platform,
        device_id,
        ga_session_id                                                as native_session_id,
        min(event_ts)                                                as session_start_ts,
        max(event_ts)                                                as session_end_ts,
        max(case when event_seq = 1 then source end)                 as source,
        max(case when event_seq = 1 then medium end)                 as medium,
        max(case when event_seq = 1 then campaign end)               as campaign,
        max(case when event_seq = 1 then device_category end)        as device_category,
        sum(case when event_name = 'page_view' then 1 else 0 end)   as page_views,
        count(*)                                                     as events,
        max(case when event_name = 'add_to_cart' then 1 else 0 end) as added_to_cart,
        max(transaction_id)                                          as order_id
    from web_events
    group by device_id, ga_session_id
),
app_events as (
    select
        *,
        lag(event_ts) over (partition by device_id order by event_ts) as prev_ts
    from {{ ref('stg_segment__tracks') }}
),
app_flagged as (
    select
        *,
        case when prev_ts is null
               or {{ dbt.datediff('prev_ts', 'event_ts', 'minute') }} > {{ timeout }}
             then 1 else 0 end as is_new_session
    from app_events
),
app_numbered as (
    select
        *,
        sum(is_new_session) over (partition by device_id order by event_ts
                                  rows between unbounded preceding and current row) as session_number
    from app_flagged
),
app_seq as (
    select *, row_number() over (partition by device_id, session_number order by event_ts) as event_seq
    from app_numbered
),
app_sessions as (
    select
        'app'                                                                as platform,
        device_id,
        cast(session_number as {{ dbt.type_string() }})                     as native_session_id,
        min(event_ts)                                                        as session_start_ts,
        max(event_ts)                                                        as session_end_ts,
        coalesce(max(case when event_seq = 1 then source end), '(direct)')   as source,
        coalesce(max(case when event_seq = 1 then medium end), '(none)')     as medium,
        max(case when event_seq = 1 then campaign end)                       as campaign,
        max(case when event_seq = 1 then device_category end)                as device_category,
        sum(case when event_name = 'screen_viewed' then 1 else 0 end)       as page_views,
        count(*)                                                             as events,
        max(case when event_name = 'product_added' then 1 else 0 end)       as added_to_cart,
        max(order_id)                                                        as order_id
    from app_seq
    group by device_id, session_number
),
sessions as (
    select * from web_sessions
    union all
    select * from app_sessions
)
select
    {{ surrogate_key(['s.platform', 's.device_id', 's.native_session_id']) }} as session_id,
    s.platform,
    s.device_id,
    i.customer_key,
    i.contact_id,
    i.is_identified,
    s.session_start_ts,
    s.session_end_ts,
    {{ seconds_between('s.session_start_ts', 's.session_end_ts') }}             as session_duration_s,
    s.source,
    s.medium,
    s.campaign,
    coalesce(m.channel, 'Other')                                                as channel,
    coalesce(m.is_paid, false)                                                  as is_paid_channel,
    s.device_category,
    s.page_views,
    s.events,
    s.added_to_cart = 1                                                         as added_to_cart,
    s.order_id
from sessions s
left join {{ ref('channel_mapping') }} m
    on s.source = m.source and s.medium = m.medium
left join {{ ref('int_identity_graph') }} i
    on s.device_id = i.device_id
