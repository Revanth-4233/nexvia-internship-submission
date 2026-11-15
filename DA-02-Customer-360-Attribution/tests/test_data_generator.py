import csv, os
from data_generator.generate_data import generate


def read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_generator_is_deterministic(tmp_path):
    a = generate(300, 7, str(tmp_path / "a"))
    b = generate(300, 7, str(tmp_path / "b"))
    assert a == b
    assert read(tmp_path / "a" / "crm_orders.csv") == read(tmp_path / "b" / "crm_orders.csv")


def test_referential_integrity(tmp_path):
    generate(300, 11, str(tmp_path))
    contacts = {r["contact_id"] for r in read(tmp_path / "crm_contacts.csv")}
    orders = read(tmp_path / "crm_orders.csv")
    assert orders and all(o["contact_id"] in contacts for o in orders)
    emails = [r["email"].lower() for r in read(tmp_path / "crm_contacts.csv")]
    assert len(emails) == len(set(emails))


def test_every_order_has_a_purchase_event(tmp_path):
    generate(300, 3, str(tmp_path))
    order_ids = {o["order_id"] for o in read(tmp_path / "crm_orders.csv")}
    web = {r["transaction_id"] for r in read(tmp_path / "ga4_events.csv") if r["transaction_id"]}
    app = {r["order_id"] for r in read(tmp_path / "segment_tracks.csv") if r["order_id"]}
    assert order_ids == web | app
