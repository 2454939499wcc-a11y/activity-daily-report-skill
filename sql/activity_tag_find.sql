-- 按活动名找 activity_id
-- 参数: dt, is_dawn, keyword
SELECT DISTINCT activity_id,
       activity_name
FROM music_new_dm.ads_log_h5_activity_tag_di
WHERE dt = '${dt}'
  AND is_dawn = ${is_dawn}
  AND activity_name LIKE '%${keyword}%'
LIMIT 50;
