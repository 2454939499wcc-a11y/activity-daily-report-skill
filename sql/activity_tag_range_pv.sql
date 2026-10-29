-- 活动累计页面 PV
-- 参数: start_dt, end_dt, is_dawn, activity_id
SELECT SUM(activity_page_cnt_1d) AS page_pv
FROM music_new_dm.ads_log_h5_activity_tag_di
WHERE dt BETWEEN '${start_dt}' AND '${end_dt}'
  AND is_dawn = ${is_dawn}
  AND activity_id = '${activity_id}';
