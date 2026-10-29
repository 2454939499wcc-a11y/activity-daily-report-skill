-- 活动标签表日趋势
-- 参数: start_dt, end_dt, is_dawn, activity_id
SELECT dt,
       activity_page_cnt_1d   AS pv,
       activity_page_unt_1d   AS uv,
       activity_active_unt_1d AS active_uv,
       activity_share_unt_1d  AS share_uv,
       play_uv_num,
       like_uv_num
FROM music_new_dm.ads_log_h5_activity_tag_di
WHERE dt BETWEEN '${start_dt}' AND '${end_dt}'
  AND is_dawn = ${is_dawn}
  AND activity_id = '${activity_id}'
ORDER BY dt;
