
-- ==================================================
-- RETAIL AND SUPPLY CHAIN CONTROL TOWER
-- PHASE 1: DATABASE SCHEMA
-- ==================================================

CREATE SCHEMA IF NOT EXISTS control_tower;

SET search_path TO control_tower, public;


-- 1. PRODUCTS
CREATE TABLE IF NOT EXISTS products (
    product_id VARCHAR(100) PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    category_name VARCHAR(255),
    source_system VARCHAR(50) DEFAULT 'OLIST',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- 2. SUPPLIERS
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id VARCHAR(100) PRIMARY KEY,
    supplier_name VARCHAR(255) NOT NULL,
    city VARCHAR(150),
    state VARCHAR(100),
    average_lead_time NUMERIC(10,2),
    supplier_performance NUMERIC(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CHECK (
        average_lead_time IS NULL
        OR average_lead_time >= 0
    ),

    CHECK (
        supplier_performance IS NULL
        OR supplier_performance BETWEEN 0 AND 100
    )
);


-- 3. SUPPLIER PRODUCTS
CREATE TABLE IF NOT EXISTS supplier_products (
    supplier_id VARCHAR(100) REFERENCES suppliers(supplier_id),
    product_id VARCHAR(100) REFERENCES products(product_id),

    PRIMARY KEY (supplier_id, product_id)
);


-- 4. WAREHOUSES
CREATE TABLE IF NOT EXISTS warehouses (
    warehouse_id VARCHAR(50) PRIMARY KEY,
    warehouse_name VARCHAR(150) NOT NULL,
    location VARCHAR(255),
    is_simulated BOOLEAN DEFAULT TRUE
);


-- 5. CUSTOMER ORDERS
CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(100) PRIMARY KEY,
    order_status VARCHAR(50),
    purchase_timestamp TIMESTAMP,
    approved_timestamp TIMESTAMP,
    carrier_handover_timestamp TIMESTAMP,
    actual_delivery_timestamp TIMESTAMP,
    expected_delivery_timestamp TIMESTAMP
);


-- 6. SALES / HISTORICAL DEMAND
CREATE TABLE IF NOT EXISTS sales (
    sale_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    order_id VARCHAR(100) NOT NULL
        REFERENCES orders(order_id),

    order_item_id INTEGER NOT NULL,

    product_id VARCHAR(100) NOT NULL
        REFERENCES products(product_id),

    supplier_id VARCHAR(100)
        REFERENCES suppliers(supplier_id),

    sales_date TIMESTAMP NOT NULL,

    quantity_sold INTEGER NOT NULL DEFAULT 1,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(order_id, order_item_id),

    CHECK(quantity_sold > 0)
);


-- 7. INVENTORY SNAPSHOTS
CREATE TABLE IF NOT EXISTS inventory_snapshots (
    snapshot_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    product_id VARCHAR(100) NOT NULL
        REFERENCES products(product_id),

    warehouse_id VARCHAR(50) NOT NULL
        REFERENCES warehouses(warehouse_id),

    available_stock INTEGER NOT NULL,

    reorder_level INTEGER NOT NULL,

    stock_update_timestamp TIMESTAMP NOT NULL,

    data_source VARCHAR(50) DEFAULT 'SIMULATED',

    CHECK(available_stock >= 0),
    CHECK(reorder_level >= 0),

    UNIQUE(
        product_id,
        warehouse_id,
        stock_update_timestamp
    )
);


-- 8. SHIPMENTS
CREATE TABLE IF NOT EXISTS shipments (
    shipment_id VARCHAR(120) PRIMARY KEY,

    product_id VARCHAR(100) NOT NULL
        REFERENCES products(product_id),

    supplier_id VARCHAR(100) NOT NULL
        REFERENCES suppliers(supplier_id),

    warehouse_id VARCHAR(50)
        REFERENCES warehouses(warehouse_id),

    order_id VARCHAR(100)
        REFERENCES orders(order_id),

    shipment_direction VARCHAR(30) NOT NULL,

    shipment_date TIMESTAMP NOT NULL,

    expected_delivery_date TIMESTAMP NOT NULL,

    actual_delivery_date TIMESTAMP,

    shipment_status VARCHAR(40) NOT NULL,

    data_source VARCHAR(50) NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CHECK (
        shipment_direction IN (
            'inbound_supplier',
            'outbound_customer'
        )
    )
);


-- 9. ANOMALY RECORDS
CREATE TABLE IF NOT EXISTS anomalies (
    anomaly_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    anomaly_type VARCHAR(100) NOT NULL,

    product_id VARCHAR(100)
        REFERENCES products(product_id),

    shipment_id VARCHAR(120)
        REFERENCES shipments(shipment_id),

    actual_value NUMERIC(15,4),

    expected_value NUMERIC(15,4),

    detection_method VARCHAR(50) NOT NULL,

    severity VARCHAR(20) NOT NULL,

    detection_timestamp TIMESTAMP NOT NULL,

    description TEXT,

    CHECK (
        severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
    )
);


-- 10. DEMAND FORECASTS
CREATE TABLE IF NOT EXISTS demand_forecasts (
    forecast_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    product_id VARCHAR(100) NOT NULL
        REFERENCES products(product_id),

    forecast_date DATE NOT NULL,

    predicted_demand NUMERIC(15,4) NOT NULL,

    lower_bound NUMERIC(15,4),

    upper_bound NUMERIC(15,4),

    model_name VARCHAR(50) DEFAULT 'PROPHET',

    generated_at TIMESTAMP NOT NULL,

    CHECK(predicted_demand >= 0)
);


-- 11. KPI SNAPSHOTS
CREATE TABLE IF NOT EXISTS kpi_snapshots (
    kpi_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    calculation_timestamp TIMESTAMP NOT NULL,

    stock_out_rate NUMERIC(10,4),

    on_time_delivery_rate NUMERIC(10,4),

    average_supplier_lead_time NUMERIC(10,2),

    days_of_inventory NUMERIC(10,2)
);


-- 12. WHAT-IF SCENARIOS
CREATE TABLE IF NOT EXISTS what_if_scenarios (
    scenario_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    supplier_id VARCHAR(100)
        REFERENCES suppliers(supplier_id),

    shipment_id VARCHAR(120)
        REFERENCES shipments(shipment_id),

    additional_delay_days INTEGER NOT NULL DEFAULT 7,

    simulated_at TIMESTAMP NOT NULL,

    affected_products JSONB,

    expected_shortage JSONB,

    scenario_status VARCHAR(30) DEFAULT 'SIMULATED',

    CHECK(additional_delay_days = 7)
);


-- 13. ALERT EVENTS
CREATE TABLE IF NOT EXISTS alert_events (
    alert_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    anomaly_id BIGINT
        REFERENCES anomalies(anomaly_id),

    product_id VARCHAR(100)
        REFERENCES products(product_id),

    shipment_id VARCHAR(120)
        REFERENCES shipments(shipment_id),

    alert_title VARCHAR(255) NOT NULL,

    severity VARCHAR(20) NOT NULL,

    message TEXT NOT NULL,

    notification_channel VARCHAR(30),

    notification_status VARCHAR(30) DEFAULT 'PENDING',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    sent_at TIMESTAMP
);


-- ==================================================
-- INDEXES FOR QUERY PERFORMANCE
-- ==================================================

CREATE INDEX IF NOT EXISTS idx_sales_product_date
ON sales(product_id, sales_date);

CREATE INDEX IF NOT EXISTS idx_sales_supplier
ON sales(supplier_id);

CREATE INDEX IF NOT EXISTS idx_inventory_product_time
ON inventory_snapshots(product_id, stock_update_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_shipments_status
ON shipments(shipment_status);

CREATE INDEX IF NOT EXISTS idx_shipments_expected_date
ON shipments(expected_delivery_date);

CREATE INDEX IF NOT EXISTS idx_shipments_supplier
ON shipments(supplier_id);

CREATE INDEX IF NOT EXISTS idx_anomalies_timestamp
ON anomalies(detection_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_forecasts_product_date
ON demand_forecasts(product_id, forecast_date);

CREATE INDEX IF NOT EXISTS idx_alerts_status
ON alert_events(notification_status);


-- ==================================================
-- END OF SCHEMA
-- ==================================================
