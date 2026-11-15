"""
Synthetic data generator for the Customer 360 & Marketing Attribution Platform.

Produces representative raw data for five source systems, shaped like their
real exports so the dbt models work the same way on real data:

  ga4_events.csv          Website events (flattened GA4 BigQuery export)
  segment_tracks.csv      Mobile app events (Segment `tracks` table)
  segment_identifies.csv  Segment `identifies` (anonymous_id -> user_id)
  crm_contacts.csv        CRM contacts (HubSpot / Salesforce style)
  crm_orders.csv          CRM orders / closed-won revenue
  ad_spend.csv            Daily ad spend (Google Ads + Meta Ads)

The simulation is journey based: each person browses over time from a mix of
marketing channels on web and app, may sign up, and may convert. Channels
carry different "lift", so attribution models give different, explainable
answers. A few real-world data quality problems are injected on purpose
(duplicate events, mixed-case emails, a refunded order status) so the
staging layer has something real to clean.

Usage:
    python data_generator/generate_data.py --customers 5000 --seed 42 --out data/raw
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 9, 30, 23, 59, 59, tzinfo=timezone.utc)

# channel -> (source, medium, platform for paid spend or None, base weight, conversion lift)
CHANNELS = {
    "Organic Search": [("google", "organic", None), ("bing", "organic", None)],
    "Paid Search":    [("google", "cpc", "google_ads")],
    "Paid Social":    [("facebook", "paid_social", "meta_ads"), ("instagram", "paid_social", "meta_ads")],
    "Display":        [("google", "display", "google_ads")],
    "Email":          [("newsletter", "email", None)],
    "Organic Social": [("facebook", "social", None), ("instagram", "social", None), ("youtube", "social", None)],
    "Referral":       [("partnerblog.com", "referral", None), ("dealsite.in", "referral", None)],
    "Affiliate":      [("cashkaro", "affiliate", None)],
    "Direct":         [("(direct)", "(none)", None)],
}
# Share of sessions that *start* a journey from each channel (acquisition mix)
ACQ_WEIGHTS = {"Organic Search": 22, "Paid Search": 18, "Paid Social": 20, "Display": 10,
               "Organic Social": 10, "Referral": 6, "Affiliate": 5, "Direct": 9, "Email": 0}
# Mix for returning sessions (people come back through email/direct more)
RET_WEIGHTS = {"Organic Search": 15, "Paid Search": 14, "Paid Social": 10, "Display": 6,
               "Organic Social": 6, "Referral": 3, "Affiliate": 4, "Direct": 22, "Email": 20}
# Multiplier on per-session conversion probability
LIFT = {"Organic Search": 1.1, "Paid Search": 1.6, "Paid Social": 0.8, "Display": 0.35,
        "Organic Social": 0.5, "Referral": 1.2, "Affiliate": 1.4, "Direct": 1.3, "Email": 1.7}

CAMPAIGNS = {
    "google_ads": {"Paid Search": ["gs_brand", "gs_generic_shoes", "gs_competitor"],
                   "Display": ["gd_remarketing", "gd_prospecting"]},
    "meta_ads": {"Paid Social": ["fb_prospecting_lal", "fb_retargeting", "ig_reels_launch"]},
}
EMAIL_CAMPAIGNS = ["weekly_newsletter", "abandoned_cart", "winback_60d"]
CPC = {"gs_brand": 6.0, "gs_generic_shoes": 18.0, "gs_competitor": 24.0, "gd_remarketing": 4.0,
       "gd_prospecting": 3.0, "fb_prospecting_lal": 9.0, "fb_retargeting": 7.0, "ig_reels_launch": 8.0}

FIRST = ["Aarav", "Vivaan", "Aditya", "Sai", "Arjun", "Reyansh", "Krishna", "Ishaan", "Ananya", "Diya",
         "Saanvi", "Aadhya", "Kavya", "Meera", "Priya", "Lakshmi", "Rahul", "Kiran", "Sneha", "Pooja",
         "Ravi", "Teja", "Harika", "Mahesh", "Divya", "Naveen", "Swathi", "Venkat", "Nikhil", "Keerthi"]
LAST = ["Reddy", "Rao", "Sharma", "Naidu", "Kumar", "Patel", "Iyer", "Varma", "Gupta", "Chowdary",
        "Menon", "Singh", "Das", "Pillai", "Joshi"]
CITIES = [("Hyderabad", "Telangana"), ("Bengaluru", "Karnataka"), ("Chennai", "Tamil Nadu"),
          ("Vijayawada", "Andhra Pradesh"), ("Anantapur", "Andhra Pradesh"), ("Mumbai", "Maharashtra"),
          ("Pune", "Maharashtra"), ("Delhi", "Delhi"), ("Visakhapatnam", "Andhra Pradesh"), ("Kochi", "Kerala")]
PAGES = ["/", "/men/running-shoes", "/women/sneakers", "/sale", "/product/air-glide-2", "/product/trail-max",
         "/product/street-pro", "/blog/how-to-choose-running-shoes"]
PRODUCTS = [("air-glide-2", 3499), ("trail-max", 4999), ("street-pro", 2799), ("comfy-slides", 999),
            ("sport-socks-3pk", 499), ("marathon-elite", 8999)]


@dataclass
class Person:
    idx: int
    web_ids: list = field(default_factory=list)
    app_id: str | None = None
    user_id: str | None = None
    contact_id: str | None = None
    email: str | None = None
    signed_up_at: datetime | None = None
    propensity: float = 1.0


def micros(dt: datetime) -> int:
    return int(dt.timestamp() * 1_000_000)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def pick(rng: random.Random, weights: dict) -> str:
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys])[0]


def generate(n_customers: int, seed: int, out: str) -> dict:
    rng = random.Random(seed)
    uuid_rng = random.Random(seed + 1)

    def uid() -> str:
        return str(uuid.UUID(int=uuid_rng.getrandbits(128)))

    os.makedirs(out, exist_ok=True)
    ga4, tracks, identifies, contacts, orders = [], [], [], [], []
    paid_clicks = {}  # (date, platform, campaign) -> clicks
    contact_seq, order_seq, user_seq = 1, 1, 1

    span = (END - START).total_seconds()
    for i in range(n_customers):
        p = Person(idx=i, propensity=rng.lognormvariate(0, 0.6))
        p.web_ids = [f"{rng.randint(10**8, 10**9-1)}.{rng.randint(10**9, 2*10**9)}"
                     for _ in range(1 if rng.random() < 0.75 else 2)]
        if rng.random() < 0.45:
            p.app_id = uid()

        t = START + timedelta(seconds=rng.random() * span * 0.9)
        n_sessions = max(1, int(rng.expovariate(1 / 6)))
        n_orders = 0
        for s in range(n_sessions):
            if t > END:
                break
            channel = pick(rng, ACQ_WEIGHTS if s == 0 else RET_WEIGHTS)
            source, medium, platform = rng.choice(CHANNELS[channel])
            if platform:
                campaign = rng.choice(CAMPAIGNS[platform][channel])
                key = (t.date().isoformat(), platform, campaign)
                paid_clicks[key] = paid_clicks.get(key, 0) + 1
            elif channel == "Email":
                campaign = rng.choice(EMAIL_CAMPAIGNS)
            else:
                campaign = "(organic)" if channel != "Direct" else "(direct)"

            on_app = p.app_id is not None and rng.random() < 0.5
            device_id = p.app_id if on_app else rng.choice(p.web_ids)
            logged_in = p.user_id is not None and rng.random() < 0.8

            # conversion probability for this session
            prior = s
            p_conv = 0.035 * LIFT[channel] * p.propensity * (1 + 0.25 * min(prior, 6)) * (0.5 if n_orders else 1)
            converts = rng.random() < min(p_conv, 0.6)

            # sign up happens before / at the first order, or sometimes just from browsing
            signs_up = p.user_id is None and (converts or rng.random() < 0.06)
            if signs_up:
                p.user_id = f"u_{user_seq:06d}"; user_seq += 1
                p.contact_id = f"C{contact_seq:06d}"; contact_seq += 1
                fn, ln = rng.choice(FIRST), rng.choice(LAST)
                p.email = f"{fn}.{ln}{contact_seq - 1}@example.com".lower()
                p.signed_up_at = t
                city, state = rng.choice(CITIES)
                email_raw = p.email.upper() if rng.random() < 0.1 else p.email  # DQ: casing
                contacts.append({
                    "contact_id": p.contact_id, "app_user_id": p.user_id, "email": email_raw,
                    "first_name": fn, "last_name": ln, "phone": f"+91{rng.randint(7000000000, 9999999999)}",
                    "city": city, "state": state, "country": "IN", "created_at": iso(t),
                    "lead_source": channel, "lifecycle_stage": "lead",
                    "marketing_opt_in": str(rng.random() < 0.7).lower(),
                })
                identifies.append({"id": uid(), "anonymous_id": device_id, "user_id": p.user_id,
                                   "email": p.email, "timestamp": iso(t)})
                logged_in = True

            # build the session's events
            ga_session_id = int(t.timestamp())
            n_pages = rng.randint(1, 6)
            et = t
            ev_list = ["session_start"] + ["page_view"] * n_pages
            if converts:
                ev_list += ["add_to_cart", "begin_checkout", "purchase"]
            elif rng.random() < 0.25:
                ev_list += ["add_to_cart"]
            order_id, revenue = None, None
            if converts:
                items = rng.sample(PRODUCTS, rng.randint(1, 3))
                revenue = float(sum(pr for _, pr in items))
                order_id = f"ORD-{order_seq:07d}"; order_seq += 1
                n_orders += 1

            for ev in ev_list:
                et = et + timedelta(seconds=rng.randint(5, 180))
                is_purchase = ev == "purchase"
                if on_app:
                    app_names = {"session_start": "Application Opened", "page_view": "Screen Viewed",
                                 "add_to_cart": "Product Added", "begin_checkout": "Checkout Started",
                                 "purchase": "Order Completed"}
                    tracks.append({
                        "id": uid(), "anonymous_id": device_id,
                        "user_id": p.user_id if logged_in else "",
                        "event": app_names[ev], "timestamp": iso(et),
                        "context_campaign_source": source if channel != "Direct" else "",
                        "context_campaign_medium": medium if channel != "Direct" else "",
                        "context_campaign_name": campaign if channel not in ("Direct",) else "",
                        "context_device_type": rng.choice(["ios", "android", "android"]),
                        "order_id": order_id if is_purchase else "",
                        "revenue": revenue if is_purchase else "",
                    })
                else:
                    ga4.append({
                        "event_date": et.strftime("%Y%m%d"), "event_timestamp": micros(et),
                        "event_name": ev, "user_pseudo_id": device_id,
                        "user_id": p.user_id if logged_in else "",
                        "ga_session_id": ga_session_id,
                        "traffic_source": source, "traffic_medium": medium, "traffic_campaign": campaign,
                        "page_location": "https://www.stridekart.in" + rng.choice(PAGES),
                        "device_category": rng.choice(["mobile", "mobile", "desktop", "tablet"]),
                        "transaction_id": order_id if is_purchase else "",
                        "purchase_revenue": revenue if is_purchase else "",
                    })
                    if rng.random() < 0.01:  # DQ: duplicate event from double-firing tag
                        ga4.append(dict(ga4[-1]))

            if converts:
                status = "refunded" if rng.random() < 0.04 else "completed"
                orders.append({
                    "order_id": order_id, "contact_id": p.contact_id, "order_ts": iso(et),
                    "order_platform": "app" if on_app else "web", "gross_revenue": revenue,
                    "discount": round(revenue * rng.choice([0, 0, 0, 0.1, 0.15]), 2),
                    "currency": "INR", "status": status,
                })

            gap_days = rng.expovariate(1 / 9)
            t = et + timedelta(days=gap_days, hours=rng.random() * 12)

        if p.contact_id and n_orders:
            for c in contacts[::-1]:
                if c["contact_id"] == p.contact_id:
                    c["lifecycle_stage"] = "customer"
                    break

    # CRM-only leads (events/tradeshows) that never touched digital
    for _ in range(n_customers // 25):
        fn, ln = rng.choice(FIRST), rng.choice(LAST)
        city, state = rng.choice(CITIES)
        contacts.append({
            "contact_id": f"C{contact_seq:06d}", "app_user_id": "",
            "email": f"{fn}.{ln}{contact_seq}@example.com",
            "first_name": fn, "last_name": ln, "phone": "", "city": city, "state": state, "country": "IN",
            "created_at": iso(START + timedelta(seconds=rng.random() * span)),
            "lead_source": "Offline Event", "lifecycle_stage": "lead", "marketing_opt_in": "false",
        })
        contact_seq += 1

    # Ad spend: every campaign every day, clicks >= observed paid sessions
    spend = []
    day = START.date()
    while day <= END.date():
        for platform, chans in CAMPAIGNS.items():
            for chan, camps in chans.items():
                for camp in camps:
                    sessions = paid_clicks.get((day.isoformat(), platform, camp), 0)
                    clicks = sessions + rng.randint(0, 4) + int(sessions * rng.uniform(0.05, 0.3))
                    ctr = {"Paid Search": 0.045, "Display": 0.004, "Paid Social": 0.012}[chan]
                    impressions = int(max(clicks, 1) / ctr * rng.uniform(0.8, 1.2))
                    cost = round(clicks * CPC[camp] * 12 * rng.uniform(0.85, 1.15), 2)
                    spend.append({
                        "date": day.isoformat(), "platform": platform,
                        "campaign_id": f"{platform}:{camp}",
                        "campaign_name": camp, "impressions": impressions, "clicks": clicks,
                        "spend": cost, "currency": "INR",
                    })
        day += timedelta(days=1)

    tables = {"ga4_events": ga4, "segment_tracks": tracks, "segment_identifies": identifies,
              "crm_contacts": contacts, "crm_orders": orders, "ad_spend": spend}
    for name, rows in tables.items():
        with open(os.path.join(out, f"{name}.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    return {k: len(v) for k, v in tables.items()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--customers", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "data", "raw"))
    a = ap.parse_args()
    counts = generate(a.customers, a.seed, a.out)
    for k, v in counts.items():
        print(f"{k:22s} {v:>8,d} rows")
