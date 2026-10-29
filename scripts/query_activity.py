#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""活动查询入口。固定查询包，不生成 SQL。

用法:
    python3 query_activity.py <card> --pack overview --date 2026-10-28
    python3 query_activity.py <card> --pack page --page 加载页 --date 2026-10-28
    python3 query_activity.py <card> --pack trend --page 加载页 --start 2026-10-21 --end 2026-10-28
    python3 query_activity.py <card> --pack total
"""
import argparse
import json
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import daily_report as dr
import das_query


def resolve_range(args, trend=False):
    end = args.end or args.date or dr.resolve_date(None)
    if args.start:
        start = args.start
    elif trend:
        start = (common.parse_dt(end) - timedelta(days=6)).strftime("%Y-%m-%d")
    else:
        start = end
    return start, end


def find_pages(card, selector):
    pages = card.get("pages") or []
    if not selector:
        return pages
    selected = []
    for page in pages:
        if selector in (page.get("name"), page.get("spm_no")):
            selected.append(page)
        elif selector and selector in str(page.get("name") or ""):
            selected.append(page)
    return selected


def page_trend(card, page, start, end, env):
    spm = page.get("spm_no")
    pt = page.get("pt_action") or dr.guess_pt_action(spm)
    sql = das_query.render_sql(dr.read_sql("spm_pv_uv_trend.sql"), {
        "start_dt": start, "end_dt": end, "pt_action": pt, "spm_no": spm,
    })
    result = das_query.run_query(sql, env=env, limit=10000, timeout=300, catalog="hive_da_music")
    if not result.get("ok"):
        return {"name": page.get("name"), "spm_no": spm, "error": result.get("error")}
    return {"name": page.get("name"), "spm_no": spm, "pt_action": pt, "rows": result.get("rows") or []}


def activity_trend(card, activity_id, start, end, env):
    if not activity_id:
        return {"error": "no_activity_id"}
    das = (card.get("metrics") or {}).get("das") or {}
    sql = das_query.render_sql(dr.read_sql("activity_tag_trend.sql"), {
        "start_dt": start, "end_dt": end, "is_dawn": das.get("is_dawn", 0),
        "activity_id": activity_id,
    })
    result = das_query.run_query(sql, env=env, limit=10000, timeout=300)
    if not result.get("ok"):
        return {"error": result.get("error")}
    return {"rows": result.get("rows") or []}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("card")
    parser.add_argument("--pack", default="overview", choices=["overview", "page", "trend", "total"])
    parser.add_argument("--date", default=None)
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--page", default=None, help="页面名或 spm_no")
    parser.add_argument("--data", default=None, help="自定义数据 JSON")
    args = parser.parse_args()

    card = common.load_json(args.card)
    if not card:
        print("读不到名片: " + args.card, file=sys.stderr)
        return 2
    env = (card.get("platform") or {}).get("env") or "online"
    date = args.date or dr.resolve_date(None)
    activity_id, id_error = dr.resolve_activity_id(card, date, env)
    pages = find_pages(card, args.page)
    extra = common.load_json(args.data, {}) if args.data else {}

    if args.pack == "overview":
        activity, activity_error = dr.query_activity_daily(card, date, env, activity_id)
        page_results = []
        for page in pages:
            row, error, approx = dr.query_page(card, page, date, env)
            page_results.append({
                "name": page.get("name"), "spm_no": page.get("spm_no"),
                "pt_action": page.get("pt_action") or dr.guess_pt_action(page.get("spm_no")),
                "row": row, "error": error, "approx": approx,
            })
        first = next((p for p in page_results if p.get("row")), None)
        total_pv, total_uv, total_error = dr.query_total(card, date, env, activity_id, first)
        result = {
            "ok": True, "pack": "overview", "date": date, "activityId": activity_id,
            "activity": activity, "activityError": activity_error,
            "pages": page_results,
            "total": {"pv": total_pv, "uv": total_uv, "error": total_error},
            "custom": extra,
        }
    elif args.pack == "page":
        start, end = resolve_range(args)
        if start == end:
            result = {"ok": True, "pack": "page", "date": date, "pages": []}
            for page in pages:
                row, error, approx = dr.query_page(card, page, date, env)
                result["pages"].append({
                    "name": page.get("name"), "spm_no": page.get("spm_no"),
                    "pt_action": page.get("pt_action") or dr.guess_pt_action(page.get("spm_no")),
                    "row": row, "error": error, "approx": approx,
                })
        else:
            result = {"ok": True, "pack": "page", "start": start, "end": end,
                      "pages": [page_trend(card, p, start, end, env) for p in pages]}
    elif args.pack == "trend":
        start, end = resolve_range(args, trend=True)
        if pages:
            result = {"ok": True, "pack": "trend", "start": start, "end": end,
                      "type": "page", "pages": [page_trend(card, p, start, end, env) for p in pages]}
        else:
            result = {"ok": True, "pack": "trend", "start": start, "end": end,
                      "type": "activity", "activityId": activity_id,
                      "activity": activity_trend(card, activity_id, start, end, env), "idError": id_error}
    else:
        first = None
        for page in pages:
            row, _, _ = dr.query_page(card, page, date, env)
            if row:
                first = {"row": row, "spm_no": page.get("spm_no"), "pt_action": page.get("pt_action")}
                break
        total_pv, total_uv, total_error = dr.query_total(card, date, env, activity_id, first)
        result = {"ok": True, "pack": "total", "activityId": activity_id,
                  "start": str((card.get("lifecycle") or {}).get("start") or "")[:10],
                  "end": date, "pv": total_pv, "uv": total_uv, "error": total_error}

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
