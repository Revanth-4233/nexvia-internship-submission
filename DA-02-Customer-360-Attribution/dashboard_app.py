"""
Customer 360 & Marketing Attribution Platform - Interactive Analytical Dashboard
Runs on Streamlit + DuckDB data warehouse.
"""

from __future__ import annotations

import os
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Customer 360 & Marketing Attribution Platform",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Dark Theme Styling
st.markdown(
    """
    <style>
    .main { background-color: #0e1117; color: #e6edf3; }
    .kpi-card {
        background: linear-gradient(135deg, #161b22 0%, #1f242c 100%);
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 12px;
    }
    .kpi-title { font-size: 13px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; }
    .kpi-val { font-size: 26px; font-weight: 700; color: #f0f6fc; margin: 4px 0; }
    .kpi-sub { font-size: 12px; color: #58a6ff; }
    .stSelectbox label, .stSlider label { color: #c9d1d9 !important; font-weight: 500; }
    hr { border-color: #30363d; }
    </style>
    """,
    unsafe_allow_html=True,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "warehouse.duckdb")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")


@st.cache_resource
def get_db_connection():
    if os.path.exists(DB_PATH):
        try:
            return duckdb.connect(DB_PATH, read_only=True)
        except Exception:
            return None
    return None


@st.cache_data
def query_data(sql: str, fallback_csv: str | None = None) -> pd.DataFrame:
    con = get_db_connection()
    if con:
        try:
            return con.execute(sql).df()
        except Exception:
            pass
    if fallback_csv:
        csv_file = os.path.join(EXPORTS_DIR, fallback_csv)
        if os.path.exists(csv_file):
            return pd.read_csv(csv_file)
    return pd.DataFrame()


# Sidebar Navigation
with st.sidebar:
    st.markdown("## 🎯 Customer 360 & Attribution")
    st.caption("Developed by: Mukesh Revanth | Nexvia Internship")
    st.markdown("---")

    view = st.radio(
        "Navigation Views:",
        [
            "1. Executive Overview & RFM",
            "2. Multi-Touch Attribution Engine",
            "3. Paid Channel ROAS & Spend",
            "4. Customer 360 Profile Explorer",
            "5. Markov Chain Graph & Removal Effects",
        ],
    )

    st.markdown("---")
    st.markdown("### 🛠️ Engineering Highlights")
    st.caption("• **Identity Resolution:** Deterministic matching linking GA4 cookies & Segment IDs to CRM")
    st.caption("• **Data Warehouse:** DuckDB (Local) / BigQuery (Prod)")
    st.caption("• **Transformation:** dbt Core (Staging → Int → Marts)")
    st.caption("• **Data-Driven Attribution:** First-order Markov chain with exact absorbing matrix algebra")
    st.caption("• **Quality Gate:** 77 dbt tests + 7 pytest modules (100% pass)")


# ==============================================================================
# VIEW 1: EXECUTIVE OVERVIEW & RFM
# ==============================================================================
if view == "1. Executive Overview & RFM":
    st.markdown("## 📈 Executive Summary: Customer 360 & Marketing Performance")
    st.markdown("Unified omni-channel customer intelligence across GA4 web sessions, Segment mobile app events, and CRM transactions.")

    customers_df = query_data(
        "SELECT * FROM analytics_marts.dim_customers",
        fallback_csv="dim_customers.csv",
    )
    orders_df = query_data(
        "SELECT * FROM analytics_marts.fct_orders",
        fallback_csv="fct_orders.csv",
    )

    total_customers = len(customers_df)
    multi_device = (
        len(customers_df[(customers_df["web_devices"] > 0) & (customers_df["app_devices"] > 0)])
        if not customers_df.empty else 0
    )
    stitching_pct = (multi_device / total_customers * 100) if total_customers else 0.0

    total_orders = len(orders_df[orders_df["order_status"] == "completed"]) if "order_status" in orders_df.columns else len(orders_df)
    total_rev = orders_df["net_revenue"].sum() if "net_revenue" in orders_df.columns else customers_df["lifetime_revenue"].sum()
    aov = (total_rev / total_orders) if total_orders else 0.0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">Total Unified Profiles</div>
                <div class="kpi-val">{total_customers:,}</div>
                <div class="kpi-sub">GA4 + Segment + CRM Stitched</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">Cross-Device Stitched</div>
                <div class="kpi-val">{multi_device:,} ({stitching_pct:.1f}%)</div>
                <div class="kpi-sub">Web & Mobile Identity Graph</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">Completed Orders</div>
                <div class="kpi-val">{total_orders:,}</div>
                <div class="kpi-sub">AOV: ${aov:,.2f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col4:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">Total Lifetime Revenue</div>
                <div class="kpi-val">${total_rev:,.2f}</div>
                <div class="kpi-sub">Reconciled to Finance Orders</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### 🏆 Customer RFM Segmentation")
        if not customers_df.empty and "rfm_segment" in customers_df.columns:
            rfm_counts = (
                customers_df.groupby("rfm_segment")
                .agg(
                    customers=("customer_key", "count"),
                    avg_ltv=("lifetime_revenue", "mean"),
                    total_rev=("lifetime_revenue", "sum"),
                )
                .reset_index()
                .sort_values(by="total_rev", ascending=False)
            )

            fig_rfm = px.bar(
                rfm_counts,
                x="rfm_segment",
                y="total_rev",
                color="rfm_segment",
                text="total_rev",
                labels={"rfm_segment": "RFM Segment", "total_rev": "Total Revenue ($)"},
                title="Revenue Contribution by RFM Cohort",
                color_discrete_sequence=px.colors.qualitative.Prism,
            )
            fig_rfm.update_traces(
                texttemplate="$%{text:,.0f}",
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>Revenue: $%{y:,.2f}<extra></extra>",
            )
            fig_rfm.update_layout(
                template="plotly_dark",
                showlegend=False,
                height=380,
                margin=dict(l=20, r=20, t=50, b=30),
            )
            st.plotly_chart(fig_rfm, use_container_width=True)

    with c2:
        st.markdown("### 🌐 First-Touch Acquisition Channel vs. LTV")
        if not customers_df.empty and "acquisition_channel" in customers_df.columns:
            acq_df = (
                customers_df.groupby("acquisition_channel")
                .agg(
                    customers=("customer_key", "count"),
                    avg_ltv=("lifetime_revenue", "mean"),
                    total_rev=("lifetime_revenue", "sum"),
                )
                .reset_index()
                .sort_values(by="avg_ltv", ascending=False)
            )

            fig_acq = px.bar(
                acq_df,
                x="acquisition_channel",
                y="avg_ltv",
                text="avg_ltv",
                labels={"acquisition_channel": "Acquisition Channel", "avg_ltv": "Average LTV ($)"},
                title="Average Customer Lifetime Value by First Channel",
                color="avg_ltv",
                color_continuous_scale="Viridis",
            )
            fig_acq.update_traces(
                texttemplate="$%{text:,.2f}",
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>Average LTV: $%{y:,.2f}<extra></extra>",
            )
            fig_acq.update_layout(
                template="plotly_dark",
                coloraxis_showscale=False,
                height=380,
                margin=dict(l=20, r=20, t=50, b=30),
            )
            st.plotly_chart(fig_acq, use_container_width=True)


# ==============================================================================
# VIEW 2: MULTI-TOUCH ATTRIBUTION ENGINE
# ==============================================================================
elif view == "2. Multi-Touch Attribution Engine":
    st.markdown("## ⚖️ Multi-Touch Marketing Attribution Comparison")
    st.markdown(
        "Evaluate how revenue credit shifts across marketing touchpoints when transitioning from biased single-touch rules to algorithmic Markov models."
    )

    attr_long = query_data(
        "SELECT channel, attribution_model, SUM(attributed_revenue) AS attributed_revenue, SUM(credit) AS conversions FROM analytics_marts.fct_attribution_long GROUP BY channel, attribution_model",
        fallback_csv="fct_attribution_long.csv",
    )
    markov_df = query_data(
        "SELECT channel, 'markov' AS attribution_model, attributed_revenue, attributed_conversions AS conversions FROM analytics_marts.markov_channel_attribution",
        fallback_csv="markov_channel_attribution.csv",
    )

    combined_attr = pd.concat([attr_long, markov_df], ignore_index=True)

    available_models = sorted(combined_attr["attribution_model"].unique().tolist())
    selected_model = st.selectbox(
        "Select Attribution Model to Inspect:",
        options=available_models,
        index=available_models.index("markov") if "markov" in available_models else 0,
    )

    model_slice = combined_attr[combined_attr["attribution_model"] == selected_model].sort_values(
        by="attributed_revenue", ascending=False
    )

    total_model_rev = model_slice["attributed_revenue"].sum()
    st.caption(f"Total Attributed Revenue under **{selected_model}**: **${total_model_rev:,.2f}**")

    fig_bar = px.bar(
        model_slice,
        x="channel",
        y="attributed_revenue",
        color="channel",
        text="attributed_revenue",
        labels={"channel": "Marketing Channel", "attributed_revenue": "Attributed Revenue ($)"},
        title=f"Revenue Attribution by Channel — Model: [{selected_model.upper()}]",
        color_discrete_sequence=px.colors.qualitative.Safe,
    )
    fig_bar.update_traces(
        texttemplate="$%{text:,.0f}",
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Revenue Credit: $%{y:,.2f}<extra></extra>",
    )
    fig_bar.update_layout(
        template="plotly_dark",
        showlegend=False,
        height=400,
        margin=dict(l=20, r=20, t=50, b=30),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")
    st.markdown("### 📊 Cross-Model Comparison Matrix (Revenue Shift)")

    pivot_rev = combined_attr.pivot_table(
        index="channel",
        columns="attribution_model",
        values="attributed_revenue",
        aggfunc="sum",
        fill_value=0,
    )

    pivot_pct = pivot_rev.div(pivot_rev.sum(axis=0), axis=1) * 100

    col_a, col_b = st.columns([1, 1])
    with col_a:
        st.markdown("**Revenue Share by Channel (%)**")
        st.dataframe(
            pivot_pct.style.format("{:.1f}%").background_gradient(cmap="Blues", axis=0),
            use_container_width=True,
        )
    with col_b:
        st.markdown("**Absolute Revenue Credit ($ USD)**")
        st.dataframe(
            pivot_rev.style.format("${:,.0f}").background_gradient(cmap="YlGn", axis=0),
            use_container_width=True,
        )


# ==============================================================================
# VIEW 3: PAID CHANNEL ROAS & SPEND
# ==============================================================================
elif view == "3. Paid Channel ROAS & Spend":
    st.markdown("## 💰 Paid Marketing Spend & ROAS Financial Reconciliation")
    st.markdown(
        "Compare actual media investments against attributed order revenue to discover true Return on Ad Spend (ROAS) across models."
    )

    roas_df = query_data(
        "SELECT * FROM analytics_marts.mart_campaign_roas",
        fallback_csv="mart_campaign_roas.csv",
    )

    if not roas_df.empty:
        paid_models = sorted(roas_df["attribution_model"].unique().tolist())
        sel_paid_model = st.selectbox(
            "Select Attribution Model for Campaign ROAS Audit:",
            options=paid_models,
            index=paid_models.index("linear") if "linear" in paid_models else 0,
        )

        filtered_roas = roas_df[roas_df["attribution_model"] == sel_paid_model].sort_values(
            by="roas", ascending=False
        )

        c1, c2, c3, c4 = st.columns(4)
        tot_spend = filtered_roas["spend"].sum()
        tot_attr_rev = filtered_roas["attributed_revenue"].sum()
        blended_roas = (tot_attr_rev / tot_spend) if tot_spend > 0 else 0.0
        tot_conversions = filtered_roas["attributed_conversions"].sum()
        blended_cpa = (tot_spend / tot_conversions) if tot_conversions > 0 else 0.0

        with c1:
            st.metric("Total Paid Media Spend", f"${tot_spend:,.2f}")
        with c2:
            st.metric("Attributed Paid Revenue", f"${tot_attr_rev:,.2f}")
        with c3:
            st.metric("Blended Portfolio ROAS", f"{blended_roas:.2f}x")
        with c4:
            st.metric("Average Paid CPA", f"${blended_cpa:,.2f}")

        st.markdown("---")
        fig_roas = px.bar(
            filtered_roas,
            x="campaign_name",
            y="roas",
            color="roas",
            text="roas",
            labels={"campaign_name": "Ad Campaign", "roas": "ROAS (Revenue / Spend)"},
            title=f"Campaign ROAS Performance [{sel_paid_model.upper()}] (Target: > 2.0x)",
            color_continuous_scale=["#f85149", "#d29922", "#3fb950"],
            color_continuous_midpoint=2.0,
        )
        fig_roas.update_traces(
            texttemplate="%{text:.2f}x",
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>ROAS: %{y:.2f}x<extra></extra>",
        )
        fig_roas.update_layout(template="plotly_dark", height=400)
        st.plotly_chart(fig_roas, use_container_width=True)

        st.markdown("### 📋 Campaign Financial Breakdown")
        display_cols = [
            "platform",
            "campaign_name",
            "channel",
            "spend",
            "attributed_conversions",
            "attributed_revenue",
            "roas",
            "cost_per_conversion",
        ]
        available_display_cols = [c for c in display_cols if c in filtered_roas.columns]

        format_dict = {
            "spend": "${:,.2f}",
            "attributed_revenue": "${:,.2f}",
            "attributed_conversions": "{:,.1f}",
            "roas": "{:.2f}x",
            "cost_per_conversion": "${:,.2f}",
        }
        st.dataframe(
            filtered_roas[available_display_cols].style.format(
                {k: v for k, v in format_dict.items() if k in available_display_cols}
            ),
            use_container_width=True,
        )


# ==============================================================================
# VIEW 4: CUSTOMER 360 PROFILE EXPLORER
# ==============================================================================
elif view == "4. Customer 360 Profile Explorer":
    st.markdown("## 👤 Canonical Customer 360 & Journey Lineage")
    st.markdown(
        "Inspect individual customer profiles with resolved cross-device identity graphs and chronological conversion touchpoints."
    )

    customers_df = query_data(
        "SELECT * FROM analytics_marts.dim_customers",
        fallback_csv="dim_customers.csv",
    )

    if not customers_df.empty:
        search_query = st.text_input(
            "Search Customer by Email or Name:",
            placeholder="Type customer email (e.g. .com) or select below...",
        )

        if search_query:
            matched = customers_df[
                customers_df["email"].str.contains(search_query, case=False, na=False)
                | customers_df["full_name"].str.contains(search_query, case=False, na=False)
            ]
        else:
            matched = customers_df.head(50)

        selected_customer_key = st.selectbox(
            "Select Customer Record:",
            options=matched["customer_key"].tolist(),
            format_func=lambda ck: f"{matched.loc[matched['customer_key']==ck, 'full_name'].values[0]} ({matched.loc[matched['customer_key']==ck, 'email'].values[0]}) - LTV: ${matched.loc[matched['customer_key']==ck, 'lifetime_revenue'].values[0]:,.2f}",
        )

        cust = customers_df[customers_df["customer_key"] == selected_customer_key].iloc[0]

        st.markdown("---")
        card_col1, card_col2, card_col3 = st.columns([1, 1, 1])

        with card_col1:
            st.markdown("#### 📇 Identity & Demographics")
            st.markdown(f"**Full Name:** {cust.get('full_name', 'N/A')}")
            st.markdown(f"**Email:** `{cust.get('email', 'N/A')}`")
            st.markdown(f"**Phone:** `{cust.get('phone', 'N/A')}`")
            st.markdown(f"**Location:** {cust.get('city', 'N/A')}, {cust.get('state', 'N/A')}")
            st.markdown(f"**Marketing Opt-In:** {'✅ Yes' if cust.get('marketing_opt_in') else '❌ No'}")

        with card_col2:
            st.markdown("#### 📱 Connected Devices & Identity Graph")
            st.markdown(f"**Web Devices (GA4 cookies):** `{cust.get('web_devices', 0)}`")
            st.markdown(f"**Mobile Devices (Segment):** `{cust.get('app_devices', 0)}`")
            st.markdown(f"**Total Sessions:** `{cust.get('total_sessions', 0)}` ({cust.get('web_sessions', 0)} Web / {cust.get('app_sessions', 0)} App)")
            st.markdown(f"**Channels Touched:** `{cust.get('channels_touched', 0)}`")
            st.markdown(f"**Acquisition Channel:** **{cust.get('acquisition_channel', 'N/A')}**")

        with card_col3:
            st.markdown("#### 🛍️ Commercial Value & RFM")
            st.markdown(f"**Lifecycle Stage:** `{cust.get('lifecycle_stage', 'Customer')}`")
            st.markdown(f"**RFM Segment:** **{cust.get('rfm_segment', 'N/A')}** (R:{cust.get('r_score', '-')}, F:{cust.get('f_score', '-')}, M:{cust.get('m_score', '-')})")
            st.markdown(f"**Completed Orders:** `{cust.get('completed_orders', 0)}`")
            st.markdown(f"**Lifetime Revenue:** **${cust.get('lifetime_revenue', 0.0):,.2f}**")
            st.markdown(f"**Average Order Value:** **${cust.get('avg_order_value', 0.0):,.2f}**")

        st.markdown("---")
        st.markdown("#### 🛤️ Chronological Pre-Conversion Journey")

        journey_df = query_data(
            f"SELECT * FROM analytics_marts.fct_conversion_paths WHERE customer_key = '{selected_customer_key}'",
            fallback_csv="fct_conversion_paths.csv",
        )

        if not journey_df.empty:
            if "customer_key" in journey_df.columns:
                user_paths = journey_df[journey_df["customer_key"] == selected_customer_key]
            else:
                user_paths = journey_df.head(10)

            st.dataframe(
                user_paths[["order_id", "order_ts", "path_string", "touchpoint_count", "order_net_revenue"]],
                use_container_width=True,
            )
        else:
            st.info("No conversion journey paths recorded for this specific profile in sample exports.")


# ==============================================================================
# VIEW 5: MARKOV CHAIN GRAPH & REMOVAL EFFECTS
# ==============================================================================
elif view == "5. Markov Chain Graph & Removal Effects":
    st.markdown("## 🕸️ First-Order Markov Chain Graph & Removal Effects")
    st.markdown(
        "Data-driven attribution models state transitions between marketing touchpoints as a directed stochastic process. The **removal effect** calculates the percentage drop in conversion probability if a channel were entirely eliminated from the customer journey."
    )

    markov_df = query_data(
        "SELECT * FROM analytics_marts.markov_channel_attribution ORDER BY removal_effect DESC",
        fallback_csv="markov_channel_attribution.csv",
    )

    if not markov_df.empty:
        base_conv = markov_df["baseline_conversion_probability"].iloc[0] * 100

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Baseline Journey Conversion Probability", f"{base_conv:.2f}%")
        with col2:
            top_channel = markov_df.iloc[0]["channel"]
            top_effect = markov_df.iloc[0]["removal_effect"] * 100
            st.metric("Highest Impact Removal Channel", f"{top_channel} (-{top_effect:.1f}%)")
        with col3:
            total_attributed_rev = markov_df["attributed_revenue"].sum()
            st.metric("Total Attributed Conversion Revenue", f"${total_attributed_rev:,.2f}")

        st.markdown("---")

        fig_removal = px.bar(
            markov_df,
            x="channel",
            y="removal_effect",
            text="removal_effect",
            color="removal_effect",
            labels={"channel": "Marketing Channel", "removal_effect": "Removal Effect Coefficient"},
            title="Channel Removal Effect (Impact on Conversion if Channel is Removed)",
            color_continuous_scale="Reds",
        )
        fig_removal.update_traces(
            texttemplate="%{text:.3f}",
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Removal Effect: %{y:.3f}<br>(Removes %{y:.1%} of conversions)<extra></extra>",
        )
        fig_removal.update_layout(template="plotly_dark", height=420)
        st.plotly_chart(fig_removal, use_container_width=True)

        st.markdown("### 📋 Markov Mathematical Transition Outputs")
        st.dataframe(
            markov_df.style.format(
                {
                    "removal_effect": "{:.3f}",
                    "credit_share": "{:.1%}",
                    "attributed_conversions": "{:,.1f}",
                    "attributed_revenue": "${:,.2f}",
                    "baseline_conversion_probability": "{:.3f}",
                }
            ),
            use_container_width=True,
        )
