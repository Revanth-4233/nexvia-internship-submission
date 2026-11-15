# Data Dictionary: Retail & Supply Chain Control Tower

## 1. Project & Dataset Overview

### Selected Dataset: Olist Brazilian E-Commerce
The **Olist Brazilian E-Commerce Public Dataset** was selected as the foundation for this enterprise Control Tower.

**Rationale for Selection:**
- **Real-World Commercial Operations:** Contains 99,441 actual retail customer orders spanning 2016 to 2018 across Brazil, providing realistic commercial order velocity and customer purchasing behavior.
- **Supply Chain Logistics Timestamps:** Features granular delivery tracking lifecycle stages: order purchase, payment approval, carrier delivery handover, actual customer delivery, and estimated delivery dates.
- **Multi-Supplier Ecosystem:** Features 3,095 sellers distributed geographically across Brazil acting as decentralized suppliers with distinct logistics lead times and fulfillment dynamics.
- **Product Categorization:** Contains 32,951 distinct products spanning 73 commercial categories with weight, volume, and descriptive metrics.
- **Realistic Gap Simulation:** As expected in e-commerce drop-ship datasets, internal warehouse inventory snapshots and supplier replenishment feeds are simulated with statistical rigor directly tied to true order demand.

---

## 2. Raw Dataset Specifications (`data/raw/`)

| File Name | Rows | Columns | Description |
|:---|:---:|:---:|:---|
| `olist_customers_dataset.csv` | 99,441 | 5 | Customer identifiers, unique keys, and location coordinates (ZIP, city, state). |
| `olist_geolocation_dataset.csv` | 1,000,163 | 5 | Brazilian ZIP prefix geographic coordinates (latitude, longitude, city, state). |
| `olist_orders_dataset.csv` | 99,441 | 8 | Core order fulfillment records and lifecycle tracking timestamps. |
| `olist_order_items_dataset.csv` | 112,650 | 7 | Order line items detailing product IDs, seller IDs, item pricing, and freight. |
| `olist_order_payments_dataset.csv` | 103,886 | 5 | Payment methods, installment breakdowns, and transaction amounts. |
| `olist_order_reviews_dataset.csv` | 99,224 | 7 | Customer review ratings (1-5), review timestamps, and customer feedback. |
| `olist_products_dataset.csv` | 32,951 | 9 | Product catalog attributes, category tags, weight, and cubic dimensions. |
| `olist_sellers_dataset.csv` | 3,095 | 4 | Seller / supplier identifiers, ZIP codes, municipal cities, and states. |
| `product_category_name_translation.csv` | 71 | 2 | Portuguese-to-English product category lookup mappings. |

---

## 3. Cleaned Dataset Specifications (`data/processed/`)

| File Name | Output Rows | Key Transformations & Cleansing Logic |
|:---|:---:|:---|
| `customers_clean.csv` | 99,441 | Zero-padded 5-digit ZIP codes (`str.zfill(5)`), normalized string fields. |
| `geolocation_clean.csv` | 19,015 | Deduplicated 1M raw rows to distinct ZIP prefixes; calculated mean lat/long centroids and modal city/state names. |
| `orders_clean.csv` | 99,441 | Converted all 5 timestamp columns to ISO-8601 standard datetime format. Preserved legitimate nulls for undelivered / in-transit orders. |
| `order_items_clean.csv` | 112,650 | Parsed `shipping_limit_date` to standard datetime. Verified price and freight integrity. |
| `payments_clean.csv` | 103,886 | Verified installment sequences and numeric payment integrity. |
| `products_clean.csv` | 32,951 | Left-joined English translations; imputed missing categories with `'unknown'`; preserved null physical measurements. |
| `reviews_clean.csv` | 99,224 | Generated unique synthetic primary key `review_row_id` to resolve 814 duplicate `review_id` collisions in raw source. |
| `sellers_clean.csv` | 3,095 | Zero-padded 5-digit seller ZIP codes; verified uniqueness. |

---

## 4. PostgreSQL Relational Database Schema (`control_tower`)

### 4.1 Master & Dimension Tables

#### `products`
Stores product catalog metadata mapped from clean Olist products.
- `product_id` (VARCHAR(100), PK): Unique hexadecimal product identifier.
- `product_name` (VARCHAR(255), NOT NULL): Commercial title constructed from English category + product prefix.
- `category_name` (VARCHAR(255)): Translated English category name.
- `source_system` (VARCHAR(50)): Source provenance (default: `'OLIST'`).
- `created_at` (TIMESTAMP): Ingestion timestamp.

#### `suppliers`
Stores supplier profiles mapped from Olist sellers with derived logistics KPIs.
- `supplier_id` (VARCHAR(100), PK): Hexadecimal supplier identifier (from Olist seller_id).
- `supplier_name` (VARCHAR(255), NOT NULL): Synthetic business name (`Supplier_[City]_[Prefix]`).
- `city` (VARCHAR(150)): Supplier fulfillment facility city.
- `state` (VARCHAR(100)): Supplier state code (e.g., SP, RJ, MG).
- `average_lead_time` (NUMERIC(10,2)): Historical average fulfillment days (from carrier handover to delivery).
- `supplier_performance` (NUMERIC(5,2)): 0–100 quality/on-time compliance rating.
- `created_at` (TIMESTAMP): Record creation timestamp.

#### `supplier_products`
Many-to-many junction table mapping product sourcing relationships.
- `supplier_id` (VARCHAR(100), FK -> `suppliers.supplier_id`): Supplier key.
- `product_id` (VARCHAR(100), FK -> `products.product_id`): Product key.
- Composite PK: `(supplier_id, product_id)`.

#### `warehouses`
Regional distribution centers storing buffer inventory.
- `warehouse_id` (VARCHAR(50), PK): Code identifier (`WH-SP`, `WH-RJ`, `WH-MG`, `WH-PR`, `WH-RS`).
- `warehouse_name` (VARCHAR(150), NOT NULL): Descriptive warehouse title.
- `location` (VARCHAR(255)): Geographic region / Brazilian state.
- `is_simulated` (BOOLEAN): Flag indicating simulated infrastructure (`TRUE`).

---

### 4.2 Transactional & Operational Tables

#### `orders`
Customer transaction headers tracking end-to-end order lifecycle.
- `order_id` (VARCHAR(100), PK): Unique order key.
- `order_status` (VARCHAR(50)): Status (`delivered`, `shipped`, `canceled`, `invoiced`, etc.).
- `purchase_timestamp` (TIMESTAMP): Customer purchase date and time.
- `approved_timestamp` (TIMESTAMP): Payment approval time.
- `carrier_handover_timestamp` (TIMESTAMP): Handover to logistics carrier.
- `actual_delivery_timestamp` (TIMESTAMP): Final recorded customer receipt time.
- `expected_delivery_timestamp` (TIMESTAMP): SLA promised delivery deadline.

#### `sales`
Individual item-level sales demand records.
- `sale_id` (BIGINT, PK, Generated Identity): Unique sale entry ID.
- `order_id` (VARCHAR(100), FK -> `orders.order_id`): Order reference.
- `order_item_id` (INTEGER): Sequential line number within order.
- `product_id` (VARCHAR(100), FK -> `products.product_id`): Product purchased.
- `supplier_id` (VARCHAR(100), FK -> `suppliers.supplier_id`): Fulfilling supplier.
- `sales_date` (TIMESTAMP): Date and time of sale.
- `quantity_sold` (INTEGER, NOT NULL DEFAULT 1): Number of units sold.
- Constraints: `UNIQUE(order_id, order_item_id)`, `CHECK(quantity_sold > 0)`.

#### `inventory_snapshots`
Time-series stock level records per SKU per warehouse facility.
- `snapshot_id` (BIGINT, PK, Generated Identity): Unique snapshot key.
- `product_id` (VARCHAR(100), FK -> `products.product_id`): SKU ID.
- `warehouse_id` (VARCHAR(50), FK -> `warehouses.warehouse_id`): Warehouse ID.
- `available_stock` (INTEGER, NOT NULL): Units on hand and unallocated.
- `reorder_level` (INTEGER, NOT NULL): Safety stock threshold triggering replenishment.
- `stock_update_timestamp` (TIMESTAMP, NOT NULL): Snapshot timestamp.
- `data_source` (VARCHAR(50) DEFAULT `'SIMULATED'`): Data provenance tag.
- Constraints: `CHECK(available_stock >= 0)`, `CHECK(reorder_level >= 0)`, `UNIQUE(product_id, warehouse_id, stock_update_timestamp)`.

#### `shipments`
Inbound supplier replenishments and outbound customer delivery consignments.
- `shipment_id` (VARCHAR(120), PK): Unique tracking identifier.
- `product_id` (VARCHAR(100), FK -> `products.product_id`): Shipped item.
- `supplier_id` (VARCHAR(100), FK -> `suppliers.supplier_id`): Originating supplier.
- `warehouse_id` (VARCHAR(50), FK -> `warehouses.warehouse_id`): Associated distribution center.
- `order_id` (VARCHAR(100), FK -> `orders.order_id`): Outbound customer order reference (NULL for inbound).
- `shipment_direction` (VARCHAR(30)): `'inbound_supplier'` or `'outbound_customer'`.
- `shipment_date` (TIMESTAMP NOT NULL): Dispatch timestamp.
- `expected_delivery_date` (TIMESTAMP NOT NULL): Planned arrival deadline.
- `actual_delivery_date` (TIMESTAMP): Actual arrival timestamp (NULL if in transit).
- `shipment_status` (VARCHAR(40)): `'delivered'`, `'in_transit'`, `'delayed'`.
- `data_source` (VARCHAR(50)): `'OLIST_DERIVED'` or `'SIMULATED'`.

---

### 4.3 Analytics & Intelligence Tables

#### `anomalies`
Audit log of anomalies detected via Z-score and Isolation Forest.
- `anomaly_id` (BIGINT, PK, Generated Identity): Unique anomaly ID.
- `anomaly_type` (VARCHAR(100)): `'DEMAND_SPIKE'`, `'DELIVERY_DELAY'`, `'INVENTORY_DROP'`, `'LEAD_TIME_ANOMALY'`.
- `product_id` (VARCHAR(100), FK -> `products.product_id`): Affected SKU.
- `shipment_id` (VARCHAR(120), FK -> `shipments.shipment_id`): Affected shipment.
- `actual_value` (NUMERIC(15,4)): Observed measurement.
- `expected_value` (NUMERIC(15,4)): Statistical mean or baseline value.
- `detection_method` (VARCHAR(50)): `'Z_SCORE'` or `'ISOLATION_FOREST'`.
- `severity` (VARCHAR(20)): `'LOW'`, `'MEDIUM'`, `'HIGH'`, `'CRITICAL'`.
- `detection_timestamp` (TIMESTAMP): Detection run timestamp.
- `description` (TEXT): Diagnostic narrative.

#### `demand_forecasts`
Machine learning demand predictions generated via Facebook Prophet.
- `forecast_id` (BIGINT, PK, Generated Identity): Unique forecast entry ID.
- `product_id` (VARCHAR(100), FK -> `products.product_id`): SKU evaluated.
- `forecast_date` (DATE NOT NULL): Target forecast date.
- `predicted_demand` (NUMERIC(15,4) NOT NULL): Forecasted units ($\hat{y}$).
- `lower_bound` (NUMERIC(15,4)): 80% credible interval lower bound.
- `upper_bound` (NUMERIC(15,4)): 80% credible interval upper bound.
- `model_name` (VARCHAR(50) DEFAULT `'PROPHET'`): Algorithm identifier.
- `generated_at` (TIMESTAMP NOT NULL): Training run timestamp.

#### `kpi_snapshots`
Periodic operational KPI benchmarks.
- `kpi_id` (BIGINT, PK, Generated Identity): Metric snapshot key.
- `calculation_timestamp` (TIMESTAMP NOT NULL): Execution timestamp.
- `stock_out_rate` (NUMERIC(10,4)): Percentage of active SKUs out of stock.
- `on_time_delivery_rate` (NUMERIC(10,4)): Percentage of shipments delivered on time.
- `average_supplier_lead_time` (NUMERIC(10,2)): Average fulfillment lead time in days.
- `days_of_inventory` (NUMERIC(10,2)): Average days of on-hand supply.

#### `what_if_scenarios`
Audit logs of simulated disruption stress tests (e.g., 7-day supplier delays).
- `scenario_id` (BIGINT, PK, Generated Identity): Scenario run key.
- `supplier_id` (VARCHAR(100), FK -> `suppliers.supplier_id`): Disrupted supplier.
- `shipment_id` (VARCHAR(120), FK -> `shipments.shipment_id`): Simulated shipment.
- `additional_delay_days` (INTEGER DEFAULT 7): Delay injected (mandated: 7 days).
- `simulated_at` (TIMESTAMP NOT NULL): Simulation execution timestamp.
- `affected_products` (JSONB): Structured payload of affected SKUs.
- `expected_shortage` (JSONB): Projected inventory stockout units.
- `scenario_status` (VARCHAR(30)): Status (`'SIMULATED'`).

#### `alert_events`
Outbound automated notifications generated for Slack and Email channels.
- `alert_id` (BIGINT, PK, Generated Identity): Alert sequence key.
- `anomaly_id` (BIGINT, FK -> `anomalies.anomaly_id`): Optional anomaly link.
- `product_id` (VARCHAR(100)): Target product.
- `shipment_id` (VARCHAR(120)): Target shipment.
- `alert_title` (VARCHAR(255) NOT NULL): Concise summary subject.
- `severity` (VARCHAR(20) NOT NULL): `'LOW'`, `'MEDIUM'`, `'HIGH'`, `'CRITICAL'`.
- `message` (TEXT NOT NULL): Detailed alert narrative with actual vs threshold values.
- `notification_channel` (VARCHAR(30)): `'SLACK'`, `'EMAIL'`, `'LOG'`.
- `notification_status` (VARCHAR(30)): `'PENDING'`, `'SENT'`, `'FAILED'`.
- `created_at` (TIMESTAMP): Trigger timestamp.
- `sent_at` (TIMESTAMP): Dispatch timestamp.
