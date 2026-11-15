-- Every completed order must appear in attribution.
select o.order_id
from {{ ref('stg_crm__orders') }} o
left join (select distinct order_id from {{ ref('fct_attribution') }}) a on o.order_id = a.order_id
where o.is_completed and a.order_id is null
