#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自定义数据取值。

名片 customMetrics[i].source 声明来源，支持：
  provider=owl_ddb：mws owl gateway-api-owl-query 查 DDB/MySQL
其余情况跳过，日报显示 "-"。

source 字段：
  host, port, dbType(ddb|mysql|oceanbase), schema, sql, field, tenant(可选)
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common


def run_owl(source, env="online", timeout=120):
    body = {
        "mode": "query",
        "host": str(source["host"]),
        "port": int(source["port"]),
        "dbType": source.get("dbType") or "ddb",
        "query": source["sql"],
    }
    if source.get("schema"):
        body["schema"] = source["schema"]
    if source.get("tenant"):
        body["tenant"] = source["tenant"]
    cmd = [
        "mws", "owl", "gateway-api-owl-query",
        "--env", env,
        "--reason", "activity-daily-report",
        "--json", json.dumps(body, ensure_ascii=False),
        "--format", "json",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    out = (proc.stdout or "").strip()
    if proc.returncode != 0:
        return None, (out or proc.stderr or "mws_exit_%d" % proc.returncode)[:400]
    try:
        data = json.loads(out)
    except Exception:
        return None, "invalid_json: %s" % out[:200]
    if data.get("code") != 200:
        return None, str(data.get("msg") or data)[:300]
    rows = ((data.get("data") or {}).get("dataResult") or [])
    if not rows:
        return None, "no_rows"
    return rows[0], None


def collect(card, env="online"):
    """返回 ({key: 显示值}, {key: 错误})。失败的 key 不进结果，日报显示 -。"""
    values = {}
    errors = {}
    for item in card.get("customMetrics") or []:
        key = item.get("key")
        source = item.get("source") or {}
        if not key or not source:
            continue
        provider = source.get("provider")
        if provider != "owl_ddb":
            errors[key] = "unsupported_provider:%s" % provider
            continue
        row, err = run_owl(source, env=env)
        if err:
            errors[key] = err
            continue
        field = source.get("field") or "c"
        raw = row.get(field)
        num = common.to_int(raw)
        values[key] = common.fmt_num(num) if num is not None else str(raw)
    return values, errors
