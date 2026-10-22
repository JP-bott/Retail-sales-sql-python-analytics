-- ============================================================================
-- 03 CUSTOMER BEHAVIOUR
-- Customers are the "left" side of every join so people who never bought (or
-- whose only orders were cancelled) are not silently dropped.
-- The status filter sits in the JOIN condition, not in WHERE: a WHERE filter
-- on the orders table would remove the customers with no completed orders.
-- ============================================================================


-- name: customer_counts
-- How many registered customers bought, bought once, or bought repeatedly?
-- Repeat customer = 2 or more completed orders.
WITH customer_orders AS (
    SELECT
        c.customer_id,
        COUNT(o.order_id) AS completed_orders
    FROM customers AS c
    LEFT JOIN orders AS o
           ON o.customer_id = c.customer_id
          AND o.order_status = 'Completed'
    GROUP BY c.customer_id
)
SELECT
    COUNT(*)                                                     AS registered_customers,
    SUM(CASE WHEN completed_orders >= 1 THEN 1 ELSE 0 END)       AS customers_with_purchases,
    SUM(CASE WHEN completed_orders = 0  THEN 1 ELSE 0 END)       AS customers_without_purchases,
    SUM(CASE WHEN completed_orders = 1  THEN 1 ELSE 0 END)       AS one_time_customers,
    SUM(CASE WHEN completed_orders >= 2 THEN 1 ELSE 0 END)       AS repeat_customers,
    ROUND(100.0 * SUM(CASE WHEN completed_orders >= 2 THEN 1 ELSE 0 END)
          / SUM(CASE WHEN completed_orders >= 1 THEN 1 ELSE 0 END), 1)
                                                                 AS repeat_rate_of_buyers_pct
FROM customer_orders;


-- name: customer_spending
-- One row per registered customer (including zero-spend customers): completed
-- orders, net revenue and first/last purchase dates. Used for averages,
-- distributions and the top-customer list.
SELECT
    c.customer_id,
    c.customer_name,
    c.region,
    c.registration_date,
    COUNT(DISTINCT o.order_id)                                         AS completed_orders,
    ROUND(COALESCE(SUM(oi.quantity * oi.unit_price - oi.discount_amount), 0), 2)
                                                                       AS net_revenue,
    MIN(o.order_date)                                                  AS first_order_date,
    MAX(o.order_date)                                                  AS last_order_date
FROM customers AS c
LEFT JOIN orders AS o
       ON o.customer_id = c.customer_id
      AND o.order_status = 'Completed'
LEFT JOIN order_items AS oi ON oi.order_id = o.order_id
GROUP BY c.customer_id, c.customer_name, c.region, c.registration_date
ORDER BY c.customer_id;


-- name: spending_summary
-- Average spending per customer, two ways: across ALL registered customers
-- (zero spenders included) and across buying customers only.
WITH customer_revenue AS (
    SELECT
        c.customer_id,
        COALESCE(SUM(oi.quantity * oi.unit_price - oi.discount_amount), 0) AS net_revenue
    FROM customers AS c
    LEFT JOIN orders AS o
           ON o.customer_id = c.customer_id
          AND o.order_status = 'Completed'
    LEFT JOIN order_items AS oi ON oi.order_id = o.order_id
    GROUP BY c.customer_id
)
SELECT
    COUNT(*)                                                           AS registered_customers,
    ROUND(SUM(net_revenue), 2)                                         AS total_revenue,
    ROUND(AVG(net_revenue), 2)                                         AS avg_revenue_per_registered_customer,
    ROUND(AVG(CASE WHEN net_revenue > 0 THEN net_revenue END), 2)      AS avg_revenue_per_buying_customer,
    ROUND(MAX(net_revenue), 2)                                         AS max_customer_revenue
FROM customer_revenue;


-- name: top_customers_by_spending
-- Who are the 10 highest-spending customers?
SELECT
    c.customer_id,
    c.customer_name,
    c.region,
    COUNT(DISTINCT o.order_id)                                         AS completed_orders,
    ROUND(SUM(oi.quantity * oi.unit_price - oi.discount_amount), 2)    AS net_revenue,
    ROUND(SUM(oi.quantity * oi.unit_price - oi.discount_amount)
          / COUNT(DISTINCT o.order_id), 2)                             AS avg_order_value
FROM customers AS c
JOIN orders      AS o  ON o.customer_id = c.customer_id
JOIN order_items AS oi ON oi.order_id   = o.order_id
WHERE o.order_status = 'Completed'
GROUP BY c.customer_id, c.customer_name, c.region
ORDER BY net_revenue DESC
LIMIT 10;


-- name: purchase_frequency_distribution
-- How many customers fall into each purchase-frequency band? The CASE
-- expression groups completed-order counts; sort_order keeps bands in sequence.
WITH customer_orders AS (
    SELECT
        c.customer_id,
        COUNT(o.order_id) AS completed_orders
    FROM customers AS c
    LEFT JOIN orders AS o
           ON o.customer_id = c.customer_id
          AND o.order_status = 'Completed'
    GROUP BY c.customer_id
)
SELECT
    CASE
        WHEN completed_orders = 0   THEN '0 orders'
        WHEN completed_orders = 1   THEN '1 order'
        WHEN completed_orders <= 5  THEN '2-5 orders'
        WHEN completed_orders <= 10 THEN '6-10 orders'
        WHEN completed_orders <= 20 THEN '11-20 orders'
        WHEN completed_orders <= 30 THEN '21-30 orders'
        ELSE '31+ orders'
    END AS frequency_band,
    CASE
        WHEN completed_orders = 0   THEN 1
        WHEN completed_orders = 1   THEN 2
        WHEN completed_orders <= 5  THEN 3
        WHEN completed_orders <= 10 THEN 4
        WHEN completed_orders <= 20 THEN 5
        WHEN completed_orders <= 30 THEN 6
        ELSE 7
    END AS sort_order,
    COUNT(*) AS customers
FROM customer_orders
GROUP BY frequency_band, sort_order
ORDER BY sort_order;


-- name: customers_without_purchases
-- Which registered customers have no completed purchase, and why? Either they
-- never placed an order, or every order they placed was cancelled.
SELECT
    c.customer_id,
    c.customer_name,
    c.region,
    c.registration_date,
    COUNT(o.order_id) AS total_orders_placed,
    CASE WHEN COUNT(o.order_id) = 0 THEN 'Never ordered'
         ELSE 'Only cancelled orders' END AS reason
FROM customers AS c
LEFT JOIN orders AS o ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.customer_name, c.region, c.registration_date
HAVING SUM(CASE WHEN o.order_status = 'Completed' THEN 1 ELSE 0 END) = 0 -- ELSE 0 matters: no orders would give NULL
ORDER BY c.registration_date;
