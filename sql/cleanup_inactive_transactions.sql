-- Remove transaction data for INACTIVE merchants.
-- Merchant and terminal records are preserved.
-- Run order matters: transaction_log → transactions → settlement (FK deps).

BEGIN;

-- 1. Audit log rows referencing these transactions
DELETE FROM transaction_log
WHERE transaction_id IN (
    SELECT t.transaction_id
    FROM   transactions t
    JOIN   merchants    m ON m.merchant_id = t.merchant_id
    WHERE  m.merchant_status = 'INACTIVE'
);

-- 2. Transaction rows
DELETE FROM transactions
WHERE merchant_id IN (
    SELECT merchant_id FROM merchants WHERE merchant_status = 'INACTIVE'
);

-- 3. Settlement summaries
DELETE FROM settlement
WHERE merchant_id IN (
    SELECT merchant_id FROM merchants WHERE merchant_status = 'INACTIVE'
);

-- Verify
SELECT
    (SELECT COUNT(*) FROM transactions t
     JOIN merchants m ON m.merchant_id = t.merchant_id
     WHERE m.merchant_status = 'INACTIVE') AS remaining_txns,
    (SELECT COUNT(*) FROM merchants WHERE merchant_status = 'INACTIVE') AS inactive_merchants;

COMMIT;
