#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据更新管线入口：抓 POI -> 抓爱跑98命中 -> 抓中石化官方售卡网点 -> 清洗 -> 官方名单匹配

用法（本机执行，key 不入仓库）：
  方式一：set AMAP_KEY=<你的高德key> && python run_all.py
  方式二：把 key 写入 scripts/.amap_key 文件（已被 .gitignore 排除）

完整管线：
  1. fetch_pois.py        抓高德 010101 中石化 POI（需 AMAP_KEY）
  2. fetch_aipao_hits.py  抓高德关键词"爱跑98"命中（需 AMAP_KEY，弱信号）
  3. fetch_official_gd.py 抓中石化加油卡网上营业厅广东全省售卡网点（无需 key）
  4. build_stations.py    合并 raw_pois + manual_overrides -> stations.json
  5. match_official_gd.py 用官方名单匹配并升级 status（confirmed/unverified/unlikely）

按需重跑：
  - 仅刷官方名单：python fetch_official_gd.py && python match_official_gd.py
  - 仅刷 POI：     python fetch_pois.py && python fetch_aipao_hits.py && python build_stations.py && python match_official_gd.py
  - 完整刷新：     python run_all.py

人工核验某站：编辑 data/manual_overrides.json 加一条（status + note），重跑 build_stations.py + match_official_gd.py。
"""
import subprocess
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))

STEPS = [
    "fetch_pois.py",
    "fetch_aipao_hits.py",
    "fetch_official_gd.py",
    "build_stations.py",
    "match_official_gd.py",
]

for script in STEPS:
    print(f"===== {script} =====")
    r = subprocess.run([sys.executable, os.path.join(HERE, script)])
    if r.returncode != 0:
        sys.exit(f"{script} 执行失败，管线中止")
print("全部完成。请检查 data/stations.json 并提交。")
