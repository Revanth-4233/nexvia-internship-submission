-- Spend in the channel mart must match raw ad-platform spend (counted once, not once per model).
with mart as (
    select sum(spend) as spend from {{ ref('mart_channel_performance') }} where attribution_model = 'linear'
),
raw_spend as (
    select sum(spend) as spend from {{ source('raw', 'ad_spend') }}
)
select * from mart cross join raw_spend r where abs(mart.spend - r.spend) > 0.01
