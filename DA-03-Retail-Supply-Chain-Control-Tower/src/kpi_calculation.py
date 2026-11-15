"""
Retail and Supply Chain Control Tower - KPI Calculation Engine
Calculates the 4 mandatory supply chain metrics:
1. Stock-out Rate (%)
2. On-Time Delivery Rate (%)
3. Supplier Lead Time (Days)
4. Days of Inventory (DOI)
"""

import os
import logging
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("KPICalculation")

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


def calculate_stock_out_rate(engine=None, days_window=30):
    """
    KPI A: Stock-Out Rate (%)
    Formula: (Products with 0 stock where demand exists) / (Total active products with demand) * 100
    """
    logger.info("Computing Stock-Out Rate KPI...")
    query = f"""
    SET search_path TO control_tower, public;
    WITH latest_inventory AS (
        SELECT DISTINCT ON (product_id)
            product_id,
            available_stock,
            reorder_level
        FROM inventory_snapshots
        ORDER BY product_id, stock_update_timestamp DESC
    ),
    active_demand AS (
        SELECT DISTINCT product_id
        FROM sales
        WHERE sales_date >= (SELECT MAX(sales_date) - INTERVAL '{days_window} days' FROM sales)
    )
    SELECT
        COUNT(CASE WHEN li.available_stock = 0 THEN 1 END) AS stockout_count,
        COUNT(*) AS total_demand_skus,
        ROUND(
            (COUNT(CASE WHEN li.available_stock = 0 THEN 1 END)::NUMERIC / NULLIF(COUNT(*), 0)) * 100.0,
            2
        ) AS stock_out_rate_pct
    FROM active_demand ad
    JOIN latest_inventory li ON ad.product_id = li.product_id;
    """
    if engine:
        with engine.connect() as conn:
            result = conn.execute(text(query)).fetchone()
            rate = float(result[2]) if result and result[2] is not None else 0.0
            stockout_count = int(result[0]) if result else 0
            total_count = int(result[1]) if result else 0
            return {
                "metric_name": "Stock-out Rate",
                "value": rate,
                "unit": "%",
                "stockout_skus": stockout_count,
                "total_active_skus": total_count,
                "benchmark": "< 10.0%"
            }
    else:
        return {"metric_name": "Stock-out Rate", "value": 14.2, "unit": "%", "benchmark": "< 10.0%"}


def calculate_on_time_delivery_rate(engine=None):
    """
    KPI B: On-Time Delivery Rate (%)
    Formula: (Delivered shipments on/before expected date) / (Total delivered shipments) * 100
    """
    logger.info("Computing On-Time Delivery Rate KPI...")
    query = """
    SET search_path TO control_tower, public;
    SELECT
        COUNT(CASE WHEN actual_delivery_date <= expected_delivery_date THEN 1 END) AS on_time_count,
        COUNT(*) AS total_delivered_count,
        ROUND(
            (COUNT(CASE WHEN actual_delivery_date <= expected_delivery_date THEN 1 END)::NUMERIC / NULLIF(COUNT(*), 0)) * 100.0,
            2
        ) AS on_time_delivery_rate_pct
    FROM shipments
    WHERE actual_delivery_date IS NOT NULL;
    """
    if engine:
        with engine.connect() as conn:
            result = conn.execute(text(query)).fetchone()
            rate = float(result[2]) if result and result[2] is not None else 0.0
            on_time = int(result[0]) if result else 0
            total = int(result[1]) if result else 0
            return {
                "metric_name": "On-time Delivery Rate",
                "value": rate,
                "unit": "%",
                "on_time_shipments": on_time,
                "total_delivered_shipments": total,
                "benchmark": "> 90.0%"
            }
    else:
        return {"metric_name": "On-time Delivery Rate", "value": 91.8, "unit": "%", "benchmark": "> 90.0%"}


def calculate_supplier_lead_time(engine=None):
    """
    KPI C: Average Supplier Lead Time (Days)
    Formula: AVG(actual_delivery_date - shipment_date) in days across shipments
    """
    logger.info("Computing Supplier Lead Time KPI...")
    query = """
    SET search_path TO control_tower, public;
    SELECT
        ROUND(AVG(EXTRACT(EPOCH FROM (actual_delivery_date - shipment_date)) / 86400)::NUMERIC, 2) AS avg_lead_time_days,
        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (actual_delivery_date - shipment_date)) / 86400)::NUMERIC, 2) AS median_lead_time_days,
        COUNT(*) AS total_eval_shipments
    FROM shipments
    WHERE actual_delivery_date IS NOT NULL AND actual_delivery_date >= shipment_date;
    """
    if engine:
        with engine.connect() as conn:
            result = conn.execute(text(query)).fetchone()
            avg_lead = float(result[0]) if result and result[0] is not None else 0.0
            med_lead = float(result[1]) if result and result[1] is not None else 0.0
            return {
                "metric_name": "Supplier Lead Time",
                "value": avg_lead,
                "median_value": med_lead,
                "unit": "Days",
                "benchmark": "7 - 15 Days"
            }
    else:
        return {"metric_name": "Supplier Lead Time", "value": 12.4, "median_value": 10.5, "unit": "Days", "benchmark": "7 - 15 Days"}


def calculate_days_of_inventory(engine=None, days_window=30):
    """
    KPI D: Days of Inventory (DOI)
    Formula: Total On-Hand Inventory / Average Daily Sales Demand (trailing 30 days)
    """
    logger.info("Computing Days of Inventory (DOI) KPI...")
    query = f"""
    SET search_path TO control_tower, public;
    WITH latest_inventory AS (
        SELECT SUM(available_stock) AS total_on_hand_units
        FROM (
            SELECT DISTINCT ON (product_id, warehouse_id)
                product_id, warehouse_id, available_stock
            FROM inventory_snapshots
            ORDER BY product_id, warehouse_id, stock_update_timestamp DESC
        ) sub
    ),
    daily_sales AS (
        SELECT (SUM(quantity_sold)::NUMERIC / {days_window}.0) AS avg_daily_demand_units
        FROM sales
        WHERE sales_date >= (SELECT MAX(sales_date) - INTERVAL '{days_window} days' FROM sales)
    )
    SELECT
        li.total_on_hand_units,
        ROUND(ds.avg_daily_demand_units, 2) AS avg_daily_demand,
        ROUND((li.total_on_hand_units / NULLIF(ds.avg_daily_demand_units, 0))::NUMERIC, 2) AS days_of_inventory
    FROM latest_inventory li, daily_sales ds;
    """
    if engine:
        with engine.connect() as conn:
            result = conn.execute(text(query)).fetchone()
            doi = float(result[2]) if result and result[2] is not None else 0.0
            stock = int(result[0]) if result and result[0] is not None else 0
            daily_demand = float(result[1]) if result and result[1] is not None else 0.0
            return {
                "metric_name": "Days of Inventory",
                "value": doi,
                "total_stock_units": stock,
                "avg_daily_demand_units": daily_demand,
                "unit": "Days",
                "benchmark": "14 - 30 Days"
            }
    else:
        return {"metric_name": "Days of Inventory", "value": 18.6, "unit": "Days", "benchmark": "14 - 30 Days"}


def calculate_all_kpis(engine=None, save_snapshot=True):
    """Execute all four mandatory KPIs and persist snapshot to database."""
    kpi_a = calculate_stock_out_rate(engine)
    kpi_b = calculate_on_time_delivery_rate(engine)
    kpi_c = calculate_supplier_lead_time(engine)
    kpi_d = calculate_days_of_inventory(engine)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kpis": {
            "stock_out_rate": kpi_a,
            "on_time_delivery_rate": kpi_b,
            "supplier_lead_time": kpi_c,
            "days_of_inventory": kpi_d,
        }
    }

    if engine and save_snapshot:
        logger.info("Persisting KPI snapshot to control_tower.kpi_snapshots...")
        insert_sql = """
        SET search_path TO control_tower, public;
        INSERT INTO kpi_snapshots (
            calculation_timestamp,
            stock_out_rate,
            on_time_delivery_rate,
            average_supplier_lead_time,
            days_of_inventory
        ) VALUES (
            :ts, :stockout, :ontime, :leadtime, :doi
        );
        """
        with engine.begin() as conn:
            conn.execute(
                text(insert_sql),
                {
                    "ts": datetime.now(timezone.utc),
                    "stockout": kpi_a["value"],
                    "ontime": kpi_b["value"],
                    "leadtime": kpi_c["value"],
                    "doi": kpi_d["value"]
                }
            )
        logger.info("KPI snapshot saved successfully.")

    return report


def print_kpi_dashboard(report):
    """Render formatted console KPI dashboard."""
    print("\n" + "=" * 70)
    print("RETAIL & SUPPLY CHAIN CONTROL TOWER - EXECUTIVE KPI DASHBOARD")
    print("=" * 70)
    print(f"Timestamp: {report['timestamp']}")
    print("-" * 70)
    print(f"{'Metric':<30} | {'Value':<12} | {'Target Benchmark':<18} | Status")
    print("-" * 70)

    kpis = report["kpis"]
    # Metric 1: Stockout
    v = kpis["stock_out_rate"]["value"]
    status = "[WARN]" if v > 10.0 else "[OK]"
    print(f"{kpis['stock_out_rate']['metric_name']:<30} | {v:>6.2f} %     | {kpis['stock_out_rate']['benchmark']:<18} | {status}")

    # Metric 2: On-time delivery
    v = kpis["on_time_delivery_rate"]["value"]
    status = "[OK]" if v >= 90.0 else "[WARN]"
    print(f"{kpis['on_time_delivery_rate']['metric_name']:<30} | {v:>6.2f} %     | {kpis['on_time_delivery_rate']['benchmark']:<18} | {status}")

    # Metric 3: Lead time
    v = kpis["supplier_lead_time"]["value"]
    status = "[OK]" if 7 <= v <= 15 else "[WARN]"
    print(f"{kpis['supplier_lead_time']['metric_name']:<30} | {v:>6.2f} Days  | {kpis['supplier_lead_time']['benchmark']:<18} | {status}")

    # Metric 4: Days of Inventory
    v = kpis["days_of_inventory"]["value"]
    status = "[OK]" if 14 <= v <= 30 else "[WARN]"
    print(f"{kpis['days_of_inventory']['metric_name']:<30} | {v:>6.2f} Days  | {kpis['days_of_inventory']['benchmark']:<18} | {status}")

    print("=" * 70 + "\n")


if __name__ == "__main__":
    try:
        eng = get_db_engine()
        rep = calculate_all_kpis(eng)
        print_kpi_dashboard(rep)
    except Exception as exc:
        logger.error(f"Failed to run DB KPI calculation: {exc}")
        logger.info("Displaying benchmark reference KPI snapshot:")
        rep = calculate_all_kpis(None, save_snapshot=False)
        print_kpi_dashboard(rep)
