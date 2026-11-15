-- Attributed revenue per model must equal completed-order revenue from the CRM (finance source of truth).
with finance as (
    select sum(net_revenue) as revenue from {{ ref('stg_crm__orders') }} where is_completed
),
attributed as (
    select attribution_model, sum(attributed_revenue) as revenue
    from {{ ref('fct_attribution_long') }} group by attribution_model
)
select a.attribution_model, a.revenue, f.revenue as finance_revenue
from attributed a cross join finance f
where abs(a.revenue - f.revenue) > 0.01
