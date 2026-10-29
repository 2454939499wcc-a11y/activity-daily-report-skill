#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""活动日报生成器。

标准数据自动查：
  - 页面 SPM：music_dws.dws_log_music_user_spm_di
  - 活动总览：music_new_dm.ads_log_h5_activity_tag_di

自定义数据：
  --data extra.json

输出：
  {"ok": true, "hasMessages": true, "head": "...", "lines": [...]}
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import das_query

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_DIR = os.path.join(BASE, "sql")
TEMPLATE_DIR = os.path.join(BASE, "templates")
MAX_SEGMENT_DAYS = 30


def read_sql(name):
    with open(os.path.join(SQL_DIR, name), "r", encoding="utf-8") as f:
        return f.read()


def guess_pt_action(spm_no):
    spm = str(spm_no or "")
    if spm.startswith("btn_"):
        return "_ec"
    if spm.startswith("mod_"):
        return "_ev"
    if spm.startswith("page_"):
        return "_pv"
    return None


def resolve_date(value):
    if not value:
        return (datetime.now(common.CST) - timedelta(days=1)).strftime("%Y-%m-%d")
    text = str(value)
    if text.isdigit():
        return datetime.fromtimestamp(int(text) / 1000, common.CST).strftime("%Y-%m-%d")
    dt = common.parse_dt(text)
    return dt.strftime("%Y-%m-%d") if dt else text


def split_segments(start, end, max_days=MAX_SEGMENT_DAYS):
    segments = []
    cur = start
    while cur <= end:
        seg_end = min(cur + timedelta(days=max_days - 1), end)
        segments.append((cur.isoformat(), seg_end.isoformat()))
        cur = seg_end + timedelta(days=1)
    return segments


def resolve_activity_id(card, date, env):
    das = (card.get("metrics") or {}).get("das") or {}
    aid = das.get("activity_id")
    if aid:
        return str(aid), None
    keyword = das.get("activity_name_keyword") or card.get("displayName") or card.get("name")
    if not keyword:
        return None, "no_activity_id"
    sql = das_query.render_sql(read_sql("activity_tag_find.sql"), {
        "dt": date, "is_dawn": das.get("is_dawn", 0), "keyword": keyword,
    })
    result = das_query.run_query(sql, env=env, limit=50, timeout=120)
    if not result.get("ok"):
        return None, "find_activity_failed"
    ids = sorted({str(x.get("activity_id")) for x in (result.get("rows") or []) if x.get("activity_id")})
    if len(ids) == 1:
        return ids[0], None
    if not ids:
        return None, "activity_not_found"
    return None, "activity_id_ambiguous"


def query_activity_daily(card, date, env, activity_id):
    if not activity_id:
        return None, "no_activity_id"
    das = (card.get("metrics") or {}).get("das") or {}
    sql = das_query.render_sql(read_sql("activity_tag_daily.sql"), {
        "dt": date, "is_dawn": das.get("is_dawn", 0), "activity_id": activity_id,
    })
    result = das_query.run_query(sql, env=env, limit=10, timeout=120)
    if not result.get("ok"):
        return None, result.get("error") or "activity_query_failed"
    rows = result.get("rows") or []
    return (rows[0] if rows else None), None


def query_page(card, page, date, env):
    spm = page.get("spm_no")
    pt = page.get("pt_action") or guess_pt_action(spm)
    if not spm or not pt:
        return None, "missing_spm_or_pt_action", False
    sql = das_query.render_sql(read_sql("spm_pv_uv.sql"), {
        "dt": date, "pt_action": pt, "spm_no": spm,
    })
    approx = False
    result = das_query.run_query(sql, env=env, limit=10, timeout=180, catalog="hive_da_music")
    if not result.get("ok"):
        result = das_query.run_query(sql, env=env, limit=10, timeout=180)
    if not result.get("ok"):
        sql_approx = sql.replace("COUNT(DISTINCT user_id)", "APPROX_COUNT_DISTINCT(user_id)")
        result = das_query.run_query(sql_approx, env=env, limit=10, timeout=180, catalog="hive_da_music")
        approx = True
    if not result.get("ok"):
        return None, result.get("error") or "page_query_failed", approx
    rows = result.get("rows") or []
    return (rows[0] if rows else None), None, approx


def query_total(card, date, env, activity_id, first_page):
    """返回 (pv, uv, note)。"""
    life = card.get("lifecycle") or {}
    start_text = str(life.get("start") or "")[:10]
    if not start_text:
        return None, None, None
    try:
        start = datetime.strptime(start_text, "%Y-%m-%d").date()
        end = datetime.strptime(date, "%Y-%m-%d").date()
    except Exception:
        return None, None, None
    if start > end:
        return None, None, None
    segments = split_segments(start, end)
    das = (card.get("metrics") or {}).get("das") or {}
    is_dawn = int(das.get("is_dawn", 0))
    errors = []

    if activity_id:
        total_pv = 0
        pv_ok = True
        for seg_start, seg_end in segments:
            sql = das_query.render_sql(read_sql("activity_tag_range_pv.sql"), {
                "start_dt": seg_start, "end_dt": seg_end,
                "is_dawn": is_dawn, "activity_id": activity_id,
            })
            result = das_query.run_query(sql, env=env, limit=10, timeout=180)
            if not result.get("ok"):
                pv_ok = False
                errors.append("pv")
                break
            rows = result.get("rows") or []
            total_pv += common.to_int(rows[0].get("page_pv")) if rows else 0
        if not pv_ok:
            total_pv = None

        subqueries = []
        for seg_start, seg_end in segments:
            subqueries.append(
                "SELECT user_id FROM music_dws.dws_act_user_h5_activity_page_dawn_di "
                "WHERE dt BETWEEN '%s' AND '%s' AND activity_id = '%s'"
                % (seg_start, seg_end, activity_id)
            )
        uv_sql = (
            "SELECT COUNT(DISTINCT user_id) AS act_uv FROM (\n"
            + "\nUNION ALL\n".join(subqueries)
            + "\n) t WHERE user_id <> '0' AND user_id IS NOT NULL"
        )
        uv_result = das_query.run_query(uv_sql, env=env, limit=10, timeout=600, catalog="hive_da_music")
        total_uv = None
        if uv_result.get("ok"):
            rows = uv_result.get("rows") or []
            total_uv = common.to_int(rows[0].get("act_uv")) if rows else 0
        else:
            errors.append("uv")
        return total_pv, total_uv, ("、".join(errors) if errors else None)

    # 不在活动标签表：用第一个页面做累计兜底
    if not first_page:
        return None, None, None
    spm = first_page.get("spm_no")
    pt = first_page.get("pt_action") or guess_pt_action(spm)
    if not spm or not pt:
        return None, None, None
    sql = das_query.render_sql(read_sql("spm_pv_uv_range.sql"), {
        "start_dt": start.isoformat(), "end_dt": end.isoformat(),
        "pt_action": pt, "spm_no": spm,
    })
    result = das_query.run_query(sql, env=env, limit=10, timeout=300, catalog="hive_da_music")
    if not result.get("ok"):
        return None, None, "page_range_failed"
    rows = result.get("rows") or []
    return (common.to_int(rows[0].get("pv")) if rows else None,
            common.to_int(rows[0].get("uv")) if rows else None,
            None)


def safe_format(text, ctx):
    class SafeDict(dict):
        def __missing__(self, key):
            return "-"
    return str(text).format_map(SafeDict(ctx))


def build_step_lines(page_results):
    lines = []
    prev_uv = None
    for item in page_results:
        row = item.get("row")
        if not row:
            line = "%d. %s：⚠️无数据" % (item["index"] + 1, item["name"])
            if item.get("error"):
                line += "（%s）" % item["error"]
            lines.append(line)
            continue
        pv = common.to_int(row.get("pv"))
        uv = common.to_int(row.get("uv"))
        line = "%d. %s：PV %s｜UV %s" % (
            item["index"] + 1, item["name"], common.fmt_num(pv), common.fmt_num(uv))
        if prev_uv:
            line += "｜转化 %s" % common.fmt_rate(uv, prev_uv)
        if item.get("approx"):
            line += "（UV 近似）"
        if item.get("cached"):
            line += "（缓存）"
        lines.append(line)
        if uv is not None:
            prev_uv = uv
    return lines


def build_custom_lines(card, extra):
    lines = []
    for item in card.get("customMetrics") or []:
        key = item.get("key")
        if not key:
            continue
        label = item.get("label") or key
        value = extra.get(key)
        if value is None or value == "":
            value = "-"
        unit = item.get("unit") or ""
        sep = " " if unit else ""
        lines.append("%s：%s%s%s" % (label, value, sep, unit))
    return lines


def render(card, date, activity_row, page_results, template_name, totals, extra, custom_lines):
    path = os.path.join(TEMPLATE_DIR, template_name + ".json")
    if not os.path.exists(path):
        path = os.path.join(TEMPLATE_DIR, "daily_generic.json")
    with open(path, "r", encoding="utf-8") as f:
        template = json.load(f)

    row = activity_row or {}
    totals = totals or {}
    ctx = {
        "displayName": card.get("displayName") or card.get("name"),
        "date": date,
        "dt": date,
        "scope": "数据分区 %s" % date,
        "total_start": str((card.get("lifecycle") or {}).get("start") or "")[:10],
        "total_end": date,
        "activity_pv": common.fmt_num(row.get("activity_page_cnt_1d")),
        "activity_uv": common.fmt_num(row.get("activity_page_unt_1d")),
        "active_cnt": common.fmt_num(row.get("activity_active_cnt_1d")),
        "active_uv": common.fmt_num(row.get("activity_active_unt_1d")),
        "share_cnt": common.fmt_num(row.get("activity_share_cnt_1d")),
        "share_uv": common.fmt_num(row.get("activity_share_unt_1d")),
        "play_pv": common.fmt_num(row.get("play_pv_num")),
        "play_uv": common.fmt_num(row.get("play_uv_num")),
        "like_pv": common.fmt_num(row.get("like_pv_num")),
        "like_uv": common.fmt_num(row.get("like_uv_num")),
        "total_pv": common.fmt_num(totals.get("pv")),
        "total_uv": common.fmt_num(totals.get("uv")),
        "total_note": "（缓存）" if totals.get("cached") else "",
    }
    if extra:
        ctx.update(extra)

    head = safe_format(template.get("head", ""), ctx)
    lines = []
    sections = template.get("sections") or []
    for section in sections:
        block = []
        for line in section.get("lines") or []:
            if line == "{step_lines}":
                block.extend(build_step_lines(page_results))
            elif line == "{custom_lines}":
                block.extend(custom_lines)
            else:
                block.append(safe_format(line, ctx))
        if section.get("optional") and not any(x.strip() for x in block):
            continue
        if lines:
            lines.append("")
        title = section.get("title")
        if title:
            lines.append(safe_format(title, ctx))
        lines.extend(block)
    return head, lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("card")
    parser.add_argument("--date", default=None)
    parser.add_argument("--state", default=None)
    parser.add_argument("--cache", default=None)
    parser.add_argument("--data", default=None)
    parser.add_argument("--template", default=None)
    parser.add_argument("--no-total", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    card = common.load_json(args.card)
    if not card:
        print("读不到名片: " + args.card, file=sys.stderr)
        return 2
    date = resolve_date(args.date)
    env = (card.get("platform") or {}).get("env") or "online"

    if args.state:
        state = common.load_json(args.state, {}) or {}
        if state.get("lastSentDate") == date and not args.force:
            print(json.dumps({"ok": True, "skipped": "already_sent", "date": date}, ensure_ascii=False, indent=2))
            return 0
    if not args.force and not common.date_in_lifecycle(card, date):
        print(json.dumps({"ok": True, "skipped": "outside_lifecycle", "date": date}, ensure_ascii=False, indent=2))
        return 0

    activity_id, id_error = resolve_activity_id(card, date, env)
    activity_row, activity_error = query_activity_daily(card, date, env, activity_id)
    cache = common.load_json(args.cache, {}) if args.cache else {}
    cache_day = cache.get(date) or {}
    if not activity_row and cache_day.get("_activity"):
        activity_row = cache_day["_activity"]
        activity_error = None

    page_results = []
    for index, page in enumerate(card.get("pages") or []):
        row, error, approx = query_page(card, page, date, env)
        cached = False
        if not row and page.get("spm_no") in cache_day:
            row = cache_day[page.get("spm_no")]
            error = None
            approx = False
            cached = True
        page_results.append({
            "index": index,
            "name": page.get("name") or page.get("spm_no"),
            "spm_no": page.get("spm_no"),
            "pt_action": page.get("pt_action") or guess_pt_action(page.get("spm_no")),
            "row": row,
            "error": error,
            "approx": approx,
            "cached": cached,
        })

    if not activity_row:
        first = next((p for p in page_results if p.get("row")), None)
        if first:
            activity_row = {"activity_page_cnt_1d": first["row"].get("pv"),
                            "activity_page_unt_1d": first["row"].get("uv")}

    totals = None
    total_error = None
    daily_cfg = (card.get("broadcast") or {}).get("daily") or {}
    if (not args.no_total) and daily_cfg.get("includeTotal", True):
        total_pv, total_uv, total_error = query_total(
            card, date, env, activity_id, next((p for p in page_results if p.get("row")), None))
        cached_total = cache_day.get("_total") or {}
        total_cached = False
        if total_pv is None and cached_total.get("pv") is not None:
            total_pv = cached_total.get("pv")
            total_cached = True
        if total_uv is None and cached_total.get("uv") is not None:
            total_uv = cached_total.get("uv")
            total_cached = True
        totals = {"pv": total_pv, "uv": total_uv, "cached": total_cached}

    extra = common.load_json(args.data, {}) if args.data else {}
    custom_lines = build_custom_lines(card, extra)
    template_name = args.template or daily_cfg.get("template") or "daily_generic"
    head, lines = render(card, date, activity_row, page_results, template_name, totals, extra, custom_lines)

    result = {
        "ok": True,
        "hasMessages": bool(lines),
        "head": head,
        "lines": lines,
        "date": date,
        "activityId": activity_id,
        "idError": id_error,
        "activityError": activity_error if not activity_row else None,
        "totalPv": totals.get("pv") if totals else None,
        "totalUv": totals.get("uv") if totals else None,
        "totalError": total_error,
        "pages": page_results,
        "customLines": custom_lines,
        "template": template_name,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
