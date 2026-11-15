-- No touchpoint may happen after its conversion or outside the look-back window.
select *
from {{ ref('int_attribution_touchpoints') }}
where days_before_conversion < 0
   or days_before_conversion > {{ var('attribution_lookback_days') }}
   or touch_ts > order_ts
