-- Identity resolution: every device (GA4 user_pseudo_id / Segment anonymous_id) -> one customer.
-- Rule: a device belongs to the FIRST user_id it was ever seen with (deterministic stitching);
-- the user_id belongs to the CRM contact that carries it. Devices never seen logged in stay anonymous,
-- so their sessions are still counted (and still feed non-converting paths), keyed 'anon_<device>'.
with device_user_pairs as (
    select device_id, user_id, event_ts as seen_at from {{ ref('stg_ga4__events') }} where user_id is not null
    union all
    select device_id, user_id, event_ts from {{ ref('stg_segment__tracks') }} where user_id is not null
    union all
    select device_id, user_id, identified_at from {{ ref('stg_segment__identifies') }}
),
first_link as (
    select device_id, user_id, first_linked_at
    from (
        select
            device_id, user_id, min(seen_at) as first_linked_at,
            row_number() over (partition by device_id order by min(seen_at), user_id) as rn
        from device_user_pairs
        group by device_id, user_id
    ) ranked
    where rn = 1
),
all_devices as (
    select device_id, min(event_ts) as first_seen_at, max(event_ts) as last_seen_at, 'web' as platform
    from {{ ref('stg_ga4__events') }} group by device_id
    union all
    select device_id, min(event_ts), max(event_ts), 'app'
    from {{ ref('stg_segment__tracks') }} group by device_id
),
contacts as (
    select contact_id, user_id from {{ ref('stg_crm__contacts') }} where user_id is not null
)
select
    d.device_id,
    d.platform,
    d.first_seen_at,
    d.last_seen_at,
    l.user_id,
    l.first_linked_at,
    c.contact_id,
    coalesce(c.contact_id, 'anon_' || d.device_id) as customer_key,
    c.contact_id is not null                         as is_identified
from all_devices d
left join first_link l on d.device_id = l.device_id
left join contacts c   on l.user_id = c.user_id
