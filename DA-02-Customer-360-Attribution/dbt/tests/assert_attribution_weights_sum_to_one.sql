-- Every attribution model must hand out exactly 100% of the credit for each order.
select order_id,
       sum(w_first_touch) as ft, sum(w_last_touch) as lt, sum(w_last_non_direct) as lnd,
       sum(w_linear) as lin, sum(w_time_decay) as td, sum(w_position_based) as pb
from {{ ref('fct_attribution') }}
group by order_id
having abs(sum(w_first_touch) - 1) > 1e-6 or abs(sum(w_last_touch) - 1) > 1e-6
    or abs(sum(w_last_non_direct) - 1) > 1e-6 or abs(sum(w_linear) - 1) > 1e-6
    or abs(sum(w_time_decay) - 1) > 1e-6 or abs(sum(w_position_based) - 1) > 1e-6
