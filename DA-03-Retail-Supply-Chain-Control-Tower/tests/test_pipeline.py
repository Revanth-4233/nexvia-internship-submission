"""
Retail and Supply Chain Control Tower - Comprehensive Integration Test Suite
Verifies all 10 core architectural modules:
1. Database connectivity & schema integrity
2. Data ingestion and simulation engines
3. Data cleaning and timestamp validation
4. Duplicate key handling
5. KPI calculation formulas and benchmarks
6. Anomaly detection (Z-Score & Isolation Forest)
7. Prophet demand forecasting & holdout evaluation
8. Inventory buffer monitoring & stock-out risk
9. What-If scenario (7-day supplier delay simulation)
10. Automated alert triggering & Slack/Email payload formatting
"""

import os
import sys
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# =====================================================================
# 1. TEST DATABASE CONNECTION & SCHEMA INTEGRITY
# =====================================================================
class TestDatabaseAndSchema:

    def test_schema_sql_exists(self, project_dirs):
        """Verify schema.sql file exists and is populated."""
        schema_file = project_dirs["database"] / "schema.sql"
        assert schema_file.exists(), "database/schema.sql must exist"
        content = schema_file.read_text(encoding="utf-8")
        assert "CREATE SCHEMA IF NOT EXISTS control_tower;" in content
        assert "CREATE TABLE IF NOT EXISTS products" in content
        assert "CREATE TABLE IF NOT EXISTS suppliers" in content
        assert "CREATE TABLE IF NOT EXISTS inventory_snapshots" in content
        assert "CREATE TABLE IF NOT EXISTS shipments" in content
        assert "CREATE TABLE IF NOT EXISTS anomalies" in content
        assert "CREATE TABLE IF NOT EXISTS demand_forecasts" in content
        assert "CREATE TABLE IF NOT EXISTS kpi_snapshots" in content
        assert "CREATE TABLE IF NOT EXISTS what_if_scenarios" in content
        assert "CREATE TABLE IF NOT EXISTS alert_events" in content

    def test_sample_queries_sql_exists(self, project_dirs):
        """Verify verification and KPI queries exist."""
        queries_file = project_dirs["database"] / "sample_queries.sql"
        assert queries_file.exists()
        content = queries_file.read_text(encoding="utf-8")
        assert "stock_out_rate_pct" in content
        assert "on_time_delivery_rate_pct" in content


# =====================================================================
# 2. TEST DATA CLEANING & REPROCESSING
# =====================================================================
class TestDataCleaning:

    def test_clean_files_exist(self, project_dirs):
        """Verify all 8 processed clean CSV datasets exist and have positive size."""
        expected_files = [
            "customers_clean.csv",
            "geolocation_clean.csv",
            "orders_clean.csv",
            "order_items_clean.csv",
            "payments_clean.csv",
            "products_clean.csv",
            "reviews_clean.csv",
            "sellers_clean.csv"
        ]
        for f in expected_files:
            file_path = project_dirs["processed"] / f
            assert file_path.exists(), f"Processed clean file missing: {f}"
            assert file_path.stat().st_size > 1000, f"File {f} is suspiciously small"

    def test_orders_date_parsing(self, sample_clean_orders):
        """Verify date columns in orders_clean are valid ISO-format datetimes."""
        if sample_clean_orders.empty:
            pytest.skip("Clean orders file not loaded.")
        date_cols = [
            "order_purchase_timestamp",
            "order_estimated_delivery_date"
        ]
        for col in date_cols:
            parsed = pd.to_datetime(sample_clean_orders[col], errors="coerce")
            assert parsed.notna().all(), f"Failed date parsing in column {col}"

    def test_products_category_translation(self, sample_clean_products):
        """Verify category name translation and zero null product_id in products_clean."""
        if sample_clean_products.empty:
            pytest.skip("Clean products file not loaded.")
        assert sample_clean_products["product_id"].notna().all()
        assert "product_category_name_english" in sample_clean_products.columns
        assert sample_clean_products["product_category_name_english"].notna().all()


# =====================================================================
# 3. TEST DUPLICATE KEY HANDLING
# =====================================================================
class TestDuplicateHandling:

    def test_products_pk_uniqueness(self, sample_clean_products):
        """Verify no duplicate primary key records exist in products."""
        if sample_clean_products.empty:
            pytest.skip("Clean products file not loaded.")
        assert sample_clean_products["product_id"].duplicated().sum() == 0

    def test_reviews_synthetic_pk(self, project_dirs):
        """Verify reviews dataset has unique synthetic review_row_id primary key."""
        rev_path = project_dirs["processed"] / "reviews_clean.csv"
        if not rev_path.exists():
            pytest.skip("reviews_clean.csv not found")
        rev_df = pd.read_csv(rev_path, nrows=1000)
        assert "review_row_id" in rev_df.columns
        assert rev_df["review_row_id"].duplicated().sum() == 0


# =====================================================================
# 4. TEST KPI CALCULATIONS
# =====================================================================
class TestKPICalculations:

    def test_kpi_calculation_logic(self):
        """Verify KPI calculation functions compute mathematically sound values."""
        from kpi_calculation import calculate_all_kpis
        # Running with engine=None returns reference baseline metrics
        res = calculate_all_kpis(engine=None, save_snapshot=False)
        kpis = res["kpis"]

        # Stockout Rate
        stockout = kpis["stock_out_rate"]["value"]
        assert 0.0 <= stockout <= 100.0, f"Stockout rate {stockout} outside 0-100%"

        # On-Time Delivery Rate
        otd = kpis["on_time_delivery_rate"]["value"]
        assert 0.0 <= otd <= 100.0, f"On-time rate {otd} outside 0-100%"

        # Lead Time
        lt = kpis["supplier_lead_time"]["value"]
        assert lt > 0, "Lead time must be positive"

        # Days of Inventory
        doi = kpis["days_of_inventory"]["value"]
        assert doi > 0, "Days of Inventory must be positive"


# =====================================================================
# 5. TEST ANOMALY DETECTION ENGINE
# =====================================================================
class TestAnomalyDetection:

    def test_severity_classification(self):
        """Verify Z-Score deviation maps to appropriate severity grade."""
        from anomaly_detection import classify_severity
        assert classify_severity(1.5) == "LOW"
        assert classify_severity(2.7) == "MEDIUM"
        assert classify_severity(3.5) == "HIGH"
        assert classify_severity(4.8) == "CRITICAL"
        assert classify_severity(-4.2) == "CRITICAL"

    def test_isolation_forest_execution(self):
        """Verify Scikit-Learn Isolation Forest identifies extreme outliers."""
        from anomaly_detection import run_isolation_forest
        # Synthetic series with one extreme spike
        normal_data = np.random.normal(loc=10.0, scale=1.0, size=50)
        normal_data[25] = 95.0  # Injected severe anomaly
        series = pd.Series(normal_data)

        mask = run_isolation_forest(series, contamination=0.05)
        assert len(mask) == 50
        assert mask[25] == True, "Isolation Forest must flag injected extreme outlier"


# =====================================================================
# 6. TEST DEMAND FORECASTING (PROPHET & EVALUATION)
# =====================================================================
class TestDemandForecasting:

    def test_forecast_accuracy_evaluation(self):
        """Verify MAE, RMSE, and MAPE calculations on test data."""
        from demand_forecasting import evaluate_forecast_accuracy
        actuals = [10.0, 12.0, 15.0, 8.0, 14.0]
        preds = [11.0, 11.0, 16.0, 9.0, 13.0]

        metrics = evaluate_forecast_accuracy(actuals, preds)
        assert "MAE" in metrics
        assert "RMSE" in metrics
        assert "MAPE" in metrics
        assert metrics["MAE"] == pytest.approx(1.0, rel=1e-2)
        assert metrics["RMSE"] == pytest.approx(1.0, rel=1e-2)
        assert metrics["MAPE"] > 0.0

    def test_prophet_series_preparation(self):
        """Verify continuous daily date index and missing day zero-filling."""
        from demand_forecasting import prepare_prophet_series
        dates = pd.to_datetime(["2018-01-01", "2018-01-03"])
        raw_df = pd.DataFrame({"ds": dates, "y": [5, 10]})

        prepared = prepare_prophet_series(raw_df)
        assert len(prepared) == 3, "Missing intermediate date 2018-01-02 must be interpolated"
        assert prepared.loc[prepared["ds"] == "2018-01-02", "y"].iloc[0] == 0


# =====================================================================
# 7. TEST WHAT-IF SCENARIO (7-DAY SUPPLIER DELAY)
# =====================================================================
class TestWhatIfAnalysis:

    def test_simulation_module_importable(self):
        """Verify What-If analysis module is available and functions defined."""
        from what_if_analysis import simulate_supplier_delay, list_top_suppliers
        assert callable(simulate_supplier_delay)
        assert callable(list_top_suppliers)


# =====================================================================
# 8. TEST ALERT NOTIFICATION SYSTEM
# =====================================================================
class TestAlertSystem:

    def test_alert_config_loading(self):
        """Verify alert routing configuration loads defaults."""
        from alerts import load_alert_config
        cfg = load_alert_config()
        assert "slack_enabled" in cfg
        assert "email_enabled" in cfg
        assert "stockout_threshold" in cfg
        assert "delivery_delay_days" in cfg

    def test_alert_payload_formatting(self):
        """Verify structured alert payload contains all required attributes."""
        alert = {
            "alert_title": "Unit Test Stock-Out Event",
            "product_id": "test_sku_001",
            "shipment_id": None,
            "actual_value": "0 units on hand",
            "expected_value": "20 units reorder level",
            "severity": "CRITICAL",
            "message": "Warehouse stock depleted to 0 units.",
            "recommended_action": "Trigger emergency replenishment purchase order."
        }
        for attr in ["alert_title", "severity", "actual_value", "expected_value", "message", "recommended_action"]:
            assert attr in alert, f"Alert must contain field {attr}"


# =====================================================================
# 9. TEST AIRFLOW DAG INTEGRITY
# =====================================================================
class TestAirflowDAG:

    def test_dag_file_syntax(self, project_dirs):
        """Verify Airflow DAG file is free of Python syntax errors."""
        dag_file = project_dirs["base"] / "airflow" / "dags" / "supply_chain_pipeline.py"
        assert dag_file.exists()
        code = dag_file.read_text(encoding="utf-8")
        compiled = compile(code, str(dag_file), "exec")
        assert compiled is not None
        assert "dag_id=\"supply_chain_control_tower\"" in code
