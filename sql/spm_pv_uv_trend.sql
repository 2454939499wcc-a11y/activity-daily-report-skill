-- 单个页面 SPM 的日趋势
-- 参数: start_dt, end_dt, pt_action, spm_no
SELECT dt,
       SUM(pv)                 AS pv,
       COUNT(DISTINCT user_id) AS uv
FROM music_dws.dws_log_music_user_spm_di
WHERE dt BETWEEN '${start_dt}' AND '${end_dt}'
  AND pt_action = '${pt_action}'
  AND spm_no = '${spm_no}'
GROUP BY dt
ORDER BY dt;
