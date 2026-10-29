-- 活动标签表日指标
-- 参数: dt, is_dawn, activity_id
SELECT activity_page_cnt_1d,
       activity_page_unt_1d,
       activity_active_cnt_1d,
       activity_active_unt_1d,
       activity_share_cnt_1d,
       activity_share_unt_1d,
       play_pv_num,
       play_uv_num,
       like_pv_num,
       like_uv_num
FROM music_new_dm.ads_log_h5_activity_tag_di
WHERE dt = '${dt}'
  AND is_dawn = ${is_dawn}
  AND activity_id = '${activity_id}'
LIMIT 10;
