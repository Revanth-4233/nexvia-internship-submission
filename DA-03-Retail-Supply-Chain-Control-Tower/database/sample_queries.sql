-- ====================================================================
-- RETAIL AND SUPPLY CHAIN CONTROL TOWER: SAMPLE & VERIFICATION QUERIES
-- Schema: control_tower
-- ====================================================================

SET search_path TO control_tower, public;

-- ====================================================================
-- 1. DATA VERIFICATION & TABLE RECORD COUNTS
-- ====================================================================

-- 1.1 Row counts across all control tower tables
SELECT 'products' AS table_name, COUNT(*) AS total_records FROM products
UNION ALL
SELECT 'suppliers', COUNT(*) FROM suppliers
UNION ALL
SELECT 'supplier_products', COUNT(*) FROM supplier_products
UNION ALL
SELECT 'warehouses', COUNT(*) FROM warehouses
UNION ALL
SELECT 'orders', COUNT(*) FROM orders
UNION ALL
SELECT 'sales', COUNT(*) FROM sales
UNION ALL
SELECT 'inventory_snapshots', COUNT(*) FROM inventory_snapshots
UNION ALL
SELECT 'shipments', COUNT(*) FROM shipments
UNION ALL
SELECT 'anomalies', COUNT(*) FROM anomalies
UNION ALL
SELECT 'demand_forecasts', COUNT(*) FROM demand_forecasts
UNION ALL
SELECT 'kpi_snapshots', COUNT(*) FROM kpi_snapshots
UNION ALL
SELECT 'what_if_scenarios', COUNT(*) FROM what_if_scenarios
UNION ALL
SELECT 'alert_events', COUNT(*) FROM alert_events;

-- 1.2 Check date range of customer orders & sales
SELECT
    MIN(purchase_timestamp) AS earliest_order,
    MAX(purchase_timestamp) AS latest_order,
    COUNT(*) AS total_orders,
    COUNT(DISTINCT customer_id) AS distinct_customers
FROM orders;

-- 1.3 Check for any orphan sales (missing product or order reference)
SELECT
    COUNT(*) AS orphan_sales_count
FROM sales s
LEFT JOIN products p ON s.product_id = p.product_id
LEFT JOIN orders o ON s.order_id = o.order_id
WHERE p.product_id IS NULL OR o.order_id IS NULL;


-- ====================================================================
-- 2. MANDATORY KPI QUERIES
-- ====================================================================

-- 2.1 Stock-out Rate (%)
-- Formula: (Products with 0 stock where demand exists) / (Total active products with demand) * 100
WITH latest_inventory AS (
    SELECT DISTINCT ON (product_id)
        product_id,
        available_stock,
        reorder_level,
        stock_update_timestamp
    FROM inventory_snapshots
    ORDER BY product_id, stock_update_timestamp DESC
),
recent_demand AS (
    SELECT DISTINCT product_id
    FROM sales
    WHERE sales_date >= (SELECT MAX(sales_date) - INTERVAL '30 days' FROM sales)
)
SELECT
    COUNT(CASE WHEN li.available_stock = 0 THEN 1 END) AS stockout_product_count,
    COUNT(*) AS total_products_with_demand,
    ROUND(
        (COUNT(CASE WHEN li.available_stock = 0 THEN 1 END)::NUMERIC / NULLIF(COUNT(*), 0)) * 100,
        2
    ) AS stock_out_rate_pct
FROM recent_demand rd
JOIN latest_inventory li ON rd.product_id = li.product_id;

-- 2.2 On-Time Delivery Rate (%)
-- Formula: (Delivered shipments on/before expected date) / (Total delivered shipments) * 100
SELECT
    COUNT(CASE WHEN actual_delivery_date <= expected_delivery_date THEN 1 END) AS on_time_shipments,
    COUNT(*) AS total_delivered_shipments,
    ROUND(
        (COUNT(CASE WHEN actual_delivery_date <= expected_delivery_date THEN 1 END)::NUMERIC / NULLIF(COUNT(*), 0)) * 100,
        2
    ) AS on_time_delivery_rate_pct
FROM shipments
WHERE actual_delivery_date IS NOT NULL;

-- 2.3 Supplier Lead Time (Days)
-- Overall average lead time and top supplier breakdown
SELECT
    s.supplier_id,
    s.supplier_name,
    s.city,
    s.state,
    COUNT(shp.shipment_id) AS shipment_volume,
    ROUND(AVG(EXTRACT(EPOCH FROM (shp.actual_delivery_date - shp.shipment_date)) / 86400)::NUMERIC, 2) AS calculated_avg_lead_time_days,
    s.average_lead_time AS recorded_lead_time,
    s.supplier_performance AS performance_score
FROM suppliers s
JOIN shipments shp ON s.supplier_id = shp.supplier_id
WHERE shp.actual_delivery_date IS NOT NULL
GROUP BY s.supplier_id, s.supplier_name, s.city, s.state, s.average_lead_time, s.supplier_performance
ORDER BY shipment_volume DESC
LIMIT 20;

-- 2.4 Days of Inventory (DOI)
-- Formula: current_available_stock / average_daily_demand (over last 30 days)
WITH latest_stock AS (
    SELECT
        product_id,
        SUM(available_stock) AS total_available_stock
    FROM (
        SELECT DISTINCT ON (product_id, warehouse_id)
            product_id, warehouse_id, available_stock
        FROM inventory_snapshots
        ORDER BY product_id, warehouse_id, stock_update_timestamp DESC
    ) sub
    GROUP BY product_id
),
daily_demand AS (
    SELECT
        product_id,
        ROUND((SUM(quantity_sold)::NUMERIC / 30.0), 3) AS avg_daily_demand_units
    FROM sales
    WHERE sales_date >= (SELECT MAX(sales_date) - INTERVAL '30 days' FROM sales)
    GROUP BY product_id
)
SELECT
    p.product_id,
    p.product_name,
    p.category_name,
    ls.total_available_stock,
    dd.avg_daily_demand_units,
    CASE
        WHEN dd.avg_daily_demand_units > 0
        THEN ROUND((ls.total_available_stock / dd.avg_daily_demand_units), 1)
        ELSE NULL
    END AS days_of_inventory
FROM latest_stock ls
JOIN daily_demand dd ON ls.product_id = dd.product_id
JOIN products p ON ls.product_id = p.product_id
ORDER BY days_of_inventory ASC NULLS LAST
LIMIT 25;


-- ====================================================================
-- 3. INVENTORY & STOCK MONITORING QUERIES
-- ====================================================================

-- 3.1 Products below reorder level (critical stock replenishment needed)
WITH latest_stock AS (
    SELECT DISTINCT ON (product_id, warehouse_id)
        product_id,
        warehouse_id,
        available_stock,
        reorder_level,
        stock_update_timestamp
    FROM inventory_snapshots
    ORDER BY product_id, warehouse_id, stock_update_timestamp DESC
)
SELECT
    ls.product_id,
    p.product_name,
    p.category_name,
    ls.warehouse_id,
    ls.available_stock,
    ls.reorder_level,
    (ls.reorder_level - ls.available_stock) AS replenishment_gap,
    ROUND(((ls.available_stock::NUMERIC / NULLIF(ls.reorder_level, 0)) * 100), 1) AS stock_pct_of_reorder
FROM latest_stock ls
JOIN products p ON ls.product_id = p.product_id
WHERE ls.available_stock <= ls.reorder_level
ORDER BY replenishment_gap DESC
LIMIT 25;

-- 3.2 Inventory distribution across regional warehouses
SELECT
    w.warehouse_id,
    w.warehouse_name,
    w.location,
    COUNT(DISTINCT inv.product_id) AS distinct_skus,
    SUM(inv.available_stock) AS total_units_in_stock
FROM warehouses w
JOIN (
    SELECT DISTINCT ON (warehouse_id, product_id)
        warehouse_id, product_id, available_stock
    FROM inventory_snapshots
    ORDER BY warehouse_id, product_id, stock_update_timestamp DESC
) inv ON w.warehouse_id = inv.warehouse_id
GROUP BY w.warehouse_id, w.warehouse_name, w.location
ORDER BY total_units_in_stock DESC;


-- ====================================================================
-- 4. SHIPMENT & SUPPLIER LOGISTICS QUERIES
-- ====================================================================

-- 4.1 Shipment status breakdown and delay analysis
SELECT
    shipment_status,
    shipment_direction,
    COUNT(*) AS shipment_count,
    ROUND(AVG(CASE WHEN actual_delivery_date > expected_delivery_date
              THEN EXTRACT(EPOCH FROM (actual_delivery_date - expected_delivery_date)) / 86400
              ELSE 0 END)::NUMERIC, 1) AS avg_delay_days_when_late
FROM shipments
GROUP BY shipment_status, shipment_direction;

-- 4.2 Delayed shipments currently in transit or delivered late
SELECT
    shipment_id,
    product_id,
    supplier_id,
    shipment_date,
    expected_delivery_date,
    actual_delivery_date,
    shipment_status,
    ROUND(EXTRACT(EPOCH FROM (COALESCE(actual_delivery_date, CURRENT_TIMESTAMP) - expected_delivery_date)) / 86400, 1) AS days_overdue
FROM shipments
WHERE (actual_delivery_date > expected_delivery_date)
   OR (actual_delivery_date IS NULL AND CURRENT_TIMESTAMP > expected_delivery_date)
ORDER BY days_overdue DESC
LIMIT 20;


-- ====================================================================
-- 5. ANOMALY DETECTION QUERIES
-- ====================================================================

-- 5.1 Anomaly summary by detection method, type, and severity
SELECT
    detection_method,
    anomaly_type,
    severity,
    COUNT(*) AS total_anomalies,
    ROUND(AVG(actual_value), 2) AS avg_actual_value,
    ROUND(AVG(expected_value), 2) AS avg_expected_value
FROM anomalies
GROUP BY detection_method, anomaly_type, severity
ORDER BY severity DESC, total_anomalies DESC;

-- 5.2 Top critical anomalies flagged
SELECT
    anomaly_id,
    anomaly_type,
    detection_method,
    severity,
    product_id,
    shipment_id,
    actual_value,
    expected_value,
    ROUND((actual_value - expected_value), 2) AS variance,
    detection_timestamp,
    description
FROM anomalies
WHERE severity IN ('HIGH', 'CRITICAL')
ORDER BY detection_timestamp DESC
LIMIT 25;


-- ====================================================================
-- 6. DEMAND FORECASTING VS INVENTORY COMPARISON
-- ====================================================================

-- 6.1 7-Day forecasted demand compared against current on-hand stock
WITH current_stock AS (
    SELECT
        product_id,
        SUM(available_stock) AS current_on_hand_stock
    FROM (
        SELECT DISTINCT ON (product_id, warehouse_id)
            product_id, warehouse_id, available_stock
        FROM inventory_snapshots
        ORDER BY product_id, warehouse_id, stock_update_timestamp DESC
    ) sub
    GROUP BY product_id
),
forecast_7d AS (
    SELECT
        product_id,
        ROUND(SUM(predicted_demand), 1) AS total_7d_predicted_demand,
        ROUND(SUM(lower_bound), 1) AS lower_bound_7d,
        ROUND(SUM(upper_bound), 1) AS upper_bound_7d
    FROM demand_forecasts
    WHERE forecast_date BETWEEN CURRENT_DATE AND (CURRENT_DATE + INTERVAL '7 days')
    GROUP BY product_id
)
SELECT
    p.product_id,
    p.product_name,
    p.category_name,
    COALESCE(cs.current_on_hand_stock, 0) AS current_stock,
    f.total_7d_predicted_demand,
    f.lower_bound_7d,
    f.upper_bound_7d,
    (COALESCE(cs.current_on_hand_stock, 0) - f.total_7d_predicted_demand) AS projected_stock_balance,
    CASE
        WHEN COALESCE(cs.current_on_hand_stock, 0) < f.total_7d_predicted_demand THEN 'HIGH STOCKOUT RISK'
        WHEN COALESCE(cs.current_on_hand_stock, 0) < f.upper_bound_7d THEN 'MODERATE RISK'
        ELSE 'SUFFICIENT STOCK'
    END AS risk_assessment
FROM forecast_7d f
JOIN products p ON f.product_id = p.product_id
LEFT JOIN current_stock cs ON f.product_id = cs.product_id
ORDER BY projected_stock_balance ASC
LIMIT 25;


-- ====================================================================
-- 7. ALERTS AUDIT & NOTIFICATION HISTORY
-- ====================================================================

SELECT
    alert_id,
    alert_title,
    severity,
    notification_channel,
    notification_status,
    created_at,
    sent_at,
    message
FROM alert_events
ORDER BY created_at DESC
LIMIT 25;
