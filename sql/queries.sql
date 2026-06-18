-- =========================================================
-- EDC POC  —  Operational & Analytical Queries
-- Database : edtransmap
-- =========================================================
-- HOW TO USE
--   In psql, set the date window once:
--       \set date_from '2026-03-12'
--       \set date_to   '2026-06-12'
--   then reference as  :date_from  and  :date_to  in any query.
--
-- ID / CODE MASKING POLICY
--   Raw internal IDs (transaction_id, merchant_id, terminal_id …)
--   are never selected.  trace_number is the only external
--   transaction reference.  merchant_code and terminal_code are
--   partially masked: first 3 chars + repeating * + last 2 chars.
--     MCH-5814-20250301-00001  →  MCH******************01
--     TID-5814-20250301-00001  →  TID******************01
-- =========================================================


-- =========================================================
-- 1. RAW TRANSACTIONS  (date-range filter, newest first)
-- =========================================================
SELECT
    t.trace_number,
    t.transaction_time::timestamptz                        AS txn_time,
    m.merchant_name,
    m.mcc_code,
    LEFT(te.terminal_code, 3) || REPEAT('*', LENGTH(te.terminal_code) - 5) || RIGHT(te.terminal_code, 2) AS terminal_code,
    t.payment_channel,
    t.transaction_type,
    qi.issuer_name                                         AS qris_issuer,
    c.card_brand,
    c.card_number_masked,
    t.amount,
    t.response_code,
    t.response_message,
    t.transaction_status,
    t.settled_flag,
    t.batch_number
FROM transactions t
JOIN merchants  m  ON m.merchant_id  = t.merchant_id
JOIN terminals  te ON te.terminal_id = t.terminal_id
LEFT JOIN qris_issuers qi ON qi.qris_issuer_id = t.qris_issuer_id
LEFT JOIN cards        c  ON c.card_id          = t.card_id
WHERE t.transaction_time >= :date_from::date
  AND t.transaction_time <  :date_to::date + interval '1 day'
ORDER BY t.transaction_time DESC
LIMIT 200;


-- =========================================================
-- 2. OVERALL TOTALS  (single-row summary)
-- =========================================================
SELECT
    COUNT(*)                                               AS total_transactions,
    COUNT(*) FILTER (WHERE transaction_status = 'APPROVED')  AS approved,
    COUNT(*) FILTER (WHERE transaction_status = 'DECLINED')  AS declined,
    COUNT(*) FILTER (WHERE transaction_status = 'VOIDED')    AS voided,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE transaction_status = 'APPROVED')
              / NULLIF(COUNT(*), 0), 2
    )                                                      AS approval_rate_pct,
    SUM(amount) FILTER (WHERE transaction_status = 'APPROVED'
                          AND transaction_type   = 'SALE')   AS gross_sales,
    SUM(amount) FILTER (WHERE transaction_status = 'APPROVED'
                          AND transaction_type   = 'REFUND') AS total_refunds,
    SUM(amount) FILTER (WHERE transaction_status = 'APPROVED'
                          AND transaction_type   = 'SALE')
    - COALESCE(SUM(amount) FILTER (WHERE transaction_status = 'APPROVED'
                                     AND transaction_type   = 'REFUND'), 0)
                                                           AS net_revenue
FROM transactions
WHERE transaction_time >= :date_from::date
  AND transaction_time <  :date_to::date + interval '1 day';


-- =========================================================
-- 3. DAILY TRANSACTION TREND
-- =========================================================
SELECT
    transaction_time::date                                 AS txn_date,
    COUNT(*)                                               AS total_trx,
    COUNT(*) FILTER (WHERE transaction_status = 'APPROVED')  AS approved,
    COUNT(*) FILTER (WHERE transaction_status = 'DECLINED')  AS declined,
    SUM(amount) FILTER (WHERE transaction_status = 'APPROVED'
                          AND transaction_type   = 'SALE')   AS daily_sales,
    COUNT(*) FILTER (WHERE payment_channel = 'QRIS')       AS qris_trx,
    COUNT(*) FILTER (WHERE payment_channel = 'EDC_CARD')   AS card_trx
FROM transactions
WHERE transaction_time >= :date_from::date
  AND transaction_time <  :date_to::date + interval '1 day'
GROUP BY 1
ORDER BY 1;


-- =========================================================
-- 4. PAYMENT CHANNEL SPLIT  (QRIS vs EDC_CARD)
-- =========================================================
SELECT
    payment_channel,
    COUNT(*)                                               AS trx_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)    AS share_pct,
    SUM(amount) FILTER (WHERE transaction_status = 'APPROVED') AS total_amount
FROM transactions
WHERE transaction_time >= :date_from::date
  AND transaction_time <  :date_to::date + interval '1 day'
GROUP BY 1
ORDER BY 2 DESC;


-- =========================================================
-- 5. QRIS ISSUER BREAKDOWN  (approved only)
-- =========================================================
SELECT
    qi.issuer_name,
    qi.issuer_type,
    COUNT(*)                                               AS trx_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)    AS share_pct,
    SUM(t.amount)                                          AS total_amount,
    ROUND(AVG(t.amount), 0)                                AS avg_amount
FROM transactions t
JOIN qris_issuers qi ON qi.qris_issuer_id = t.qris_issuer_id
WHERE t.transaction_status = 'APPROVED'
  AND t.transaction_time  >= :date_from::date
  AND t.transaction_time  <  :date_to::date + interval '1 day'
GROUP BY qi.issuer_name, qi.issuer_type
ORDER BY trx_count DESC;


-- =========================================================
-- 6. CARD BRAND BREAKDOWN  (approved EDC_CARD only)
-- =========================================================
SELECT
    c.card_brand,
    c.card_type,
    COUNT(*)                                               AS trx_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)    AS share_pct,
    SUM(t.amount)                                          AS total_amount
FROM transactions t
JOIN cards c ON c.card_id = t.card_id
WHERE t.transaction_status = 'APPROVED'
  AND t.payment_channel    = 'EDC_CARD'
  AND t.transaction_time  >= :date_from::date
  AND t.transaction_time  <  :date_to::date + interval '1 day'
GROUP BY c.card_brand, c.card_type
ORDER BY trx_count DESC;


-- =========================================================
-- 7. TOP MERCHANTS BY TRANSACTION VOLUME
-- =========================================================
SELECT
    m.merchant_name,
    m.mcc_code,
    LEFT(m.merchant_code, 3) || REPEAT('*', LENGTH(m.merchant_code) - 5) || RIGHT(m.merchant_code, 2) AS merchant_code,
    COUNT(*)                                               AS total_trx,
    COUNT(*) FILTER (WHERE t.transaction_status = 'APPROVED') AS approved_trx,
    SUM(t.amount) FILTER (WHERE t.transaction_status = 'APPROVED'
                            AND t.transaction_type    = 'SALE') AS gross_sales,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE t.transaction_status = 'APPROVED')
              / NULLIF(COUNT(*), 0), 2
    )                                                      AS approval_rate_pct
FROM transactions t
JOIN merchants m ON m.merchant_id = t.merchant_id
WHERE t.transaction_time >= :date_from::date
  AND t.transaction_time <  :date_to::date + interval '1 day'
GROUP BY m.merchant_name, m.mcc_code, m.merchant_code
ORDER BY total_trx DESC
LIMIT 20;


-- =========================================================
-- 8. CATEGORY / MCC BREAKDOWN
-- =========================================================
SELECT
    m.mcc_code,
    COUNT(DISTINCT m.merchant_id)                          AS merchant_count,
    COUNT(*)                                               AS total_trx,
    COUNT(*) FILTER (WHERE t.transaction_status = 'APPROVED') AS approved_trx,
    SUM(t.amount) FILTER (WHERE t.transaction_status = 'APPROVED'
                            AND t.transaction_type    = 'SALE') AS gross_sales,
    ROUND(AVG(t.amount) FILTER (WHERE t.transaction_status = 'APPROVED'), 0) AS avg_ticket,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE t.payment_channel = 'QRIS')
              / NULLIF(COUNT(*), 0), 1
    )                                                      AS qris_share_pct
FROM transactions t
JOIN merchants m ON m.merchant_id = t.merchant_id
WHERE t.transaction_time >= :date_from::date
  AND t.transaction_time <  :date_to::date + interval '1 day'
GROUP BY m.mcc_code
ORDER BY total_trx DESC;


-- =========================================================
-- 9. DECLINE ANALYSIS  (breakdown by response code)
-- =========================================================
SELECT
    response_code,
    response_message,
    COUNT(*)                                               AS decline_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)    AS share_pct
FROM transactions
WHERE transaction_status  = 'DECLINED'
  AND transaction_time   >= :date_from::date
  AND transaction_time   <  :date_to::date + interval '1 day'
GROUP BY response_code, response_message
ORDER BY decline_count DESC;


-- =========================================================
-- 10. TERMINAL APPROVAL RATES
-- =========================================================
SELECT
    LEFT(te.terminal_code, 3) || REPEAT('*', LENGTH(te.terminal_code) - 5) || RIGHT(te.terminal_code, 2) AS terminal_code,
    m.merchant_name,
    COUNT(*)                                               AS total_trx,
    COUNT(*) FILTER (WHERE t.transaction_status = 'APPROVED') AS approved,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE t.transaction_status = 'APPROVED')
              / NULLIF(COUNT(*), 0), 2
    )                                                      AS approval_rate_pct,
    SUM(t.amount) FILTER (WHERE t.transaction_status = 'APPROVED') AS approved_amount
FROM transactions t
JOIN terminals te ON te.terminal_id = t.terminal_id
JOIN merchants  m ON m.merchant_id  = t.merchant_id
WHERE t.transaction_time >= :date_from::date
  AND t.transaction_time <  :date_to::date + interval '1 day'
GROUP BY te.terminal_code, m.merchant_name
ORDER BY total_trx DESC;


-- =========================================================
-- 11. GEOGRAPHIC SUMMARY  (province → city → district)
-- =========================================================
SELECT
    COALESCE(prov.area_name, '(unknown)')                  AS province,
    COALESCE(city.area_name, '(unknown)')                  AS city,
    COALESCE(dist.area_name, '(unknown)')                  AS district,
    COUNT(DISTINCT m.merchant_id)                          AS merchant_count,
    COUNT(*)                                               AS total_trx,
    SUM(t.amount) FILTER (WHERE t.transaction_status = 'APPROVED') AS approved_amount
FROM transactions t
JOIN merchants m ON m.merchant_id = t.merchant_id
LEFT JOIN admin_areas dist ON dist.area_id = m.admin_area_id
LEFT JOIN admin_areas city ON city.area_id = dist.parent_id
LEFT JOIN admin_areas prov ON prov.area_id = city.parent_id
WHERE t.transaction_time >= :date_from::date
  AND t.transaction_time <  :date_to::date + interval '1 day'
GROUP BY 1, 2, 3
ORDER BY total_trx DESC;


-- =========================================================
-- 12. SETTLEMENT STATUS SUMMARY
-- =========================================================
SELECT
    s.settlement_date,
    COUNT(*)                                               AS batch_count,
    SUM(s.total_sales_count)                               AS total_sales_trx,
    SUM(s.total_sales_amount)                              AS total_sales_amount,
    SUM(s.total_refund_count)                              AS total_refund_trx,
    SUM(s.total_refund_amount)                             AS total_refund_amount,
    SUM(s.net_amount)                                      AS net_settled,
    COUNT(*) FILTER (WHERE s.status = 'PENDING')           AS pending_batches,
    COUNT(*) FILTER (WHERE s.status = 'SETTLED')           AS settled_batches,
    COUNT(*) FILTER (WHERE s.status = 'FAILED')            AS failed_batches
FROM settlement s
WHERE s.settlement_date >= :date_from::date
  AND s.settlement_date <= :date_to::date
GROUP BY s.settlement_date
ORDER BY s.settlement_date;


-- =========================================================
-- 13. UNSETTLED APPROVED TRANSACTIONS
-- =========================================================
SELECT
    t.trace_number,
    m.merchant_name,
    LEFT(te.terminal_code, 3) || REPEAT('*', LENGTH(te.terminal_code) - 5) || RIGHT(te.terminal_code, 2) AS terminal_code,
    t.payment_channel,
    t.transaction_type,
    t.amount,
    t.transaction_time
FROM transactions t
JOIN merchants m  ON m.merchant_id  = t.merchant_id
JOIN terminals te ON te.terminal_id = t.terminal_id
WHERE t.transaction_status = 'APPROVED'
  AND t.settled_flag        = FALSE
  AND t.transaction_time   >= :date_from::date
  AND t.transaction_time   <  :date_to::date + interval '1 day'
ORDER BY t.transaction_time
LIMIT 500;


-- =========================================================
-- 14. HOLIDAY EFFECT  (approved sales on holiday vs normal days)
-- =========================================================
WITH holiday_dates AS (
    SELECT txn_date, is_holiday FROM (VALUES
        (date '2026-01-01', true),(date '2026-01-17', true),
        (date '2026-02-17', true),(date '2026-03-19', true),
        (date '2026-03-20', true),(date '2026-03-21', true),
        (date '2026-03-23', true),(date '2026-03-24', true),
        (date '2026-04-03', true),(date '2026-05-01', true),
        (date '2026-05-02', true),(date '2026-05-14', true),
        (date '2026-05-27', true),(date '2026-06-01', true),
        (date '2026-06-17', true),(date '2026-08-17', true),
        (date '2026-08-26', true),(date '2026-12-25', true)
    ) AS h(txn_date, is_holiday)
),
daily AS (
    SELECT
        t.transaction_time::date                           AS txn_date,
        m.mcc_code,
        SUM(t.amount) FILTER (WHERE t.transaction_status = 'APPROVED'
                               AND t.transaction_type = 'SALE') AS daily_sales,
        COUNT(*) FILTER (WHERE t.transaction_status = 'APPROVED') AS approved_trx
    FROM transactions t
    JOIN merchants m ON m.merchant_id = t.merchant_id
    WHERE t.transaction_time >= :date_from::date
      AND t.transaction_time <  :date_to::date + interval '1 day'
    GROUP BY 1, 2
)
SELECT
    d.mcc_code,
    COALESCE(h.is_holiday, false)                          AS is_holiday,
    COUNT(*)                                               AS day_count,
    ROUND(AVG(d.daily_sales), 0)                           AS avg_daily_sales,
    ROUND(AVG(d.approved_trx), 1)                          AS avg_daily_trx
FROM daily d
LEFT JOIN holiday_dates h ON h.txn_date = d.txn_date
GROUP BY d.mcc_code, COALESCE(h.is_holiday, false)
ORDER BY d.mcc_code, is_holiday;


-- =========================================================
-- 15. HOURLY HEATMAP  (transaction density by hour-of-day)
-- =========================================================
SELECT
    EXTRACT(HOUR FROM t.transaction_time)::int             AS hour_of_day,
    COUNT(*)                                               AS total_trx,
    ROUND(AVG(t.amount) FILTER (WHERE t.transaction_status = 'APPROVED'), 0) AS avg_amount,
    COUNT(*) FILTER (WHERE t.payment_channel = 'QRIS')     AS qris_trx,
    COUNT(*) FILTER (WHERE t.payment_channel = 'EDC_CARD') AS card_trx
FROM transactions t
WHERE t.transaction_time >= :date_from::date
  AND t.transaction_time <  :date_to::date + interval '1 day'
GROUP BY 1
ORDER BY 1;
