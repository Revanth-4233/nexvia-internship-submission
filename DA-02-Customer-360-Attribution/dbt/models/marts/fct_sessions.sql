select
    session_id, platform, device_id, customer_key, contact_id, is_identified,
    session_start_ts, session_end_ts, cast(session_start_ts as date) as session_date,
    session_duration_s, source, medium, campaign, channel, is_paid_channel,
    device_category, page_views, events, added_to_cart,
    order_id is not null as converted_in_session, order_id
from {{ ref('int_sessions') }}
