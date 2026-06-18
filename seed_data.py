#!/usr/bin/env python3
"""
seed_data.py — EDC POC database seeder
Reads poi_edc.csv and populates all tables with realistic Indonesian payment data.

Requirements: psycopg2-binary
    pip install psycopg2-binary

Override DB connection via environment variables:
    PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD
"""

import csv
import math
import os
import random
import re
import string
import sys
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
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
DATE_START = date(2026, 5, 1)
DATE_END   = date.today()         # inclusive

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
    "Car Wash-Detailing":            (time( 8, 0), time(18, 0)),
    # ── Recreation ───────────────────────────────────────────────────────────
    "Billiards-Pool Hall":           (time(14, 0), time(23, 0)),
    "Video Arcade-Game Room":        (time(10, 0), time(22, 0)),
    "Golf Course":                   (time( 6, 0), time(18, 0)),
    "Night Club":                    (time(20, 0), time(23, 0)),
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
# UTILITY FUNCTIONS
# ──────────────────────────────────────────────────────────────────────────────

_trace_seq = 0


def next_trace_number(txn_date: date) -> str:
    global _trace_seq
    _trace_seq += 1
    return f"RRN{txn_date.strftime('%Y%m%d')}{_trace_seq:06d}"


def make_approval_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def round_to_thousand(value: int) -> Decimal:
    return Decimal(round(value / 1000) * 1000)


def fraction_to_time(frac_str: str) -> time | None:
    """
    Convert a CSV day-fraction to a time object.
    Uses round(val * 1440) to avoid float truncation errors:
      0.333333... * 1440 = 479.999... → round → 480 → 08:00 (not 07:59).
    """
    s = frac_str.strip()
    if not s:
        return None
    try:
        val = float(s)
    except ValueError:
        return None
    total_minutes = round(val * 24 * 60)
    hours, minutes = divmod(total_minutes, 60)
    if hours >= 24:
        hours, minutes = 23, 59
    return time(hours, minutes)


def get_day_window(row: dict, weekday: int) -> tuple[time, time] | None:
    """
    Return (open_time, close_time) for ISO weekday 0=Monday…6=Sunday.
    Returns None if closed (both fields empty or both '0').
    """
    day_names = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
    day = day_names[weekday]
    open_str  = row.get(f"{day}opening",  "").strip()
    close_str = row.get(f"{day}closing", "").strip()

    if not open_str or not close_str:
        return None
    if open_str == "0" and close_str == "0":
        return None

    open_t  = fraction_to_time(open_str)
    close_t = fraction_to_time(close_str)
    if open_t is None or close_t is None:
        return None

    open_dt  = datetime.combine(date.today(), open_t)
    close_dt = datetime.combine(date.today(), close_t)
    if close_dt <= open_dt:
        return None

    return (open_t, close_t)


def resolve_hours(row: dict, weekday: int, category: str) -> tuple[time, time] | None:
    """Return CSV hours or category-based default."""
    window = get_day_window(row, weekday)
    if window:
        return window
    return CATEGORY_DEFAULT_HOURS.get(category)   # may be None


def random_time_in_window(open_t: time, close_t: time, txn_date: date) -> datetime:
    open_dt   = datetime.combine(txn_date, open_t)
    close_dt  = datetime.combine(txn_date, close_t)
    delta_sec = max(int((close_dt - open_dt).total_seconds()) - 1, 0)
    return open_dt + timedelta(seconds=random.randint(0, delta_sec))


def mask_card_number(prefix: str) -> str:
    """Format: XXXX XX** **** XXXX — first 4 digits and last 4 visible."""
    last4 = f"{random.randint(0, 9999):04d}"
    second_group = f"{prefix[2]}X"
    return f"{prefix} {second_group}** **** {last4}"


# ──────────────────────────────────────────────────────────────────────────────
# DATABASE HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def reset_database(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            TRUNCATE
                transaction_log,
                settlement,
                transactions,
                terminals,
                cards,
                merchants,
                admin_areas
            RESTART IDENTITY CASCADE
        """)
    conn.commit()
    print("      All tables truncated.")


# ──────────────────────────────────────────────────────────────────────────────
# LOAD STATIC REFERENCE DATA
# ──────────────────────────────────────────────────────────────────────────────

def load_acquirers(conn) -> dict[str, int]:
    """Return {bank_code: acquirer_id}. Static data seeded by schema.sql."""
    with conn.cursor() as cur:
        cur.execute("SELECT bank_code, acquirer_id FROM acquirers")
        result = {r[0]: r[1] for r in cur.fetchall()}
    if not result:
        raise RuntimeError("No acquirers found — run schema.sql first.")
    return result


def load_qris_issuers(conn) -> dict[str, int]:
    """Return {issuer_code: qris_issuer_id}. Static data seeded by schema.sql."""
    with conn.cursor() as cur:
        cur.execute("SELECT issuer_code, qris_issuer_id FROM qris_issuers")
        result = {r[0]: r[1] for r in cur.fetchall()}
    if not result:
        raise RuntimeError("No QRIS issuers found — run schema.sql first.")
    return result


# ──────────────────────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────────────
# BATCH XLSX HELPERS
# ──────────────────────────────────────────────────────────────────────────────

_DAY_IDX = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}
_TIME_RE = re.compile(r'(\d{1,2}):(\d{2})')


def _parse_hours_text(text: str) -> dict[int, tuple[time, time] | None]:
    """
    Parse text operating hours to a weekday→(open,close) dict.
    Handles formats like:
      "Monday-Sunday, 07:00-21:00"
      "Monday-Saturday, 08:00-13:00, 16:00-22:00"  → open=08:00, close=22:00
      "Monday-Friday, 08:00-17:00, Saturday-Sunday, 11:30-22:00"
    """
    if not text or not text.strip():
        return {}

    norm = text.strip().lower()
    if "24/7" in norm or norm in ("24 hours", "open 24 hours", "always open"):
        return {wd: (time(0, 0), time(23, 59)) for wd in range(7)}

    schedule: dict[int, tuple[time, time] | None] = {}
    parts = [p.strip() for p in text.split(",")]

    current_days: list[int] = []
    all_times: list[time] = []

    def _flush():
        if current_days and len(all_times) >= 2:
            open_t, close_t = all_times[0], all_times[-1]
            for wd in current_days:
                schedule[wd] = (open_t, close_t)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        time_matches = _TIME_RE.findall(part)

        if time_matches:
            for h, m in time_matches:
                try:
                    all_times.append(time(int(h), int(m)))
                except ValueError:
                    pass
        else:
            _flush()
            current_days = []
            all_times = []

            day_part = re.sub(r'\s*-\s*', '-', part)
            if '-' in day_part:
                halves = day_part.split('-', 1)
                start_idx = _DAY_IDX.get(halves[0].strip().lower())
                end_idx   = _DAY_IDX.get(halves[1].strip().lower())
                if start_idx is not None and end_idx is not None:
                    if end_idx >= start_idx:
                        current_days = list(range(start_idx, end_idx + 1))
                    else:
                        current_days = list(range(start_idx, 7)) + list(range(0, end_idx + 1))
            else:
                idx = _DAY_IDX.get(day_part.strip().lower())
                if idx is not None:
                    current_days = [idx]

    _flush()
    return schedule


def _normalize_city(name: str) -> str:
    """Strip Indonesian administrative prefixes from city names."""
    for prefix in ("Kota ", "Kabupaten ", "Kab. ", "Kab "):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def _rand_closed_2024() -> str:
    """Return a random ISO date string in 2024."""
    d = date(2024, 1, 1) + timedelta(days=random.randint(0, 365))
    return d.isoformat()


def read_batch_xlsx(xlsx_path: Path, batch_type: str) -> list[dict]:
    """
    Read list_new_edc.xlsx (sheet 'new') or list_update_edc.xlsx (sheet 'update')
    and return rows normalised to the internal csv_row format.

    Key internal fields produced:
      name1, displaylatitude, displaylongitude, routinglatitude, routinglongitude,
      primarycategorynm, admin2, admin3, admin4, admin5,
      hno, streetname, postalcode, PHONE, MOBILE,
      _schedule_override (dict[int, tuple[time,time]|None]),
      closed_from (ISO string or ""),
      batch_type, status="ACTIVE"
    """
    try:
        from openpyxl import load_workbook
    except ImportError:
        print(f"      [batch] openpyxl not installed — cannot read {xlsx_path.name}")
        return []

    sheet_name = "new" if batch_type == "new" else "update"
    try:
        wb = load_workbook(str(xlsx_path), read_only=True, data_only=True)
    except Exception as exc:
        print(f"      [batch] Cannot open {xlsx_path.name}: {exc}")
        return []

    if sheet_name not in wb.sheetnames:
        sheet_name = wb.sheetnames[0]
    ws = wb[sheet_name]

    rows_iter = ws.iter_rows(values_only=True)
    raw_headers = next(rows_iter, None)
    if raw_headers is None:
        return []
    headers = [str(h).strip() if h is not None else "" for h in raw_headers]

    result = []
    for raw_row in rows_iter:
        row = {headers[i]: (raw_row[i] if i < len(raw_row) else None) for i in range(len(headers))}

        def _s(key: str, *aliases) -> str:
            for k in (key, *aliases):
                v = row.get(k)
                if v is not None:
                    return str(v).strip()
            return ""

        if batch_type == "new":
            id_val    = _s("supplier_poiid")
            name      = _s("poi_nm")
            lat       = _s("display_point_latitude")
            lon       = _s("display_point_longitude")
            rlat      = _s("routing_latitude")
            rlon      = _s("routing_longitude")
            category  = _s("category")
            hours_raw = _s("operating hours")
            phone     = _s("phone number")
            mobile    = _s("Mobile")
            hno       = _s("house_number")
            street    = _s("street_name")
            postal    = _s("postal_code")
        else:
            id_val    = _s("ID")
            name      = _s("POI name")
            lat       = _s("displaylatitude")
            lon       = _s("displaylongitude")
            rlat      = _s("routing_latitude")
            rlon      = _s("routing_longitude")
            category  = _s("primarycategorynm")
            hours_raw = _s("operating_hours")
            phone     = _s("PHONE")
            mobile    = _s("MOBILE")
            hno       = _s("house_number")
            street    = _s("streetname")
            postal    = _s("postalcode")

        if not name:
            continue

        admin2 = _s("Admin 2")
        admin3 = _normalize_city(_s("Admin 3"))
        admin4 = _s("Admin 4")
        admin5 = _s("Admin 5")

        sched_override = _parse_hours_text(hours_raw) if hours_raw else None

        result.append({
            "name1":             name,
            "displaylatitude":   lat,
            "displaylongitude":  lon,
            "routinglatitude":   rlat,
            "routinglongitude":  rlon,
            "primarycategorynm": category,
            "admin2":            admin2,
            "admin3":            admin3,
            "admin4":            admin4,
            "admin5":            admin5,
            "hno":               hno,
            "streetname":        street,
            "postalcode":        postal,
            "PHONE":             phone,
            "MOBILE":            mobile,
            "_schedule_override": sched_override,
            "_xlsx_id":          id_val,
            "closed_from":       "",
            "batch_type":        f"xlsx-{batch_type}",   # "xlsx-new" or "xlsx-update"
            "status":            "ACTIVE",
        })

    wb.close()

    # Disambiguate duplicate names by appending street (without "Jalan " prefix).
    from collections import Counter as _Counter
    name_counts = _Counter(r["name1"] for r in result)
    for r in result:
        if name_counts[r["name1"]] > 1:
            raw_street = r.get("streetname", "").strip()
            clean = re.sub(r"(?i)^jalan\s+", "", raw_street).strip()
            if clean:
                r["name1"] = f"{r['name1']} {clean}"

    return result


# ──────────────────────────────────────────────────────────────────────────────
# INSERT ADMIN AREAS  (Province → City/Regency → District → Village)
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_admin_tuple(row: dict) -> tuple[str | None, str | None, str | None]:
    """
    Normalise the inconsistent admin2-5 columns in the CSV.

    Two layouts exist in this dataset:
      Layout A: admin3=Province, admin4=City, admin5=District  (most rows)
      Layout B: admin2=Province, admin3=City, admin4=District  (a few rows)

    Returns (province, city, district) — any element may be None if missing.
    """
    a2 = row.get("admin2", "").strip()
    a3 = row.get("admin3", "").strip()
    a4 = row.get("admin4", "").strip()
    a5 = row.get("admin5", "").strip()

    if a2:
        return (a2 or None, a3 or None, a4 or None)
    return (a3 or None, a4 or None, a5 or None)


def insert_admin_areas(conn, csv_rows: list[dict]) -> dict[tuple, int]:
    """
    Build the Province → City/Regency → District hierarchy from CSV admin columns.
    Returns a mapping of (province, city, district) → area_id for the deepest
    available level (used as the merchant FK).

    Structure:
      Level 1 = Province  (Provinsi)
      Level 2 = City/Regency  (Kota/Kabupaten)
      Level 3 = District  (Kecamatan)
      Level 4 = Village  (Kelurahan/Desa) — structure ready, not in CSV data
    """
    # Collect unique tuples present in the CSV
    combos: set[tuple[str | None, str | None, str | None]] = set()
    for row in csv_rows:
        combos.add(_resolve_admin_tuple(row))

    province_ids: dict[str, int] = {}   # name → area_id
    city_ids:     dict[tuple, int] = {} # (province, city) → area_id
    district_ids: dict[tuple, int] = {} # (province, city, district) → area_id

    with conn.cursor() as cur:
        # ── Level 1: provinces ──────────────────────────────────────────────
        provinces = {p for p, c, d in combos if p}
        for prov in sorted(provinces):
            cur.execute(
                """
                INSERT INTO admin_areas (area_name, area_level, parent_id)
                VALUES (%s, 1, NULL)
                ON CONFLICT (area_name, area_level, parent_id) DO UPDATE
                    SET area_name = EXCLUDED.area_name
                RETURNING area_id
                """,
                (prov,),
            )
            province_ids[prov] = cur.fetchone()[0]

        # ── Level 2: cities ─────────────────────────────────────────────────
        cities = {(p, c) for p, c, d in combos if p and c}
        for prov, city in sorted(cities):
            parent = province_ids.get(prov)
            cur.execute(
                """
                INSERT INTO admin_areas (area_name, area_level, parent_id)
                VALUES (%s, 2, %s)
                ON CONFLICT (area_name, area_level, parent_id) DO UPDATE
                    SET area_name = EXCLUDED.area_name
                RETURNING area_id
                """,
                (city, parent),
            )
            city_ids[(prov, city)] = cur.fetchone()[0]

        # ── Level 3: districts ───────────────────────────────────────────────
        for prov, city, dist in sorted(combos):
            if not dist:
                continue
            parent = city_ids.get((prov, city)) or province_ids.get(prov)
            cur.execute(
                """
                INSERT INTO admin_areas (area_name, area_level, parent_id)
                VALUES (%s, 3, %s)
                ON CONFLICT (area_name, area_level, parent_id) DO UPDATE
                    SET area_name = EXCLUDED.area_name
                RETURNING area_id
                """,
                (dist, parent),
            )
            district_ids[(prov, city, dist)] = cur.fetchone()[0]

    conn.commit()

    # Build merchant lookup: (prov, city, dist) → deepest area_id
    result: dict[tuple, int] = {}
    for prov, city, dist in combos:
        if dist and (prov, city, dist) in district_ids:
            result[(prov, city, dist)] = district_ids[(prov, city, dist)]
        elif city and (prov, city) in city_ids:
            result[(prov, city, dist)] = city_ids[(prov, city)]
        elif prov and prov in province_ids:
            result[(prov, city, dist)] = province_ids[prov]

    return result


# ──────────────────────────────────────────────────────────────────────────────
# INSERT MERCHANTS + TERMINALS
# ──────────────────────────────────────────────────────────────────────────────

def insert_merchants_and_terminals(
    conn,
    csv_rows: list[dict],
    acquirer_ids: dict[str, int],
    area_map: dict[tuple, int],
    idx_offset: int = 0,
) -> list[dict]:
    """
    Insert one merchant + one terminal per active CSV row.
    Returns list of info dicts consumed by the transaction generator.
    """
    acquirer_codes = list(acquirer_ids.keys())
    merchant_insert_rows = []
    terminal_meta        = []

    for idx, row in enumerate(csv_rows):
        category      = row.get("primarycategorynm", "").strip()
        mcc           = CATEGORY_TO_MCC.get(category, "5999")
        # Registration date: random within 3–18 months before DATE_START
        reg_date      = (DATE_START - timedelta(days=random.randint(90, 548))).strftime("%Y%m%d")
        serial_number = f"SN-2026-{idx_offset + idx + 1:04d}"
        merchant_code = f"MCH-{mcc}-{reg_date}-{idx_offset + idx + 1:05d}"
        terminal_code = f"TID-{mcc}-{reg_date}-{idx_offset + idx + 1:05d}"

        lat_str = row.get("displaylatitude",  "").strip()
        lon_str = row.get("displaylongitude", "").strip()
        latitude  = float(lat_str)  if lat_str  else None
        longitude = float(lon_str) if lon_str else None

        acquirer_id   = acquirer_ids[random.choice(acquirer_codes)]
        admin_tuple   = _resolve_admin_tuple(row)
        admin_area_id = area_map.get(admin_tuple)

        address = " ".join(filter(None, [
            row.get("hno", "").strip(),
            row.get("streetname", "").strip(),
        ])) or None
        # Denormalised display city: prefer City level, fall back to Province
        city = admin_tuple[1] or admin_tuple[0] or "Jakarta"

        merchant_insert_rows.append((
            row.get("name1", f"Merchant {idx+1}").strip(),
            merchant_code,
            mcc,
            address,
            city,
            admin_area_id,
            latitude,
            longitude,
            acquirer_id,
        ))

        sched_override = row.get("_schedule_override")
        schedule = sched_override if sched_override else {wd: resolve_hours(row, wd, category) for wd in range(7)}

        cf_str     = row.get("closed_from", "")
        if isinstance(cf_str, str):
            cf_str = cf_str.strip()
        else:
            cf_str = ""
        closed_from = date.fromisoformat(cf_str) if cf_str else None

        terminal_meta.append({
            "merchant_name": row.get("name1", f"Merchant {idx+1}").strip(),
            "merchant_code": merchant_code,
            "terminal_code": terminal_code,
            "serial_number": serial_number,
            "model":         random.choice(TERMINAL_MODELS),
            "category":      category,
            "schedule":      schedule,
            "closed_from":   closed_from,
        })

    # Insert merchants, capture generated UUIDs (fetch=True collects all pages)
    with conn.cursor() as cur:
        returned = execute_values(
            cur,
            """
            INSERT INTO merchants
                (merchant_name, merchant_code, mcc_code, address, city,
                 admin_area_id, latitude, longitude, acquirer_id)
            VALUES %s
            RETURNING merchant_id, merchant_code
            """,
            merchant_insert_rows,
            page_size=200,
            fetch=True,
        )
        merchant_code_to_uuid = {r[1]: r[0] for r in returned}

    # Insert terminals, capture generated UUIDs (fetch=True collects all pages)
    with conn.cursor() as cur:
        returned = execute_values(
            cur,
            """
            INSERT INTO terminals (merchant_id, terminal_code, serial_number, model)
            VALUES %s
            RETURNING terminal_id, terminal_code
            """,
            [
                (
                    merchant_code_to_uuid[m["merchant_code"]],
                    m["terminal_code"],
                    m["serial_number"],
                    m["model"],
                )
                for m in terminal_meta
            ],
            page_size=200,
            fetch=True,
        )
        terminal_code_to_uuid = {r[1]: r[0] for r in returned}

    conn.commit()

    # Attach resolved UUIDs back to the info dicts
    for m in terminal_meta:
        m["merchant_id"] = merchant_code_to_uuid[m["merchant_code"]]
        m["terminal_id"] = terminal_code_to_uuid[m["terminal_code"]]

    return terminal_meta


# ──────────────────────────────────────────────────────────────────────────────
# INSERT CARDS
# ──────────────────────────────────────────────────────────────────────────────

def insert_cards(conn, count: int = 300) -> list[int]:
    """Generate synthetic masked cards. Returns list of card_ids."""
    rows = []
    for _ in range(count):
        brand     = random.choice(CARD_BRANDS)
        prefix    = random.choice(CARD_PREFIXES[brand])
        card_type = random.choices(CARD_TYPES, weights=[40, 50, 10])[0]
        bank      = random.choice(ISSUING_BANKS)
        exp_month = random.randint(1, 12)
        exp_year  = random.randint(2026, 2030)
        rows.append((
            mask_card_number(prefix),
            card_type,
            brand,
            bank,
            f"{exp_month:02d}/{exp_year}",
        ))

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO cards (card_number_masked, card_type, card_brand, issuing_bank, expiry_date)
            VALUES %s
            RETURNING card_id
            """,
            rows,
            page_size=300,
        )
        card_ids = [r[0] for r in cur.fetchall()]
    conn.commit()
    return card_ids


# ──────────────────────────────────────────────────────────────────────────────
# VOLUME MULTIPLIER HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _get_holiday_multiplier(txn_date: date, category: str) -> float:
    """
    Return a volume multiplier for holiday/event surge periods.
    Only categories whose surge group appears in the period's dict are affected;
    all others return 1.0 (no change).
    """
    group = CATEGORY_SURGE_GROUP.get(category)
    if group is None:
        return 1.0
    for start, end, _label, mult_map in HOLIDAY_SURGE_PERIODS:
        if start <= txn_date <= end:
            return mult_map.get(group, 1.0)
    return 1.0


def _get_closure_multiplier(txn_date: date, closed_from: date | None) -> float:
    """
    Return a volume multiplier based on how many days until permanent closure.
    Returns 0.0 on or after the closure date (caller should skip the day).
    """
    if closed_from is None:
        return 1.0
    days_left = (closed_from - txn_date).days
    if days_left <= 0:
        return 0.0
    for threshold, factor in CLOSURE_DECLINE_STEPS:
        if days_left <= threshold:
            return factor
    return 1.0


# ──────────────────────────────────────────────────────────────────────────────
# TRANSACTION GENERATION
# ──────────────────────────────────────────────────────────────────────────────

def generate_and_insert_transactions(
    conn,
    merchants_info: list[dict],
    card_ids: list[int],
    qris_issuer_ids: dict[str, int],
    start_date: date | None = None,
    end_date: date | None = None,
) -> None:
    """
    For each merchant × each day in start_date..end_date (defaults to DATE_START..DATE_END):
      - Determine open window from schedule
      - Generate N transactions (volume per category)
      - ~85% SALE, ~3% REFUND, plus ~2% VOID companions for approved SALEs
      - Split EDC_CARD / QRIS per category probability
      - Insert in batches; build settlement + audit log records
    """
    qris_codes   = list(QRIS_ISSUER_WEIGHTS.keys())
    qris_weights = [QRIS_ISSUER_WEIGHTS[c] for c in qris_codes]
    qris_id_list = [qris_issuer_ids[c] for c in qris_codes]

    _start = start_date if start_date is not None else DATE_START
    _end   = end_date   if end_date   is not None else DATE_END

    date_range = [
        _start + timedelta(days=i)
        for i in range((_end - _start).days + 1)
    ]

    batch_counter = 1
    total_inserted = 0

    for info in merchants_info:
        category = info["category"]

        if category == "Bus Stop":
            continue  # no EDC terminal at bus stops

        m_id     = info["merchant_id"]
        t_id     = info["terminal_id"]
        schedule = info["schedule"]

        vol_min, vol_max = VOLUME_PROFILE.get(category, DEFAULT_VOLUME)
        amt_min, amt_max = AMOUNT_RANGE.get(category, DEFAULT_AMOUNT)
        qris_prob        = QRIS_PROBABILITY.get(category, DEFAULT_QRIS_PROB)
        closed_from      = info.get("closed_from")

        for txn_date in date_range:
            if closed_from and txn_date >= closed_from:
                continue  # permanently closed from this date

            weekday = txn_date.weekday()
            window  = schedule.get(weekday)
            if window is None:
                continue  # closed this weekday

            if txn_date in ID_NATIONAL_HOLIDAYS and category in HOLIDAY_CLOSED_CATEGORIES:
                continue  # closed for national holiday

            holiday_mult = _get_holiday_multiplier(txn_date, category)
            closure_mult = _get_closure_multiplier(txn_date, closed_from)

            open_t, close_t = window

            # For today: cap the close time to now so we never write future timestamps.
            if txn_date == date.today():
                now_local = datetime.now().time()
                if now_local <= open_t:
                    continue  # merchant hasn't opened yet
                if now_local < close_t:
                    close_t = now_local

            n_txns = max(1, int(random.randint(vol_min, vol_max) * holiday_mult * closure_mult))
            batch_number     = f"{batch_counter:03d}"
            batch_counter   += 1

            # Pre-sort timestamps to mimic sequential receipt flow
            timestamps = sorted(
                random_time_in_window(open_t, close_t, txn_date)
                for _ in range(n_txns)
            )

            txn_rows = []
            settle_sales_count   = 0
            settle_sales_amount  = Decimal("0")
            settle_refund_count  = 0
            settle_refund_amount = Decimal("0")

            for txn_time in timestamps:
                is_qris = random.random() < qris_prob
                if is_qris:
                    qris_id = random.choices(qris_id_list, weights=qris_weights)[0]
                    card_id = None
                    channel = "QRIS"
                else:
                    card_id = random.choice(card_ids)
                    qris_id = None
                    channel = "EDC_CARD"

                # QRIS never produces REFUND records — failed QRIS payments are
                # reversed automatically by the network without an EDC entry.
                tx_type = "SALE"
                if not is_qris and random.random() < 0.03:
                    tx_type = "REFUND"

                amount  = round_to_thousand(random.randint(amt_min, amt_max))

                if tx_type == "REFUND":
                    rc, status, appr = "00", "APPROVED", make_approval_code()
                else:
                    if is_qris:
                        rc = random.choices(QRIS_RESPONSE_CODE_POPULATION, weights=QRIS_RESPONSE_CODE_WEIGHTS)[0]
                    else:
                        rc = random.choices(RESPONSE_CODE_POPULATION, weights=RESPONSE_CODE_WEIGHTS)[0]
                    status = "APPROVED" if rc == "00" else "DECLINED"
                    appr   = make_approval_code() if rc == "00" else None

                settled = (rc == "00") and (txn_date < date.today())
                trace   = next_trace_number(txn_date)

                txn_rows.append((
                    trace, t_id, m_id,
                    card_id, qris_id, channel,
                    tx_type, float(amount), "IDR",
                    rc, RESPONSE_MESSAGES.get(rc, ""), appr,
                    status, batch_number, txn_time, settled,
                ))

                if tx_type == "SALE" and status == "APPROVED":
                    settle_sales_count  += 1
                    settle_sales_amount += amount
                elif tx_type == "REFUND" and status == "APPROVED":
                    settle_refund_count  += 1
                    settle_refund_amount += amount

            # Bulk-insert the day's transactions
            inserted_ids = _insert_transactions(conn, txn_rows)
            total_inserted += len(inserted_ids)

            # Generate VOID companions for ~2% of approved SALEs
            void_count = _insert_voids(conn, inserted_ids, m_id, t_id, batch_number, txn_date)
            total_inserted += void_count

            # Audit log (REQUEST + RESPONSE per transaction)
            _insert_logs(conn, inserted_ids)

            # Settlement summary for this merchant-day
            _upsert_settlement(
                conn, m_id, t_id, batch_number, txn_date,
                settle_sales_count,   settle_sales_amount,
                settle_refund_count,  settle_refund_amount,
            )

    print(f"      {total_inserted:,} transactions inserted.")


def _insert_transactions(conn, rows: list) -> list[int]:
    """Bulk-insert transaction rows; return list of transaction_ids."""
    if not rows:
        return []
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO transactions
                (trace_number, terminal_id, merchant_id,
                 card_id, qris_issuer_id, payment_channel,
                 transaction_type, amount, currency,
                 response_code, response_message, approval_code,
                 transaction_status, batch_number, transaction_time, settled_flag)
            VALUES %s
            RETURNING transaction_id
            """,
            rows,
            page_size=500,
        )
        ids = [r[0] for r in cur.fetchall()]
    conn.commit()
    return ids


def _insert_voids(
    conn,
    txn_ids: list[int],
    merchant_id,
    terminal_id,
    batch_number: str,
    txn_date: date,
) -> int:
    """
    For ~2% of approved SALEs in txn_ids:
      1. Insert a VOID companion row (timestamped a few minutes later)
      2. Update the original SALE to REVERSED
    Returns the number of VOID rows inserted.
    """
    if not txn_ids:
        return 0

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT transaction_id, card_id, qris_issuer_id,
                   payment_channel, amount, transaction_time
            FROM   transactions
            WHERE  transaction_id    = ANY(%s)
              AND  transaction_type   = 'SALE'
              AND  transaction_status = 'APPROVED'
            """,
            (txn_ids,),
        )
        candidates = cur.fetchall()

    void_rows     = []
    reversed_ids  = []

    for txn_id, card_id, qris_id, channel, amount, txn_time in candidates:
        if random.random() > 0.02:
            continue
        void_time = txn_time + timedelta(minutes=random.randint(1, 5))
        void_rows.append((
            next_trace_number(txn_date),
            terminal_id, merchant_id,
            card_id, qris_id, channel,
            "VOID", float(amount), "IDR",
            "00", "APPROVED", make_approval_code(),
            "VOIDED", batch_number, void_time, False,
        ))
        reversed_ids.append(txn_id)

    if not void_rows:
        return 0

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO transactions
                (trace_number, terminal_id, merchant_id,
                 card_id, qris_issuer_id, payment_channel,
                 transaction_type, amount, currency,
                 response_code, response_message, approval_code,
                 transaction_status, batch_number, transaction_time, settled_flag)
            VALUES %s
            """,
            void_rows,
            page_size=200,
        )
        cur.execute(
            """
            UPDATE transactions
            SET    transaction_status = 'REVERSED', settled_flag = FALSE
            WHERE  transaction_id = ANY(%s)
            """,
            (reversed_ids,),
        )
    conn.commit()
    return len(void_rows)


def _insert_logs(conn, txn_ids: list[int]) -> None:
    """Insert REQUEST + RESPONSE audit entries for the given transaction IDs."""
    if not txn_ids:
        return

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT transaction_id, trace_number, card_id, qris_issuer_id,
                   payment_channel, amount, response_code
            FROM   transactions
            WHERE  transaction_id = ANY(%s)
            """,
            (txn_ids,),
        )
        rows = cur.fetchall()

    log_rows = []
    for txn_id, trace, card_id, qris_id, channel, amount, rc in rows:
        ref = f'"pan_ref":"{card_id}"' if channel == "EDC_CARD" else f'"qris_ref":"{qris_id}"'
        req  = f'{{"mti":"0200","trace":"{trace}","amount":"{int(amount)}","channel":"{channel}",{ref}}}'
        resp = (
            f'{{"mti":"0210","trace":"{trace}","rc":"{rc}"'
            + (f',"approval":"{make_approval_code()}"' if rc == "00" else "")
            + "}}"
        )
        log_rows.append((txn_id, "REQUEST",  req))
        log_rows.append((txn_id, "RESPONSE", resp))

    with conn.cursor() as cur:
        execute_values(
            cur,
            "INSERT INTO transaction_log (transaction_id, log_type, raw_message) VALUES %s",
            log_rows,
            page_size=1000,
        )
    conn.commit()


def _upsert_settlement(
    conn,
    merchant_id,
    terminal_id,
    batch_number: str,
    settlement_date: date,
    sales_count: int,
    sales_amount: Decimal,
    refund_count: int,
    refund_amount: Decimal,
) -> None:
    net    = sales_amount - refund_amount
    status = "SETTLED" if settlement_date < date.today() else "PENDING"
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO settlement
                (merchant_id, terminal_id, batch_number, settlement_date,
                 total_sales_count, total_sales_amount,
                 total_refund_count, total_refund_amount,
                 net_amount, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (merchant_id, terminal_id, settlement_date)
            DO UPDATE SET
                total_sales_count   = EXCLUDED.total_sales_count,
                total_sales_amount  = EXCLUDED.total_sales_amount,
                total_refund_count  = EXCLUDED.total_refund_count,
                total_refund_amount = EXCLUDED.total_refund_amount,
                net_amount          = EXCLUDED.net_amount,
                status              = EXCLUDED.status
            """,
            (
                merchant_id, terminal_id, batch_number, settlement_date,
                sales_count,  float(sales_amount),
                refund_count, float(refund_amount),
                float(net),   status,
            ),
        )
    conn.commit()


# ──────────────────────────────────────────────────────────────────────────────
# LOAD FROM DB  (used by --purge to skip re-inserting reference rows)
# ──────────────────────────────────────────────────────────────────────────────

def load_merchants_from_db(conn, csv_rows: list[dict]) -> list[dict]:
    """
    Re-build the merchants_info list from existing DB rows + CSV schedule data.
    Matches by merchant_name so the correct operating hours are applied.
    """
    # Build a name → (category, schedule) lookup from the CSV
    csv_schedule: dict[str, dict] = {}
    for row in csv_rows:
        name     = row.get("name1", "").strip()
        category = row.get("primarycategorynm", "").strip()
        if not name:
            continue
        sched_override = row.get("_schedule_override")
        schedule = sched_override if sched_override else {wd: resolve_hours(row, wd, category) for wd in range(7)}
        cf_raw = row.get("closed_from", "")
        cf_str = cf_raw.strip() if isinstance(cf_raw, str) else ""
        bt      = row.get("batch_type", "").strip()
        xlsx_id = row.get("_xlsx_id", "")
        csv_schedule[name] = {
            "category":    category,
            "schedule":    schedule,
            "closed_from": date.fromisoformat(cf_str) if cf_str else None,
            "batch_type":  bt if bt else None,
            "_xlsx_id":    xlsx_id if xlsx_id else None,
        }

    with conn.cursor() as cur:
        cur.execute("""
            SELECT m.merchant_id, m.merchant_name, m.merchant_code, m.mcc_code,
                   t.terminal_id, t.terminal_code, t.serial_number, t.model
            FROM   merchants m
            JOIN   terminals t ON t.merchant_id = m.merchant_id
        """)
        db_rows = cur.fetchall()

    # Reverse MCC lookup for fallback schedule when merchant isn't in csv_rows
    _mcc_to_cat = {v: k for k, v in CATEGORY_TO_MCC.items()}

    result = []
    for merchant_id, merchant_name, merchant_code, mcc_code, terminal_id, terminal_code, serial_number, model in db_rows:
        sched = csv_schedule.get(merchant_name)
        if sched is None:
            # Batch xlsx merchant not in csv_rows — build default schedule from MCC
            cat         = _mcc_to_cat.get(mcc_code, "")
            default_hrs = CATEGORY_DEFAULT_HOURS.get(cat)
            sched = {
                "category":    cat,
                "schedule":    {wd: default_hrs for wd in range(7)},
                "closed_from": None,
                "batch_type":  None,
            }
        result.append({
            "merchant_id":   merchant_id,
            "merchant_name": merchant_name,
            "merchant_code": merchant_code,
            "mcc_code":      mcc_code,
            "terminal_id":   terminal_id,
            "terminal_code": terminal_code,
            "serial_number": serial_number,
            "model":         model,
            "category":      sched.get("category", ""),
            "schedule":      sched.get("schedule", {}),
            "closed_from":   sched.get("closed_from"),
            "batch_type":    sched.get("batch_type"),
            "_xlsx_id":      sched.get("_xlsx_id"),
        })
    return result


def filter_new_csv_rows(conn, csv_rows: list[dict]) -> list[dict]:
    """Return only rows whose name1 is not already in the merchants table."""
    with conn.cursor() as cur:
        cur.execute("SELECT merchant_name FROM merchants")
        existing = {r[0] for r in cur.fetchall()}
    return [r for r in csv_rows if r.get("name1", "").strip() not in existing]


def get_merchant_idx_offset(conn) -> int:
    """Highest sequence number already embedded in merchant_code (5-digit suffix)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COALESCE(MAX(CAST(RIGHT(merchant_code, 5) AS INTEGER)), 0) FROM merchants"
        )
        return cur.fetchone()[0]


def load_cards_from_db(conn) -> list[int]:
    """Return existing card_ids from the DB."""
    with conn.cursor() as cur:
        cur.execute("SELECT card_id FROM cards")
        return [r[0] for r in cur.fetchall()]


def get_append_start_date(conn) -> date | None:
    """Return the day after the latest transaction date already in the DB, or None if empty."""
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(transaction_time::date) FROM transactions")
        last_date = cur.fetchone()[0]
    return (last_date + timedelta(days=1)) if last_date else None


def reset_trace_seq(conn) -> None:
    """Advance the global trace-seq counter past all existing trace numbers to avoid collisions."""
    global _trace_seq
    with conn.cursor() as cur:
        # Extract the full numeric suffix after 'RRN' + 8-char date (positions 1-11)
        cur.execute(
            "SELECT COALESCE(MAX(CAST(SUBSTRING(trace_number FROM 12) AS BIGINT)), 0) FROM transactions"
        )
        _trace_seq = cur.fetchone()[0]


# ──────────────────────────────────────────────────────────────────────────────
# DATE-RANGE PURGE  (delete only the seeded date window, keep static tables)
# ──────────────────────────────────────────────────────────────────────────────

def purge_date_range(conn) -> None:
    """
    Delete all transaction data for DATE_START..DATE_END without touching
    merchants, terminals, cards, admin_areas, or reference tables.
    Useful for re-seeding a date range without a full reset.
    """
    start_ts = datetime.combine(DATE_START, time.min)
    end_ts   = datetime.combine(DATE_END,   time.max)

    with conn.cursor() as cur:
        cur.execute("""
            DELETE FROM transaction_log
            WHERE transaction_id IN (
                SELECT transaction_id FROM transactions
                WHERE transaction_time BETWEEN %s AND %s
            )
        """, (start_ts, end_ts))
        logs_deleted = cur.rowcount

        cur.execute("""
            DELETE FROM transactions
            WHERE transaction_time BETWEEN %s AND %s
        """, (start_ts, end_ts))
        txn_deleted = cur.rowcount

        cur.execute("""
            DELETE FROM settlement
            WHERE settlement_date BETWEEN %s AND %s
        """, (DATE_START, DATE_END))
        settle_deleted = cur.rowcount

    conn.commit()
    print(f"      Purged {txn_deleted:,} transactions, "
          f"{logs_deleted:,} log entries, "
          f"{settle_deleted:,} settlement rows "
          f"({DATE_START} – {DATE_END}).")


# ──────────────────────────────────────────────────────────────────────────────
# PRUNE CLOSED MERCHANTS  (remove data on/after each merchant's closed_from date)
# ──────────────────────────────────────────────────────────────────────────────

def prune_closed_merchants(conn, csv_rows: list[dict]) -> None:
    """
    For every merchant in the CSV that has a non-empty closed_from date,
    delete all transaction_log / transactions / settlement rows on or after
    that date.  Merchant, terminal, card, and admin-area rows are untouched.
    """
    closure_map: dict[str, date] = {}
    for row in csv_rows:
        name   = row.get("name1", "").strip()
        cf_str = row.get("closed_from", "").strip()
        if name and cf_str:
            try:
                closure_map[name] = date.fromisoformat(cf_str)
            except ValueError:
                print(f"      WARNING: invalid closed_from '{cf_str}' for '{name}' — skipped.")

    if not closure_map:
        print("      No closed_from dates found in CSV — nothing to prune.")
        return

    with conn.cursor() as cur:
        cur.execute("SELECT merchant_name, merchant_id FROM merchants")
        db_map = {name: mid for name, mid in cur.fetchall()}

    total_txn = total_log = total_settle = 0

    for name, closed_from in sorted(closure_map.items(), key=lambda x: x[1]):
        m_id = db_map.get(name)
        if m_id is None:
            print(f"      WARNING: '{name}' not found in DB — skipped.")
            continue

        close_ts = datetime.combine(closed_from, time.min)
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM transaction_log
                WHERE transaction_id IN (
                    SELECT transaction_id FROM transactions
                    WHERE  merchant_id      = %s
                      AND  transaction_time >= %s
                )
            """, (m_id, close_ts))
            logs_del = cur.rowcount

            cur.execute("""
                DELETE FROM transactions
                WHERE merchant_id      = %s
                  AND transaction_time >= %s
            """, (m_id, close_ts))
            txn_del = cur.rowcount

            cur.execute("""
                DELETE FROM settlement
                WHERE merchant_id    = %s
                  AND settlement_date >= %s
            """, (m_id, closed_from))
            settle_del = cur.rowcount

        conn.commit()
        total_txn    += txn_del
        total_log    += logs_del
        total_settle += settle_del

        print(f"      {name[:38]:<38}  closed {closed_from}"
              f"  → -{txn_del:,} txn  -{logs_del:,} log  -{settle_del:,} settle")

    print(f"\n      Total: -{total_txn:,} transactions, "
          f"-{total_log:,} log entries, "
          f"-{total_settle:,} settlement rows.")


# ──────────────────────────────────────────────────────────────────────────────
# MERCHANT STATUS REPORT
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


def _load_font(size: int):
    """Try Consolas → Courier New → Pillow default."""
    from PIL import ImageFont
    for path in [
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/cour.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            pass
    return ImageFont.load_default()


def _save_card_jpeg(
    merchant_name: str,
    status: str,
    confidence: float,
    last_txn_fmt: str,
    ago_str: str,
    c24h: int, c7d: int, c30d: int,
    qris_30d: int, edc_30d: int,
    active_days: int, window_days: int,
    activity_ratio: float, max_gap: int,
    reasons: list[str],
    now_wib,
    output_dir: Path,
    seq: int,
) -> "Path | None":
    """Render a styled JPEG activity card for one merchant. Returns the saved path."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    font_sm  = _load_font(13)
    font_md  = _load_font(15)
    font_lg  = _load_font(18)

    status_colour = _C_ACTIVE if status == "ACTIVE" else _C_INACTIVE

    # ── compute card height dynamically ───────────────────────────────────────
    n_lines  = 6                     # name + 5 data rows
    n_reason = len(reasons)
    height   = _PAD + _LH + 6 + _LH + (_LH * n_lines) + 10 + (_LH * n_reason) + _PAD + 20

    img  = Image.new("RGB", (_CARD_W, max(height, 240)), _C_BG)
    draw = ImageDraw.Draw(img)

    # outer panel
    draw.rounded_rectangle([8, 8, _CARD_W - 8, height - 8], radius=10,
                            fill=_C_PANEL, outline=_C_BORDER, width=1)

    y = _PAD

    # merchant name
    draw.text((_PAD, y), merchant_name, font=font_lg, fill=_C_NAME)
    y += _LH + 6

    # thin divider
    draw.line([_PAD, y, _CARD_W - _PAD, y], fill=_C_DIVIDER, width=1)
    y += 8

    def row(label: str, value: str, value_colour: str = _C_VALUE) -> None:
        nonlocal y
        draw.text((_PAD, y), f"{label:<14}", font=font_md, fill=_C_LABEL)
        draw.text((_PAD + 14 * 9, y), value, font=font_md, fill=value_colour)
        y += _LH

    row("STATUS",        f"{status}   (confidence {confidence:.3f})", status_colour)
    row("last_txn",      f"{last_txn_fmt}  ({ago_str})")
    row("24h / 7d / 30d", f"{c24h}  /  {c7d}  /  {c30d}")
    row("channel split", f"QRIS {qris_30d}   |   EDC {edc_30d}")
    row("active days",   f"{active_days}/{window_days}  (ratio {activity_ratio}, max gap {max_gap}d)")

    if reasons:
        y += 4
        draw.line([_PAD, y, _CARD_W - _PAD, y], fill=_C_DIVIDER, width=1)
        y += 8
        for r in reasons:
            draw.text((_PAD, y), f"  -  {r}", font=font_sm, fill=_C_REASON)
            y += _LH

    # footer timestamp
    y += 6
    footer = f"Generated {now_wib.strftime('%Y-%m-%dT%H:%M:%S%z')}"
    draw.text((_PAD, y), footer, font=font_sm, fill=_C_BORDER)

    # save
    safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in merchant_name)
    fname = output_dir / f"{seq:02d}_{safe_name[:40].strip()}.jpg"
    img.save(fname, "JPEG", quality=92)
    return fname


def _save_excel_report(
    records: list[tuple[int, str, str, "Path | None"]],
    output_dir: Path,
    now_wib,
) -> "Path | None":
    """
    Write merchant_activity_report.xlsx to output_dir.
    records = [(seq, poi_name, last_signal_str, jpeg_path), ...]
    """
    try:
        from openpyxl import Workbook
        from openpyxl.drawing.image import Image as XLImage
        from openpyxl.styles import Font, Alignment, PatternFill
    except ImportError:
        print("      [excel] openpyxl not installed — skipping Excel export")
        return None

    wb = Workbook()
    ws = wb.active
    ws.title = "Merchant Activity"

    HDR_FILL = PatternFill("solid", fgColor="1E2A3A")
    HDR_FONT = Font(bold=True, color="FFFFFF", size=11)
    HDR_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)

    headers    = ["#",  "POI Name", "Last Signal Update",  "Proof (IMG)"]
    col_widths = [4,    36,         28,                     48          ]

    ws.row_dimensions[1].height = 28
    for col_idx, (h, w) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font      = HDR_FONT
        cell.fill      = HDR_FILL
        cell.alignment = HDR_ALIGN
        ws.column_dimensions[cell.column_letter].width = w

    IMG_W  = 320   # pixels in Excel
    IMG_H  = 160   # pixels in Excel
    ROW_H  = 122   # row height in points (≈ 163px @ 96 dpi)

    CTR = Alignment(horizontal="center", vertical="center")
    MID = Alignment(vertical="center", wrap_text=True)

    for row_idx, (seq_n, name, last_signal, jpeg_path) in enumerate(records, start=2):
        ws.row_dimensions[row_idx].height = ROW_H
        ws.cell(row=row_idx, column=1, value=seq_n).alignment    = CTR
        ws.cell(row=row_idx, column=2, value=name).alignment     = MID
        ws.cell(row=row_idx, column=3, value=last_signal).alignment = CTR
        if jpeg_path and Path(jpeg_path).exists():
            xl_img        = XLImage(str(jpeg_path))
            xl_img.width  = IMG_W
            xl_img.height = IMG_H
            ws.add_image(xl_img, f"D{row_idx}")

    xlsx_path = output_dir / "merchant_activity_report.xlsx"
    wb.save(xlsx_path)
    return xlsx_path


def _save_batch_excel_report(
    new_records:    list,
    update_records: list,
    output_dir: Path,
    now_wib,
) -> "Path | None":
    """Two-sheet Excel (NEW / UPDATE) for batch merchants only."""
    try:
        from openpyxl import Workbook
        from openpyxl.drawing.image import Image as XLImage
        from openpyxl.styles import Font, Alignment, PatternFill
    except ImportError:
        return None

    wb = Workbook()

    HDR_FILL  = PatternFill("solid", fgColor="1E2A3A")
    HDR_FONT  = Font(bold=True, color="FFFFFF", size=11)
    HDR_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)
    headers    = ["#", "ID", "POI Name", "Last Signal Update", "Proof (IMG)"]
    col_widths = [4, 36, 36, 28, 48]
    IMG_W, IMG_H, ROW_H = 320, 160, 122

    def _write_sheet(ws, records, sheet_title):
        ws.title = sheet_title
        ws.row_dimensions[1].height = 28
        for col_idx, (h, w) in enumerate(zip(headers, col_widths), start=1):
            cell = ws.cell(row=1, column=col_idx, value=h)
            cell.font = HDR_FONT
            cell.fill = HDR_FILL
            cell.alignment = HDR_ALIGN
            ws.column_dimensions[cell.column_letter].width = w
        CTR = Alignment(horizontal="center", vertical="center")
        MID = Alignment(vertical="center", wrap_text=True)
        for row_idx, (seq_n, name, last_signal, jpeg_path, xlsx_id) in enumerate(records, start=2):
            ws.row_dimensions[row_idx].height = ROW_H
            ws.cell(row=row_idx, column=1, value=seq_n).alignment    = CTR
            ws.cell(row=row_idx, column=2, value=xlsx_id).alignment  = MID
            ws.cell(row=row_idx, column=3, value=name).alignment     = MID
            ws.cell(row=row_idx, column=4, value=last_signal).alignment = CTR
            if jpeg_path and Path(jpeg_path).exists():
                xl_img        = XLImage(str(jpeg_path))
                xl_img.width  = IMG_W
                xl_img.height = IMG_H
                ws.add_image(xl_img, f"E{row_idx}")

    ws_new = wb.active
    _write_sheet(ws_new, new_records, "NEW")
    ws_upd = wb.create_sheet()
    _write_sheet(ws_upd, update_records, "UPDATE")

    xlsx_path = output_dir / "batch_activity_report.xlsx"
    wb.save(xlsx_path)
    return xlsx_path


def _format_ago(hours_ago: float) -> str:
    """Format an elapsed-hours value as 'Xh ago', 'Xd ago', or 'X.Xyr ago'."""
    if hours_ago < 24:
        return f"{hours_ago:.1f}h ago"
    if hours_ago < 24 * 365:
        return f"{hours_ago / 24:.0f}d ago"
    return f"{hours_ago / (24 * 365.25):.1f}yr ago"


def generate_merchant_status_report(conn, merchants_info: list[dict]) -> None:
    """
    Print a live-signal activity health card for every seeded merchant,
    modelled on the card shown in the product spec.

    Reference "now" is end-of-day on DATE_END (the last seeded day).
    Windows:
      24h  = last 24 h before reference time
       7d  = DATE_END minus 6 days  (7 calendar days inclusive)
      30d  = DATE_END minus 29 days (30 calendar days inclusive)
    """
    now_wib        = datetime.now(WIB)
    end_of_data    = datetime.combine(DATE_END, time(23, 59, 59)).replace(tzinfo=WIB)
    # Use end-of-DATE_END when seeded data extends past the current clock
    # (transactions near closing time today would otherwise show negative hours).
    ref_time       = max(now_wib, end_of_data)
    window_30d     = (DATE_END - timedelta(days=29))
    window_7d      = (DATE_END - timedelta(days=6))
    window_24h     = datetime.combine(DATE_END, time(23, 59, 59)).replace(tzinfo=WIB) - timedelta(hours=24)
    WINDOW_DAYS    = 30

    output_dir = Path(__file__).parent / "reports" / DATE_END.strftime("%Y%m%d")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 62)
    print("  MERCHANT ACTIVITY REPORT")
    print(f"  Loaded at : {now_wib.strftime('%Y-%m-%dT%H:%M:%S%z')}  (WIB UTC+7)")
    print(f"  Data range: {DATE_START} – {DATE_END}")
    print(f"  Output    : {output_dir}")
    print("=" * 62)

    seq = 1
    excel_records: list[tuple[int, str, str, "Path | None"]] = []
    batch_records: list[tuple[int, str, str, "Path | None", str, str]] = []

    with conn.cursor() as cur:
        for info in merchants_info:

            m_id   = info["merchant_id"]
            m_name = info["merchant_name"]

            # ── last approved transaction ──────────────────────────────────
            cur.execute("""
                SELECT MAX(transaction_time)
                FROM transactions
                WHERE merchant_id = %s AND transaction_status = 'APPROVED'
            """, (m_id,))
            last_txn_utc = cur.fetchone()[0]

            if last_txn_utc is None:
                print(f"\n{'─'*62}\n{m_name}")
                closed_from_val = info.get("closed_from")
                if closed_from_val:
                    # Closed before the seeded period — synthesise ago from the closure date
                    h_ago = (ref_time - datetime.combine(closed_from_val, time(23, 59, 59)).replace(tzinfo=WIB)).total_seconds() / 3600
                    ago_s = _format_ago(h_ago)
                    ltf   = f"~{closed_from_val}"
                    print(f"STATUS        : {'INACTIVE':<10} (permanently closed)")
                    print(f"last_txn      : {ltf}  ({ago_s})")
                    jpeg_path = _save_card_jpeg(
                        merchant_name=m_name, status="INACTIVE", confidence=0.0,
                        last_txn_fmt=ltf, ago_str=ago_s,
                        c24h=0, c7d=0, c30d=0, qris_30d=0, edc_30d=0,
                        active_days=0, window_days=WINDOW_DAYS,
                        activity_ratio=0.0, max_gap=0,
                        reasons=[f"last txn {ago_s}"],
                        now_wib=now_wib, output_dir=output_dir, seq=seq,
                    )
                    excel_records.append((seq, m_name, f"{ltf}  ({ago_s})", jpeg_path))
                    bt      = info.get("batch_type")
                    xlsx_id = info.get("_xlsx_id") or ""
                    if bt in ("xlsx-new", "xlsx-update"):
                        batch_records.append((seq, m_name, f"{ltf}  ({ago_s})", jpeg_path, bt, xlsx_id))
                    seq += 1
                else:
                    print("STATUS        : NO DATA")
                    bt      = info.get("batch_type")
                    xlsx_id = info.get("_xlsx_id") or ""
                    if bt in ("xlsx-new", "xlsx-update"):
                        jpeg_path = _save_card_jpeg(
                            merchant_name=m_name, status="INACTIVE", confidence=0.0,
                            last_txn_fmt="—", ago_str="no data",
                            c24h=0, c7d=0, c30d=0, qris_30d=0, edc_30d=0,
                            active_days=0, window_days=WINDOW_DAYS,
                            activity_ratio=0.0, max_gap=0,
                            reasons=["no transaction data found"],
                            now_wib=now_wib, output_dir=output_dir, seq=seq,
                        )
                        excel_records.append((seq, m_name, "—  (no data)", jpeg_path))
                        batch_records.append((seq, m_name, "—  (no data)", jpeg_path, bt, xlsx_id))
                        seq += 1
                continue

            last_txn_wib = last_txn_utc.astimezone(WIB)
            hours_ago    = (ref_time - last_txn_wib).total_seconds() / 3600

            # ── transaction counts (approved SALE only) ────────────────────
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE transaction_time >= %s)                             AS c24h,
                    COUNT(*) FILTER (WHERE transaction_time >= %s::date)                       AS c7d,
                    COUNT(*) FILTER (WHERE transaction_time >= %s::date)                       AS c30d,
                    COUNT(*) FILTER (WHERE transaction_time >= %s::date
                                      AND payment_channel = 'QRIS')                           AS qris,
                    COUNT(*) FILTER (WHERE transaction_time >= %s::date
                                      AND payment_channel = 'EDC_CARD')                       AS edc
                FROM transactions
                WHERE merchant_id        = %s
                  AND transaction_status = 'APPROVED'
                  AND transaction_type   = 'SALE'
            """, (window_24h, window_7d, window_30d, window_30d, window_30d, m_id))
            c24h, c7d, c30d, qris_30d, edc_30d = cur.fetchone()

            # ── active days + max gap ──────────────────────────────────────
            cur.execute("""
                SELECT DISTINCT transaction_time::date AS d
                FROM   transactions
                WHERE  merchant_id        = %s
                  AND  transaction_status = 'APPROVED'
                  AND  transaction_time  >= %s::date
                ORDER  BY 1
            """, (m_id, window_30d))
            active_dates = [r[0] for r in cur.fetchall()]
            active_days  = len(active_dates)

            max_gap = 1
            if len(active_dates) >= 2:
                gaps    = [(active_dates[i+1] - active_dates[i]).days for i in range(len(active_dates) - 1)]
                max_gap = max(gaps)

            activity_ratio = round(active_days / WINDOW_DAYS, 3)

            # ── confidence score ───────────────────────────────────────────
            recency_score = (
                1.0 if hours_ago <=  24 else
                0.9 if hours_ago <=  72 else
                0.7 if hours_ago <= 168 else
                0.3
            )
            activity_score = min(active_days / WINDOW_DAYS, 1.0)
            volume_score   = min(math.log10(max(c30d, 1)) / math.log10(500), 1.0)
            confidence     = round(recency_score * 0.40 + activity_score * 0.35 + volume_score * 0.25, 3)

            # ── status (ACTIVE = at least one txn within 90 days) ─────────
            status = "ACTIVE" if hours_ago <= 90 * 24 else "INACTIVE"

            # ── format helpers ─────────────────────────────────────────────
            ago_str      = _format_ago(hours_ago)
            last_txn_fmt = last_txn_wib.strftime("%Y-%m-%dT%H:%M:%S%z")

            # ── reason bullets ─────────────────────────────────────────────
            reasons: list[str] = []
            if hours_ago <= 72:
                reasons.append(f"last txn {int(hours_ago)}h ago (<= 72h)")
            if active_days >= WINDOW_DAYS * 0.8:
                reasons.append(f"{active_days}/{WINDOW_DAYS} active days, max gap {max_gap}d")
            if c30d >= 50:
                reasons.append(f"{c30d} approved txn / 30d ({qris_30d} QRIS, {edc_30d} EDC)")

            # ── override: permanently closed merchants ─────────────────────
            closed_from_val = info.get("closed_from")
            if closed_from_val:
                status = "INACTIVE"
                reasons.insert(0, f"last txn {ago_str}")

            # ── print card ─────────────────────────────────────────────────
            print(f"\n{'─'*62}")
            print(f"{m_name}")
            print(f"STATUS        : {status:<10} (confidence {confidence:.3f})")
            print(f"last_txn      : {last_txn_fmt}  ({ago_str})")
            print(f"txn 24h/7d/30d: {c24h} / {c7d} / {c30d}")
            print(f"channel split : QRIS {qris_30d}  |  EDC {edc_30d}")
            print(f"active days   : {active_days}/{WINDOW_DAYS}  (ratio {activity_ratio}, max gap {max_gap}d)")
            if reasons:
                print("reasons       :")
                for r in reasons:
                    print(f"  - {r}")

            # ── save JPEG card ─────────────────────────────────────────────
            jpeg_path = _save_card_jpeg(
                merchant_name=m_name,
                status=status,
                confidence=confidence,
                last_txn_fmt=last_txn_fmt,
                ago_str=ago_str,
                c24h=c24h, c7d=c7d, c30d=c30d,
                qris_30d=qris_30d, edc_30d=edc_30d,
                active_days=active_days, window_days=WINDOW_DAYS,
                activity_ratio=activity_ratio, max_gap=max_gap,
                reasons=reasons,
                now_wib=now_wib,
                output_dir=output_dir,
                seq=seq,
            )
            excel_records.append((seq, m_name, f"{last_txn_fmt}  ({ago_str})", jpeg_path))
            bt      = info.get("batch_type")
            xlsx_id = info.get("_xlsx_id") or ""
            if bt in ("xlsx-new", "xlsx-update"):
                batch_records.append((seq, m_name, f"{last_txn_fmt}  ({ago_str})", jpeg_path, bt, xlsx_id))
            seq += 1

    xlsx_path = _save_excel_report(excel_records, output_dir, now_wib)

    batch_new    = [(s, n, ls, jp, xid) for s, n, ls, jp, bt, xid in batch_records if bt == "xlsx-new"]
    batch_update = [(s, n, ls, jp, xid) for s, n, ls, jp, bt, xid in batch_records if bt == "xlsx-update"]
    if batch_new or batch_update:
        batch_path = _save_batch_excel_report(batch_new, batch_update, output_dir, now_wib)
    else:
        batch_path = None

    print(f"\n{'='*62}")
    print(f"  JPEG cards saved to: {output_dir}")
    if xlsx_path:
        print(f"  Excel report     : {xlsx_path}")
    if batch_path:
        print(f"  Batch report     : {batch_path}")
    print()


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

_BATCH_NEW_XLSX = INPUT_DIR / "list_new_edc.xlsx"
_BATCH_UPD_XLSX = INPUT_DIR / "list_update_edc.xlsx"


def _load_xlsx_supplement(csv_rows: list[dict]) -> int:
    """
    Append batch xlsx rows to csv_rows in-place (for schedule lookup / batch tagging).
    Returns the number of xlsx rows appended.
    """
    count = 0
    if _BATCH_NEW_XLSX.exists():
        rows = read_batch_xlsx(_BATCH_NEW_XLSX, "new")
        csv_rows.extend(rows)
        count += len(rows)
    if _BATCH_UPD_XLSX.exists():
        rows = read_batch_xlsx(_BATCH_UPD_XLSX, "update")
        csv_rows.extend(rows)
        count += len(rows)
    return count


def main() -> None:
    # Ensure UTF-8 output on Windows (─ and ═ chars in report cards)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    purge_mode        = "--purge"          in sys.argv
    report_mode       = "--report"         in sys.argv
    prune_closed_mode = "--prune-closed"   in sys.argv
    append_mode       = "--append"         in sys.argv
    reset_mode        = "--reset"          in sys.argv
    add_merchants_mode = "--add-merchants" in sys.argv
    batch_seed_mode   = "--batch-seed"     in sys.argv

    conn = get_connection()

    # Auto-detect: if no explicit mode and DB already has data → append instead of wipe
    if not any([reset_mode, purge_mode, append_mode, report_mode,
                prune_closed_mode, add_merchants_mode, batch_seed_mode]):
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM transactions")
            if cur.fetchone()[0] > 0:
                append_mode = True

    if report_mode:
        mode_label = "REPORT ONLY"
    elif purge_mode:
        mode_label = "PURGE DATE RANGE then re-seed"
    elif prune_closed_mode:
        mode_label = "PRUNE CLOSED MERCHANTS"
    elif batch_seed_mode:
        mode_label = "BATCH SEED (list_new + list_update xlsx)"
    elif add_merchants_mode:
        mode_label = "ADD NEW MERCHANTS (no-touch existing)"
    elif append_mode:
        mode_label = "APPEND (continue from last transaction date)"
    elif reset_mode:
        mode_label = "FULL RESET"
    else:
        mode_label = "INITIAL SEED"

    print("=" * 60)
    print("  EDC POC Seeder")
    print(f"  Mode       : {mode_label}")
    print(f"  Date range : {DATE_START} — {DATE_END}")
    print(f"  CSV        : {CSV_PATH}")
    print(f"  Database   : {DB_CONFIG['dbname']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print("=" * 60)

    if prune_closed_mode:
        print("[1/3] Loading CSV for closure dates...")
        with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
            csv_rows = [r for r in csv.DictReader(f) if r.get("status", "").strip() == "ACTIVE"]
        print(f"      {len(csv_rows)} active POIs loaded.")

        print("[2/3] Pruning closed merchant data...")
        prune_closed_merchants(conn, csv_rows)

        print("[3/3] Loading merchants from DB for report...")
        merchants_info = load_merchants_from_db(conn, csv_rows)
        print(f"      {len(merchants_info)} merchants loaded.")

        print("\nGenerating merchant activity report...")
        generate_merchant_status_report(conn, merchants_info)
        conn.close()
        return

    if append_mode:
        print("[1/4] Loading CSV + batch xlsx for schedule data...")
        with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
            csv_rows = [r for r in csv.DictReader(f) if r.get("status", "").strip() == "ACTIVE"]
        _n_xlsx = _load_xlsx_supplement(csv_rows)
        print(f"      {len(csv_rows) - _n_xlsx} CSV POIs + {_n_xlsx} xlsx rows loaded.")

        append_start = get_append_start_date(conn)
        if append_start is None:
            print("      No existing transactions found — run a full seed first.")
            conn.close()
            return
        if append_start > DATE_END:
            print(f"      Already up to date (last date: {append_start - timedelta(days=1)}).")
            conn.close()
            return
        print(f"      Appending from {append_start} → {DATE_END} "
              f"({(DATE_END - append_start).days + 1} days).")

        print("[2/4] Loading reference data (QRIS issuers)...")
        qris_issuer_ids = load_qris_issuers(conn)

        print("[3/4] Loading merchants + cards from DB...")
        merchants_info = load_merchants_from_db(conn, csv_rows)
        card_ids       = load_cards_from_db(conn)
        print(f"      {len(merchants_info)} merchants, {len(card_ids)} cards.")

        print("[4/4] Generating and inserting transactions...")
        reset_trace_seq(conn)
        generate_and_insert_transactions(
            conn, merchants_info, card_ids, qris_issuer_ids,
            start_date=append_start, end_date=DATE_END,
        )

        print("\nRow count verification:")
        with conn.cursor() as cur:
            for table in ["transactions", "settlement", "transaction_log"]:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                n = cur.fetchone()[0]
                print(f"      {table:<22} {n:>10,}")

        print("\nGenerating merchant activity report...")
        generate_merchant_status_report(conn, merchants_info)
        conn.close()
        return

    if report_mode:
        # Skip all seeding — load existing merchants from DB and generate report only
        print("[1/2] Loading CSV + batch xlsx for schedule data...")
        with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
            csv_rows = [r for r in csv.DictReader(f) if r.get("status", "").strip() == "ACTIVE"]
        _n_xlsx = _load_xlsx_supplement(csv_rows)
        print(f"      {len(csv_rows) - _n_xlsx} CSV POIs + {_n_xlsx} xlsx rows loaded.")

        print("[2/2] Loading merchants from DB...")
        merchants_info = load_merchants_from_db(conn, csv_rows)
        print(f"      {len(merchants_info)} merchants loaded.")

        print("\nGenerating merchant activity report...")
        generate_merchant_status_report(conn, merchants_info)
        conn.close()
        return

    if batch_seed_mode:
        new_xlsx = _BATCH_NEW_XLSX
        upd_xlsx = _BATCH_UPD_XLSX

        print("[1/7] Reading batch xlsx files...")
        batch_rows: list[dict] = []
        if new_xlsx.exists():
            nr = read_batch_xlsx(new_xlsx, "new")
            print(f"      list_new_edc.xlsx   : {len(nr)} rows")
            batch_rows.extend(nr)
        else:
            print(f"      list_new_edc.xlsx   : not found — skipped")
        if upd_xlsx.exists():
            ur = read_batch_xlsx(upd_xlsx, "update")
            print(f"      list_update_edc.xlsx: {len(ur)} rows")
            batch_rows.extend(ur)
        else:
            print(f"      list_update_edc.xlsx: not found — skipped")

        if not batch_rows:
            print("      No batch rows loaded — nothing to do.")
            conn.close()
            return

        print("[2/7] Identifying merchants not yet in DB...")
        new_to_db = filter_new_csv_rows(conn, batch_rows)
        print(f"      {len(new_to_db)} new (not in DB), "
              f"{len(batch_rows) - len(new_to_db)} already exist.")

        print("[3/7] Loading reference data...")
        acquirer_ids    = load_acquirers(conn)
        qris_issuer_ids = load_qris_issuers(conn)

        if new_to_db:
            idx_offset = get_merchant_idx_offset(conn)
            print(f"      Sequence offset: {idx_offset}")

            print("[4/7] Inserting admin areas (idempotent)...")
            area_map = insert_admin_areas(conn, new_to_db)

            print("[5/7] Inserting new merchants + terminals...")
            new_merchants_info = insert_merchants_and_terminals(
                conn, new_to_db, acquirer_ids, area_map, idx_offset=idx_offset
            )
            print(f"      {len(new_merchants_info)} merchants and terminals inserted.")
        else:
            new_merchants_info = []
            print("[4/7] No new merchants — skipping insert.")
            print("[5/7] (skipped)")

        # Also seed transactions for batch merchants already in DB but with zero transactions
        with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
            csv_base = [r for r in csv.DictReader(f) if r.get("status", "").strip() == "ACTIVE"]
        all_schedule_rows = csv_base + batch_rows
        all_batch_info = load_merchants_from_db(conn, all_schedule_rows)

        batch_names = {r.get("name1", "").strip() for r in batch_rows}
        batch_info_only = [m for m in all_batch_info if m["merchant_name"] in batch_names]

        # Find batch merchants that have no transactions yet
        with conn.cursor() as cur:
            cur.execute("SELECT merchant_id FROM transactions GROUP BY merchant_id")
            has_txn = {r[0] for r in cur.fetchall()}
        no_txn_info = [m for m in batch_info_only if m["merchant_id"] not in has_txn]

        if new_merchants_info or no_txn_info:
            to_seed = new_merchants_info + [m for m in no_txn_info
                                            if m["merchant_id"] not in
                                            {x["merchant_id"] for x in new_merchants_info}]
            print(f"[6/7] Generating transactions for {len(to_seed)} batch merchant(s) with no data...")
            card_ids = load_cards_from_db(conn)
            reset_trace_seq(conn)
            generate_and_insert_transactions(
                conn, to_seed, card_ids, qris_issuer_ids,
                start_date=DATE_START, end_date=DATE_END,
            )
        else:
            print("[6/7] All batch merchants already have transactions — skipping.")

        print("\nRow count verification:")
        with conn.cursor() as cur:
            for table in ["merchants", "terminals", "transactions", "settlement", "transaction_log"]:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                n = cur.fetchone()[0]
                print(f"      {table:<22} {n:>10,}")

        print("[7/7] Generating report (all merchants, batch-tagged)...")
        # Re-load merchants_info so new transaction data is reflected in the report
        all_merchants_info = load_merchants_from_db(conn, all_schedule_rows)
        generate_merchant_status_report(conn, all_merchants_info)
        conn.close()
        return

    if add_merchants_mode:
        print("[1/6] Loading CSV...")
        with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
            csv_rows = [r for r in csv.DictReader(f)
                        if r.get("status", "").strip() == "ACTIVE"]
        print(f"      {len(csv_rows)} active POIs in CSV.")

        print("[2/6] Identifying new merchants...")
        new_rows = filter_new_csv_rows(conn, csv_rows)
        if not new_rows:
            print("      No new merchants found — DB is already up to date.")
            conn.close()
            return
        print(f"      {len(new_rows)} new merchant(s): "
              + ", ".join(r.get("name1", "") for r in new_rows))

        idx_offset = get_merchant_idx_offset(conn)
        print(f"      Sequence offset: {idx_offset}")

        print("[3/6] Inserting admin areas (idempotent)...")
        acquirer_ids    = load_acquirers(conn)
        qris_issuer_ids = load_qris_issuers(conn)
        area_map = insert_admin_areas(conn, new_rows)

        print("[4/6] Inserting new merchants + terminals...")
        new_merchants_info = insert_merchants_and_terminals(
            conn, new_rows, acquirer_ids, area_map, idx_offset=idx_offset
        )
        print(f"      {len(new_merchants_info)} merchants and terminals inserted.")

        print("[5/6] Loading cards + generating transactions for new merchants...")
        card_ids = load_cards_from_db(conn)
        reset_trace_seq(conn)
        generate_and_insert_transactions(
            conn, new_merchants_info, card_ids, qris_issuer_ids,
            start_date=DATE_START, end_date=DATE_END,
        )

        print("\nRow count verification:")
        with conn.cursor() as cur:
            for table in ["merchants", "terminals", "transactions", "settlement", "transaction_log"]:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                n = cur.fetchone()[0]
                print(f"      {table:<22} {n:>10,}")

        print("[6/6] Generating report (all merchants)...")
        all_merchants_info = load_merchants_from_db(conn, csv_rows)
        generate_merchant_status_report(conn, all_merchants_info)
        conn.close()
        return

    print("[2/7] Loading reference data (acquirers + QRIS issuers)...")
    acquirer_ids    = load_acquirers(conn)
    qris_issuer_ids = load_qris_issuers(conn)
    print(f"      {len(acquirer_ids)} acquirers, {len(qris_issuer_ids)} QRIS issuers.")

    print("[3/7] Loading CSV...")
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        csv_rows = [r for r in csv.DictReader(f) if r.get("status", "").strip() == "ACTIVE"]
    print(f"      {len(csv_rows)} active POIs loaded.")

    if purge_mode:
        print("[1/7] Purging transaction data for date range...")
        purge_date_range(conn)

        print("[4/7] Loading admin areas from DB (skipped — purge mode)...")
        print("[5/7] Loading merchants + terminals from DB...")
        merchants_info = load_merchants_from_db(conn, csv_rows)
        print(f"      {len(merchants_info)} merchants loaded from DB.")

        print("[6/7] Loading cards from DB (skipped — purge mode)...")
        card_ids = load_cards_from_db(conn)
        print(f"      {len(card_ids)} cards loaded from DB.")
    else:
        print("[1/7] Resetting database...")
        reset_database(conn)

        print("[4/7] Inserting admin areas (Province → City → District)...")
        area_map = insert_admin_areas(conn, csv_rows)
        with conn.cursor() as cur:
            cur.execute("SELECT area_level, COUNT(*) FROM admin_areas GROUP BY 1 ORDER BY 1")
            for lvl, cnt in cur.fetchall():
                label = {1: "Province", 2: "City/Regency", 3: "District", 4: "Village"}[lvl]
                print(f"      Level {lvl} ({label}): {cnt}")

        print("[5/7] Inserting merchants + terminals...")
        merchants_info = insert_merchants_and_terminals(conn, csv_rows, acquirer_ids, area_map)
        print(f"      {len(merchants_info)} merchants and terminals inserted.")

        print("[6/7] Inserting cards...")
        card_ids = insert_cards(conn, count=300)
        print(f"      {len(card_ids)} cards inserted.")

    print("[7/7] Generating transactions, settlement, and audit logs...")
    generate_and_insert_transactions(conn, merchants_info, card_ids, qris_issuer_ids)

    print("\nRow count verification:")
    with conn.cursor() as cur:
        for table in [
            "admin_areas", "merchants", "terminals", "cards", "qris_issuers",
            "transactions", "settlement", "transaction_log",
        ]:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            n = cur.fetchone()[0]
            print(f"      {table:<22} {n:>10,}")

    print("\n[8/8] Merchant activity report...")
    generate_merchant_status_report(conn, merchants_info)

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
