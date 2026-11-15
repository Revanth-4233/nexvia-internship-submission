"""
Retail and Supply Chain Control Tower - Anomaly Detection Engine
Detects supply chain anomalies across 4 operational dimensions using:
1. Parametric Z-Score Analysis
2. Non-Parametric Scikit-Learn Isolation Forest
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sklearn.ensemble import IsolationForest

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("AnomalyDetection")

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


def get_db_engine():
    """Create SQLAlchemy engine using environment variables."""
    db_user = os.getenv("DB_USER", "admin")
    db_pass = os.getenv("DB_PASSWORD", "admin123")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "supply_chain_db")

    db_url = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    return create_engine(db_url, pool_pre_ping=True)


def classify_severity(z_score):
    """Assign severity grade according to absolute Z-score deviation magnitude."""
    abs_z = abs(z_score)
    if abs_z >= 4.0:
        return "CRITICAL"
    elif abs_z >= 3.0:
        return "HIGH"
    elif abs_z >= 2.5:
        return "MEDIUM"
    else:
        return "LOW"


def run_isolation_forest(data_series, contamination=0.05):
    """
    Execute Isolation Forest on 1D feature array.
    Returns boolean mask of detected anomalies (True for anomaly).
    """
    if len(data_series) < 10:
        return np.zeros(len(data_series), dtype=bool)

    X = data_series.values.reshape(-1, 1)
    iso = IsolationForest(
        contamination=contamination,
        random_state=42,
        n_estimators=100
    )
    preds = iso.fit_predict(X)
    return preds == -1


def detect_demand_spikes(engine, z_threshold=3.0):
    """
    Dimension 1: Sudden increases in product demand.
    Identifies daily SKU demand exceeding historical baseline.
    """
    logger.info("Detecting daily demand spikes (Z-Score & Isolation Forest)...")
    query = """
    SET search_path TO control_tower, public;
    SELECT
        product_id,
        DATE(sales_date) AS sale_date,
        SUM(quantity_sold) AS daily_quantity
    FROM sales
    GROUP BY product_id, DATE(sales_date)
    HAVING SUM(quantity_sold) >= 3;
    """
    df = pd.read_sql(text(query), engine.connect())
    if df.empty:
        return []

    anomalies = []
    # Group by product to evaluate relative demand spike
    for prod_id, group in df.groupby("product_id"):
        if len(group) < 7:
            continue
        vals = group["daily_quantity"].astype(float)
        mean_val = vals.mean()
        std_val = vals.std()

        if std_val == 0 or np.isnan(std_val):
            continue

        z_scores = (vals - mean_val) / std_val
        if_mask = run_isolation_forest(vals, contamination=0.03)

        for idx, (row_idx, row) in enumerate(group.iterrows()):
            z = z_scores.iloc[idx]
            is_if = if_mask[idx]
            # Flag if Z-Score threshold exceeded or Isolation Forest flags
            if (z >= z_threshold) or (is_if and z > 2.0):
                method = "CONSENSUS" if (z >= z_threshold and is_if) else ("Z_SCORE" if z >= z_threshold else "ISOLATION_FOREST")
                anomalies.append({
                    "anomaly_type": "DEMAND_SPIKE",
                    "product_id": prod_id,
                    "shipment_id": None,
                    "actual_value": round(float(row["daily_quantity"]), 2),
                    "expected_value": round(float(mean_val), 2),
                    "detection_method": method,
                    "severity": classify_severity(z),
                    "detection_timestamp": datetime.now(timezone.utc),
                    "description": f"Demand spike of {int(row['daily_quantity'])} units on {row['sale_date']} (Baseline: {mean_val:.1f}, Z: {z:.2f})"
                })
    return anomalies


def detect_delivery_delays(engine, z_threshold=3.0):
    """
    Dimension 2: Unexpected supplier delivery delays past carrier SLA.
    """
    logger.info("Detecting unexpected shipment delivery delays...")
    query = """
    SET search_path TO control_tower, public;
    SELECT
        shipment_id,
        supplier_id,
        product_id,
        expected_delivery_date,
        actual_delivery_date,
        EXTRACT(EPOCH FROM (actual_delivery_date - expected_delivery_date)) / 86400 AS delay_days
    FROM shipments
    WHERE actual_delivery_date IS NOT NULL
      AND actual_delivery_date > expected_delivery_date;
    """
    df = pd.read_sql(text(query), engine.connect())
    if df.empty:
        return []

    anomalies = []
    delays = df["delay_days"].astype(float)
    mean_delay = delays.mean()
    std_delay = delays.std()

    if std_delay > 0:
        df["z_score"] = (delays - mean_delay) / std_delay
        df["is_if"] = run_isolation_forest(delays, contamination=0.05)

        for _, row in df.iterrows():
            z = row["z_score"]
            if (z >= z_threshold) or (row["is_if"] and row["delay_days"] >= 7.0):
                method = "CONSENSUS" if (z >= z_threshold and row["is_if"]) else ("Z_SCORE" if z >= z_threshold else "ISOLATION_FOREST")
                anomalies.append({
                    "anomaly_type": "DELIVERY_DELAY",
                    "product_id": row["product_id"],
                    "shipment_id": row["shipment_id"],
                    "actual_value": round(float(row["delay_days"]), 2),
                    "expected_value": round(float(mean_delay), 2),
                    "detection_method": method,
                    "severity": classify_severity(z),
                    "detection_timestamp": datetime.now(timezone.utc),
                    "description": f"Shipment delayed by {row['delay_days']:.1f} days beyond SLA (Mean delay: {mean_delay:.1f} days, Z: {z:.2f})"
                })
    return anomalies


def detect_inventory_anomalies(engine, z_threshold=3.0):
    """
    Dimension 3: Unusual changes or sudden precipitous drops in warehouse stock levels.
    """
    logger.info("Detecting unusual inventory stock depletion anomalies...")
    query = """
    SET search_path TO control_tower, public;
    SELECT
        product_id,
        warehouse_id,
        stock_update_timestamp,
        available_stock
    FROM inventory_snapshots
    ORDER BY product_id, warehouse_id, stock_update_timestamp ASC;
    """
    df = pd.read_sql(text(query), engine.connect())
    if df.empty:
        return []

    anomalies = []
    # Calculate daily stock diff per SKU per warehouse
    df["stock_change"] = df.groupby(["product_id", "warehouse_id"])["available_stock"].diff()
    drops = df[df["stock_change"] < 0].copy()

    if len(drops) >= 20:
        mean_drop = drops["stock_change"].mean()
        std_drop = drops["stock_change"].std()
        if std_drop > 0:
            drops["z_score"] = (drops["stock_change"] - mean_drop) / std_drop
            drops["is_if"] = run_isolation_forest(drops["stock_change"].abs(), contamination=0.03)

            for _, row in drops.iterrows():
                z = abs(row["z_score"])
                if (z >= z_threshold) or (row["is_if"] and abs(row["stock_change"]) > 20):
                    method = "CONSENSUS" if (z >= z_threshold and row["is_if"]) else ("Z_SCORE" if z >= z_threshold else "ISOLATION_FOREST")
                    anomalies.append({
                        "anomaly_type": "INVENTORY_CHANGE",
                        "product_id": row["product_id"],
                        "shipment_id": None,
                        "actual_value": round(float(abs(row["stock_change"])), 2),
                        "expected_value": round(float(abs(mean_drop)), 2),
                        "detection_method": method,
                        "severity": classify_severity(z),
                        "detection_timestamp": datetime.now(timezone.utc),
                        "description": f"Sudden inventory drop of {int(abs(row['stock_change']))} units at {row['warehouse_id']} (Baseline drop: {abs(mean_drop):.1f})"
                    })
    return anomalies


def detect_lead_time_anomalies(engine, z_threshold=3.0):
    """
    Dimension 4: Abnormal supplier shipment lead times.
    """
    logger.info("Detecting abnormal supplier lead times...")
    query = """
    SET search_path TO control_tower, public;
    SELECT
        shipment_id,
        supplier_id,
        product_id,
        EXTRACT(EPOCH FROM (actual_delivery_date - shipment_date)) / 86400 AS lead_time_days
    FROM shipments
    WHERE actual_delivery_date IS NOT NULL
      AND actual_delivery_date >= shipment_date;
    """
    df = pd.read_sql(text(query), engine.connect())
    if df.empty:
        return []

    anomalies = []
    lead_times = df["lead_time_days"].astype(float)
    mean_lt = lead_times.mean()
    std_lt = lead_times.std()

    if std_lt > 0:
        df["z_score"] = (lead_times - mean_lt) / std_lt
        df["is_if"] = run_isolation_forest(lead_times, contamination=0.04)

        for _, row in df.iterrows():
            z = row["z_score"]
            if (z >= z_threshold) or (row["is_if"] and row["lead_time_days"] >= 30.0):
                method = "CONSENSUS" if (z >= z_threshold and row["is_if"]) else ("Z_SCORE" if z >= z_threshold else "ISOLATION_FOREST")
                anomalies.append({
                    "anomaly_type": "ABNORMAL_LEAD_TIME",
                    "product_id": row["product_id"],
                    "shipment_id": row["shipment_id"],
                    "actual_value": round(float(row["lead_time_days"]), 2),
                    "expected_value": round(float(mean_lt), 2),
                    "detection_method": method,
                    "severity": classify_severity(z),
                    "detection_timestamp": datetime.now(timezone.utc),
                    "description": f"Abnormal transit lead time of {row['lead_time_days']:.1f} days (Supplier avg: {mean_lt:.1f} days, Z: {z:.2f})"
                })
    return anomalies


def store_anomalies(engine, anomalies_list):
    """Insert detected anomalies list into control_tower.anomalies."""
    if not anomalies_list:
        logger.info("No anomalies detected to store.")
        return 0

    df = pd.DataFrame(anomalies_list)
    logger.info(f"Storing {len(df):,} anomaly records in database...")

    with engine.begin() as conn:
        conn.execute(text("SET search_path TO control_tower, public;"))
        df.to_sql("anomalies", conn, if_exists="append", index=False, chunksize=1000)

    logger.info("Anomalies successfully stored.")
    return len(df)


def run_full_anomaly_detection(engine=None):
    """Execute complete anomaly detection across all 4 operational dimensions."""
    print("=" * 70)
    print("RETAIL & SUPPLY CHAIN CONTROL TOWER: ANOMALY DETECTION ENGINE")
    print("=" * 70)

    if engine is None:
        engine = get_db_engine()

    all_anomalies = []
    try:
        a1 = detect_demand_spikes(engine)
        logger.info(f"Detected {len(a1):,} demand spike anomalies.")
        all_anomalies.extend(a1)
    except Exception as e:
        logger.warning(f"Demand spike detection skipped: {e}")

    try:
        a2 = detect_delivery_delays(engine)
        logger.info(f"Detected {len(a2):,} delivery delay anomalies.")
        all_anomalies.extend(a2)
    except Exception as e:
        logger.warning(f"Delivery delay detection skipped: {e}")

    try:
        a3 = detect_inventory_anomalies(engine)
        logger.info(f"Detected {len(a3):,} inventory change anomalies.")
        all_anomalies.extend(a3)
    except Exception as e:
        logger.warning(f"Inventory anomaly detection skipped: {e}")

    try:
        a4 = detect_lead_time_anomalies(engine)
        logger.info(f"Detected {len(a4):,} abnormal lead time anomalies.")
        all_anomalies.extend(a4)
    except Exception as e:
        logger.warning(f"Lead time anomaly detection skipped: {e}")

    stored_count = store_anomalies(engine, all_anomalies)

    print("\n" + "-" * 70)
    print(f"ANOMALY DETECTION SUMMARY: {stored_count:,} TOTAL ANOMALIES FLAGGED")
    print("-" * 70)
    if all_anomalies:
        summary_df = pd.DataFrame(all_anomalies)
        print(summary_df.groupby(["anomaly_type", "severity"]).size().unstack(fill_value=0))
    print("=" * 70 + "\n")
    return all_anomalies


if __name__ == "__main__":
    eng = get_db_engine()
    run_full_anomaly_detection(eng)
