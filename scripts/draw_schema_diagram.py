"""
Draw assets/database_schema.png from the real database.

Table names, columns, types, primary keys and foreign keys are read from the
SQLite file with PRAGMA statements, so the diagram always matches the schema
that was actually created.

Usage (from the repository root, after building the database):
    python scripts/draw_schema_diagram.py
"""

import sqlite3
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "database" / "retail_analytics.db"
OUTPUT_PATH = PROJECT_ROOT / "assets" / "database_schema.png"

NAVY = "#243B53"
BLUE = "#3B82F6"
TEAL = "#0F766E"
LIGHT_GRAY = "#F3F4F6"
DARK_GRAY = "#374151"

# Left-to-right order that keeps the relationship lines short and uncrossed.
TABLE_ORDER = ["categories", "products", "order_items", "orders", "customers"]
BOX_WIDTH = 3.6
BOX_GAP = 1.5
ROW_HEIGHT = 0.5
HEADER_HEIGHT = 0.7


def read_schema(connection):
    """Return {table: [column dicts]} and a list of foreign key relationships."""
    tables = {}
    foreign_keys = []
    for table in TABLE_ORDER:
        columns = []
        for _, name, col_type, not_null, _, pk in connection.execute(f"PRAGMA table_info({table})"):
            columns.append({"name": name, "type": col_type, "not_null": bool(not_null), "pk": bool(pk)})
        fk_columns = set()
        for row in connection.execute(f"PRAGMA foreign_key_list({table})"):
            _, _, parent_table, from_column, to_column = row[0], row[1], row[2], row[3], row[4]
            foreign_keys.append((table, from_column, parent_table, to_column))
            fk_columns.add(from_column)
        for column in columns:
            column["fk"] = column["name"] in fk_columns
        tables[table] = columns
    return tables, foreign_keys


def main():
    if not DB_PATH.exists():
        print("Database not found. Run python scripts/load_database.py first.", file=sys.stderr)
        sys.exit(1)

    connection = sqlite3.connect(DB_PATH)
    try:
        tables, foreign_keys = read_schema(connection)
    finally:
        connection.close()

    max_rows = max(len(columns) for columns in tables.values())
    figure_width = len(TABLE_ORDER) * BOX_WIDTH + (len(TABLE_ORDER) - 1) * BOX_GAP + 1.0
    figure_height = HEADER_HEIGHT + max_rows * ROW_HEIGHT + 2.6
    fig, ax = plt.subplots(figsize=(figure_width, figure_height))
    ax.set_xlim(-0.5, figure_width - 0.5)
    ax.set_ylim(-(HEADER_HEIGHT + max_rows * ROW_HEIGHT + 1.4), 1.6)
    ax.axis("off")

    positions = {}   # table -> x of left edge
    row_centres = {}  # (table, column) -> y centre
    for index, table in enumerate(TABLE_ORDER):
        x_left = index * (BOX_WIDTH + BOX_GAP)
        positions[table] = x_left
        columns = tables[table]
        box_height = HEADER_HEIGHT + len(columns) * ROW_HEIGHT

        ax.add_patch(FancyBboxPatch((x_left, -box_height), BOX_WIDTH, box_height,
                                    boxstyle="round,pad=0,rounding_size=0.08",
                                    facecolor="white", edgecolor=NAVY, linewidth=1.6, zorder=2))
        ax.add_patch(Rectangle((x_left, -HEADER_HEIGHT), BOX_WIDTH, HEADER_HEIGHT,
                               facecolor=NAVY, edgecolor=NAVY, zorder=3))
        ax.text(x_left + BOX_WIDTH / 2, -HEADER_HEIGHT / 2, table, color="white",
                ha="center", va="center", fontsize=13, fontweight="bold", zorder=4)

        for row_index, column in enumerate(columns):
            y_top = -HEADER_HEIGHT - row_index * ROW_HEIGHT
            y_centre = y_top - ROW_HEIGHT / 2
            row_centres[(table, column["name"])] = y_centre
            if row_index % 2 == 1:
                ax.add_patch(Rectangle((x_left, y_top - ROW_HEIGHT), BOX_WIDTH, ROW_HEIGHT,
                                       facecolor=LIGHT_GRAY, edgecolor="none", zorder=2.5))
            tag = "PK" if column["pk"] else ("FK" if column["fk"] else "")
            tag_color = TEAL if column["pk"] else BLUE
            if tag:
                ax.text(x_left + 0.15, y_centre, tag, color=tag_color, fontsize=9.5,
                        fontweight="bold", va="center", zorder=4)
            ax.text(x_left + 0.75, y_centre, column["name"], color=DARK_GRAY, fontsize=10.5,
                    va="center", fontweight="bold" if column["pk"] else "normal", zorder=4)
            ax.text(x_left + BOX_WIDTH - 0.15, y_centre, column["type"], color="#6B7280",
                    fontsize=9.5, va="center", ha="right", zorder=4)

    # Relationship lines: child foreign key (many) -> parent primary key (one).
    for child, child_column, parent, parent_column in foreign_keys:
        child_x, parent_x = positions[child], positions[parent]
        child_y = row_centres[(child, child_column)]
        parent_y = row_centres[(parent, parent_column)]
        if child_x > parent_x:   # parent is to the left of the child
            start_x, end_x = child_x, parent_x + BOX_WIDTH
            many_x, one_x, ha_many, ha_one = start_x - 0.12, end_x + 0.12, "right", "left"
        else:                    # parent is to the right of the child
            start_x, end_x = child_x + BOX_WIDTH, parent_x
            many_x, one_x, ha_many, ha_one = start_x + 0.12, end_x - 0.12, "left", "right"
        ax.plot([start_x, end_x], [child_y, parent_y], color=BLUE, linewidth=1.8, zorder=1)
        ax.plot([start_x, end_x], [child_y, parent_y], marker="o", markersize=5, color=BLUE,
                linestyle="none", zorder=5)
        ax.text(many_x, child_y + 0.22, "N", color=BLUE, fontsize=10.5, fontweight="bold",
                ha=ha_many, va="bottom", zorder=5)
        ax.text(one_x, parent_y + 0.22, "1", color=BLUE, fontsize=10.5, fontweight="bold",
                ha=ha_one, va="bottom", zorder=5)

    ax.text(-0.3, 1.25, "Westbridge Retail - database schema", fontsize=17, fontweight="bold",
            color=NAVY, ha="left", va="center")
    ax.text(-0.3, 0.7, "SQLite, 5 tables. PK = primary key, FK = foreign key, N : 1 = many rows point to one parent row.",
            fontsize=10.5, color=DARK_GRAY, ha="left", va="center")
    ax.text(-0.3, -(HEADER_HEIGHT + max_rows * ROW_HEIGHT + 0.9),
            "Generated from database/retail_analytics.db with PRAGMA table_info and PRAGMA foreign_key_list. "
            "Synthetic data.", fontsize=9, color="#6B7280", ha="left", va="center")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"Saved {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
