---
name: activity-daily-report
description: >
  通用活动每日数据播报。新活动接入时主动收集活动名、起止时间、POPO 群号、日报时间、页面 SPM 清单、
  自定义数据项；自动推断 pt_action、自动反查 activity_id，生成名片并创建每日 cron。
  日报固定查询页面 PV/UV、活动总览、累计 PV/UV，并按用户自定义字段补充播报。
  触发词：接入新活动、活动日报、每日播报、活动数据播报、配置活动日报。
metadata:
  openclaw:
    emoji: "📊"
---

# activity-daily-report — 通用活动日报

一个活动一张名片。新活动只填名片，不改脚本。

## 一、新活动接入

用户说「接入新活动」后，主动问：

```
给我这几项就能接入：
1. 活动中文名
2. 开始时间、结束时间（长期活动结束填 permanent）
3. 播报 POPO 群号（纯数字 tid）
4. 每天几点播报（默认 10:00）
5. 页面清单，按漏斗顺序：
   页面名 | spm_no
6. 自定义数据项（可选）：
   显示名 | 字段名 | 单位
   例：参与用户 | participate_uv | 人

可选：
- 活动名关键词（自动反查 activity_id）
- 应用名（默认 music-content-activity-home）
```

不填 SQL、不填 `pt_action`、不填表名。

流程：

1. 复制 `cards/_template.json` 生成名片。
2. `probe_spm.py` 自动补 `pt_action`。
3. `daily_report.py` 自动反查 `activity_id`。
4. `validate_card.py` 校验。
5. 用昨天数据预览。
6. 用户确认后建 cron。

## 二、名片

```json
{
  "name": "xxx",
  "displayName": "活动名",
  "bizCode": "xxx",
  "status": "active",
  "lifecycle": {
    "start": "2026-11-10 00:00:00",
    "end": "permanent"
  },
  "platform": {
    "appNames": ["music-content-activity-home"],
    "env": "online"
  },
  "broadcast": {
    "groupId": "1234567",
    "daily": {
      "enabled": true,
      "cron": "0 10 * * *",
      "template": "daily_generic",
      "includeTotal": true
    }
  },
  "metrics": {
    "provider": "das",
    "das": {
      "table": "music_new_dm.ads_log_h5_activity_tag_di",
      "activity_id": "",
      "activity_name_keyword": "活动名关键词",
      "is_dawn": 0
    }
  },
  "pages": [
    {"name": "首页", "spm_no": "page_xxx|page_h5_biz", "pt_action": "", "step": 1},
    {"name": "结果页", "spm_no": "page_xxx_result|page_h5_biz", "pt_action": "", "step": 2}
  ],
  "customMetrics": [
    {"key": "participate_uv", "label": "参与用户", "unit": "人"}
  ]
}
```

## 三、固定查询口径

### 页面 PV/UV

表：`music_dws.dws_log_music_user_spm_di`

```sql
SELECT SUM(pv) AS pv,
       COUNT(DISTINCT user_id) AS uv
FROM music_dws.dws_log_music_user_spm_di
WHERE dt = '${dt}'
  AND pt_action = '${pt_action}'
  AND spm_no = '${spm_no}';
```

- `pt_action` 自动推断：`page_*` → `_pv`，`mod_*` → `_ev`，`btn_*` → `_ec`
- 一个页面一条 SQL
- 大分区走 `--catalog hive_da_music`
- `COUNT(DISTINCT)` 超时自动退化近似 UV

### 活动总览

表：`music_new_dm.ads_log_h5_activity_tag_di`

```sql
WHERE dt = '${dt}'
  AND is_dawn = ${is_dawn}
  AND activity_id = '${activity_id}'
```

- `activity_id` 为空时按 `activity_name_keyword` 反查
- `is_dawn` 默认 0，不同活动可能为 1
- 查不到活动总览时，用第一个页面兜底 PV/UV

### 累计 PV/UV

- 累计 PV：`SUM(activity_page_cnt_1d)`，跨天可加
- 累计 UV：用户明细表 `COUNT(DISTINCT user_id)`，30 天分段 `UNION ALL` 后统一去重
- 不在活动标签表的活动：用第一个页面 SPM 做累计兜底

## 四、日报模板

`templates/daily_generic.json`

```
【{活动名} 日报】{date}

◆ 当日活动
PV / UV
参与 UV / 分享 UV
播放 UV / 红心 UV

◆ 活动累计（{start} ~ {end}）
PV / UV

◆ 页面漏斗
1. 首页：PV / UV
2. 结果页：PV / UV｜转化率
...

◆ 自定义数据
{用户定义的行}

统计口径：数据分区 {date}
```

自定义数据为空时，整个「自定义数据」区块省略。

## 五、自定义数据

名片声明字段：

```json
"customMetrics": [
  {"key": "participate_uv", "label": "参与用户", "unit": "人"},
  {"key": "submit_fail_cnt", "label": "提交校验失败", "unit": "次"}
]
```

日报运行时通过 `--data` 注入：

```json
{
  "participate_uv": "567,151",
  "submit_fail_cnt": "944"
}
```

```bash
python3 scripts/daily_report.py <card> --date 2026-10-28 --data extra.json
```

- 缺失字段显示 `-`
- 不编数据
- 数据源可以是应用只读 ops 接口、业务表、mlog；skill 只负责渲染

## 六、每日播报

用 `mws_exec` 跑：

```bash
python3 <skill>/scripts/daily_report.py <card> \
  --date <昨天> \
  --state <state> \
  --cache <cache> \
  --data <extra.json>
```

- `skipped=already_sent`：今天已发，回复 `NO_REPLY`
- `skipped=outside_lifecycle`：活动不在生命周期，回复 `NO_REPLY`
- `hasMessages=false`：无数据，回复 `NO_REPLY`
- 有消息：用 `fabric_exec` 跑 `send_rich_text.py` 发群
- 发送成功后跑 `commit_daily_state.py`

## 七、查询

固定查询包，AI 只选包、填日期/页面，不写 SQL。

### overview

活动总览 + 页面漏斗 + 累计：

```bash
python3 scripts/query_activity.py <card> --pack overview --date 2026-10-28
```

### page

单页面 PV/UV：

```bash
python3 scripts/query_activity.py <card> --pack page --page 首页 --date 2026-10-28
```

### trend

趋势：

```bash
python3 scripts/query_activity.py <card> --pack trend --page 首页 \
  --start 2026-10-21 --end 2026-10-28
```

不传 `--page` 时查活动总览趋势。

### total

活动累计 PV/UV：

```bash
python3 scripts/query_activity.py <card> --pack total
```

### 自然语言映射

- 「昨天活动怎么样」：`overview --date 昨天`
- 「首页昨天 PV/UV」：`page --page 首页 --date 昨天`
- 「近 7 天趋势」：`trend --start ... --end ...`
- 「活动累计 PV/UV」：`total`
- 「自定义指标」：`--data extra.json` 注入，或先接业务只读接口

查询只读，不发群。用户级查询要脱敏、审计。

## 八、cron

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

## 九、边界

- mws 查询用 `forDe=false`。
- 发送用 `fabric_exec`。
- 不直连数据库，不让 LLM 写 SQL。
- 一个活动一张名片、一个 state、一个 cron。
- 同一天只发一次。
- 活动结束后按 `lifecycle.end` 自动静默。
- 自定义数据没有来源时显示 `-`，不编。

## 十、文件

```
SKILL.md
schema/activity.schema.json
cards/_template.json
scripts/common.py
scripts/das_query.py
scripts/daily_report.py
scripts/query_activity.py
scripts/probe_spm.py
scripts/validate_card.py
scripts/send_rich_text.py
scripts/commit_daily_state.py
sql/spm_pv_uv.sql
sql/spm_pv_uv_range.sql
sql/activity_tag_daily.sql
sql/activity_tag_find.sql
sql/activity_tag_range_pv.sql
templates/daily_generic.json
references/card-guide.md
references/cron.md
```
