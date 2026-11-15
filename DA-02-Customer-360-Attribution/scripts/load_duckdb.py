"""Load the raw CSVs into a local DuckDB warehouse (schema `raw`) for development and CI.

    python scripts/load_duckdb.py --db warehouse.duckdb --data data/raw
"""
import argparse, glob, os
import duckdb

TYPES = {  # explicit types keep DuckDB and BigQuery behaviour identical
    "ga4_events": {"event_date": "VARCHAR", "event_timestamp": "BIGINT", "user_id": "VARCHAR",
                   "ga_session_id": "BIGINT", "transaction_id": "VARCHAR", "purchase_revenue": "DOUBLE"},
    "segment_tracks": {"user_id": "VARCHAR", "timestamp": "TIMESTAMP", "order_id": "VARCHAR", "revenue": "DOUBLE",
                       "context_campaign_source": "VARCHAR", "context_campaign_medium": "VARCHAR",
                       "context_campaign_name": "VARCHAR"},
    "segment_identifies": {"timestamp": "TIMESTAMP"},
    "crm_contacts": {"app_user_id": "VARCHAR", "phone": "VARCHAR", "created_at": "TIMESTAMP",
                     "marketing_opt_in": "BOOLEAN"},
    "crm_orders": {"order_ts": "TIMESTAMP"},
    "ad_spend": {"date": "DATE"},
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="warehouse.duckdb")
    ap.add_argument("--data", default="data/raw")
    a = ap.parse_args()
    con = duckdb.connect(a.db)
    con.execute("create schema if not exists raw")
    for path in sorted(glob.glob(os.path.join(a.data, "*.csv"))):
        name = os.path.splitext(os.path.basename(path))[0]
        types = TYPES.get(name, {})
        con.execute(f"create or replace table raw.{name} as select * from read_csv(?, header=true, types=?)",
                    [path, types])
        n = con.execute(f"select count(*) from raw.{name}").fetchone()[0]
        print(f"raw.{name:20s} {n:>8,d}")
    con.close()

if __name__ == "__main__":
    main()
