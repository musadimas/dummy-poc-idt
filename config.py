"""
config.py — pure-data constants for the EDC POC seeder.
No function definitions — only assignments.
"""

import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# DATABASE / PATHS
# ──────────────────────────────────────────────────────────────────────────────

DB_CONFIG = {
    "host":     os.getenv("PG_HOST",     "localhost"),
    "port":     int(os.getenv("PG_PORT", "5432")),
    "dbname":   os.getenv("PG_DB",       "edtransmap"),
    "user":     os.getenv("PG_USER",     "postgres"),
    "password": os.getenv("PG_PASSWORD", "Manualbrew1"),
}

INPUT_DIR  = Path(__file__).parent / "input"
CSV_PATH   = INPUT_DIR / "poi_edc.csv"
DATE_START = date(2025, 1, 1)
DATE_END   = date.today()         # inclusive

# ── Google Drive upload ───────────────────────────────────────────────────────
GDRIVE_FOLDER_ID   = ""           # paste your Drive folder ID here
GDRIVE_CREDENTIALS = Path(__file__).parent / "credentials.json"
GDRIVE_TOKEN       = Path(__file__).parent / "token.json"
GDRIVE_SCOPES      = ["https://www.googleapis.com/auth/drive.file"]

TERMINAL_MODELS = [
    "Verifone VX520",
    "Verifone V240m",
    "Ingenico iCT250",
    "Ingenico Move5000",
]

CARD_BRANDS   = ["VISA", "MASTERCARD", "JCB", "AMEX", "GPN"]
CARD_TYPES    = ["CREDIT", "DEBIT", "PREPAID"]
ISSUING_BANKS = [
    "Bank BCA", "Bank Mandiri", "Bank BNI", "Bank BRI",
    "Bank Permata", "CIMB Niaga", "Bank BTN", "Bank BSI",
]
CARD_PREFIXES = {
    "VISA":       ["4111", "4532", "4916", "4539"],
    "MASTERCARD": ["5400", "5105", "5500", "5425"],
    "JCB":        ["3530", "3566", "3500"],
    "AMEX":       ["3714", "3782", "3787"],
    "GPN":        ["6011", "6500", "6221"],
}

# ──────────────────────────────────────────────────────────────────────────────
# MCC MAPPING
# ──────────────────────────────────────────────────────────────────────────────

CATEGORY_TO_MCC = {
    # ── Original categories ──────────────────────────────────────────────────
    "Restaurant":                    "5812",
    "Casual Dining":                 "5812",
    "Fine Dining":                   "5812",
    "Coffee Shop":                   "5814",
    "Food-Beverage Specialty Store": "5499",
    "Clothing and Accessories":      "5651",
    "Women's Apparel":               "5621",
    "Children's Apparel":            "5641",
    "Florist":                       "5992",
    "Hair and Beauty":               "7230",
    "Wellness Center and Services":  "7298",
    "Therapist":                     "8049",
    "Dentist-Dental Office":         "8021",
    "School":                        "8220",
    "Language Studies":              "8220",
    "Training and Development":      "8249",
    "Bus Stop":                      "4111",
    "Convention-Exhibition Center":  "7990",
    # ── F&B ──────────────────────────────────────────────────────────────────
    "Bakery and Baked Goods Store":  "5462",
    "Butcher":                       "5499",
    "Convenience Store":             "5411",
    "Wine and Liquor":               "5921",
    "Bar or Pub":                    "5813",
    "Night Club":                    "5813",
    # ── Retail ───────────────────────────────────────────────────────────────
    "Specialty Store":               "5999",
    "Jeweler":                       "5944",
    "Sporting Goods Store":          "5941",
    "Major Appliance":               "5722",
    "Home Improvement-Hardware Store": "5251",
    "Floor and Carpet":              "5713",
    "Office Supply and Services Store": "5112",
    "Automobile Dealership-New Cars": "5511",
    "Pharmacy":                      "5912",
    # ── Services ─────────────────────────────────────────────────────────────
    "Car Wash-Detailing":            "7542",
    "Dry Cleaning and Laundry":      "7211",
    "Fitness-Health Club":           "7997",
    "Barber":                        "7241",
    "Pet Care":                      "5995",
    "Repair Service":                "7699",
    "Mobile Service Center":         "7629",
    "IT and Office Equipment Services": "7372",
    "Interior and Exterior Design":  "7389",
    "Business Service":              "7389",
    "Consumer Services":             "7299",
    "Couriers":                      "4215",
    "Tire Repair":                   "7534",
    "Billiards-Pool Hall":           "7993",
    "Video Arcade-Game Room":        "7993",
    "Golf Course":                   "7992",
    # ── Health ───────────────────────────────────────────────────────────────
    "Medical Services-Clinics":      "8099",
    "Hospital":                      "8062",
    # ── Real estate / other ──────────────────────────────────────────────────
    "Real Estate Services":          "6513",
    "Residential Area-Building":     "6512",
    # ── F&B (additional) ─────────────────────────────────────────────────────
    "Fast Food":                     "5814",
    "Deli":                          "5812",
    "Take Out and Delivery Only":    "5812",
    "Grocery":                       "5411",
    "Cigar and Tobacco Shop":        "5993",
    "Vaping Store":                  "5999",
    # ── Retail (additional) ──────────────────────────────────────────────────
    "Shoes-Footwear":                "5661",
    "Computer and Software":         "5734",
    "Mobile Retailer":               "5732",
    "Optical":                       "8043",
    # ── Services (additional) ────────────────────────────────────────────────
    "Hotel":                         "7011",
    "Karaoke":                       "5813",
    "Transportation Service":        "4789",
    "Wedding Services and Bridal Studio": "7230",
}

# ──────────────────────────────────────────────────────────────────────────────
# CATEGORY PROFILES  (transactions/day range, IDR amount range)
# ──────────────────────────────────────────────────────────────────────────────

VOLUME_PROFILE = {
    "Restaurant":                    (30, 150),
    "Casual Dining":                 (30, 150),
    "Fine Dining":                   (15,  60),
    "Coffee Shop":                   (30, 150),
    "Food-Beverage Specialty Store": (20,  80),
    "Bakery and Baked Goods Store":  (20,  80),
    "Butcher":                       (10,  40),
    "Convenience Store":             (30, 120),
    "Wine and Liquor":               ( 5,  25),
    "Bar or Pub":                    (15,  60),
    "Night Club":                    (10,  50),
    "Clothing and Accessories":      (10,  50),
    "Women's Apparel":               (10,  50),
    "Children's Apparel":            ( 5,  25),
    "Specialty Store":               ( 5,  25),
    "Jeweler":                       ( 2,  15),
    "Sporting Goods Store":          ( 5,  20),
    "Pharmacy":                      (10,  40),
    "Florist":                       ( 5,  30),
    "Hair and Beauty":               ( 5,  25),
    "Barber":                        ( 8,  30),
    "Wellness Center and Services":  ( 3,  20),
    "Therapist":                     ( 3,  20),
    "Fitness-Health Club":           ( 5,  25),
    "Pet Care":                      ( 3,  15),
    "Dentist-Dental Office":         ( 3,  15),
    "Medical Services-Clinics":      ( 5,  25),
    "Hospital":                      ( 5,  20),
    "School":                        ( 1,   8),
    "Language Studies":              ( 2,  10),
    "Training and Development":      ( 2,  10),
    "Convention-Exhibition Center":  ( 1,   8),
    "Car Wash-Detailing":            ( 5,  20),
    "Dry Cleaning and Laundry":      ( 5,  20),
    "Repair Service":                ( 3,  15),
    "Mobile Service Center":         ( 5,  20),
    "Fast Food":                     (30, 120),
    "Deli":                          (15,  60),
    "Take Out and Delivery Only":    (15,  60),
    "Grocery":                       (20,  80),
    "Cigar and Tobacco Shop":        ( 3,  15),
    "Vaping Store":                  ( 3,  15),
    "Shoes-Footwear":                ( 5,  25),
    "Computer and Software":         ( 2,  10),
    "Mobile Retailer":               ( 3,  15),
    "Optical":                       ( 2,  10),
    "Hotel":                         ( 5,  20),
    "Karaoke":                       ( 5,  25),
    "Transportation Service":        ( 3,  15),
    "Wedding Services and Bridal Studio": ( 1,   5),
}

AMOUNT_RANGE = {
    "Restaurant":                    (  25_000,   500_000),
    "Casual Dining":                 (  25_000,   500_000),
    "Fine Dining":                   ( 100_000, 1_500_000),
    "Coffee Shop":                   (  20_000,   150_000),
    "Food-Beverage Specialty Store": (  20_000,   150_000),
    "Bakery and Baked Goods Store":  (  15_000,   100_000),
    "Butcher":                       (  30_000,   300_000),
    "Convenience Store":             (  10_000,   200_000),
    "Wine and Liquor":               (  50_000,   500_000),
    "Bar or Pub":                    (  30_000,   400_000),
    "Night Club":                    (  50_000,   500_000),
    "Clothing and Accessories":      (  50_000, 2_000_000),
    "Women's Apparel":               (  50_000, 2_000_000),
    "Children's Apparel":            (  50_000,   500_000),
    "Specialty Store":               (  50_000, 1_000_000),
    "Jeweler":                       ( 200_000, 5_000_000),
    "Sporting Goods Store":          (  50_000, 1_500_000),
    "Pharmacy":                      (  20_000,   500_000),
    "Florist":                       (  50_000,   500_000),
    "Hair and Beauty":               ( 100_000, 1_000_000),
    "Barber":                        (  30_000,   150_000),
    "Wellness Center and Services":  ( 100_000, 1_500_000),
    "Therapist":                     ( 100_000, 1_000_000),
    "Fitness-Health Club":           ( 100_000, 1_000_000),
    "Pet Care":                      (  50_000,   500_000),
    "Dentist-Dental Office":         ( 200_000, 2_000_000),
    "Medical Services-Clinics":      (  50_000,   500_000),
    "Hospital":                      ( 100_000, 2_000_000),
    "School":                        (  50_000,   500_000),
    "Language Studies":              (  50_000,   500_000),
    "Training and Development":      ( 100_000, 2_000_000),
    "Convention-Exhibition Center":  ( 100_000, 2_000_000),
    "Car Wash-Detailing":            (  30_000,   300_000),
    "Dry Cleaning and Laundry":      (  20_000,   200_000),
    "Repair Service":                (  30_000,   500_000),
    "Mobile Service Center":         (  30_000,   500_000),
    "Automobile Dealership-New Cars":( 500_000, 5_000_000),
    "Fast Food":                     (  15_000,   100_000),
    "Deli":                          (  20_000,   200_000),
    "Take Out and Delivery Only":    (  20_000,   200_000),
    "Grocery":                       (  50_000,   500_000),
    "Cigar and Tobacco Shop":        (  20_000,   200_000),
    "Vaping Store":                  (  50_000,   500_000),
    "Shoes-Footwear":                (  50_000, 1_500_000),
    "Computer and Software":         ( 100_000, 5_000_000),
    "Mobile Retailer":               (  50_000, 2_000_000),
    "Optical":                       ( 200_000, 2_000_000),
    "Hotel":                         ( 300_000, 3_000_000),
    "Karaoke":                       (  50_000,   500_000),
    "Transportation Service":        (  20_000,   200_000),
    "Wedding Services and Bridal Studio": ( 500_000, 10_000_000),
}

DEFAULT_VOLUME = (1, 5)
DEFAULT_AMOUNT = (50_000, 500_000)

# ──────────────────────────────────────────────────────────────────────────────
# INDONESIAN NATIONAL HOLIDAYS
# ──────────────────────────────────────────────────────────────────────────────

# Official public holidays + cuti bersama declared by the Indonesian government.
# Covers 2025–2026 to match typical simulation date ranges.
ID_NATIONAL_HOLIDAYS: dict[date, str] = {
    # ── 2025 ──────────────────────────────────────────────────────────────────
    date(2025,  1,  1): "Tahun Baru Masehi",
    date(2025,  1, 27): "Isra Mi'raj",
    date(2025,  1, 28): "Cuti Bersama Tahun Baru Imlek",
    date(2025,  1, 29): "Tahun Baru Imlek",
    date(2025,  3, 29): "Hari Suci Nyepi",
    date(2025,  3, 31): "Idul Fitri Hari Ke-1",
    date(2025,  4,  1): "Idul Fitri Hari Ke-2",
    date(2025,  4,  2): "Cuti Bersama Idul Fitri",
    date(2025,  4,  3): "Cuti Bersama Idul Fitri",
    date(2025,  4,  4): "Cuti Bersama Idul Fitri",
    date(2025,  4, 18): "Wafat Isa Almasih",
    date(2025,  5,  1): "Hari Buruh Internasional",
    date(2025,  5, 12): "Hari Raya Waisak",
    date(2025,  5, 29): "Kenaikan Isa Almasih",
    date(2025,  5, 30): "Cuti Bersama Kenaikan Isa Almasih",
    date(2025,  6,  1): "Hari Lahir Pancasila",
    date(2025,  6,  6): "Idul Adha",
    date(2025,  6, 27): "Tahun Baru Islam",
    date(2025,  8, 17): "Hari Kemerdekaan RI",
    date(2025,  9,  5): "Maulid Nabi Muhammad SAW",
    date(2025, 12, 25): "Hari Raya Natal",
    date(2025, 12, 26): "Cuti Bersama Natal",
    # ── 2026 ──────────────────────────────────────────────────────────────────
    date(2026,  1,  1): "Tahun Baru Masehi",
    date(2026,  1, 17): "Isra Mi'raj",
    date(2026,  2, 17): "Tahun Baru Imlek",
    date(2026,  3, 19): "Hari Suci Nyepi",
    date(2026,  3, 20): "Idul Fitri Hari Ke-1",
    date(2026,  3, 21): "Idul Fitri Hari Ke-2",
    date(2026,  3, 23): "Cuti Bersama Idul Fitri",
    date(2026,  3, 24): "Cuti Bersama Idul Fitri",
    date(2026,  4,  3): "Wafat Isa Almasih",
    date(2026,  5,  1): "Hari Buruh Internasional",
    date(2026,  5,  2): "Hari Raya Waisak",
    date(2026,  5, 14): "Kenaikan Isa Almasih",
    date(2026,  5, 27): "Idul Adha",
    date(2026,  6,  1): "Hari Lahir Pancasila",
    date(2026,  6, 17): "Tahun Baru Islam",
    date(2026,  8, 17): "Hari Kemerdekaan RI",
    date(2026,  8, 26): "Maulid Nabi Muhammad SAW",
    date(2026, 12, 25): "Hari Raya Natal",
}

# Categories that CLOSE on national holidays.
# F&B and wellness stay OPEN — they benefit from holiday foot traffic.
# Schools, retail, florists, dentists, and convention centres close.
HOLIDAY_CLOSED_CATEGORIES: frozenset[str] = frozenset({
    "Clothing and Accessories",
    "Women's Apparel",
    "Florist",
    "Dentist-Dental Office",
    "School",
    "Convention-Exhibition Center",
})

# ──────────────────────────────────────────────────────────────────────────────
# HOLIDAY SURGE MULTIPLIERS
# ──────────────────────────────────────────────────────────────────────────────

# Maps each category to a surge group so multipliers can be defined per group
# rather than per individual category.
CATEGORY_SURGE_GROUP: dict[str, str] = {
    "Restaurant":                    "fnb",
    "Casual Dining":                 "fnb",
    "Fine Dining":                   "fnb",
    "Coffee Shop":                   "fnb",
    "Food-Beverage Specialty Store": "fnb",
    "Bakery and Baked Goods Store":  "fnb",
    "Butcher":                       "fnb",
    "Convenience Store":             "fnb",
    "Wine and Liquor":               "fnb",
    "Bar or Pub":                    "fnb",
    "Night Club":                    "events",
    "Clothing and Accessories":      "retail",
    "Women's Apparel":               "retail",
    "Children's Apparel":            "retail",
    "Specialty Store":               "retail",
    "Jeweler":                       "retail",
    "Sporting Goods Store":          "retail",
    "Pharmacy":                      "health",
    "Florist":                       "retail",
    "Hair and Beauty":               "beauty",
    "Barber":                        "beauty",
    "Wellness Center and Services":  "beauty",
    "Therapist":                     "beauty",
    "Fitness-Health Club":           "beauty",
    "Pet Care":                      "retail",
    "Dentist-Dental Office":         "health",
    "Medical Services-Clinics":      "health",
    "Hospital":                      "health",
    "School":                        "education",
    "Language Studies":              "education",
    "Training and Development":      "education",
    "Convention-Exhibition Center":  "events",
    "Car Wash-Detailing":            "retail",
    "Dry Cleaning and Laundry":      "retail",
}

# Each entry: (start_date, end_date, event_label, {group: multiplier})
# Only groups meaningfully affected by the event are listed;
# any group absent from the dict gets multiplier 1.0 (no change).
#
# Groups and their typical behaviour:
#   fnb       — most holidays increase dining out
#   retail    — surges before Eid & Christmas; quiet on religious holidays
#   beauty    — surges before Eid (salon prep); mild boost on long weekends
#   health    — dentists not affected by celebrations; slightly down on holidays
#   education — closed most holidays; effectively 0 on school breaks
#   events    — spikes on national celebrations and long weekends
HOLIDAY_SURGE_PERIODS: list[tuple] = [
    # ── Idul Fitri 2026 (2026-03-20 / 21) ────────────────────────────────────
    # Pre-Lebaran shopping frenzy: H-10 → H-1
    (date(2026, 3, 10), date(2026, 3, 19), "Pre-Idul Fitri",
     {"fnb": 1.5, "retail": 2.8, "beauty": 2.2, "health": 0.7, "education": 0.5}),
    # Post-Lebaran return & family visits: H+3 → H+7
    (date(2026, 3, 24), date(2026, 3, 28), "Post-Idul Fitri",
     {"fnb": 1.6, "retail": 1.3, "beauty": 1.3, "health": 0.8}),

    # ── Idul Adha 2026 (2026-05-27) ──────────────────────────────────────────
    (date(2026, 5, 24), date(2026, 5, 28), "Idul Adha",
     {"fnb": 1.4, "events": 1.2}),

    # ── Hari Lahir Pancasila 2026 (2026-06-01) ────────────────────────────────
    (date(2026, 5, 30), date(2026, 6, 2), "Pancasila Day",
     {"fnb": 1.2, "events": 1.3}),

    # ── Chinese New Year 2026 (2026-02-17) ───────────────────────────────────
    (date(2026, 2, 14), date(2026, 2, 19), "Imlek",
     {"fnb": 1.7, "retail": 1.5, "beauty": 1.4, "events": 1.3}),

    # ── Indonesian Independence Day 2026 (2026-08-17) ─────────────────────────
    (date(2026, 8, 15), date(2026, 8, 19), "HUT RI",
     {"fnb": 1.3, "events": 1.5, "retail": 1.2}),

    # ── Waisak 2026 (2026-05-02) ─────────────────────────────────────────────
    (date(2026, 4, 30), date(2026, 5, 3), "Waisak",
     {"fnb": 1.2, "events": 1.2}),

    # ── Christmas 2026 (2026-12-25) ───────────────────────────────────────────
    (date(2026, 12, 22), date(2026, 12, 28), "Natal",
     {"fnb": 1.5, "retail": 1.7, "beauty": 1.3, "events": 1.6}),

    # ── New Year 2026 → 2027 ─────────────────────────────────────────────────
    (date(2026, 12, 29), date(2027, 1, 2), "Tahun Baru",
     {"fnb": 1.7, "retail": 1.4, "beauty": 1.3, "events": 1.8}),

    # ── New Year 2025 → 2026 ─────────────────────────────────────────────────
    (date(2025, 12, 29), date(2026, 1, 3), "Tahun Baru",
     {"fnb": 1.7, "retail": 1.4, "beauty": 1.3, "events": 1.8}),

    # ── Chinese New Year 2025 (2025-01-29) ───────────────────────────────────
    (date(2025, 1, 25), date(2025, 1, 31), "Imlek",
     {"fnb": 1.7, "retail": 1.5, "beauty": 1.4, "events": 1.3}),

    # ── Idul Fitri 2025 (2025-03-31 / 04-01) ────────────────────────────────
    (date(2025, 3, 21), date(2025, 3, 30), "Pre-Idul Fitri",
     {"fnb": 1.5, "retail": 2.8, "beauty": 2.2, "health": 0.7, "education": 0.5}),
    (date(2025, 4,  3), date(2025, 4,  7), "Post-Idul Fitri",
     {"fnb": 1.6, "retail": 1.3, "beauty": 1.3, "health": 0.8}),

    # ── Christmas 2025 (2025-12-25) ───────────────────────────────────────────
    (date(2025, 12, 22), date(2025, 12, 28), "Natal",
     {"fnb": 1.5, "retail": 1.7, "beauty": 1.3, "events": 1.6}),
]

# ── Pre-closure volume decay ───────────────────────────────────────────────────
# When a merchant has a closed_from date, transaction volume tapers
# in the weeks leading up to closure.  Pairs: (days_to_close, multiplier).
# Evaluated from smallest to largest threshold.
CLOSURE_DECLINE_STEPS: list[tuple[int, float]] = [
    (1,  0.10),   # last day
    (7,  0.25),   # within 1 week
    (14, 0.50),   # 1–2 weeks out
    (30, 0.70),   # 2–4 weeks out
    (60, 0.85),   # 1–2 months out
]

# ──────────────────────────────────────────────────────────────────────────────
# QRIS PROFILES
# ──────────────────────────────────────────────────────────────────────────────

# Probability a given transaction uses QRIS (vs EDC card swipe/tap).
# Everyday F&B/services lean heavily QRIS; luxury goods lean card.
QRIS_PROBABILITY = {
    "Coffee Shop":                   0.70,
    "Food-Beverage Specialty Store": 0.68,
    "Bakery and Baked Goods Store":  0.68,
    "Convenience Store":             0.67,
    "Butcher":                       0.65,
    "Restaurant":                    0.65,
    "Casual Dining":                 0.62,
    "Bar or Pub":                    0.60,
    "Night Club":                    0.58,
    "Florist":                       0.58,
    "Pharmacy":                      0.58,
    "Barber":                        0.58,
    "Hair and Beauty":               0.55,
    "Dry Cleaning and Laundry":      0.55,
    "Car Wash-Detailing":            0.52,
    "Wellness Center and Services":  0.52,
    "Therapist":                     0.50,
    "Fitness-Health Club":           0.50,
    "Medical Services-Clinics":      0.48,
    "Pet Care":                      0.48,
    "Repair Service":                0.48,
    "Mobile Service Center":         0.48,
    "Fine Dining":                   0.45,
    "School":                        0.45,
    "Language Studies":              0.45,
    "Training and Development":      0.42,
    "Convention-Exhibition Center":  0.40,
    "Dentist-Dental Office":         0.35,
    "Hospital":                      0.35,
    "Sporting Goods Store":          0.32,
    "Specialty Store":               0.30,
    "Women's Apparel":               0.28,
    "Children's Apparel":            0.28,
    "Clothing and Accessories":      0.25,
    "Jeweler":                       0.22,
    "Wine and Liquor":               0.30,
}

DEFAULT_QRIS_PROB = 0.45

# Relative weights for QRIS issuer selection.
# Bank QRIS collectively > fintech (BCA mobile banking is the largest).
# Among fintech, GoPay dominates by a wide margin.
QRIS_ISSUER_WEIGHTS = {
    "BCA-QRIS":   30,   # largest bank app user base
    "MDR-QRIS":   12,   # second bank
    "BRI-QRIS":    8,   # strong retail/unbanked reach
    "BNI-QRIS":    7,   # government-linked bank
    "GOPAY":      25,   # fintech leader, clear #1
    "SHOPEEPAY":   8,   # second fintech
    "OVO":         6,   # third
    "DANA":        3,   # fourth
    "LINKAJA":     1,   # smallest share
}
# Bank total ≈ 57 %  |  Fintech total ≈ 43 %  |  GoPay ≈ 60 % of fintech

# ──────────────────────────────────────────────────────────────────────────────
# RESPONSE CODE PROFILES  (ISO 8583)
# ──────────────────────────────────────────────────────────────────────────────

# EDC card response codes — full ISO 8583 set applies
RESPONSE_CODE_POPULATION = ["00", "05", "51", "91", "54", "61"]
RESPONSE_CODE_WEIGHTS    = [  88,    4,    4,    2,    1,    1]

# QRIS response codes — balance is shown before confirmation so the customer
# can never be declined for insufficient funds, limit breach, or card issues.
# Only technical/network failures can cause a QRIS decline, and those are
# automatically reversed by the network (no REFUND record generated in EDC).
QRIS_RESPONSE_CODE_POPULATION = ["00", "91", "05"]
QRIS_RESPONSE_CODE_WEIGHTS    = [ 97,    2,    1]

RESPONSE_MESSAGES = {
    "00": "APPROVED",
    "05": "DECLINED - DO NOT HONOR",
    "51": "DECLINED - INSUFFICIENT FUNDS",
    "91": "DECLINED - CONNECTION TIMEOUT",
    "54": "DECLINED - EXPIRED CARD",
    "61": "DECLINED - EXCEEDS WITHDRAWAL LIMIT",
    "14": "DECLINED - INVALID CARD NUMBER",
}

# ──────────────────────────────────────────────────────────────────────────────
# DEFAULT OPERATING HOURS (fallback when CSV has no hours data)
# ──────────────────────────────────────────────────────────────────────────────

CATEGORY_DEFAULT_HOURS: dict[str, tuple[time, time] | None] = {
    # ── F&B ──────────────────────────────────────────────────────────────────
    "Coffee Shop":                   (time( 7, 0), time(22, 0)),
    "Restaurant":                    (time(10, 0), time(22, 0)),
    "Casual Dining":                 (time(10, 0), time(21, 0)),
    "Fine Dining":                   (time(11, 0), time(22, 0)),
    "Food-Beverage Specialty Store": (time( 9, 0), time(21, 0)),
    "Bakery and Baked Goods Store":  (time( 7, 0), time(20, 0)),
    "Butcher":                       (time( 7, 0), time(17, 0)),
    "Convenience Store":             (time( 7, 0), time(23, 0)),
    "Wine and Liquor":               (time(10, 0), time(21, 0)),
    "Bar or Pub":                    (time(17, 0), time(23, 0)),
    "Night Club":                    (time(20, 0), time(23, 0)),
    # ── Retail ───────────────────────────────────────────────────────────────
    "Clothing and Accessories":      (time(10, 0), time(21, 0)),
    "Women's Apparel":               (time(10, 0), time(21, 0)),
    "Children's Apparel":            (time(10, 0), time(21, 0)),
    "Specialty Store":               (time( 9, 0), time(21, 0)),
    "Jeweler":                       (time(10, 0), time(20, 0)),
    "Sporting Goods Store":          (time( 9, 0), time(21, 0)),
    "Pharmacy":                      (time( 8, 0), time(22, 0)),
    "Florist":                       (time( 9, 0), time(18, 0)),
    # ── Beauty / wellness ────────────────────────────────────────────────────
    "Hair and Beauty":               (time( 9, 0), time(20, 0)),
    "Barber":                        (time( 9, 0), time(20, 0)),
    "Wellness Center and Services":  (time( 9, 0), time(21, 0)),
    "Therapist":                     (time( 9, 0), time(21, 0)),
    "Fitness-Health Club":           (time( 6, 0), time(22, 0)),
    "Pet Care":                      (time( 9, 0), time(18, 0)),
    # ── Health ───────────────────────────────────────────────────────────────
    "Dentist-Dental Office":         (time( 9, 0), time(17, 0)),
    "Medical Services-Clinics":      (time( 8, 0), time(17, 0)),
    "Hospital":                      (time( 8, 0), time(20, 0)),
    # ── Education ────────────────────────────────────────────────────────────
    "School":                        (time( 8, 0), time(16, 0)),
    "Language Studies":              (time( 9, 0), time(20, 0)),
    "Training and Development":      (time( 8, 0), time(17, 0)),
    # ── Services ─────────────────────────────────────────────────────────────
    "Car Wash-Detailing":            (time( 8, 0), time(18, 0)),
    "Dry Cleaning and Laundry":      (time( 8, 0), time(18, 0)),
    "Repair Service":                (time( 9, 0), time(18, 0)),
    "Mobile Service Center":         (time( 9, 0), time(20, 0)),
    "IT and Office Equipment Services": (time( 8, 0), time(17, 0)),
    "Business Service":              (time( 8, 0), time(17, 0)),
    "Consumer Services":             (time( 9, 0), time(18, 0)),
    "Interior and Exterior Design":  (time( 9, 0), time(17, 0)),
    # ── Events / other ───────────────────────────────────────────────────────
    "Convention-Exhibition Center":  (time( 8, 0), time(20, 0)),
    # ── Automotive / misc ────────────────────────────────────────────────────
    "Automobile Dealership-New Cars": (time( 9, 0), time(17, 0)),
    "Tire Repair":                   (time( 8, 0), time(17, 0)),
    # ── Recreation ───────────────────────────────────────────────────────────
    "Billiards-Pool Hall":           (time(14, 0), time(23, 0)),
    "Video Arcade-Game Room":        (time(10, 0), time(22, 0)),
    "Golf Course":                   (time( 6, 0), time(18, 0)),
    # ── Other ────────────────────────────────────────────────────────────────
    "Couriers":                      (time( 8, 0), time(17, 0)),
    "Real Estate Services":          (time( 9, 0), time(17, 0)),
    "Residential Area-Building":     (time( 9, 0), time(17, 0)),
    "Floor and Carpet":              (time( 9, 0), time(18, 0)),
    "Home Improvement-Hardware Store": (time( 8, 0), time(18, 0)),
    "Major Appliance":               (time( 9, 0), time(20, 0)),
    "Office Supply and Services Store": (time( 8, 0), time(17, 0)),
    "Bus Stop":                      None,
    # ── F&B (additional) ─────────────────────────────────────────────────────
    "Fast Food":                     (time( 8, 0), time(22, 0)),
    "Deli":                          (time( 8, 0), time(21, 0)),
    "Take Out and Delivery Only":    (time( 9, 0), time(22, 0)),
    "Grocery":                       (time( 8, 0), time(22, 0)),
    "Cigar and Tobacco Shop":        (time(10, 0), time(22, 0)),
    "Vaping Store":                  (time(10, 0), time(22, 0)),
    # ── Retail (additional) ──────────────────────────────────────────────────
    "Shoes-Footwear":                (time(10, 0), time(21, 0)),
    "Computer and Software":         (time( 9, 0), time(20, 0)),
    "Mobile Retailer":               (time( 9, 0), time(20, 0)),
    "Optical":                       (time( 9, 0), time(17, 0)),
    # ── Hospitality / entertainment ──────────────────────────────────────────
    "Hotel":                         (time( 6, 0), time(23, 0)),
    "Karaoke":                       (time(14, 0), time(23, 0)),
    "Transportation Service":        (time( 7, 0), time(22, 0)),
    "Wedding Services and Bridal Studio": (time(10, 0), time(18, 0)),
}

# ──────────────────────────────────────────────────────────────────────────────
# TIMEZONE
# ──────────────────────────────────────────────────────────────────────────────

WIB = timezone(timedelta(hours=7))   # Waktu Indonesia Barat (UTC+7)

# ── card image colours (GitHub dark palette) ──────────────────────────────────
_C_BG      = "#0d1117"
_C_PANEL   = "#161b22"
_C_BORDER  = "#30363d"
_C_NAME    = "#e6edf3"
_C_LABEL   = "#8b949e"
_C_VALUE   = "#c9d1d9"
_C_ACTIVE  = "#3fb950"
_C_INACTIVE= "#d29922"
_C_SUSPEND = "#f85149"
_C_REASON  = "#58a6ff"
_C_DIVIDER = "#21262d"

_CARD_W    = 620
_PAD       = 28
_LH        = 24   # line height px

# ──────────────────────────────────────────────────────────────────────────────
# REPORT WINDOW CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

WINDOW_DAYS          = 30
REALTIME_ACTIVE_DAYS = 90

# ──────────────────────────────────────────────────────────────────────────────
# INPUT PATH CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

_BATCH_UNIFIED_CSV = INPUT_DIR / "list_edc.csv"
_REALTIME_CSV      = INPUT_DIR / "list_realtime.csv"
