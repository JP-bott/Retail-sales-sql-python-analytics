"""
Run the project checks and print PASS / FAIL for each one.

Usage (from the repository root, after building the database):
    python scripts/validate_project.py

Checks cover the CSV files, the database, every SQL analysis query, the main
business rules (cancelled orders excluded, discounts, growth, RFM), the chart
files, and whether the key figures quoted in README.md match the database.
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis import (FOREIGN_KEYS, PRIMARY_KEYS, TABLES, business_rule_checks,  # noqa: E402
                          duplicate_key_report, referential_integrity_report,
                          sales_consistency_check)
from src.database import DB_PATH, SQL_ANALYSIS_DIR, load_sql_file, run_query  # noqa: E402

RAW_DIR = PROJECT_ROOT / "data" / "raw"
results = []


def check(description, condition, detail=""):
    results.append((description, bool(condition), detail))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}" + (f"  ({detail})" if detail else ""))


def main():
    # --- CSV files -------------------------------------------------------
    csv_frames = {}
    for table in TABLES:
        path = RAW_DIR / f"{table}.csv"
        try:
            csv_frames[table] = pd.read_csv(path)
            check(f"CSV loads: {path.name}", True, f"{len(csv_frames[table]):,} rows")
        except Exception as error:  # noqa: BLE001
            check(f"CSV loads: {path.name}", False, str(error))
    if len(csv_frames) < len(TABLES):
        sys.exit(1)

    # --- Database --------------------------------------------------------
    check("Database file exists", DB_PATH.exists())
    with sqlite3.connect(DB_PATH) as connection:
        db_tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")}
        check("Database has exactly the 5 expected tables", db_tables == set(TABLES), str(sorted(db_tables)))
        for table in TABLES:
            db_rows = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            check(f"Row count matches CSV: {table}", db_rows == len(csv_frames[table]), f"{db_rows:,}")
        declared_fks = set()
        for table in TABLES:
            for row in connection.execute(f"PRAGMA foreign_key_list({table})"):
                declared_fks.add((table, row[3], row[2], row[4]))
        check("Declared foreign keys match the 4 expected relationships", declared_fks == set(FOREIGN_KEYS))
        check("PRAGMA foreign_key_check returns no violations",
              connection.execute("PRAGMA foreign_key_check").fetchall() == [])

    check("No duplicate primary keys", (duplicate_key_report()["duplicate_keys"] == 0).all())
    check("No orphan foreign key rows", (referential_integrity_report()["orphan_rows"] == 0).all())
    check("Business rules have 0 violations", (business_rule_checks()["violations"] == 0).all())

    counts = {table: len(csv_frames[table]) for table in TABLES}
    check("Dataset size in expected ranges",
          counts["customers"] == 1000 and counts["products"] == 100 and counts["orders"] == 15000
          and 25000 <= counts["order_items"] <= 35000 and 10 <= counts["categories"] <= 15
          and 4 <= csv_frames["customers"]["region"].nunique() <= 6, str(counts))

    # --- SQL scripts -----------------------------------------------------
    total_queries = 0
    for sql_path in sorted(SQL_ANALYSIS_DIR.glob("*.sql")):
        for name, sql in load_sql_file(sql_path.name).items():
            total_queries += 1
            try:
                frame = run_query(sql)
                check(f"SQL runs: {sql_path.name} / {name}", len(frame) > 0, f"{len(frame)} rows")
            except Exception as error:  # noqa: BLE001
                check(f"SQL runs: {sql_path.name} / {name}", False, str(error))
    check("All six analysis files contain queries", len(list(SQL_ANALYSIS_DIR.glob("*.sql"))) == 6,
          f"{total_queries} queries")

    # --- Business logic --------------------------------------------------
    consistency = sales_consistency_check()
    check("SQL revenue / orders / gross profit match pandas recalculation", consistency["matches"].all())

    all_lines_revenue = run_query(
        "SELECT SUM(quantity * unit_price - discount_amount) AS r FROM order_items")["r"].iloc[0]
    completed_revenue = run_query("SELECT net_revenue FROM (" + load_sql_file(
        "01_sales_performance.sql")["kpi_summary"].rstrip(";") + ")")["net_revenue"].iloc[0]
    check("Revenue KPI excludes cancelled orders", completed_revenue < all_lines_revenue,
          f"completed {completed_revenue:,.2f} < all lines {all_lines_revenue:,.2f}")

    counts_row = run_query("SELECT * FROM (" + load_sql_file("03_customer_behavior.sql")["customer_counts"]
                           .rstrip(";") + ")").iloc[0]
    check("Customer counts include customers with no purchases",
          counts_row["registered_customers"] == 1000 and counts_row["customers_without_purchases"] > 0,
          f"{int(counts_row['customers_without_purchases'])} without purchases")
    check("Buyers + non-buyers = registered customers",
          counts_row["customers_with_purchases"] + counts_row["customers_without_purchases"]
          == counts_row["registered_customers"])

    growth = run_query(load_sql_file("04_monthly_growth.sql")["monthly_growth"])
    check("Monthly growth: 24 months, first month has NULL growth",
          len(growth) == 24 and pd.isna(growth.loc[0, "mom_growth_pct"]) and growth["mom_growth_pct"].iloc[1:].notna().all())

    rfm_sql = (SQL_ANALYSIS_DIR / "05_customer_segmentation.sql").read_text()
    check("RFM uses fixed reference date 2025-12-31 (not the system date)",
          "2025-12-31" in rfm_sql and "'now'" not in rfm_sql.lower())
    rfm = run_query(load_sql_file("05_customer_segmentation.sql")["rfm_customer_segments"])
    check("RFM assigns a segment to all 1,000 customers",
          len(rfm) == 1000 and rfm["segment"].notna().all(), str(rfm["segment"].value_counts().to_dict()))

    # --- Files -----------------------------------------------------------
    chart_files = sorted((PROJECT_ROOT / "assets" / "charts").glob("*.png"))
    check("8 chart PNG files exist and are not empty",
          len(chart_files) == 8 and all(f.stat().st_size > 5000 for f in chart_files))
    check("Schema diagram exists", (PROJECT_ROOT / "assets" / "database_schema.png").stat().st_size > 5000)

    required_files = ["README.md", "requirements.txt", ".gitignore", "LICENSE",
                      "notebooks/retail_business_analysis.ipynb", ".devcontainer/devcontainer.json",
                      "scripts/generate_data.py", "scripts/load_database.py", "src/database.py",
                      "src/analysis.py", "sql/01_create_tables.sql", "reports/business_analysis_report.html"]
    missing = [name for name in required_files if not (PROJECT_ROOT / name).exists()]
    check("All required project files exist", not missing, f"missing: {missing}" if missing else "")

    # --- README figures --------------------------------------------------
    readme_path = PROJECT_ROOT / "README.md"
    if readme_path.exists():
        readme = readme_path.read_text(encoding="utf-8")
        kpi = run_query(load_sql_file("01_sales_performance.sql")["kpi_summary"]).iloc[0]
        quoted = {
            "net revenue": f"${kpi['net_revenue']:,.2f}",
            "completed orders": f"{int(kpi['completed_orders']):,}",
            "average order value": f"${kpi['avg_order_value']:,.2f}",
            "units sold": f"{int(kpi['units_sold']):,}",
        }
        for label, text in quoted.items():
            check(f"README quotes the correct {label}", text in readme, text)

    failed = [description for description, passed, _ in results if not passed]
    print(f"\n{len(results) - len(failed)} of {len(results)} checks passed.")
    if failed:
        print("Failed:", *failed, sep="\n  - ")
        sys.exit(1)


if __name__ == "__main__":
    main()
