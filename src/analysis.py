"""
Analysis helpers used by the notebook.

- validate_result / run_validated: run a named SQL query and check the output
- data-quality functions: table sizes, missing values, duplicate keys,
  foreign key checks, date coverage and a revenue recalculation in pandas
- small helpers that prepare query results for charts

The business calculations themselves stay in the SQL files; Python is used for
checks, light reshaping and plotting.
"""

import pandas as pd

from src.database import get_connection, run_named_query, run_query

# Colour palette used for every chart
PALETTE = {
    "navy": "#243B53",
    "blue": "#3B82F6",
    "teal": "#0F766E",
    "light_gray": "#F3F4F6",
    "dark_gray": "#374151",
}

TABLES = ["categories", "customers", "products", "orders", "order_items"]
PRIMARY_KEYS = {
    "categories": "category_id",
    "customers": "customer_id",
    "products": "product_id",
    "orders": "order_id",
    "order_items": "order_item_id",
}
# (child table, child column, parent table, parent column)
FOREIGN_KEYS = [
    ("products", "category_id", "categories", "category_id"),
    ("orders", "customer_id", "customers", "customer_id"),
    ("order_items", "order_id", "orders", "order_id"),
    ("order_items", "product_id", "products", "product_id"),
]


# --------------------------------------------------------------------------
# Running and validating queries
# --------------------------------------------------------------------------
def validate_result(dataframe, query_name, required_columns=None, min_rows=1, no_nulls_in=None):
    """Raise ValueError if a query result is empty, missing columns, or has unexpected NULLs."""
    if len(dataframe) < min_rows:
        raise ValueError(f"{query_name}: expected at least {min_rows} row(s), got {len(dataframe)}")
    missing_columns = [c for c in (required_columns or []) if c not in dataframe.columns]
    if missing_columns:
        raise ValueError(f"{query_name}: missing columns {missing_columns}")
    for column in (no_nulls_in or []):
        if dataframe[column].isna().any():
            raise ValueError(f"{query_name}: column '{column}' contains NULL values")
    return dataframe


def run_validated(sql_file, query_name, required_columns=None, min_rows=1, no_nulls_in=None):
    """Run a named query from a SQL file and validate the result."""
    dataframe = run_named_query(sql_file, query_name)
    return validate_result(dataframe, query_name, required_columns, min_rows, no_nulls_in)


# --------------------------------------------------------------------------
# Data inspection
# --------------------------------------------------------------------------
def table_row_counts():
    """Row count for each table."""
    rows = []
    for table in TABLES:
        count = run_query(f"SELECT COUNT(*) AS n FROM {table}")["n"].iloc[0]
        rows.append({"table": table, "rows": int(count)})
    return pd.DataFrame(rows)


def column_types():
    """Declared column types for every table (from PRAGMA table_info)."""
    frames = []
    for table in TABLES:
        info = run_query(f"PRAGMA table_info({table})")
        info.insert(0, "table", table)
        frames.append(info[["table", "name", "type", "notnull", "pk"]])
    return pd.concat(frames, ignore_index=True)


def missing_values_report():
    """Count NULL / empty values in every column of every table."""
    rows = []
    with get_connection() as connection:
        for table in TABLES:
            dataframe = pd.read_sql_query(f"SELECT * FROM {table}", connection)
            for column in dataframe.columns:
                null_count = int(dataframe[column].isna().sum())
                if dataframe[column].dtype == object:
                    null_count += int((dataframe[column].astype(str).str.strip() == "").sum())
                rows.append({"table": table, "column": column, "missing_values": null_count})
    return pd.DataFrame(rows)


def duplicate_key_report():
    """Number of duplicated primary key values per table (should all be 0)."""
    rows = []
    for table, key in PRIMARY_KEYS.items():
        duplicates = run_query(
            f"SELECT COUNT(*) AS n FROM (SELECT {key} FROM {table} GROUP BY {key} HAVING COUNT(*) > 1)"
        )["n"].iloc[0]
        rows.append({"table": table, "primary_key": key, "duplicate_keys": int(duplicates)})
    return pd.DataFrame(rows)


def referential_integrity_report():
    """Count child rows whose foreign key has no matching parent (should all be 0)."""
    rows = []
    for child, child_col, parent, parent_col in FOREIGN_KEYS:
        orphans = run_query(
            f"""SELECT COUNT(*) AS n
                FROM {child} AS c
                LEFT JOIN {parent} AS p ON p.{parent_col} = c.{child_col}
                WHERE p.{parent_col} IS NULL"""
        )["n"].iloc[0]
        rows.append({"relationship": f"{child}.{child_col} -> {parent}.{parent_col}",
                     "orphan_rows": int(orphans)})
    return pd.DataFrame(rows)


def date_coverage():
    """First and last date in the main date columns."""
    return run_query(
        """
        SELECT 'orders.order_date' AS date_column,
               MIN(order_date) AS first_date, MAX(order_date) AS last_date,
               COUNT(DISTINCT STRFTIME('%Y-%m', order_date)) AS distinct_months
        FROM orders
        UNION ALL
        SELECT 'customers.registration_date', MIN(registration_date), MAX(registration_date),
               COUNT(DISTINCT STRFTIME('%Y-%m', registration_date))
        FROM customers
        """
    )


def business_rule_checks():
    """Check rules that the data should obey. 'violations' should be 0 for every rule."""
    checks = {
        "Discount greater than gross line amount": """
            SELECT COUNT(*) FROM order_items WHERE discount_amount > quantity * unit_price""",
        "Order line price differs from product list price": """
            SELECT COUNT(*) FROM order_items AS oi
            JOIN products AS p ON p.product_id = oi.product_id
            WHERE ROUND(oi.unit_price, 2) <> ROUND(p.unit_price, 2)""",
        "Order placed before customer registration": """
            SELECT COUNT(*) FROM orders AS o
            JOIN customers AS c ON c.customer_id = o.customer_id
            WHERE o.order_date < c.registration_date""",
        "Order without any order lines": """
            SELECT COUNT(*) FROM orders AS o
            WHERE NOT EXISTS (SELECT 1 FROM order_items AS oi WHERE oi.order_id = o.order_id)""",
        "Order date outside Jan 2024 - Dec 2025": """
            SELECT COUNT(*) FROM orders WHERE order_date < '2024-01-01' OR order_date > '2025-12-31'""",
        "Unit cost not below unit price": """
            SELECT COUNT(*) FROM products WHERE unit_cost >= unit_price""",
    }
    rows = []
    with get_connection() as connection:
        for rule, sql in checks.items():
            violations = connection.execute(sql).fetchone()[0]
            rows.append({"rule": rule, "violations": int(violations)})
    return pd.DataFrame(rows)


def sales_consistency_check():
    """
    Recalculate revenue and gross profit in pandas straight from the raw tables
    and compare with the SQL KPI queries. Cancelled orders are excluded.
    """
    with get_connection() as connection:
        orders = pd.read_sql_query("SELECT * FROM orders", connection)
        items = pd.read_sql_query("SELECT * FROM order_items", connection)
        products = pd.read_sql_query("SELECT product_id, unit_cost FROM products", connection)

    completed = items.merge(orders[orders["order_status"] == "Completed"][["order_id"]], on="order_id")
    completed = completed.merge(products, on="product_id")
    completed["line_revenue"] = completed["quantity"] * completed["unit_price"] - completed["discount_amount"]
    completed["line_gross_profit"] = completed["line_revenue"] - completed["quantity"] * completed["unit_cost"]

    pandas_revenue = round(completed["line_revenue"].sum(), 2)
    pandas_gross_profit = round(completed["line_gross_profit"].sum(), 2)
    pandas_orders = completed["order_id"].nunique()

    kpi = run_named_query("01_sales_performance.sql", "kpi_summary").iloc[0]
    by_product = run_named_query("02_product_performance.sql", "gross_profit_by_product")
    monthly = run_named_query("01_sales_performance.sql", "monthly_revenue")

    cancelled_revenue = items.merge(orders[orders["order_status"] == "Cancelled"][["order_id"]], on="order_id")
    cancelled_revenue = (cancelled_revenue["quantity"] * cancelled_revenue["unit_price"]
                         - cancelled_revenue["discount_amount"]).sum()

    rows = [
        ("Net revenue (completed orders)", pandas_revenue, round(float(kpi["net_revenue"]), 2)),
        ("Net revenue - sum of monthly query", pandas_revenue, round(float(monthly["net_revenue"].sum()), 2)),
        ("Completed orders", pandas_orders, int(kpi["completed_orders"])),
        ("Gross profit - sum of product query", pandas_gross_profit,
         round(float(by_product["gross_profit"].sum()), 2)),
    ]
    report = pd.DataFrame(rows, columns=["check", "pandas_value", "sql_value"])
    report["difference"] = (report["pandas_value"] - report["sql_value"]).round(2)
    report["matches"] = report["difference"].abs() < 0.05
    report.attrs["cancelled_revenue_excluded"] = round(float(cancelled_revenue), 2)
    return report


# --------------------------------------------------------------------------
# Preparing results for charts
# --------------------------------------------------------------------------
def add_month_start(dataframe, month_column="order_month"):
    """Add a datetime column (first day of the month) from a 'YYYY-MM' text column."""
    dataframe = dataframe.copy()
    dataframe["month_start"] = pd.to_datetime(dataframe[month_column] + "-01")
    return dataframe


def growth_for_plot(monthly_growth):
    """Drop the first month (no prior period) and add a colour flag for the diverging bar chart."""
    plot_data = add_month_start(monthly_growth).dropna(subset=["mom_growth_pct"]).copy()
    plot_data["direction"] = plot_data["mom_growth_pct"].apply(lambda v: "Increase" if v >= 0 else "Decrease")
    return plot_data


def format_currency(value, _position=None):
    """Format a number as $1,234 (works as a matplotlib tick formatter)."""
    return f"${value:,.0f}"


def format_currency_short(value, _position=None):
    """Format large numbers compactly: $1.2M, $85K."""
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:,.0f}"
