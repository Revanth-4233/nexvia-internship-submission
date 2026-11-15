
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def load_csv(filename):
    return pd.read_csv(
        RAW_DIR / filename,
        low_memory=False
    )


def save_csv(df, filename):
    output_path = PROCESSED_DIR / filename
    df.to_csv(output_path, index=False)
    print(f"Saved: {output_path.name} | Rows: {len(df):,}")


def clean_orders():
    df = load_csv("olist_orders_dataset.csv")

    date_columns = [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date"
    ]

    for col in date_columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    save_csv(df, "orders_clean.csv")
    return df


def clean_customers():
    df = load_csv("olist_customers_dataset.csv")

    df["customer_zip_code_prefix"] = (
        df["customer_zip_code_prefix"].astype(str).str.zfill(5)
    )

    save_csv(df, "customers_clean.csv")


def clean_sellers():
    df = load_csv("olist_sellers_dataset.csv")

    df["seller_zip_code_prefix"] = (
        df["seller_zip_code_prefix"].astype(str).str.zfill(5)
    )

    save_csv(df, "sellers_clean.csv")


def clean_products():
    products = load_csv("olist_products_dataset.csv")
    translations = load_csv("product_category_name_translation.csv")

    products = products.merge(
        translations,
        on="product_category_name",
        how="left",
        validate="many_to_one"
    )

    products["product_category_name"] = (
        products["product_category_name"].fillna("unknown")
    )

    products["product_category_name_english"] = (
        products["product_category_name_english"]
        .fillna(products["product_category_name"])
    )

    # Keep missing physical measurements as NULL.
    save_csv(products, "products_clean.csv")


def clean_order_items():
    df = load_csv("olist_order_items_dataset.csv")

    df["shipping_limit_date"] = pd.to_datetime(
        df["shipping_limit_date"],
        errors="coerce"
    )

    save_csv(df, "order_items_clean.csv")


def clean_payments():
    df = load_csv("olist_order_payments_dataset.csv")

    save_csv(df, "payments_clean.csv")


def clean_reviews():
    df = load_csv("olist_order_reviews_dataset.csv")

    # Source review_id is not unique.
    # Create our own unique row identifier.
    df.insert(
        0,
        "review_row_id",
        range(1, len(df) + 1)
    )

    date_columns = [
        "review_creation_date",
        "review_answer_timestamp"
    ]

    for col in date_columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    # Preserve missing comments and all original review rows.
    save_csv(df, "reviews_clean.csv")


def clean_geolocation():
    df = load_csv("olist_geolocation_dataset.csv")

    df["geolocation_zip_code_prefix"] = (
        df["geolocation_zip_code_prefix"]
        .astype(str)
        .str.zfill(5)
    )

    # Aggregate multiple coordinate points per ZIP prefix.
    result = (
        df.groupby("geolocation_zip_code_prefix")
        .agg(
            geolocation_lat=("geolocation_lat", "mean"),
            geolocation_lng=("geolocation_lng", "mean"),
            geolocation_city=(
                "geolocation_city",
                lambda x: x.mode().iloc[0] if not x.mode().empty else None
            ),
            geolocation_state=(
                "geolocation_state",
                lambda x: x.mode().iloc[0] if not x.mode().empty else None
            )
        )
        .reset_index()
    )

    save_csv(result, "geolocation_clean.csv")


def main():
    print("=" * 65)
    print("OLIST DATA CLEANING PIPELINE")
    print("=" * 65)

    clean_orders()
    clean_customers()
    clean_sellers()
    clean_products()
    clean_order_items()
    clean_payments()
    clean_reviews()
    clean_geolocation()

    print("\n" + "=" * 65)
    print("DATA CLEANING COMPLETED")
    print("=" * 65)


if __name__ == "__main__":
    main()


