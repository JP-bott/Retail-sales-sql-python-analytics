-- ============================================================================
-- 02 PRODUCT PERFORMANCE
--   line revenue      = quantity * unit_price - discount_amount
--   line gross profit = line revenue - (quantity * unit_cost)
--
-- GROSS profit is NOT net profit. It only subtracts the product cost. The
-- dataset has no rent, payroll, shipping, marketing or other operating
-- expenses, so true net profit cannot be calculated here.
-- Only completed orders are counted.
-- ============================================================================


-- name: top_products_by_revenue
-- Which 10 products bring in the most net revenue?
SELECT
    p.product_id,
    p.product_name,
    cat.category_name,
    SUM(oi.quantity)                                                   AS units_sold,
    ROUND(SUM(oi.quantity * oi.unit_price - oi.discount_amount), 2)    AS net_revenue,
    ROUND(SUM(oi.quantity * oi.unit_price - oi.discount_amount
              - oi.quantity * p.unit_cost), 2)                         AS gross_profit
FROM order_items AS oi
JOIN orders      AS o   ON o.order_id    = oi.order_id
JOIN products    AS p   ON p.product_id  = oi.product_id
JOIN categories  AS cat ON cat.category_id = p.category_id
WHERE o.order_status = 'Completed'
GROUP BY p.product_id, p.product_name, cat.category_name
ORDER BY net_revenue DESC
LIMIT 10;


-- name: top_products_by_units
-- Which 10 products sell the most units? (High volume is not always high revenue.)
SELECT
    p.product_id,
    p.product_name,
    cat.category_name,
    SUM(oi.quantity)                                                   AS units_sold,
    ROUND(SUM(oi.quantity * oi.unit_price - oi.discount_amount), 2)    AS net_revenue
FROM order_items AS oi
JOIN orders      AS o   ON o.order_id    = oi.order_id
JOIN products    AS p   ON p.product_id  = oi.product_id
JOIN categories  AS cat ON cat.category_id = p.category_id
WHERE o.order_status = 'Completed'
GROUP BY p.product_id, p.product_name, cat.category_name
ORDER BY units_sold DESC, net_revenue DESC
LIMIT 10;


-- name: revenue_by_category
-- Revenue, units and share of total revenue for each product category.
SELECT
    cat.category_name,
    COUNT(DISTINCT p.product_id)                                       AS products_sold,
    SUM(oi.quantity)                                                   AS units_sold,
    ROUND(SUM(oi.quantity * oi.unit_price - oi.discount_amount), 2)    AS net_revenue,
    ROUND(100.0 * SUM(oi.quantity * oi.unit_price - oi.discount_amount)
          / SUM(SUM(oi.quantity * oi.unit_price - oi.discount_amount)) OVER (), 1)
                                                                       AS revenue_share_pct
FROM order_items AS oi
JOIN orders      AS o   ON o.order_id    = oi.order_id
JOIN products    AS p   ON p.product_id  = oi.product_id
JOIN categories  AS cat ON cat.category_id = p.category_id
WHERE o.order_status = 'Completed'
GROUP BY cat.category_name
ORDER BY net_revenue DESC;


-- name: gross_profit_by_product
-- Gross profit and gross margin for every product that has completed sales.
SELECT
    p.product_id,
    p.product_name,
    cat.category_name,
    SUM(oi.quantity)                                                   AS units_sold,
    ROUND(SUM(oi.quantity * oi.unit_price - oi.discount_amount), 2)    AS net_revenue,
    ROUND(SUM(oi.quantity * p.unit_cost), 2)                           AS cost_of_goods,
    ROUND(SUM(oi.quantity * oi.unit_price - oi.discount_amount
              - oi.quantity * p.unit_cost), 2)                         AS gross_profit,
    ROUND(100.0 * SUM(oi.quantity * oi.unit_price - oi.discount_amount
                      - oi.quantity * p.unit_cost)
          / SUM(oi.quantity * oi.unit_price - oi.discount_amount), 1)  AS gross_margin_pct
FROM order_items AS oi
JOIN orders      AS o   ON o.order_id    = oi.order_id
JOIN products    AS p   ON p.product_id  = oi.product_id
JOIN categories  AS cat ON cat.category_id = p.category_id
WHERE o.order_status = 'Completed'
GROUP BY p.product_id, p.product_name, cat.category_name
ORDER BY gross_profit DESC;


-- name: margin_by_category
-- Gross margin by category = gross profit / net revenue. The discount rate shows
-- how much of the list-price sales value was given away as discounts.
SELECT
    cat.category_name,
    ROUND(SUM(oi.quantity * oi.unit_price - oi.discount_amount), 2)    AS net_revenue,
    ROUND(SUM(oi.quantity * oi.unit_price - oi.discount_amount
              - oi.quantity * p.unit_cost), 2)                         AS gross_profit,
    ROUND(100.0 * SUM(oi.quantity * oi.unit_price - oi.discount_amount
                      - oi.quantity * p.unit_cost)
          / SUM(oi.quantity * oi.unit_price - oi.discount_amount), 1)  AS gross_margin_pct,
    ROUND(100.0 * SUM(oi.discount_amount)
          / SUM(oi.quantity * oi.unit_price), 1)                       AS discount_rate_pct
FROM order_items AS oi
JOIN orders      AS o   ON o.order_id    = oi.order_id
JOIN products    AS p   ON p.product_id  = oi.product_id
JOIN categories  AS cat ON cat.category_id = p.category_id
WHERE o.order_status = 'Completed'
GROUP BY cat.category_name
ORDER BY gross_margin_pct DESC;


-- name: low_activity_products
-- Which 10 products sold the fewest units? The CTE keeps only completed order
-- lines first, then LEFT JOIN keeps products with no completed sales at all.
WITH completed_lines AS (
    SELECT oi.product_id, oi.quantity, oi.unit_price, oi.discount_amount
    FROM order_items AS oi
    JOIN orders AS o ON o.order_id = oi.order_id
    WHERE o.order_status = 'Completed'
)
SELECT
    p.product_id,
    p.product_name,
    cat.category_name,
    COALESCE(SUM(cl.quantity), 0)                                      AS units_sold,
    ROUND(COALESCE(SUM(cl.quantity * cl.unit_price - cl.discount_amount), 0), 2)
                                                                       AS net_revenue
FROM products AS p
JOIN categories AS cat ON cat.category_id = p.category_id
LEFT JOIN completed_lines AS cl ON cl.product_id = p.product_id
GROUP BY p.product_id, p.product_name, cat.category_name
ORDER BY units_sold ASC, net_revenue ASC
LIMIT 10;
