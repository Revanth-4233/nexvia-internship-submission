-- One row per mobile app event from Segment.
with source as (
    select * from {{ source('raw', 'segment_tracks') }}
)
select
    cast(id as {{ dbt.type_string() }})                         as event_id,
    'app'                                                         as platform,
    cast({{ adapter.quote('timestamp') }} as {{ dbt.type_timestamp() }})             as event_ts,
    lower(replace(event, ' ', '_'))                               as event_name,
    cast(anonymous_id as {{ dbt.type_string() }})               as device_id,
    {{ nullif_blank('user_id') }}                                 as user_id,
    lower({{ nullif_blank('context_campaign_source') }})          as source,
    lower({{ nullif_blank('context_campaign_medium') }})          as medium,
    {{ nullif_blank('context_campaign_name') }}                   as campaign,
    context_device_type                                           as device_category,
    {{ nullif_blank('order_id') }}                                as order_id,
    cast(revenue as {{ dbt.type_float() }})                       as revenue
from source
