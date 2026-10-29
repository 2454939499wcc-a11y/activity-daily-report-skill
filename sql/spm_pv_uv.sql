-- 单个页面 SPM 的日 PV / UV
-- 参数: dt, pt_action, spm_no
SELECT SUM(pv)                 AS pv,
       COUNT(DISTINCT user_id) AS uv
FROM music_dws.dws_log_music_user_spm_di
WHERE dt = '${dt}'
  AND pt_action = '${pt_action}'
  AND spm_no = '${spm_no}';
