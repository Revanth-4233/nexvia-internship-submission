with source as (
    select * from {{ source('raw', 'crm_contacts') }}
)
select
    contact_id,
    {{ nullif_blank('app_user_id') }}                      as user_id,
    lower(trim(email))                                     as email,       -- CRM has mixed-case emails
    trim(first_name)                                as first_name,
    trim(last_name)                                 as last_name,
    {{ nullif_blank('phone') }}                            as phone,
    city, state, country,
    cast(created_at as {{ dbt.type_timestamp() }})        as created_at,
    lead_source,
    lifecycle_stage,
    cast(marketing_opt_in as {{ dbt.type_boolean() }})    as marketing_opt_in
from source
