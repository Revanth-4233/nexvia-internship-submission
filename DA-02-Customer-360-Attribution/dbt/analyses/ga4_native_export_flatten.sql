-- How to point stg_ga4__events at a REAL GA4 BigQuery export (analytics_<property_id>.events_*).
-- The GA4 export is nested; this query flattens it to exactly the columns raw.ga4_events uses,
-- so every downstream model works unchanged. Create it as a view named raw.ga4_events.
select
    event_date,
    event_timestamp,
    event_name,
    user_pseudo_id,
    user_id,
    (select value.int_value from unnest(event_params) where key = 'ga_session_id')         as ga_session_id,
    coalesce(collected_traffic_source.manual_source, traffic_source.source)                 as traffic_source,
    coalesce(collected_traffic_source.manual_medium, traffic_source.medium)                 as traffic_medium,
    coalesce(collected_traffic_source.manual_campaign_name, traffic_source.name)            as traffic_campaign,
    (select value.string_value from unnest(event_params) where key = 'page_location')       as page_location,
    device.category                                                                          as device_category,
    ecommerce.transaction_id                                                                 as transaction_id,
    ecommerce.purchase_revenue                                                               as purchase_revenue
from `{{ env_var('GCP_PROJECT', 'my-project') }}.analytics_123456789.events_*`
where _table_suffix between '20260101' and format_date('%Y%m%d', current_date())
