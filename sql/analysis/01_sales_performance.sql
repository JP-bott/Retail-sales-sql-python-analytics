-- ============================================================================
-- 01 SALES PERFORMANCE
-- Each query starts with a "-- name: <query_name>" line. src/database.py splits
-- the file on those markers so the notebook can run one query by name.
--
-- Definitions used in every file:
--   line revenue = quantity * unit_price - discount_amount
--   "completed" sales only: orders.order_status = 'Completed'
--   (cancelled orders stay in the database but are excluded from revenue KPIs)
-- ============================================================================


-- name: kpi_summary
-- Headline KPIs for completed orders: orders, units, gross sales, discounts,
-- net revenue and average order value (net revenue / completed orders).
SELECT
    COUNT(DISTINCT o.order_id)                                         AS completed_orders,
    SUM(oi.quantity)                                                   AS units_sold,
    ROUND(SUM(oi.quantity * oi.unit_price), 2)                         AS gross_sales,
    ROUND(SUM(oi.discount_amount), 2)                                  AS total_discounts,
    ROUND(SUM(oi.quantity * oi.unit_price - oi.discount_amount), 2)    AS net_revenue,
    ROUND(SUM(oi.quantity * oi.unit_price - oi.discount_amount)
          / COUNT(DISTINCT o.order_id), 2)                             AS avg_order_value
FROM orders AS o
JOIN order_items AS oi ON oi.order_id = o.order_id
WHERE o.order_status = 'Completed';


-- name: monthly_revenue
-- How much revenue, how many orders and what average order value in each month?
SELECT
    STRFTIME('%Y-%m', o.order_date)                                    AS order_month,
    COUNT(DISTINCT o.order_id)                                         AS completed_orders,
    SUM(oi.quantity)                                                   AS units_sold,
    ROUND(SUM(oi.quantity * oi.unit_price - oi.discount_amount), 2)    AS net_revenue,
    ROUND(SUM(oi.quantity * oi.unit_price - oi.discount_amount)
          / COUNT(DISTINCT o.order_id), 2)                             AS avg_order_value
FROM orders AS o
JOIN order_items AS oi ON oi.order_id = o.order_id
WHERE o.order_status = 'Completed'
GROUP BY STRFTIME('%Y-%m', o.order_date)
ORDER BY order_month;


-- name: revenue_by_channel
-- Online vs in-store: revenue, orders, average order value and share of revenue.
SELECT
    o.sales_channel,
    COUNT(DISTINCT o.order_id)                                         AS completed_orders,
    SUM(oi.quantity)                                                   AS units_sold,
    ROUND(SUM(oi.quantity * oi.unit_price - oi.discount_amount), 2)    AS net_revenue,
    ROUND(SUM(oi.quantity * oi.unit_price - oi.discount_amount)
          / COUNT(DISTINCT o.order_id), 2)                             AS avg_order_value,
    ROUND(100.0 * SUM(oi.quantity * oi.unit_price - oi.discount_amount)
          / SUM(SUM(oi.quantity * oi.unit_price - oi.discount_amount)) OVER (), 1)
                                                                       AS revenue_share_pct
FROM orders AS o
JOIN order_items AS oi ON oi.order_id = o.order_id
WHERE o.order_status = 'Completed'
GROUP BY o.sales_channel
ORDER BY net_revenue DESC;


-- name: revenue_by_region
-- Which regions generate the most revenue? Region comes from the customer record.
SELECT
    c.region,
    COUNT(DISTINCT c.customer_id)                                      AS buying_customers,
    COUNT(DISTINCT o.order_id)                                         AS completed_orders,
    ROUND(SUM(oi.quantity * oi.unit_price - oi.discount_amount), 2)    AS net_revenue,
    ROUND(SUM(oi.quantity * oi.unit_price - oi.discount_amount)
          / COUNT(DISTINCT o.order_id), 2)                             AS avg_order_value,
    ROUND(100.0 * SUM(oi.quantity * oi.unit_price - oi.discount_amount)
          / SUM(SUM(oi.quantity * oi.unit_price - oi.discount_amount)) OVER (), 1)
                                                                       AS revenue_share_pct
FROM orders AS o
JOIN order_items AS oi ON oi.order_id = o.order_id
JOIN customers   AS c  ON c.customer_id = o.customer_id
WHERE o.order_status = 'Completed'
GROUP BY c.region
ORDER BY net_revenue DESC;


-- name: cancellations_by_channel
-- Cancellations are analysed explicitly here (and only here): what share of
-- orders is cancelled in each channel, and how much sales value did that remove?
SELECT
    o.sales_channel,
    COUNT(DISTINCT o.order_id)                                         AS total_orders,
    COUNT(DISTINCT CASE WHEN o.order_status = 'Cancelled' THEN o.order_id END)
                                                                       AS cancelled_orders,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN o.order_status = 'Cancelled' THEN o.order_id END)
          / COUNT(DISTINCT o.order_id), 2)                             AS cancellation_rate_pct,
    ROUND(SUM(CASE WHEN o.order_status = 'Cancelled'
                   THEN oi.quantity * oi.unit_price - oi.discount_amount ELSE 0 END), 2)
                                                                       AS cancelled_value
FROM orders AS o
JOIN order_items AS oi ON oi.order_id = o.order_id
GROUP BY o.sales_channel
ORDER BY o.sales_channel;
