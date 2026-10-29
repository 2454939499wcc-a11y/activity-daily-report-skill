#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发送 POPO rich_text。

用法:
    python3 send_rich_text.py --file msg.json <tid>
    python3 send_rich_text.py '<message_json>' <tid> --dry-run
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common


def node(text, style=None, href=None):
    item = {"tag": "text", "text": text}
    if style:
        item["style"] = style
    if href:
        item["href"] = href
    return item


def build(msg):
    content = []
    head = msg.get("head") or ""
    lines = msg.get("lines") or []
    if head:
        content.append(node("【%s】\n" % head, "bold"))
    for i, line in enumerate(lines):
        content.append(node(str(line) + ("\n" if i < len(lines) - 1 else "")))
    return content


def send(content, tid):
    for path in (os.environ.get("POPO_PYTHONPATH"),
                 "/home/appops/.local/lib/python3.11/site-packages"):
        if path and path not in sys.path:
            sys.path.insert(0, path)
    from popo_group.api import call_team_api
    return call_team_api("send-msg", {
        "tid": tid,
        "msgType": "rich_text",
        "message": {"content": content},
    })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("message", nargs="?")
    parser.add_argument("tid", nargs="?")
    parser.add_argument("--file", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.file:
        msg = common.load_json(args.file)
        tid = args.tid or args.message
    elif args.message:
        msg = json.loads(args.message)
        tid = args.tid
    else:
        print("需要 message 或 --file", file=sys.stderr)
        return 2
    if msg is None:
        print("消息为空", file=sys.stderr)
        return 2

    content = build(msg)
    if args.dry_run:
        print(json.dumps(content, ensure_ascii=False, indent=2))
        return 0
    if not tid:
        print("缺少群号 tid", file=sys.stderr)
        return 2
    try:
        result = send(content, tid)
    except Exception as exc:
        print("发送失败: %s" % exc, file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
