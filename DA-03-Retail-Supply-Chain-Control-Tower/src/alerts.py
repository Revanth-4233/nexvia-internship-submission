"""
Retail and Supply Chain Control Tower - Automated Alert Dispatch Engine
Monitors operational triggers (stock-outs, low buffer, shipment delays, anomalies)
and dispatches rich notifications to Slack Webhook channels and Email (SMTP),
logging all events in control_tower.alert_events.
"""

import os
import sys
import json
import logging
import smtplib
from pathlib import Path
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("AlertEngine")

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


def get_db_engine():
    """Create SQLAlchemy engine using environment variables."""
    db_user = os.getenv("DB_USER", "admin")
    db_pass = os.getenv("DB_PASSWORD", "admin123")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "supply_chain_db")

    db_url = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    return create_engine(db_url, pool_pre_ping=True)


def load_alert_config():
    """Load notification routing configuration from environment."""
    return {
        "slack_webhook": os.getenv("SLACK_WEBHOOK_URL", ""),
        "slack_enabled": os.getenv("SLACK_ENABLED", "false").lower() in ("true", "1", "yes"),
        "email_enabled": os.getenv("EMAIL_ENABLED", "false").lower() in ("true", "1", "yes"),
        "smtp_host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "smtp_port": int(os.getenv("SMTP_PORT", "587")),
        "email_user": os.getenv("EMAIL_USER", ""),
        "email_password": os.getenv("EMAIL_PASSWORD", ""),
        "recipients": [r.strip() for r in os.getenv("ALERT_RECIPIENTS", "supply_chain_ops@company.com").split(",") if r.strip()],
        "stockout_threshold": float(os.getenv("STOCK_OUT_THRESHOLD", "0.05")),
        "delivery_delay_days": float(os.getenv("DELIVERY_DELAY_DAYS", "3.0")),
    }


def send_slack_notification(webhook_url, alert):
    """
    Dispatch structured Slack Block Kit message payload to configured incoming webhook.
    """
    if not webhook_url or webhook_url.startswith("https://hooks.slack.com/services/YOUR/"):
        logger.warning("Slack webhook URL not configured. Simulating dispatch.")
        return True

    severity_emojis = {
        "CRITICAL": ":rotating_light:",
        "HIGH": ":warning:",
        "MEDIUM": ":large_yellow_circle:",
        "LOW": ":information_source:"
    }
    emoji = severity_emojis.get(alert["severity"], ":bell:")

    payload = {
        "text": f"{emoji} [{alert['severity']}] {alert['alert_title']}",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {alert['alert_title']}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Severity:* `{alert['severity']}`"},
                    {"type": "mrkdwn", "text": f"*Target ID:* `{alert.get('product_id') or alert.get('shipment_id') or 'N/A'}`"},
                    {"type": "mrkdwn", "text": f"*Observed Value:* {alert['actual_value']}"},
                    {"type": "mrkdwn", "text": f"*Threshold / Baseline:* {alert['expected_value']}"}
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Problem Description:*\n{alert['message']}\n\n*Recommended Operational Action:*\n:point_right: _{alert['recommended_action']}_"
                }
            }
        ]
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=5)
        return response.status_code == 200
    except Exception as exc:
        logger.error(f"Slack webhook dispatch failed: {exc}")
        return False


def send_email_notification(config, alert):
    """
    Dispatch HTML formatted alert email via SMTP transport.
    """
    if not config["email_enabled"] or not config["email_user"]:
        logger.warning("SMTP email dispatch not configured. Simulating dispatch.")
        return True

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[{alert['severity']}] Control Tower Alert: {alert['alert_title']}"
    msg["From"] = config["email_user"]
    msg["To"] = ", ".join(config["recipients"])

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.5; color: #333;">
        <div style="background-color: #f8f9fa; border-left: 6px solid #dc3545; padding: 15px; margin-bottom: 20px;">
          <h2 style="margin-top: 0; color: #dc3545;">{alert['alert_title']}</h2>
          <p><strong>Severity:</strong> <span style="background-color: #dc3545; color: white; padding: 3px 8px; border-radius: 3px;">{alert['severity']}</span></p>
          <p><strong>Entity Reference:</strong> {alert.get('product_id') or alert.get('shipment_id') or 'N/A'}</p>
        </div>
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
          <tr>
            <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold; width: 30%;">Observed Value</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{alert['actual_value']}</td>
          </tr>
          <tr>
            <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Expected / Threshold</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{alert['expected_value']}</td>
          </tr>
        </table>
        <p><strong>Description:</strong> {alert['message']}</p>
        <div style="background-color: #e9ecef; padding: 12px; border-radius: 4px;">
          <strong>Recommended Action:</strong> {alert['recommended_action']}
        </div>
      </body>
    </html>
    """
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as server:
            server.starttls()
            server.login(config["email_user"], config["email_password"])
            server.send_message(msg)
        return True
    except Exception as exc:
        logger.error(f"Email dispatch failed: {exc}")
        return False


def persist_alert_event(engine, alert, status="SENT", channel="ALL"):
    """
    Log generated alert into control_tower.alert_events.
    """
    insert_sql = """
    SET search_path TO control_tower, public;
    INSERT INTO alert_events (
        product_id,
        shipment_id,
        alert_title,
        severity,
        message,
        notification_channel,
        notification_status,
        created_at,
        sent_at
    ) VALUES (
        :product_id, :shipment_id, :title, :severity,
        :message, :channel, :status, :created_at, :sent_at
    );
    """
    with engine.begin() as conn:
        conn.execute(
            text(insert_sql),
            {
                "product_id": alert.get("product_id"),
                "shipment_id": alert.get("shipment_id"),
                "title": alert["alert_title"],
                "severity": alert["severity"],
                "message": f"{alert['message']} | Action: {alert['recommended_action']}",
                "channel": channel,
                "status": status,
                "created_at": datetime.now(timezone.utc),
                "sent_at": datetime.now(timezone.utc)
            }
        )


def check_low_stock_alerts(engine):
    """Trigger 1 & 2: Inventory below reorder level or active stock-out."""
    query = """
    SET search_path TO control_tower, public;
    WITH latest_inv AS (
        SELECT DISTINCT ON (i.product_id, i.warehouse_id)
            i.product_id, p.product_name, i.warehouse_id, i.available_stock, i.reorder_level
        FROM inventory_snapshots i
        JOIN products p ON i.product_id = p.product_id
        ORDER BY i.product_id, i.warehouse_id, i.stock_update_timestamp DESC
    )
    SELECT * FROM latest_inv
    WHERE available_stock <= reorder_level
    ORDER BY available_stock ASC
    LIMIT 5;
    """
    df = pd.read_sql(text(query), engine.connect())
    alerts = []
    for _, row in df.iterrows():
        is_zero = row["available_stock"] == 0
        severity = "CRITICAL" if is_zero else "HIGH"
        alerts.append({
            "alert_title": f"Stock-Out Event: {row['product_name'][:25]}" if is_zero else f"Low Buffer Alert: {row['product_name'][:25]}",
            "product_id": row["product_id"],
            "shipment_id": None,
            "actual_value": f"{row['available_stock']} units",
            "expected_value": f"{row['reorder_level']} units reorder threshold",
            "severity": severity,
            "message": f"Product on-hand stock ({row['available_stock']} units) at warehouse {row['warehouse_id']} is below reorder level ({row['reorder_level']} units).",
            "recommended_action": "Issue urgent replenishment purchase order to primary supplier." if is_zero else "Schedule routine inventory replenishment."
        })
    return alerts


def check_shipment_delay_alerts(engine, threshold_days=3.0):
    """Trigger 3: In-transit or delivered shipment exceeding expected delivery date."""
    query = f"""
    SET search_path TO control_tower, public;
    SELECT
        shipment_id, product_id, supplier_id,
        expected_delivery_date, actual_delivery_date,
        EXTRACT(EPOCH FROM (COALESCE(actual_delivery_date, CURRENT_TIMESTAMP) - expected_delivery_date)) / 86400 AS delay_days
    FROM shipments
    WHERE (actual_delivery_date > expected_delivery_date OR (actual_delivery_date IS NULL AND CURRENT_TIMESTAMP > expected_delivery_date))
      AND (EXTRACT(EPOCH FROM (COALESCE(actual_delivery_date, CURRENT_TIMESTAMP) - expected_delivery_date)) / 86400) >= {threshold_days}
    ORDER BY delay_days DESC
    LIMIT 5;
    """
    df = pd.read_sql(text(query), engine.connect())
    alerts = []
    for _, row in df.iterrows():
        delay = float(row["delay_days"])
        severity = "CRITICAL" if delay > 7.0 else "HIGH"
        alerts.append({
            "alert_title": f"Severe Logistics Delivery Delay ({delay:.1f} Days Overdue)",
            "product_id": row["product_id"],
            "shipment_id": row["shipment_id"],
            "actual_value": f"{delay:.1f} days late",
            "expected_value": "Delivery on or before SLA deadline",
            "severity": severity,
            "message": f"Consignment {row['shipment_id']} from supplier {row['supplier_id'][:8]} has breached promised SLA delivery deadline by {delay:.1f} days.",
            "recommended_action": "Contact logistics carrier for GPS status trace and dispatch proactive customer delivery notification."
        })
    return alerts


def check_forecast_shortage_alerts(engine):
    """Trigger 5: Forecasted 7-day demand exceeds on-hand warehouse inventory."""
    query = """
    SET search_path TO control_tower, public;
    WITH current_stock AS (
        SELECT product_id, SUM(available_stock) AS stock
        FROM (
            SELECT DISTINCT ON (product_id, warehouse_id) product_id, available_stock
            FROM inventory_snapshots
            ORDER BY product_id, warehouse_id, stock_update_timestamp DESC
        ) sub
        GROUP BY product_id
    ),
    forecast_demand AS (
        SELECT product_id, SUM(predicted_demand) AS demand_7d
        FROM demand_forecasts
        WHERE forecast_date BETWEEN CURRENT_DATE AND (CURRENT_DATE + INTERVAL '7 days')
        GROUP BY product_id
    )
    SELECT
        f.product_id, p.product_name, cs.stock, f.demand_7d,
        (cs.stock - f.demand_7d) AS balance
    FROM forecast_demand f
    JOIN products p ON f.product_id = p.product_id
    LEFT JOIN current_stock cs ON f.product_id = cs.product_id
    WHERE cs.stock < f.demand_7d
    ORDER BY balance ASC
    LIMIT 5;
    """
    df = pd.read_sql(text(query), engine.connect())
    alerts = []
    for _, row in df.iterrows():
        shortage = abs(float(row["balance"]))
        alerts.append({
            "alert_title": f"Forecast Stockout Warning: {row['product_name'][:25]}",
            "product_id": row["product_id"],
            "shipment_id": None,
            "actual_value": f"{int(row['stock'])} on-hand units",
            "expected_value": f"{row['demand_7d']:.1f} units 7-day demand",
            "severity": "CRITICAL" if row["stock"] == 0 else "HIGH",
            "message": f"7-day ML forecasted demand ({row['demand_7d']:.1f} units) exceeds on-hand stock ({int(row['stock'])} units). Projected shortage of {shortage:.1f} units.",
            "recommended_action": "Expedite inbound replenishment freight or reallocate inventory from adjacent distribution centers."
        })
    return alerts


def dispatch_alert(engine, alert, config):
    """
    Route alert to enabled notification channels (Slack, Email, DB).
    """
    logger.info(f"Dispatching [{alert['severity']}] {alert['alert_title']}...")

    slack_ok = True
    if config["slack_enabled"] and config["slack_webhook"]:
        slack_ok = send_slack_notification(config["slack_webhook"], alert)

    email_ok = True
    if config["email_enabled"]:
        email_ok = send_email_notification(config, alert)

    status = "SENT" if (slack_ok and email_ok) else "PARTIAL_FAILURE"
    persist_alert_event(engine, alert, status=status)


def run_all_alerts(engine=None):
    """
    Evaluate all operational triggers and dispatch pending notifications.
    """
    print("=" * 70)
    print("RETAIL & SUPPLY CHAIN CONTROL TOWER: AUTOMATED ALERT ENGINE")
    print("=" * 70)

    if engine is None:
        engine = get_db_engine()

    cfg = load_alert_config()
    all_alerts = []

    # 1. Stockout & Low Stock
    try:
        a_stock = check_low_stock_alerts(engine)
        all_alerts.extend(a_stock)
    except Exception as e:
        logger.warning(f"Stock alert check skipped: {e}")

    # 2. Shipment Delays
    try:
        a_delays = check_shipment_delay_alerts(engine, threshold_days=cfg["delivery_delay_days"])
        all_alerts.extend(a_delays)
    except Exception as e:
        logger.warning(f"Delay alert check skipped: {e}")

    # 3. Forecast Shortage
    try:
        a_fc = check_forecast_shortage_alerts(engine)
        all_alerts.extend(a_fc)
    except Exception as e:
        logger.warning(f"Forecast alert check skipped: {e}")

    # Dispatch alerts
    for alt in all_alerts:
        dispatch_alert(engine, alt, cfg)

    print(f"\nDispatched {len(all_alerts):,} operational alerts.")
    print("=" * 70 + "\n")
    return all_alerts


if __name__ == "__main__":
    eng = get_db_engine()
    run_all_alerts(eng)
