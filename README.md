# Nexvia Technologies - Final Capstone Project Submission

**Candidate Name:** Mukesh Revanth  
**GitHub Profile:** [@Revanth-4233](https://github.com/Revanth-4233)  
**Organization:** Nexvia Technologies  
**Allotted Projects:** `DA-02` (Customer 360 & Marketing Attribution) & `DA-03` (Retail & Supply Chain Control Tower)

---

## Repository Structure & Overview

Per the mandatory final evaluation submission requirements, this repository contains the complete source code, tests, documentation, and deliverables for both allotted engineering projects organized in dedicated subfolders:

```text
nexvia-internship-submission/
├── README.md                                  # Master repository submission overview
├── .gitignore                                 # Unified exclusions for virtual envs and large raw feeds
│
├── DA-02-Customer-360-Attribution/            # Project 1: Customer 360 & Multi-Touch Attribution
│   ├── attribution/                           # Markov Chain transition graph & removal-effect attribution
│   ├── data_generator/                        # Deterministic synthetic touchpoint & journey generator
│   ├── dbt/                                   # dbt transformation models (staging, intermediate, marts)
│   ├── docs/                                  # Data lineage, architecture diagrams, model comparison
│   ├── exports/                               # Analytical exports for BI consumption
│   ├── scripts/                               # BigQuery & DuckDB loader scripts, Tableau export runners
│   ├── tableau/                               # Tableau dashboard workbook specifications
│   ├── tests/                                 # Unit & integration tests for data generator & Markov models
│   ├── Makefile                               # Automation shortcuts (generate, load, run, test)
│   ├── README.md                              # In-depth project documentation
│   └── requirements.txt                       # Pinned Python dependencies
│
└── DA-03-Retail-Supply-Chain-Control-Tower/   # Project 2: Retail & Supply Chain Control Tower
    ├── airflow/dags/                          # 8-stage hourly Apache Airflow monitoring DAG
    ├── dashboard_app.py                       # Live Streamlit interactive Control Tower web application
    ├── dashboards/                            # Superset dashboard specifications & SQL queries
    ├── database/                              # 13 relational tables schema DDL & sample queries
    ├── docs/                                  # Architectural ERDs, data dictionary, results benchmarks
    ├── src/                                   # Production pipeline & ML analytics engines
    │   ├── alerts.py                          # Multi-channel Slack & Email automated alerting
    │   ├── anomaly_detection.py               # Z-Score & Isolation Forest anomaly detection
    │   ├── data_cleaning.py                   # Olist raw data cleansing & normalization
    │   ├── data_ingestion.py                  # PostgreSQL loader & simulated warehouse snapshot engine
    │   ├── demand_forecasting.py              # 7-day Facebook Prophet forecasting & holdout backtesting
    │   ├── inventory_analysis.py              # Warehouse buffer audit & low-stock replenishment
    │   ├── kpi_calculation.py                 # 4 core supply chain KPIs (Stockout, OTD, Lead Time, DOI)
    │   └── what_if_analysis.py                # 7-day supplier delay disruption shock simulator
    ├── tests/                                 # 16-module comprehensive integration test suite
    ├── docker-compose.yaml                    # PostgreSQL, Airflow, Superset container orchestration
    ├── LICENSE                                # MIT License
    ├── README.md                              # In-depth project documentation
    └── requirements.txt                       # Pinned Python dependencies
```

---

## Project 1: DA-02 | Customer 360 & Marketing Attribution Platform

### 1. Executive Summary
Modern omni-channel D2C brands struggle with cross-device identity fragmentation and channel attribution bias. When customers interact across website touchpoints (GA4), mobile app events (Segment), and purchase in a CRM, ad networks (Meta Ads, Google Ads) redundantly claim 100% credit for the same conversion using last-touch heuristics.

This platform unifies raw omni-channel user touchpoints into a canonical **Customer 360** profile and calculates realistic channel revenue credit using **six rule-based models** plus a data-driven **Markov Chain graph with removal effects**.

### 2. Architecture & Data Flow
- **Raw Ingestion:** Google Analytics 4 (web session events), Segment (app identifies & screen tracks), CRM (order lines, customer contacts), and Ad Spend (daily campaign costs).
- **Transformation Engine (dbt + DuckDB / BigQuery):**
  - **Staging (`stg_`):** Data hygiene, type-casting, session boundary demarcation, and deduplication.
  - **Intermediate (`int_`):** Graph-based identity stitching (`int_identity_graph`) linking anonymous cookie IDs (`ga_client_id`, `anonymous_id`) to registered `customer_id` profiles; sessionization with 30-minute inactivity timeouts.
  - **Marts (`marts_`):** Clean analytical dimensions (`dim_customers`), order touchpoints (`fct_orders`, `fct_attribution_long`), and campaign financial reconciliation (`mart_campaign_roas`, `mart_channel_performance`).
- **Attribution Algorithms:** First-Touch, Last-Touch, Linear, Time-Decay (7-day half-life), Position-Based (U-Shaped 40/40/20), and First-Order Markov Chain with graph transition probability matrices.
- **Reporting:** Reconciles attributed marketing revenue directly back to finance General Ledger order records.

### 3. Pipeline Execution Results & Benchmarks

The entire end-to-end pipeline was executed and validated locally on DuckDB (`warehouse.duckdb`):

| Pipeline Stage | Entity / Model | Verified Output / Row Count | Status |
|---|---|---|---|
| **Synthetic Ingestion** | GA4 Web Events | 96,571 events | ✅ Completed |
| | Segment Mobile Tracks | 28,028 events | ✅ Completed |
| | Segment Identifies | 2,071 mappings | ✅ Completed |
| | CRM Contacts | 2,271 profiles | ✅ Completed |
| | CRM Orders | 1,858 purchases | ✅ Completed |
| | Ad Spend Records | 2,184 spend rows | ✅ Completed |
| **dbt Build** | Staging, Int, Marts Models | 17 models, 2 seeds, 58 data tests | ✅ 77/77 Passed (0 errors) |
| **Markov Attribution** | Channel Removal Graph | 9 omni-channels evaluated | ✅ Baseline Conv: 23.5% |
| **BI Data Exports** | Tableau CSV Exports | 8 analytical tables generated | ✅ Fully synced |
| **Automated Tests** | Integration Test Suite | 7 unit & identity tests | ✅ 7/7 Passed (100%) |

#### Channel Attribution & ROAS Comparison Matrix
| Channel | First-Touch Share | Last-Touch Share | Linear Share | Time-Decay Share | Markov Share | Attributed Revenue | Paid ROAS (Markov) |
|---|---|---|---|---|---|---|---|
| **Direct** | 17.8% | 20.8% | 19.4% | 19.8% | **17.8%** | $2,212,730 | — |
| **Email** | 9.5% | 24.5% | 17.2% | 20.3% | **17.1%** | $2,131,084 | — |
| **Paid Search** | 17.6% | 20.2% | 18.4% | 19.1% | **16.4%** | $2,046,510 | **1.88x** |
| **Organic Search**| 18.6% | 12.2% | 15.7% | 14.3% | **15.1%** | $1,879,875 | — |
| **Paid Social** | 14.9% | 8.1% | 11.4% | 10.1% | **11.5%** | $1,427,761 | **3.12x** |
| **Display** | 7.0% | 2.1% | 4.9% | 3.7% | **6.4%** | $796,029 | **6.57x** |
| **Organic Social**| 6.0% | 2.7% | 4.8% | 4.0% | **6.1%** | $763,550 | — |
| **Affiliate** | 4.3% | 6.0% | 4.6% | 5.2% | **5.5%** | $681,016 | — |
| **Referral** | 4.3% | 3.4% | 3.6% | 3.6% | **4.2%** | $522,732 | — |

> **Key Analytical Takeaway:** Last-touch models severely undervalue top-of-funnel discovery channels like Display (underreported by 67% relative to Markov removal effects) and Paid Social, while over-attributing to bottom-of-funnel channels like Email and Direct.

### 4. Quick Run Instructions
```bash
cd DA-02-Customer-360-Attribution

# Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run full pipeline locally on DuckDB
make all

# Execute automated test suite
pytest tests/ -v
```
*Test suite status:* **7/7 Passed (100%)** | *dbt test status:* **58/58 Passed (100%)**.

---

## Project 2: DA-03 | Retail & Supply Chain Control Tower

### 1. Executive Summary
The Control Tower platform centralizes operational visibility across e-commerce commercial logistics, regional distribution centers, safety inventory buffers, and inbound supplier replenishment consignments. Built on top of the real-world **Olist Brazilian commercial dataset** (99,441 orders, 112,650 sales records, 32,951 SKUs, and 3,095 sellers), it continuously audits inventory health, identifies transit anomalies, projects forward demand, and simulates network shocks.

### 2. Core Modules & Innovations
- **Centralized Operational Data Store (PostgreSQL):** 13 relational tables in schema `control_tower` with full constraints and foreign keys.
- **Executive KPI Engine:** Computes the 4 mandatory supply chain metrics directly from relational records:
  - **Stockout Rate (0.0% – 14.2%):** Tracking active SKUs with zero stock under positive demand.
  - **On-Time Delivery Rate (91.88%):** Carrier compliance against estimated SLA promises.
  - **Supplier Lead Time (9.24 Days):** Mean freight transit time across continental Brazil.
  - **Days of Inventory (68.33 Days):** Network safety buffer runway based on trailing 30-day run-rate demand.
- **Consensus Anomaly Detection Engine:** Evaluates deviations across 4 operational dimensions (Demand Spikes, Delivery Delays, Inventory Depletions, Abnormal Lead Times) combining **Parametric Z-Score** ($|Z| \ge 3.0$) and **Isolation Forest** ($\text{contamination} = 0.05$). Flagged **3,490 active anomalies**.
- **Demand Forecasting Engine:** 7-day forward daily demand projection with 80% credible uncertainty intervals (`yhat_lower`, `yhat_upper`). Validated against an out-of-sample holdout test split (**MAE: 1.26 units/day, RMSE: 1.61 units/day, MAPE: 14.62%**). Compares forecasted demand against warehouse stock to trigger proactive replenishment.
- **What-If Disruption Simulator:** Interactive shock modeling simulating 1–30 day inbound supplier delays (labor strikes, customs holds), projecting stockout acceleration, shortage units, and revenue at risk.
- **Automated Alerts:** Dispatches structured Slack Block Kit and SMTP HTML email alerts with actual vs. threshold values and managerial mitigation steps.
- **Interactive Control Tower Dashboard (`dashboard_app.py`):** Production Streamlit application connected directly to PostgreSQL with 6 live views: Executive Summary, Warehouse Inventory, Shipments & Logistics, Demand Forecasting, Operational Incidents, and Disruption Simulator.

### 3. Quick Run Instructions
```bash
cd DA-03-Retail-Supply-Chain-Control-Tower

# Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env

# Run database pipeline and load tables
python src/data_ingestion.py
python src/kpi_calculation.py
python src/anomaly_detection.py
python src/demand_forecasting.py
python src/what_if_analysis.py
python src/alerts.py

# Launch interactive web dashboard
streamlit run dashboard_app.py

# Run integration test suite
pytest tests/ -v
```
*Test suite status:* **16/16 Passed (100%)**.

---

## Verification & Test Results

Both projects feature comprehensive automated test suites verifying schema integrity, data hygiene, mathematical correctness, and machine learning components:

```text
========================================================================================
PROJECT DA-02: Customer 360 & Marketing Attribution Platform
tests/test_data_generator.py::test_generator_is_deterministic PASSED              [14%]
tests/test_data_generator.py::test_referential_integrity PASSED                   [28%]
tests/test_data_generator.py::test_every_order_has_a_purchase_event PASSED        [42%]
tests/test_markov.py::test_single_channel_gets_all_credit PASSED                  [57%]
tests/test_markov.py::test_credit_sums_to_totals PASSED                           [71%]
tests/test_markov.py::test_channel_that_never_converts_gets_no_credit PASSED      [85%]
tests/test_markov.py::test_baseline_probability_matches_observed_rate PASSED      [100%]
================================ 7 passed in 1.78s ====================================

========================================================================================
PROJECT DA-03: Retail & Supply Chain Control Tower
tests/test_pipeline.py::TestDatabaseAndSchema::test_schema_sql_exists PASSED      [ 6%]
tests/test_pipeline.py::TestDatabaseAndSchema::test_sample_queries_sql_exists PASSED [12%]
tests/test_pipeline.py::TestDataCleaning::test_clean_files_exist PASSED           [18%]
tests/test_pipeline.py::TestDataCleaning::test_orders_date_parsing PASSED         [25%]
tests/test_pipeline.py::TestDataCleaning::test_products_category_translation PASSED [31%]
tests/test_pipeline.py::TestDuplicateHandling::test_products_pk_uniqueness PASSED [37%]
tests/test_pipeline.py::TestDuplicateHandling::test_reviews_synthetic_pk PASSED  [43%]
tests/test_pipeline.py::TestKPICalculations::test_kpi_calculation_logic PASSED    [50%]
tests/test_pipeline.py::TestAnomalyDetection::test_severity_classification PASSED [56%]
tests/test_pipeline.py::TestAnomalyDetection::test_isolation_forest_execution PASSED [62%]
tests/test_pipeline.py::TestDemandForecasting::test_forecast_accuracy_evaluation PASSED [68%]
tests/test_pipeline.py::TestDemandForecasting::test_prophet_series_preparation PASSED [75%]
tests/test_pipeline.py::TestWhatIfAnalysis::test_simulation_module_importable PASSED [81%]
tests/test_pipeline.py::TestAlertSystem::test_alert_config_loading PASSED         [87%]
tests/test_pipeline.py::TestAlertSystem::test_alert_payload_formatting PASSED     [93%]
tests/test_pipeline.py::TestAirflowDAG::test_dag_file_syntax PASSED              [100%]
================================ 16 passed in 34.47s ==================================
```

---

## Submission Notes for Technical Evaluator

- **Repository Visibility:** Public
- **GitHub Repository URL:** `https://github.com/Revanth-4233/nexvia-internship-submission`
- **Primary Contacts:** Mukesh Revanth (mukeshrevanth94@gmail.com)
- **Live Local Control Tower:** Runs on `http://localhost:8501` via `streamlit run dashboard_app.py`
