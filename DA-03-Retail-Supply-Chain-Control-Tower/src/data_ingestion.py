"""
Retail and Supply Chain Control Tower - Data Ingestion Engine
Loads cleaned Olist dataset into PostgreSQL and generates realistic
simulated inventory snapshots, warehouse records, and inbound shipments.
"""

import os
import uuid
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("DataIngestion")

# Base directories
BASE_DIR = Path(__file__).resolve().parents[1]
PROCESSED_DIR = BASE_DIR / "data" / "processed"
RAW_DIR = BASE_DIR / "data" / "raw"
SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"

# Load environment configuration
load_dotenv(BASE_DIR / ".env")


def get_db_engine():
    """Create SQLAlchemy engine using environment variables."""
    db_user = os.getenv("DB_USER", "admin")
    db_pass = os.getenv("DB_PASSWORD", "admin123")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "supply_chain_db")

    db_url = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    try:
        engine = create_engine(db_url, pool_pre_ping=True)
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info(f"Connected to PostgreSQL database at {db_host}:{db_port}/{db_name}")
        return engine
    except Exception as e:
        logger.error(f"PostgreSQL connection failed: {e}")
        logger.warning("Please ensure PostgreSQL is running (e.g. via docker-compose up -d)")
        raise


def init_database(engine):
    """Execute schema.sql to ensure all tables, constraints, and indexes exist."""
    logger.info("Initializing schema from database/schema.sql...")
    if not SCHEMA_PATH.exists():
        logger.error(f"Schema file not found at {SCHEMA_PATH}")
        return

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    with engine.begin() as conn:
        conn.execute(text(schema_sql))
    logger.info("Schema initialization completed successfully.")


def load_processed_file(filename, fallback_raw=None):
    """Helper to load processed CSV or raw CSV if processed does not exist."""
    path = PROCESSED_DIR / filename
    if path.exists():
        return pd.read_csv(path, low_memory=False)
    elif fallback_raw and (RAW_DIR / fallback_raw).exists():
        logger.warning(f"{filename} not found, reading from raw/{fallback_raw}")
        return pd.read_csv(RAW_DIR / fallback_raw, low_memory=False)
    else:
        raise FileNotFoundError(f"Neither {path} nor fallback exists.")


def ingest_products(engine):
    """Ingest products catalog into control_tower.products."""
    logger.info("Ingesting products...")
    df = load_processed_file("products_clean.csv", "olist_products_dataset.csv")

    category_col = "product_category_name_english" if "product_category_name_english" in df.columns else "product_category_name"
    
    # Construct commercial product name
    df["product_name"] = df[category_col].fillna("general_merchandise").str.replace("_", " ").str.title() + " (SKU-" + df["product_id"].str[:6].str.upper() + ")"
    df["category_name"] = df[category_col].fillna("unknown")
    df["source_system"] = "OLIST"
    df["created_at"] = datetime.now(timezone.utc)

    products_db = df[["product_id", "product_name", "category_name", "source_system", "created_at"]].drop_duplicates(subset=["product_id"])

    with engine.begin() as conn:
        conn.execute(text("SET search_path TO control_tower, public;"))
        products_db.to_sql("products", conn, if_exists="append", index=False, chunksize=5000)

    logger.info(f"Ingested {len(products_db):,} products.")


def ingest_suppliers(engine):
    """Ingest sellers as suppliers with derived lead times and performance scores."""
    logger.info("Ingesting suppliers...")
    sellers_df = load_processed_file("sellers_clean.csv", "olist_sellers_dataset.csv")
    orders_df = load_processed_file("orders_clean.csv", "olist_orders_dataset.csv")
    items_df = load_processed_file("order_items_clean.csv", "olist_order_items_dataset.csv")

    # Calculate actual average lead time from seller shipping limit to customer delivery
    orders_df["order_delivered_customer_date"] = pd.to_datetime(orders_df["order_delivered_customer_date"], errors="coerce")
    orders_df["order_delivered_carrier_date"] = pd.to_datetime(orders_df["order_delivered_carrier_date"], errors="coerce")
    orders_df["order_estimated_delivery_date"] = pd.to_datetime(orders_df["order_estimated_delivery_date"], errors="coerce")

    merged = items_df.merge(orders_df, on="order_id", how="inner")
    merged["lead_time_days"] = (merged["order_delivered_customer_date"] - merged["order_delivered_carrier_date"]).dt.total_seconds() / 86400.0
    merged["on_time"] = merged["order_delivered_customer_date"] <= merged["order_estimated_delivery_date"]

    seller_stats = merged.groupby("seller_id").agg(
        avg_lead_time=("lead_time_days", "mean"),
        on_time_ratio=("on_time", "mean")
    ).reset_index()

    sellers_df = sellers_df.merge(seller_stats, on="seller_id", how="left")
    
    # Fill defaults for sellers with few or missing deliveries
    sellers_df["average_lead_time"] = sellers_df["avg_lead_time"].fillna(12.5).clip(lower=2.0, upper=45.0).round(2)
    sellers_df["supplier_performance"] = (sellers_df["on_time_ratio"].fillna(0.90) * 100.0).clip(lower=50.0, upper=100.0).round(2)

    sellers_df["supplier_id"] = sellers_df["seller_id"]
    sellers_df["supplier_name"] = "Supplier " + sellers_df["seller_city"].fillna("Regional").str.title() + " " + sellers_df["seller_id"].str[:6].str.upper()
    sellers_df["city"] = sellers_df["seller_city"]
    sellers_df["state"] = sellers_df["seller_state"]
    sellers_df["created_at"] = datetime.now(timezone.utc)

    suppliers_db = sellers_df[[
        "supplier_id", "supplier_name", "city", "state",
        "average_lead_time", "supplier_performance", "created_at"
    ]].drop_duplicates(subset=["supplier_id"])

    with engine.begin() as conn:
        conn.execute(text("SET search_path TO control_tower, public;"))
        suppliers_db.to_sql("suppliers", conn, if_exists="append", index=False, chunksize=2000)

    logger.info(f"Ingested {len(suppliers_db):,} suppliers.")


def ingest_supplier_products(engine):
    """Ingest supplier-product catalog relationships."""
    logger.info("Ingesting supplier_products relationships...")
    items_df = load_processed_file("order_items_clean.csv", "olist_order_items_dataset.csv")

    sp_df = items_df[["seller_id", "product_id"]].drop_duplicates().rename(
        columns={"seller_id": "supplier_id"}
    )

    with engine.begin() as conn:
        conn.execute(text("SET search_path TO control_tower, public;"))
        sp_df.to_sql("supplier_products", conn, if_exists="append", index=False, chunksize=5000)

    logger.info(f"Ingested {len(sp_df):,} supplier-product mappings.")


def ingest_warehouses(engine):
    """Ingest standard regional distribution centers."""
    logger.info("Ingesting regional distribution center warehouses...")
    warehouses_data = [
        {"warehouse_id": "WH-SP", "warehouse_name": "São Paulo Central Distribution Center", "location": "São Paulo, SP", "is_simulated": True},
        {"warehouse_id": "WH-RJ", "warehouse_name": "Rio de Janeiro Coastal Hub", "location": "Rio de Janeiro, RJ", "is_simulated": True},
        {"warehouse_id": "WH-MG", "warehouse_name": "Belo Horizonte Logistics Hub", "location": "Minas Gerais, MG", "is_simulated": True},
        {"warehouse_id": "WH-PR", "warehouse_name": "Curitiba Southern Regional Hub", "location": "Paraná, PR", "is_simulated": True},
        {"warehouse_id": "WH-RS", "warehouse_name": "Porto Alegre Southern Facility", "location": "Rio Grande do Sul, RS", "is_simulated": True},
    ]
    df = pd.DataFrame(warehouses_data)

    with engine.begin() as conn:
        conn.execute(text("SET search_path TO control_tower, public;"))
        df.to_sql("warehouses", conn, if_exists="append", index=False)

    logger.info("Ingested 5 regional warehouses.")


def ingest_orders(engine):
    """Ingest customer orders."""
    logger.info("Ingesting orders...")
    df = load_processed_file("orders_clean.csv", "olist_orders_dataset.csv")

    cols = {
        "order_id": "order_id",
        "order_status": "order_status",
        "order_purchase_timestamp": "purchase_timestamp",
        "order_approved_at": "approved_timestamp",
        "order_delivered_carrier_date": "carrier_handover_timestamp",
        "order_delivered_customer_date": "actual_delivery_timestamp",
        "order_estimated_delivery_date": "expected_delivery_timestamp",
    }
    orders_db = df[list(cols.keys())].rename(columns=cols)

    with engine.begin() as conn:
        conn.execute(text("SET search_path TO control_tower, public;"))
        orders_db.to_sql("orders", conn, if_exists="append", index=False, chunksize=5000)

    logger.info(f"Ingested {len(orders_db):,} orders.")


def ingest_sales(engine):
    """Ingest sales line items."""
    logger.info("Ingesting sales...")
    items_df = load_processed_file("order_items_clean.csv", "olist_order_items_dataset.csv")
    orders_df = load_processed_file("orders_clean.csv", "olist_orders_dataset.csv")

    merged = items_df.merge(
        orders_df[["order_id", "order_purchase_timestamp"]],
        on="order_id",
        how="inner"
    )

    merged["supplier_id"] = merged["seller_id"]
    merged["sales_date"] = pd.to_datetime(merged["order_purchase_timestamp"], errors="coerce")
    merged["quantity_sold"] = 1
    merged["created_at"] = datetime.now(timezone.utc)

    sales_db = merged[[
        "order_id", "order_item_id", "product_id", "supplier_id",
        "sales_date", "quantity_sold", "created_at"
    ]].drop_duplicates(subset=["order_id", "order_item_id"])

    with engine.begin() as conn:
        conn.execute(text("SET search_path TO control_tower, public;"))
        sales_db.to_sql("sales", conn, if_exists="append", index=False, chunksize=5000)

    logger.info(f"Ingested {len(sales_db):,} sales line records.")


def ingest_inventory_snapshots(engine):
    """
    Generate realistic time-series inventory snapshots for top 500 products
    across 5 regional warehouses over the last 90 days of the dataset.
    """
    logger.info("Generating realistic inventory snapshots...")
    items_df = load_processed_file("order_items_clean.csv", "olist_order_items_dataset.csv")
    orders_df = load_processed_file("orders_clean.csv", "olist_orders_dataset.csv")

    merged = items_df.merge(orders_df, on="order_id", how="inner")
    merged["sales_date"] = pd.to_datetime(merged["order_purchase_timestamp"], errors="coerce")

    # Identify top 500 SKUs by volume
    top_products = merged["product_id"].value_counts().head(500).index.tolist()
    warehouses = ["WH-SP", "WH-RJ", "WH-MG", "WH-PR", "WH-RS"]

    # Date range: past 90 days ending at max dataset date
    max_date = merged["sales_date"].max()
    if pd.isna(max_date):
        max_date = datetime(2018, 10, 17)
    
    dates = [max_date - timedelta(days=d) for d in range(89, -1, -1)]

    # Pre-calculate daily demand for each product
    daily_sales = merged[merged["product_id"].isin(top_products)].groupby(
        ["product_id", merged["sales_date"].dt.date]
    ).size().unstack(fill_value=0)

    snapshots = []
    np.random.seed(42)

    for p_idx, prod in enumerate(top_products):
        # Assign 1-2 primary regional warehouses
        assigned_wh = np.random.choice(warehouses, size=np.random.choice([1, 2]), replace=False)
        avg_daily_demand = max(1, int(merged[merged["product_id"] == prod].shape[0] / 365.0 * 2.0))
        reorder_level = int(avg_daily_demand * 14)  # 2 weeks buffer
        current_stock = int(avg_daily_demand * 28)  # 4 weeks starting stock

        # Purposefully simulate ~15% of products entering stockout / low-stock condition
        is_stressed = (p_idx % 7 == 0)

        for d in dates:
            d_date = d.date()
            demand = daily_sales.loc[prod, d_date] if (prod in daily_sales.index and d_date in daily_sales.columns) else 0

            current_stock = max(0, current_stock - int(demand))

            # Replenishment cycle
            if current_stock <= reorder_level and not (is_stressed and current_stock == 0):
                # 30% chance per day of replenishment delivery arrival
                if np.random.rand() > 0.70:
                    current_stock += int(reorder_level * 2.5)

            for wh in assigned_wh:
                stock_share = max(0, int(current_stock / len(assigned_wh)))
                snapshots.append({
                    "product_id": prod,
                    "warehouse_id": wh,
                    "available_stock": stock_share,
                    "reorder_level": int(reorder_level / len(assigned_wh)),
                    "stock_update_timestamp": d,
                    "data_source": "SIMULATED"
                })

    snapshots_df = pd.DataFrame(snapshots)
    with engine.begin() as conn:
        conn.execute(text("SET search_path TO control_tower, public;"))
        snapshots_df.to_sql("inventory_snapshots", conn, if_exists="append", index=False, chunksize=5000)

    logger.info(f"Generated and ingested {len(snapshots_df):,} inventory snapshots.")


def ingest_shipments(engine):
    """
    Ingest shipments:
    1. Outbound customer deliveries derived from Olist orders.
    2. Inbound supplier replenishments simulated for key products.
    """
    logger.info("Ingesting outbound customer shipments from orders...")
    orders_df = load_processed_file("orders_clean.csv", "olist_orders_dataset.csv")
    items_df = load_processed_file("order_items_clean.csv", "olist_order_items_dataset.csv")

    merged = items_df.merge(orders_df, on="order_id", how="inner")
    delivered = merged[merged["order_delivered_carrier_date"].notna()].copy()

    delivered["shipment_id"] = "SHP-OUT-" + delivered["order_id"].str[:8] + "-" + delivered["order_item_id"].astype(str)
    delivered["supplier_id"] = delivered["seller_id"]
    delivered["warehouse_id"] = "WH-SP"
    delivered["shipment_direction"] = "outbound_customer"
    delivered["shipment_date"] = pd.to_datetime(delivered["order_delivered_carrier_date"])
    delivered["expected_delivery_date"] = pd.to_datetime(delivered["order_estimated_delivery_date"])
    delivered["actual_delivery_date"] = pd.to_datetime(delivered["order_delivered_customer_date"])

    # Determine status
    delivered["shipment_status"] = np.where(
        delivered["actual_delivery_date"].notna(),
        np.where(delivered["actual_delivery_date"] <= delivered["expected_delivery_date"], "delivered", "delayed"),
        "in_transit"
    )
    delivered["data_source"] = "OLIST_DERIVED"
    delivered["created_at"] = datetime.now(timezone.utc)

    outbound_db = delivered[[
        "shipment_id", "product_id", "supplier_id", "warehouse_id", "order_id",
        "shipment_direction", "shipment_date", "expected_delivery_date",
        "actual_delivery_date", "shipment_status", "data_source", "created_at"
    ]].drop_duplicates(subset=["shipment_id"])

    # Simulated inbound supplier replenishments
    logger.info("Generating simulated inbound supplier shipments...")
    top_products = items_df["product_id"].value_counts().head(200).index.tolist()
    sp_map = items_df[items_df["product_id"].isin(top_products)][["product_id", "seller_id"]].drop_duplicates()

    inbound = []
    base_date = datetime(2018, 1, 1)
    np.random.seed(99)

    for _, row in sp_map.iterrows():
        prod = row["product_id"]
        supp = row["seller_id"]
        # Generate 4-8 replenishments over the year
        num_shipments = np.random.randint(4, 9)
        for i in range(num_shipments):
            s_date = base_date + timedelta(days=int(np.random.randint(1, 280)))
            lead_days = int(np.random.normal(12, 3))
            e_date = s_date + timedelta(days=lead_days)
            
            # 20% delayed arrivals
            is_delayed = (np.random.rand() < 0.20)
            actual_days = lead_days + (np.random.randint(3, 10) if is_delayed else -np.random.randint(0, 3))
            a_date = s_date + timedelta(days=max(2, actual_days))

            inbound.append({
                "shipment_id": f"SHP-IN-{str(uuid.uuid4())[:8]}",
                "product_id": prod,
                "supplier_id": supp,
                "warehouse_id": np.random.choice(["WH-SP", "WH-RJ", "WH-MG", "WH-PR", "WH-RS"]),
                "order_id": None,
                "shipment_direction": "inbound_supplier",
                "shipment_date": s_date,
                "expected_delivery_date": e_date,
                "actual_delivery_date": a_date,
                "shipment_status": "delayed" if is_delayed else "delivered",
                "data_source": "SIMULATED",
                "created_at": datetime.now(timezone.utc)
            })

    inbound_db = pd.DataFrame(inbound)
    all_shipments = pd.concat([outbound_db, inbound_db], ignore_index=True)

    with engine.begin() as conn:
        conn.execute(text("SET search_path TO control_tower, public;"))
        all_shipments.to_sql("shipments", conn, if_exists="append", index=False, chunksize=5000)

    logger.info(f"Ingested {len(all_shipments):,} total shipments ({len(outbound_db):,} outbound, {len(inbound_db):,} inbound).")


def run_full_ingestion():
    """Execute complete end-to-end data ingestion pipeline."""
    print("=" * 70)
    print("RETAIL & SUPPLY CHAIN CONTROL TOWER: DATA INGESTION ENGINE")
    print("=" * 70)

    engine = get_db_engine()
    init_database(engine)

    # Ingest master dimension tables
    ingest_products(engine)
    ingest_suppliers(engine)
    ingest_supplier_products(engine)
    ingest_warehouses(engine)

    # Ingest transactional tables
    ingest_orders(engine)
    ingest_sales(engine)

    # Ingest simulated logistics & inventory
    ingest_inventory_snapshots(engine)
    ingest_shipments(engine)

    print("\n" + "=" * 70)
    print("DATA INGESTION SUCCESSFULLY COMPLETED!")
    print("=" * 70)


if __name__ == "__main__":
    run_full_ingestion()
