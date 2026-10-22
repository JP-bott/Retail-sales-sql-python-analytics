-- ============================================================================
-- 04 MONTHLY GROWTH
-- LAG(value, n) returns the value from the row n positions earlier in the
-- ordering. Ordered by month, LAG(revenue) gives the previous month's revenue,
-- so growth = (this month - previous month) / previous month.
--
-- A recursive calendar CTE lists every month in the reporting period, so a
-- month with no sales would still appear (with 0 revenue) and LAG would still
-- compare against the true previous calendar month.
-- ============================================================================


-- name: monthly_growth
-- Monthly revenue, previous-month revenue, month-over-month (MoM) growth,
-- same-month-last-year growth (YoY), order count and average order value.
-- MoM is NULL for the first month (no prior period) and NULL if the previous
-- month's revenue is zero (growth from zero is undefined).
WITH RECURSIVE calendar AS (
    SELECT DATE('2024-01-01') AS month_start
    UNION ALL
    SELECT DATE(month_start, '+1 month')
    FROM calendar
    WHERE month_start < DATE('2025-12-01')
),
monthly_sales AS (
    SELECT
        STRFTIME('%Y-%m', o.order_date)                                AS order_month,
        COUNT(DISTINCT o.order_id)                                     AS completed_orders,
        SUM(oi.quantity * oi.unit_price - oi.discount_amount)          AS net_revenue
    FROM orders AS o
    JOIN order_items AS oi ON oi.order_id = o.order_id
    WHERE o.order_status = 'Completed'
    GROUP BY STRFTIME('%Y-%m', o.order_date)
),
monthly AS (
    SELECT
        STRFTIME('%Y-%m', cal.month_start)                             AS order_month,
        COALESCE(ms.completed_orders, 0)                               AS completed_orders,
        COALESCE(ms.net_revenue, 0)                                    AS net_revenue
    FROM calendar AS cal
    LEFT JOIN monthly_sales AS ms
           ON ms.order_month = STRFTIME('%Y-%m', cal.month_start)
),
with_previous AS (
    SELECT
        order_month,
        completed_orders,
        net_revenue,
        LAG(net_revenue, 1)  OVER (ORDER BY order_month)               AS previous_month_revenue,
        LAG(net_revenue, 12) OVER (ORDER BY order_month)               AS same_month_last_year_revenue
    FROM monthly
)
SELECT
    order_month,
    completed_orders,
    ROUND(net_revenue, 2)                                              AS net_revenue,
    ROUND(previous_month_revenue, 2)                                   AS previous_month_revenue,
    CASE
        WHEN previous_month_revenue IS NULL OR previous_month_revenue = 0 THEN NULL
        ELSE ROUND(100.0 * (net_revenue - previous_month_revenue) / previous_month_revenue, 2)
    END                                                                AS mom_growth_pct,
    CASE
        WHEN same_month_last_year_revenue IS NULL OR same_month_last_year_revenue = 0 THEN NULL
        ELSE ROUND(100.0 * (net_revenue - same_month_last_year_revenue) / same_month_last_year_revenue, 2)
    END                                                                AS yoy_growth_pct,
    CASE
        WHEN completed_orders = 0 THEN NULL
        ELSE ROUND(net_revenue / completed_orders, 2)
    END                                                                AS avg_order_value
FROM with_previous
ORDER BY order_month;
