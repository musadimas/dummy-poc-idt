"""
helpers.py — utility functions with no database access for the EDC POC seeder.
"""

from config import *
import random
import re
import string
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# TRACE SEQUENCE  (module-level counter; reset via seed_data.reset_trace_seq)
# ──────────────────────────────────────────────────────────────────────────────

_trace_seq = 0

# ──────────────────────────────────────────────────────────────────────────────
# DAY / TIME PARSING HELPERS  (used by _parse_hours_text)
# ──────────────────────────────────────────────────────────────────────────────

_DAY_IDX = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}
_TIME_RE = re.compile(r'(\d{1,2}):(\d{2})')


# ──────────────────────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# ──────────────────────────────────────────────────────────────────────────────

def _normalize_city(name: str) -> str:
    """Strip Indonesian administrative prefixes from city names."""
    for prefix in ("Kota ", "Kabupaten ", "Kab. ", "Kab "):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


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


def next_trace_number(txn_date: date) -> str:
    global _trace_seq
    _trace_seq += 1
    return f"RRN{txn_date.strftime('%Y%m%d')}{_trace_seq:06d}"


def make_approval_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def round_to_thousand(value: int) -> Decimal:
    return Decimal(round(value / 1000) * 1000)


def mask_card_number(prefix: str) -> str:
    """Format: XXXX XX** **** XXXX — first 4 digits and last 4 visible."""
    last4 = f"{random.randint(0, 9999):04d}"
    second_group = f"{prefix[2]}X"
    return f"{prefix} {second_group}** **** {last4}"


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


def _read_unified_csv(path: Path) -> list[dict]:
    """
    Read the unified list_edc.csv and return rows in the same dict format
    as the internal csv_row format.  Required column: report_status (new|update|delete|realtime).
    """
    import csv as _csv_mod

    result = []
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in _csv_mod.DictReader(f):
                def _g(col):
                    v = row.get(col)
                    return "" if v is None else str(v).strip()

                status = _g("report_status").lower()
                if status not in ("new", "update", "delete", "realtime"):
                    continue

                id_val   = _g("id")
                name     = _g("name")
                lat      = _g("latitude")
                lon      = _g("longitude")
                rlat     = _g("routing_lat") or lat
                rlon     = _g("routing_lon") or lon
                category = _g("category")
                phone    = _g("phone")
                mobile   = _g("mobile")
                hno      = _g("house_number")
                street   = _g("street_name")
                postal   = _g("postal_code")
                admin2   = _g("admin2")
                admin3   = _normalize_city(_g("admin3"))
                admin4   = _g("admin4")
                admin5   = _g("admin5")

                hours_text     = _g("operating_hours")
                sched_override = _parse_hours_text(hours_text) if hours_text else None
                if not sched_override:
                    default        = CATEGORY_DEFAULT_HOURS.get(category)
                    sched_override = {wd: default for wd in range(7)}

                closed_from_str = ""
                if status == "delete":
                    cf_raw = _g("closed_from")
                    closed_from_str = cf_raw[:10] if cf_raw else ""

                last_signal_str = ""
                batch_type_tag  = f"xlsx-{status}"
                if status == "realtime":
                    _today = date.today()
                    _wd    = _today.weekday()
                    _win   = (sched_override or {}).get(_wd)
                    if _win and _win[0] and _win[1]:
                        _open_s  = _win[0].hour * 3600 + _win[0].minute * 60
                        _close_s = _win[1].hour * 3600 + _win[1].minute * 60
                        _sig_s   = random.randint(_open_s, _close_s - 1) if _close_s > _open_s else _open_s
                    else:
                        _sig_s = random.randint(8 * 3600, 22 * 3600 - 1)
                    _sig_h, _sig_rem = divmod(_sig_s, 3600)
                    _sig_m, _sig_sec = divmod(_sig_rem, 60)
                    last_signal_str = datetime(_today.year, _today.month, _today.day,
                                               _sig_h, _sig_m, _sig_sec).strftime("%Y-%m-%d %H:%M:%S")

                if not name:
                    continue

                result.append({
                    "name1":              name,
                    "displaylatitude":    lat,
                    "displaylongitude":   lon,
                    "routinglatitude":    rlat,
                    "routinglongitude":   rlon,
                    "primarycategorynm":  category,
                    "admin2":             admin2,
                    "admin3":             admin3,
                    "admin4":             admin4,
                    "admin5":             admin5,
                    "hno":                hno,
                    "streetname":         street,
                    "postalcode":         postal,
                    "PHONE":              phone,
                    "MOBILE":             mobile,
                    "_schedule_override": sched_override,
                    "_xlsx_id":           id_val,
                    "closed_from":        closed_from_str,
                    "batch_type":         batch_type_tag,
                    "last_signal":        last_signal_str,
                    "status":             "ACTIVE",
                })
    except Exception as exc:
        print(f"      [unified-csv] Cannot read {path.name}: {exc}")

    from collections import Counter as _Counter
    name_counts = _Counter(r["name1"] for r in result)
    for r in result:
        if name_counts[r["name1"]] > 1:
            raw_street = r.get("streetname", "").strip()
            clean = re.sub(r"(?i)^jalan\s+", "", raw_street).strip()
            if clean:
                r["name1"] = f"{r['name1']} {clean}"

    return result


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


def _format_ago(hours_ago: float) -> str:
    """Format an elapsed-hours value as 'Xh ago', 'Xd ago', or 'X.Xyr ago'."""
    if hours_ago < 24:
        return f"{hours_ago:.1f}h ago"
    if hours_ago < 24 * 365:
        return f"{hours_ago / 24:.0f}d ago"
    return f"{hours_ago / (24 * 365.25):.1f}yr ago"


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
