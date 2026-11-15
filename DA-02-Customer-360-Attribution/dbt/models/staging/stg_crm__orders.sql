with source as (
    select * from {{ source('raw', 'crm_orders') }}
)
select
    order_id,
    contact_id,
    cast(order_ts as {{ dbt.type_timestamp() }})                     as order_ts,
    order_platform,
    cast(gross_revenue as {{ dbt.type_float() }})                    as gross_revenue,
    cast(coalesce(discount, 0) as {{ dbt.type_float() }})           as discount,
    cast(gross_revenue - coalesce(discount, 0) as {{ dbt.type_float() }}) as net_revenue,
    currency,
    lower(status)                                                    as status,
    lower(status) = 'completed'                                      as is_completed
from source
