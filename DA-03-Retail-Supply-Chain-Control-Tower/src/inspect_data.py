
import os
import pandas as pd

# Project directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RAW_DIR = os.path.join(BASE_DIR, "data", "raw")

def inspect_csv_files():

    print("=" * 70)
    print("OLIST DATASET INSPECTION")
    print("=" * 70)

    if not os.path.exists(RAW_DIR):
        print("ERROR: data/raw folder not found!")
        return

    files = [
        file for file in os.listdir(RAW_DIR)
        if file.lower().endswith(".csv")
    ]

    if not files:
        print("ERROR: No CSV files found!")
        return

    print(f"\nTotal CSV files found: {len(files)}")

    for file in sorted(files):

        file_path = os.path.join(RAW_DIR, file)

        print("\n" + "=" * 70)
        print(f"FILE: {file}")
        print("=" * 70)

        try:
            df = pd.read_csv(
                file_path,
                nrows=5,
                encoding="utf-8"
            )

            print("\nColumns:")
            print(df.columns.tolist())

            print("\nData types:")
            print(df.dtypes)

            print("\nFirst 5 records:")
            print(df.to_string(index=False))

            print("\nFile size:")
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            print(f"{size_mb:.2f} MB")

        except Exception as error:
            print(f"ERROR reading {file}: {error}")

    print("\n" + "=" * 70)
    print("DATASET INSPECTION COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    inspect_csv_files()
