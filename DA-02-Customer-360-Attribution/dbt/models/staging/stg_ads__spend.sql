-- Daily paid-media spend, unioned across Google Ads and Meta Ads with a channel attached.
with source as (
    select * from {{ source('raw', 'ad_spend') }}
),
mapping as (
    select * from {{ ref('ad_platform_channel') }}
)
select
    {{ surrogate_key(['s.date', 's.campaign_id']) }}       as spend_id,
    cast(s.date as date)                                    as spend_date,
    s.platform,
    s.campaign_id,
    s.campaign_name,
    m.channel,
    cast(s.impressions as {{ dbt.type_int() }})            as impressions,
    cast(s.clicks as {{ dbt.type_int() }})                 as clicks,
    cast(s.spend as {{ dbt.type_float() }})                as spend,
    s.currency
from source s
left join mapping m
    on s.platform = m.platform
   and {{ dbt.position("m.campaign_prefix", "s.campaign_name") }} = 1
