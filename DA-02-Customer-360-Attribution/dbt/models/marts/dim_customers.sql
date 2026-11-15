-- Customer 360: one row per known customer (CRM contact) combining CRM profile, web + app behaviour,
-- orders and marketing journey, plus RFM segmentation.
{% set as_of = "cast('" ~ var('as_of_date', '2026-09-30') ~ "' as date)" %}
with contacts as (
    select * from {{ ref('stg_crm__contacts') }}
),
devices as (
    select
        contact_id,
        sum(case when platform = 'web' then 1 else 0 end) as web_devices,
        sum(case when platform = 'app' then 1 else 0 end) as app_devices
    from {{ ref('int_identity_graph') }}
    where contact_id is not null
    group by contact_id
),
sessions as (
    select
        contact_id,
        count(*)                                                     as total_sessions,
        sum(case when platform = 'web' then 1 else 0 end)           as web_sessions,
        sum(case when platform = 'app' then 1 else 0 end)           as app_sessions,
        sum(page_views)                                              as total_page_views,
        min(session_start_ts)                                        as first_seen_at,
        max(session_start_ts)                                        as last_seen_at,
        count(distinct channel)                                      as channels_touched
    from {{ ref('int_sessions') }}
    where contact_id is not null
    group by contact_id
),
first_last_channel as (
    select
        contact_id,
        max(case when rn_first = 1 then channel end) as acquisition_channel,
        max(case when rn_last = 1 then channel end)  as latest_channel
    from (
        select
            contact_id, channel,
            row_number() over (partition by contact_id order by session_start_ts) as rn_first,
            row_number() over (partition by contact_id order by session_start_ts desc) as rn_last
        from {{ ref('int_sessions') }}
        where contact_id is not null
    ) x
    group by contact_id
),
orders as (
    select
        customer_key                                                       as contact_id,
        sum(case when is_completed then 1 else 0 end)                      as completed_orders,
        sum(case when status = 'refunded' then 1 else 0 end)               as refunded_orders,
        sum(case when is_completed then net_revenue else 0 end)            as lifetime_revenue,
        min(case when is_completed then order_ts end)                      as first_order_at,
        max(case when is_completed then order_ts end)                      as last_order_at
    from {{ ref('fct_orders') }}
    group by customer_key
),
base as (
    select
        c.contact_id                                     as customer_key,
        c.contact_id,
        c.user_id,
        c.email,
        c.first_name,
        c.last_name,
        c.first_name || ' ' || c.last_name               as full_name,
        c.phone, c.city, c.state, c.country,
        c.created_at                                     as crm_created_at,
        c.lead_source,
        c.marketing_opt_in,
        coalesce(d.web_devices, 0)                       as web_devices,
        coalesce(d.app_devices, 0)                       as app_devices,
        coalesce(s.total_sessions, 0)                    as total_sessions,
        coalesce(s.web_sessions, 0)                      as web_sessions,
        coalesce(s.app_sessions, 0)                      as app_sessions,
        coalesce(s.total_page_views, 0)                  as total_page_views,
        coalesce(s.channels_touched, 0)                  as channels_touched,
        s.first_seen_at,
        s.last_seen_at,
        coalesce(f.acquisition_channel, c.lead_source)   as acquisition_channel,
        f.latest_channel,
        coalesce(o.completed_orders, 0)                  as completed_orders,
        coalesce(o.refunded_orders, 0)                   as refunded_orders,
        coalesce(o.lifetime_revenue, 0)                  as lifetime_revenue,
        o.lifetime_revenue / nullif(o.completed_orders, 0) as avg_order_value,
        o.first_order_at,
        o.last_order_at,
        {{ dbt.datediff('cast(o.last_order_at as date)', as_of, 'day') }} as days_since_last_order
    from contacts c
    left join devices d            on c.contact_id = d.contact_id
    left join sessions s           on c.contact_id = s.contact_id
    left join first_last_channel f on c.contact_id = f.contact_id
    left join orders o             on c.contact_id = o.contact_id
),
rfm as (
    select
        customer_key,
        ntile(5) over (order by days_since_last_order desc) as r_score,
        ntile(5) over (order by completed_orders)            as f_score,
        ntile(5) over (order by lifetime_revenue)            as m_score
    from base
    where completed_orders > 0
)
select
    b.*,
    case
        when b.completed_orders = 0 and b.total_sessions = 0 then 'Offline lead'
        when b.completed_orders = 0 then 'Prospect'
        else 'Customer'
    end                                                        as lifecycle_stage,
    r.r_score, r.f_score, r.m_score,
    case
        when r.customer_key is null then null
        when r.r_score >= 4 and r.f_score >= 4                 then 'Champions'
        when r.r_score >= 3 and r.f_score >= 3                 then 'Loyal'
        when r.r_score >= 4 and r.f_score <= 2                 then 'New / Promising'
        when r.r_score <= 2 and r.m_score >= 4                 then 'At risk - high value'
        when r.r_score <= 2                                    then 'Hibernating'
        else 'Needs attention'
    end                                                        as rfm_segment
from base b
left join rfm r on b.customer_key = r.customer_key
