-- ============================================================================
-- Westbridge Retail - database schema (SQLite)
-- Five tables: categories, customers, products, orders, order_items.
-- Run with foreign keys enabled:  PRAGMA foreign_keys = ON;
-- The DROP statements make the script safe to re-run (child tables first).
-- ============================================================================

DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS categories;

-- Product categories (12 rows)
CREATE TABLE categories (
    category_id    INTEGER PRIMARY KEY,
    category_name  TEXT    NOT NULL UNIQUE
);

-- Registered customers. Dates are stored as ISO text (YYYY-MM-DD), which
-- sorts correctly and works with SQLite's date functions.
CREATE TABLE customers (
    customer_id        INTEGER PRIMARY KEY,
    customer_name      TEXT NOT NULL,
    gender             TEXT NOT NULL
                       CHECK (gender IN ('Female', 'Male', 'Non-binary')),
    age_group          TEXT NOT NULL
                       CHECK (age_group IN ('18-24', '25-34', '35-44', '45-54', '55-64', '65+')),
    city               TEXT NOT NULL,
    region             TEXT NOT NULL,
    registration_date  TEXT NOT NULL
                       CHECK (registration_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')
);

-- Products and their current list price and unit cost
CREATE TABLE products (
    product_id    INTEGER PRIMARY KEY,
    product_name  TEXT    NOT NULL,
    category_id   INTEGER NOT NULL,
    unit_price    REAL    NOT NULL CHECK (unit_price > 0),
    unit_cost     REAL    NOT NULL CHECK (unit_cost > 0),
    CHECK (unit_cost < unit_price),
    FOREIGN KEY (category_id) REFERENCES categories (category_id)
);

-- One row per order. Cancelled orders stay in the table with order_status = 'Cancelled'.
CREATE TABLE orders (
    order_id      INTEGER PRIMARY KEY,
    customer_id   INTEGER NOT NULL,
    order_date    TEXT    NOT NULL
                  CHECK (order_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    sales_channel TEXT    NOT NULL CHECK (sales_channel IN ('Online', 'In-Store')),
    order_status  TEXT    NOT NULL CHECK (order_status IN ('Completed', 'Cancelled')),
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
);

-- One row per product on an order. unit_price is the price charged on the
-- order line; discount_amount is the total discount for the whole line.
CREATE TABLE order_items (
    order_item_id    INTEGER PRIMARY KEY,
    order_id         INTEGER NOT NULL,
    product_id       INTEGER NOT NULL,
    quantity         INTEGER NOT NULL CHECK (quantity > 0),
    unit_price       REAL    NOT NULL CHECK (unit_price > 0),
    discount_amount  REAL    NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    CHECK (discount_amount <= quantity * unit_price),
    UNIQUE (order_id, product_id),
    FOREIGN KEY (order_id)   REFERENCES orders (order_id),
    FOREIGN KEY (product_id) REFERENCES products (product_id)
);

-- Indexes on foreign keys and the most-filtered columns
CREATE INDEX idx_products_category    ON products (category_id);
CREATE INDEX idx_orders_customer      ON orders (customer_id);
CREATE INDEX idx_orders_date          ON orders (order_date);
CREATE INDEX idx_orders_status        ON orders (order_status);
CREATE INDEX idx_order_items_order    ON order_items (order_id);
CREATE INDEX idx_order_items_product  ON order_items (product_id);
