"""Load the raw CSVs into BigQuery (dataset `raw`).

Requires: pip install google-cloud-bigquery, and `gcloud auth application-default login`
(or GOOGLE_APPLICATION_CREDENTIALS pointing to a service-account key).

    python scripts/load_bigquery.py --project my-gcp-project --dataset raw --location asia-south1
"""
import argparse, glob, os
from google.cloud import bigquery

SCHEMAS = {
    "ga4_events": [("event_date", "STRING"), ("event_timestamp", "INT64"), ("event_name", "STRING"),
                   ("user_pseudo_id", "STRING"), ("user_id", "STRING"), ("ga_session_id", "INT64"),
                   ("traffic_source", "STRING"), ("traffic_medium", "STRING"), ("traffic_campaign", "STRING"),
                   ("page_location", "STRING"), ("device_category", "STRING"), ("transaction_id", "STRING"),
                   ("purchase_revenue", "FLOAT64")],
    "segment_tracks": [("id", "STRING"), ("anonymous_id", "STRING"), ("user_id", "STRING"), ("event", "STRING"),
                       ("timestamp", "TIMESTAMP"), ("context_campaign_source", "STRING"),
                       ("context_campaign_medium", "STRING"), ("context_campaign_name", "STRING"),
                       ("context_device_type", "STRING"), ("order_id", "STRING"), ("revenue", "FLOAT64")],
    "segment_identifies": [("id", "STRING"), ("anonymous_id", "STRING"), ("user_id", "STRING"),
                           ("email", "STRING"), ("timestamp", "TIMESTAMP")],
    "crm_contacts": [("contact_id", "STRING"), ("app_user_id", "STRING"), ("email", "STRING"),
                     ("first_name", "STRING"), ("last_name", "STRING"), ("phone", "STRING"), ("city", "STRING"),
                     ("state", "STRING"), ("country", "STRING"), ("created_at", "TIMESTAMP"),
                     ("lead_source", "STRING"), ("lifecycle_stage", "STRING"), ("marketing_opt_in", "BOOL")],
    "crm_orders": [("order_id", "STRING"), ("contact_id", "STRING"), ("order_ts", "TIMESTAMP"),
                   ("order_platform", "STRING"), ("gross_revenue", "FLOAT64"), ("discount", "FLOAT64"),
                   ("currency", "STRING"), ("status", "STRING")],
    "ad_spend": [("date", "DATE"), ("platform", "STRING"), ("campaign_id", "STRING"), ("campaign_name", "STRING"),
                 ("impressions", "INT64"), ("clicks", "INT64"), ("spend", "FLOAT64"), ("currency", "STRING")],
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--dataset", default="raw")
    ap.add_argument("--location", default="asia-south1")
    ap.add_argument("--data", default="data/raw")
    a = ap.parse_args()
    client = bigquery.Client(project=a.project)
    ds = bigquery.Dataset(f"{a.project}.{a.dataset}"); ds.location = a.location
    client.create_dataset(ds, exists_ok=True)
    for path in sorted(glob.glob(os.path.join(a.data, "*.csv"))):
        name = os.path.splitext(os.path.basename(path))[0]
        cfg = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV, skip_leading_rows=1,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            schema=[bigquery.SchemaField(n, t) for n, t in SCHEMAS[name]])
        with open(path, "rb") as f:
            job = client.load_table_from_file(f, f"{a.project}.{a.dataset}.{name}", job_config=cfg)
        job.result()
        print(f"{a.dataset}.{name:20s} {client.get_table(job.destination).num_rows:>8,d} rows")

if __name__ == "__main__":
    main()
