"""
Build database/retail_analytics.db from sql/01_create_tables.sql and the CSV
files in data/raw/.

The script always starts from a clean schema (the SQL file drops and recreates
every table), so running it again never produces duplicate records.

Usage (from the repository root):
    python scripts/load_database.py
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "database" / "retail_analytics.db"
SCHEMA_PATH = PROJECT_ROOT / "sql" / "01_create_tables.sql"
RAW_DIR = PROJECT_ROOT / "data" / "raw"

# Parent tables first so foreign keys are satisfied while loading.
LOAD_ORDER = ["categories", "customers", "products", "orders", "order_items"]


def create_schema(connection):
    """Run the CREATE TABLE script."""
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_table(connection, table_name):
    """Read one CSV and append its rows to the matching table."""
    csv_path = RAW_DIR / f"{table_name}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing {csv_path}. Run scripts/generate_data.py first.")
    dataframe = pd.read_csv(csv_path)
    dataframe.to_sql(table_name, connection, if_exists="append", index=False)
    return len(dataframe)


def check_database(connection):
    """Basic sanity checks after loading. Raises ValueError if something is wrong."""
    foreign_key_problems = connection.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_problems:
        raise ValueError(f"Foreign key violations found: {foreign_key_problems[:5]}")
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise ValueError(f"SQLite integrity check failed: {integrity}")


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        connection = sqlite3.connect(DB_PATH)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            create_schema(connection)
            print(f"Loading CSV files into {DB_PATH.relative_to(PROJECT_ROOT)}")
            for table_name in LOAD_ORDER:
                row_count = load_table(connection, table_name)
                print(f"  {table_name:<12} {row_count:>7,} rows")
            connection.commit()
            check_database(connection)
            print("Foreign key check and integrity check passed.")
        finally:
            connection.close()
    except (FileNotFoundError, sqlite3.Error, ValueError) as error:
        print(f"Database build failed: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
