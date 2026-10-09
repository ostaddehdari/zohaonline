from __future__ import annotations
from datetime import date

PERSIAN_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')


def _div(a, b):
    return a // b


def gregorian_to_jalali(gy: int, gm: int, gd: int):
    g_d_m = [0,31,59,90,120,151,181,212,243,273,304,334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + 365 * gy + _div(gy2 + 3, 4) - _div(gy2 + 99, 100) + _div(gy2 + 399, 400) + gd + g_d_m[gm - 1]
    jy = -1595 + 33 * _div(days, 12053)
    days %= 12053
    jy += 4 * _div(days, 1461)
    days %= 1461
    if days > 365:
        jy += _div(days - 1, 365)
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + _div(days, 31)
        jd = 1 + days % 31
    else:
        jm = 7 + _div(days - 186, 30)
        jd = 1 + (days - 186) % 30
    return jy, jm, jd


def jalali_to_gregorian(jy: int, jm: int, jd: int):
    jy += 1595
    days = -355668 + 365 * jy + _div(jy, 33) * 8 + _div(jy % 33 + 3, 4) + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += (jm - 7) * 30 + 186
    gy = 400 * _div(days, 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * _div(days, 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * _div(days, 1461)
    days %= 1461
    if days > 365:
        gy += _div(days - 1, 365)
        days = (days - 1) % 365
    gd = days + 1
    leap = gy % 4 == 0 and (gy % 100 != 0 or gy % 400 == 0)
    month_days = [0,31,29 if leap else 28,31,30,31,30,31,31,30,31,30,31]
    gm = 1
    while gm <= 12 and gd > month_days[gm]:
        gd -= month_days[gm]
        gm += 1
    return gy, gm, gd


def parse_jalali(value: str | None):
    text = (value or '').strip().translate(PERSIAN_DIGITS).replace('-', '/').replace('.', '/')
    if not text:
        return None
    parts = [p.strip() for p in text.split('/') if p.strip()]
    if len(parts) != 3:
        return None
    try:
        jy, jm, jd = map(int, parts)
        if not (1200 <= jy <= 1700 and 1 <= jm <= 12 and 1 <= jd <= 31):
            return None
        gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
        return date(gy, gm, gd)
    except (ValueError, TypeError):
        return None


def format_jalali(value):
    if not value:
        return ''
    if hasattr(value, 'date') and not isinstance(value, date):
        value = value.date()
    jy, jm, jd = gregorian_to_jalali(value.year, value.month, value.day)
    return f'{jy:04d}/{jm:02d}/{jd:02d}'
