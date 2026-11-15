# Customer 360 & Marketing Attribution Platform (DA-02)

**Author:** Mukesh Revanth ([@Revanth-4233](https://github.com/Revanth-4233))  
**Organization:** Nexvia Technologies — Data Analytics Internship Capstone  
**Repository:** [https://github.com/Revanth-4233/nexvia-internship-submission](https://github.com/Revanth-4233/nexvia-internship-submission)

Combines **website (GA4), mobile app (Segment), CRM and ad-platform data** into a single customer view, and shows
**which marketing channels actually bring revenue** using six rule-based multi-touch attribution models plus a
data-driven **Markov chain** model.

**Stack:** BigQuery · dbt · Python · Tableau · GA4 · Segment · DuckDB · Streamlit. The whole pipeline also runs locally on DuckDB at
zero cost, which is also how CI tests it on every push.

![Revenue credit by channel under each attribution model](docs/model_comparison.png)

---

## Engineering Decisions & Trade-Offs

During development, several architectural trade-offs were made to balance computational efficiency against modeling accuracy:

1. **Why First-Order Markov Chain over Cooperative Game Theory (Shapley Values)?**
   - Cooperative game theory (Shapley values) requires evaluating marginal contributions across all $2^n$ channel subsets. For 9 omni-channels, this requires computing 512 coalition combinations per customer journey.
   - In contrast, a first-order absorbing Markov chain represents journeys as state transition probabilities and solves the absorption matrix $B = (I - Q)^{-1} R$ in $O(m^3)$ polynomial time, scaling effortlessly across hundreds of thousands of customer touchpoints.

2. **Deterministic Identity Resolution vs. Probabilistic Graph Matching:**
   - Instead of fragile third-party cookie matching or fuzzy probabilistic heuristics, we implemented a deterministic identity graph in dbt (`int_identity_graph`).
   - When a user signs in, places an order, or registers on either web (GA4 `user_pseudo_id`) or mobile (Segment `anonymous_id`), the event records their verified `user_id` or CRM email. We propagate this forward and backward across session windows, bridging the anonymous pre-login journey to their permanent CRM `contact_id`.

3. **Reconciling Marketing Attribution with Finance General Ledger:**
   - A classic pain point in marketing analytics is that the sum of attributed revenue rarely matches accounting revenue.
   - In this platform, every completed order is attributed exactly 1.0 total credit across touchpoints in the lookback window. If a customer converts with zero tracked touchpoints, the order is credited to a fallback `Direct` interaction. This is enforced by a custom dbt data test (`assert_attributed_revenue_reconciles`), ensuring finance and growth teams look at the exact same dollar figures.

---

## 1. The business problem

A D2C footwear brand ("StrideKart") sells on its website and app, and spends on Google Ads and Meta Ads.

* Marketing sees **last-click** numbers in each ad platform, and every platform claims the same sale.
* One person shows up as several anonymous devices (web and app), so the CRM can't see the journey before purchase.
* Finance's revenue (CRM orders) never matches the revenue marketing reports.

**This platform answers:**
1. Who is each customer across every device and system? (**Customer 360**)
2. Which channels and campaigns drive revenue, and how does the answer change by attribution model? (**Attribution**)
3. What is the real ROAS / CPA of each paid channel, reconciled to finance revenue?

---

## 2. Architecture

```mermaid
flowchart LR
    subgraph Sources
        GA4[GA4 web events]
        SEG[Segment app tracks + identifies]
        CRM[CRM contacts + orders]
        ADS[Google Ads + Meta Ads spend]
    end
    subgraph BigQuery["BigQuery (or DuckDB locally)"]
        RAW[(raw)]
        STG[staging<br/>clean, type, dedupe]
        INT[intermediate<br/>identity graph, sessions,<br/>attribution touchpoints]
        MART[marts<br/>dim_customers, fct_attribution,<br/>mart_channel_performance ...]
    end
    PY[Python<br/>Markov attribution]
    TAB[Tableau dashboards]
    GA4 & SEG & CRM & ADS --> RAW --> STG --> INT --> MART
    MART -- fct_conversion_paths --> PY -- markov_channel_attribution --> MART
    MART --> TAB
```

| Layer | Models | What happens |
|---|---|---|
| **staging** (views) | `stg_ga4__events`, `stg_segment__tracks`, `stg_segment__identifies`, `stg_crm__contacts`, `stg_crm__orders`, `stg_ads__spend` | type casting, de-duplicating double-fired GA4 tags, lower-casing CRM emails, net revenue, ad campaign → channel |
| **intermediate** | `int_identity_graph` | **identity resolution**: every device (GA4 `user_pseudo_id`, Segment `anonymous_id`) → `user_id` → CRM `contact_id`. Anonymous history before login gets stitched to the customer |
| | `int_sessions` | GA4 sessions + Segment app events sessionised on 30-min inactivity, one channel grouping via the `channel_mapping` seed |
| | `int_attribution_touchpoints` | every session in the 30-day look-back window before each completed order |
| **marts** | `dim_customers` | **Customer 360**: profile, devices, web/app sessions, acquisition & latest channel, orders, LTV, AOV, recency, **RFM segment** |
| | `fct_attribution` / `fct_attribution_long` | credit per touchpoint under 6 models |
| | `mart_channel_performance` | month × channel × model: spend, sessions, attributed conversions & revenue, **ROAS, CPA**, conversion rate |
| | `mart_campaign_roas` | paid campaign ROAS by model |
| | `fct_orders`, `fct_sessions`, `fct_conversion_paths` | facts; journeys feed the Markov model |
| **Python** | `attribution/markov.py` | Markov chain removal-effect attribution, written back as `markov_channel_attribution` |

### Attribution models

| Model | Rule |
|---|---|
| First touch | 100% to the first touch in the window |
| Last touch | 100% to the last touch |
| Last non-direct | 100% to the last touch that isn't Direct (Google Analytics' classic default) |
| Linear | equal split |
| Time decay | weight = 0.5^(days before conversion / 7), so credit halves every 7 days |
| Position based (U-shaped) | 40% first, 40% last, 20% split over the middle |
| **Markov chain** (data-driven) | builds the channel transition matrix from converting **and non-converting** journeys; each channel's credit is proportional to its **removal effect** (the drop in overall conversion probability if the channel is removed), solved exactly with absorbing-Markov-chain algebra |

Look-back window, half-life and U-shape weights are dbt `vars` in `dbt/dbt_project.yml`.
Orders with no tracked touch get one synthetic `Direct` touch, so **attributed revenue always equals finance revenue** (enforced by a test).

---

## 3. Data

`data_generator/generate_data.py` simulates realistic journeys for 5,000 people (Jan to Sep 2026) and writes each
source **in its native export shape**:

| File | Shaped like | Rows (seed 42) |
|---|---|---|
| `ga4_events.csv` | GA4 BigQuery export (flattened) | ~95k |
| `segment_tracks.csv`, `segment_identifies.csv` | Segment warehouse tables | ~28k, ~2k |
| `crm_contacts.csv`, `crm_orders.csv` | HubSpot / Salesforce export | ~2.3k, ~1.8k |
| `ad_spend.csv` | Google Ads + Meta Ads daily campaign report | ~2.2k |

Channels carry different conversion lift, people come back through email/direct, some browse anonymously, some
use web and app. Real-world data-quality problems are injected on purpose (duplicate GA4 events, upper-case CRM
emails, refunded orders) so the staging layer has real cleaning to do.
To use a **real GA4 property**, create `raw.ga4_events` as a view over `dbt/analyses/ga4_native_export_flatten.sql`.

---

## 4. Results (synthetic data, seed 42)

* **2,271** CRM contacts unified with **7,077 devices** (2,960 stitched to a known customer) and **24,906 sessions**; **803 customers use more than one device**.
* **1,771** completed orders, **₹1.25 crore** net revenue, **₹16.7 lakh** ad spend; on average **3.1 touches** before purchase.
* **Last touch flatters Email** (24.5% of revenue vs 17.1% in Markov), because email closes sales that other channels started.
* **First touch / Markov reward Display and Paid Social** for starting journeys. Display ROAS is **2.1× under last touch but 6.6× under Markov**. Judged on last click alone, it would be wrongly cut.
* **Paid Search** stays strong in every model (ROAS 1.9 to 2.7×). Its budget is safe whichever model the team trusts.

Reproduce with `make compare`.

---

## 5. Run it

### Local (free, about 1 minute)
```bash
git clone <this repo> && cd customer-360-attribution
python -m venv .venv && source .venv/bin/activate
make setup          # pip install + copies dbt/profiles.yml
make all            # generate data → load DuckDB → dbt build (models + tests) → Markov → exports → chart → pytest
```
Browse the lineage graph and column docs with `make docs`.

### BigQuery
```bash
gcloud auth application-default login
export GCP_PROJECT=your-project-id
make data
make bq-load        # loads CSVs into dataset `raw`
make bq-dbt         # builds analytics_staging / analytics_intermediate / analytics_marts
make bq-markov      # writes analytics_marts.markov_channel_attribution
```
Every model is written with dbt cross-database macros (`dbt.datediff`, `dbt.date_trunc`, `dbt.listagg`,
`dbt.type_*`) plus small dispatch macros in `dbt/macros/cross_db.sql`, so the same SQL runs on both warehouses.
The BigQuery sandbox (free tier) is enough for this data volume.

### Tableau
Connect Tableau Desktop to `analytics_marts` in BigQuery, or open the CSVs in `exports/` with Tableau Public.
The dashboard specs (parameters, calculated fields, sheets) are in [`tableau/README.md`](tableau/README.md).

---

## 6. Testing, Validation & Benchmarks

The entire pipeline was executed locally on DuckDB (`warehouse.duckdb`) and verified:
- **dbt Build & Test:** **77 / 77 Passed (100%)** — 2 seeds loaded, 17 models materialized (11 tables, 6 views), 58 schema and reconciliation data tests executed with 0 errors.
- **Python Test Suite:** **7 / 7 pytest tests Passed (100%)** across Markov graph edge cases and data generator referential integrity.

### Verified Markov Attribution Benchmarks
| Channel | Removal Effect | Credit Share | Attributed Conversions | Attributed Revenue | Baseline Conv Prob |
|---|---|---|---|---|---|
| **Direct** | 0.429 | 17.8% | 314.5 | $2,212,730 | 0.235 |
| **Email** | 0.414 | 17.1% | 302.9 | $2,131,084 | 0.235 |
| **Paid Search** | 0.397 | 16.4% | 290.9 | $2,046,510 | 0.235 |
| **Organic Search** | 0.365 | 15.1% | 267.2 | $1,879,875 | 0.235 |
| **Paid Social** | 0.277 | 11.5% | 202.9 | $1,427,761 | 0.235 |
| **Display** | 0.154 | 6.4% | 113.1 | $796,029 | 0.235 |
| **Organic Social** | 0.148 | 6.1% | 108.5 | $763,550 | 0.235 |
| **Affiliate** | 0.132 | 5.5% | 96.8 | $681,016 | 0.235 |
| **Referral** | 0.101 | 4.2% | 74.3 | $522,732 | 0.235 |

### Verified ROAS Comparison by Attribution Model
| Paid Channel | First-Touch | Last-Touch | Last-Non-Direct | Linear | Time-Decay | Position-Based | Markov (Data-Driven) |
|---|---|---|---|---|---|---|---|
| **Paid Social** | 4.05x | 2.22x | 2.84x | 3.10x | 2.74x | 3.14x | **3.12x** |
| **Display** | 7.15x | 2.12x | 3.12x | 5.04x | 3.83x | 4.77x | **6.57x** |
| **Paid Search** | 2.02x | 2.32x | 2.68x | 2.11x | 2.19x | 2.14x | **1.88x** |

### Test Assertions Passed
* Schema tests: uniqueness / not-null on every key, relationships (orders → contacts, devices → contacts), accepted values (channels, models, statuses).
* Business-logic tests (`dbt/tests/`):
  * `assert_attribution_weights_sum_to_one`: every model gives out exactly 100% credit per order
  * `assert_attributed_revenue_reconciles`: attributed revenue = CRM completed revenue, per model
  * `assert_every_order_attributed`: no completed order left out
  * `assert_touchpoints_within_lookback`: no touch after conversion or outside the window
  * `assert_spend_reconciles`: mart spend = raw ad-platform spend
* Python (`tests/`): Markov edge cases (single channel, never-converting channel, credit sums, baseline probability), generator determinism and referential integrity.

---

## 7. Repository layout
```
├── data_generator/generate_data.py   synthetic multi-source data
├── scripts/
│   ├── load_duckdb.py / load_bigquery.py
│   ├── export_for_tableau.py
│   └── model_comparison.py
├── dbt/
│   ├── models/{staging,intermediate,marts}
│   ├── seeds/ (channel_mapping, ad_platform_channel)
│   ├── macros/ (cross-db helpers)
│   ├── tests/ (business-logic tests)
│   └── analyses/ga4_native_export_flatten.sql
├── attribution/markov.py             data-driven attribution
├── tests/                            pytest
├── tableau/README.md                 dashboard spec
├── exports/                          Tableau-ready CSVs
├── docs/model_comparison.png
└── Makefile · requirements.txt · .github/workflows/ci.yml
```

## 8. Possible extensions
Probabilistic identity matching (email/phone hashing across sources) · incremental models partitioned by
`event_date` for production GA4 volumes · Shapley-value attribution · media-mix modelling for channels without
click tracking · reverse-ETL of RFM segments to the CRM and ad audiences.
