# 活动名片字段

## 必填

- `name`：名片 / state 唯一标识
- `displayName`：日报标题
- `bizCode`：应用内业务码
- `lifecycle.start` / `lifecycle.end`：活动起止时间；长期活动 `end=permanent`
- `broadcast.groupId`：POPO 群 tid
- `broadcast.daily.cron`：日报时间，如 `0 10 * * *`
- `pages`：页面清单，按漏斗顺序

## 页面

```json
{
  "name": "首页",
  "spm_no": "page_xxx|page_h5_biz",
  "pt_action": "",
  "step": 1
}
```

- `pt_action` 留空，自动推断：
  - `page_*` → `_pv`
  - `mod_*` → `_ev`
  - `btn_*` → `_ec`
- 不认识的 SPM 跑 `probe_spm.py --verify`

## 活动总览

```json
"metrics": {
  "das": {
    "activity_id": "",
    "activity_name_keyword": "活动名关键词",
    "is_dawn": 0
  }
}
```

- `activity_id` 留空时按关键词反查
- `is_dawn` 默认 0；如果活动标签表里是 1，改成 1
- 查不到活动总览时，日报用第一个页面兜底 PV/UV

## 自定义数据

```json
"customMetrics": [
  {"key": "participate_uv", "label": "参与用户", "unit": "人"}
]
```

日报运行时用 `--data extra.json` 注入：

```json
{"participate_uv": "567151"}
```

缺失显示 `-`。
