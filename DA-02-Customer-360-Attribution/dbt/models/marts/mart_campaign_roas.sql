-- Paid campaign ROAS under each attribution model (campaign names match utm_campaign on sessions).
with spend as (
    select platform, campaign_name, channel, sum(spend) as spend, sum(clicks) as clicks, sum(impressions) as impressions
    from {{ ref('stg_ads__spend') }}
    group by 1, 2, 3
),
attributed as (
    select campaign, attribution_model, sum(credit) as attributed_conversions, sum(attributed_revenue) as attributed_revenue
    from {{ ref('fct_attribution_long') }}
    where campaign is not null
    group by 1, 2
),
models as (select distinct attribution_model from {{ ref('fct_attribution_long') }})
select
    s.platform, s.campaign_name, s.channel, m.attribution_model,
    s.impressions, s.clicks, s.spend,
    coalesce(a.attributed_conversions, 0)         as attributed_conversions,
    coalesce(a.attributed_revenue, 0)             as attributed_revenue,
    coalesce(a.attributed_revenue, 0) / nullif(s.spend, 0) as roas,
    s.spend / nullif(a.attributed_conversions, 0) as cost_per_conversion
from spend s
cross join models m
left join attributed a on s.campaign_name = a.campaign and m.attribution_model = a.attribution_model
