# Retail & Supply Chain Control Tower

An end-to-end operational visibility, anomaly detection, demand forecasting, and risk simulation platform built for modern retail supply chain networks.

Developed as an engineering capstone at **Nexvia Technologies** by **Mukesh Revanth**.

---

## Overview & Motivation

Modern retail and e-commerce supply chains operate across fragmented systems—suppliers dispatch consignments across multi-state routes, regional distribution centers manage fluctuating buffer stocks, and carriers frequently experience SLA variances. Without a centralized control tower, operations teams only discover stockouts and delayed shipments after customer orders fail.

This project implements a centralized **Supply Chain Control Tower** that consolidates real-world e-commerce logistics data (Olist Brazilian commercial dataset spanning 99,441 orders, 112,650 sales lines, and 3,095 sellers) with regional distribution centers, inventory buffers, and inbound restock consignments. 

### Core Capabilities
1. **Centralized Relational Schema (PostgreSQL):** 13 relational tables maintaining strict referential integrity, covering product catalogs, suppliers, multi-tier orders, inventory snapshots, shipments, anomalies, and forecasts.
2. **Executive KPI Engine:** Automated tracking of the 4 primary supply chain metrics: Stockout Rate, On-Time Delivery (OTD), Supplier Lead Time, and Days of Inventory (DOI).
3. **Consensus Anomaly Detection:** Dual-layer statistical (Parametric Z-Score) and machine learning (Isolation Forest) outlier detection across demand spikes, late shipments, inventory drops, and transit delays.
4. **Demand Forecasting Engine:** 7-day forward demand projections with 80% credible uncertainty intervals to detect impending stockouts before safety buffers deplete.
5. **What-If Disruption Simulator:** Interactive shock modeling evaluating the ripple effect of supplier delays (e.g., strikes, customs backlogs) on buffer stock and projected unit shortages.
6. **Multi-Channel Alert Dispatcher:** Automated routing of high/critical operational incidents to Slack and Email with root causes and suggested actions.
7. **Interactive Operations Dashboard:** Built with Streamlit and Plotly for real-time exploratory visibility.

---

## System Architecture

```text
       +-------------------------------------------------------------+
       |                     DATA SOURCES & INGESTION                |
       |  - Real Olist E-Commerce (99k orders, 112k items, 3k sellers) |
       |  - 5 Regional Distribution Centers (SP, RJ, MG, PR, RS)     |
       |  - Simulated Inbound Freight & Warehouse Stock Buffer Feeds |
       +-------------------------------------------------------------+
                                      |
                                      v
       +-------------------------------------------------------------+
       |               DATA CLEANSING & PIPELINE HYGIENE             |
       |  - ISO-8601 timestamp normalization across order lifecycle  |
       |  - Category name translation (PT -> EN) & null imputation   |
       |  - Address zero-padding & duplicate primary key resolution  |
       +-------------------------------------------------------------+
                                      |
                                      v
       +-------------------------------------------------------------+
       |            POSTGRESQL RELATIONAL STORE (control_tower)      |
       |  - Dimensions: products, suppliers, supplier_products,      |
       |                warehouses                                   |
       |  - Transactions: orders, sales, inventory_snapshots,        |
       |                  shipments                                  |
       |  - Analytics: anomalies, demand_forecasts, kpi_snapshots,   |
       |               what_if_scenarios, alert_events               |
       +-------------------------------------------------------------+
                 |                           |
                 v                           v
+-------------------------------+  +---------------------------------+
|     ANALYTICS & ML ENGINES    |  |     PIPELINE ORCHESTRATION      |
|  - 4 Executive Supply KPIs    |  |  - Apache Airflow DAG           |
|  - Z-Score & Isolation Forest |  |  - 8-stage hourly dependency    |
|  - 7-Day Demand Forecasting   |  |  - Validation, compute & alerts |
|  - What-If Disruption Engine  |  +---------------------------------+
+-------------------------------+                    |
                 |                                   v
                 v                 +---------------------------------+
+-------------------------------+  |     MULTI-CHANNEL ALERTING      |
|     STREAMLIT CONTROL TOWER   |  |  - Slack Webhook (Block Kit)    |
|  - 6 Operational Views        |  |  - Formatted HTML SMTP Emails   |
|  - Live SQL Database Queries  |  |  - Dynamic Action Recommendations|
+-------------------------------+  +---------------------------------+
```

---

## Database Design (`control_tower` Schema)

The database runs on PostgreSQL under a dedicated `control_tower` schema. Key entities include:

| Table | Records Loaded | Description |
|:---|:---:|:---|
| `products` | **32,951** | Catalog dimension with normalized categories and English translations |
| `suppliers` | **3,095** | Commercial sellers with computed historical lead times and SLA scores |
| `supplier_products` | **34,448** | Many-to-many supplier to SKU fulfillment mapping |
| `warehouses` | **5** | Regional distribution facilities: `WH-SP`, `WH-RJ`, `WH-MG`, `WH-PR`, `WH-RS` |
| `orders` | **99,441** | Purchase, approval, carrier dispatch, delivery, and SLA deadlines |
| `sales` | **112,650** | Itemized order lines linked to products and fulfilling sellers |
| `inventory_snapshots` | **68,220** | Daily warehouse stock levels and reorder safety thresholds |
| `shipments` | **113,249** | Outbound customer dispatches + inbound replenishment freight |
| `kpi_snapshots` | Live Log | Historical snapshots of executive metrics |
| `anomalies` | **3,490** | Detected outliers with severity classification and operational narratives |
| `demand_forecasts` | **140** | 7-day forward predictions with 80% credible interval bounds |
| `what_if_scenarios` | Live Log | Disruption simulation runs (shortages, at-risk SKUs) |
| `alert_events` | Live Log | Log of dispatched Slack and Email alerts |

---

## Supply Chain KPIs

The system continuously tracks 4 primary operational indicators:

### 1. Stock-Out Rate (%)
$$\text{Stock-Out Rate} = \frac{\text{Active SKUs with Available Stock} = 0}{\text{Total Active SKUs with Sales Demand in Trailing 30 Days}} \times 100$$
- **Evaluated Value:** **0.0% – 14.2%** (Target: $< 10.0\%$)
- **Purpose:** Identifies whether high-velocity products are failing to meet run-rate demand due to replenishment delays.

### 2. On-Time Delivery Rate (%)
$$\text{On-Time Delivery Rate} = \frac{\text{Shipments Delivered on or before Estimated Date}}{\text{Total Delivered Shipments}} \times 100$$
- **Evaluated Value:** **91.88%** (Target SLA: $> 90.0\%$)
- **Purpose:** Measures carrier compliance against estimated delivery SLA promises across continental transport lanes.

### 3. Supplier Lead Time (Days)
$$\text{Average Lead Time} = \frac{1}{N} \sum_{i=1}^N (\text{Actual Delivery Date}_i - \text{Carrier Dispatch Date}_i)$$
- **Evaluated Value:** **9.24 – 12.4 Days** (Target: $7.0 - 15.0$ Days)
- **Purpose:** Reflects transport duration between industrial hubs (e.g., São Paulo) and consumer destinations.

### 4. Days of Inventory (DOI)
$$\text{Days of Inventory} = \frac{\text{Total Available Units On Hand}}{\text{Average Daily Demand Units (Trailing 30 Days)}}$$
- **Evaluated Value:** **18.6 – 68.3 Days** (Target: $14.0 - 30.0$ Days)
- **Purpose:** Indicates the network's safety buffer runway before exhaustion under normal operating conditions.

---

## Anomaly Detection System

Logistics data frequently contains outliers caused by customs holds, unexpected volume surges, or inventory discrepancies. The platform uses a **consensus approach**:

1. **Parametric Z-Score:**
   $$Z = \frac{x - \mu}{\sigma}$$
   Flags deviations exceeding standard thresholds: $|Z| \ge 3.0$ (High Severity), $|Z| \ge 4.0$ (Critical Severity).
2. **Isolation Forest:**
   An unsupervised tree-based ensemble that isolates anomalies without requiring normality assumptions ($\text{contamination} = 0.05$).

### Operational Dimensions Monitored:
- **Demand Spikes:** Sudden surges in daily SKU sales volume.
- **Delivery Delays:** Shipments arriving well past estimated SLA dates.
- **Inventory Depletions:** Abrupt buffer drops exceeding 75% in a single day.
- **Abnormal Lead Times:** Supplier fulfillment cycles significantly longer than historical baselines.

---

## Demand Forecasting

Using time-series modeling, the platform projects forward 7-day SKU demand:
- **Intervals:** 80% credible uncertainty bands (`yhat_lower`, `yhat_upper`).
- **Holdout Accuracy Evaluation:** Validated using an out-of-sample 7-day test split:
  - **MAE (Mean Absolute Error):** $1.26 \text{ units/day}$
  - **RMSE (Root Mean Squared Error):** $1.61 \text{ units/day}$
  - **MAPE (Mean Absolute Percentage Error):** $14.62\%$
- **Buffer Depletion Alerting:** Automatically compares projected 7-day cumulative consumption against on-hand warehouse inventory to flag impending stockouts before orders fail.

---

## What-If Disruption Simulator

To evaluate supply chain resilience, the simulator models external shocks:
- **Scenario:** An unexpected 1 to 30 day inbound delay on a selected supplier (e.g., transport strike, customs backlog).
- **Engine Logic:**
  1. Identifies all dependent SKUs supplied by the selected vendor.
  2. Projects daily consumer run-rate demand over the shock window.
  3. Simulates on-hand inventory drawdown at regional warehouses.
  4. Flags vulnerable SKUs transitioning into stockout prior to delayed shipment arrival.
  5. Computes total unfulfilled customer units and financial revenue at risk.

---

## Project Structure

```text
retail-supply-chain-control-tower/
├── dashboard_app.py               # Streamlit interactive web dashboard
├── docker-compose.yaml            # PostgreSQL, Airflow, Superset orchestration
├── requirements.txt               # Pinned Python package dependencies
├── README.md                      # Project documentation
├── .env.example                   # Environment configuration template
├── airflow/
│   └── dags/
│       └── supply_chain_pipeline.py  # Hourly 8-stage Airflow DAG
├── dashboards/
│   └── dashboards_documentation.md   # Superset dashboard specifications & SQL
├── data/
│   ├── raw/                       # Original Olist raw CSV datasets
│   └── processed/                 # Cleaned CSV datasets & quality reports
├── database/
│   ├── schema.sql                 # 13 relational tables DDL & constraints
│   └── sample_queries.sql         # Verification and analytical SQL queries
├── docs/
│   ├── data_dictionary.md         # Schema attribute documentation
│   └── results.md                 # Empirical benchmark results & evaluations
├── src/
│   ├── alerts.py                  # Multi-channel Slack & Email notification engine
│   ├── anomaly_detection.py       # Z-Score & Isolation Forest detection
│   ├── data_cleaning.py           # Preprocessing and transformation pipeline
│   ├── data_ingestion.py          # PostgreSQL bulk loader & simulation engine
│   ├── demand_forecasting.py      # 7-day demand forecasting & holdout evaluation
│   ├── inventory_analysis.py      # Warehouse inventory buffer & stockout auditor
│   ├── kpi_calculation.py         # 4 mandatory supply chain KPI calculations
│   └── what_if_analysis.py        # Supplier delay shock simulation engine
└── tests/
    ├── conftest.py                # Pytest configuration & test fixtures
    └── test_pipeline.py           # 16-module comprehensive test suite
```

---

## Getting Started

### 1. Prerequisites
- Python 3.10+
- PostgreSQL 15+ (local instance or Docker)
- Git

### 2. Setup & Virtual Environment
```bash
# Clone the repository
git clone https://github.com/Revanth-4233/retail-supply-chain-control-tower.git
cd retail-supply-chain-control-tower

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy the configuration template:
```bash
cp .env.example .env
```
Ensure your `.env` contains your PostgreSQL credentials:
```env
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=supply_chain_db
DB_USER=admin
DB_PASSWORD=admin123
```

### 4. Run Data Pipeline & Populate Database
```bash
# Clean raw datasets
python src/data_cleaning.py

# Ingest data into PostgreSQL
python src/data_ingestion.py

# Compute KPIs
python src/kpi_calculation.py

# Run Anomaly Detection
python src/anomaly_detection.py

# Generate Demand Forecasts
python src/demand_forecasting.py

# Execute What-If Disruption Simulation
python src/what_if_analysis.py

# Evaluate and Dispatch Alerts
python src/alerts.py
```

### 5. Launch Interactive Dashboard
```bash
streamlit run dashboard_app.py
```
Open **`http://localhost:8501`** in your browser to view the live Control Tower.

### 6. Run Integration Test Suite
```bash
pytest tests/ -v
```
All 16 test modules pass with 100% test coverage across schema, cleaning, KPIs, ML models, and pipelines.

---

## Developer Reflection & Notes

Building this control tower provided valuable hands-on experience in production data engineering and logistics analytics:
- **Real-World Logistics Challenges:** Working with the Olist dataset highlighted the realities of physical supply chains—missing carrier timestamps, geographical transit variances between São Paulo and northern Brazil, and reconciling drop-ship transactions with regional warehouse buffers.
- **Parametric vs. Non-Parametric Anomaly Detection:** Combining Z-Scores with Isolation Forests allowed us to catch both obvious statistical outliers (e.g., shipments 30+ days overdue) and subtle multi-dimensional anomalies that single-variable thresholds miss.
- **Actionable Alert Design:** Rather than spamming alerts, structuring notifications with severity grading, expected vs. actual values, and immediate mitigation actions makes operational feeds genuinely useful for warehouse managers and logistics directors.

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.
