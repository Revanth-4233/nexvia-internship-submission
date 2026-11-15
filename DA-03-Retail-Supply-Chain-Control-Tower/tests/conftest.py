"""
Pytest configuration and shared fixtures for Control Tower test suite.
"""

import os
import sys
from pathlib import Path
import pytest
import pandas as pd
from dotenv import load_dotenv

# Ensure src is on path
BASE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

load_dotenv(BASE_DIR / ".env")


@pytest.fixture(scope="session")
def project_dirs():
    """Return dictionary of primary project directory paths."""
    return {
        "base": BASE_DIR,
        "raw": BASE_DIR / "data" / "raw",
        "processed": BASE_DIR / "data" / "processed",
        "database": BASE_DIR / "database",
        "src": SRC_DIR,
        "docs": BASE_DIR / "docs"
    }


@pytest.fixture(scope="session")
def sample_clean_orders(project_dirs):
    """Load sample of cleaned orders for data testing."""
    orders_path = project_dirs["processed"] / "orders_clean.csv"
    if orders_path.exists():
        return pd.read_csv(orders_path, nrows=500)
    return pd.DataFrame()


@pytest.fixture(scope="session")
def sample_clean_products(project_dirs):
    """Load sample of cleaned products."""
    products_path = project_dirs["processed"] / "products_clean.csv"
    if products_path.exists():
        return pd.read_csv(products_path, nrows=500)
    return pd.DataFrame()


@pytest.fixture(scope="session")
def db_engine():
    """Attempt database connection fixture, graceful fallback."""
    try:
        from kpi_calculation import get_db_engine
        engine = get_db_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        return engine
    except Exception:
        return None
