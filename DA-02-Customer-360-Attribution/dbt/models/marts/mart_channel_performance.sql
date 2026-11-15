-- Channel x month x attribution model: spend, sessions, attributed conversions & revenue, ROAS, CPA.
-- This is the table that answers "which marketing channels actually bring revenue?".
with attributed as (
    select
        cast({{ dbt.date_trunc('month', 'order_ts') }} as date)  as month,
        channel,
        attribution_model,
        sum(credit)               as attributed_conversions,
        sum(attributed_revenue)   as attributed_revenue
    from {{ ref('fct_attribution_long') }}
    group by 1, 2, 3
),
spend as (
    select
        cast({{ dbt.date_trunc('month', 'spend_date') }} as date) as month,
        channel,
        sum(spend) as spend, sum(impressions) as impressions, sum(clicks) as clicks
    from {{ ref('stg_ads__spend') }}
    group by 1, 2
),
traffic as (
    select
        cast({{ dbt.date_trunc('month', 'session_start_ts') }} as date) as month,
        channel,
        count(*) as sessions,
        count(distinct customer_key) as visitors
    from {{ ref('int_sessions') }}
    group by 1, 2
),
models as (
    select distinct attribution_model from {{ ref('fct_attribution_long') }}
),
spine as (
    select month, channel from attributed
    {{ union_distinct() }}
    select month, channel from spend
    {{ union_distinct() }}
    select month, channel from traffic
)
select
    sp.month,
    sp.channel,
    m.attribution_model,
    coalesce(t.sessions, 0)                         as sessions,
    coalesce(t.visitors, 0)                         as visitors,
    coalesce(s.impressions, 0)                      as impressions,
    coalesce(s.clicks, 0)                           as clicks,
    coalesce(s.spend, 0)                            as spend,
    coalesce(a.attributed_conversions, 0)           as attributed_conversions,
    coalesce(a.attributed_revenue, 0)               as attributed_revenue,
    a.attributed_revenue / nullif(s.spend, 0)       as roas,
    s.spend / nullif(a.attributed_conversions, 0)   as cost_per_conversion,
    a.attributed_conversions / nullif(t.sessions, 0) as conversion_rate
from spine sp
cross join models m
left join attributed a on sp.month = a.month and sp.channel = a.channel and m.attribution_model = a.attribution_model
left join spend s      on sp.month = s.month and sp.channel = s.channel
left join traffic t    on sp.month = t.month and sp.channel = t.channel
