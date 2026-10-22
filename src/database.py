"""
Database helpers: connect to SQLite, run SQL, return pandas DataFrames.

SQL lives in the .sql files under sql/analysis/. Each query in those files
starts with a marker line:

    -- name: monthly_revenue

load_sql_file() splits a file on those markers and returns {name: sql_text},
so the notebook can run a query by name instead of copying SQL into Python.
"""

import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "database" / "retail_analytics.db"
SQL_ANALYSIS_DIR = PROJECT_ROOT / "sql" / "analysis"

QUERY_MARKER = re.compile(r"^--\s*name:\s*(\w+)\s*$", re.MULTILINE)


@contextmanager
def get_connection(db_path=DB_PATH):
    """Open a SQLite connection with foreign keys on and always close it."""
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(
            f"Database not found at {db_path}. Run: python scripts/load_database.py"
        )
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
    finally:
        connection.close()


def run_query(sql, params=None, db_path=DB_PATH):
    """Run one SQL statement and return the result as a DataFrame."""
    with get_connection(db_path) as connection:
        return pd.read_sql_query(sql, connection, params=params)


def load_sql_file(sql_file):
    """Split a SQL file into {query_name: sql_text} using the '-- name:' markers."""
    sql_path = Path(sql_file)
    if not sql_path.is_absolute():
        sql_path = SQL_ANALYSIS_DIR / sql_path
    text = sql_path.read_text(encoding="utf-8")

    markers = list(QUERY_MARKER.finditer(text))
    if not markers:
        raise ValueError(f"No '-- name:' markers found in {sql_path.name}")

    queries = {}
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        queries[marker.group(1)] = text[marker.end():end].strip()
    return queries


def run_named_query(sql_file, query_name, params=None, db_path=DB_PATH):
    """Run one named query from a SQL file, e.g. run_named_query('01_sales_performance.sql', 'kpi_summary')."""
    queries = load_sql_file(sql_file)
    if query_name not in queries:
        raise KeyError(f"'{query_name}' not found in {sql_file}. Available: {list(queries)}")
    return run_query(queries[query_name], params=params, db_path=db_path)
