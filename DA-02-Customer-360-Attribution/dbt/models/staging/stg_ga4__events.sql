-- One row per GA4 web event, de-duplicated (tags sometimes double-fire) and typed.
with source as (
    select * from {{ source('raw', 'ga4_events') }}
),
typed as (
    select
        {{ micros_to_timestamp('event_timestamp') }}             as event_ts,
        event_timestamp                                           as event_timestamp_micros,
        lower(event_name)                                         as event_name,
        cast(user_pseudo_id as {{ dbt.type_string() }})          as device_id,
        {{ nullif_blank('user_id') }}                             as user_id,
        cast(ga_session_id as {{ dbt.type_string() }})           as ga_session_id,
        lower(coalesce({{ nullif_blank('traffic_source') }}, '(direct)'))  as source,
        lower(coalesce({{ nullif_blank('traffic_medium') }}, '(none)'))    as medium,
        {{ nullif_blank('traffic_campaign') }}                    as campaign,
        page_location,
        device_category,
        {{ nullif_blank('transaction_id') }}                      as transaction_id,
        cast(purchase_revenue as {{ dbt.type_float() }})          as purchase_revenue
    from source
),
deduped as (
    select
        *,
        row_number() over (
            partition by device_id, event_timestamp_micros, event_name
            order by event_timestamp_micros
        ) as _rn
    from typed
)
select
    {{ surrogate_key(['device_id', 'event_timestamp_micros', 'event_name']) }} as event_id,
    'web' as platform,
    event_ts, event_name, device_id, user_id, ga_session_id,
    source, medium, campaign, page_location, device_category,
    transaction_id, purchase_revenue
from deduped
where _rn = 1
