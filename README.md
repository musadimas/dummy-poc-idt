# EDC Transaction POC

A proof-of-concept PostgreSQL database for Indonesian EDC (Electronic Data Capture) transaction processing, built around real Points of Interest data from Depok/Bogor area.

---

## Project Structure

```
poc-edc/
├── schema.sql        # DDL — all tables, indexes, views, static seed data
├── seed_data.py      # Python seeder — generates realistic transactions from poi_edc.csv
├── queries.sql       # Analytical SQL queries with date-range filters
├── poi_edc.csv       # Source POI data (29 active merchants)
└── reports/
    └── YYYYMMDD/     # JPEG activity cards generated per run (one file per merchant)
```

---

## Prerequisites

- PostgreSQL 13+
- Python 3.9+
- `psycopg2-binary` — database driver
- `Pillow` — JPEG card generation
- `openpyxl` — Excel report generation

---

## Quick Start

### 1. Create the database and apply schema

```bash
python -m venv venv && source venv/Scripts/activate && pip install psycopg2-binary Pillow && PGPASSWORD=Manualbrew1 psql -U postgres -c "CREATE DATABASE edtransmap;" && PGPASSWORD=Manualbrew1 psql -U postgres -d edtransmap -f schema.sql
```

### 2. Seed the data

```bash
python seed_data.py
```

---

## Seeder Modes

| Command | Behaviour |
|---|---|
| `python seed_data.py` | Smart default — if DB already has data, appends from the last transaction date to `DATE_END`; if DB is empty, performs an initial full seed |
| `python seed_data.py --reset` | Full reset — truncates all tables and re-seeds from scratch (explicit wipe required) |
| `python seed_data.py --purge` | Date-range purge — deletes only transactions/settlement for `DATE_START`–`DATE_END`, keeps merchants/cards/admin areas, then re-seeds transactions |
| `python seed_data.py --report` | Report only — skips all seeding, queries existing data, prints console cards and saves JPEGs |
| `python seed_data.py --append` | Append — finds the last transaction date already in the DB, seeds only from the next day up to `DATE_END`, and generates the report. Never touches existing rows. |
| `python seed_data.py --prune-closed` | Closed-merchant prune — reads `closed_from` dates from `poi_edc.csv` and deletes all transaction/settlement data on or after each merchant's closure date, then generates a fresh report |
| `python seed_data.py --batch-seed` | Batch seed — reads `list_new_edc.xlsx` (sheet "new") and `list_update_edc.xlsx` (sheet "update"), inserts only merchants not already in the DB, generates transactions for them, and produces a two-sheet `batch_activity_report.xlsx` alongside the full report |
| `python seed_data.py --add-merchants` | Add merchants — inserts only merchants from `poi_edc.csv` not already in the DB, then generates their transactions and report |

After seeding (or with `--report`), the script prints a merchant activity health card for every POI and saves a JPEG per merchant to `reports/YYYYMMDD/`.

---

## Configuration

All settings are at the top of `seed_data.py`. Override the DB connection via environment variables:

| Variable | Default | Description |
|---|---|---|
| `PG_HOST` | `localhost` | PostgreSQL host |
| `PG_PORT` | `5432` | PostgreSQL port |
| `PG_DB` | `edtransmap` | Database name |
| `PG_USER` | `postgres` | Username |
| `PG_PASSWORD` | `Manualbrew1` | Password |

**Date range** — change these two lines in `seed_data.py`:

```python
DATE_START = date(2026, 3, 12)
DATE_END   = date(2026, 6, 12)   # inclusive
```

The merchant registration date embedded in codes (e.g. `MCH-5814-20250301-00001`) is automatically set to a random date 3–18 months before `DATE_START`.

---

## Database Schema

### Tables

| Table | PK | Purpose |
|---|---|---|
| `admin_areas` | `SERIAL` | Self-referential hierarchy: Province → City/Regency → District → Village |
| `acquirers` | `SMALLSERIAL` | Banks operating EDC acquiring (BCA, Mandiri, BNI) |
| `merchants` | `UUID` | Merchant profiles with geo-coordinates and admin area FK |
| `terminals` | `UUID` | Physical EDC machines, one per merchant |
| `cards` | `BIGSERIAL` | Synthetic masked card references |
| `qris_issuers` | `SMALLSERIAL` | QRIS sources: GoPay, ShopeePay, Dana, OVO, LinkAja, BCA, Mandiri, BNI, BRI |
| `transactions` | `BIGSERIAL` | All payment transactions with CHECK constraint enforcing EDC_CARD/QRIS exclusivity |
| `settlement` | `SERIAL` | Daily batch settlement summary per merchant |
| `transaction_log` | `BIGSERIAL` | ISO 8583 raw message audit trail |

### Views

| View | Description |
|---|---|
| `vw_merchant_admin_hierarchy` | Full province → city → district → village path per merchant |
| `vw_district_transaction_summary` | Transaction volume grouped by administrative district |
| `vw_daily_merchant_summary` | Daily transaction summary per merchant |
| `vw_terminal_approval_rate` | Approval rate per terminal |
| `vw_channel_split` | QRIS vs card channel split per merchant |
| `vw_unsettled_transactions` | Approved transactions not yet settled |
| `vw_settlement_reconciliation` | Settlement vs computed totals discrepancy check |

### Code Formats

| Field | Format | Example |
|---|---|---|
| `merchant_code` | `MCH-{MCC}-{YYYYMMDD}-{SEQ:05d}` | `MCH-5814-20250301-00001` |
| `terminal_code` | `TID-{MCC}-{YYYYMMDD}-{SEQ:05d}` | `TID-5814-20250301-00001` |
| `serial_number` | `SN-{YYYY}-{SEQ:04d}` | `SN-2026-0001` |
| `trace_number` | `RRN{YYYYMMDD}{SEQ:06d}` | `RRN20260601000001` |
| `approval_code` | 6-char alphanumeric | `A1B2C3` |

---

## Data Characteristics

### Merchants (29 POIs)

Categories seeded from `poi_edc.csv`, mapped to ISO 18245 MCC codes:

| Category | MCC |
|---|---|
| Restaurant / Casual Dining | 5812 |
| Coffee Shop | 5814 |
| Food-Beverage Specialty Store | 5499 |
| Clothing and Accessories | 5651 |
| Women's Apparel | 5621 |
| Florist | 5992 |
| Hair and Beauty | 7230 |
| Wellness Center and Services | 7298 |
| Therapist | 8049 |
| Dentist-Dental Office | 8021 |
| School | 8220 |
| Convention-Exhibition Center | 7990 |

### Transaction Behaviour

- **QRIS vs Card** — F&B and everyday services lean QRIS (55–70%); luxury retail leans card (25–28%). Bank QRIS collectively exceeds fintech. GoPay leads fintech issuers.
- **QRIS declines** — limited to connection timeout (`91`) and do-not-honor (`05`) only. Insufficient funds (`51`), expired card (`54`), and limit codes never fire on QRIS because the wallet balance is shown to the customer before confirmation.
- **QRIS refunds** — not generated as transaction records. When a QRIS payment fails, the network reverses it automatically; no `REFUND` row is written to the EDC system.
- **Transaction mix** — ~85% SALE, ~3% REFUND (card only), ~2% VOID companions for approved SALEs.
- **Approval rate** — ~88% for EDC card, ~97% for QRIS.
- **Operating hours** — sourced from actual Google Maps data in the CSV. Category-level defaults applied when CSV has no hours.
- **Holiday closures** — Indonesian national holidays (2025–2026) cause Clothing, Florist, School, Dentist, and Convention categories to generate zero transactions that day. F&B and wellness remain open.

### Cards (300 synthetic)

Brands: VISA, MASTERCARD, JCB, AMEX, GPN  
Types: DEBIT (50%), CREDIT (40%), PREPAID (10%)  
Issuing banks: BCA, Mandiri, BNI, BRI, Permata, CIMB Niaga, BTN, BSI

---

## Seeder Output

Running `python seed_data.py` produces a step-by-step progress log, a row-count verification, and a merchant activity health report. Each merchant gets a console card and a JPEG saved to `reports/YYYYMMDD/`.

```
============================================================
  EDC POC Seeder
  Mode       : FULL RESET
  Date range : 2026-03-12 — 2026-06-12
  CSV        : poi_edc.csv
  Database   : edtransmap@localhost:5432
============================================================
[1/7] Resetting database...
[2/7] Loading reference data...
[3/7] Loading CSV...          29 active POIs loaded.
[4/7] Inserting admin areas...
[5/7] Inserting merchants + terminals...
[6/7] Inserting cards...      300 cards inserted.
[7/7] Generating transactions, settlement, and audit logs...

Row count verification:
      admin_areas                   12
      merchants                     29
      terminals                     29
      cards                        300
      qris_issuers                   9
      transactions              87,241
      settlement                   580
      transaction_log          171,604

[8/8] Merchant activity report...

══════════════════════════════════════════════════════════════
  MERCHANT ACTIVITY REPORT
  Loaded at : 2026-06-12T14:30:00+0700  (WIB UTC+7)
  Data range: 2026-03-12 – 2026-06-12
  Output    : reports/20260612
══════════════════════════════════════════════════════════════

──────────────────────────────────────────────────────────────
Kopi Konnichiwa
STATUS        : ACTIVE     (confidence 0.941)
last_txn      : 2026-06-12T18:44:10+0700  (0.3h ago)
txn 24h/7d/30d: 87 / 612 / 2451
channel split : QRIS 1714  |  EDC 737
active days   : 30/30  (ratio 1.000, max gap 1d)
reasons       :
  - last txn 0h ago (<= 72h)
  - 30/30 active days, max gap 1d
  - 2451 approved txn / 30d (1714 QRIS, 737 EDC)

══════════════════════════════════════════════════════════════
  JPEG cards saved to: reports/20260612
══════════════════════════════════════════════════════════════
```

### Activity Card — Confidence Score

Each merchant gets a `STATUS` derived from a weighted score (0–1):

| Factor | Weight | Signal |
|---|---|---|
| Recency | 40% | Hours since last approved transaction |
| Activity ratio | 35% | Distinct active days / 30-day window |
| Volume | 25% | Log-scaled approved SALE count (30d) |

| Status | Condition |
|---|---|
| `ACTIVE` | confidence ≥ 0.75 and last transaction ≤ 72h ago |
| `INACTIVE` | confidence ≥ 0.40 or last transaction ≤ 7 days ago |
| `SUSPENDED` | below both thresholds |

---

## Analytical Queries

`queries.sql` contains 15 ready-to-run queries. Set the date window in psql first:

```sql
\set date_from '2026-03-12'
\set date_to   '2026-06-12'
```

| # | Query |
|---|---|
| 1 | Raw transactions (date range, newest first) |
| 2 | Overall totals — gross sales, refunds, net revenue, approval rate |
| 3 | Daily transaction trend |
| 4 | Payment channel split (QRIS vs EDC_CARD) |
| 5 | QRIS issuer breakdown with share % |
| 6 | Card brand breakdown |
| 7 | Top merchants by transaction volume |
| 8 | Category / MCC breakdown with avg ticket and QRIS share |
| 9 | Decline analysis by ISO 8583 response code |
| 10 | Terminal approval rates |
| 11 | Geographic summary (Province → City → District) |
| 12 | Settlement status by date |
| 13 | Unsettled approved transactions |
| 14 | Holiday effect — avg daily sales on holidays vs normal days |
| 15 | Hourly transaction heatmap |

All queries mask internal IDs. Codes are partially masked using `LEFT / REPEAT / RIGHT`:

```
MCH-5814-20250301-00001  →  MCH******************01
TID-5814-20250301-00001  →  TID******************01
```
