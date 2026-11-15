"""
Retail and Supply Chain Control Tower - What-If Scenario Analysis
Simulates supply chain disruptions, specifically the mandatory scenario:
"What happens if a supplier is delayed by 7 days?"
Calculates cascading impacts on expected arrival dates, inventory buffer depletion,
stock-out vulnerabilities, and projected unit shortages.
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("WhatIfAnalysis")

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


def list_top_suppliers(engine, limit=10):
    """
    List candidate suppliers with highest shipment volumes and dependent SKUs.
    """
    query = f"""
    SET search_path TO control_tower, public;
    SELECT
        s.supplier_id,
        s.supplier_name,
        s.city,
        s.state,
        COUNT(DISTINCT shp.shipment_id) AS total_shipments,
        COUNT(DISTINCT sp.product_id) AS active_products_supplied,
        s.average_lead_time,
        s.supplier_performance
    FROM suppliers s
    JOIN shipments shp ON s.supplier_id = shp.supplier_id
    LEFT JOIN supplier_products sp ON s.supplier_id = sp.supplier_id
    GROUP BY s.supplier_id, s.supplier_name, s.city, s.state, s.average_lead_time, s.supplier_performance
    ORDER BY total_shipments DESC
    LIMIT {limit};
    """
    return pd.read_sql(text(query), engine.connect())


def simulate_supplier_delay(engine, supplier_id=None, delay_days=7):
    """
    Mandatory Scenario Simulation:
    Applies an additional 7-day logistics delay to pending or recent shipments
    for a chosen supplier and evaluates buffer stock depletion across dependent SKUs.
    """
    logger.info(f"Initiating What-If simulation: Injecting {delay_days}-day delay...")

    # If supplier not specified, pick top supplier
    if supplier_id is None:
        top_supp = list_top_suppliers(engine, limit=1)
        if top_supp.empty:
            logger.error("No suppliers found in database.")
            return None
        supplier_id = top_supp.iloc[0]["supplier_id"]
        supplier_name = top_supp.iloc[0]["supplier_name"]
    else:
        s_query = f"SELECT supplier_name FROM control_tower.suppliers WHERE supplier_id = '{supplier_id}';"
        s_res = engine.connect().execute(text(s_query)).fetchone()
        supplier_name = s_res[0] if s_res else f"Supplier-{supplier_id[:8]}"

    logger.info(f"Selected Supplier: {supplier_name} ({supplier_id})")

    # 1. Fetch shipments for this supplier
    shipment_query = f"""
    SET search_path TO control_tower, public;
    SELECT
        shipment_id,
        product_id,
        expected_delivery_date,
        actual_delivery_date,
        shipment_status
    FROM shipments
    WHERE supplier_id = '{supplier_id}'
    ORDER BY expected_delivery_date DESC
    LIMIT 20;
    """
    shipments_df = pd.read_sql(text(shipment_query), engine.connect())

    # 2. Fetch inventory and daily demand for dependent products
    prod_ids = shipments_df["product_id"].unique()
    if len(prod_ids) == 0:
        logger.warning(f"No shipments found for supplier {supplier_id}")
        return None

    prod_list_str = "'" + "','".join(prod_ids) + "'"

    inv_query = f"""
    SET search_path TO control_tower, public;
    WITH current_stock AS (
        SELECT product_id, SUM(available_stock) AS on_hand_stock
        FROM (
            SELECT DISTINCT ON (product_id, warehouse_id) product_id, available_stock
            FROM inventory_snapshots
            WHERE product_id IN ({prod_list_str})
            ORDER BY product_id, warehouse_id, stock_update_timestamp DESC
        ) sub
        GROUP BY product_id
    ),
    demand AS (
        SELECT product_id, ROUND(SUM(quantity_sold)::NUMERIC / 30.0, 2) AS daily_demand
        FROM sales
        WHERE product_id IN ({prod_list_str})
          AND sales_date >= (SELECT MAX(sales_date) - INTERVAL '30 days' FROM sales)
        GROUP BY product_id
    )
    SELECT
        p.product_id,
        p.product_name,
        p.category_name,
        COALESCE(cs.on_hand_stock, 15) AS on_hand_stock,
        COALESCE(d.daily_demand, 1.2) AS avg_daily_demand
    FROM products p
    LEFT JOIN current_stock cs ON p.product_id = cs.product_id
    LEFT JOIN demand d ON p.product_id = d.product_id
    WHERE p.product_id IN ({prod_list_str});
    """
    product_stats = pd.read_sql(text(inv_query), engine.connect())

    # 3. Simulate 7-day delay and evaluate depletion
    impact_records = []
    affected_products_list = []
    expected_shortage_map = {}

    for _, row in product_stats.iterrows():
        sku = row["product_id"]
        stock = float(row["on_hand_stock"])
        daily_d = max(0.2, float(row["avg_daily_demand"]))

        # Base days of inventory
        doi = round(stock / daily_d, 1)

        # Additional demand accrued during 7-day supplier delay
        additional_demand = round(daily_d * delay_days, 1)
        simulated_balance = round(stock - additional_demand, 1)
        is_stockout = simulated_balance <= 0
        shortage_units = round(abs(min(0.0, simulated_balance)), 1)

        impact_records.append({
            "product_id": sku[:8] + "...",
            "product_name": row["product_name"][:25],
            "category": row["category_name"][:18],
            "current_stock": int(stock),
            "daily_demand": daily_d,
            "baseline_doi": doi,
            "delay_period_demand": additional_demand,
            "simulated_ending_stock": simulated_balance,
            "stockout_risk": "HIGH RISK [STOCK-OUT]" if is_stockout else "SAFE BUFFER",
            "shortage_units": shortage_units
        })

        if is_stockout:
            affected_products_list.append(sku)
            expected_shortage_map[sku] = shortage_units

    impact_df = pd.DataFrame(impact_records)

    # 4. Store simulation results in control_tower.what_if_scenarios
    scenario_payload = {
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "additional_delay_days": delay_days,
        "simulated_at": datetime.now(timezone.utc),
        "affected_products": json.dumps(affected_products_list),
        "expected_shortage": json.dumps(expected_shortage_map),
        "scenario_status": "SIMULATED"
    }

    insert_sql = """
    SET search_path TO control_tower, public;
    INSERT INTO what_if_scenarios (
        supplier_id,
        additional_delay_days,
        simulated_at,
        affected_products,
        expected_shortage,
        scenario_status
    ) VALUES (
        :supplier_id, :additional_delay_days, :simulated_at,
        CAST(:affected_products AS JSONB), CAST(:expected_shortage AS JSONB), :scenario_status
    );
    """
    with engine.begin() as conn:
        conn.execute(text(insert_sql), scenario_payload)

    logger.info("What-If simulation scenario persisted to database.")

    return {
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "delay_days": delay_days,
        "impact_df": impact_df,
        "total_affected_skus": len(affected_products_list),
        "total_shortage_units": sum(expected_shortage_map.values())
    }


def print_simulation_report(sim_result):
    """Render formatted What-If scenario impact assessment."""
    if not sim_result:
        return

    print("\n" + "=" * 75)
    print("WHAT-IF SCENARIO SIMULATION REPORT [SIMULATED EXPERIMENT]")
    print("=" * 75)
    print(f"Target Supplier: {sim_result['supplier_name']} ({sim_result['supplier_id']})")
    print(f"Simulated Shock: Additional {sim_result['delay_days']}-Day Inbound Delivery Delay")
    print(f"Products at Risk: {sim_result['total_affected_skus']} SKUs")
    print(f"Estimated Stock Shortage: {sim_result['total_shortage_units']:.1f} Units")
    print("-" * 75)
    print(sim_result["impact_df"].to_string(index=False))
    print("=" * 75 + "\n")


if __name__ == "__main__":
    eng = get_db_engine()
    res = simulate_supplier_delay(eng, delay_days=7)
    print_simulation_report(res)
