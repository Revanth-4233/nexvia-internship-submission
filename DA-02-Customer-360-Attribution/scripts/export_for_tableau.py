"""Export the mart tables to CSV (exports/) for Tableau Public / Tableau Desktop.

With BigQuery, connect Tableau straight to the analytics_marts dataset instead (Google BigQuery connector);
these CSVs are for Tableau Public, which cannot connect to a live warehouse.

    python scripts/export_for_tableau.py --db warehouse.duckdb
"""
import argparse, os
import duckdb

TABLES = ["dim_customers", "fct_orders", "fct_sessions", "fct_attribution_long",
          "mart_channel_performance", "mart_campaign_roas", "fct_conversion_paths", "markov_channel_attribution"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="warehouse.duckdb")
    ap.add_argument("--schema", default="analytics_marts")
    ap.add_argument("--out", default="exports")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    con = duckdb.connect(a.db, read_only=True)
    existing = {r[0] for r in con.execute(
        "select table_name from information_schema.tables where table_schema = ?", [a.schema]).fetchall()}
    for t in TABLES:
        if t not in existing:
            print(f"skip {t} (not built)"); continue
        path = os.path.join(a.out, f"{t}.csv")
        con.execute(f"copy (select * from {a.schema}.{t}) to '{path}' (header, delimiter ',')")
        n = con.execute(f"select count(*) from {a.schema}.{t}").fetchone()[0]
        print(f"{path:45s} {n:>8,d} rows")

if __name__ == "__main__":
    main()
