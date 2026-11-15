with source as (
    select * from {{ source('raw', 'segment_identifies') }}
)
select
    cast(id as {{ dbt.type_string() }})            as identify_id,
    cast(anonymous_id as {{ dbt.type_string() }})  as device_id,
    {{ nullif_blank('user_id') }}                    as user_id,
    lower(trim(email))                               as email,
    cast({{ adapter.quote('timestamp') }} as {{ dbt.type_timestamp() }}) as identified_at
from source
where {{ nullif_blank('user_id') }} is not null
