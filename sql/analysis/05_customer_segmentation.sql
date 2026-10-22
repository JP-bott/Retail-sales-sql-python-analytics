-- ============================================================================
-- 05 CUSTOMER SEGMENTATION (RFM)
--
-- Reference date: 2025-12-31 (the last day of the dataset). A fixed date is used
-- instead of the current system date, so results do not change depending on when the query runs.
--
--   Recency   (R) = days between the customer's last completed order and 2025-12-31
--   Frequency (F) = number of completed orders
--   Monetary  (M) = total net revenue from completed orders
--
-- F and M are scored 1-5 with NTILE(5) (5 = top 20% of buyers). NTILE splits
-- rows into equal-sized groups, so customers with identical values can land in
-- different groups; customer_id is used as a tie-breaker so results are repeatable.
--
-- Segment rules, applied in this order (first matching rule wins):
--   No Purchases : no completed orders (shown separately, no RFM values)
--   At-Risk      : recency_days > 120  (no completed purchase in the last ~4 months)
--   High-Value   : not At-Risk AND F score >= 4 AND M score >= 4
--   Regular      : not At-Risk AND F score >= 3
--   Occasional   : everyone else who bought and is not At-Risk
-- ============================================================================


-- name: rfm_customer_segments
-- One row per registered customer with R, F, M values, F/M scores and segment.
WITH customer_rfm AS (
    SELECT
        c.customer_id,
        c.customer_name,
        COUNT(DISTINCT o.order_id)                                     AS frequency,
        ROUND(SUM(oi.quantity * oi.unit_price - oi.discount_amount), 2) AS monetary,
        MAX(o.order_date)                                              AS last_order_date,
        CAST(JULIANDAY('2025-12-31') - JULIANDAY(MAX(o.order_date)) AS INTEGER)
                                                                       AS recency_days
    FROM customers AS c
    JOIN orders      AS o  ON o.customer_id = c.customer_id AND o.order_status = 'Completed'
    JOIN order_items AS oi ON oi.order_id   = o.order_id
    GROUP BY c.customer_id, c.customer_name
),
scored AS (
    SELECT
        *,
        NTILE(5) OVER (ORDER BY frequency ASC, customer_id) AS f_score,
        NTILE(5) OVER (ORDER BY monetary  ASC, customer_id) AS m_score
    FROM customer_rfm
)
SELECT
    c.customer_id,
    c.customer_name,
    s.recency_days,
    s.frequency,
    s.monetary,
    s.f_score,
    s.m_score,
    CASE
        WHEN s.customer_id IS NULL          THEN 'No Purchases'
        WHEN s.recency_days > 120           THEN 'At-Risk'
        WHEN s.f_score >= 4 AND s.m_score >= 4 THEN 'High-Value'
        WHEN s.f_score >= 3                 THEN 'Regular'
        ELSE 'Occasional'
    END AS segment
FROM customers AS c
LEFT JOIN scored AS s ON s.customer_id = c.customer_id
ORDER BY c.customer_id;


-- name: rfm_segment_summary
-- Customers, revenue and average RFM values per segment. Same logic as the
-- query above, aggregated by segment.
WITH customer_rfm AS (
    SELECT
        c.customer_id,
        COUNT(DISTINCT o.order_id)                                     AS frequency,
        SUM(oi.quantity * oi.unit_price - oi.discount_amount)          AS monetary,
        CAST(JULIANDAY('2025-12-31') - JULIANDAY(MAX(o.order_date)) AS INTEGER)
                                                                       AS recency_days
    FROM customers AS c
    JOIN orders      AS o  ON o.customer_id = c.customer_id AND o.order_status = 'Completed'
    JOIN order_items AS oi ON oi.order_id   = o.order_id
    GROUP BY c.customer_id
),
scored AS (
    SELECT
        *,
        NTILE(5) OVER (ORDER BY frequency ASC, customer_id) AS f_score,
        NTILE(5) OVER (ORDER BY monetary  ASC, customer_id) AS m_score
    FROM customer_rfm
),
segmented AS (
    SELECT
        c.customer_id,
        s.recency_days,
        s.frequency,
        s.monetary,
        CASE
            WHEN s.customer_id IS NULL          THEN 'No Purchases'
            WHEN s.recency_days > 120           THEN 'At-Risk'
            WHEN s.f_score >= 4 AND s.m_score >= 4 THEN 'High-Value'
            WHEN s.f_score >= 3                 THEN 'Regular'
            ELSE 'Occasional'
        END AS segment
    FROM customers AS c
    LEFT JOIN scored AS s ON s.customer_id = c.customer_id
)
SELECT
    segment,
    COUNT(*)                                                           AS customers,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)                 AS customer_share_pct,
    ROUND(COALESCE(SUM(monetary), 0), 2)                               AS total_revenue,
    ROUND(100.0 * COALESCE(SUM(monetary), 0)
          / SUM(SUM(monetary)) OVER (), 1)                             AS revenue_share_pct,
    ROUND(AVG(frequency), 1)                                           AS avg_orders,
    ROUND(AVG(monetary), 2)                                            AS avg_revenue_per_customer,
    ROUND(AVG(recency_days), 0)                                        AS avg_recency_days
FROM segmented
GROUP BY segment
ORDER BY CASE segment
             WHEN 'High-Value'   THEN 1
             WHEN 'Regular'      THEN 2
             WHEN 'Occasional'   THEN 3
             WHEN 'At-Risk'      THEN 4
             ELSE 5
         END;
