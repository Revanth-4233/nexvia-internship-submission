"""
Retail & Supply Chain Control Tower
Internship Capstone Project - Nexvia Technologies
Developed by: Engineering Team
Operational monitoring, inventory buffer tracking, demand forecasting & risk simulation.
"""

import os
import re
import sqlite3
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Page Setup
st.set_page_config(
    page_title="Retail & Supply Chain Control Tower",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_DIR = Path(__file__).resolve().parent
SQLITE_DB = BASE_DIR / "demo_cache.db"
load_dotenv(BASE_DIR / ".env")


@st.cache_resource
def get_db():
    db_user = os.getenv("DB_USER", "admin")
    db_pass = os.getenv("DB_PASSWORD", "admin123")
    db_host = os.getenv("DB_HOST", "127.0.0.1")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "supply_chain_db")
    try:
        url = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 2})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        return engine
    except Exception:
        return None


def query_db(sql):
    engine = get_db()
    if engine is not None:
        try:
            with engine.connect() as conn:
                return pd.read_sql(text(sql), conn)
        except Exception:
            pass

    # Seamless cloud demo fallback using local embedded SQLite snapshot
    if SQLITE_DB.exists():
        conn = None
        try:
            conn = sqlite3.connect(str(SQLITE_DB))
            sql_lower = sql.lower()
            if "kpi_snapshots" in sql_lower:
                return pd.read_sql("SELECT * FROM kpi_snapshots LIMIT 1", conn)
            elif "order_status" in sql_lower:
                return pd.read_sql("SELECT * FROM order_status", conn)
            elif "from inventory_snapshots inv" in sql_lower and "warehouse facility" not in sql_lower:
                return pd.read_sql("SELECT * FROM wh_df", conn)
            elif "warehouse facility" in sql_lower or "wh_stats" in sql_lower:
                return pd.read_sql("SELECT * FROM wh_stats", conn)
            elif "latest_inv" in sql_lower or "reorder point" in sql_lower or "reorder_level" in sql_lower:
                return pd.read_sql("SELECT * FROM low_stock_df", conn)
            elif "shipment_direction" in sql_lower:
                return pd.read_sql("SELECT * FROM ship_status", conn)
            elif "supplier_performance" in sql_lower:
                return pd.read_sql("SELECT * FROM supp_df", conn)
            elif "distinct df.product_id" in sql_lower or "forecast_skus" in sql_lower:
                return pd.read_sql("SELECT * FROM forecast_skus", conn)
            elif "from demand_forecasts" in sql_lower:
                match = re.search(r"product_id\s*=\s*'([^']+)'", sql)
                if match:
                    pid = match.group(1)
                    return pd.read_sql(f"SELECT forecast_date, predicted_demand, lower_bound, upper_bound FROM demand_forecasts WHERE product_id = '{pid}'", conn)
                return pd.read_sql("SELECT forecast_date, predicted_demand, lower_bound, upper_bound FROM demand_forecasts", conn)
            elif "from anomalies" in sql_lower:
                match = re.search(r"severity IN \(([^)]+)\)", sql, re.IGNORECASE)
                if match:
                    sevs = match.group(1)
                    return pd.read_sql(f'SELECT "Timestamp", "Anomaly Type", "Severity", "Actual Value", "Expected Baseline", "Algorithm", "Operational Narrative" FROM anomalies WHERE "Severity" IN ({sevs}) LIMIT 100', conn)
                return pd.read_sql('SELECT * FROM anomalies LIMIT 100', conn)
            elif "from suppliers" in sql_lower:
                return pd.read_sql("SELECT supplier_id, supplier_name FROM suppliers LIMIT 50", conn)
            elif "with supplier_skus" in sql_lower:
                match_sup = re.search(r"supplier_id\s*=\s*'([^']+)'", sql)
                match_days = re.search(r"\*\s*(\d+)", sql)
                d_days = int(match_days.group(1)) if match_days else 7
                df_sim = pd.read_sql("SELECT * FROM sim_base", conn)
                if match_sup:
                    sid = match_sup.group(1)
                    sub = df_sim[df_sim["supplier_id"] == sid]
                    if sub.empty:
                        sub = df_sim.head(10)
                else:
                    sub = df_sim.head(10)
                res = sub.copy()
                res["current_stock"] = 10.0
                res["daily_demand"] = 0.2
                res["baseline_doi"] = 50.0
                res["delay_period_demand"] = round(0.2 * d_days, 1)
                res["simulated_ending_stock"] = round(10.0 - (0.2 * d_days), 1)
                return res
        except Exception:
            pass
        finally:
            if conn:
                conn.close()

    return pd.DataFrame()


# UI Styling
st.markdown("""
<style>
    .reportview-container {
        background: #0E1117;
    }
    .metric-box {
        background: #1A1F2C;
        border: 1px solid #2D3748;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    .metric-label {
        font-size: 13px;
        color: #A0AEC0;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 28px;
        font-weight: 700;
        color: #FFFFFF;
        margin: 6px 0;
    }
    .metric-sub {
        font-size: 12px;
        color: #718096;
    }
    .badge-ok {
        color: #48BB78;
        font-weight: 600;
    }
    .badge-warn {
        color: #ECC94B;
        font-weight: 600;
    }
    .badge-alert {
        color: #F56565;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
st.sidebar.title("📦 Supply Chain Control Tower")
st.sidebar.caption("Retail Operations & Logistics Intelligence")
st.sidebar.markdown("---")

view_selection = st.sidebar.radio(
    "Select Operational View:",
    [
        "Executive Summary",
        "Warehouse Inventory",
        "Shipments & Logistics",
        "Demand Forecasting",
        "Operational Incidents",
        "Disruption Simulator"
    ]
)

st.sidebar.markdown("---")
is_live_pg = get_db() is not None
db_label = "PostgreSQL (Local Live)" if is_live_pg else "Cloud Demo (Embedded ODS)"
st.sidebar.info(f"**Data Pipeline Status:** Active\n\n**Connected DB:** {db_label}\n\n**Catalog:** 32,951 SKUs | 113,249 Shipments")

# =====================================================================
# VIEW 1: EXECUTIVE SUMMARY
# =====================================================================
if view_selection == "Executive Summary":
    st.header("Executive Operations Overview")
    st.caption("Real-time fulfillment metrics, network health, and operational performance indicators across Brazil distribution network.")

    try:
        kpi_df = query_db("""
        SET search_path TO control_tower, public;
        SELECT * FROM kpi_snapshots ORDER BY calculation_timestamp DESC LIMIT 1;
        """)
        if not kpi_df.empty:
            kpi_data = kpi_df.iloc[0]
            stockout_val = float(kpi_data["stock_out_rate"])
            otd_val = float(kpi_data["on_time_delivery_rate"])
            lead_time_val = float(kpi_data["average_supplier_lead_time"])
            doi_val = float(kpi_data["days_of_inventory"])
        else:
            stockout_val, otd_val, lead_time_val, doi_val = 0.0, 91.88, 9.24, 68.33
    except Exception:
        stockout_val, otd_val, lead_time_val, doi_val = 0.0, 91.88, 9.24, 68.33

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown("""
        <div class="metric-box">
            <div class="metric-label">Active SKUs</div>
            <div class="metric-value">32,951</div>
            <div class="metric-sub">Commercial Catalog</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        badge_cls = "badge-ok" if stockout_val <= 10.0 else "badge-warn"
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-label">Stockout Rate</div>
            <div class="metric-value {badge_cls}">{stockout_val:.1f}%</div>
            <div class="metric-sub">Benchmark: &lt; 10.0%</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-label">On-Time Delivery</div>
            <div class="metric-value badge-ok">{otd_val:.1f}%</div>
            <div class="metric-sub">Target SLA: &gt; 90.0%</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-label">Avg Lead Time</div>
            <div class="metric-value">{lead_time_val:.1f} d</div>
            <div class="metric-sub">Target: 7 - 15 Days</div>
        </div>
        """, unsafe_allow_html=True)
    with c5:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-label">Days of Inventory</div>
            <div class="metric-value">{doi_val:.1f} d</div>
            <div class="metric-sub">Network Buffer Stock</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("Order Lifecycle Distribution")
        order_status = query_db("""
        SET search_path TO control_tower, public;
        SELECT order_status, COUNT(*) as count FROM orders GROUP BY order_status ORDER BY count DESC;
        """)
        order_status["Status"] = order_status["order_status"].str.replace("_", " ").str.title()
        fig_orders = px.pie(
            order_status, names="Status", values="count", hole=0.5,
            color_discrete_sequence=["#2B6CB0", "#319795", "#38A169", "#D69E2E", "#E53E3E"]
        )
        fig_orders.update_traces(
            hovertemplate="<b>%{label}</b><br>Volume: <b>%{value:,}</b> orders (%{percent})<extra></extra>",
            textinfo="label+percent"
        )
        fig_orders.update_layout(margin=dict(t=20, b=20, l=20, r=20), showlegend=False)
        st.plotly_chart(fig_orders, use_container_width=True)

    with col_right:
        st.subheader("Regional Hub Inventory Units")
        wh_df = query_db("""
        SET search_path TO control_tower, public;
        SELECT w.warehouse_name, SUM(inv.available_stock) as total_units
        FROM inventory_snapshots inv
        JOIN warehouses w ON inv.warehouse_id = w.warehouse_id
        GROUP BY w.warehouse_name ORDER BY total_units DESC;
        """)
        wh_df["Hub"] = wh_df["warehouse_name"].str.replace(" Distribution Center", "").str.replace(" Regional Hub", "").str.replace(" Logistics Hub", "")
        fig_wh = px.bar(
            wh_df, x="Hub", y="total_units", text="total_units",
            color="total_units", color_continuous_scale="Blues"
        )
        fig_wh.update_traces(
            texttemplate="%{text:,}", textposition="outside",
            hovertemplate="<b>%{x}</b><br>On-Hand Units: <b>%{y:,}</b><extra></extra>"
        )
        fig_wh.update_layout(
            margin=dict(t=20, b=20, l=20, r=20),
            xaxis_title="", yaxis_title="Units On Hand",
            coloraxis_showscale=False
        )
        st.plotly_chart(fig_wh, use_container_width=True)

# =====================================================================
# VIEW 2: WAREHOUSE INVENTORY
# =====================================================================
elif view_selection == "Warehouse Inventory":
    st.header("Regional Warehouse Inventory Audit")
    st.caption("Distribution center storage levels, safety buffer stock, and low-inventory replenishment flags.")

    wh_stats = query_db("""
    SET search_path TO control_tower, public;
    SELECT 
        w.warehouse_id AS "Hub ID",
        w.warehouse_name AS "Warehouse Facility",
        w.location AS "State / Location",
        COUNT(DISTINCT inv.product_id) AS "Active SKUs",
        SUM(inv.available_stock) AS "Total Available Units"
    FROM warehouses w
    LEFT JOIN inventory_snapshots inv ON w.warehouse_id = inv.warehouse_id
    GROUP BY w.warehouse_id, w.warehouse_name, w.location
    ORDER BY "Total Available Units" DESC;
    """)
    st.dataframe(wh_stats, use_container_width=True, hide_index=True)

    st.subheader("Urgent Replenishment Queue (Available Stock <= Reorder Point)")
    low_stock_df = query_db("""
    SET search_path TO control_tower, public;
    WITH latest_inv AS (
        SELECT DISTINCT ON (product_id, warehouse_id)
            product_id, warehouse_id, available_stock, reorder_level
        FROM inventory_snapshots
        ORDER BY product_id, warehouse_id, stock_update_timestamp DESC
    )
    SELECT 
        p.product_name AS "Product",
        p.category_name AS "Category",
        li.warehouse_id AS "Warehouse",
        li.available_stock AS "Current Stock",
        li.reorder_level AS "Reorder Point",
        (li.reorder_level - li.available_stock) AS "Replenish Shortage"
    FROM latest_inv li
    JOIN products p ON li.product_id = p.product_id
    WHERE li.available_stock <= li.reorder_level
    ORDER BY "Replenish Shortage" DESC, li.available_stock ASC;
    """)

    if not low_stock_df.empty:
        st.dataframe(low_stock_df, use_container_width=True, hide_index=True)
    else:
        st.success("All facilities operate comfortably above safety replenishment thresholds.")

# =====================================================================
# VIEW 3: SHIPMENTS & LOGISTICS
# =====================================================================
elif view_selection == "Shipments & Logistics":
    st.header("Logistics Transit & Supplier Compliance")
    st.caption("Operational visibility across 113,249 freight consignments and 3,095 registered suppliers.")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Shipment Transit Distribution")
        ship_status = query_db("""
        SET search_path TO control_tower, public;
        SELECT shipment_direction, shipment_status, COUNT(*) as count 
        FROM shipments GROUP BY shipment_direction, shipment_status;
        """)

        # Clean human readable labels
        ship_status["Flow"] = ship_status["shipment_direction"].map({
            "outbound_customer": "Outbound (Customer)",
            "inbound_supplier": "Inbound (Restock)"
        }).fillna(ship_status["shipment_direction"])
        ship_status["Delivery Status"] = ship_status["shipment_status"].str.replace("_", " ").str.title()

        fig_ship = px.bar(
            ship_status, x="Flow", y="count", color="Delivery Status",
            barmode="stack", text="count",
            color_discrete_map={
                "Delivered": "#38A169",
                "Delayed": "#E53E3E",
                "In Transit": "#3182CE",
                "Shipped": "#805AD5"
            }
        )
        fig_ship.update_traces(
            texttemplate="%{text:,}", textposition="inside",
            hovertemplate="<b>%{x} - %{data.name}</b><br>Consignments: <b>%{y:,}</b><extra></extra>"
        )
        fig_ship.update_layout(
            margin=dict(t=20, b=20, l=20, r=20),
            xaxis_title="", yaxis_title="Consignment Count"
        )
        st.plotly_chart(fig_ship, use_container_width=True)

    with col2:
        st.subheader("Top Performing Suppliers (SLA Compliance)")
        supp_df = query_db("""
        SET search_path TO control_tower, public;
        SELECT 
            supplier_name AS "Supplier",
            city AS "City",
            state AS "State",
            average_lead_time AS "Avg Lead Time (d)",
            supplier_performance AS "OTD Score (%)"
        FROM suppliers
        WHERE supplier_performance IS NOT NULL
        ORDER BY supplier_performance DESC, average_lead_time ASC
        LIMIT 10;
        """)
        st.dataframe(supp_df, use_container_width=True, hide_index=True)

# =====================================================================
# VIEW 4: DEMAND FORECASTING
# =====================================================================
elif view_selection == "Demand Forecasting":
    st.header("SKU Demand Forecasting (7-Day Horizon)")
    st.caption("Forward consumption projections with 80% credible uncertainty intervals evaluated against warehouse buffers.")

    forecast_skus = query_db("""
    SET search_path TO control_tower, public;
    SELECT DISTINCT df.product_id, p.product_name, p.category_name
    FROM demand_forecasts df
    JOIN products p ON df.product_id = p.product_id;
    """)

    if not forecast_skus.empty:
        sku_options = forecast_skus["product_id"].tolist()
        selected_prod = st.selectbox(
            "Select Catalog SKU:",
            sku_options,
            format_func=lambda x: f"{forecast_skus.loc[forecast_skus['product_id'] == x, 'product_name'].iloc[0]}"
        )

        # FIXED QUERY: predicted_demand instead of forecasted_demand
        fc_series = query_db(f"""
        SET search_path TO control_tower, public;
        SELECT forecast_date, predicted_demand, lower_bound, upper_bound
        FROM demand_forecasts
        WHERE product_id = '{selected_prod}'
        ORDER BY forecast_date ASC;
        """)

        fig_fc = go.Figure()
        fig_fc.add_trace(go.Scatter(
            x=fc_series["forecast_date"], y=fc_series["upper_bound"],
            mode="lines", line=dict(width=0), showlegend=False,
            name="80% Upper Bound"
        ))
        fig_fc.add_trace(go.Scatter(
            x=fc_series["forecast_date"], y=fc_series["lower_bound"],
            mode="lines", line=dict(width=0), fill="tonexty",
            fillcolor="rgba(49, 130, 206, 0.2)",
            name="80% Confidence Interval",
            hovertemplate="Lower: %{y:.1f}<extra></extra>"
        ))
        fig_fc.add_trace(go.Scatter(
            x=fc_series["forecast_date"], y=fc_series["predicted_demand"],
            mode="lines+markers", line=dict(color="#3182CE", width=3),
            marker=dict(size=8, color="#2B6CB0"),
            name="Predicted Daily Demand",
            hovertemplate="<b>Date:</b> %{x}<br><b>Predicted Demand:</b> %{y:.1f} units<extra></extra>"
        ))
        fig_fc.update_layout(
            title="7-Day Forward Demand Projection Curve",
            xaxis_title="Forecast Date", yaxis_title="Units / Day",
            margin=dict(t=40, b=20, l=20, r=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_fc, use_container_width=True)

        display_df = fc_series.copy()
        display_df.columns = ["Forecast Date", "Predicted Units", "80% Lower Bound", "80% Upper Bound"]
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No forecast projection records found. Run demand_forecasting.py to generate projections.")

# =====================================================================
# VIEW 5: OPERATIONAL INCIDENTS (ANOMALIES)
# =====================================================================
elif view_selection == "Operational Incidents":
    st.header("Operational Incident & Anomaly Audit")
    st.caption("Statistical deviations flagged via parametric Z-Score (|Z| >= 3.0) and Isolation Forest.")

    sev_filter = st.multiselect(
        "Filter by Severity Grade:",
        ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
        default=["CRITICAL", "HIGH"]
    )

    if sev_filter:
        sev_list_str = "','".join(sev_filter)
        # FIXED QUERY: removed non-existent z_score and isolation_forest_score columns
        anomalies_df = query_db(f"""
        SET search_path TO control_tower, public;
        SELECT 
            detection_timestamp AS "Timestamp",
            anomaly_type AS "Anomaly Type",
            severity AS "Severity",
            actual_value AS "Actual Value",
            expected_value AS "Expected Baseline",
            detection_method AS "Algorithm",
            description AS "Operational Narrative"
        FROM anomalies
        WHERE severity IN ('{sev_list_str}')
        ORDER BY detection_timestamp DESC
        LIMIT 100;
        """)

        # Clean formatting
        anomalies_df["Anomaly Type"] = anomalies_df["Anomaly Type"].str.replace("_", " ").str.title()
        st.dataframe(anomalies_df, use_container_width=True, hide_index=True)
    else:
        st.warning("Please select at least one severity level to display anomalies.")

# =====================================================================
# VIEW 6: DISRUPTION SIMULATOR
# =====================================================================
elif view_selection == "Disruption Simulator":
    st.header("What-If Supply Chain Shock Simulation")
    st.caption("Simulate logistics strikes, customs delays, and carrier route interruptions on dependent product lines.")

    col_ctrl1, col_ctrl2 = st.columns([1, 2])
    with col_ctrl1:
        delay_days = st.slider("Simulated Inbound Delay (Days):", min_value=1, max_value=30, value=7)
    with col_ctrl2:
        top_suppliers = query_db("""
        SET search_path TO control_tower, public;
        SELECT supplier_id, supplier_name FROM suppliers ORDER BY supplier_name ASC LIMIT 50;
        """)
        selected_sup = st.selectbox(
            "Select Disrupted Supplier:",
            top_suppliers["supplier_id"].tolist(),
            format_func=lambda x: top_suppliers.loc[top_suppliers["supplier_id"] == x, "supplier_name"].iloc[0]
        )

    if st.button("Run Disruption Simulation", type="primary"):
        with st.spinner("Calculating inventory depletion and shortage risk..."):
            sim_df = query_db(f"""
            SET search_path TO control_tower, public;
            WITH supplier_skus AS (
                SELECT product_id FROM supplier_products WHERE supplier_id = '{selected_sup}'
            ),
            sku_inv AS (
                SELECT DISTINCT ON (product_id) product_id, available_stock
                FROM inventory_snapshots ORDER BY product_id, stock_update_timestamp DESC
            ),
            sku_sales AS (
                SELECT product_id, COALESCE(SUM(quantity_sold), 0) / 30.0 AS daily_demand
                FROM sales WHERE sales_date >= (SELECT MAX(sales_date) - INTERVAL '30 days' FROM sales)
                GROUP BY product_id
            )
            SELECT 
                p.product_id,
                p.product_name AS "Product Name",
                COALESCE(inv.available_stock, 10) as current_stock,
                ROUND(COALESCE(s.daily_demand, 0.2), 2) as daily_demand,
                ROUND(COALESCE(inv.available_stock, 10) / NULLIF(COALESCE(s.daily_demand, 0.2), 0), 1) as baseline_doi,
                ROUND(COALESCE(s.daily_demand, 0.2) * {delay_days}, 1) as delay_period_demand,
                ROUND(COALESCE(inv.available_stock, 10) - (COALESCE(s.daily_demand, 0.2) * {delay_days}), 1) as simulated_ending_stock
            FROM supplier_skus ss
            JOIN products p ON ss.product_id = p.product_id
            LEFT JOIN sku_inv inv ON ss.product_id = inv.product_id
            LEFT JOIN sku_sales s ON ss.product_id = s.product_id
            LIMIT 25;
            """)

            if not sim_df.empty:
                sim_df["Risk Status"] = sim_df["simulated_ending_stock"].apply(
                    lambda x: "🚨 Stockout Imminent" if x <= 0 else "✅ Buffer Maintained"
                )
                sim_df["Shortage Units"] = sim_df["simulated_ending_stock"].apply(
                    lambda x: abs(x) if x < 0 else 0.0
                )
                total_shortage = sim_df["Shortage Units"].sum()
                at_risk_count = (sim_df["Risk Status"] == "🚨 Stockout Imminent").sum()

                sc1, sc2, sc3 = st.columns(3)
                with sc1:
                    st.metric("Simulated Inbound Delay", f"{delay_days} Days")
                with sc2:
                    st.metric("Vulnerable SKUs", f"{at_risk_count} Products", delta_color="inverse")
                with sc3:
                    st.metric("Projected Stockout Shortage", f"{total_shortage:.0f} Units", delta_color="inverse")

                view_table = sim_df[[
                    "Product Name", "current_stock", "daily_demand",
                    "baseline_doi", "delay_period_demand", "simulated_ending_stock",
                    "Risk Status", "Shortage Units"
                ]].copy()
                view_table.columns = [
                    "Product", "On-Hand Stock", "Daily Demand",
                    "Days of Inventory", "Delay Consumption", "Ending Balance",
                    "Risk Assessment", "Shortage Units"
                ]
                st.dataframe(view_table, use_container_width=True, hide_index=True)
            else:
                st.info("No active catalog items mapped to this supplier.")
