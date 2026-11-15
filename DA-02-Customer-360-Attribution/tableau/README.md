# Tableau dashboards

Two dashboards sit on top of the marts. Connect one of two ways:

| Where | How |
|---|---|
| **Tableau Desktop + BigQuery** (live) | Connect → Google BigQuery → project → dataset `analytics_marts` |
| **Tableau Public** (free) | Connect → Text file → the CSVs in `/exports` (run `make export` first) |

## Dashboard 1: Marketing Attribution ("Which channels actually bring revenue?")

Data source: `mart_channel_performance` (+ `markov_channel_attribution`, + `mart_campaign_roas`)

**Parameter**: `p_model` (string list: first_touch, last_touch, last_non_direct, linear, time_decay, position_based). Default `linear`.

**Calculated fields**
```
[Selected model]      = [attribution_model] = [p_model]
[Attributed revenue]  = SUM(IF [Selected model] THEN [attributed_revenue] END)
[Spend]               = SUM(IF [Selected model] THEN [spend] END)
[ROAS]                = [Attributed revenue] / NULLIF([Spend], 0)
[CPA]                 = [Spend] / NULLIF(SUM(IF [Selected model] THEN [attributed_conversions] END), 0)
[Revenue share]       = [Attributed revenue] / TOTAL([Attributed revenue])
```

**Sheets**
1. KPI tiles: Attributed revenue, Spend, ROAS, CPA (for the selected model).
2. Bar: revenue by channel, sorted, colour = paid vs organic.
3. Model comparison: channel on rows, `attribution_model` on columns, `SUM(attributed_revenue)` as a highlight table (shows how much credit moves between models). Add Markov from `markov_channel_attribution` as a 7th column via a relationship on `channel`.
4. Line: monthly ROAS for Paid Search / Paid Social / Display.
5. Campaign table (`mart_campaign_roas`): spend, conversions, revenue, ROAS, with ROAS < 1 highlighted red.

## Dashboard 2: Customer 360

Data source: `dim_customers` (relationship to `fct_orders` and `fct_sessions` on `customer_key`)

**Sheets**
1. KPI tiles: customers, prospects, total lifetime revenue, AOV, % multi-device customers (`web_devices + app_devices > 1`).
2. RFM segment treemap: size = count of customers, colour = avg lifetime revenue.
3. Acquisition channel vs LTV: bar of `AVG(lifetime_revenue)` by `acquisition_channel`.
4. Cohort heat map: `DATETRUNC('month', first_order_at)` × months since first order, from `fct_orders`.
5. Customer lookup: search by email, one row showing profile, devices, sessions, orders, LTV, segment, latest channel.

**Filters**: state, city, lifecycle_stage, rfm_segment, marketing_opt_in.
