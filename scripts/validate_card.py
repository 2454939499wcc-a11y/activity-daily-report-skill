#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""活动日报名片校验。"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def blank(value):
    return value is None or value == "" or value == [] or value == {}


def validate(card):
    errors = []
    missing = []
    warnings = []

    if not isinstance(card, dict):
        return {"ok": False, "activatable": False, "errors": ["名片不是 JSON 对象"],
                "missing": [], "warnings": []}

    for field in ("name", "displayName", "bizCode"):
        if blank(card.get(field)):
            errors.append("缺少 " + field)

    status = card.get("status") or "draft"
    if status not in ("draft", "active"):
        errors.append("status 只能是 draft 或 active")

    life = card.get("lifecycle") or {}
    start = common.parse_dt(life.get("start"))
    end_perm = common.is_permanent(life.get("end"))
    end = None if end_perm else common.parse_dt(life.get("end"))
    if blank(life.get("start")):
        missing.append("lifecycle.start")
    elif not start:
        errors.append("lifecycle.start 格式不对")
    if blank(life.get("end")):
        missing.append("lifecycle.end")
    elif not end_perm and not end:
        errors.append("lifecycle.end 格式不对，用日期或 permanent")
    if start and end and start >= end:
        errors.append("lifecycle.start 必须早于 lifecycle.end")

    broadcast = card.get("broadcast") or {}
    if blank(broadcast.get("groupId")):
        missing.append("broadcast.groupId")
    daily = broadcast.get("daily") or {}
    if blank(daily.get("cron")):
        missing.append("broadcast.daily.cron")
    template = daily.get("template") or "daily_generic"
    if not os.path.exists(os.path.join(BASE, "templates", template + ".json")):
        errors.append("模板不存在: templates/%s.json" % template)

    pages = card.get("pages") or []
    if not pages:
        missing.append("pages")
    for i, page in enumerate(pages):
        prefix = "pages[%d]" % i
        if blank(page.get("name")):
            errors.append(prefix + ".name 必填")
        if blank(page.get("spm_no")):
            errors.append(prefix + ".spm_no 必填")
        if blank(page.get("pt_action")):
            warnings.append(prefix + ".pt_action 为空，接入时会按前缀自动推断")

    das = (card.get("metrics") or {}).get("das") or {}
    if blank(das.get("activity_id")) and blank(das.get("activity_name_keyword")):
        warnings.append("activity_id 和 activity_name_keyword 都为空，只能按页面兜底活动总览")
    if das.get("is_dawn") not in (None, 0, 1):
        errors.append("metrics.das.is_dawn 只能是 0 或 1")

    for i, item in enumerate(card.get("customMetrics") or []):
        prefix = "customMetrics[%d]" % i
        if blank(item.get("key")):
            errors.append(prefix + ".key 必填")
        if blank(item.get("label")):
            warnings.append(prefix + ".label 为空，将显示 key")

    missing = list(dict.fromkeys(missing))
    warnings = list(dict.fromkeys(warnings))
    return {
        "ok": not errors,
        "activatable": not errors and not missing,
        "errors": errors,
        "missing": missing,
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("card")
    parser.add_argument("--require-active", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    card = common.load_json(args.card)
    if not card:
        print("读不到名片: " + args.card, file=sys.stderr)
        return 2
    result = validate(card)
    result["card"] = args.card
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("名片: " + args.card)
        print("结构: " + ("通过" if result["ok"] else "不通过"))
        print("上线: " + ("可以" if result["activatable"] else "还不行"))
        if result["errors"]:
            print("\n必须修复:")
            for x in result["errors"]:
                print("- " + x)
        if result["missing"]:
            print("\n上线前要补:")
            for x in result["missing"]:
                print("- " + x)
        if result["warnings"]:
            print("\n提示:")
            for x in result["warnings"]:
                print("- " + x)
    if not result["ok"]:
        return 1
    if args.require_active and not result["activatable"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
