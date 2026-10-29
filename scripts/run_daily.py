#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地每日播报 runner（launchd 调用）。

1. 调 daily_report.py 生成日报
2. skipped / hasMessages=false 直接退出
3. 通过 popo-cli 发群（本机无 popo_group 库）
4. 发送成功后 commit_daily_state.py
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import custom_data

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def log(msg):
    print("[%s] %s" % (datetime.now(common.CST).strftime("%Y-%m-%d %H:%M:%S"), msg), flush=True)


def run_report(card, date, state, cache, data=None, force=False):
    cmd = [sys.executable, os.path.join(SKILL, "scripts", "daily_report.py"), card, "--date", date]
    if state:
        cmd += ["--state", state]
    if cache:
        cmd += ["--cache", cache]
    if data:
        cmd += ["--data", data]
    if force:
        cmd += ["--force"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if proc.returncode != 0:
        return None, "daily_report exit %d: %s" % (proc.returncode, (proc.stderr or "").strip()[:400])
    try:
        return json.loads(proc.stdout), None
    except Exception:
        return None, "daily_report 输出非 JSON: %s" % (proc.stdout or proc.stderr or "")[:400]


def render_text(msg):
    """模板 head 自带【】，不能再包一层。"""
    parts = []
    head = msg.get("head") or ""
    lines = [str(x) for x in (msg.get("lines") or [])]
    if head:
        parts.append(head)
        if lines:
            parts.append("")
    parts.extend(lines)
    return "\n".join(parts)


def send_via_popo_cli(text, tid):
    fd, path = tempfile.mkstemp(prefix="daily-msg-", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        cmd = ["popo-cli", "popo", "message_send_team",
               "message=@text:%s" % path, "receiver=%s" % tid, "source=AGENT"]
        env = dict(os.environ)
        env["PATH"] = "/opt/homebrew/bin:/Users/admin/.local/bin:" + env.get("PATH", "")
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env)
        out = (proc.stdout or "").strip()
        if proc.returncode != 0:
            return False, "popo-cli exit %d: %s" % (proc.returncode, (out or proc.stderr)[:400])
        try:
            data = json.loads(out)
        except Exception:
            return False, "popo-cli 输出非 JSON: %s" % out[:400]
        if not data.get("ok"):
            return False, "popo-cli 失败: %s" % json.dumps(data, ensure_ascii=False)[:400]
        return True, None
    finally:
        if os.path.exists(path):
            os.unlink(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("card")
    parser.add_argument("--date", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    card = common.load_json(args.card)
    if not card:
        log("读不到名片: %s" % args.card)
        return 2
    name = card.get("name")
    state = os.path.join(SKILL, "state", "%s.json" % name)
    cache = os.path.join(SKILL, "state", "%s.cache.json" % name)
    date = args.date or (datetime.now(common.CST).replace(hour=0, minute=0, second=0, microsecond=0)
                         - common.timedelta(days=1)).strftime("%Y-%m-%d")
    tid = str((card.get("broadcast") or {}).get("groupId") or "")
    if not tid:
        log("名片缺 broadcast.groupId")
        return 2

    env = (card.get("platform") or {}).get("env") or "online"
    custom_values, custom_errors = custom_data.collect(card, env=env)
    for key, err in custom_errors.items():
        log("自定义数据 %s 取数失败: %s（日报显示 -）" % (key, err))
    data_path = None
    if custom_values:
        fd, data_path = tempfile.mkstemp(prefix="daily-data-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(custom_values, f, ensure_ascii=False)
        log("自定义数据: %s" % json.dumps(custom_values, ensure_ascii=False))

    msg, err = run_report(args.card, date, state, cache, data=data_path, force=args.force)
    if data_path and os.path.exists(data_path):
        os.unlink(data_path)
    if err:
        log("生成失败: %s" % err)
        return 1
    if msg.get("skipped"):
        log("跳过: %s (%s)" % (msg["skipped"], date))
        return 0
    if not msg.get("hasMessages"):
        log("无数据: %s" % date)
        return 0

    text = render_text(msg)
    if args.dry_run:
        log("dry-run 不发送,内容:\n%s" % text)
        return 0

    ok, send_err = send_via_popo_cli(text, tid)
    if not ok:
        log("发送失败: %s（state 不写，下次重试）" % send_err)
        return 1
    log("已发送到群 %s: %s" % (tid, date))
    proc = subprocess.run([sys.executable, os.path.join(SKILL, "scripts", "commit_daily_state.py"),
                           state, date], capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        log("state 写入失败: %s" % ((proc.stderr or proc.stdout) or "")[:300])
        return 1
    log("state 已更新: %s" % date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
