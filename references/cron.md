# 日报 cron 与 state

## cron

```
sessionTarget=isolated
payload.kind=agentTurn
schedule.kind=cron
expr=<card.broadcast.daily.cron>
tz=Asia/Shanghai
```

`payload.message`：

```
读 <skill>/SKILL.md，按「每日播报」执行一轮。
名片：<card 绝对路径>
state：<state 绝对路径>
```

## state

```json
{
  "lastSentDate": "2026-10-28",
  "lastSentAt": "2026-10-29 10:00:12"
}
```

- `daily_report.py` 先读 state
- `lastSentDate == 查询日期` 时返回 `skipped=already_sent`
- 发送成功后跑 `commit_daily_state.py`
- 发送失败不写 state，下一轮重试

## 数据日期

日报查 T-1：

```bash
--date <昨天>
```

今天分区可能还没出，不要查今天。

## 生命周期

`lifecycle.start` 前、`lifecycle.end` 后自动返回：

```json
{"skipped": "outside_lifecycle"}
```

## 失败处理

- 单页失败：标 `⚠️无数据`，其他页继续
- 活动总览失败：用第一个页面兜底
- 累计 UV 失败：显示 `-` 或用 `--cache` 的 `_total`
- mws `transportError`：该页标 `⚠️`，不阻塞整份日报
