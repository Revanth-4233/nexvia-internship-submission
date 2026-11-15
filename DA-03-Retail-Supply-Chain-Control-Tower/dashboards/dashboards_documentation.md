# Apache Superset Interactive Dashboards Documentation
## Retail and Supply Chain Control Tower

This documentation details the architecture, SQL datasets, visual chart configurations, and setup procedures for all **6 interactive Apache Superset dashboards** connected to the PostgreSQL `control_tower` schema.

---

## 1. Apache Superset Database Connection Setup

### 1.1 Connection Parameters
- **Database Driver:** PostgreSQL (`psycopg2`)
- **Host (Inside Docker Network):** `postgres:5432`
- **Host (Local Host Machine):** `localhost:5432`
- **Database Name:** `supply_chain_db`
- **Username:** `admin`
- **Password:** `admin123`
- **SQLAlchemy URI:**
  ```text
  postgresql+psycopg2://admin:admin123@postgres:5432/supply_chain_db
  ```

### 1.2 Configuration Steps in Superset UI
1. Navigate to `http://localhost:8088` and authenticate with `admin` / `admin`.
2. Click **+ Database** $\rightarrow$ Select **PostgreSQL**.
3. In **Advanced Settings** $\rightarrow$ **SQL Lab**, check:
   - *Expose in SQL Lab*
   - *Allow DDL*
   - *Set Search Path:* `control_tower, public`
4. Test Connection $\rightarrow$ Save.

---

## 2. Dashboard 1: Executive Overview

**Target Audience:** Chief Supply Chain Officer (CSCO), VP of Operations, Logistics Directors.  
**Purpose:** High-level executive pulse monitoring overall network velocity, fulfillment SLA adherence, inventory buffer health, and core KPIs.

### Visual Components & Exact SQL Queries:

#### Card 1.1: Total Products Managed
- **Chart Type:** Big Number / KPI Card
```sql
SELECT COUNT(*) AS total_active_products FROM control_tower.products;
```

#### Card 1.2: Total On-Hand Inventory
- **Chart Type:** Big Number / KPI Card
```sql
SELECT SUM(available_stock) AS total_inventory_units
FROM (
    SELECT DISTINCT ON (product_id, warehouse_id) product_id, available_stock
    FROM control_tower.inventory_snapshots
    ORDER BY product_id, warehouse_id, stock_update_timestamp DESC
) sub;
```

#### Card 1.3: Stock-out Rate (%)
- **Chart Type:** Big Number with Trendline
```sql
SELECT
    calculation_timestamp AS ds,
    stock_out_rate AS "Stock-out Rate (%)"
FROM control_tower.kpi_snapshots
ORDER BY calculation_timestamp DESC
LIMIT 30;
```

#### Card 1.4: On-Time Delivery Rate (%)
- **Chart Type:** Big Number with Gauge
```sql
SELECT
    calculation_timestamp AS ds,
    on_time_delivery_rate AS "On-Time Delivery Rate (%)"
FROM control_tower.kpi_snapshots
ORDER BY calculation_timestamp DESC
LIMIT 30;
```

#### Card 1.5: Average Supplier Lead Time (Days)
- **Chart Type:** Big Number
```sql
SELECT
    calculation_timestamp AS ds,
    average_supplier_lead_time AS "Lead Time (Days)"
FROM control_tower.kpi_snapshots
ORDER BY calculation_timestamp DESC
LIMIT 1;
```

#### Card 1.6: Days of Inventory (DOI)
- **Chart Type:** Big Number
```sql
SELECT
    calculation_timestamp AS ds,
    days_of_inventory AS "Days of Inventory"
FROM control_tower.kpi_snapshots
ORDER BY calculation_timestamp DESC
LIMIT 1;
```

#### Chart 1.7: Overall Supply Chain Health Score
- **Chart Type:** Gauge Chart ($0 - 100$)
- **Formula:** Weighted composite score:
  $$\text{Health} = 0.40 \times \text{OTD} + 0.30 \times (100 - \text{Stockout}) + 0.15 \times \text{LeadTimeCompliance} + 0.15 \times \text{DOICompliance}$$
```sql
SELECT
    ROUND(
        (0.40 * on_time_delivery_rate) +
        (0.30 * (100.0 - stock_out_rate)) +
        (0.15 * GREATEST(0, 100 - ABS(average_supplier_lead_time - 12.0) * 5)) +
        (0.15 * GREATEST(0, 100 - ABS(days_of_inventory - 20.0) * 3))
    , 1) AS "Supply Chain Health Score"
FROM control_tower.kpi_snapshots
ORDER BY calculation_timestamp DESC
LIMIT 1;
```

---

## 3. Dashboard 2: Inventory Monitoring

**Target Audience:** Warehouse Operations Managers, Inventory Planners.  
**Purpose:** Real-time visibility into stock availability, replenishment triggers, and regional warehouse stock allocation.

### Visual Components & Queries:

#### Chart 2.1: Top 20 SKUs by On-Hand Stock Volume
- **Chart Type:** Horizontal Bar Chart
```sql
SELECT
    p.product_name AS "Product",
    SUM(i.available_stock) AS "Available Stock Units"
FROM (
    SELECT DISTINCT ON (product_id, warehouse_id) product_id, available_stock
    FROM control_tower.inventory_snapshots
    ORDER BY product_id, warehouse_id, stock_update_timestamp DESC
) i
JOIN control_tower.products p ON i.product_id = p.product_id
GROUP BY p.product_name
ORDER BY "Available Stock Units" DESC
LIMIT 20;
```

#### Table 2.2: Critical Low-Stock Products Below Reorder Level
- **Chart Type:** Interactive Data Table (Sortable, Searchable)
```sql
WITH latest_inv AS (
    SELECT DISTINCT ON (i.product_id, i.warehouse_id)
        i.product_id, p.product_name, p.category_name, i.warehouse_id,
        i.available_stock, i.reorder_level
    FROM control_tower.inventory_snapshots i
    JOIN control_tower.products p ON i.product_id = p.product_id
    ORDER BY i.product_id, i.warehouse_id, i.stock_update_timestamp DESC
)
SELECT
    product_name AS "Product Name",
    category_name AS "Category",
    warehouse_id AS "Warehouse",
    available_stock AS "On-Hand Stock",
    reorder_level AS "Reorder Point",
    (reorder_level - available_stock) AS "Replenishment Shortfall",
    ROUND((available_stock::NUMERIC / NULLIF(reorder_level, 0)) * 100, 1) AS "Stock % of Target"
FROM latest_inv
WHERE available_stock <= reorder_level
ORDER BY "Replenishment Shortfall" DESC;
```

#### Chart 2.3: Inventory Distribution Across Regional Warehouses
- **Chart Type:** Donut / Pie Chart
```sql
SELECT
    w.warehouse_name AS "Regional Facility",
    SUM(i.available_stock) AS "Units in Storage"
FROM control_tower.warehouses w
JOIN (
    SELECT DISTINCT ON (warehouse_id, product_id) warehouse_id, available_stock
    FROM control_tower.inventory_snapshots
    ORDER BY warehouse_id, product_id, stock_update_timestamp DESC
) i ON w.warehouse_id = i.warehouse_id
GROUP BY w.warehouse_name;
```

#### Chart 2.4: Inventory Breakdown by Commercial Product Category
- **Chart Type:** Treemap / Stacked Bar
```sql
SELECT
    p.category_name AS "Category",
    SUM(i.available_stock) AS "Inventory Units"
FROM control_tower.products p
JOIN (
    SELECT DISTINCT ON (product_id) product_id, available_stock
    FROM control_tower.inventory_snapshots
    ORDER BY product_id, stock_update_timestamp DESC
) i ON p.product_id = i.product_id
GROUP BY p.category_name
ORDER BY "Inventory Units" DESC
LIMIT 12;
```

---

## 4. Dashboard 3: Shipment and Supplier Monitoring

**Target Audience:** Logistics Dispatchers, Carrier Managers, Procurement Specialists.  
**Purpose:** Monitor freight transit velocity, track delivery delays, and evaluate supplier fulfillment compliance.

### Visual Components & Queries:

#### Cards 3.1 - 3.4: Shipment Status Overview Cards
- **Chart Type:** Multi-Card Row
```sql
SELECT
    COUNT(*) AS total_shipments,
    COUNT(CASE WHEN shipment_status = 'delivered' THEN 1 END) AS delivered_shipments,
    COUNT(CASE WHEN shipment_status = 'delayed' THEN 1 END) AS delayed_shipments,
    COUNT(CASE WHEN shipment_status = 'in_transit' THEN 1 END) AS in_transit_shipments
FROM control_tower.shipments;
```

#### Chart 3.5: On-Time Delivery Rate by Top Suppliers
- **Chart Type:** Grouped Bar Chart
```sql
SELECT
    s.supplier_name AS "Supplier",
    COUNT(shp.shipment_id) AS "Total Consignments",
    ROUND(
        (COUNT(CASE WHEN shp.actual_delivery_date <= shp.expected_delivery_date THEN 1 END)::NUMERIC / NULLIF(COUNT(shp.actual_delivery_date), 0)) * 100,
        1
    ) AS "On-Time Compliance (%)"
FROM control_tower.suppliers s
JOIN control_tower.shipments shp ON s.supplier_id = shp.supplier_id
WHERE shp.actual_delivery_date IS NOT NULL
GROUP BY s.supplier_name
HAVING COUNT(shp.shipment_id) >= 50
ORDER BY "On-Time Compliance (%)" DESC
LIMIT 15;
```

#### Chart 3.6: Average Transit Lead Time by Supplier Location (State)
- **Chart Type:** Geographic Map / Bar Chart
```sql
SELECT
    s.state AS "Supplier State",
    ROUND(AVG(EXTRACT(EPOCH FROM (shp.actual_delivery_date - shp.shipment_date)) / 86400)::NUMERIC, 1) AS "Avg Lead Time (Days)"
FROM control_tower.suppliers s
JOIN control_tower.shipments shp ON s.supplier_id = shp.supplier_id
WHERE shp.actual_delivery_date IS NOT NULL
GROUP BY s.state
ORDER BY "Avg Lead Time (Days)" ASC;
```

#### Table 3.7: Active Overdue Shipments Log
- **Chart Type:** Table with Conditional Severity Highlighting
```sql
SELECT
    shp.shipment_id AS "Shipment ID",
    s.supplier_name AS "Supplier",
    shp.expected_delivery_date AS "SLA Promised Date",
    ROUND(EXTRACT(EPOCH FROM (COALESCE(shp.actual_delivery_date, CURRENT_TIMESTAMP) - shp.expected_delivery_date)) / 86400, 1) AS "Days Overdue",
    shp.shipment_status AS "Status"
FROM control_tower.shipments shp
JOIN control_tower.suppliers s ON shp.supplier_id = s.supplier_id
WHERE (shp.actual_delivery_date > shp.expected_delivery_date)
   OR (shp.actual_delivery_date IS NULL AND CURRENT_TIMESTAMP > shp.expected_delivery_date)
ORDER BY "Days Overdue" DESC
LIMIT 25;
```

---

## 5. Dashboard 4: Demand Forecasting

**Target Audience:** Demand Forecasters, Procurement Planners, Supply Chain Analysts.  
**Purpose:** Visualize Prophet 7-day future predictions, confidence uncertainty intervals, and compare forecasted demand against warehouse inventory.

### Visual Components & Queries:

#### Chart 4.1: Historical Sales Demand vs. Prophet 7-Day Forecast Horizon
- **Chart Type:** Time-Series Multi-Line Chart with Shaded Uncertainty Bands
```sql
-- Historical actual sales
SELECT
    DATE(sales_date) AS "Date",
    product_id AS "Product",
    SUM(quantity_sold) AS "Actual Demand",
    NULL::NUMERIC AS "Predicted Demand",
    NULL::NUMERIC AS "Lower Bound",
    NULL::NUMERIC AS "Upper Bound"
FROM control_tower.sales
WHERE sales_date >= (SELECT MAX(sales_date) - INTERVAL '90 days' FROM control_tower.sales)
GROUP BY DATE(sales_date), product_id

UNION ALL

-- 7-Day Prophet Forecast
SELECT
    forecast_date AS "Date",
    product_id AS "Product",
    NULL::NUMERIC AS "Actual Demand",
    predicted_demand AS "Predicted Demand",
    lower_bound AS "Lower Bound",
    upper_bound AS "Upper Bound"
FROM control_tower.demand_forecasts
WHERE forecast_date BETWEEN CURRENT_DATE AND (CURRENT_DATE + INTERVAL '7 days')
ORDER BY "Date" ASC;
```

#### Table 4.2: Forecasted Demand vs Current On-Hand Inventory
- **Chart Type:** Table with Vulnerability Highlighting
```sql
WITH current_stock AS (
    SELECT product_id, SUM(available_stock) AS stock
    FROM (
        SELECT DISTINCT ON (product_id, warehouse_id) product_id, available_stock
        FROM control_tower.inventory_snapshots
        ORDER BY product_id, warehouse_id, stock_update_timestamp DESC
    ) sub
    GROUP BY product_id
),
forecast_7d AS (
    SELECT
        product_id,
        ROUND(SUM(predicted_demand), 1) AS total_7d_forecast,
        ROUND(SUM(lower_bound), 1) AS lower_7d,
        ROUND(SUM(upper_bound), 1) AS upper_7d
    FROM control_tower.demand_forecasts
    WHERE forecast_date BETWEEN CURRENT_DATE AND (CURRENT_DATE + INTERVAL '7 days')
    GROUP BY product_id
)
SELECT
    p.product_name AS "Product Name",
    p.category_name AS "Category",
    COALESCE(cs.stock, 0) AS "Current On-Hand Stock",
    f.total_7d_forecast AS "7-Day Projected Demand",
    (COALESCE(cs.stock, 0) - f.total_7d_forecast) AS "Projected Stock Balance",
    CASE
        WHEN COALESCE(cs.stock, 0) < f.total_7d_forecast THEN 'CRITICAL SHORTAGE RISK'
        WHEN COALESCE(cs.stock, 0) < f.upper_7d THEN 'MODERATE BUFFER RISK'
        ELSE 'SUFFICIENT INVENTORY'
    END AS "Risk Assessment"
FROM forecast_7d f
JOIN control_tower.products p ON f.product_id = p.product_id
LEFT JOIN current_stock cs ON f.product_id = cs.product_id
ORDER BY "Projected Stock Balance" ASC;
```

---

## 6. Dashboard 5: Anomaly Monitoring

**Target Audience:** Anomaly Response Unit, Quality Assurance, Exception Handlers.  
**Purpose:** Real-time triage of statistical outliers identified by Z-Score and Isolation Forest across sales, inventory, and logistics.

### Visual Components & Queries:

#### Card 5.1 - 5.4: Anomaly Severity Metric Cards
- **Chart Type:** KPI Row
```sql
SELECT
    COUNT(*) AS total_anomalies,
    COUNT(CASE WHEN severity = 'CRITICAL' THEN 1 END) AS critical_count,
    COUNT(CASE WHEN severity = 'HIGH' THEN 1 END) AS high_count,
    COUNT(CASE WHEN severity = 'MEDIUM' THEN 1 END) AS medium_count
FROM control_tower.anomalies;
```

#### Chart 5.5: Anomalies Flagged by Operational Type
- **Chart Type:** Bar Chart
```sql
SELECT
    anomaly_type AS "Anomaly Type",
    COUNT(*) AS "Total Occurrences"
FROM control_tower.anomalies
GROUP BY anomaly_type
ORDER BY "Total Occurrences" DESC;
```

#### Chart 5.6: Consensus vs Independent Detection Methods
- **Chart Type:** Donut Chart
```sql
SELECT
    detection_method AS "Algorithm",
    COUNT(*) AS "Detections"
FROM control_tower.anomalies
GROUP BY detection_method;
```

#### Table 5.7: Priority Anomaly Audit Log
- **Chart Type:** Interactive Table with Color Severity Pills
```sql
SELECT
    anomaly_id AS "ID",
    detection_timestamp AS "Timestamp",
    severity AS "Severity",
    anomaly_type AS "Type",
    detection_method AS "Method",
    actual_value AS "Observed",
    expected_value AS "Baseline",
    description AS "Diagnostic Narrative"
FROM control_tower.anomalies
WHERE severity IN ('HIGH', 'CRITICAL')
ORDER BY detection_timestamp DESC
LIMIT 50;
```

---

## 7. Dashboard 6: What-If Analysis

**Target Audience:** Supply Chain Risk Managers, Contingency Planners.  
**Purpose:** Interactive sandbox simulating the mandatory scenario: **What happens if a supplier is delayed by 7 days?**

### Visual Components & Queries:

#### Filter 6.1: Supplier Selector Dropdown
- **Filter Type:** Single Select Filter
- **Source:** `SELECT DISTINCT supplier_id, supplier_name FROM control_tower.suppliers ORDER BY supplier_name;`

#### Chart 6.2: Projected Unit Shortage Across Affected SKUs
- **Chart Type:** Bar Chart
```sql
WITH latest_scenario AS (
    SELECT scenario_id, expected_shortage
    FROM control_tower.what_if_scenarios
    ORDER BY simulated_at DESC
    LIMIT 1
)
SELECT
    key AS "Product ID",
    value::numeric AS "Projected Stockout Shortage (Units)"
FROM latest_scenario,
     jsonb_each_text(expected_shortage)
ORDER BY "Projected Stockout Shortage (Units)" DESC;
```

#### Table 6.3: Simulated Shock Impact Assessment Table
- **Chart Type:** Detailed Impact Table
```sql
SELECT
    scenario_id AS "Run ID",
    simulated_at AS "Simulation Timestamp",
    supplier_id AS "Target Supplier",
    additional_delay_days AS "Injected Delay (Days)",
    jsonb_array_length(affected_products) AS "SKUs at Risk",
    scenario_status AS "Scenario Type"
FROM control_tower.what_if_scenarios
ORDER BY simulated_at DESC
LIMIT 10;
```

---

## 8. Superset Dashboard Deployment Checklist

- [x] Schema initialized with `schema.sql` and indexes enabled.
- [x] Cleaned data ingested via `src/data_ingestion.py`.
- [x] Initial KPI snapshot generated via `src/kpi_calculation.py`.
- [x] Anomaly detection run via `src/anomaly_detection.py`.
- [x] Prophet demand forecast populated via `src/demand_forecasting.py`.
- [x] What-If simulation executed via `src/what_if_analysis.py`.
- [x] PostgreSQL dataset registered in Apache Superset UI.
- [x] All 6 dashboard pages created and charts mapped to the SQL queries above.
