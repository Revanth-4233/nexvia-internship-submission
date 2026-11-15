"""
Retail and Supply Chain Control Tower - Inventory Analytics Engine
Provides real-time visibility into warehouse stock levels, buffer depletion,
stock-out vulnerabilities, and SKU inventory turnover.
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("InventoryAnalysis")

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


def get_current_inventory(engine):
    """
    Retrieve latest stock level per SKU and warehouse facility.
    """
    logger.info("Extracting latest warehouse inventory snapshots...")
    query = """
    SET search_path TO control_tower, public;
    SELECT DISTINCT ON (i.product_id, i.warehouse_id)
        i.product_id,
        p.product_name,
        p.category_name,
        i.warehouse_id,
        w.warehouse_name,
        w.location,
        i.available_stock,
        i.reorder_level,
        i.stock_update_timestamp
    FROM inventory_snapshots i
    JOIN products p ON i.product_id = p.product_id
    JOIN warehouses w ON i.warehouse_id = w.warehouse_id
    ORDER BY i.product_id, i.warehouse_id, i.stock_update_timestamp DESC;
    """
    return pd.read_sql(text(query), engine.connect())


def get_low_stock_products(engine, threshold_ratio=1.0):
    """
    Identify products where available stock is below or near reorder level.
    """
    logger.info("Identifying low-stock SKUs requiring replenishment...")
    query = f"""
    SET search_path TO control_tower, public;
    WITH latest_inv AS (
        SELECT DISTINCT ON (product_id, warehouse_id)
            product_id, warehouse_id, available_stock, reorder_level
        FROM inventory_snapshots
        ORDER BY product_id, warehouse_id, stock_update_timestamp DESC
    )
    SELECT
        li.product_id,
        p.product_name,
        p.category_name,
        li.warehouse_id,
        li.available_stock,
        li.reorder_level,
        (li.reorder_level - li.available_stock) AS replenishment_gap,
        ROUND((li.available_stock::NUMERIC / NULLIF(li.reorder_level, 0)) * 100.0, 1) AS stock_pct_of_reorder
    FROM latest_inv li
    JOIN products p ON li.product_id = p.product_id
    WHERE li.available_stock <= (li.reorder_level * {threshold_ratio})
    ORDER BY replenishment_gap DESC;
    """
    return pd.read_sql(text(query), engine.connect())


def get_stockout_products(engine):
    """
    Identify SKUs with 0 available stock despite active customer sales demand.
    """
    logger.info("Identifying total stock-out SKUs...")
    query = """
    SET search_path TO control_tower, public;
    WITH latest_stock AS (
        SELECT product_id, SUM(available_stock) AS total_stock
        FROM (
            SELECT DISTINCT ON (product_id, warehouse_id) product_id, available_stock
            FROM inventory_snapshots
            ORDER BY product_id, warehouse_id, stock_update_timestamp DESC
        ) sub
        GROUP BY product_id
    ),
    active_demand AS (
        SELECT product_id, SUM(quantity_sold) AS sales_30d
        FROM sales
        WHERE sales_date >= (SELECT MAX(sales_date) - INTERVAL '30 days' FROM sales)
        GROUP BY product_id
    )
    SELECT
        ls.product_id,
        p.product_name,
        p.category_name,
        ad.sales_30d,
        COALESCE(ls.total_stock, 0) AS current_stock
    FROM active_demand ad
    JOIN products p ON ad.product_id = p.product_id
    LEFT JOIN latest_stock ls ON ad.product_id = ls.product_id
    WHERE COALESCE(ls.total_stock, 0) = 0
    ORDER BY ad.sales_30d DESC;
    """
    return pd.read_sql(text(query), engine.connect())


def get_inventory_distribution(engine):
    """
    Aggregate inventory distribution across warehouses and commercial categories.
    """
    query_wh = """
    SET search_path TO control_tower, public;
    SELECT
        w.warehouse_id,
        w.warehouse_name,
        w.location,
        COUNT(DISTINCT i.product_id) AS distinct_skus,
        SUM(i.available_stock) AS total_inventory_units
    FROM warehouses w
    JOIN (
        SELECT DISTINCT ON (warehouse_id, product_id) warehouse_id, product_id, available_stock
        FROM inventory_snapshots
        ORDER BY warehouse_id, product_id, stock_update_timestamp DESC
    ) i ON w.warehouse_id = i.warehouse_id
    GROUP BY w.warehouse_id, w.warehouse_name, w.location
    ORDER BY total_inventory_units DESC;
    """
    query_cat = """
    SET search_path TO control_tower, public;
    SELECT
        p.category_name,
        COUNT(DISTINCT i.product_id) AS sku_count,
        SUM(i.available_stock) AS total_stock_units
    FROM products p
    JOIN (
        SELECT DISTINCT ON (product_id) product_id, available_stock
        FROM inventory_snapshots
        ORDER BY product_id, stock_update_timestamp DESC
    ) i ON p.product_id = i.product_id
    GROUP BY p.category_name
    ORDER BY total_stock_units DESC
    LIMIT 15;
    """
    wh_dist = pd.read_sql(text(query_wh), engine.connect())
    cat_dist = pd.read_sql(text(query_cat), engine.connect())
    return {"by_warehouse": wh_dist, "by_category": cat_dist}


def run_inventory_audit(engine=None):
    """
    Execute full operational inventory analysis report.
    """
    print("=" * 70)
    print("RETAIL & SUPPLY CHAIN CONTROL TOWER: INVENTORY AUDIT")
    print("=" * 70)

    if engine is None:
        engine = get_db_engine()

    # 1. Distribution
    dist = get_inventory_distribution(engine)
    print("\n1. REGIONAL WAREHOUSE INVENTORY DISTRIBUTION:")
    print("-" * 70)
    print(dist["by_warehouse"].to_string(index=False))

    # 2. Stockout products
    stockouts = get_stockout_products(engine)
    print(f"\n2. ACTIVE STOCKOUT PRODUCTS ({len(stockouts)} SKUs):")
    print("-" * 70)
    if not stockouts.empty:
        print(stockouts.head(10).to_string(index=False))
    else:
        print("No stockouts currently recorded.")

    # 3. Low stock below reorder level
    low_stock = get_low_stock_products(engine)
    print(f"\n3. PRODUCTS BELOW REORDER LEVEL ({len(low_stock)} SKUs):")
    print("-" * 70)
    if not low_stock.empty:
        print(low_stock.head(10).to_string(index=False))

    print("=" * 70 + "\n")


if __name__ == "__main__":
    eng = get_db_engine()
    run_inventory_audit(eng)
