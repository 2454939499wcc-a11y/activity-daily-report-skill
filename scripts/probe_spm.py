#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为名片 pages 自动补 pt_action。

规则:
    page_* -> _pv
    mod_*  -> _ev
    btn_*  -> _ec
其他 SPM 可加 --verify 实际查询探测。
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import das_query

CANDIDATES = ["_pv", "_ev", "_ec", "_pd", "_es", "_hover", "_elc"]


def guess(spm):
    spm = str(spm or "")
    if spm.startswith("page_"):
        return "_pv"
    if spm.startswith("mod_"):
        return "_ev"
    if spm.startswith("btn_"):
        return "_ec"
    return None


def exists(spm, pt_action, date, env):
    sql = das_query.render_sql(
        "select 1 as ok from music_dws.dws_log_music_user_spm_di "
        "where dt = '${dt}' and pt_action = '${pt_action}' and spm_no = '${spm_no}' limit 1",
        {"dt": date, "pt_action": pt_action, "spm_no": spm},
    )
    for catalog in (None, "hive_da_music"):
        result = das_query.run_query(sql, env=env, limit=1, timeout=90, catalog=catalog)
        if result.get("ok") and result.get("rows"):
            return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("card")
    parser.add_argument("--date", default=None)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    card = common.load_json(args.card)
    if not card:
        print("读不到名片: " + args.card, file=sys.stderr)
        return 2
    date = args.date or (datetime.now(common.CST) - timedelta(days=1)).strftime("%Y-%m-%d")
    env = (card.get("platform") or {}).get("env") or "online"
    report = []

    for page in card.get("pages") or []:
        spm = page.get("spm_no")
        current = page.get("pt_action")
        if current and not args.force:
            report.append({"spm_no": spm, "pt_action": current, "source": "existing"})
            continue
        candidate = guess(spm)
        source = "guess"
        if args.verify:
            if candidate and exists(spm, candidate, date, env):
                source = "verified"
            else:
                source = "probe"
                candidate = None
                for item in CANDIDATES:
                    if exists(spm, item, date, env):
                        candidate = item
                        break
        if candidate:
            page["pt_action"] = candidate
        report.append({"spm_no": spm, "pt_action": candidate, "source": source})

    common.save_json(args.card, card)
    print(json.dumps({"ok": True, "date": date, "pages": report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
