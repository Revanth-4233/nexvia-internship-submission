
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
OUTPUT_DIR = BASE_DIR / "data" / "processed"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Expected primary keys
PRIMARY_KEYS = {
    "olist_customers_dataset.csv": ["customer_id"],
    "olist_orders_dataset.csv": ["order_id"],
    "olist_order_items_dataset.csv": ["order_id", "order_item_id"],
    "olist_order_payments_dataset.csv": ["order_id", "payment_sequential"],
    "olist_order_reviews_dataset.csv": ["review_id"],
    "olist_products_dataset.csv": ["product_id"],
    "olist_sellers_dataset.csv": ["seller_id"],
}

# Relationships to validate
RELATIONSHIPS = [
    ("olist_orders_dataset.csv", "customer_id",
     "olist_customers_dataset.csv", "customer_id"),

    ("olist_order_items_dataset.csv", "order_id",
     "olist_orders_dataset.csv", "order_id"),

    ("olist_order_items_dataset.csv", "product_id",
     "olist_products_dataset.csv", "product_id"),

    ("olist_order_items_dataset.csv", "seller_id",
     "olist_sellers_dataset.csv", "seller_id"),

    ("olist_order_payments_dataset.csv", "order_id",
     "olist_orders_dataset.csv", "order_id"),

    ("olist_order_reviews_dataset.csv", "order_id",
     "olist_orders_dataset.csv", "order_id"),
]

def audit_dataset():
    report = []
    data = {}

    report.append("=" * 70)
    report.append("OLIST DATA QUALITY AUDIT")
    report.append("=" * 70)

    # Read all CSV files
    for file_path in sorted(RAW_DIR.glob("*.csv")):
        print(f"Reading: {file_path.name}")

        df = pd.read_csv(file_path, low_memory=False)
        data[file_path.name] = df

        report.append(f"\nFILE: {file_path.name}")
        report.append(f"Rows: {len(df):,}")
        report.append(f"Columns: {len(df.columns)}")

        report.append("\nMissing values:")
        missing = df.isnull().sum()

        if missing.sum() == 0:
            report.append("No missing values found.")
        else:
            for column, count in missing.items():
                if count > 0:
                    percentage = count / len(df) * 100
                    report.append(
                        f"{column}: {count:,} ({percentage:.2f}%)"
                    )

        report.append("\nDuplicate key records:")
        if file_path.name in PRIMARY_KEYS:
            keys = PRIMARY_KEYS[file_path.name]
            duplicates = df.duplicated(subset=keys).sum()
            report.append(f"Duplicate primary keys: {duplicates:,}")
        else:
            report.append("No primary key configured for this file.")

    # Check relationships between datasets
    report.append("\n" + "=" * 70)
    report.append("FOREIGN KEY / RELATIONSHIP CHECKS")
    report.append("=" * 70)

    for child_file, child_col, parent_file, parent_col in RELATIONSHIPS:
        child_values = set(data[child_file][child_col].dropna())
        parent_values = set(data[parent_file][parent_col].dropna())

        unmatched = child_values - parent_values

        report.append(
            f"\n{child_file}.{child_col} -> "
            f"{parent_file}.{parent_col}"
        )
        report.append(f"Unmatched unique values: {len(unmatched):,}")

    # Check date columns
    date_columns = {
        "olist_orders_dataset.csv": [
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
        "olist_order_items_dataset.csv": [
            "shipping_limit_date"
        ],
    }

    report.append("\n" + "=" * 70)
    report.append("DATE VALIDATION")
    report.append("=" * 70)

    for filename, columns in date_columns.items():
        df = data[filename]

        for column in columns:
            parsed = pd.to_datetime(df[column], errors="coerce")
            invalid = df[column].notna() & parsed.isna()

            report.append(
                f"{filename} | {column}: "
                f"{invalid.sum():,} invalid dates"
            )

    report.append("\n" + "=" * 70)
    report.append("AUDIT COMPLETED")
    report.append("=" * 70)

    output_file = OUTPUT_DIR / "data_quality_report.txt"
    output_file.write_text("\n".join(report), encoding="utf-8")

    print("\n".join(report))
    print(f"\nReport saved to: {output_file}")


if __name__ == "__main__":
    audit_dataset()

