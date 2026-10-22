-- ============================================================================
-- 06 ADVANCED QUERIES
-- Each query answers a specific business question and uses a technique that
-- fits it. Completed orders only, line revenue = quantity * unit_price - discount_amount.
-- ============================================================================


-- name: best_product_per_category
-- Business question: what is the single best-selling product in each category?
-- Techniques: CTE, multi-table JOIN, ROW_NUMBER() per category.
WITH product_revenue AS (
    SELECT
        cat.category_name,
        p.product_name,
        SUM(oi.quantity * oi.unit_price - oi.discount_amount)          AS net_revenue
    FROM order_items AS oi
    JOIN orders      AS o   ON o.order_id      = oi.order_id
    JOIN products    AS p   ON p.product_id    = oi.product_id
    JOIN categories  AS cat ON cat.category_id = p.category_id
    WHERE o.order_status = 'Completed'
    GROUP BY cat.category_name, p.product_name
),
ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY category_name ORDER BY net_revenue DESC) AS rank_in_category,
        SUM(net_revenue) OVER (PARTITION BY category_name)                       AS category_revenue
    FROM product_revenue
)
SELECT
    category_name,
    product_name                                                       AS best_product,
    ROUND(net_revenue, 2)                                              AS product_revenue,
    ROUND(100.0 * net_revenue / category_revenue, 1)                   AS share_of_category_pct
FROM ranked
WHERE rank_in_category = 1
ORDER BY product_revenue DESC;


-- name: top_categories_by_region
-- Business question: which three categories lead revenue in each region, and do
-- regions differ? Techniques: CTE, multi-table JOIN, RANK() partitioned by region.
WITH region_category_revenue AS (
    SELECT
        cu.region,
        cat.category_name,
        SUM(oi.quantity * oi.unit_price - oi.discount_amount)          AS net_revenue
    FROM order_items AS oi
    JOIN orders      AS o   ON o.order_id      = oi.order_id
    JOIN customers   AS cu  ON cu.customer_id  = o.customer_id
    JOIN products    AS p   ON p.product_id    = oi.product_id
    JOIN categories  AS cat ON cat.category_id = p.category_id
    WHERE o.order_status = 'Completed'
    GROUP BY cu.region, cat.category_name
),
ranked AS (
    SELECT
        *,
        RANK() OVER (PARTITION BY region ORDER BY net_revenue DESC)    AS category_rank
    FROM region_category_revenue
)
SELECT
    region,
    category_rank,
    category_name,
    ROUND(net_revenue, 2)                                              AS net_revenue
FROM ranked
WHERE category_rank <= 3
ORDER BY region, category_rank;


-- name: channel_mix_by_category
-- Business question: which categories lean online and which lean in-store?
-- Techniques: conditional aggregation (SUM + CASE) to pivot channels into columns.
SELECT
    cat.category_name,
    ROUND(SUM(CASE WHEN o.sales_channel = 'Online'
                   THEN oi.quantity * oi.unit_price - oi.discount_amount ELSE 0 END), 2)
                                                                       AS online_revenue,
    ROUND(SUM(CASE WHEN o.sales_channel = 'In-Store'
                   THEN oi.quantity * oi.unit_price - oi.discount_amount ELSE 0 END), 2)
                                                                       AS in_store_revenue,
    ROUND(100.0 * SUM(CASE WHEN o.sales_channel = 'Online'
                           THEN oi.quantity * oi.unit_price - oi.discount_amount ELSE 0 END)
          / SUM(oi.quantity * oi.unit_price - oi.discount_amount), 1)  AS online_share_pct
FROM order_items AS oi
JOIN orders      AS o   ON o.order_id      = oi.order_id
JOIN products    AS p   ON p.product_id    = oi.product_id
JOIN categories  AS cat ON cat.category_id = p.category_id
WHERE o.order_status = 'Completed'
GROUP BY cat.category_name
ORDER BY online_share_pct DESC;


-- name: category_growth_2025_vs_2024
-- Business question: which categories grew or shrank from 2024 to 2025?
-- Techniques: conditional aggregation by year, CASE for the growth label.
WITH yearly AS (
    SELECT
        cat.category_name,
        SUM(CASE WHEN STRFTIME('%Y', o.order_date) = '2024'
                 THEN oi.quantity * oi.unit_price - oi.discount_amount ELSE 0 END) AS revenue_2024,
        SUM(CASE WHEN STRFTIME('%Y', o.order_date) = '2025'
                 THEN oi.quantity * oi.unit_price - oi.discount_amount ELSE 0 END) AS revenue_2025
    FROM order_items AS oi
    JOIN orders      AS o   ON o.order_id      = oi.order_id
    JOIN products    AS p   ON p.product_id    = oi.product_id
    JOIN categories  AS cat ON cat.category_id = p.category_id
    WHERE o.order_status = 'Completed'
    GROUP BY cat.category_name
)
SELECT
    category_name,
    ROUND(revenue_2024, 2)                                             AS revenue_2024,
    ROUND(revenue_2025, 2)                                             AS revenue_2025,
    ROUND(100.0 * (revenue_2025 - revenue_2024) / revenue_2024, 1)     AS growth_pct,
    CASE
        WHEN revenue_2025 >= revenue_2024 * 1.10 THEN 'Growing (10%+)'
        WHEN revenue_2025 >= revenue_2024        THEN 'Stable / slight growth'
        ELSE 'Declining'
    END                                                                AS trend_label
FROM yearly
ORDER BY growth_pct DESC;


-- name: repurchase_interval
-- Business question: how many days pass between a customer's orders?
-- Techniques: LAG() partitioned by customer to find each customer's previous
-- order date, then average the gaps. Useful for timing reminder campaigns.
WITH customer_orders AS (
    SELECT
        customer_id,
        order_date,
        LAG(order_date) OVER (PARTITION BY customer_id ORDER BY order_date, order_id)
                                                                       AS previous_order_date
    FROM orders
    WHERE order_status = 'Completed'
),
gaps AS (
    SELECT
        customer_id,
        JULIANDAY(order_date) - JULIANDAY(previous_order_date)         AS days_since_previous_order
    FROM customer_orders
    WHERE previous_order_date IS NOT NULL
)
SELECT
    COUNT(DISTINCT customer_id)                                        AS customers_with_repeat_orders,
    COUNT(*)                                                           AS order_gaps_measured,
    ROUND(AVG(days_since_previous_order), 1)                           AS avg_days_between_orders,
    MIN(days_since_previous_order)                                     AS min_days,
    MAX(days_since_previous_order)                                     AS max_days
FROM gaps;


-- name: first_channel_and_retention
-- Business question: do customers whose first order was online come back more
-- often than customers whose first order was in-store?
-- Techniques: ROW_NUMBER() to pick each customer's first completed order, CTEs,
-- CASE inside a conditional aggregate, JOIN back to the order counts.
WITH numbered_orders AS (
    SELECT
        customer_id,
        sales_channel,
        ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date, order_id) AS order_number
    FROM orders
    WHERE order_status = 'Completed'
),
first_orders AS (
    SELECT customer_id, sales_channel AS first_channel
    FROM numbered_orders
    WHERE order_number = 1
),
order_counts AS (
    SELECT customer_id, COUNT(*) AS completed_orders
    FROM orders
    WHERE order_status = 'Completed'
    GROUP BY customer_id
)
SELECT
    f.first_channel,
    COUNT(*)                                                           AS customers,
    SUM(CASE WHEN oc.completed_orders >= 2 THEN 1 ELSE 0 END)          AS repeat_customers,
    ROUND(100.0 * SUM(CASE WHEN oc.completed_orders >= 2 THEN 1 ELSE 0 END) / COUNT(*), 1)
                                                                       AS repeat_rate_pct,
    ROUND(AVG(oc.completed_orders), 1)                                 AS avg_orders_per_customer
FROM first_orders AS f
JOIN order_counts AS oc ON oc.customer_id = f.customer_id
GROUP BY f.first_channel
ORDER BY f.first_channel;


-- name: discount_impact_on_margin
-- Business question: do discounted order lines earn a lower gross margin than
-- full-price lines, and how common are discounts?
-- Techniques: CASE to label lines, multi-table JOIN, aggregate comparison.
SELECT
    CASE WHEN oi.discount_amount > 0 THEN 'Discounted' ELSE 'Full price' END AS line_type,
    COUNT(*)                                                           AS order_lines,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)                 AS share_of_lines_pct,
    ROUND(SUM(oi.quantity * oi.unit_price - oi.discount_amount), 2)    AS net_revenue,
    ROUND(SUM(oi.quantity * oi.unit_price - oi.discount_amount
              - oi.quantity * p.unit_cost), 2)                         AS gross_profit,
    ROUND(100.0 * SUM(oi.quantity * oi.unit_price - oi.discount_amount
                      - oi.quantity * p.unit_cost)
          / SUM(oi.quantity * oi.unit_price - oi.discount_amount), 1)  AS gross_margin_pct
FROM order_items AS oi
JOIN orders   AS o ON o.order_id   = oi.order_id
JOIN products AS p ON p.product_id = oi.product_id
WHERE o.order_status = 'Completed'
GROUP BY line_type
ORDER BY line_type;


-- name: underperforming_products_vs_category
-- Business question: which products earn less than half of the average product
-- in their own category? (A fairer yardstick than comparing across categories.)
-- Techniques: CTE and a correlated subquery for the category average.
WITH product_revenue AS (
    SELECT
        p.product_id,
        p.product_name,
        p.category_id,
        COALESCE(SUM(CASE WHEN o.order_status = 'Completed'
                          THEN oi.quantity * oi.unit_price - oi.discount_amount END), 0) AS net_revenue
    FROM products AS p
    LEFT JOIN order_items AS oi ON oi.product_id = p.product_id
    LEFT JOIN orders      AS o  ON o.order_id    = oi.order_id
    GROUP BY p.product_id, p.product_name, p.category_id
)
SELECT
    cat.category_name,
    pr.product_name,
    ROUND(pr.net_revenue, 2)                                           AS net_revenue,
    ROUND((SELECT AVG(pr2.net_revenue)
           FROM product_revenue AS pr2
           WHERE pr2.category_id = pr.category_id), 2)                 AS category_avg_product_revenue
FROM product_revenue AS pr
JOIN categories AS cat ON cat.category_id = pr.category_id
WHERE pr.net_revenue < 0.5 * (SELECT AVG(pr2.net_revenue)
                              FROM product_revenue AS pr2
                              WHERE pr2.category_id = pr.category_id)
ORDER BY cat.category_name, pr.net_revenue;


-- name: customers_above_twice_average
-- Business question: which buying customers spend more than twice the average
-- buying customer? Techniques: CTE plus a scalar subquery in the WHERE clause.
WITH customer_revenue AS (
    SELECT
        o.customer_id,
        SUM(oi.quantity * oi.unit_price - oi.discount_amount)          AS net_revenue
    FROM orders AS o
    JOIN order_items AS oi ON oi.order_id = o.order_id
    WHERE o.order_status = 'Completed'
    GROUP BY o.customer_id
)
SELECT
    cu.customer_id,
    cu.customer_name,
    cu.region,
    ROUND(cr.net_revenue, 2)                                           AS net_revenue,
    ROUND(cr.net_revenue / (SELECT AVG(net_revenue) FROM customer_revenue), 1)
                                                                       AS times_average_buyer
FROM customer_revenue AS cr
JOIN customers AS cu ON cu.customer_id = cr.customer_id
WHERE cr.net_revenue > 2 * (SELECT AVG(net_revenue) FROM customer_revenue)
ORDER BY cr.net_revenue DESC;
