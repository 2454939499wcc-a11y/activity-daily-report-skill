#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""活动日报公共函数。"""
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))


def load_json(path, default=None):
    try:
        with open(os.path.expanduser(path), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    path = os.path.abspath(os.path.expanduser(path))
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".daily-report-", dir=parent or ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def parse_dt(value):
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=CST)
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=CST)
        return dt.astimezone(CST)
    except Exception:
        return None


def is_permanent(value):
    return value is None or str(value).strip().lower() in ("", "permanent", "forever", "none", "长期", "永久")


def date_in_lifecycle(card, date):
    life = card.get("lifecycle") or {}
    day = parse_dt(str(date) + " 00:00:00") or parse_dt(date)
    start = parse_dt(life.get("start"))
    end = None if is_permanent(life.get("end")) else parse_dt(life.get("end"))
    if not day:
        return True
    if start and day.date() < start.date():
        return False
    if end and day.date() > end.date():
        return False
    return True


def to_int(value):
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return None


def fmt_num(value):
    n = to_int(value)
    return "-" if n is None else "{:,}".format(n)


def fmt_rate(numerator, denominator):
    a = to_int(numerator)
    b = to_int(denominator)
    if a is None or not b:
        return "-"
    return "%.2f%%" % (a * 100.0 / b)
