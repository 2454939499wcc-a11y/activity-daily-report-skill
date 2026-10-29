#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mws DAS 查询封装。

默认: mws music-das-mcp queryHiveDataWithOmni
指定 catalog: mws music-das-mcp queryData
"""
import json
import re
import subprocess


def render_sql(sql, params):
    def repl(match):
        key = match.group(1)
        if key not in params:
            raise RuntimeError("SQL 缺少参数: " + key)
        value = str(params[key])
        if any(bad in value for bad in (";", "--", "/*", "*/")):
            raise RuntimeError("参数含非法片段: " + key)
        return value.replace("'", "''")

    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", repl, sql)


def run_query(sql, env="online", limit=1000, timeout=300, catalog=None):
    body = {"sql": sql, "limit": int(limit)}
    if catalog:
        body["catalog"] = catalog
        sub = "queryData"
    else:
        sub = "queryHiveDataWithOmni"
    cmd = [
        "mws", "music-das-mcp", sub,
        "--env", env,
        "--reason", "activity-daily-report",
        "--json", json.dumps(body, ensure_ascii=False),
        "--format", "json",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except Exception as exc:
        return {"ok": False, "error": "exec_failed", "detail": str(exc)}

    out = (proc.stdout or "").strip()
    if proc.returncode != 0:
        return {"ok": False, "error": "mws_exit_%d" % proc.returncode,
                "detail": (out or proc.stderr or "")[:1000]}
    try:
        data = json.loads(out)
    except Exception:
        return {"ok": False, "error": "invalid_json", "detail": out[:1000]}
    if isinstance(data, dict):
        if data.get("error"):
            return {"ok": False, "error": "mws_error", "detail": data}
        for key in ("data", "result", "rows"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        return {"ok": False, "error": "unknown_shape", "detail": data}
    return {"ok": True, "rows": data, "count": len(data)}
