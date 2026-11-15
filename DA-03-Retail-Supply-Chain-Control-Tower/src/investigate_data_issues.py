
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"

def investigate():
    # Load only the files needed for investigation
    reviews = pd.read_csv(
        RAW_DIR / "olist_order_reviews_dataset.csv"
    )

    orders = pd.read_csv(
        RAW_DIR / "olist_orders_dataset.csv"
    )

    products = pd.read_csv(
        RAW_DIR / "olist_products_dataset.csv"
    )

    geolocation = pd.read_csv(
        RAW_DIR / "olist_geolocation_dataset.csv"
    )

    print("\n" + "=" * 65)
    print("1. REVIEW DUPLICATE INVESTIGATION")
    print("=" * 65)

    print("Total review records:", len(reviews))
    print("Unique review IDs:", reviews["review_id"].nunique())
    print("Unique order IDs:", reviews["order_id"].nunique())

    print(
        "Exact duplicate rows:",
        reviews.duplicated().sum()
    )

    duplicate_reviews = reviews[
        reviews.duplicated("review_id", keep=False)
    ].sort_values("review_id")

    print("\nRecords with repeated review IDs:")
    print(duplicate_reviews.head(15).to_string(index=False))

    print("\nOrders with multiple review records:")
    multiple_reviews = reviews[
        reviews.duplicated("order_id", keep=False)
    ]

    print(multiple_reviews.head(15).to_string(index=False))

    print("\n" + "=" * 65)
    print("2. ORDER STATUS AND MISSING DELIVERY DATES")
    print("=" * 65)

    print("\nOrder status counts:")
    print(orders["order_status"].value_counts(dropna=False))

    date_columns = [
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date"
    ]

    print("\nMissing delivery timestamps by order status:")
    print(
        orders.groupby("order_status")[date_columns]
        .agg(lambda col: col.isna().sum())
    )

    print("\n" + "=" * 65)
    print("3. PRODUCT MISSING VALUE INVESTIGATION")
    print("=" * 65)

    missing_category = products[
        products["product_category_name"].isna()
    ]

    print("Products without category:", len(missing_category))
    print(missing_category.head(10).to_string(index=False))

    dimension_columns = [
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm"
    ]

    missing_dimensions = products[
        products[dimension_columns].isna().any(axis=1)
    ]

    print("\nProducts with missing physical dimensions:")
    print(missing_dimensions.to_string(index=False))

    print("\n" + "=" * 65)
    print("4. GEOLOCATION ZIP CODE INVESTIGATION")
    print("=" * 65)

    print("Total geolocation records:", len(geolocation))
    print(
        "Unique ZIP prefixes:",
        geolocation["geolocation_zip_code_prefix"].nunique()
    )

    print(
        "Duplicate ZIP prefix records:",
        geolocation.duplicated(
            "geolocation_zip_code_prefix"
        ).sum()
    )

    print("\nSample ZIP prefixes with multiple coordinates:")
    print(
        geolocation[
            geolocation.duplicated(
                "geolocation_zip_code_prefix",
                keep=False
            )
        ].head(10).to_string(index=False)
    )

    print("\n" + "=" * 65)
    print("INVESTIGATION COMPLETED")
    print("=" * 65)


if __name__ == "__main__":
    investigate()


