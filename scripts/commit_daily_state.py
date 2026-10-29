#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发送成功后记录 lastSentDate。"""
import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("state")
    parser.add_argument("date")
    args = parser.parse_args()
    state = common.load_json(args.state, {}) or {}
    state["lastSentDate"] = args.date
    state["lastSentAt"] = datetime.now(common.CST).strftime("%Y-%m-%d %H:%M:%S")
    common.save_json(args.state, state)
    print("state 已更新: lastSentDate=%s" % args.date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
