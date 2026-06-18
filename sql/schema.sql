-- =========================================================
-- EDC (Electronic Data Capture) Transaction POC Database
-- PostgreSQL 13+  |  gen_random_uuid() built-in, no extension needed
-- =========================================================

DROP TABLE IF EXISTS transaction_log  CASCADE;
DROP TABLE IF EXISTS settlement        CASCADE;
DROP TABLE IF EXISTS transactions      CASCADE;
DROP TABLE IF EXISTS cards             CASCADE;
DROP TABLE IF EXISTS qris_issuers      CASCADE;
DROP TABLE IF EXISTS terminals         CASCADE;
DROP TABLE IF EXISTS merchants         CASCADE;
DROP TABLE IF EXISTS admin_areas       CASCADE;
DROP TABLE IF EXISTS acquirers         CASCADE;

-- =========================================================
-- 1. ADMINISTRATIVE AREAS  (Indonesia: Province → City → District → Village)
-- =========================================================
CREATE TABLE admin_areas (
    area_id     SERIAL       PRIMARY KEY,
    area_name   VARCHAR(200) NOT NULL,
    area_level  SMALLINT     NOT NULL
                             CHECK (area_level BETWEEN 1 AND 4),
                             -- 1 = Province  (Provinsi)
                             -- 2 = City/Regency  (Kota/Kabupaten)
                             -- 3 = District  (Kecamatan)
                             -- 4 = Village  (Kelurahan/Desa)
    parent_id   INT          REFERENCES admin_areas(area_id),
    area_code   VARCHAR(20),                -- BPS / Kemendagri code placeholder
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (area_name, area_level, parent_id)
);

CREATE INDEX idx_admin_areas_parent ON admin_areas(parent_id);

-- =========================================================
-- 2. ACQUIRERS  (banks that operate EDC acquiring services)
-- =========================================================
CREATE TABLE acquirers (
    acquirer_id   SMALLSERIAL  PRIMARY KEY,
    acquirer_name VARCHAR(100) NOT NULL,
    bank_code     VARCHAR(20)  NOT NULL UNIQUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- =========================================================
-- 3. MERCHANTS
-- =========================================================
CREATE TABLE merchants (
    merchant_id   UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_name VARCHAR(200) NOT NULL,
    merchant_code VARCHAR(30)  NOT NULL UNIQUE,   -- MCH-{MCC}-{YYYYMMDD}-{SEQ:05d}  e.g. MCH-5814-20250301-00001
    mcc_code      CHAR(4)      NOT NULL,           -- ISO 18245 MCC
    address       TEXT,
    city          VARCHAR(100),                    -- denormalised display name
    admin_area_id INT          REFERENCES admin_areas(area_id),  -- FK to deepest known level
    latitude      DECIMAL(10,8),                   -- ±90 with 8 decimal places
    longitude     DECIMAL(11,8),                   -- ±180 with 8 decimal places
    acquirer_id   SMALLINT     REFERENCES acquirers(acquirer_id),
    status        VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE'
                               CHECK (status IN ('ACTIVE','INACTIVE','SUSPENDED')),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_merchants_admin_area ON merchants(admin_area_id);

-- =========================================================
-- 4. TERMINALS  (physical EDC machines; UUID for field exposure)
-- =========================================================
CREATE TABLE terminals (
    terminal_id   UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    terminal_code VARCHAR(30)  NOT NULL UNIQUE,   -- TID-{MCC}-{YYYYMMDD}-{SEQ:05d}  e.g. TID-5814-20250301-00001
    merchant_id   UUID         NOT NULL REFERENCES merchants(merchant_id),
    serial_number VARCHAR(50)  UNIQUE,            -- SN-2026-0001
    model         VARCHAR(100),
    status        VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE'
                               CHECK (status IN ('ACTIVE','INACTIVE','MAINTENANCE')),
    installed_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- =========================================================
-- 5. CARDS  (cardholder reference — tokenised / masked)
-- =========================================================
CREATE TABLE cards (
    card_id            BIGSERIAL    PRIMARY KEY,
    card_number_masked VARCHAR(25)  NOT NULL,   -- 4111 11** **** 1111
    card_type          VARCHAR(10)  NOT NULL
                                    CHECK (card_type IN ('CREDIT','DEBIT','PREPAID')),
    card_brand         VARCHAR(20)  NOT NULL
                                    CHECK (card_brand IN ('VISA','MASTERCARD','JCB','AMEX','GPN')),
    issuing_bank       VARCHAR(100),
    expiry_date        CHAR(7),                 -- MM/YYYY
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- =========================================================
-- 6. QRIS ISSUERS  (bank & fintech e-wallet QR sources)
-- =========================================================
CREATE TABLE qris_issuers (
    qris_issuer_id SMALLSERIAL  PRIMARY KEY,
    issuer_name    VARCHAR(100) NOT NULL,
    issuer_code    VARCHAR(20)  NOT NULL UNIQUE,   -- GOPAY, SHOPEEPAY, BCA-QRIS …
    issuer_type    VARCHAR(10)  NOT NULL
                                CHECK (issuer_type IN ('FINTECH','BANK')),
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- =========================================================
-- 7. TRANSACTIONS
-- =========================================================
CREATE TABLE transactions (
    transaction_id     BIGSERIAL      PRIMARY KEY,
    trace_number       VARCHAR(30)    NOT NULL UNIQUE,   -- RRN20260601000001
    terminal_id        UUID           NOT NULL REFERENCES terminals(terminal_id),
    merchant_id        UUID           NOT NULL REFERENCES merchants(merchant_id),
    -- payment reference: exactly one of card_id or qris_issuer_id must be set
    card_id            BIGINT         REFERENCES cards(card_id),
    qris_issuer_id     SMALLINT       REFERENCES qris_issuers(qris_issuer_id),
    payment_channel    VARCHAR(10)    NOT NULL DEFAULT 'EDC_CARD'
                                      CHECK (payment_channel IN ('EDC_CARD','QRIS')),
    transaction_type   VARCHAR(20)    NOT NULL
                                      CHECK (transaction_type IN ('SALE','REFUND','VOID','PRE_AUTH','CASH_ADVANCE')),
    amount             NUMERIC(15,2)  NOT NULL,
    currency           CHAR(3)        NOT NULL DEFAULT 'IDR',
    response_code      VARCHAR(5)     NOT NULL,   -- ISO 8583: 00 approved, 05 declined …
    response_message   VARCHAR(100),
    approval_code      VARCHAR(10),               -- NULL when declined
    transaction_status VARCHAR(20)    NOT NULL
                                      CHECK (transaction_status IN ('PENDING','APPROVED','DECLINED','REVERSED','VOIDED')),
    batch_number       VARCHAR(10),
    transaction_time   TIMESTAMPTZ    NOT NULL,
    settled_flag       BOOLEAN        NOT NULL DEFAULT FALSE,

    -- Enforce: EDC_CARD txns must have card_id; QRIS txns must have qris_issuer_id
    CONSTRAINT chk_payment_ref CHECK (
        (payment_channel = 'EDC_CARD' AND card_id IS NOT NULL AND qris_issuer_id IS NULL)
        OR
        (payment_channel = 'QRIS'     AND qris_issuer_id IS NOT NULL AND card_id IS NULL)
    )
);

CREATE INDEX idx_trx_time           ON transactions(transaction_time);
CREATE INDEX idx_trx_status         ON transactions(transaction_status);
CREATE INDEX idx_trx_merchant       ON transactions(merchant_id);
CREATE INDEX idx_trx_merchant_settle ON transactions(merchant_id, settled_flag);
CREATE INDEX idx_trx_channel        ON transactions(payment_channel);

-- =========================================================
-- 8. SETTLEMENT  (batch settlement summary per merchant-day)
-- =========================================================
CREATE TABLE settlement (
    settlement_id        SERIAL         PRIMARY KEY,
    merchant_id          UUID           NOT NULL REFERENCES merchants(merchant_id),
    terminal_id          UUID           NOT NULL REFERENCES terminals(terminal_id),
    batch_number         VARCHAR(10)    NOT NULL,
    settlement_date      DATE           NOT NULL,
    total_sales_count    INT            NOT NULL DEFAULT 0,
    total_sales_amount   NUMERIC(15,2)  NOT NULL DEFAULT 0,
    total_refund_count   INT            NOT NULL DEFAULT 0,
    total_refund_amount  NUMERIC(15,2)  NOT NULL DEFAULT 0,
    net_amount           NUMERIC(15,2)  NOT NULL DEFAULT 0,
    status               VARCHAR(20)    NOT NULL DEFAULT 'PENDING'
                                        CHECK (status IN ('PENDING','SETTLED','FAILED')),
    created_at           TIMESTAMPTZ    NOT NULL DEFAULT now(),
    UNIQUE (merchant_id, terminal_id, settlement_date)
);

-- =========================================================
-- 9. TRANSACTION LOG  (ISO 8583 raw message audit trail)
-- =========================================================
CREATE TABLE transaction_log (
    log_id         BIGSERIAL    PRIMARY KEY,
    transaction_id BIGINT       NOT NULL REFERENCES transactions(transaction_id),
    log_type       VARCHAR(20)  NOT NULL
                                CHECK (log_type IN ('REQUEST','RESPONSE','REVERSAL')),
    raw_message    TEXT,
    logged_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_txlog_txn ON transaction_log(transaction_id);

-- =========================================================
-- STATIC SEED DATA
-- =========================================================

INSERT INTO acquirers (acquirer_name, bank_code) VALUES
    ('Bank Central Asia',    'BCA001'),
    ('Bank Mandiri',         'MDR002'),
    ('Bank Negara Indonesia','BNI003');

INSERT INTO qris_issuers (issuer_name, issuer_code, issuer_type) VALUES
    ('GoPay',       'GOPAY',      'FINTECH'),
    ('ShopeePay',   'SHOPEEPAY',  'FINTECH'),
    ('Dana',        'DANA',       'FINTECH'),
    ('OVO',         'OVO',        'FINTECH'),
    ('LinkAja',     'LINKAJA',    'FINTECH'),
    ('BCA Mobile',  'BCA-QRIS',   'BANK'),
    ('Mandiri QRIS','MDR-QRIS',   'BANK'),
    ('BNI QRIS',    'BNI-QRIS',   'BANK'),
    ('BRI QRIS',    'BRI-QRIS',   'BANK');

-- =========================================================
-- USEFUL VIEWS
-- =========================================================

-- Full admin hierarchy path for each merchant (Province > City > District > Village)
CREATE OR REPLACE VIEW vw_merchant_admin_hierarchy AS
WITH RECURSIVE hier AS (
    SELECT area_id, area_name, area_level, parent_id,
           area_name::TEXT AS path
    FROM   admin_areas
    WHERE  parent_id IS NULL
    UNION ALL
    SELECT c.area_id, c.area_name, c.area_level, c.parent_id,
           h.path || ' > ' || c.area_name
    FROM   admin_areas c
    JOIN   hier h ON h.area_id = c.parent_id
)
SELECT
    m.merchant_id,
    m.merchant_name,
    m.merchant_code,
    prov.area_name   AS province,
    city.area_name   AS city,
    dist.area_name   AS district,
    vill.area_name   AS village,
    h.path           AS full_path
FROM merchants m
LEFT JOIN admin_areas dist ON dist.area_id    = m.admin_area_id
LEFT JOIN admin_areas city ON city.area_id    = dist.parent_id
LEFT JOIN admin_areas prov ON prov.area_id    = city.parent_id
LEFT JOIN admin_areas vill ON vill.parent_id  = m.admin_area_id  -- village level below district
LEFT JOIN hier        h    ON h.area_id       = m.admin_area_id;

-- Transaction volume grouped by administrative district
CREATE OR REPLACE VIEW vw_district_transaction_summary AS
SELECT
    prov.area_name                         AS province,
    city.area_name                         AS city,
    dist.area_name                         AS district,
    COUNT(DISTINCT m.merchant_id)          AS merchant_count,
    COUNT(t.transaction_id)                AS total_trx,
    SUM(t.amount)                          AS total_amount,
    ROUND(AVG(t.amount), 0)               AS avg_amount
FROM transactions t
JOIN merchants   m    ON m.merchant_id  = t.merchant_id
LEFT JOIN admin_areas dist ON dist.area_id = m.admin_area_id
LEFT JOIN admin_areas city ON city.area_id = dist.parent_id
LEFT JOIN admin_areas prov ON prov.area_id = city.parent_id
WHERE t.transaction_status = 'APPROVED'
GROUP BY 1, 2, 3
ORDER BY 5 DESC;

-- Daily transaction summary per merchant
CREATE OR REPLACE VIEW vw_daily_merchant_summary AS
SELECT
    m.merchant_name,
    m.merchant_code,
    t.transaction_time::date             AS txn_date,
    t.payment_channel,
    t.transaction_status,
    COUNT(*)                             AS total_trx,
    SUM(t.amount)                        AS total_amount
FROM transactions t
JOIN merchants m ON m.merchant_id = t.merchant_id
GROUP BY 1, 2, 3, 4, 5
ORDER BY 1, 3;

-- Approval rate per terminal
CREATE OR REPLACE VIEW vw_terminal_approval_rate AS
SELECT
    te.terminal_code,
    m.merchant_name,
    COUNT(*)                                                          AS total_trx,
    SUM(CASE WHEN t.transaction_status = 'APPROVED' THEN 1 ELSE 0 END) AS approved_trx,
    ROUND(
        100.0 * SUM(CASE WHEN t.transaction_status = 'APPROVED' THEN 1 ELSE 0 END)
              / NULLIF(COUNT(*), 0),
        2
    )                                                                 AS approval_rate_pct
FROM transactions t
JOIN terminals te ON te.terminal_id = t.terminal_id
JOIN merchants  m ON m.merchant_id  = t.merchant_id
GROUP BY 1, 2
ORDER BY 3 DESC;

-- QRIS vs card channel split per merchant
CREATE OR REPLACE VIEW vw_channel_split AS
SELECT
    m.merchant_name,
    t.payment_channel,
    qi.issuer_name                        AS qris_issuer,
    c.card_brand,
    COUNT(*)                              AS trx_count,
    SUM(t.amount)                         AS total_amount
FROM transactions t
JOIN merchants m ON m.merchant_id = t.merchant_id
LEFT JOIN qris_issuers qi ON qi.qris_issuer_id = t.qris_issuer_id
LEFT JOIN cards        c  ON c.card_id          = t.card_id
WHERE t.transaction_status = 'APPROVED'
GROUP BY 1, 2, 3, 4
ORDER BY 1, 5 DESC;

-- Unsettled approved transactions
CREATE OR REPLACE VIEW vw_unsettled_transactions AS
SELECT
    t.trace_number,
    m.merchant_name,
    te.terminal_code,
    t.payment_channel,
    t.amount,
    t.transaction_time
FROM transactions t
JOIN merchants m  ON m.merchant_id  = t.merchant_id
JOIN terminals te ON te.terminal_id = t.terminal_id
WHERE t.transaction_status = 'APPROVED'
  AND t.settled_flag = FALSE
ORDER BY t.transaction_time;

-- Settlement reconciliation check
CREATE OR REPLACE VIEW vw_settlement_reconciliation AS
SELECT
    s.merchant_id,
    m.merchant_name,
    s.batch_number,
    s.settlement_date,
    s.total_sales_amount                        AS recorded_sales,
    COALESCE((
        SELECT SUM(t.amount)
        FROM   transactions t
        WHERE  t.merchant_id     = s.merchant_id
          AND  t.batch_number    = s.batch_number
          AND  t.transaction_type = 'SALE'
          AND  t.transaction_status = 'APPROVED'
    ), 0)                                       AS computed_sales,
    s.total_sales_amount - COALESCE((
        SELECT SUM(t.amount)
        FROM   transactions t
        WHERE  t.merchant_id      = s.merchant_id
          AND  t.batch_number     = s.batch_number
          AND  t.transaction_type = 'SALE'
          AND  t.transaction_status = 'APPROVED'
    ), 0)                                       AS discrepancy
FROM settlement s
JOIN merchants m ON m.merchant_id = s.merchant_id
ORDER BY ABS(
    s.total_sales_amount - COALESCE((
        SELECT SUM(t.amount)
        FROM   transactions t
        WHERE  t.merchant_id      = s.merchant_id
          AND  t.batch_number     = s.batch_number
          AND  t.transaction_type = 'SALE'
          AND  t.transaction_status = 'APPROVED'
    ), 0)
) DESC;
